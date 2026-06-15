# Remote forensic audit register — 2026-06-15

This register captures the items that can be handled from GitHub-only access while local keyboard, Docker, and host sandbox access are unavailable.

## Remote-safe items already handled

- Added frontend unit/build workflow in `.github/workflows/frontend.yml`.
- Added `docs/REMOTE_HANDOFF.md` to separate GitHub-side work from local-only proof.
- Added `tests/test_operator_github_status_contract.py` to prove the operator repo inspection uses `git status --short --branch`, not the older porcelain-only route.
- Updated `README.md` clone instructions to use `otiseduncan/xv7` instead of the placeholder organization.
- Updated `README.md` test instructions to include frontend unit/build commands and local browser smoke notes.
- Documented the host-visible sandbox export variable in `README.md`.

## Still local-only and not claimable from GitHub-only access

- Prove the Revo or Windows host is running.
- Prove Docker Desktop is healthy on the local machine.
- Prove the live stack starts locally.
- Prove the host sandbox folder exists and is writable.
- Prove generated website exports appear on the Windows host.
- Prove browser smoke against the live local stack.
- Prove a generated sandbox project can be committed and pushed from the local operator path.

## Remaining remote-safe candidates

These can be handled without local machine access:

1. Add more unit tests around preview-only versus sandbox-write routing.
2. Add tests that operator GitHub proof receipts always include exact failed command and stderr summary.
3. Add docs for the expected proof receipt fields for sandbox export and GitHub push.
4. Review README and docs for stale references after each route/workflow change.
5. Keep GitHub Actions focused on checks that can run in hosted CI.

## Required local proof later

When local access returns, run the proof sequence from `docs/REMOTE_HANDOFF.md` and capture whether each stage passes or fails. Do not mark local sandbox/export/browser proof complete until that local receipt exists.
