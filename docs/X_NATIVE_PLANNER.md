# X Native Planner

X Native Planner v1 turns inspection or repair-style requests into structured sandbox-only repair proposals, review bundles, Codex prompts, and result reviews.

UI URL: `http://localhost:3100`

API URL: `http://localhost:3101`

The old XV7 core is intentionally bypassed. X Native is the new control baseline. Old XV7 is a parts yard and will be mined later for useful pieces only.

## Planner Output

Planner proposals include:

- problem summary
- exact current limitation
- proposed next repair
- probable cause
- proposed fix
- affected files
- validation commands
- rollback plan
- risk
- stage id when staged
- receipt path when saved
- `execution_allowed=false`
- `apply_allowed=false`
- `repo_write=false`
- `sandbox_only=true`

## Review Bundles

Review bundles are sandbox-only artifacts under `data/x_native/stages/review_bundles`.

They include:

- planner proposal
- intended file paths
- pseudo-diff preview text
- validation checklist
- rollback checklist
- human decision required
- safety flags
- recommended Codex prompt draft

Endpoints:

- `POST /x-native/review-bundle`
- `GET /x-native/review-bundles`
- `GET /x-native/review-bundles/latest`
- `GET /x-native/review-bundles/{bundle_id}`

The generated Codex prompt draft is copy-friendly task material only. Otis must paste the prompt/results to ChatGPT or another explicit authorization channel before any future implementation work is applied outside X Native.

## Prompt Factory and Result Intake

The operator loop is:

```text
X Native plan -> review bundle -> Codex prompt -> Codex result -> X Native review -> ChatGPT authorization -> human decision
```

Prompt Factory outputs include:

- prompt id
- source bundle id
- Codex-ready prompt
- guardrails summary
- expected files
- expected validation
- stop conditions
- `human_authorization_required=true`
- `execution_allowed=false`
- `apply_allowed=false`
- `repo_write=false`

Result Intake accepts pasted Codex completion text and extracts branch, commit, files changed, validation results, dirty files, safety claims, URLs, and next milestone. It compares the pasted report against the source bundle, expected files, denied paths, guardrails, and validation expectations.

Result Intake verdicts are:

- `pass`
- `fail`
- `needs_human_decision`
- `incomplete`

Endpoints:

- `POST /x-native/prompt-factory/from-latest`
- `POST /x-native/prompt-factory/from-bundle/{bundle_id}`
- `GET /x-native/prompts/latest`
- `GET /x-native/prompts`
- `POST /x-native/result-intake`
- `GET /x-native/result-intake/latest`

X Native result reviews are review-only. They do not authorize apply/write behavior. The generated authorization summary must be copied to ChatGPT or another external human authorization channel before any future write/apply decision.

## Sandbox Workspace

Workspace drafts are written only under:

```text
data/x_native/workspace
```

Workspace endpoints:

- `POST /x-native/workspace/draft`
- `GET /x-native/workspace`

Workspace drafts are sandbox-only and are not promoted to repo source. Absolute paths, `..`, Windows drive prefixes, and paths outside the workspace are rejected.

## Current Safety State

Allowed:

- inspect
- plan
- stage
- preview
- draft to sandbox

Not yet allowed:

- repo apply
- repo writes
- shell execution

## Validation

```powershell
python -m py_compile apps/x_native_api/main.py apps/x_native_api/planner.py
docker compose -f docker-compose.x-native.yml up -d --build
Invoke-RestMethod http://localhost:3101/health
Invoke-RestMethod http://localhost:3101/x-native/state
.\scripts\x_native_smoke.ps1
.\scripts\x_native_full_check.ps1
```
