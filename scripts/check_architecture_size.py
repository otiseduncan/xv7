"""Architecture size guard for XV7.

This is intentionally conservative:
- generated/vendor/runtime output must not be tracked;
- new hand-maintained source files may not exceed SAFE_MAX_LINES;
- existing oversized files are allowed only through the baseline below;
- existing oversized files may shrink, but may not grow past their baseline ceiling.

The goal is to stop new architectural debt while we split the current large files down.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SAFE_MAX_LINES = 1000
WATCH_LINES = 500

# Transitional baseline for known oversized hand-maintained files.
# These are split debt, not acceptable long-term architecture.
# Keep ceilings close to the latest audit so these files cannot keep growing.
BASELINE_MAX_LINES: dict[str, int] = {
    "core/brain/answer_contract.py": 6700,
    "core/brain/artifact_response_service.py": 1700,
    "public/app.js": 6500,
    "public/app.test.js": 5500,
    "core/main.py": 4600,
    "tests/test_conversation_quality.py": 3400,
    "tests/test_answer_contract.py": 3200,
    "core/operator/manager.py": 2600,
    "communication-gauntlet-cases.json": 2500,
    "public/styles.css": 2300,
    "tests/test_operator_chat_integration.py": 1600,
    "scripts/operator_readiness_report.py": 1400,
    "tests/test_operator_chat_routing_v1e.py": 1100,
}

TRACKED_FORBIDDEN_PREFIXES = (
    "node_modules/",
    "dist/",
    "build/",
    "coverage/",
    "playwright-report/",
    "test-results/",
    "generated-sites/",
    "runtime/",
    "logs/",
    "tmp/",
    "temp/",
    ".venv/",
    "venv/",
    "__pycache__/",
    ".pytest_cache/",
)

IGNORED_DIR_PARTS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".vite",
    ".cache",
    ".turbo",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "playwright-report",
    "test-results",
    "generated-sites",
    "runtime",
    "logs",
    "tmp",
    "temp",
}

IGNORED_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
}

SOURCE_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".py",
    ".ps1",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".css",
    ".scss",
    ".html",
    ".sql",
    ".sh",
    ".bat",
    ".cmd",
}


@dataclass(frozen=True)
class FileSizeResult:
    path: str
    lines: int
    max_lines: int
    status: str


def run_git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def is_forbidden_tracked_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in TRACKED_FORBIDDEN_PREFIXES)


def is_ignored_for_size(path: str) -> bool:
    normalized = path.replace("\\", "/")
    parts = set(normalized.split("/"))
    if parts & IGNORED_DIR_PARTS:
        return True
    if Path(normalized).name in IGNORED_FILENAMES:
        return True
    return Path(normalized).suffix.lower() not in SOURCE_EXTENSIONS


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            return sum(1 for _ in handle)
    except OSError as exc:
        raise RuntimeError(f"Could not read {path}: {exc}") from exc


def check_file_size(path: str) -> FileSizeResult | None:
    if is_ignored_for_size(path):
        return None

    line_count = count_lines(Path(path))
    max_lines = BASELINE_MAX_LINES.get(path, SAFE_MAX_LINES)

    if line_count > max_lines:
        return FileSizeResult(path=path, lines=line_count, max_lines=max_lines, status="FAIL")
    if path not in BASELINE_MAX_LINES and line_count > WATCH_LINES:
        return FileSizeResult(path=path, lines=line_count, max_lines=max_lines, status="WARN")
    return FileSizeResult(path=path, lines=line_count, max_lines=max_lines, status="OK")


def main() -> int:
    tracked_files = run_git_ls_files()

    forbidden = [path for path in tracked_files if is_forbidden_tracked_path(path)]
    failures: list[FileSizeResult] = []
    warnings: list[FileSizeResult] = []
    baseline_missing: list[str] = []

    tracked_set = set(tracked_files)
    for baseline_path in BASELINE_MAX_LINES:
        if baseline_path not in tracked_set:
            baseline_missing.append(baseline_path)

    for path in tracked_files:
        result = check_file_size(path)
        if result is None:
            continue
        if result.status == "FAIL":
            failures.append(result)
        elif result.status == "WARN":
            warnings.append(result)

    if forbidden:
        print("Architecture size guard failed: generated/vendor/runtime output is tracked:")
        for path in forbidden[:100]:
            print(f"  - {path}")
        if len(forbidden) > 100:
            print(f"  ... and {len(forbidden) - 100} more")
        print()

    if failures:
        print("Architecture size guard failed: files exceed allowed line ceilings:")
        for item in sorted(failures, key=lambda entry: entry.lines, reverse=True):
            print(f"  - {item.path}: {item.lines} lines > allowed {item.max_lines}")
        print()

    if baseline_missing:
        print("Architecture size guard warning: baseline paths no longer exist.")
        print("Remove these from BASELINE_MAX_LINES after confirming the split/removal was intentional:")
        for path in baseline_missing:
            print(f"  - {path}")
        print()

    if warnings:
        print("Architecture size guard warning: non-baselined files over watch threshold:")
        for item in sorted(warnings, key=lambda entry: entry.lines, reverse=True):
            print(f"  - {item.path}: {item.lines} lines")
        print()

    if forbidden or failures:
        print("Policy: no new hand-maintained source file may exceed 1000 lines.")
        print("Existing oversized files must stay under their transition baseline until split.")
        return 1

    print("Architecture size guard passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
