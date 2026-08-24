# AI Agent Loop Schedule

## 目的

建立 E500 多 Agent 程式開發循環，固定由三個角色依序完成：

1. GPT / Codex：負責編程與主要實作
2. AGY / Gemini：負責審驗、驗證與找問題
3. Claude：負責最終結論、修護、收尾、GitHub 上傳與產生 Markdown 紀錄

核心原則：**GPT 寫、AGY 驗、Claude 收尾。**

---

## Loop 流程

```text
使用者 / Telegram Task
        ↓
1. GPT / Codex
   編程 / 修正 / 測試
        ↓
2. AGY
   Review / 驗證 / 找漏洞
        ↓
3. Claude
   整合 AGY findings
   修護必要問題
   最終測試
   Git commit / push
   產生 Markdown 報告
        ↓
PASS → 結束
FAIL → 回到 GPT / Codex 下一輪
```

---

## Stage 1：GPT / Codex 編程

Telegram 入口：

```text
/gpt <task>
```

執行路徑：

```text
/gpt
→ Job Queue
→ provider=codex
→ runner=codex
→ codex exec
→ workspace-write
→ 自動結果回 Telegram
```

### GPT 任務

- 分析需求
- 設計最小修改方案
- 修改程式
- 新增/更新測試
- 執行專案 smoke test
- 不 commit
- 不 push
- 不宣告最終 PASS

### 建議 Prompt

```text
/gpt LOOP TASK <TASK-ID> STAGE 1

ROLE: LEAD DEVELOPER

GOAL:
<任務內容>

請：
1. 分析需求
2. 做 minimal implementation
3. 新增或更新 tests
4. 執行正式 smoke test
5. 回報 changed files

禁止：
- unrelated refactor
- 輸出 secret
- commit
- push

最後輸出：
TASK: <TASK-ID>
STAGE: GPT_IMPLEMENT
RESULT: PASS / FAIL / BLOCKED
CHANGED_FILES:
...
TESTS: PASS / FAIL
READY_FOR_AGY: YES / NO
```

只有 `READY_FOR_AGY: YES` 才進入 Stage 2。

---

## Stage 2：AGY 審驗

Telegram 入口：

```text
/agy <task>
```

執行路徑：

```text
/agy
→ Job Queue
→ provider=agy
→ runner=agy
→ agy -p
→ Google AI Pro OAuth
→ gemini-3.7-flash-high
→ 自動結果回 Telegram
```

### AGY 任務

- 不做主要功能開發
- Review GPT 修改
- 找 regression
- 找 security 問題
- 找 edge case
- 驗證 API / logic
- 驗證測試是否足夠
- 提供具體 findings

### 建議 Prompt

```text
/agy LOOP TASK <TASK-ID> STAGE 2 REVIEW

ROLE: REVIEWER / VALIDATOR

請審查 GPT/Codex 對 <TASK-ID> 的實作。

Focus:
1. logic correctness
2. regression
3. API contract
4. security
5. edge cases
6. tests coverage
7. 是否可進入 Claude finalization

不要：
- 大規模重寫
- unrelated refactor
- commit
- push
- 輸出 secret

最後輸出：
TASK: <TASK-ID>
STAGE: AGY_REVIEW
RESULT: APPROVE / REQUEST_CHANGES / BLOCKED
SEVERITY: LOW / MEDIUM / HIGH
FINDINGS:
1.
2.
3.
READY_FOR_CLAUDE: YES / NO
```

若：

```text
RESULT: APPROVE
READY_FOR_CLAUDE: YES
```

進 Stage 3。

若：

```text
REQUEST_CHANGES
```

則 Claude 判斷是否屬於小修；若是重大修改，回到 GPT 開下一輪。

---

## Stage 3：Claude 結論、修護與收尾

Claude 是最後 Integrator。

### Claude 任務

1. 讀取 GPT 實作結果
2. 讀取 AGY Review findings
3. 判斷是否需要 final repair
4. 只做必要的小型修護
5. 執行完整測試
6. 確認 runtime / service 狀態
7. 確認 Telegram E2E（若適用）
8. Git status / diff / secret scan
9. 建立 commit
10. push GitHub
11. 產生本次任務 Markdown 報告

### 建議最終 Prompt

```text
CLAUDE LOOP TASK <TASK-ID> STAGE 3 FINALIZE

ROLE: FINAL INTEGRATOR

INPUT:
- GPT implementation completed
- AGY review completed

請：
1. 檢查目前 git diff
2. 整合 AGY findings
3. 僅做必要 final repair
4. 執行完整 tests / smoke test
5. 檢查 secrets
6. 確認不包含 .env / token / private key
7. 若需要 Telegram E2E，執行或要求 live acceptance
8. 建立本次 Markdown report
9. git commit
10. git push origin main

禁止：
- force push
- reset/rebase 已完成歷史
- git add .（除非已證明安全）
- 輸出 secret
- 大規模 unrelated refactor

若 AGY finding 屬重大架構修改：
不要自行重寫，輸出 RETURN_TO_GPT。

最後輸出：
TASK: <TASK-ID>
STAGE: CLAUDE_FINALIZE
GPT: PASS / FAIL
AGY: PASS / FAIL
CLAUDE_REPAIR: PASS / NOT_REQUIRED / FAIL
TESTS: PASS / FAIL
LIVE_E2E: PASS / NOT_REQUIRED / FAIL
GIT_COMMIT: <sha or NOT_DONE>
GITHUB_PUSH: PASS / FAIL
REPORT_MD: <path>
OVERALL: PASS / RETURN_TO_GPT / FAIL
```

---

## Loop 判定規則

### 結束條件

只有全部符合才結束：

```text
GPT implementation = PASS
AGY review = APPROVE
Claude finalization = PASS
Tests = PASS
Live E2E = PASS 或 NOT_REQUIRED
GitHub push = PASS
Markdown report = CREATED
```

### 回到 GPT 的條件

任何以下狀況回到 Stage 1：

- AGY 發現重大 logic bug
- AGY 發現重大 security issue
- Claude 判定需要架構重寫
- 完整 tests FAIL
- Telegram Live E2E FAIL
- provider routing 不符合需求

流程：

```text
Claude: RETURN_TO_GPT
        ↓
GPT LOOP TASK <TASK-ID> ROUND 2
        ↓
AGY REVIEW ROUND 2
        ↓
Claude FINALIZE ROUND 2
```

---

## Markdown 報告命名規則

每個完成任務建立：

```text
reports/<TASK-ID>.md
```

例如：

```text
reports/AGY-CLI-001.md
reports/AUTO-RESULT-001.md
reports/SKILL-002.md
```

內容至少包含：

```markdown
# <TASK-ID>

## Goal

## GPT / Codex Implementation

## AGY Review

## Claude Final Repair

## Tests

## Telegram Live E2E

## Changed Files

## Git

- Commit: <sha>
- Branch: main
- Push: PASS

## Final Result

OVERALL: PASS
```

---

## GitHub 收尾規則

Claude 最終收尾前：

```bash
git status
git diff
git diff --cached
```

禁止直接：

```bash
git add .
```

應只 stage 本任務檔案。

Commit 命名建議：

```text
feat: <feature>
fix: <bug>
docs: <documentation>
refactor: <scope>
```

Push：

```bash
git push origin main
```

最後驗證：

```bash
git status
git log -1 --oneline
git ls-remote origin refs/heads/main
```

---

## E500 Agent Role Mapping

```text
/gpt
→ Codex exec
→ Lead Developer

/agy
→ agy -p
→ Google AI Pro OAuth
→ gemini-3.7-flash-high
→ Reviewer / Validator

/claude
→ Claude runner
→ Final Integrator / Repair / GitHub closer

/gemini
→ Gemini API Key / Meeting Room
→ 可作額外 API Reviewer

/hermes
→ Hermes / Meeting Room
→ 可作額外 Runtime Reviewer
```

---

## 推薦 Loop

```text
ROUND N

1. GPT / Codex
   IMPLEMENT
      ↓
2. AGY
   REVIEW
      ↓
3. Claude
   FINALIZE
      ↓
   ┌───────────────┐
   │ PASS          │→ GitHub + MD → END
   │ RETURN_TO_GPT │→ ROUND N+1
   └───────────────┘
```

---

## 核心原則

> **GPT 負責把功能做出來，AGY 負責證明它值得信任，Claude 負責整合結論、做最後修護、完成 GitHub 與文件收尾。**

這個 Loop 的目的不是讓三個 Agent 重複做同一件事，而是讓每個 Agent 有明確責任，並以測試、Live E2E、GitHub commit 與 Markdown 報告作為真正完成的證據。
