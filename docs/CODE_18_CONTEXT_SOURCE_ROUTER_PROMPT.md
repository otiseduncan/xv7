# CODE-18 — Context Source Router Prompt

## Purpose

Define how Xoduz chooses the right source before answering, so answers stay local-first, honest, and receipt-based.

This prompt defines routing order, confidence policy, and hard no-hallucination rules.

## Prompt

```text
CODE-18 — Context Source Router

You are working in XV7/Xoduz.
Implement a context source router that chooses the best source before answering.

Core requirement:
Never answer from vibes when an inspectable source is required.

Priority order:
1. Current user request
2. Active Focus
3. Live inspected repo/tool result
4. Current verified records
5. Historical records only when relevant
6. Model reasoning only when clearly labeled as reasoning

Routing table:
A) Use Active Focus when:
- request is continuation of current session goal
- user asks "what are we working on" or equivalent
- active focus clarifies ambiguity

B) Use live repo inspection when:
- user asks repo status / branch / changed files / CI state
- user asks "what changed" / "what is left" in code lane context
- answer requires current filesystem/runtime state

C) Use Brain Records when:
- request is policy/workflow/memory-like
- verified status is needed and no fresher live source exists
- context is historical and explicitly asked

D) Ask clarification when:
- request could map to multiple sources with low confidence
- user intent is broad and source selection changes outcome

E) Say unavailable when:
- required source cannot be inspected now
- tool/bridge is offline
- evidence required but missing

F) Use web/research later when:
- user asks for external/non-local facts
- repo/local context cannot answer
- and policy allows external access

Confidence levels:
- high: exact source match and fresh evidence exists
- medium: likely source fit, partial evidence
- low: ambiguity or stale/missing evidence

Do-not-answer-without-inspection cases (must inspect first or say unavailable):
- "is CI green?"
- "what branch/dirty files are we on?"
- "did tests pass?"
- "what changed in the repo?"
- "is service X up right now?"

No-hallucination policy:
- never claim inspected state if no inspection receipt exists
- never claim test pass without command result
- never claim CI state without proof source

Source pins/receipts:
- keep compact source pins in answer metadata
- avoid giant proof spam in visible answer
- include source type, confidence, and limitation when applicable

Suggested compact source pin:
{
  "source_type": "active_focus|live_repo|brain_verified|brain_history|reasoning|unavailable",
  "confidence": "high|medium|low",
  "record_ids": [],
  "tool_receipts": [],
  "limitation": ""
}

Acceptance:
- routing table is implemented/documented
- confidence levels are defined and used
- no-inspection-required cases are enforced
- examples map to expected source routes

Return:
- router decision flow
- do-not-answer gate list
- source pin shape
- tests to validate routing correctness
```

## Example Prompts and Expected Routing

1. Prompt: "Check the repo and tell me what is left."
- Expected route: live repo inspection
- Confidence: high
- If unavailable: explicit unavailable with limitation

2. Prompt: "What are we working on right now?"
- Expected route: active focus
- Confidence: high

3. Prompt: "Why did you say that yesterday?"
- Expected route: brain records + historical context if relevant
- Confidence: medium

4. Prompt: "Is CI green right now?"
- Expected route: live CI/repo inspection only
- If unavailable: do not guess; return unavailable

## Validation Commands

```powershell
python -m pytest tests/ -v --tb=short --asyncio-mode=auto
python -m ruff check core/ tests/
python -m ruff format --check core/ tests/
```
