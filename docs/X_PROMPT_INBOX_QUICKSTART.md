# X Prompt Inbox Quickstart

Run these commands from the repo root in Windows PowerShell.

## Run Self Check

```powershell
python scripts\xv7_x.py self
```

## Run Doctor And Save Proof

```powershell
python scripts\xv7_x.py doctor --save
```

## Self-Diagnostics

```powershell
python scripts\xv7_x.py diagnose --save
python scripts\xv7_x.py proof
```

## Submit A Prompt

```powershell
@'
TASK: Test prompt intake.

GOAL:
Confirm X can receive a prompt package and save a receipt.

SUCCESS:
A completed receipt exists under data/x_inbox/receipts.
'@ | python scripts\xv7_prompt.py submit --source powershell
```

## Run Next Prompt

```powershell
python scripts\xv7_prompt.py run-next
```

## List Prompt Inbox

```powershell
python scripts\xv7_prompt.py list
```

## Submit A Diagnostic Prompt

```powershell
@'
TASK: Run X self-diagnostics.

GOAL:
Tell Otis what is wrong with X right now and recommend the next action.

SUCCESS:
A diagnosis receipt exists at data/x_inbox/receipts/latest_diagnose.json.
'@ | python scripts\xv7_prompt.py submit --source powershell

python scripts\xv7_prompt.py run-next
```

## Applying Structured Prompt Packages

Submit a package:

```powershell
@'
TASK: Create X test note

GOAL:
Confirm X can apply a structured prompt package.

X_ACTIONS:
CREATE_FILE data/x_runtime/tmp/x_prompt_apply_test.txt
---CONTENT---
X prompt package apply test.
---END_CONTENT---

RUN_CHECK python scripts/xv7_x.py diagnose --save

SUCCESS:
The test note exists and diagnosis receipt is updated.
'@ | python scripts\xv7_prompt.py submit --source powershell
```

Preview and apply:

```powershell
python scripts\xv7_prompt.py list
python scripts\xv7_prompt.py preview TASK_ID
python scripts\xv7_prompt.py apply TASK_ID
python scripts\xv7_x.py readiness --save
python scripts\xv7_x.py proof
```

Run oldest pending with apply:

```powershell
python scripts\xv7_prompt.py run-next --apply
```
