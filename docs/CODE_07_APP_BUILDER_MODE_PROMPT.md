# CODE-07 — App Builder Mode Prompt

## Purpose

Start the first narrow app-building lane after the code operator loop is stable.

The first version should build one reliable local stack instead of trying to support every framework.

## Target stack

- React or static frontend under a generated app folder
- FastAPI backend when needed
- local preview instructions
- tests or smoke checks

## Required flow

1. Ask for missing requirements only when needed.
2. Create a small plan.
3. Scaffold the app in a safe generated-apps folder.
4. Run a smoke check.
5. Report files, run command, and next steps.

## Acceptance

Xoduz can take a simple app request and produce a local runnable starter without touching unrelated project files.
