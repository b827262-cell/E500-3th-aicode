# Multi-Agent Programming Workflow

## 1. 目的

本文件定義 `e500-codex-smoke` 專案中的多方 AI 協作編程方式，讓 GPT / Codex、Hermes、Gemini 在同一個 Meeting Room / Telegram 流程中分工、互相審查、提出修正，最後由單一執行者套用變更並完成驗收。

核心原則：

1. 一個任務，一個主責 Agent
2. 其他 Agent 只做審查、補充或反證
3. 任何修改都必須有明確 owner
4. 禁止多個 Agent 同時直接修改同一檔案
5. 所有變更都必須經測試與 Live Acceptance
6. Secret 不進 prompt、不進 log、不進 Git

## 2. Agent 角色

### GPT / Codex

定位：**主程式設計師 / 執行者**

主要任務：

- 讀取專案結構
- 實作功能
- 修改程式碼
- 執行測試
- 修復 regression
- 建立 patch / commit
- 整合其他 Agent 的建議

### Hermes

定位：**系統工程師 / Linux 與執行環境審查者**

主要任務：

- Linux / systemd / service 診斷
- process / PID / restart / journal 分析
- shell command 審查
- deployment path 驗證
- runtime / `.env` / permission 檢查

Hermes 原則上不直接修改主程式碼，除非明確指派。

### Gemini

定位：**第二審查者 / API 與架構反證者**

主要任務：

- API schema 檢查
- edge cases
- OpenAPI / payload contract
- alternate implementation
- 找出 Codex 可能忽略的錯誤
- 針對既有方案提出反例

Gemini 原則上先做 review，不直接與 Codex 同時修改同一檔案。

## 3. 多方編程基本模式

```text
使用者
   │
   ▼
Meeting Room
   │
   ├── GPT / Codex  ── 主實作
   ├── Hermes       ── Linux / runtime review
   └── Gemini       ── API / logic review
   │
   ▼
Codex 整合
   │
   ▼
測試
   │
   ▼
Live Acceptance
```

## 4. 任務生命週期

### Phase 1：任務定義

```text
TASK_ID: MR-001
GOAL: 修正 Telegram → Meeting API HTTP 422
OWNER: GPT/Codex
REVIEWERS: Hermes, Gemini
FILES:
- adapters/telegram.py
- bridge/meeting.py
ACCEPTANCE:
- tests pass
- service active
- polling process = 1
- /gpt returns GPT_OK
```

### Phase 2：主責分析

```text
/gpt
分析目前 Telegram → Meeting API 失敗原因。
先只診斷，不修改。
請回報：
1. root cause
2. affected files
3. minimal patch
4. acceptance test
```

### Phase 3：交叉審查

Hermes：

```text
/hermes
Review the proposed fix.
Focus on:
- Linux/systemd/runtime impact
- environment variables
- service restart risk
- rollback
Do not modify files.
```

Gemini：

```text
/gemini
Review the proposed fix.
Focus on:
- API contract
- payload schema
- edge cases
- regression risk
Do not modify files.
```

## 5. 決策規則

若三方意見一致，直接由 Codex 實作。

若意見不同，不得三邊一起改，必須建立 decision table：

| 方案 | 風險 | 影響範圍 | 是否改 API contract | 建議 |
|---|---:|---:|---:|---|
| client 轉型 | 低 | 小 | 否 | 採用 |
| systemd workaround | 中 | 中 | 否 | 不採用 |
| API schema 放寬 | 中 | 大 | 是 | 不採用 |

優先順序：

```text
最小修改
> 不破壞 contract
> 可測試
> 可 rollback
> 才考慮大改
```

## 6. 單一寫入者原則

同一時間只能有一個 Agent 有權修改程式碼。

```text
Writer: GPT/Codex
Reviewer 1: Hermes
Reviewer 2: Gemini
```

避免：

- overwrite
- race condition
- patch conflict
- regression 無法歸因

## 7. 最終整合

收到三方意見後，只由 Codex 進行最終整合：

```text
/gpt
TASK MR-002 FINALIZE

Integrate only accepted review findings.

Before modification:
- list accepted suggestions
- list rejected suggestions with reason

Then:
- implement
- run tests
- restart only required services
- perform acceptance checks
```

## 8. 測試層級

### Level 1：Unit Test

```bash
pytest -q
```

### Level 2：Integration Test

驗證：

```text
Telegram adapter
→ Meeting client
→ Meeting API
```

### Level 3：Service Test

```bash
systemctl --user show gpt-codex-telegram.service \
  -p ActiveState \
  -p SubState \
  -p MainPID \
  -p NRestarts
```

應符合：

```text
ActiveState=active
SubState=running
NRestarts=0
```

Polling process：

```bash
pgrep -af 'python3 -m adapters.telegram'
```

必須只有一個。

### Level 4：Live E2E

```text
/gpt Reply exactly GPT_OK
/hermes Reply exactly HERMES_OK
/gemini Reply exactly GEMINI_OK
```

只有實際 Telegram inbound/outbound 成功才算 E2E PASS。

API health 200 不能取代 Telegram live acceptance。

## 9. Failure Handling

任何 Agent 發現 failure 時：

1. 保留現場
2. 不大範圍重構
3. 不一次改多個 subsystem
4. 先取得 evidence
5. 建立最小 root cause
6. 只修一層
7. 重新驗收

錯誤分類：

```text
AUTH
SCHEMA
ROUTE
PROVIDER
RUNTIME
SYSTEMD
NETWORK
APPLICATION
```

## 10. Secret 管理

禁止：

```text
把 API key 貼到 Telegram
把 token 放入 Agent prompt
把 secret 印到 journal
把 .env commit 到 git
```

允許只回報：

```text
MEETING_API_TOKEN:
present=yes
length=<N>
```

建議：

```bash
chmod 600 .env
```

各 provider 的 credential 應由自己的 service 管理，不要全部集中放在 Telegram bridge `.env`。

## 11. Git 工作方式

每個 task 建議獨立 branch：

```bash
git switch -c task/MR-002
```

完成後：

```bash
git status
git diff
pytest -q
```

Commit：

```bash
git add <changed-files>
git commit -m "fix: normalize telegram ids for meeting api"
```

## 12. Review 報告格式

```text
TASK:
MR-002

RESULT:
APPROVE / REQUEST_CHANGES

FINDINGS:
1.
2.
3.

CRITICAL:
none

RECOMMENDED_PATCH:
...

REGRESSION_RISK:
low / medium / high
```

## 13. 最終驗收格式

```text
TASK:
MR-002

IMPLEMENTER:
GPT/Codex

REVIEW:
Hermes: PASS
Gemini: PASS

TESTS:
PASS

SERVICE:
active/running

NRestarts:
0

Polling:
1

LIVE:
GPT: PASS
Hermes: PASS
Gemini: PASS

OVERALL:
PASS
```

## 14. 核心原則

多 Agent 的價值不是「三個 AI 同時寫 code」。

真正有效的模式是：

```text
一個負責寫
兩個負責挑錯
一個流程負責裁決
測試負責證明
```

最終標準永遠是：

> **不是 Agent 說修好了，而是測試與 Live Acceptance 證明修好了。**
