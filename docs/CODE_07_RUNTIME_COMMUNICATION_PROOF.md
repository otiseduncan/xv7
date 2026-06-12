# Code 7 — Runtime Communication Proof

Code 7 proves that the communication routing fixed in Codes 5–6 works through the runtime API, not only through isolated record-loader tests.

## Goal

Prove the following behavior end-to-end:

1. Natural-language Active Focus updates are intercepted before model fallback.
2. The Active Focus record is persisted to the runtime brain-record store.
3. The same session can recall the changed focus.
4. A fresh session can load the persisted focus from runtime brain records.
5. Focus-guided communication follow-ups use the deterministic policy path.
6. Runtime metadata proves `policy_only`, `fallback_used=false`, and no model receipt.
7. The runtime brain-record API shows the active focus record as active.
8. A broken runtime record store fails loudly instead of pretending focus was saved.

## Files

- `scripts/code7_runtime_communication_proof.py`
  - Live HTTP proof harness for a running XV7 API.
  - Creates sessions, posts focus updates, checks provenance, checks fresh-session recall, checks guided follow-up metadata, and verifies active focus through `/runtime/brain/records`.

- `tests/test_code7_runtime_communication_proof.py`
  - Pytest API contract proof using `TestClient`.
  - Replaces the runtime model agent with a failing fake agent so any model fallback fails the test.
  - Covers the expected hard failure when runtime record storage is not writable as a directory.

## Local validation

From repo root:

```powershell
$env:PYTHONPATH = (Get-Location).Path
pytest tests/test_code7_runtime_communication_proof.py
pytest tests/test_brain_records.py tests/test_active_focus_runtime_store.py tests/test_operator_chat_integration.py tests/test_code7_runtime_communication_proof.py
pytest
```

Expected result:

- Code 7 test file passes.
- Targeted communication suite passes.
- Full suite passes.

## Live runtime proof

Start the XV7 API however the current runtime launcher expects, then run:

```powershell
$env:XV7_API_KEY = "<your-local-api-key>"
python scripts/code7_runtime_communication_proof.py --base-url http://127.0.0.1:8000
```

Expected output shape:

```json
{
  "ok": true,
  "elapsed_ms": 123.45,
  "steps": [
    {"name": "health", "ok": true, "detail": "runtime API reachable"},
    {"name": "session", "ok": true, "detail": "<session-id>"},
    {"name": "focus_update", "ok": true, "detail": "XV7-FOCUS-#### persisted"},
    {"name": "same_session_recall", "ok": true, "detail": "focus recalled without model fallback"},
    {"name": "fresh_session_recall", "ok": true, "detail": "persisted focus loaded in new session"},
    {"name": "guided_follow_up", "ok": true, "detail": "active-focus-guided response used"},
    {"name": "runtime_records", "ok": true, "detail": "active focus visible through runtime brain API"}
  ]
}
```

## Manual browser/API prompt sequence

Use the app UI or raw API and send these prompts in order:

1. `change your active focus to correct communication with operator Otis, learning his workflows, and reducing hallucinations with proof-first answers`
2. `what did I just change your focus to?`
3. Open a fresh session.
4. `what is your current active focus`
5. `so what are the next steps that we need to pursue an increasing fluid communication`

Expected behavior:

- First answer says Active Focus is updating and includes a new `XV7-FOCUS-*` record id.
- Follow-up answers mention communication / Otis / workflow / proof-first focus.
- The guided next-step answer is the deterministic communication plan, not a generic fallback.
- Metadata should show:
  - `answer_provenance.runtime_model_inference_proven=false`
  - `response_mode=active_focus_guided` for the guided follow-up
  - `model_used=policy_only` for the guided follow-up
  - `fallback_used=false` for the guided follow-up
  - `context_receipt.record_ids` contains the active focus record id

## Done criteria

Code 7 is complete when:

- `pytest tests/test_code7_runtime_communication_proof.py` passes.
- The full suite passes.
- The live script returns `ok: true` against the running API.
- Browser/manual prompt sequence matches the expected behavior.
