# CODE-15 — App Template Registry Prompt

## Mission

Create a small template registry so Xoduz can build apps from known, repeatable patterns instead of inventing every project from scratch.

This is the first real foundation for app-builder mode.

## Goal

When Otis says:

```text
build me a small inventory app
build a customer tracker
build a shop estimate tool
build a home budget app
```

Xoduz should map that request to a known app template, scaffold files, run tests, and report what changed.

## Template registry concept

Add a registry that describes supported app templates.

Suggested templates for version 1:

```text
simple-react-static
react-fastapi-crud
react-fastapi-sqlite-crud
landing-page
admin-dashboard
```

Start with one reliable implementation if needed:

```text
react-fastapi-crud
```

Do not try to support every framework at once.

## Files to inspect first

```text
package.json
public/
core/main.py
core/operator/actions/
docs/CODE_07_APP_BUILDER_MODE_PROMPT.md
docs/CODE_10_APP_BUILDER_GAUNTLET_PROMPT.md
```

## Required registry fields

Each template should define:

```text
template_id
name
description
stack
output_root
required_inputs
optional_inputs
files_to_create
test_commands
preview_command
risk_level
```

Example:

```json
{
  "template_id": "react-fastapi-crud",
  "name": "React + FastAPI CRUD App",
  "stack": ["React", "FastAPI", "SQLite optional"],
  "output_root": "generated-apps/{app_slug}",
  "required_inputs": ["app_name", "entity_name", "fields"],
  "test_commands": ["npm test -- public/app.test.js", "python -m pytest tests/ -v --tb=short --asyncio-mode=auto"],
  "preview_command": "documented by generated README"
}
```

## Required implementation

### 1. Template data module

Create a small registry module, for example:

```text
core/app_builder/templates.py
```

or the closest existing app-builder location.

### 2. Template selection

Given a user app request, return:

```text
selected_template
default_stack
missing_required_inputs
assumptions
risk_level
```

### 3. Scaffold plan only at first

This lane may start as plan-only if CODE-03 apply patch is not ready.

For plan-only, Xoduz should say:

```text
I would use template react-fastapi-crud and create these files...
```

without writing yet.

### 4. Generated app README

Every generated app must include a README explaining:

- what was generated,
- how to run it,
- how to test it,
- known limitations.

## Tests required

Add tests for:

1. template registry loads,
2. known template can be selected,
3. unknown app request returns helpful fallback,
4. missing required fields are reported,
5. scaffold plan stays inside `generated-apps/`,
6. app builder does not mutate without approval.

## Acceptance commands

```powershell
python -m pytest tests/ -v --tb=short --asyncio-mode=auto
python -m ruff check core/ tests/
python -m ruff format --check core/ tests/
```

## Definition of done

CODE-15 is done when Xoduz can take a basic app idea and produce a safe, structured scaffold plan using a known template.

## Commit message

```text
feat: add app template registry
```
