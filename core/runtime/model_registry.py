from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse, urlunparse

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional at runtime
    yaml = None


DEFAULT_REGISTRY: dict[str, Any] = {
    "active_profile": "balanced",
    "role_aliases": {
        "default": "chat",
        "chat": "chat",
        "model_default": "chat",
        "assistant": "chat",
        "embedding": "embedding",
        "embed": "embedding",
        "embedding_model": "embedding",
        "model_embed": "embedding",
        "reasoning": "reasoning",
        "model_reasoning": "reasoning",
        "code": "code",
        "model_code": "code",
    },
    "profiles": {
        "low_resource": {
            "chat": "qwen3:1.7b",
            "reasoning": "qwen3:8b",
            "code": "qwen3:8b",
            "embedding": "nomic-embed-text:latest",
        },
        "balanced": {
            "chat": "qwen3:8b",
            "reasoning": "qwen3:14b",
            "code": "qwen3:14b",
            "embedding": "nomic-embed-text:latest",
        },
        "local_test": {
            "chat": "qwen3:14b",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
            "embedding": "nomic-embed-text:latest",
        },
        "large_code": {
            "chat": "qwen3-coder:30b",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
            "embedding": "nomic-embed-text:latest",
        },
    },
    "legacy": {
        "unused": ["qwen2.5-coder:14b"],
    },
}

DEFAULT_OLLAMA: dict[str, Any] = {
    "base_url": "http://ollama:11434",
    "timeout_seconds": 2.0,
}


@dataclass
class ModelResolution:
    profile: str | None
    profile_source: str
    roles: dict[str, str | None]
    role_aliases: dict[str, str]
    error: str | None


@dataclass
class RegistryConfig:
    ollama: dict[str, Any]
    registry: dict[str, Any]


@dataclass
class RuntimeRoleModelResolution:
    profile: str | None
    profile_source: str
    alias_used: str
    canonical_role: str
    model_tag: str | None
    error: str | None


def _candidate_paths() -> list[Path]:
    env_override = os.getenv("XV7_MODELS_CONFIG_PATH")
    candidates: list[Path] = []
    if env_override:
        candidates.append(Path(env_override))

    candidates.append(Path(__file__).resolve().parents[2] / "config" / "models.yml")
    candidates.append(Path.cwd() / "config" / "models.yml")
    return candidates


def _first_existing_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _clone_defaults() -> RegistryConfig:
    return RegistryConfig(
        ollama=dict(DEFAULT_OLLAMA),
        registry={
            "active_profile": DEFAULT_REGISTRY["active_profile"],
            "role_aliases": dict(DEFAULT_REGISTRY["role_aliases"]),
            "profiles": {
                profile: dict(values)
                for profile, values in DEFAULT_REGISTRY["profiles"].items()
            },
            "legacy": {
                "unused": list(DEFAULT_REGISTRY["legacy"]["unused"]),
            },
        },
    )


def _normalized(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _merge_registry_data(raw: dict[str, Any], base: RegistryConfig) -> RegistryConfig:
    merged = _clone_defaults()
    merged.ollama.update(base.ollama)
    merged.registry.update(base.registry)

    raw_ollama = raw.get("ollama")
    if isinstance(raw_ollama, dict):
        base_url = _normalized(raw_ollama.get("base_url"))
        if base_url is not None:
            merged.ollama["base_url"] = base_url

        timeout_raw = raw_ollama.get("timeout_seconds")
        try:
            if timeout_raw is not None:
                merged.ollama["timeout_seconds"] = max(0.1, float(timeout_raw))
        except (TypeError, ValueError):
            pass

    raw_registry = raw.get("registry")
    if not isinstance(raw_registry, dict):
        return merged

    active_profile = _normalized(raw_registry.get("active_profile"))
    if active_profile is not None:
        merged.registry["active_profile"] = active_profile

    role_aliases = raw_registry.get("role_aliases")
    if isinstance(role_aliases, dict):
        parsed_aliases: dict[str, str] = {}
        for key, value in role_aliases.items():
            alias = _normalized(key)
            canonical = _normalized(value)
            if alias and canonical:
                parsed_aliases[alias] = canonical
        if parsed_aliases:
            merged.registry["role_aliases"] = parsed_aliases

    profiles = raw_registry.get("profiles")
    if isinstance(profiles, dict):
        parsed_profiles: dict[str, dict[str, str]] = {}
        for profile_name, role_values in profiles.items():
            profile_key = _normalized(profile_name)
            if profile_key is None or not isinstance(role_values, dict):
                continue

            parsed_roles: dict[str, str] = {}
            for role_name, model_name in role_values.items():
                role_key = _normalized(role_name)
                model_value = _normalized(model_name)
                if role_key and model_value:
                    parsed_roles[role_key] = model_value

            if parsed_roles:
                parsed_profiles[profile_key] = parsed_roles

        if parsed_profiles:
            merged.registry["profiles"] = parsed_profiles

    legacy = raw_registry.get("legacy")
    if isinstance(legacy, dict):
        unused = legacy.get("unused")
        if isinstance(unused, list):
            cleaned_unused = [item for item in (_normalized(v) for v in unused) if item]
            merged.registry["legacy"] = {"unused": cleaned_unused}

    return merged


def load_registry_config() -> RegistryConfig:
    defaults = _clone_defaults()
    path = _first_existing_path(_candidate_paths())
    if path is None or yaml is None:
        return defaults

    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return defaults

    if not isinstance(parsed, dict):
        return defaults

    return _merge_registry_data(parsed, defaults)


def resolve_active_models(
    *,
    profile_override: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> ModelResolution:
    env = environ if environ is not None else os.environ
    config = load_registry_config()

    profiles = config.registry.get("profiles", {})
    role_aliases_raw = config.registry.get("role_aliases", {})

    role_aliases: dict[str, str] = {}
    if isinstance(role_aliases_raw, dict):
        for key, value in role_aliases_raw.items():
            alias = _normalized(key)
            canonical = _normalized(value)
            if alias and canonical:
                role_aliases[alias] = canonical

    selected_profile = _normalized(profile_override)
    profile_source = "override"
    warning_parts: list[str] = []

    if selected_profile is None:
        try:
            from core.runtime.model_profile_selection import (
                get_runtime_profile_override,
            )

            runtime_override = _normalized(get_runtime_profile_override())
        except Exception:
            runtime_override = None

        if runtime_override is not None:
            if isinstance(profiles, dict) and runtime_override in profiles:
                selected_profile = runtime_override
                profile_source = "runtime_override"
            else:
                warning_parts.append(
                    f"Runtime override profile '{runtime_override}' was not found."
                )

    if selected_profile is None:
        selected_profile = _normalized(env.get("XV7_MODEL_PROFILE"))
        profile_source = "env"

    if selected_profile is None:
        selected_profile = _normalized(config.registry.get("active_profile"))
        profile_source = "registry_default"

    if selected_profile is None:
        return ModelResolution(
            profile=None,
            profile_source=profile_source,
            roles={"chat": None, "embedding": None, "reasoning": None, "code": None},
            role_aliases=role_aliases,
            error="No active model profile configured.",
        )

    if not isinstance(profiles, dict) or selected_profile not in profiles:
        return ModelResolution(
            profile=selected_profile,
            profile_source=profile_source,
            roles={"chat": None, "embedding": None, "reasoning": None, "code": None},
            role_aliases=role_aliases,
            error=f"Configured model profile '{selected_profile}' was not found.",
        )

    selected = profiles[selected_profile]
    if not isinstance(selected, dict):
        return ModelResolution(
            profile=selected_profile,
            profile_source=profile_source,
            roles={"chat": None, "embedding": None, "reasoning": None, "code": None},
            role_aliases=role_aliases,
            error=f"Configured model profile '{selected_profile}' is invalid.",
        )

    roles = {
        "chat": _normalized(selected.get("chat")),
        "embedding": _normalized(selected.get("embedding")),
        "reasoning": _normalized(selected.get("reasoning")),
        "code": _normalized(selected.get("code")),
    }

    missing_required = [
        role for role in ("chat", "embedding") if roles.get(role) is None
    ]
    if missing_required:
        return ModelResolution(
            profile=selected_profile,
            profile_source=profile_source,
            roles=roles,
            role_aliases=role_aliases,
            error=(
                f"Profile '{selected_profile}' is missing required roles: "
                f"{', '.join(sorted(missing_required))}."
            ),
        )

    warning = "; ".join(warning_parts) if warning_parts else None

    return ModelResolution(
        profile=selected_profile,
        profile_source=profile_source,
        roles=roles,
        role_aliases=role_aliases,
        error=warning,
    )


def resolve_model_for_runtime_role(
    role: str,
    profile: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> RuntimeRoleModelResolution:
    role_alias = _normalized(role)
    if role_alias is None:
        raise ValueError("Runtime role is required.")

    resolution = resolve_active_models(profile_override=profile, environ=environ)
    valid_roles = {"chat", "reasoning", "code", "embedding"}

    canonical = resolution.role_aliases.get(role_alias, role_alias)
    if canonical not in valid_roles:
        known = sorted(set(valid_roles).union(resolution.role_aliases.keys()))
        raise ValueError(
            f"Unknown runtime role alias '{role_alias}'. Known aliases: {', '.join(known)}"
        )

    model_tag = resolution.roles.get(canonical)
    return RuntimeRoleModelResolution(
        profile=resolution.profile,
        profile_source=resolution.profile_source,
        alias_used=role_alias,
        canonical_role=canonical,
        model_tag=model_tag,
        error=resolution.error,
    )


def configured_ollama_base_url() -> str:
    candidates = configured_ollama_base_url_candidates()
    if candidates:
        return candidates[0]
    return DEFAULT_OLLAMA["base_url"].rstrip("/")


def _in_docker_runtime() -> bool:
    if Path("/.dockerenv").exists():
        return True
    cgroup_path = Path("/proc/1/cgroup")
    if cgroup_path.exists():
        try:
            lowered = cgroup_path.read_text(encoding="utf-8", errors="ignore").lower()
            if "docker" in lowered or "kubepods" in lowered or "containerd" in lowered:
                return True
        except OSError:
            return False
    return False


def _replace_host(base_url: str, host: str) -> str:
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "http"
    port = parsed.port
    netloc = f"{host}:{port}" if port is not None else host
    return urlunparse((scheme, netloc, parsed.path or "", "", "", "")).rstrip("/")


def configured_ollama_base_url_candidates() -> list[str]:
    env_value = _normalized(os.getenv("OLLAMA_BASE_URL"))
    config = load_registry_config()
    config_base = _normalized(config.ollama.get("base_url"))
    base_url = (env_value or config_base or DEFAULT_OLLAMA["base_url"]).rstrip("/")

    parsed = urlparse(base_url)
    hostname = (parsed.hostname or "").lower()
    in_docker = _in_docker_runtime()

    candidates: list[str] = [base_url]

    # Native runs cannot resolve Docker service DNS names like 'ollama'.
    if not in_docker and hostname in {"ollama", "xv7-ollama"}:
        candidates.append(_replace_host(base_url, "127.0.0.1"))
        candidates.append(_replace_host(base_url, "localhost"))

    # Container runs should prefer service DNS if a localhost host leaked into config.
    if in_docker and hostname in {"127.0.0.1", "localhost", "host.docker.internal"}:
        candidates.append(_replace_host(base_url, "ollama"))
        candidates.append(_replace_host(base_url, "xv7-ollama"))

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = candidate.rstrip("/")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def configured_ollama_timeout_seconds() -> float:
    raw_value = _normalized(os.getenv("OLLAMA_STATUS_TIMEOUT_SECONDS"))
    if raw_value is not None:
        try:
            return max(0.1, float(raw_value))
        except ValueError:
            pass

    config = load_registry_config()
    value = config.ollama.get("timeout_seconds")
    if value is None:
        return float(DEFAULT_OLLAMA["timeout_seconds"])

    try:
        return max(0.1, float(value))
    except (TypeError, ValueError):
        return float(DEFAULT_OLLAMA["timeout_seconds"])
