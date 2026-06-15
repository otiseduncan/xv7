# Sandbox proof checklist

Purpose: keep the next validation pass clear and honest.

The sandbox export target for the local machine is the approved host sandbox folder. The local environment must be configured before containers are recreated.

Proof boundary:

- GitHub can store this checklist and related tests.
- GitHub cannot prove host folder visibility.
- Local validation must prove the folder exists, the app containers use it, and generated files appear there.

Proof order:

1. Pull latest repository changes.
2. Confirm the local sandbox export setting is present without exposing secrets.
3. Recreate the app containers so the mount setting is active.
4. Confirm service health.
5. Run frontend unit checks.
6. Run the browser smoke check.
7. Send a website preview request and confirm it stays preview-only.
8. Send an explicit sandbox export request and confirm files appear in the host sandbox folder.
9. Capture final git status.

Pass criteria:

- Preview-only requests do not create host files.
- Explicit export requests create host files.
- The browser smoke check passes after the pending assistant-card fix.
- No generated test artifacts are committed unless intentionally requested.

Manual result fields to report back:

- git state
- sandbox setting present or missing
- container health
- unit checks
- browser smoke
- preview-only result
- sandbox export result
- generated project path
- final git state
