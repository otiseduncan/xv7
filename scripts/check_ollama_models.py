#!/usr/bin/env python
"""XV7 Ollama model inventory and selection proof.

Reports installed models, configured role models, and whether required selected
models are installed. Does not pull models unless --pull-missing is explicitly
provided.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


STATUS_CONFIGURED = "configured"
STATUS_INSTALLED = "installed"
STATUS_MISSING = "missing"
STATUS_NOT_CHECKED = "not checked"


@dataclass
class RoleCheck:
    role: str
    model: str | None
    config_status: str
    inventory_status: str
    required: bool

    @property
    def passed(self) -> bool:
        if not self.required:
            return True
        if self.config_status != STATUS_CONFIGURED:
            return False
        return self.inventory_status == STATUS_INSTALLED


def _detect_repo_root(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "docker-compose.yml").exists():
            return candidate
    return None


def _normalized(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _strip_inline_comment(raw: str) -> str:
    # Keep hashes that are not comment separators (simple heuristic).
    marker = " #"
    idx = raw.find(marker)
    if idx >= 0:
        raw = raw[:idx]
    return raw.strip()


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_inline_comment(value).strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def parse_models_yaml(path: Path) -> dict[str, str]:
    """Extract configured role model names from config/models.yml.

    This parser is intentionally lightweight and tailored to current schema.
    """
    found: dict[str, str] = {}
    if not path.exists():
        return found

    section: str | None = None
    subsection: str | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "models:":
            section = "models"
            subsection = None
            continue
        if stripped == "embeddings:":
            section = "embeddings"
            subsection = None
            continue

        if (
            line.startswith("  ")
            and stripped.endswith(":")
            and not line.startswith("    ")
        ):
            subsection = stripped[:-1]
            continue

        if line.startswith("    ") and stripped.startswith("name:"):
            if section == "models" and subsection in {"default", "reasoning", "code"}:
                model_name = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if subsection == "default":
                    found["MODEL_DEFAULT"] = model_name
                elif subsection == "reasoning":
                    found["MODEL_REASONING"] = model_name
                elif subsection == "code":
                    found["MODEL_CODE"] = model_name
            if section == "embeddings" and subsection == "default":
                model_name = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                found["EMBEDDING_MODEL"] = model_name
                found["MODEL_EMBED"] = model_name

    return found


def resolve_setting(
    key: str,
    *,
    env: dict[str, str],
    dotenv: dict[str, str],
    defaults: dict[str, str],
) -> str | None:
    value = _normalized(env.get(key))
    if value is not None:
        return value

    value = _normalized(dotenv.get(key))
    if value is not None:
        return value

    value = _normalized(defaults.get(key))
    if value is not None:
        return value

    return None


def _model_name(raw_model: Any) -> str | None:
    if not isinstance(raw_model, dict):
        return None

    value = raw_model.get("name") or raw_model.get("model")
    if not isinstance(value, str):
        return None

    return _normalized(value)


def parse_ollama_tags_payload(payload: dict[str, Any]) -> list[str]:
    raw_models = payload.get("models", [])
    if not isinstance(raw_models, list):
        return []

    models = sorted(
        model_name
        for model_name in (_model_name(item) for item in raw_models)
        if model_name
    )
    return models


def model_matches(requested: str, available: str) -> bool:
    requested_clean = _normalized(requested)
    available_clean = _normalized(available)
    if requested_clean is None or available_clean is None:
        return False

    if requested_clean == available_clean:
        return True

    if ":" not in requested_clean and available_clean == f"{requested_clean}:latest":
        return True

    return False


def has_model(requested: str, available_models: list[str]) -> bool:
    return any(model_matches(requested, available) for available in available_models)


def build_role_checks(
    *,
    active_chat_model: str | None,
    embedding_model: str | None,
    reasoning_model: str | None,
    code_model: str | None,
    installed_models: list[str],
) -> list[RoleCheck]:
    checks: list[RoleCheck] = []

    role_specs = [
        ("chat", active_chat_model, True),
        ("embedding", embedding_model, True),
        ("reasoning", reasoning_model, False),
        ("code", code_model, False),
    ]

    for role, model, required in role_specs:
        if model is None:
            checks.append(
                RoleCheck(
                    role=role,
                    model=None,
                    config_status=STATUS_NOT_CHECKED,
                    inventory_status=STATUS_NOT_CHECKED,
                    required=required,
                )
            )
            continue

        checks.append(
            RoleCheck(
                role=role,
                model=model,
                config_status=STATUS_CONFIGURED,
                inventory_status=(
                    STATUS_INSTALLED
                    if has_model(model, installed_models)
                    else STATUS_MISSING
                ),
                required=required,
            )
        )

    return checks


def compute_exit_code(checks: list[RoleCheck]) -> int:
    return 0 if all(check.passed for check in checks) else 1


def fetch_installed_models(
    ollama_base_url: str, timeout: float = 4.0
) -> tuple[list[str], str | None]:
    url = f"{ollama_base_url.rstrip('/')}/api/tags"
    try:
        with urlopen(url, timeout=timeout) as resp:
            status = int(resp.status)
            if status != 200:
                return [], f"Unexpected status code from {url}: {status}"
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            if not isinstance(payload, dict):
                return [], f"Invalid JSON payload from {url}: expected object"
            return parse_ollama_tags_payload(payload), None
    except HTTPError as exc:
        return [], f"HTTPError contacting {url}: {exc.code} {exc.reason}"
    except URLError as exc:
        return [], f"URLError contacting {url}: {exc.reason}"
    except Exception as exc:
        return [], f"{type(exc).__name__} contacting {url}: {exc}"


def print_summary(
    *,
    repo_root: Path,
    ollama_base_url: str,
    active_chat_model: str | None,
    checks: list[RoleCheck],
    installed_models: list[str],
) -> None:
    print("XV7 Ollama Model Inventory & Selection Proof")
    print(f"Repo root: {repo_root}")
    print(f"Ollama endpoint: {ollama_base_url}")
    print(f"Active chat model: {active_chat_model or '<not_set>'}")

    print("\nInstalled models:")
    if installed_models:
        for model in installed_models:
            print(f"- {model}")
    else:
        print("- <none detected>")

    headers = ["Role", "Model", "Config", "Inventory", "Required", "Result"]
    rows: list[list[str]] = []
    for check in checks:
        rows.append(
            [
                check.role,
                check.model or "<not_set>",
                check.config_status,
                check.inventory_status,
                "yes" if check.required else "no",
                "pass" if check.passed else "fail",
            ]
        )

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def row_line(items: list[str]) -> str:
        return " | ".join(item.ljust(widths[i]) for i, item in enumerate(items))

    print("\nRole status:")
    print(row_line(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(row_line(row))


def pull_missing_models(missing_models: list[str]) -> int:
    if not missing_models:
        return 0

    print("\nPull requested for missing models:")
    for model in missing_models:
        print(f"- {model}")

    for model in missing_models:
        result = subprocess.run(
            ["docker", "exec", "xv7-ollama", "ollama", "pull", model],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            print(f"FAIL: pull failed for model '{model}'")
            if result.stderr.strip():
                print(result.stderr.strip())
            return 1

    return 0


def run_inventory(
    *,
    chat_model_override: str | None,
    pull_missing: bool,
    ollama_base_url_override: str | None,
) -> int:
    repo_root = _detect_repo_root()
    if repo_root is None:
        print("FAIL: repo root not detected (docker-compose.yml not found).")
        return 1

    dotenv = load_dotenv(repo_root / ".env")
    defaults = parse_models_yaml(repo_root / "config" / "models.yml")
    env = os.environ

    core_port = (
        _normalized(env.get("CORE_PORT"))
        or _normalized(dotenv.get("CORE_PORT"))
        or "8000"
    )
    ollama_port = (
        _normalized(env.get("OLLAMA_PORT"))
        or _normalized(dotenv.get("OLLAMA_PORT"))
        or "11434"
    )

    active_chat_model = _normalized(chat_model_override) or resolve_setting(
        "MODEL_DEFAULT", env=env, dotenv=dotenv, defaults=defaults
    )
    embedding_model = resolve_setting(
        "EMBEDDING_MODEL", env=env, dotenv=dotenv, defaults=defaults
    ) or resolve_setting("MODEL_EMBED", env=env, dotenv=dotenv, defaults=defaults)
    reasoning_model = resolve_setting(
        "MODEL_REASONING", env=env, dotenv=dotenv, defaults=defaults
    )
    code_model = resolve_setting(
        "MODEL_CODE", env=env, dotenv=dotenv, defaults=defaults
    )

    ollama_base_url = (
        _normalized(ollama_base_url_override)
        or _normalized(env.get("OLLAMA_BASE_URL"))
        or f"http://localhost:{ollama_port}"
    )

    installed_models, error = fetch_installed_models(ollama_base_url)
    if error is not None:
        print(f"FAIL: {error}")
        print(
            f"Hint: verify Ollama is reachable and port mapping is correct (OLLAMA_PORT={ollama_port})."
        )
        return 1

    checks = build_role_checks(
        active_chat_model=active_chat_model,
        embedding_model=embedding_model,
        reasoning_model=reasoning_model,
        code_model=code_model,
        installed_models=installed_models,
    )

    print_summary(
        repo_root=repo_root,
        ollama_base_url=ollama_base_url,
        active_chat_model=active_chat_model,
        checks=checks,
        installed_models=installed_models,
    )

    missing_required = [
        check.model
        for check in checks
        if check.required
        and check.inventory_status == STATUS_MISSING
        and check.model is not None
    ]

    if pull_missing and missing_required:
        pull_code = pull_missing_models(sorted(set(missing_required)))
        if pull_code != 0:
            return 1

        # Re-check after explicit pull attempt.
        installed_models, error = fetch_installed_models(ollama_base_url)
        if error is not None:
            print(f"FAIL: could not re-check models after pull: {error}")
            return 1

        checks = build_role_checks(
            active_chat_model=active_chat_model,
            embedding_model=embedding_model,
            reasoning_model=reasoning_model,
            code_model=code_model,
            installed_models=installed_models,
        )

        print("\nRe-check after pull:")
        print_summary(
            repo_root=repo_root,
            ollama_base_url=ollama_base_url,
            active_chat_model=active_chat_model,
            checks=checks,
            installed_models=installed_models,
        )

    # Show current core/runtime status view for operator context.
    core_ollama_url = f"http://localhost:{core_port}/runtime/ollama"
    try:
        with urlopen(core_ollama_url, timeout=4.0) as resp:
            if int(resp.status) == 200:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
                if isinstance(payload, dict):
                    print("\n/runtime/ollama snapshot:")
                    print(
                        json.dumps(
                            {
                                "reachable": payload.get("reachable"),
                                "chat_model": payload.get("chat_model"),
                                "chat_model_available": payload.get(
                                    "chat_model_available"
                                ),
                                "embedding_model": payload.get("embedding_model"),
                                "embedding_model_available": payload.get(
                                    "embedding_model_available"
                                ),
                            },
                            indent=2,
                        )
                    )
    except Exception:
        print(
            f"\n/runtime/ollama snapshot: not checked ({core_ollama_url} not reachable)"
        )

    exit_code = compute_exit_code(checks)
    if exit_code == 0:
        print("\nModel inventory proof result: PASS")
    else:
        print("\nModel inventory proof result: FAIL")

    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check configured XV7 model roles against installed Ollama models."
    )
    parser.add_argument(
        "--chat-model",
        default=None,
        help="Override active chat model for this check (no code edits required).",
    )
    parser.add_argument(
        "--ollama-base-url",
        default=None,
        help="Override Ollama base URL (default: OLLAMA_BASE_URL or http://localhost:$OLLAMA_PORT).",
    )
    parser.add_argument(
        "--pull-missing",
        action="store_true",
        help="Explicitly pull missing required models via docker exec xv7-ollama ollama pull <model>.",
    )
    args = parser.parse_args()

    code = run_inventory(
        chat_model_override=args.chat_model,
        pull_missing=args.pull_missing,
        ollama_base_url_override=args.ollama_base_url,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
