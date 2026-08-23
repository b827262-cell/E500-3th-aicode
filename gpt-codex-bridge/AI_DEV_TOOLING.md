# AI Development Tooling Standard

## GPT-Codex Bridge — Standard AI Development Infrastructure

本文件是 `/home/b827262/project` 下所有重要軟體專案的中央 AI Development Infrastructure 標準來源。各專案的 `AGENTS.md` 只保留本專案規則與本文件的引用，不應複製本文件全文。若專案本地規則更嚴格，應遵循更嚴格的規則。

## 1. Purpose

GPT-Codex Bridge 將規劃、執行、驗證與通知責任分開，讓 AI 開發工作可追蹤、可恢復、可審查。

### ChatGPT 負責

- 架構規劃
- 問題分析
- 任務拆解
- Codex 任務規格
- Review
- 驗收
- 下一輪決策

### E500 Codex 負責

- 讀取 Git repo
- 修改程式
- 執行測試
- Git diff
- runtime diagnostics
- structured execution report

### Telegram / GPT-Codex Bridge 負責

- remote job submission
- SQLite persistent queue
- worker dispatch
- sandbox selection
- result persistence
- completion notification

## 2. Standard Architecture

```text
ChatGPT
   │
   │ task specification
   ▼
Telegram / @e500codex_bot
   │
   ▼
Telegram Adapter
   │
   ▼
SQLite Persistent Queue
   │
   ▼
Single Codex Worker
   │
   ▼
Codex CLI
   │
   ▼
Allowed Git Workspace
   │
   ├─ tests
   ├─ git diff
   └─ structured report.json
   │
   ▼
Notification Outbox
   │
   ▼
Telegram Auto Notification
   │
   ▼
ChatGPT Review
```

標準執行路徑是：ChatGPT 產生 task specification，Telegram adapter 建立 job，SQLite queue 持久化 job，由單一 Codex worker dispatch 到 Codex CLI；Codex 只在允許的 Git workspace 執行，完成 tests、`git diff` 與 `structured report.json`，再由 notification outbox 送出 Telegram 通知，最後由 ChatGPT review 與驗收。

## 3. Canonical Bridge

中央工具是：

```text
/home/b827262/project/gpt-codex-bridge
```

此 repo 是各重要專案共用的 AI development infrastructure。各專案不得自行複製一套 Telegram/Codex runner，除非有明確架構理由，且該理由、邊界與維運責任已被記錄並獲得確認。

各專案的 `AGENTS.md` 應引用本文件，並只補充該 repo 特有的 build、test、目錄與貢獻規則。

## 4. Standard Telegram Commands

```text
/run-read <task>
→ read-only

/run <task>
→ workspace-write

/run-full <task>
→ danger-full-access

/status

/result <job_id>
```

預設模式是 `workspace-write`。

使用原則：

1. 診斷優先使用 `/run-read`。
2. 一般程式修改使用 `/run`。
3. 只有必要的跨 workspace / system operation 才使用 `/run-full`。
4. 不得將 `danger-full-access` 設成全域預設。

`/run-full` 是高權限操作，task specification 必須說明需要跨 workspace 或 system operation 的原因，以及要執行的確切範圍。

## 5. Sandbox Policy

### `read-only`

適合：

- code review
- inspection
- `git status`
- log analysis
- diagnosis

### `workspace-write`

適合：

- 一般開發
- bug fix
- tests
- refactoring
- README/docs

這是標準預設。

### `danger-full-access`

僅適合：

- workspace 外必要操作
- `systemd` user unit
- 明確授權的跨 repo 工作

重要限制：`-C <workspace>` 是 Codex 起始工作目錄，不是 `danger-full-access` 下的 filesystem security boundary。使用 `danger-full-access` 時，仍必須依 task contract、workspace allowlist 與最小權限原則限制實際操作範圍。

## 6. Security Baseline

以下是不可移除的安全基線：

- Telegram Chat ID whitelist
- workspace allowlist
- Telegram 不得指定任意 `cwd`
- raw shell API forbidden
- single worker
- `concurrency=1`
- Unix file lock
- SQLite persistent queue
- restart recovery
- timeout
- secret redaction
- structured report
- per-job sandbox
- unknown mode fail closed
- `/run-full` authorization
- Telegram token 不傳給 Codex child
- persistent notification outbox
- duplicate notification protection

所有 `.env` 檔案應使用 `mode 600`，`never commit secrets`。secret 不應出現在 job log、`git diff`、`report.json`、Telegram message 或 notification outbox。

## 7. Codex Model Policy

目前 runner 若沒有 `-m`，使用 Codex effective configuration。這表示模型由當下 Codex configuration 決定，而不是由每個 repo 各自宣稱固定。

目前 E500 user configuration 已知為：

```toml
model = "gpt-5.6-luna"
```

中央規範不得宣稱所有未來 job 永遠固定使用此模型。驗證目前 effective configuration 的方式是：

```bash
grep -nE '^[[:space:]]*model[[:space:]]*=' ~/.codex/config.toml
```

若將來 runner 增加 per-job model selection，必須在 job/report 保存實際 model。

## 8. Standard Task Contract

ChatGPT 下達給 Codex 的正式任務，原則上包含以下欄位：

```text
WORKSPACE
OBJECTIVE
CONTEXT
CONSTRAINTS
DO_NOT
IMPLEMENTATION
VALIDATION
FINAL_REPORT
```

涉及高風險或 production 工作時，還應包含：

```text
BACKUP
ROLLBACK
ACCEPTANCE_CRITERIA
```

欄位應明確描述允許的 workspace、目標、不可做的動作、驗證命令與完成判定。若 task 需要更高 sandbox 權限，必須在 `CONSTRAINTS` 或 `IMPLEMENTATION` 中記錄理由。

## 9. Required Final Report

重要 Codex 任務最後至少回報以下格式。即使某欄位沒有內容，也應保留欄位並填寫 `N/A` 或具體錯誤。

```text
CODEX EXECUTION REPORT

WORKSPACE:
ROOT_CAUSE:
ACTIONS:
CHANGED_FILES:
TESTS:
GIT_DIFF:
ERRORS:
REMAINING_ISSUES:
RESULT:
```

`RESULT` 應明確表示成功、部分完成或失敗；`TESTS` 應列出實際執行的 command 與結果；`GIT_DIFF` 應說明是否有未提交變更。

## 10. Repository Adoption Rule

納入本標準的正式 repo 必須在根目錄有簡潔的 `AGENTS.md` 引用：

```text
/home/b827262/project/gpt-codex-bridge/AI_DEV_TOOLING.md
```

Codex 開始工作前應先讀取中央標準與目標 repo 根目錄至目前目錄路徑上的 `AGENTS.md`。本文件定義共用 AI tooling；repo-local `AGENTS.md` 定義程式碼、測試、文件與貢獻細節。
