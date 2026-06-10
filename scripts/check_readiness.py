#!/usr/bin/env python
"""XV7 Local Readiness Check

Run this script before launching XV7 to confirm your local environment is
configured.  It reports what is *set* vs *missing* without probing any live
service (Ollama, Docker, network) and without printing secret values.

Usage:
    python scripts/check_readiness.py
    python scripts/check_readiness.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.runtime.readiness import build_readiness_report  # noqa: E402


# ---------------------------------------------------------------------------
# ANSI helpers (no external dep required)
# ---------------------------------------------------------------------------

_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _tick(ok: bool) -> str:
    return f"{_GREEN}✓{_RESET}" if ok else f"{_RED}✗{_RESET}"


def _print_human(report) -> None:  # type: ignore[type-arg]
    print(f"\n{_BOLD}XV7 Local Readiness Report{_RESET}")
    print("=" * 48)
    for item in report.items:
        marker = _tick(item.ok)
        print(f"  {marker}  {item.key:<30}  {item.value}")

    warnings = report.warnings
    if warnings:
        print(f"\n{_YELLOW}Warnings ({len(warnings)}):{_RESET}")
        for w in warnings:
            print(f"  {_YELLOW}!{_RESET}  {w}")

    print()
    if report.all_ok:
        print(f"{_GREEN}{_BOLD}All checks passed.{_RESET}")
    else:
        failed = sum(1 for i in report.items if not i.ok)
        print(
            f"{_RED}{_BOLD}{failed} check(s) need attention "
            f"(see warnings above).{_RESET}"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="XV7 local runtime readiness check.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the report as JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    report = build_readiness_report()

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        _print_human(report)

    # Exit 1 if any item failed so CI/shell scripts can detect issues.
    sys.exit(0 if report.all_ok else 1)


if __name__ == "__main__":
    main()
