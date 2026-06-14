#!/usr/bin/env python
"""XV7 Ollama model inventory and selection proof.

Checks installed models against active role tags resolved from
config/models.yml + XV7_MODEL_PROFILE.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

# Ensure `core` package is importable when running this script directly.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


STATUS_CONFIGURED = "configured"
STATUS_INSTALLED = "installed"
STATUS_MISSING = "missing"
STATUS_NOT_CHECKED = "not checked"
STATUS_FAILED = "failed"


def _model_registry_api():
    from core.runtime.model_registry import (
        configured_ollama_base_url,
        resolve_active_models,
    )

    return configured_ollama_base_url, resolve_active_models


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


@dataclass
class AliasCheck:
    alias: str
    canonical_role: str
    resolved_model: str | None
    status: str

    @property
    def passed(self) -> bool:
        return self.status != STATUS_FAILED


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


def ollama_endpoint_mode(base_url: str) -> str:
    hostname = (urlparse(base_url).hostname or "").lower()
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return "host_shell"
    if hostname in {"ollama", "xv7-ollama"}:
        return "docker_internal"
    return "custom"


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
    roles: dict[str, str | None],
    installed_models: list[str],
) -> list[RoleCheck]:
    checks: list[RoleCheck] = []

    for role in ("chat", "embedding", "reasoning", "code"):
        model = roles.get(role)
        if model is None:
            checks.append(
                RoleCheck(
                    role=role,
                    model=None,
                    config_status=STATUS_NOT_CHECKED,
                    inventory_status=STATUS_NOT_CHECKED,
                    required=False,
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
                required=True,
            )
        )

    return checks


def build_alias_checks(
    *,
    role_aliases: dict[str, str],
    roles: dict[str, str | None],
) -> list[AliasCheck]:
    checks: list[AliasCheck] = []
    valid_roles = {"chat", "embedding", "reasoning", "code"}

    for alias in sorted(role_aliases):
        canonical = role_aliases[alias]
        if canonical not in valid_roles:
            checks.append(
                AliasCheck(
                    alias=alias,
                    canonical_role=canonical,
                    resolved_model=None,
                    status=STATUS_FAILED,
                )
            )
            continue

        resolved = roles.get(canonical)
        checks.append(
            AliasCheck(
                alias=alias,
                canonical_role=canonical,
                resolved_model=resolved,
                status=STATUS_CONFIGURED
                if resolved is not None
                else STATUS_NOT_CHECKED,
            )
        )

    return checks


def compute_exit_code(checks: list[RoleCheck], alias_checks: list[AliasCheck]) -> int:
    role_ok = all(check.passed for check in checks)
    alias_ok = all(check.passed for check in alias_checks)
    return 0 if role_ok and alias_ok else 1


def fetch_installed_models(
    ollama_base_url: str,
    timeout: float = 4.0,
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
    endpoint: str,
    profile_name: str | None,
    profile_source: str,
    checks: list[RoleCheck],
    alias_checks: list[AliasCheck],
    installed_models: list[str],
) -> None:
    active_chat = next((c.model for c in checks if c.role == "chat"), None)

    print("XV7 Ollama Model Inventory & Selection Proof")
    print(f"Repo root: {repo_root}")
    print(f"Ollama endpoint: {endpoint} ({ollama_endpoint_mode(endpoint)})")
    print(f"Selected profile: {profile_name or '<not_set>'} ({profile_source})")
    print(f"Active chat model: {active_chat or '<not_set>'}")

    print("\nInstalled models:")
    if installed_models:
        for model in installed_models:
            print(f"- {model}")
    else:
        print("- <none detected>")

    role_headers = ["Role", "Resolved tag", "Config", "Inventory", "Required", "Result"]
    role_rows: list[list[str]] = []
    for check in checks:
        role_rows.append(
            [
                check.role,
                check.model or "<not_set>",
                check.config_status,
                check.inventory_status,
                "yes" if check.required else "no",
                "pass" if check.passed else "fail",
            ]
        )

    role_widths = [len(h) for h in role_headers]
    for row in role_rows:
        for i, cell in enumerate(row):
            role_widths[i] = max(role_widths[i], len(cell))

    def role_line(items: list[str]) -> str:
        return " | ".join(item.ljust(role_widths[i]) for i, item in enumerate(items))

    print("\nRole status:")
    print(role_line(role_headers))
    print("-+-".join("-" * w for w in role_widths))
    for row in role_rows:
        print(role_line(row))

    alias_headers = ["Alias", "Canonical role", "Resolved tag", "Status"]
    alias_rows: list[list[str]] = []
    for check in alias_checks:
        alias_rows.append(
            [
                check.alias,
                check.canonical_role,
                check.resolved_model or "<not_set>",
                check.status,
            ]
        )

    alias_widths = [len(h) for h in alias_headers]
    for row in alias_rows:
        for i, cell in enumerate(row):
            alias_widths[i] = max(alias_widths[i], len(cell))

    def alias_line(items: list[str]) -> str:
        return " | ".join(item.ljust(alias_widths[i]) for i, item in enumerate(items))

    print("\nRole aliases:")
    print(alias_line(alias_headers))
    print("-+-".join("-" * w for w in alias_widths))
    for row in alias_rows:
        print(alias_line(row))


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
    profile_override: str | None,
    chat_model_override: str | None,
    pull_missing: bool,
    ollama_base_url_override: str | None,
) -> int:
    configured_ollama_base_url, resolve_active_models = _model_registry_api()

    repo_root = _detect_repo_root()
    if repo_root is None:
        print("FAIL: repo root not detected (docker-compose.yml not found).")
        return 1

    resolution = resolve_active_models(profile_override=profile_override)
    roles = dict(resolution.roles)

    if _normalized(chat_model_override) is not None:
        roles["chat"] = _normalized(chat_model_override)

    endpoint = _normalized(ollama_base_url_override) or configured_ollama_base_url()

    installed_models, error = fetch_installed_models(endpoint)
    if error is not None:
        print(f"FAIL: {error}")
        print("Hint: verify Ollama is reachable and the endpoint is correct.")
        return 1

    role_checks = build_role_checks(roles=roles, installed_models=installed_models)
    alias_checks = build_alias_checks(
        role_aliases=resolution.role_aliases,
        roles=roles,
    )

    print_summary(
        repo_root=repo_root,
        endpoint=endpoint,
        profile_name=resolution.profile,
        profile_source=resolution.profile_source,
        checks=role_checks,
        alias_checks=alias_checks,
        installed_models=installed_models,
    )

    if resolution.error is not None:
        print(f"\nProfile resolution warning: {resolution.error}")

    missing_required = sorted(
        {
            check.model
            for check in role_checks
            if check.required
            and check.inventory_status == STATUS_MISSING
            and check.model
        }
    )

    if pull_missing and missing_required:
        pull_code = pull_missing_models(missing_required)
        if pull_code != 0:
            return 1

        installed_models, error = fetch_installed_models(endpoint)
        if error is not None:
            print(f"FAIL: could not re-check models after pull: {error}")
            return 1

        role_checks = build_role_checks(roles=roles, installed_models=installed_models)
        alias_checks = build_alias_checks(
            role_aliases=resolution.role_aliases,
            roles=roles,
        )

        print("\nRe-check after pull:")
        print_summary(
            repo_root=repo_root,
            endpoint=endpoint,
            profile_name=resolution.profile,
            profile_source=resolution.profile_source,
            checks=role_checks,
            alias_checks=alias_checks,
            installed_models=installed_models,
        )

    exit_code = compute_exit_code(role_checks, alias_checks)
    if exit_code == 0:
        print("\nModel inventory proof result: PASS")
    else:
        print("\nModel inventory proof result: FAIL")

    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check configured XV7 model profiles against installed Ollama models."
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Select model profile for this check (overrides XV7_MODEL_PROFILE).",
    )
    parser.add_argument(
        "--chat-model",
        default=None,
        help="Override active chat model for this check only.",
    )
    parser.add_argument(
        "--ollama-base-url",
        default=None,
        help="Override Ollama base URL (default: configured OLLAMA_BASE_URL or models.yml).",
    )
    parser.add_argument(
        "--pull-missing",
        action="store_true",
        help="Explicitly pull missing required models via docker exec xv7-ollama ollama pull <model>.",
    )
    args = parser.parse_args()

    code = run_inventory(
        profile_override=args.profile,
        chat_model_override=args.chat_model,
        pull_missing=args.pull_missing,
        ollama_base_url_override=args.ollama_base_url,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
