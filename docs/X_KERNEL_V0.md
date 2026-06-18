# X Kernel v0

X Kernel v0 is the first internal decision-making layer for X / Xoduz.

It is not another chat window.

It is not a sidecar UI.

It is the operating layer that the existing XV7/X chat route calls before deciding whether to answer normally, run a safe read-only tool, stage an action for review, or require explicit future authority.

## Current kernel files

* core/x_kernel/types.py
* core/x_kernel/decision.py
* core/x_kernel/tool_runner.py
* core/x_kernel/action_stager.py
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
* network_control_request

## Current real API path

The existing XV7/X API route is the integration path:

```text
POST /sessions/{session_id}/messages
```

The route now performs this flow:

```text
existing backend message route
-> XDecisionKernel
-> kernel-visible response for safe kernel intents
-> safe read-only tool runner for diagnose/readiness/state/proof
-> action staging for write/control/package requests
-> receipt-backed metadata
```

## Safe tool runner

The tool runner is allowlisted and container-native.

Allowed safe read-only intents:

* diagnose
* readiness
* state
* proof

The tool runner must not:

* execute arbitrary shell
* apply prompt packages
* mutate repository files
* run system control commands
* run network control commands

Tool output is returned in response metadata under:

```text
x_kernel_tool_result
```

Tool receipts are written under:

```text
data/x_inbox/receipts
```

## Authority staging

Write/control/package requests are staged, not executed.

Stage receipts must include:

* status: staged_pending_approval
* execution_allowed: false
* approval_required: true
* approval_mode: explicit_future_authority_flow
* safety.direct_execution: false
* safety.repo_write: false
* safety.system_control: false
* safety.network_control: false

Staged action output is returned in response metadata under:

```text
x_kernel_action_stage
```

The visible response for staged actions is authoritative staging text only. Older generated/model content must not leak into staged write/control responses.

## Stage review routes

Review-only routes:

```text
GET /x-kernel/stages
GET /x-kernel/stages/latest
GET /x-kernel/stages/{stage_id}
```

Cancel route:

```text
POST /x-kernel/stages/{stage_id}/cancel
```

Cancellation writes a cancellation receipt and does not execute the staged action.

Preview-preparation route:

```text
POST /x-kernel/stages/{stage_id}/preview
```

Preview preparation marks a staged action as preview_ready and writes a preview receipt. It still does not execute, apply, or mutate repository files. It is a handoff step before a future explicit apply flow.

Preview packages are inert review artifacts. They include source_text, suggested_path, draft_steps, and rendered_preview, but remain:

* is_executor_ready: false
* preview_only: true
* execution_allowed: false

Approval-validation route:

```text
POST /x-kernel/stages/{stage_id}/validate-approval
```

Approval validation records operator approval intent only. It requires a stage-specific phrase:

```text
APPROVE_STAGE_<stage_id>
```

Approval validation writes a receipt and marks the stage approval_validated_preview_only. It still does not execute, apply, or mutate repository files. It keeps:

* execution_allowed: false
* apply_allowed: false
* safety.approval_validation_only: true

## Current proof commands

Run these from the repo root:

```powershell
python scripts\xv7_kernel_probe.py "diagnose yourself"
python scripts\xv7_kernel_probe.py "what is your current state"
python scripts\xv7_kernel_probe.py "TASK: test X_ACTIONS: CREATE_FILE data/x_runtime/tmp/kernel.txt"
python scripts\xv7_x.py diagnose --save
python scripts\xv7_x.py readiness --save
```

Expected routing:

* diagnose yourself -> intent diagnose, route tool
* what is your current state -> intent state, route tool
* TASK + X_ACTIONS -> intent x_prompt_package, route prompt_inbox
* repo write language -> staged_pending_approval, execution_allowed false

## Guardrail

Do not create another chat window for this path.

PowerShell is only the temporary loader until the existing UI can route all approved actions through XDecisionKernel.
