# AI Meeting Room Live Acceptance

直接把下面整段貼給 E500 的 Codex。這次只做 Live 驗收與必要的小修正，不要再重構已經正常的雙主機架構。

目前 AI Meeting Room 已完成核心連線，現在進行最終 Live 驗收。

## 已確認狀態

E500：

IP: 10.0.3.68
Telegram Bot: @e500codex_bot
Telegram service: gpt-codex-telegram.service
MainPID: 1088054
Polling process: 1
WorkingDirectory:
/home/b827262/project/gpt-codex-bridge

TUF A16：

IP: 10.0.3.67
Meeting API:
http://10.0.3.67:8000

Hermes: READY
GPT: READY
Gemini: READY

Authentication：

/api/agents → HTTP 200

實際結果：

{"ok":true,"agents":{"hermes":true,"gemini":true,"gpt":true}}

Telegram "/agents" 已經成功收到回覆。

因此：

Telegram → E500 → TUF A16 → Meeting API

已經打通。

不要修改 TUF firewall。
不要修改 API authentication。
不要重構 systemd 架構。

---

## 1. SUDO POLICY

使用者已完成：

sudo -v
sudo -n true

所有 root command 一律：

sudo -n <command>

禁止：

- 互動式 sudo
- 要求密碼
- 修改 sudoers
- 設定 NOPASSWD

如果：

sudo -n true

失敗，立即回報：

SUDO_TICKET_EXPIRED

---

## 2. 啟動 Live Log

先執行：

journalctl --user \
  -u gpt-codex-telegram \
  -f -o cat

保持 log follow。

同時確認：

systemctl --user status \
  gpt-codex-telegram \
  -l --no-pager

成功標準：

Active: active (running)
MainPID > 0
polling process = 1

---

## 3. 驗證 /gpt

要求使用者在 Telegram 發：

/gpt Reply exactly GPT_OK

必須驗證完整路徑：

Telegram
→ E500
→ /api/ask/gpt
→ TUF A16
→ ChatGPTCodexAgent
→ Hermes CLI
→ --provider openai-codex
→ ChatGPT OAuth
→ gpt-5.6-luna
→ GPT_OK
→ E500
→ Telegram

成功標準：

Telegram 收到：

🟢 GPT
GPT_OK

如果失敗：

只定位實際錯誤。
不要切換到 OPENAI_API_KEY。

GPT 必須繼續使用：

GPT_BACKEND=hermes-codex-oauth
provider=openai-codex

---

## 4. 驗證 /hermes

要求使用者發：

/hermes Reply exactly HERMES_OK

成功：

☤ Hermes
HERMES_OK

驗證：

Telegram
→ E500
→ TUF
→ Hermes
→ Telegram

---

## 5. 驗證 /gemini

要求使用者發：

/gemini Reply exactly GEMINI_OK

成功：

🔵 Gemini
GEMINI_OK

---

## 6. 驗證 /all

要求使用者發：

/all 請三個 Agent 各自說明自己的角色，每個只回答三句。

確認三 Agent 都執行：

☤ Hermes
...

🟢 GPT
...

🔵 Gemini
...

確認：

- parallel execution 正常
- 單一 Agent failure 不使整個 request crash
- Telegram 長訊息可安全切段
- 不洩漏 API token / OAuth token / Gemini key

---

## 7. 驗證 /roundtable

最後要求使用者發：

/roundtable 請評估目前 E500 + TUF A16 雙主機 AI Agent 架構，分析可靠性、效能、Token 成本、故障備援與下一步優化。

確認：

Round 1

Hermes
GPT
Gemini

Round 2

Hermes
GPT
Gemini

Final

優先：

GPT synthesis

若 GPT failure：

Gemini synthesis

若 GPT + Gemini failure：

deterministic Hub summary

限制必須仍是：

max rounds = 2
max hops = 6
timeout = 300 sec

不得出現 Agent infinite loop。

---

## 8. 改善 /agents 顯示

目前 Telegram 顯示：

🤖 Meeting Room Agents
{'ok': True, 'agents':
 {'hermes': True, 'gemini': True, 'gpt': True}}

功能正常，但格式不好。

請做最小 UI 修正，改成：

🤖 Meeting Room Agents

☤ Hermes   ✅ READY
🟢 GPT      ✅ READY
🔵 Gemini   ✅ READY

TUF A16     ✅ ONLINE

如果某 Agent false：

例如：

🔵 Gemini   ❌ UNAVAILABLE

不要把 Python dict 原樣顯示給 Telegram。

只修改 formatter / presentation layer。

不要修改 Meeting API schema。

---

## 9. /status 或 /meeting-status

如果已有 "/meeting-status"，讓它顯示：

🖥 AI Meeting Room

E500 Gateway
✅ ONLINE

TUF A16
✅ ONLINE
10.0.3.67:8000

☤ Hermes
✅ READY

🟢 GPT
✅ READY
ChatGPT OAuth

🔵 Gemini
✅ READY

不要顯示：

- TELEGRAM_BOT_TOKEN
- MEETING_API_TOKEN
- OAuth token
- Gemini API key

---

## 10. Regression Test

原 E500 Codex 功能不能被破壞。

確認：

/run
/run-read
/run-full
/status
/result

仍正常。

Meeting commands：

/agents
/hermes
/gpt
/gemini
/all
/roundtable
/meeting-status
/meeting-stop
/meeting-reset

---

## 11. Service 驗收

完成必要修改後：

systemctl --user daemon-reload

systemctl --user restart \
  gpt-codex-telegram

sleep 3

systemctl --user status \
  gpt-codex-telegram \
  -l --no-pager

確認：

Active = active (running)
MainPID > 0
polling process = 1

執行：

pgrep -af 'adapters.telegram|run-telegram'

不得出現第二個 Telegram polling process。

---

## 12. TUF Connectivity

再次確認：

curl -sS \
  http://10.0.3.67:8000/health

以及 authenticated：

/api/agents

只允許回報：

HTTP 200
Hermes READY
GPT READY
Gemini READY

不得輸出 MEETING_API_TOKEN。

---

## 13. Logs

檢查：

journalctl --user \
  -u gpt-codex-telegram \
  -n 100 -l --no-pager

確認沒有：

Traceback
401
403
409 Conflict
MEETING_API_TOKEN
TELEGRAM_BOT_TOKEN
OAuth token

如果有 secret value 被 log：

立即修正 sanitization。

---

## 14. Git

如果只改 user systemd：

不需要 Git commit

如果修改：

/home/b827262/project/gpt-codex-bridge

則執行：

cd /home/b827262/project/gpt-codex-bridge

git diff --check
git status

確認：

.env
tokens
credentials
auth.json

沒有被 stage。

安全後才：

git add .
git commit -m "fix: finalize Telegram meeting room live integration"

不要 push。

---

## 15. 最終回報

最後請用：

AI MEETING ROOM LIVE ACCEPTANCE REPORT

Telegram Gateway:
PASS / FAIL

Polling processes:
1 / ERROR

TUF Connectivity:
PASS / FAIL

Authentication:
PASS / FAIL

/agents:
PASS / FAIL

/hermes:
PASS / FAIL

/gpt ChatGPT OAuth:
PASS / FAIL

/gemini:
PASS / FAIL

/all:
PASS / FAIL

/roundtable:
PASS / FAIL

GPT final synthesis:
PASS / FALLBACK

Original Codex commands:
PASS / FAIL

Systemd:
PASS / FAIL

Security scan:
PASS / FAIL

Git commit:
...

Known issues:
...

不要把 mock test 當成 live success。

只有實際 Telegram command 收到真正 Agent 回覆才能標記：

LIVE PASS

現在開始最終 Live 驗收。
