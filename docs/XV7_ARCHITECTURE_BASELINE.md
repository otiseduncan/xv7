# XV7 Architecture Baseline

## Service Layout
- Frontend: static app served from public/ with no build step.
- Backend: FastAPI app in core/main.py with stable existing endpoints for sessions, runtime, brain records, and operator flow.
- Operator runtime: action specs in core/operator/registry.py, orchestration in core/operator/manager.py, slash command definitions in core/operator/slash_commands.py.

## Frontend Module Layout
- Main controller: public/app.js (Xv7UI).
- Runtime status support: public/runtime-status.js.
- Styles: public/styles.css remains single-file and cascade-ordered for compatibility with legacy rules.
- Browser smoke coverage: e2e/xv7-browser-smoke.spec.mjs.

## Backend Route And Service Layout
- Session/chat flow: core/main.py routes under /sessions/*.
- Runtime model and health flow: core/main.py routes under /runtime/*.
- Brain record lifecycle: core/main.py routes under /runtime/brain/records/*.
- Operator staging/confirm/cancel flow: core/main.py routes under /operator-*.
- Answer policy and routing: core/brain/answer_contract.py + core/brain/intent_router.py.

## Artifact And Site Generation Flow
1. Prompt intent is classified by core/brain/intent_router.py.
2. Answer contract in core/brain/answer_contract.py decides artifact/site path.
3. Site bundle helpers in core/brain/site_bundle.py assemble/refine files.
4. Deterministic rendering is produced by core/brain/website_design_renderer.py.

## Design-Edit Flow
1. Prompt phrase extraction in core/brain/website_style_plan_manager.py.
2. Design intent is converted to deterministic CSS modifications.
3. Receipt text reports concrete categories (colors, typography, cards, glow, glass/translucency, layout/shadow).
4. Refinement output is validated by existing site bundle validators.

## Operator Capability Model
- Slash command truth source: core/operator/slash_commands.py.
- Capability buckets:
  - implemented_read_only_tools
  - implemented_operator_tools
  - stubbed_read_only_tools
  - stubbed_operator_tools
- Capability responses must not claim live internet, email, calendar, or VS Code control as wired unless implemented.

## Test And Gauntlet Commands
- python -m pytest tests/test_intent_router.py -q
- python -m pytest tests/test_answer_contract.py -q
- python -m pytest tests/test_website_design_renderer.py tests/test_website_design_renderer_profiles.py -q
- python -m pytest tests/test_operator* -q
- npm test
- npm run gauntlet:browser

## Remaining P3 Candidates
- Normalize the legacy compatibility tail in public/styles.css, then split into component files with no cascade regressions.
- Continue IntentRouter/AnswerContract deduplication for shared pattern ownership.
- Evaluate low-value pass-through wrappers beyond current documented contract boundaries.
- Expand capability disclosure formatting into structured metadata in API responses.
