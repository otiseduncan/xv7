from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from prompt_factory import latest_prompt
from receipts import RESULT_INTAKE_DIR, locked_flags, read_latest_json, utc_iso, write_json
from review_bundles import get_review_bundle


DENIED_PREFIXES = (
    "core/",
    "public/x-kernel.js",
    "public/x-kernel.html",
    "apps/api/",
    "apps/web/",
    "packages/",
    "e2e/",
    "test-results/",
    "docker-compose.yml",
    "docker-compose.x.yml",
    "docker-compose.mobile-cpu.yml",
    ".env",
)
LEGACY_MARKERS = ("/sessions", "core/main.py", "session_message_routes.py", "Open WebUI", "visible-response")


def review_codex_result(raw_text: str, source_prompt_id: str | None = None, source_bundle_id: str | None = None) -> dict[str, Any]:
    prompt = latest_prompt().get("prompt")
    bundle_id = source_bundle_id or (prompt or {}).get("source_bundle_id")
    bundle = get_review_bundle(bundle_id).get("review_bundle") if bundle_id else None
    extracted = extract_report(raw_text)
    comparison = compare_report(extracted, bundle, prompt, raw_text)
    result = build_result(raw_text, extracted, comparison, source_prompt_id or (prompt or {}).get("prompt_id"), bundle_id)
    paths = write_json(RESULT_INTAKE_DIR, f"result_{result['result_id']}", result, "latest_result_intake.json")
    result.update({"receipt_path": paths["path"], "latest_receipt_path": paths.get("latest_path")})
    write_json(RESULT_INTAKE_DIR, f"result_{result['result_id']}", result, "latest_result_intake.json")
    return {"status": "result_reviewed", "result_review": result, **locked_flags()}


def latest_result_intake() -> dict[str, Any]:
    result = read_latest_json(RESULT_INTAKE_DIR, "latest_result_intake.json")
    return {"status": "completed" if result else "empty", "result_review": result, **locked_flags()}


def extract_report(raw_text: str) -> dict[str, Any]:
    files = extract_files(raw_text)
    return {
        "reported_branch": extract_value(raw_text, "branch"),
        "reported_commit_hash": extract_commit(raw_text),
        "files_changed": files,
        "validation_results": extract_section(raw_text, "validation results"),
        "denied_paths_touched": extract_yes_no(raw_text, "denied paths touched"),
        "legacy_routes_used": extract_yes_no(raw_text, "legacy routes used"),
        "dirty_files": extract_section(raw_text, "remaining dirty files"),
        "claimed_safety_flags": extract_safety_flags(raw_text),
        "claimed_urls": sorted(set(re.findall(r"https?://[^\s`)]+", raw_text))),
        "claimed_next_milestone": extract_value(raw_text, "next milestone") or extract_value(raw_text, "next step"),
    }


def compare_report(
    extracted: dict[str, Any],
    bundle: dict[str, Any] | None,
    prompt: dict[str, Any] | None,
    raw_text: str,
) -> dict[str, Any]:
    expected_files = set((prompt or {}).get("expected_files") or (bundle or {}).get("intended_files") or [])
    changed_files = set(extracted.get("files_changed", []))
    violations = detect_guardrail_violations(extracted, changed_files, raw_text)
    missing = detect_missing_evidence(extracted, expected_files, changed_files)
    reasons = build_reasons(expected_files, changed_files, violations, missing)
    verdict = choose_verdict(violations, missing, extracted)
    return {"verdict": verdict, "reasons": reasons, "missing_evidence": missing, "guardrail_violations": violations}


def build_result(
    raw_text: str,
    extracted: dict[str, Any],
    comparison: dict[str, Any],
    source_prompt_id: str | None,
    source_bundle_id: str | None,
) -> dict[str, Any]:
    result_id = str(uuid4())
    return {
        "kind": "x_native_result_intake_v0",
        "created_at": utc_iso(),
        "result_id": result_id,
        "source_prompt_id": source_prompt_id,
        "source_bundle_id": source_bundle_id,
        "source_result_text": raw_text,
        "extracted_report": extracted,
        "verdict": comparison["verdict"],
        "reasons": comparison["reasons"],
        "missing_evidence": comparison["missing_evidence"],
        "guardrail_violations": comparison["guardrail_violations"],
        "recommended_next_action": next_action(comparison["verdict"]),
        "copy_to_chatgpt_authorization_summary": authorization_summary(comparison, extracted, source_bundle_id),
        **locked_flags(),
    }


def extract_value(raw_text: str, label: str) -> str | None:
    pattern = re.compile(rf"^\s*[-*]?\s*{re.escape(label)}\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(raw_text)
    return match.group(1).strip(" `") if match else None


def extract_commit(raw_text: str) -> str | None:
    explicit = extract_value(raw_text, "commit hash")
    if explicit:
        return explicit
    match = re.search(r"\b[0-9a-f]{7,40}\b", raw_text, re.IGNORECASE)
    return match.group(0) if match else None


def extract_yes_no(raw_text: str, label: str) -> str | None:
    value = extract_value(raw_text, label)
    if not value:
        return None
    lowered = value.lower()
    if "yes" in lowered:
        return "yes"
    if "no" in lowered:
        return "no"
    return value


def extract_section(raw_text: str, label: str) -> list[str]:
    value = extract_value(raw_text, label)
    if value and value.lower() not in ("none", "no"):
        return [value]
    lines = []
    capture = False
    for line in raw_text.splitlines():
        if re.search(rf"^\s*[-*]?\s*{re.escape(label)}\s*:\s*$", line, re.IGNORECASE):
            capture = True
            continue
        if capture and re.search(r"^\s*[-*]?\s*[a-z _-]+\s*:", line, re.IGNORECASE):
            break
        if capture and line.strip():
            lines.append(line.strip(" -`"))
    return lines


def extract_files(raw_text: str) -> list[str]:
    candidates = set()
    section = extract_section(raw_text, "files changed")
    for line in section or raw_text.splitlines():
        for match in re.findall(r"[\w./\\-]+\.(?:py|js|html|css|md|ps1|yml|json)", line):
            candidates.add(match.replace("\\", "/").strip("`.,"))
    return sorted(candidates)


def extract_safety_flags(raw_text: str) -> dict[str, bool | None]:
    flags = {}
    for name in ("execution_allowed", "apply_allowed", "repo_write", "promoted_to_repo"):
        match = re.search(rf"{name}\s*=\s*(true|false)", raw_text, re.IGNORECASE)
        flags[name] = None if not match else match.group(1).lower() == "true"
    return flags


def detect_guardrail_violations(extracted: dict[str, Any], changed_files: set[str], raw_text: str) -> list[str]:
    violations = []
    for path in changed_files:
        normalized = path.replace("\\", "/")
        if any(normalized == denied or normalized.startswith(denied) for denied in DENIED_PREFIXES):
            violations.append(f"Denied path reported as changed: {path}")
    if extracted.get("denied_paths_touched") == "yes":
        violations.append("Report says denied paths were touched.")
    if extracted.get("legacy_routes_used") == "yes":
        violations.append("Report says legacy routes were used.")
    if any(marker.lower() in raw_text.lower() for marker in LEGACY_MARKERS):
        violations.append("Legacy marker appears in pasted result text.")
    for name, value in extracted.get("claimed_safety_flags", {}).items():
        if value is True:
            violations.append(f"Safety flag claimed true: {name}")
    return violations


def detect_missing_evidence(extracted: dict[str, Any], expected_files: set[str], changed_files: set[str]) -> list[str]:
    missing = []
    if not extracted.get("reported_branch"):
        missing.append("reported branch")
    if not extracted.get("reported_commit_hash"):
        missing.append("reported commit hash")
    if not changed_files:
        missing.append("files changed")
    if not extracted.get("validation_results"):
        missing.append("validation results")
    if expected_files and not expected_files.issubset(changed_files):
        missing.append("all expected files changed or explicitly accounted for")
    return missing


def build_reasons(expected_files: set[str], changed_files: set[str], violations: list[str], missing: list[str]) -> list[str]:
    reasons = []
    if expected_files:
        reasons.append(f"Expected files: {', '.join(sorted(expected_files))}")
    if changed_files:
        reasons.append(f"Reported files: {', '.join(sorted(changed_files))}")
    reasons.extend(violations)
    reasons.extend(f"Missing evidence: {item}" for item in missing)
    return reasons or ["Result text contains enough review evidence and no guardrail violation was detected."]


def choose_verdict(violations: list[str], missing: list[str], extracted: dict[str, Any]) -> str:
    if violations:
        return "fail"
    if len(missing) >= 3:
        return "incomplete"
    if missing:
        return "needs_human_decision"
    return "pass"


def next_action(verdict: str) -> str:
    if verdict == "fail":
        return "Do not authorize. Ask Codex to repair the guardrail violation and rerun validation."
    if verdict == "incomplete":
        return "Request a complete Codex report with branch, commit, changed files, validation, and dirty state."
    if verdict == "pass":
        return "Copy the passing review summary to ChatGPT for external human authorization."
    return "Copy the authorization summary to ChatGPT for external human authorization."


def authorization_summary(comparison: dict[str, Any], extracted: dict[str, Any], bundle_id: str | None) -> str:
    return (
        "X Native review-only authorization summary\n"
        f"Source bundle: {bundle_id}\n"
        f"Verdict: {comparison['verdict']}\n"
        f"Branch: {extracted.get('reported_branch')}\n"
        f"Commit: {extracted.get('reported_commit_hash')}\n"
        f"Files: {', '.join(extracted.get('files_changed') or [])}\n"
        f"Missing evidence: {', '.join(comparison['missing_evidence']) or 'none'}\n"
        f"Guardrail violations: {', '.join(comparison['guardrail_violations']) or 'none'}\n"
        "X Native has not applied, approved, or written repo changes."
    )
