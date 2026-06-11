# B7 Local Operator Tools

## Goal

B7 introduces a local operator layer that can answer a narrow set of operational questions without mutating files, git state, or runtime state.

## Scope

Allowed actions in B7 are read-only:

- `repo_status`
- `repo_recent_commits`
- `list_project_files`
- `read_project_file`
- `runtime_health`
- `docker_compose_ps`
- `logs_summary`
- `memory_audit`

All actions return `OperatorActionResult` with:

- action identity and timestamps
- operation details and target
- summarized stdout/stderr and optional exit code
- structured `data`
- explicit safety metadata
- compact operator receipt string

## Safety Model

B7 enforces read-only behavior through two layers:

1. Policy guard in `OperatorManager`:
- mutation-style prompts are denied (`write`, `delete`, `commit`, `push`, `docker compose up`, etc.)
- denied requests return a structured receipt with `status=denied`

2. Action registry in `core/operator/registry.py`:
- only explicit read-only actions are registered
- unknown actions fail fast

## Receipts And Provenance

Operator-backed chat responses append an operator receipt:

- `Operator receipt: <action_name> <action_id> <status>; read_only=true; target=<target>; exit_code=<code>.`

For successful `repo_status` actions only, session metadata stores live-proof markers:

- `live_repo_check = true`
- append `{type: "repo_check", action_id, status}` to `tool_results`

This enables answer-contract behavior for questions like "Did you check the repo?" to be proof-based instead of guessed.

## Current Limitations

- No mutation support (intentional for B7)
- `read_project_file` returns a bounded content preview, not full large-file streaming
- Runtime checks are diagnostics only (GET/read-only shell access)
- Operator actions do not replace model inference for general conversation

## B7.1 Docker Runtime Hardening

- `xv7-core` image includes `git` so repo checks are operational in container runtime.
- `xv7-core` mounts the full repository read-only at `/workspace` and uses `XV7_OPERATOR_REPO_ROOT=/workspace` for repo actions.
- `repo_status` reports branch, upstream/sync status when available, clean/dirty state, and short status lines.
- If upstream sync cannot be determined, repo checks still return success with explicit limitation text.

Runtime-health probes now use container-internal service URLs by default:

- core: `http://localhost:8000`
- ollama: `OLLAMA_BASE_URL` defaulting to `http://ollama:11434`
- open-webui: `WEBUI_BASE_URL` defaulting to `http://open-webui:8080`
- frontend: `XV7_FRONTEND_INTERNAL_URL` defaulting to `http://xv7-frontend`

Each runtime probe includes structured fields:

- `checked_from`
- `service_name`
- `url_used`
- `reachable`
- `limitation`

Container-status strategy for B7.1 is Option A:

- `docker_compose_ps` runs only when Docker CLI and socket are both available.
- If unavailable, it returns a failed read-only receipt with explicit limitation text.
- It does not claim container status proof when availability checks fail.
- Expected response text when unavailable:
	- `Container status cannot be proven from inside xv7-core because Docker CLI/socket is unavailable. No action was run beyond the read-only availability check.`

New diagnostics action:

- `operator_environment` returns read-only capability metadata:
	- repo root
	- git availability
	- docker CLI/socket availability
	- service URL config
	- memory store path
	- `read_only_mode: true`

## Out Of Scope

- Editing files
- Running git mutations
- Restarting containers or changing runtime config
- Creating/deleting memory records through operator tools

## Validation Checklist

B7 acceptance requires tests for:

- schema required fields and receipt format
- registry read-only-only action set
- path boundary denial for file reads outside repo root
- mutation prompt denial by operator manager
- proof-gated repo-check claims in chat metadata/answers
- honesty on failed operator action output
- operator receipt presence in operator-backed chat replies

## B7.2 Receipt UX And Action History

Assistant messages now include structured payload metadata while preserving plain text fallback content.

Message metadata includes:

- `visible_text`
- `context_receipt`
- `operator_receipts`
- `memory_receipts`
- `model_use_receipt`
- `policy_provenance`
- `warnings`
- `action_history_refs`

Operator receipt structure includes:

- `action_id`
- `action_name`
- `status`
- `mode`
- `target`
- `receipt_label`
- `read_only`
- `started_at`
- `completed_at`
- `exit_code`
- `safety`
- `summary`
- `limitation`
- `data_preview`

Session-scoped action history tracks read-only operator actions (success/failed/denied) and powers:

- `Did you check the repo?`
- `What did you just check?`
- `Show the last operator receipt.`
- `What operator actions have run?`

Frontend renders operator receipts as compact chips below the natural assistant answer. Receipt details are collapsible, and Operator Activity shows recent actions with time/status/target/summary/action id.
