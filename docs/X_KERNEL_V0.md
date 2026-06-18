
# X Kernel v0

X Kernel v0 is the first internal decision-making layer for X / Xoduz.

It is not another chat window.

It is not a sidecar UI.

It is the operating layer that the existing XV7/X chat route will call before deciding whether to answer normally, run a safe tool, route a structured package to X Prompt Inbox, or require confirmation.

## Current kernel files

* core/x_kernel/types.py
* core/x_kernel/decision.py
* scripts/xv7_kernel_probe.py

## Current decision object

The kernel returns an XDecision object with:

* intent
* risk
* route
* summary
* requires_confirmation
* command
* package_action
* reasons

## Current routes

* answer_only
* tool
* prompt_inbox
* draft_package
* require_confirmation

## Current intents

* empty
* answer_only
* state
* diagnose
* readiness
* proof
* x_prompt_package
* repo_change_request
* system_control_request

## Current proof commands

Run these from the repo root:

python scripts\xv7_kernel_probe.py "diagnose yourself"
python scripts\xv7_kernel_probe.py "what is your current state"
python scripts\xv7_kernel_probe.py "TASK: test X_ACTIONS: CREATE_FILE data/x_runtime/tmp/kernel.txt"

Expected routing:

* diagnose yourself -> intent diagnose, route tool
* what is your current state -> intent state, route tool
* TASK + X_ACTIONS -> intent x_prompt_package, route prompt_inbox

## Next target

Wire the existing XV7/X chat route into XDecisionKernel.

Target flow:

Existing XV7/X chat UI
-> existing backend message route
-> XDecisionKernel
-> answer_only, tool, prompt_inbox, draft_package, or require_confirmation
-> response back to existing UI
-> proof receipt when a tool or package path is used

## Guardrail

Do not create another chat window for this path.

PowerShell is only the temporary loader until the existing UI can route messages through XDecisionKernel.
