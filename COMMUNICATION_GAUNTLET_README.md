# XV7 Communication Gauntlet Kit

This kit gives you a repeatable way to find weak communication spots in Xoduz.

It has two lanes:

1. **API lane** — fast, automated scoring through the backend.
2. **Browser typing lane** — opens the real UI and types every prompt like you would, with slow motion so you can watch it.

## What this tests

- Identity/persona
- Directness and frustration handling
- Runtime date grounding
- Short-term session memory
- Current-context awareness
- Preview vs build routing
- Operator/protected-action guardrails
- Normal use of words like fix/build/create
- Technical depth
- Proof honesty
- Format following
- Model limitation diagnosis
- Browser/UI response behavior

Total cases: **138**

## Install / copy

Copy these files into your repo root:

```text
communication-gauntlet-cases.json
scripts/run-communication-gauntlet-api.mjs
scripts/run-communication-gauntlet-browser.mjs
```

## Start XV7 first

In one VS Code terminal, start your backend/frontend the normal way.

Common examples:

```powershell
cd X:\XV7\xv7
npm run dev
```

Or use your existing launcher if that starts both API and web.

## API gauntlet

In VS Code terminal:

```powershell
cd X:\XV7\xv7
$env:XV7_API_BASE="http://127.0.0.1:8000"
$env:XV7_API_KEY="test-secret"
node scripts/run-communication-gauntlet-api.mjs
```

Reports:

```text
test-results/communication-gauntlet/api-results.json
test-results/communication-gauntlet/api-results.md
```

## Browser typing gauntlet

This physically types every prompt into the browser.

```powershell
cd X:\XV7\xv7
$env:XV7_WEB_URL="http://127.0.0.1:5173"
$env:HEADLESS="0"
$env:SLOWMO_MS="80"
$env:TYPE_DELAY_MS="10"
$env:KEEP_OPEN="1"
node scripts/run-communication-gauntlet-browser.mjs
```

The browser stays open when done because `KEEP_OPEN=1`.

Reports and screenshots:

```text
test-results/communication-gauntlet/browser-results.json
test-results/communication-gauntlet/browser-results.md
test-results/communication-gauntlet/*.png
```

## Run a smaller smoke set first

```powershell
$env:LIMIT="10"
node scripts/run-communication-gauntlet-api.mjs
node scripts/run-communication-gauntlet-browser.mjs
```

Clear limit:

```powershell
Remove-Item Env:\LIMIT
```

## How to interpret failures

A failure does not automatically mean the answer is bad. It means the response needs review.

Most important categories to patch first:

1. `runtime_clock` — wrong current date is a hard failure.
2. `short_term_memory` — failed follow-up memory means context injection is broken.
3. `guard_narrowing` — normal conversation blocked as operator work means routing is too broad.
4. `operator_safety` — destructive action accepted means safety is too loose.
5. `preview_build_routing` — preview writes files or build only previews means workflow routing is wrong.
6. `truthfulness_proof` — fake proof claims are unacceptable.
7. `tone_directness` / `frustration_recovery` — these identify the “low-quality bean” feel.

## Model limitation vs orchestration

You are up against both.

You can fix a lot with orchestration:
- prompt contract,
- short-term history,
- memory priority,
- route classification,
- date grounding,
- answer format rules,
- tool proof receipts.

But local model selection still matters:
- a weak 7B model will miss nuance,
- heavy quantization can flatten reasoning,
- coder models may be better for repo work but colder in conversation,
- instruct/chat models may be better for tone but weaker at code.

Use this gauntlet across model profiles. Same prompts, same scoring, different model.
That tells you whether the weak spot is wiring or the model.
