from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any


MUTATION_PATTERNS = (
    "write",
    "edit",
    "delete",
    "remove",
    "commit",
    "push",
    "pull",
    "checkout",
    "reset",
    "git clean",
    "docker compose down",
    "docker compose up",
    "restart",
    "install",
    "create file",
)

NON_MUTATION_WRITING_PATTERNS = (
    "implementation prompt",
    "implementation prompts",
    "vs code prompt",
    "copilot prompt",
    "write a prompt",
    "write prompt",
    "app planning",
    "design architecture",
    "test planning",
    "debugging guidance",
    "documentation help",
    "to the sandbox",
    "to sandbox",
    "export to sandbox",
    "save to sandbox",
    "write to sandbox",
)

FIRST_CLASS_SLASH_COMMANDS = {
    "/build",
    "/export",
    "/write",
    "/commit",
    "/push",
    "/github",
    "/publish",
}


def normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def looks_like_natural_language_request(text: str) -> bool:
    lowered = text.lower().strip()
    return any(
        token in lowered
        for token in (
            "we are in",
            "build this feature",
            "code 9",
            "code builder",
            "add tests",
            "pytest",
            "git commit",
            "git push",
            "feature request",
        )
    )


def is_non_mutation_writing_request(normalized: str) -> bool:
    return any(token in normalized for token in NON_MUTATION_WRITING_PATTERNS)


def is_commit_proposal_request(normalized: str) -> bool:
    return any(
        token in normalized
        for token in (
            "prepare commit",
            "prepare a commit",
            "propose commit",
            "propose a commit",
            "commit proposal",
            "create commit proposal",
            "draft commit",
            "show commit proposal",
            "what would the commit be",
            "what should i commit",
            "commit it",
        )
    )


def is_commit_push_operator_request(normalized: str) -> bool:
    return any(
        token in normalized
        for token in (
            "commit the approved changes",
            "commit these changes",
            "commit the proposal",
            "approve commit",
            "confirm commit",
            "make the commit",
            "create the commit",
            "go ahead and commit",
            "push the branch",
            "push branch",
            "git push",
            "commit and push",
        )
    )


def strip_operator_mode_prefix(normalized: str) -> str:
    return re.sub(r"^operator\s+mode\s*:\s*", "", normalized, flags=re.IGNORECASE)


def extract_windows_paths(text: str) -> list[str]:
    return [
        match.strip().rstrip(".,;:)\"'")
        for match in re.findall(r"[A-Za-z]:\\[^\n\r\"']+", text or "")
    ]


def dedup_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in paths:
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return ordered


def slugify_repo_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").lower()).strip("-.")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "github-proof-project"


def extract_repo_name_from_prompt(source_text: str) -> str:
    for pattern in (
        r"\bpush\s+to\s+github\s+new\s+repo\s+(.+)$",
        r"\bcreate\s+(?:a\s+)?new\s+repo(?:sitory)?(?:\s+on\s+github)?\s+named\s+(.+)$",
        r"\bgithub\s+repo\s+(.+)$",
    ):
        match = re.search(pattern, source_text, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1).strip()
        raw = re.sub(r"\s+and\s+push\b.*$", "", raw, flags=re.IGNORECASE)
        raw = raw.strip().strip(".,;:!?")
        if raw:
            return slugify_repo_name(raw)
    return ""


def missing_project_path_message(
    *, candidate_paths: list[str], project_name_hint: str
) -> str:
    if candidate_paths:
        example = candidate_paths[0]
    else:
        slug = slugify_repo_name(project_name_hint or "sandbox-project")
        example = f"X:\\xoduz-sandbox\\{slug}"
    return (
        "I need the sandbox project path to continue GitHub repo creation/push safely. "
        f"Provide an explicit path like {example}."
    )


def is_github_proof_project_request(normalized: str) -> bool:
    stripped = strip_operator_mode_prefix(normalized)
    return any(
        token in stripped
        for token in (
            "build and push",
            "push to github",
            "create a github repo",
            "create a new repo",
            "create new repo",
            "create a new repository",
            "new repo",
            "create a new repository on github",
            "create a new repo named",
            "push to github new repo",
            "initialize the new repository and push to github",
            "initialize git",
            "git init",
            "commit and push",
            "commit and push this project",
            "finish the github push",
            "existing proof project",
            "real github proof project",
            "real build and push",
            "not a preview",
            "not a patch",
        )
    )


def is_first_class_operator_request(normalized: str) -> bool:
    stripped = strip_operator_mode_prefix(normalized)
    if any(stripped.startswith(prefix) for prefix in FIRST_CLASS_SLASH_COMMANDS):
        return True
    return is_github_proof_project_request(stripped) or is_commit_push_operator_request(
        stripped
    )


def extract_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def is_natural_validation_request(normalized: str) -> bool:
    return normalized in {
        "run validation.",
        "run validation",
        "run the checks.",
        "run the checks",
        "run checks.",
        "run checks",
        "what's failing?",
        "what's failing",
        "what is failing?",
        "what is failing",
    }


def is_natural_repair_request(normalized: str) -> bool:
    return normalized in {
        "fix the first failure.",
        "fix the first failure",
        "fix first failure.",
        "fix first failure",
        "fix it.",
        "fix it",
    }


def translate_first_class_slash(
    question: str,
    parse_slash_command: Callable[[str], tuple[str, list[str]]],
) -> str:
    stripped = question.strip()
    if not stripped.startswith("/"):
        return stripped
    slash, args = parse_slash_command(stripped)
    lower_args = [arg.lower() for arg in args]

    if slash in {"/build", "/export", "/write"}:
        if "sandbox" in lower_args or not args:
            return "build the approved website to sandbox"
    if slash == "/commit":
        return "commit and push this project"
    if slash == "/push":
        if lower_args and lower_args[0] == "github":
            return "initialize the new repository and push to github"
        return "push to github"
    if slash == "/github":
        if lower_args and lower_args[0] == "create":
            repo_name = args[1] if len(args) > 1 else ""
            if repo_name:
                return f"create a new repository on github named {repo_name} and push"
            return "create a new repository on github and push"
        if lower_args and lower_args[0] == "push":
            return "finish the github push for the existing proof project"
    if slash == "/publish" and lower_args and lower_args[0] == "github":
        return "create a new repository on github and push"
    return stripped
