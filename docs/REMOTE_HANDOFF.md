# Remote handoff

When only GitHub access is available, repository files and workflows can be updated, but local machine state cannot be verified.

GitHub-side work that can be done:

- inspect commits and tracked files
- patch tests and documentation
- add workflow checks
- commit safe repository changes

Local-only proof still requires access to the machine running the app:

- Docker service status
- local environment variables
- host-visible sandbox exports
- browser smoke against the live stack

Recommended local proof when access returns:

```powershell
git pull --ff-only
docker compose up -d --build xv7-core xv7-frontend
python -m pytest tests/test_intent_router.py tests/test_operator_github_proof_project.py tests/test_operator_chat_integration.py -q
npm test
npx playwright test e2e/xv7-browser-smoke.spec.mjs --reporter=line
```
