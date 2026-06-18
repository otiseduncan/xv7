
# X State Command

The X state command gives Otis and X a quick human-readable summary of X current condition.

## Purpose

The script scripts/xv7_state.py reads X Native proof receipts and answers:

* Who is X?
* Where is X currently running?
* What branch is active?
* Is the repo dirty?
* What was the latest diagnosis status?
* What was the latest readiness status?
* What was the latest apply result?
* What is the first blocker?
* What should happen next?
* Where is the proof?

## Commands

Run from the repo root:

python scripts\xv7_state.py
python scripts\xv7_state.py --save
python scripts\xv7_state.py --json

## Design

This is a sidecar command. It avoids editing large legacy files and gives X a clean way to extend her own self-reporting system.

## Next target

After the state command works, the next build target is a chat/API bridge into the X Prompt Inbox.

## Note

This version was repaired with an encoded payload because pasted Markdown stripped Python indentation in an earlier prompt package.
