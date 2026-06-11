# CODE-08 — Workflow Learning Prompt

## Purpose

Teach Xoduz how to remember Otis's preferred project workflows without turning every correction into noisy chat output.

## Goal

When Otis corrects a workflow, Xoduz should create a reviewable workflow rule that can be approved, edited, disabled, or reused later.

## Example

Otis says:

```text
When I ask you to check the repo, I mean git status, latest commits, failing CI, current roadmap, and next action.
```

Xoduz should create a pending workflow record like:

```text
Workflow: repo_check
Steps:
1. inspect git status
2. inspect latest commits
3. inspect latest CI status
4. inspect roadmap docs
5. answer with current status and next action
```

## Required behavior

- Store workflow rules as brain records.
- Mark new workflow rules as pending review unless the correction is explicit and low risk.
- Keep normal chat clean.
- Show source IDs in compact receipts only.
- Prefer approved workflow rules over generic answers.

## Acceptance

Xoduz can learn how Otis works and apply that workflow in future turns without hallucinating or over-explaining.
