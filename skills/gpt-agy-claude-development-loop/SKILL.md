---
name: gpt-agy-claude-development-loop
description: Run bounded software-development tasks through GPT/Codex implementation, AGY review, and Claude final integration with evidence-based tests, runtime and Telegram gates, secret-safe reports, and explicit RETURN_TO_GPT handling.
---

# GPT → AGY → Claude Development Loop

Use this skill when a software task explicitly requires the fixed ownership
workflow below. It is a process and reporting contract; it does not modify the
application's agent routing or production code by itself.

~~~text
GPT / Codex  →  AGY  →  Claude
LEAD_DEVELOPER   REVIEWER   FINAL_INTEGRATOR
~~~

## Non-negotiable ownership rules

- GPT/Codex is the implementation owner. It may make the smallest production
  and test changes required by the task.
- AGY is review-only. AGY must inspect the actual working tree and must not
  modify task files while reviewing.
- Claude is a final integrator, not a production implementer. Claude may fix
  only a report, documentation, commit metadata, or an explicit,
  reproducible, non-production closure defect within scope.
- Claude must not modify production logic, production configuration,
  architecture, or tests. A production-code, architecture, security, scope,
  regression, or uncertain-interpretation issue is always returned to GPT.
- Never allow GPT, AGY, and Claude to edit the same task files concurrently.
- The task's explicit scope and exclusions override generic examples here. Do
  not commit, push, or touch excluded files.

## Immutable task contract

Start every task with a contract and preserve it across all rounds:

~~~text
TASK: <TASK-ID>
GOAL:
<desired outcome and acceptance criteria>

INPUTS:
<scope, constraints, prior evidence, and exclusions>

MAX_ROUNDS: 3
ROUND: 1
CURRENT_ROUND: 1
NEEDS_HUMAN_DECISION: NO
~~~

MAX_ROUNDS is fixed at 3; valid rounds are only 1, 2, and 3. Keep the same
TASK-ID in every phase response, report, commit context, and handoff. Do not
silently widen scope between rounds.

## Global BLOCKED contract

Every path or template that emits `BLOCKED` must emit all of these fields in
the same response; never emit only a subset and never pair `RESULT: BLOCKED`
with `NEXT: RETURN_TO_GPT`:

~~~text
RESULT: BLOCKED
NEEDS_HUMAN_DECISION: YES
NEXT: HUMAN_DECISION
~~~

This contract applies to AGY BLOCKED, Claude BLOCKED, the MAX_ROUNDS guard,
ROUND 3 REQUEST_CHANGES, branch or secret/credential gates, and every other
blocked transition or template. A blocked state is terminal for the active
loop and stops further implementation, staging, commit, and push activity.

This same three-field output is mandatory whenever `DECISION: BLOCKED` or
`RESULT: BLOCKED` appears in any phase template. Do not emit a phase-specific
BLOCKED variant with a different `NEXT` or `NEEDS_HUMAN_DECISION` value.

## Explicit bounded state machine

The review and finalization phases belong to the current round. There is no
same-round repair loop:

~~~text
GPT IMPLEMENT
→ AGY REVIEW

AGY APPROVE
→ CLAUDE FINALIZE

AGY REQUEST_CHANGES
→ if CURRENT_ROUND < MAX_ROUNDS: RETURN_TO_GPT
→ if CURRENT_ROUND >= MAX_ROUNDS: BLOCKED

AGY BLOCKED
→ BLOCKED
→ RESULT: BLOCKED
→ NEEDS_HUMAN_DECISION: YES
→ NEXT: HUMAN_DECISION

CLAUDE finds a production-code or architecture issue
→ if CURRENT_ROUND < MAX_ROUNDS: RETURN_TO_GPT
→ if CURRENT_ROUND >= MAX_ROUNDS: BLOCKED
~~~

Required transition rules:

| Current decision/state | Required next state |
| --- | --- |
| GPT IMPLEMENT | AGY REVIEW |
| AGY APPROVE | Claude FINALIZE |
| AGY REQUEST_CHANGES with CURRENT_ROUND < MAX_ROUNDS | RETURN_TO_GPT, never a Claude repair in the same round |
| AGY REQUEST_CHANGES with CURRENT_ROUND >= MAX_ROUNDS | BLOCKED with the full BLOCKED contract; no ROUND 4 |
| AGY BLOCKED | BLOCKED with the full BLOCKED contract |
| Claude finds production/architecture/security/scope/regression/uncertain issue with CURRENT_ROUND < MAX_ROUNDS | RETURN_TO_GPT |
| Claude finds such an issue with CURRENT_ROUND >= MAX_ROUNDS | BLOCKED with the full BLOCKED contract; no ROUND 4 |
| Claude RETURN_TO_GPT | Apply the next-round guard, then GPT IMPLEMENT if allowed |
| Claude BLOCKED | BLOCKED with the full BLOCKED contract |
| Branch or secret/credential gate fails | BLOCKED with the full BLOCKED contract |

All major AGY findings must force RETURN_TO_GPT. Claude may not downgrade a
major finding into a local repair. If the next-round guard blocks the
transition, record that the required next state was RETURN_TO_GPT, then stop
with the full BLOCKED contract; do not create another round. In particular, if
ROUND=3 and AGY still returns REQUEST_CHANGES, apply the guard immediately and
emit BLOCKED/HUMAN_DECISION; never enter ROUND 4.

Before every transition that would increment the round, apply this guard:

~~~text
if CURRENT_ROUND >= MAX_ROUNDS:
    DECISION=BLOCKED
    RESULT=BLOCKED
    NEXT=HUMAN_DECISION
    NEEDS_HUMAN_DECISION=YES
    STOP
else:
    CURRENT_ROUND=CURRENT_ROUND+1
    ROUND=CURRENT_ROUND
    NEXT=GPT
~~~

Never set ROUND to 4, never create ROUND 4, and never use a ROUND greater than
MAX_ROUNDS state as a transition. When a terminal state is reached, write the
report only after the applicable final gates have been recorded and stop.

## GPT implementation phase

GPT inspects the existing implementation, makes the smallest correct change,
adds or updates relevant tests, and runs the applicable tests. On later rounds
the goal is to fix only the returned finding within the original scope. The
GPT response uses the standardized fields in the prompt template below.

RESULT: PASS means only that GPT's implementation phase completed; it is not
final task acceptance.

## AGY review phase

After GPT finishes, AGY must inspect actual state, not only a narrative:

~~~bash
git status --short
git diff -- <task-scoped-files>
git diff --cached -- <task-scoped-files>
~~~

The cached-diff inspection is conditional during AGY review: if nothing is
staged, record it as NOT_APPLICABLE rather than requiring a nonexistent staged
diff. The required credential review of `git diff --cached` occurs only after
the explicit task-file/report staging step below.

Review every task-scoped changed file for correctness, regression risk,
security, edge cases, test gaps, runtime impact, and unrelated changes. Every
finding must include a path, behavior, or concrete evidence. AGY must choose
one of APPROVE, REQUEST_CHANGES, or BLOCKED in DECISION; it must not quietly fix
findings.

REQUEST_CHANGES hands the task to RETURN_TO_GPT only when
CURRENT_ROUND < MAX_ROUNDS; it never authorizes Claude to repair production
logic in the same round. At ROUND=3, REQUEST_CHANGES is terminal BLOCKED and
must emit the full BLOCKED contract. BLOCKED always ends the active loop with
RESULT: BLOCKED, NEXT: HUMAN_DECISION, and NEEDS_HUMAN_DECISION: YES.

## Claude finalization phase

Claude reads the immutable contract, GPT response, full diff, actual test
evidence, and complete AGY review before deciding. Claude may edit only:

- the report;
- documentation;
- commit metadata; or
- an explicit, reproducible, local, non-production closure defect.

Claude must not change production logic, production configuration,
architecture, or tests. If any finding needs GPT, including any production or
architecture issue or any major finding, Claude emits RETURN_TO_GPT, applies
the next-round guard, and does not edit or commit the incomplete round. If the
guard stops the transition, emit BLOCKED/HUMAN_DECISION instead; never start
round 4.

Claude's response must include exactly these decision/result/next domains:

~~~text
DECISION: FINALIZE | RETURN_TO_GPT | BLOCKED
RESULT: PASS | FAIL | BLOCKED
NEXT: COMPLETE | RETURN_TO_GPT | HUMAN_DECISION
~~~

If Claude emits BLOCKED, it must also emit `NEEDS_HUMAN_DECISION: YES` and use
`NEXT: HUMAN_DECISION`; the Global BLOCKED contract applies.

FINALIZE is allowed only after AGY APPROVE and only when all required gates can
pass. A missing or failed required gate is not final PASS.

## Tests and evidence

Run the repository's documented test workflow. When these commands exist and
apply, run them:

~~~bash
python3 -m pytest -q
scripts/smoke-test.sh
~~~

Do not invent passing output. Every PASS in a report must name the command that
actually ran and summarize its observed result. When signals disagree, use
this evidence order:

~~~text
Telegram Live E2E > integration test > automated test > runtime evidence > agent narrative
~~~

For runtime-sensitive tasks, record service/process/health evidence separately
under Runtime Validation. If a gate is not applicable, write NOT_APPLICABLE and
explain why.

## Required gate ledger

When the task prompt names loop gates, record each gate explicitly in the
phase response and final report. A generic `RESULT: PASS` does not satisfy a
gate. Use only observed evidence from the current round:

~~~text
LOOP_CONTROL: PASS | FAIL
STATE_MACHINE: PASS | FAIL
MAX_ROUNDS_GUARD: PASS | FAIL
PROMPT_CONTRACT: PASS | FAIL
REPORT_BEFORE_COMMIT: PASS | FAIL
BRANCH_SAFETY: PASS | FAIL
SECRET_GATE: PASS | FAIL
UNTRACKED_VALIDATION: PASS | FAIL
~~~

Set a gate to FAIL when its required evidence is missing or contradictory; the
phase result cannot be PASS while a required gate is FAIL. For a task that does
not authorize commit or push, record the gates from the documented no-mutation
path and do not perform those operations merely to make the gates pass.
`REPORT_BEFORE_COMMIT` is satisfied only when the report is created from
observed evidence before staging or committing; `BRANCH_SAFETY` is satisfied
only when the current branch is checked immediately before an authorized push.
`UNTRACKED_VALIDATION` must include both normal `git diff --check` and the
separate validation required for untracked task files below.

Append this ledger after the template's `NEXT` field; do not replace or rename
the standardized template fields.

## Telegram prompt hard-limit (TG-2360)

The Telegram prompt contract uses these fixed values for every round:

~~~text
TELEGRAM_PROMPT_HARD_LIMIT=2360
TELEGRAM_PROMPT_SEND_COUNT=1
MAX_SPLIT_MESSAGES=0
OVERFLOW_MODE=TASK_FILE
~~~

Count the complete prompt's total characters, including spaces, newlines, and
punctuation. The count is characters, not bytes or tokens.

~~~text
prompt character count <= 2360 → SEND_ONCE
prompt character count > 2360  → write tasks/<TASK-ID>-R<ROUND>.md,
                                  Telegram sends one short instruction only
~~~

The overflow task file contains the full prompt. Do not split it into a second
Telegram message and do not create a second Task Job for the same TASK-ID and
ROUND. `TELEGRAM_PROMPT_SEND_COUNT` remains exactly `1` in both branches.

## Telegram Live E2E

If the task changes Telegram routing, provider dispatch, runners, notification
delivery, or Telegram commands, require a real inbound/outbound acceptance from
the user's Telegram client before final PASS. Validate the affected command and
relevant existing routes, for example:

~~~text
/gpt <small acceptance request>
/agy <small acceptance request>
/claude <small acceptance request>
~~~

Do not substitute a unit test, API 200, health check, log line, or agent
narrative for live Telegram evidence. If live evidence cannot be provided and
the task cannot proceed, use BLOCKED and emit the full BLOCKED contract; use
RETURN_TO_GPT only when a next round is still allowed, and state the missing
gate.

## Required finalization and credential order

For a task that authorizes a commit and push, the order is mandatory:

~~~text
final tests
→ Telegram Live E2E (if needed)
→ create reports/<TASK-ID>.md
→ pre-stage secret/credential scan
→ git status/diff
→ stage only explicit Task files + reports/<TASK-ID>.md
→ git diff --cached
→ staged credential review/scan
→ if suspected secret: unstage, stop, and BLOCKED
→ commit
→ push
→ remote SHA verification
→ COMPLETE
~~~

The report must be created before staging and must be included in that task's
final commit. The pre-stage scan must inspect the working tree, task files, and
report; it must not require `git diff --cached` before staging because no staged
diff exists yet. After staging, inspect the cached diff and run the separate
staged credential review/scan. If a suspected secret is found, unstage the
explicit staged paths, stop, and emit the full BLOCKED contract; do not commit
or push. Use explicit paths only; never use a repository-wide staging command.
If the task explicitly excludes commit or push, do not perform either
operation merely because this skill describes the authorized path; record
NOT_DONE and follow the task's acceptance definition.

## Branch safety

Before any push, obtain and record the current branch:

~~~bash
git branch --show-current
~~~

Record it as CURRENT_BRANCH=<branch>. Confirm that it satisfies the task's
branch policy before pushing:

~~~bash
git push origin "$CURRENT_BRANCH"
~~~

Never hardcode a push to a fixed branch such as main. If the branch is missing
or does not match the task policy, do not push. Stop with the full BLOCKED
contract:

~~~text
RESULT: BLOCKED
NEXT: HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES
~~~

Do not switch branches, rebase, force-push, or rewrite history.

## Credential and secret gate

Never output, copy, commit, or place in prompts, logs, reports, diffs, commits,
or Telegram replies any secret value, including:

- API key, token, password, OAuth credential, or cookie;
- private key or certificate material; or
- complete .env contents.

Status-only forms are safe, for example KEY present=yes or
TOKEN length=<n>. Redact values from command output and reports.

### Pre-stage secret/credential scan

After the report is created and before staging, at minimum confirm from the
working tree and task-scoped diff:

- .env files are ignored and no .env is tracked;
- private keys are not tracked;
- API keys, tokens, passwords, OAuth credentials, and cookies do not appear
  in the task-scoped working-tree diff; and
- the pre-stage scan passed without exposing any value.

If the repository already provides a secret-scan script, use it first. Use
filename/status checks such as the following without printing file contents:

~~~bash
git check-ignore -v .env
git check-ignore -v <service>/.env
git ls-files | rg '(^|/)\.env($|\.)|(^|/)(id_rsa|id_dsa|id_ecdsa|id_ed25519|.*\.(pem|key))$'
~~~

Do not require or inspect `git diff --cached` in this pre-stage step. Run the
working-tree/status checks first, then stage only the explicit task files and
the report. After staging, review `git diff --cached` for credential patterns
without exposing any value and record the staged credential review/scan.

If a suspected credential is found in the staged diff, unstage the explicit
staged paths, stop before commit and push, and emit:

~~~text
RESULT: BLOCKED
NEXT: HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES
~~~

Do not put the suspected value in the report.

The pre-stage order is therefore strictly: tests, Live E2E when needed,
report creation, pre-stage scan, status/diff review, explicit staging, cached
diff review, staged credential review/scan, suspected-secret BLOCKED gate,
commit, push, and remote SHA verification. A pre-stage scan must never require
or inspect a staged diff that does not yet exist.

## Untracked-file validation

git diff -- <path> can be empty for a new untracked file. Never interpret that
output as proof that the file has no changes. Always run:

~~~bash
git status --short
git diff --check
git diff -- skills/gpt-agy-claude-development-loop/SKILL.md
~~~

If the Skill is untracked, inspect and validate its content separately, for
example by inspecting the file content and running a frontmatter/content
validator:

~~~bash
sed -n '1,999p' skills/gpt-agy-claude-development-loop/SKILL.md
git diff --no-index --check /dev/null skills/gpt-agy-claude-development-loop/SKILL.md
~~~

The --no-index command may exit nonzero because the files differ; inspect its
output for whitespace errors and perform separate frontmatter/content
validation. The normal git diff --check remains mandatory.

## Completion report

For a completed or terminal task, create reports/<TASK-ID>.md from observed
evidence only, after the final tests and applicable Telegram gate. The report
must contain these headings:

~~~markdown
# <TASK-ID>

## Goal

## GPT Implementation

## AGY Review

## Claude Final Decision

## Changed Files

## Tests

## Runtime Validation

## Telegram Live E2E

## Git Commit

## GitHub Push

## Risks / Remaining Issues

## Final Result
DECISION: FINALIZE | RETURN_TO_GPT | BLOCKED
RESULT: PASS | FAIL | BLOCKED
NEXT: COMPLETE | RETURN_TO_GPT | HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES | NO
~~~

The final report must use exactly these decision/result/next domains and must
always include NEEDS_HUMAN_DECISION. A blocked report must use the complete
terminal contract:

~~~text
RESULT: BLOCKED
NEXT: HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES
~~~

Use `RESULT: PASS` only when all required acceptance gates pass. For an active
RETURN_TO_GPT handoff, the report must record `RETURN_REASON:` with the concrete
finding/evidence and `NEXT_ROUND:` with the next allowed round; this is allowed
only when CURRENT_ROUND < MAX_ROUNDS. If CURRENT_ROUND=3, do not use
`DECISION: RETURN_TO_GPT` or create ROUND 4: convert the outcome to
`DECISION: BLOCKED` with the complete BLOCKED contract. Use FAIL for a terminal
failed task that is not awaiting human decision. Reports must include real
commands and outcomes, safe secret-status checks only, exact task-scoped
changed files, and remaining risks; never include secret values.

## Standardized prompt templates

All five templates use the same field names and order. Do not use role-specific
field aliases; use only the ROLE field shown below.
Replace angle-bracket placeholders without adding credentials or other secret
values.

### 1. GPT implementation template

~~~text
TASK: <TASK-ID>
ROUND: <CURRENT_ROUND>
PHASE: IMPLEMENT
ROLE: GPT_LEAD_DEVELOPER
GOAL:
<desired outcome>
INPUTS:
<scope, exclusions, prior findings, and relevant evidence>
FINDINGS:
<prior AGY/Claude finding, or NONE>
CHANGED_FILES:
<explicit paths, or NONE>
TESTS:
<real commands and observed results>
DECISION: IMPLEMENT | BLOCKED
RESULT: PASS | FAIL | BLOCKED
NEXT: REVIEW | HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES | NO
~~~

GPT may implement production/test changes only within the immutable task scope.
On a later round, keep PHASE: IMPLEMENT and put the requested fix in
FINDINGS/GOAL.
If RESULT: BLOCKED, NEXT must be HUMAN_DECISION and
NEEDS_HUMAN_DECISION must be YES.

### 2. AGY review template

~~~text
TASK: <TASK-ID>
ROUND: <CURRENT_ROUND>
PHASE: REVIEW
ROLE: AGY_REVIEWER
GOAL:
<task acceptance criteria>
INPUTS:
<contract, actual status, complete diff, cached diff, tests, and runtime evidence>
FINDINGS:
<path/behavior/evidence for every finding, or NONE>
CHANGED_FILES:
<files inspected>
TESTS:
<tests/evidence inspected, or NOT_APPLICABLE with reason>
DECISION: APPROVE | REQUEST_CHANGES | BLOCKED
RESULT: PASS | FAIL | BLOCKED
NEXT: FINALIZE | RETURN_TO_GPT | HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES | NO
~~~

When CURRENT_ROUND < MAX_ROUNDS, REQUEST_CHANGES requires
NEXT: RETURN_TO_GPT and NEEDS_HUMAN_DECISION: NO. At CURRENT_ROUND >=
MAX_ROUNDS, including ROUND 3, REQUEST_CHANGES must be terminal BLOCKED with
NEXT: HUMAN_DECISION and NEEDS_HUMAN_DECISION: YES; do not create ROUND 4.
BLOCKED requires RESULT: BLOCKED, NEXT: HUMAN_DECISION, and
NEEDS_HUMAN_DECISION: YES.

### 3. Claude finalization template

~~~text
TASK: <TASK-ID>
ROUND: <CURRENT_ROUND>
PHASE: FINALIZE
ROLE: CLAUDE_FINAL_INTEGRATOR
GOAL:
<task acceptance criteria>
INPUTS:
<contract, GPT response, full diff, tests, runtime/Telegram evidence, and AGY review>
FINDINGS:
<AGY findings and any Claude-discovered issue, or NONE>
CHANGED_FILES:
<report/documentation/metadata/non-production closure files only, or NONE>
TESTS:
<final commands and observed results, or NOT_RUN with reason>
DECISION: FINALIZE | RETURN_TO_GPT | BLOCKED
RESULT: PASS | FAIL | BLOCKED
NEXT: COMPLETE | RETURN_TO_GPT | HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES | NO
~~~

Claude must use exactly the listed values for DECISION, RESULT, and NEXT. Any
production/architecture issue or major finding requires DECISION:
RETURN_TO_GPT, NEXT: RETURN_TO_GPT, NEEDS_HUMAN_DECISION: NO, and the
next-round guard. If the guard blocks it, use DECISION: BLOCKED and the full
BLOCKED contract instead.

### 4. RETURN_TO_GPT handoff template

~~~text
TASK: <TASK-ID>
ROUND: <CURRENT_ROUND>
PHASE: FINALIZE
ROLE: CLAUDE_FINAL_INTEGRATOR
GOAL:
<original acceptance criteria>
INPUTS:
<AGY review, actual diff, and evidence requiring GPT rework>
FINDINGS:
<specific production/architecture/major finding with path and evidence>
CHANGED_FILES:
NONE
TESTS:
<tests already observed, or NOT_RUN>
DECISION: RETURN_TO_GPT | BLOCKED
RESULT: FAIL | BLOCKED
NEXT: RETURN_TO_GPT | HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES | NO
~~~

If CURRENT_ROUND < MAX_ROUNDS, record `RETURN_REASON:` and
`NEXT_ROUND:` (2 or 3), use RESULT: FAIL, NEXT: RETURN_TO_GPT, and
NEEDS_HUMAN_DECISION: NO. If CURRENT_ROUND >= MAX_ROUNDS, including ROUND 3,
replace DECISION: RETURN_TO_GPT with DECISION: BLOCKED and emit RESULT: BLOCKED,
NEXT: HUMAN_DECISION, and NEEDS_HUMAN_DECISION: YES; do not create ROUND 4.

### 5. Final report template

~~~text
TASK: <TASK-ID>
ROUND: <CURRENT_ROUND>
PHASE: FINALIZE
ROLE: CLAUDE_FINAL_INTEGRATOR
GOAL:
<goal and acceptance criteria>
INPUTS:
<final gates, branch, secret checks, commit/push evidence, and report path>
FINDINGS:
<remaining risk, blocker, or NONE>
CHANGED_FILES:
<explicit task files plus reports/<TASK-ID>.md, or NONE>
TESTS:
<real commands and observed outcomes>
DECISION: FINALIZE | RETURN_TO_GPT | BLOCKED
RESULT: PASS | FAIL | BLOCKED
NEXT: COMPLETE | RETURN_TO_GPT | HUMAN_DECISION
NEEDS_HUMAN_DECISION: YES | NO
RETURN_REASON: <required when DECISION: RETURN_TO_GPT, otherwise NONE>
NEXT_ROUND: <2 or 3 when DECISION: RETURN_TO_GPT, otherwise NONE>
~~~

For `DECISION: RETURN_TO_GPT`, `RESULT` must be `FAIL`, `NEXT` must be
`RETURN_TO_GPT`, `NEEDS_HUMAN_DECISION` must be `NO`, and the report must
include a concrete `RETURN_REASON` plus the next allowed `NEXT_ROUND`. For
`CURRENT_ROUND=3`, a requested return is converted to `DECISION: BLOCKED`;
the report must not name or create ROUND 4 and must emit, together, exactly:

~~~text
RESULT: BLOCKED
NEEDS_HUMAN_DECISION: YES
NEXT: HUMAN_DECISION
~~~

The report body then uses the required headings in Completion report. For a
successful authorized task, its order is tests, Telegram Live E2E when needed,
report creation, pre-stage secret/credential scan, status/diff review, explicit
staging, cached diff review, staged credential review/scan, commit, branch-safe
push, remote SHA verification, and NEXT: COMPLETE. The report template's
DECISION/RESULT/NEXT/NEEDS_HUMAN_DECISION fields are mandatory.

## Complete loop example

~~~text
TASK FEATURE-001
ROUND 1

GPT IMPLEMENT
→ PASS

AGY REVIEW
→ REQUEST_CHANGES

NEXT:
RETURN_TO_GPT

ROUND 2

GPT FIX
→ PASS

AGY REVIEW
→ APPROVE

Claude FINALIZE
→ PASS

Report created
→ staged
→ commit
→ push
→ remote verify

RESULT:
PASS
~~~

The GPT FIX in the example is still emitted with PHASE: IMPLEMENT and ROLE:
GPT_LEAD_DEVELOPER; FIX describes the round's goal, not a different template
role.

When the limit is reached:

~~~text
ROUND 3
AGY REQUEST_CHANGES

CURRENT_ROUND >= MAX_ROUNDS

RESULT:
BLOCKED
NEXT:
HUMAN_DECISION
NEEDS_HUMAN_DECISION:
YES

No ROUND 4.
~~~
