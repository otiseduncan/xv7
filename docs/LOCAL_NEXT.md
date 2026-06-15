# Local next steps

This file is for the limited remote desktop session.

Current local fix waiting to be committed:

- public app code
- public app tests
- browser smoke spec

Local validation to run from the repo root:

1. Check git status.
2. Run the frontend unit tests.
3. Run the frontend build command.
4. Run the browser smoke test.
5. Check git status again.

Commit only the source and test fix. Do not commit browser test output artifacts unless they are explicitly requested for proof review.

Recommended commit message:

fix(ui): settle pending assistant cards on failed sends

After pushing, ask for a GitHub side verification pass.

Remaining local proof later:

- host sandbox path configured
- containers started with that path
- preview only creates chat preview
- export writes files to host sandbox
- generated sandbox project can be pushed when requested
