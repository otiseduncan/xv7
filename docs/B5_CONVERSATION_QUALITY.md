# B5 Conversation Quality and Hallucination Control

B5 adds a response policy layer focused on honesty, certainty control, and fallback clarity.

## What B5 enforces

- No hallucinated repo/runtime check claims.
- No fake memory claims.
- No fake "I checked" statements without proof metadata.
- No hidden reasoning replay.
- Explicit missing-context responses instead of guessing.
- Verified vs unverified wording separation.
- Compact context receipt on every answer.

## Implementation

- Policy module: `core/brain/answer_contract.py`
- Relevance selection and scoped context assembly: `core/brain/manager.py`
- Runtime integration: `core/main.py`

## Behavior highlights

- `Are we beta ready?`
  - Uses Verified Status + Active Focus.
  - States lack of beta-ready proof unless verified record exists.

- `Did you check the repo?`
  - Requires explicit live-check proof in session metadata.
  - Otherwise states no live-check proof is available.

- `What failed?`
  - Uses failure evidence from Verified Status only.
  - If none is loaded, says no current failure record is loaded.

- `What do you remember?`
  - Uses Memory record only.
  - Does not treat Knowledge/Verified Status as memory.

- `Make a guess ...`
  - Clearly labeled as unverified guess.

- `What model are you using?`
  - Uses model-use receipt proof if present.
  - Otherwise states that model cannot be proven from loaded context alone.
