# Code 8: Browser/UI Proof and Receipt Visibility

## Scope

Code 8 is intentionally narrow. It is not a UI redesign and it is not a new communication feature. It exists to prove that the browser-facing chat surface presents the Code 6/Code 7 communication behavior calmly and correctly.

The concern being tested is:

- normal assistant answers should stay readable;
- compact receipts should be visible enough to prove what happened;
- detailed provenance should be available on demand, not dumped into the main answer;
- copied assistant messages should not include raw internal metadata.

## Why this was added after Code 7

Code 7 proved the runtime/API contract:

- Active Focus updates are policy-only;
- persistence uses brain records;
- same-session and fresh-session recall work;
- model fallback is avoided for the protected communication path.

Code 8 proves the browser layer does not undo that work by exposing noisy metadata in the visible answer.

## Acceptance criteria

Code 8 passes when the UI proves all of the following:

1. Active Focus update responses render a clean `.chat-visible-text` answer.
2. The visible answer does not contain raw keys such as `policy_provenance`, `context_receipt`, `model_use_receipt`, or `source_record_ids`.
3. Policy-only Active Focus turns do not show a model chip in the assistant message.
4. Compact focus proof appears as a receipt chip, for example `Focus: XV7-FOCUS-0800`.
5. Detailed provenance remains available in the collapsed `Why this answer?` drawer.
6. Copying an assistant message includes the visible answer and compact receipts only, not raw provenance metadata.

## Automated proof

Run from the repo root:

```powershell
npm test -- public/app.code8.test.js
```

The focused Code 8 test file is:

```text
public/app.code8.test.js
```

It uses jsdom and a mocked runtime response to exercise the real `Xv7UI` browser controller. The mock intentionally returns a structured raw assistant `content` payload while also supplying `metadata.visible_text`. The test verifies that the UI renders the safe visible text instead of leaking the raw structured payload.

## Recommended regression run

After Code 8 changes, run:

```powershell
$env:PYTHONPATH = (Get-Location).Path
pytest tests/test_code7_runtime_communication_proof.py
pytest
npm test -- public/app.code8.test.js
npm test
```

Expected result after this block:

```text
pytest: green
vitest: green
```

## Manual browser proof

With the app running locally, open the browser UI and send:

```text
change your active focus to browser/UI proof and receipt visibility
```

Then verify:

- The assistant answer is short and natural.
- The answer text does not print raw metadata fields.
- A compact focus/source receipt is visible near the answer.
- The `Why this answer?` drawer exists and is closed by default.
- Opening the drawer shows response mode/provenance details.
- Copying the assistant message includes only the answer and compact receipts.

## Non-goals

Code 8 does not attempt to:

- redesign the chat layout;
- change Active Focus persistence;
- change model routing;
- add new runtime behavior;
- introduce Playwright/browser infrastructure.

Those are separate scopes if needed later.
