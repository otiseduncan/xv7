# X Kernel Authority State

This document records the current authority boundary for the XV7/X Kernel.

## Current execution model

The real `/sessions/{session_id}/messages` API route now feeds user text through the X Kernel decision layer before unsafe work is allowed.

Safe read-only intents may execute through the allowlisted container-native tool runner:

- `diagnose`
- `readiness`
- `state`
- `proof`

Write/control/package requests are staged, not executed.

## Staging flow

The authority chain is:

1. Stage the requested action.
2. Review the staged receipt.
3. Cancel the stage or prepare a preview.
4. Future explicit authority flow may convert an approved preview into an executable package.

## Review endpoints

- `GET /x-kernel/stages`
- `GET /x-kernel/stages/latest`
- `GET /x-kernel/stages/{stage_id}`

These routes read receipt-backed staged actions only.

## Cancel endpoint

- `POST /x-kernel/stages/{stage_id}/cancel`

This route writes a cancellation receipt and marks the staged action as cancelled. It does not execute the staged action.

## Preview endpoint

- `POST /x-kernel/stages/{stage_id}/preview`

This route marks a stage as preview-ready and adds an inert `preview_package` draft to the preview receipt.

The preview package is intentionally not executor-ready. It is a review artifact only:

- `preview_only: true`
- `is_executor_ready: false`
- `execution_allowed: false`
- `approval_required: true`

The preview may include a suggested safe path under `data/x_runtime/tmp/`, but it does not write that path and does not apply any package.

## Guardrail

No current authority-stage route applies repo changes, runs arbitrary shell commands, changes system state, or performs network control.
