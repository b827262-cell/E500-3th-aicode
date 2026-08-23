# GPT-Codex Bridge Agent Instructions

## Central AI Development Tooling

本 repo 遵循中央標準：

`/home/b827262/project/gpt-codex-bridge/AI_DEV_TOOLING.md`

開始工作前先讀取該文件。它是所有納入專案共用的 AI Development Infrastructure source of truth；本檔案只補充 GPT-Codex Bridge 本身的 repo-local 規則，不複製中央標準全文。

- 一般修改使用 `/run`（`workspace-write`）。
- 診斷與 inspection 使用 `/run-read`（`read-only`）。
- 僅在 task 明確需要跨 workspace 或 system operation 時使用 `/run-full`（`danger-full-access`）。
- 維持 SQLite queue、single worker、notification outbox 與 structured report 的既有安全邊界；不要以臨時 runner 取代中央流程。
- 最終回報至少遵循中央標準的 `CODEX EXECUTION REPORT` 欄位。
