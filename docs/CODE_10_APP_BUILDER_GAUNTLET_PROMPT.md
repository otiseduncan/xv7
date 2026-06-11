# CODE-10 — App Builder Gauntlet Prompt

## Purpose

Create a repeatable proof that Xoduz can build a small app from a prompt without hallucinating, losing context, or skipping validation.

This is the first real test of the builder loop.

## Why this matters

The goal is not for Xoduz to say she can build apps.

The goal is for Xoduz to prove it by completing a controlled flow:

```text
request -> requirements -> plan -> scaffold -> patch -> test -> report
```

The gauntlet should be small enough to run often and strict enough to catch fake success.

## First target app

Use one narrow target:

```text
Local Task Tracker
```

Requirements:

- simple frontend
- local backend route or static fallback depending on current stack
- create/list/update/delete tasks
- no cloud dependency
- no external auth
- clear README instructions
- tests or smoke checks

## Required gauntlet script

Add:

```text
scripts/gauntlet-app-builder.mjs
```

or, if the repo prefers Python for this lane:

```text
scripts/gauntlet_app_builder.py
```

The script should verify that the builder output includes:

- generated app folder
- README
- package or run instructions
- at least one frontend file
- at least one test or smoke validation
- no secrets
- no writes outside the approved generated-apps directory

## Suggested generated app path

```text
generated-apps/task-tracker/
```

This directory should be ignored or treated carefully if generated during local runs. The gauntlet can use a temporary directory to avoid committing generated output.

## Operator behavior

When Otis asks:

```text
Xoduz, build me a task tracker app.
```

Xoduz should respond with a controlled workflow:

1. summarize the requested app
2. ask at most two clarifying questions if truly needed
3. choose the approved starter stack
4. create a patch plan
5. request approval before writing files
6. write only inside approved app directory
7. run validation
8. report changed files and run commands

## Acceptance criteria

The gauntlet passes only if:

- the app folder is created in the approved path
- no files are written outside the approved path
- the app has a visible UI entry point
- the app has run instructions
- the app has at least one validation check
- the final report names exactly what was created
- failures are reported honestly

## Anti-goals

Do not start with:

- multi-framework support
- user accounts
- database migrations
- deployment automation
- paid API keys
- plugin marketplaces

The first builder proof should be boring and reliable.

## Done means

CODE-10 is done when this command can prove the flow:

```powershell
node scripts/gauntlet-app-builder.mjs
```

or:

```powershell
python scripts/gauntlet_app_builder.py
```

and it produces a pass/fail report that Otis can trust.
