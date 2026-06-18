# X Native Mode

X is Otis Duncan's assistant. X currently lives on the Omega desktop, and Omega is a host profile, not a separate identity or mode.

X Native baseline exists so X can receive prompt packages directly, inspect current state, write proof receipts, and prepare for self-building without requiring every build prompt to be fed through VS Code.

## Baseline Pieces

- X Prompt Inbox is the bridge from ChatGPT, PowerShell, and VS Code into X.
- X Doctor is X's first set of eyes for repo, tool, and write-readiness checks.
- X Proof Ledger is X's memory of actions and results.
- X Self Model records who X is, where she is hosted, and what she is becoming capable of doing.

## Authority Levels

- observe: inspect state and report findings.
- developer_write: prepare or apply ordinary repo edits with proof.
- system_admin_staged: staged system operations with explicit operator boundaries.
- break_glass_destructive: destructive disk, boot, firmware, or system actions requiring explicit future confirmation protocols.

This pass implements observe, prompt intake, developer-write readiness checks, and proof receipts only. It does not implement arbitrary command execution, destructive actions, or a full autonomous operator.

Future passes can add real patch application, test execution routing, Docker operation, and an operator broker.

## Self-Diagnostics

X self-diagnostics let X tell Otis what is wrong with her current repo/runtime condition, identify the first blocker, explain the probable cause, recommend the next action, and save proof.

Run:

```powershell
python scripts\xv7_x.py diagnose --save
python scripts\xv7_x.py proof
```

Diagnostics check Python, platform, repo root, repo write readiness, X Prompt Inbox readiness, proof receipt writing, Git, Docker, Docker Compose config, model config, Ollama availability, and core service visibility.

This is still not autonomous execution. It is evidence gathering, interpretation, and proof.

## Applying Structured Prompt Packages

X Prompt Packages give X controlled repo hands without unrestricted shell access. A package can create, update, append, or replace text in files inside the repo root, then run a small allowlist of checks.

Supported actions in this pass:

- CREATE_FILE
- UPDATE_FILE
- APPEND_FILE
- REPLACE_TEXT
- RUN_CHECK

Safety rules reject path traversal, writes outside the repo, writes into `.git/`, destructive disk/admin wording, shell operators, and commands outside the RUN_CHECK allowlist.

Run:

```powershell
python scripts\xv7_prompt.py package-help
python scripts\xv7_prompt.py preview TASK_ID
python scripts\xv7_prompt.py apply TASK_ID
python scripts\xv7_prompt.py run-next --apply
python scripts\xv7_x.py readiness --save
```

This is the controlled bridge from editor-fed prompts to X-applied prompt packages. It is not full autonomous command execution.
