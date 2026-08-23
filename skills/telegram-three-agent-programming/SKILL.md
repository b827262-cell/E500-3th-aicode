---
name: telegram-three-agent-programming
description: Use Telegram to coordinate GPT/Codex, Hermes, and Gemini as a three-agent software engineering team for analysis, implementation, runtime review, API review, testing, live acceptance, and Git delivery in the E500 project.
---

# Telegram Three-Agent Programming

## Purpose

Use Telegram as the control plane for a three-agent software engineering workflow:

- **GPT / Codex** — Lead Developer and single writer.
- **Hermes** — Linux, systemd, runtime, environment, permissions, deployment, and rollback reviewer.
- **Gemini** — API contract, schema, logic, edge-case, security, and regression reviewer.

The default rule is:

> One writer, two reviewers, one final integration path.

Do not let multiple agents edit the same task concurrently unless the user explicitly overrides this rule.

## Telegram Commands

Use these entry points:

```text
/gpt <task>
/hermes <task>
/gemini <task>
```

Examples:

```text
/gpt Reply exactly GPT_OK
/hermes Reply exactly HERMES_OK
/gemini Reply exactly GEMINI_OK
```

## Required Task Structure

For non-trivial work, assign a task ID and state the phase.

Preferred task template:

```text
/gpt TASK <TASK-ID>

GOAL:
<what must be achieved>

SCOPE:
<what may be changed>

DO NOT:
- do not modify unrelated code
- do not change API schema unless explicitly approved
- do not add API keys or secrets
- do not print tokens, passwords, private keys, or .env contents

PHASE:
ANALYZE | IMPLEMENT | FINALIZE

REPORT:
1. root cause or design
2. affected or changed files
3. risks
4. tests
5. acceptance status
```

## Standard Workflow

### Phase 1 — GPT/Codex Analysis

Start with analysis only for a new feature, bug, or architectural change.

```text
/gpt TASK <TASK-ID> ANALYZE

Analyze the requested change.
Do not modify files in this phase.

Report:
- design or root cause
- affected files
- affected functions
- API impact
- minimal implementation plan
- test plan
```

Do not proceed to implementation until the scope and likely root cause are sufficiently clear.

### Phase 2 — Hermes Runtime Review

Use Hermes when the change can affect Linux/runtime behavior, deployment, services, permissions, environment variables, networking, or rollback.

```text
/hermes TASK <TASK-ID> REVIEW

Review only from the Linux/runtime perspective.

Check:
- systemd
- process model
- environment
- file permissions
- service restart requirements
- deployment risk
- rollback plan

Do not modify code.
```

Hermes should return an outcome such as `APPROVE`, `REQUEST_CHANGES`, or `BLOCKED`, with reasons.

### Phase 3 — Gemini API and Logic Review

Use Gemini for API, schema, logic, security, and edge-case review.

```text
/gemini TASK <TASK-ID> REVIEW

Review the proposed design.

Focus on:
- API contract
- request payload
- response schema
- invalid input
- edge cases
- security
- regression risk

Do not modify code.
```

Gemini should return `APPROVE`, `REQUEST_CHANGES`, or `BLOCKED`, with specific findings.

### Phase 4 — Decision

Reconcile reviewer findings before coding.

When reviewers disagree, produce a compact decision table containing:

- issue
- GPT/Codex position
- Hermes position
- Gemini position
- final decision

Accepted reviewer findings become explicit implementation constraints.

### Phase 5 — GPT/Codex Implementation

GPT/Codex is the default single writer.

```text
/gpt TASK <TASK-ID> IMPLEMENT

Implement the accepted plan and reviewer findings.

Requirements:
- change only necessary files
- avoid unrelated refactors
- preserve existing API schema unless approved
- do not introduce secrets
- add or update tests
- run the appropriate test suite

Report:
- changed files
- implementation summary
- test command
- test result
- remaining risks
```

## Single-Writer Rule

Default ownership for one task:

```text
GPT/Codex = WRITE
Hermes    = REVIEW
Gemini    = REVIEW
GPT/Codex = FINAL INTEGRATION
```

Avoid concurrent edits by GPT/Codex, Hermes, and Gemini to the same file or task. This reduces patch conflicts, race conditions, unclear ownership, regressions, and difficult rollback.

## Bug Diagnosis

For an unknown Telegram or Meeting Room failure, diagnose before editing.

Example:

```text
/gpt TASK BUG-001

Telegram /gpt failed with a Meeting Room request error.
Diagnose only. Do not modify files.

Classify the failure as one or more of:
AUTH
SCHEMA
ROUTE
PROVIDER
RUNTIME
NETWORK
APPLICATION
```

If the symptom is an HTTP 4xx/5xx or contract mismatch, ask Gemini to compare payloads with the API/OpenAPI schema.

If the symptom involves services, process state, environment, permissions, or deployment, ask Hermes to inspect runtime state.

Only after the root cause is confirmed should GPT/Codex perform a minimal fix.

## Verification Order

Agent claims are not acceptance evidence.

Use this evidence priority:

```text
Live Telegram E2E
>
Integration Test
>
Unit Test
>
Runtime/Service Evidence
>
Logs
>
Agent Narrative
```

### Unit Tests

Run the project-appropriate tests, normally:

```bash
pytest -q
```

Do not report success unless the actual command succeeds.

### Runtime Verification

For the E500 Telegram service, verify the user service directly:

```bash
systemctl --user show gpt-codex-telegram.service \
  -p ActiveState \
  -p SubState \
  -p MainPID \
  -p NRestarts
```

Expected healthy state includes:

```text
ActiveState=active
SubState=running
NRestarts=0
```

Confirm the Telegram polling process:

```bash
pgrep -af 'python3 -m adapters.telegram'
```

There should be exactly one intended polling process.

### Telegram Live E2E

After tests and runtime checks, validate from the actual Telegram client:

```text
/gpt Reply exactly GPT_OK
/hermes Reply exactly HERMES_OK
/gemini Reply exactly GEMINI_OK
```

All three routes must return a valid response before declaring the three-agent Telegram workflow operational.

If the adapter intentionally adds agent labels or prefixes, validate the response token semantically unless the acceptance criteria explicitly require byte-for-byte exact output.

## Git Workflow

Use a task branch for non-trivial changes when appropriate:

```bash
git switch -c feature/<TASK-ID>
```

Before commit:

```bash
git status
git diff
pytest -q
```

Commit only after review and tests:

```bash
git add <explicit-files>
git commit -m "feat: <short description>"
```

Push with normal user credentials:

```bash
git push -u origin feature/<TASK-ID>
```

Do not use `sudo git`, `sudo ssh`, `git push --force`, destructive reset, or rebase unless the user explicitly authorizes that operation for a specific reason.

## Secret Handling

Never expose or transmit:

- `.env` contents
- API keys
- access tokens
- passwords
- SSH private keys
- provider credentials

Public SSH keys such as `~/.ssh/id_ed25519.pub` are safe to display when needed. Private keys such as `~/.ssh/id_ed25519` must never be displayed.

When checking a secret-backed environment variable, report status only, for example:

```text
MEETING_API_TOKEN present=yes length=<n>
```

Do not print the value.

The Telegram bridge should depend only on the credentials it actually needs. Provider credentials should remain in their own worker/provider authentication paths rather than being copied into the Telegram bridge environment without a proven requirement.

## E500 Project Notes

The current E500 repository uses the Telegram bridge under:

```text
gpt-codex-bridge/
```

The live Telegram user service is:

```text
gpt-codex-telegram.service
```

When investigating live behavior, validate the real service, process, working directory, environment source, and command line rather than assuming that a local test process is the deployed process.

## Completion Report

At the end of a task, report a concise acceptance summary:

```text
TASK: <TASK-ID>
GPT/Codex: PASS | FAIL | N/A
Hermes review: APPROVE | REQUEST_CHANGES | N/A
Gemini review: APPROVE | REQUEST_CHANGES | N/A
Tests: PASS | FAIL
Runtime: PASS | FAIL | N/A
Telegram E2E: PASS | FAIL | N/A
Git status: clean | dirty
Push: PASS | FAIL | NOT_RUN
Overall: PASS | FAIL
```

Only mark `Overall: PASS` when all required acceptance gates for the task have passed.

## Core Principle

GPT/Codex writes, Hermes verifies the system/runtime layer, Gemini challenges the API and logic layer, and objective tests plus Telegram live E2E decide whether the work is truly complete.
