"""X Native self, doctor, and diagnostics CLI.

This sidecar script is standard-library only. It reports X's current host
profile, repo visibility, write readiness, runtime diagnostics, and proof
receipts without executing arbitrary build tasks.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RECEIPT_DIR = Path("data/x_inbox/receipts")
TMP_DIR = Path("data/x_runtime/tmp")
INBOX_DIRS = [
    Path("data/x_inbox/pending"),
    Path("data/x_inbox/running"),
    Path("data/x_inbox/completed"),
    Path("data/x_inbox/failed"),
    Path("data/x_inbox/receipts"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / ".git").exists() or (parent / "docker-compose.yml").exists():
            return parent
    return Path.cwd().resolve()


def command_result(args: list[str], cwd: Path, timeout: int = 15) -> dict[str, Any]:
    executable = shutil.which(args[0])
    if not executable:
        return {
            "available": False,
            "ok": False,
            "command": " ".join(args),
            "output": "",
            "error": f"{args[0]} not found on PATH",
        }
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        output = (completed.stdout or completed.stderr or "").strip()
        return {
            "available": True,
            "ok": completed.returncode == 0,
            "command": " ".join(args),
            "returncode": completed.returncode,
            "output": output,
        }
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        return {
            "available": True,
            "ok": False,
            "command": " ".join(args),
            "output": "",
            "error": str(exc),
        }


def check_writable(path: Path) -> dict[str, Any]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix="x_write_check_",
            suffix=".tmp",
            dir=path,
            delete=False,
        ) as handle:
            handle.write("x native write check\n")
            temp_path = Path(handle.name)
        temp_path.unlink(missing_ok=True)
        return {"ok": True, "severity": "pass", "path": str(path)}
    except Exception as exc:
        return {"ok": False, "severity": "fail", "path": str(path), "error": str(exc)}


def http_get_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        data = json.loads(body) if body else {}
        return {"ok": True, "severity": "pass", "url": url, "data": data}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "severity": "warn", "url": url, "error": str(exc)}


def build_self_model(root: Path) -> dict[str, Any]:
    return {
        "name": "X / Xoduz",
        "owner": "Otis Duncan",
        "host_profile": os.environ.get("X_HOST_PROFILE", "omega"),
        "native_mode": os.environ.get("X_NATIVE_MODE", "1"),
        "repo_root": str(root),
        "mission": (
            "Assist Otis with communication, planning, research, coding, "
            "troubleshooting, automation, system operation, and improving XV7."
        ),
        "baseline": [
            "receive prompt packages",
            "inspect repo and runtime readiness",
            "verify repo write readiness",
            "save proof receipts",
            "recommend next actions",
        ],
    }


def parse_models_profile(root: Path) -> dict[str, Any]:
    path = root / "config/models.yml"
    if not path.exists():
        return {"ok": False, "severity": "fail", "path": str(path), "error": "missing"}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {"ok": False, "severity": "warn", "path": str(path), "error": str(exc)}
    candidates = []
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped and not stripped.startswith("#") and (
            "active" in lowered or "profile" in lowered or "default" in lowered
        ):
            candidates.append(stripped)
    return {
        "ok": bool(candidates),
        "severity": "pass" if candidates else "warn",
        "path": str(path),
        "summary": candidates[:5],
        "error": "" if candidates else "no obvious active/profile line found",
    }


def add_check(checks: dict[str, dict[str, Any]], name: str, result: dict[str, Any]) -> None:
    result.setdefault("severity", "pass" if result.get("ok") else "warn")
    checks[name] = result


def gather_checks(root: Path) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}

    add_check(checks, "python", {
        "ok": True,
        "severity": "pass",
        "executable": sys.executable,
        "version": sys.version.replace("\n", " "),
    })
    add_check(checks, "platform", {
        "ok": True,
        "severity": "pass",
        "platform": platform.platform(),
        "system": platform.system(),
    })
    add_check(checks, "cwd", {"ok": True, "severity": "pass", "path": str(Path.cwd())})
    add_check(checks, "repo_root", {"ok": root.exists(), "severity": "pass" if root.exists() else "fail", "path": str(root)})
    add_check(checks, "repo_writable", check_writable(root / TMP_DIR))

    for inbox_dir in INBOX_DIRS:
        path = root / inbox_dir
        add_check(checks, inbox_dir.as_posix().replace("/", "_"), {
            "ok": path.exists(),
            "severity": "pass" if path.exists() else "fail",
            "path": str(path),
        })
    add_check(checks, "receipt_writable", check_writable(root / RECEIPT_DIR))

    git_version = command_result(["git", "--version"], root)
    add_check(checks, "git_available", {**git_version, "severity": "pass" if git_version.get("ok") else "fail"})
    branch = command_result(["git", "branch", "--show-current"], root)
    add_check(checks, "git_branch", {**branch, "severity": "pass" if branch.get("ok") else "warn"})
    status = command_result(["git", "status", "--short"], root)
    dirty_lines = [line for line in str(status.get("output", "")).splitlines() if line.strip()]
    add_check(checks, "git_dirty_status", {
        **status,
        "ok": status.get("ok", False),
        "severity": "warn" if dirty_lines else ("pass" if status.get("ok") else "warn"),
        "dirty_count": len(dirty_lines),
        "summary": dirty_lines[:12],
    })

    docker = command_result(["docker", "--version"], root)
    add_check(checks, "docker_available", {**docker, "severity": "pass" if docker.get("ok") else "fail"})
    compose = command_result(["docker", "compose", "version"], root)
    add_check(checks, "docker_compose_available", {**compose, "severity": "pass" if compose.get("ok") else "fail"})
    compose_config = command_result(
        ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.x.yml", "config", "--services"],
        root,
    )
    services = [line.strip() for line in str(compose_config.get("output", "")).splitlines() if line.strip()]
    add_check(checks, "docker_compose_config", {
        **compose_config,
        "severity": "pass" if compose_config.get("ok") else "fail",
        "services": services,
    })
    compose_ps = command_result(["docker", "compose", "ps"], root, timeout=10)
    ps_output = str(compose_ps.get("output", ""))
    add_check(checks, "docker_compose_ps", {
        **compose_ps,
        "severity": "pass" if compose_ps.get("ok") and "xv7-core" in ps_output else "warn",
    })

    for name, rel in {
        "docker_compose_yml": "docker-compose.yml",
        "docker_compose_x_yml": "docker-compose.x.yml",
        "env_x_example": ".env.x.example",
        "config_models_yml": "config/models.yml",
        "xv7_prompt_script": "scripts/xv7_prompt.py",
        "x_self_model": "data/knowledge/xv7/X_SELF_MODEL.md",
        "x_mission": "data/knowledge/xv7/X_MISSION.md",
    }.items():
        path = root / rel
        add_check(checks, name, {
            "ok": path.exists(),
            "severity": "pass" if path.exists() else "fail",
            "path": str(path),
        })
    add_check(checks, "models_active_profile", parse_models_profile(root))

    ollama_cli = command_result(["ollama", "list"], root, timeout=10)
    add_check(checks, "ollama_cli", {**ollama_cli, "severity": "pass" if ollama_cli.get("ok") else "warn"})
    add_check(checks, "ollama_http", http_get_json("http://localhost:11434/api/tags"))

    return checks


def blocker(
    blocker_id: str,
    severity: str,
    explanation: str,
    probable_cause: str,
    recommended_next_action: str,
) -> dict[str, str]:
    return {
        "blocker_id": blocker_id,
        "severity": severity,
        "explanation": explanation,
        "probable_cause": probable_cause,
        "recommended_next_action": recommended_next_action,
    }


def interpret_checks(checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def failed(name: str) -> bool:
        return not checks.get(name, {}).get("ok")

    if failed("repo_root"):
        first = blocker(
            "repo_root_missing",
            "fail",
            "X cannot confirm the XV7 repo root.",
            "The script was not able to find a repo root or docker-compose.yml path.",
            "Run the script from the XV7 repo root and verify the checkout exists.",
        )
    elif failed("repo_writable"):
        first = blocker(
            "repo_write_failed",
            "fail",
            "X cannot write to the repo runtime path.",
            "X cannot write to the repo path or data/x_runtime/tmp.",
            "Verify compose mount is `./:/workspace:rw` and run the script from the repo root on the host.",
        )
    elif failed("receipt_writable"):
        first = blocker(
            "receipt_write_failed",
            "fail",
            "X cannot write proof receipts.",
            "data/x_inbox/receipts is missing or not writable.",
            "Create data/x_inbox/receipts and ensure this user can write to it, then rerun diagnose.",
        )
    elif any(failed(name) for name in [
        "data_x_inbox_pending",
        "data_x_inbox_running",
        "data_x_inbox_completed",
        "data_x_inbox_failed",
        "data_x_inbox_receipts",
    ]):
        first = blocker(
            "prompt_inbox_incomplete",
            "fail",
            "X Prompt Inbox directories are incomplete.",
            "One or more data/x_inbox folders are missing.",
            "Restore the X Prompt Inbox skeleton and rerun diagnose.",
        )
    elif failed("git_available"):
        first = blocker(
            "git_unavailable",
            "fail",
            "Git is not available to X.",
            "git is missing from PATH or failed to run.",
            "Install Git or fix PATH, then rerun `python scripts\\xv7_x.py diagnose --save`.",
        )
    elif failed("docker_available"):
        first = blocker(
            "docker_unavailable",
            "fail",
            "Docker is not available to X.",
            "Docker is missing from PATH or Docker Desktop is unavailable.",
            "Start/install Docker Desktop, then rerun `python scripts\\xv7_x.py diagnose --save`.",
        )
    elif failed("docker_compose_available"):
        first = blocker(
            "docker_compose_unavailable",
            "fail",
            "Docker Compose is not available to X.",
            "The `docker compose` plugin is unavailable or failing.",
            "Install/repair Docker Compose, then rerun `python scripts\\xv7_x.py diagnose --save`.",
        )
    elif failed("docker_compose_config"):
        first = blocker(
            "compose_config_invalid",
            "fail",
            "Docker Compose config did not validate.",
            "docker-compose.yml and docker-compose.x.yml could not be merged into a valid service config.",
            "Run `docker compose -f docker-compose.yml -f docker-compose.x.yml config --services` and fix the reported compose error.",
        )
    elif failed("config_models_yml"):
        first = blocker(
            "models_config_missing",
            "fail",
            "Model configuration is missing.",
            "config/models.yml does not exist.",
            "Restore config/models.yml, then rerun diagnose.",
        )
    elif failed("ollama_cli") and failed("ollama_http"):
        first = blocker(
            "ollama_unavailable",
            "warn",
            "Ollama is not reachable from this shell.",
            "Ollama is not running or not reachable at localhost:11434.",
            "Start Ollama or the Ollama container, then rerun `python scripts\\xv7_x.py diagnose --save`.",
        )
    elif "xv7-core" not in str(checks.get("docker_compose_ps", {}).get("output", "")):
        first = blocker(
            "core_services_unknown",
            "warn",
            "X cannot confirm core services are running.",
            "`docker compose ps` did not show xv7-core as running from this shell.",
            "Start the XV7 compose stack or rerun diagnose from the shell that controls it.",
        )
    elif int(checks.get("git_dirty_status", {}).get("dirty_count", 0)) > 0:
        first = blocker(
            "dirty_repo_warning",
            "warn",
            "The repo has uncommitted changes.",
            "Current branch contains modified or untracked files.",
            "Review `git status --short`, then commit, stash, or intentionally continue with the dirty branch.",
        )
    else:
        first = blocker(
            "none",
            "pass",
            "No first blocker detected.",
            "All required X Native diagnostic checks passed.",
            "Continue with the next X Native build task.",
        )

    failing = sorted(name for name, result in checks.items() if result.get("severity") == "fail")
    warnings = sorted(name for name, result in checks.items() if result.get("severity") == "warn")
    passing = sorted(name for name, result in checks.items() if result.get("severity") == "pass")
    if failing:
        overall = "fail"
    elif warnings or first["severity"] == "warn":
        overall = "warn"
    else:
        overall = "pass"
    return {
        "overall_status": overall,
        "passing_checks": passing,
        "warning_checks": warnings,
        "failing_checks": failing,
        "first_blocker": first,
        "probable_cause": first["probable_cause"],
        "recommended_next_action": first["recommended_next_action"],
    }


def run_doctor(root: Path) -> dict[str, Any]:
    checks = gather_checks(root)
    doctor_keys = [
        "repo_root",
        "repo_writable",
        "data_x_inbox_pending",
        "data_x_inbox_running",
        "data_x_inbox_completed",
        "data_x_inbox_failed",
        "data_x_inbox_receipts",
        "receipt_writable",
        "docker_available",
        "docker_compose_available",
        "git_available",
        "git_dirty_status",
        "config_models_yml",
        "docker_compose_yml",
        "docker_compose_x_yml",
    ]
    return {
        "receipt_type": "x_native_doctor",
        "created_at": utc_now(),
        "self": build_self_model(root),
        "checks": {key: checks[key] for key in doctor_keys if key in checks},
    }


def run_diagnose(root: Path) -> dict[str, Any]:
    checks = gather_checks(root)
    interpretation = interpret_checks(checks)
    branch = checks.get("git_branch", {}).get("output", "")
    return {
        "receipt_type": "x_native_diagnose",
        "created_at": utc_now(),
        "timestamp": utc_now(),
        "host_profile": os.environ.get("X_HOST_PROFILE", "omega"),
        "repo_root": str(root),
        "git_branch": branch,
        "checks": checks,
        **interpretation,
    }


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def run_readiness(root: Path) -> dict[str, Any]:
    checks = gather_checks(root)
    latest_diagnosis = read_json_file(root / RECEIPT_DIR / "latest_diagnose.json")
    latest_apply = read_json_file(root / RECEIPT_DIR / "latest_apply_receipt.json")
    dirty_count = int(checks.get("git_dirty_status", {}).get("dirty_count", 0))
    essentials = {
        "prompt_inbox_exists": all(
            checks.get(name, {}).get("ok")
            for name in [
                "data_x_inbox_pending",
                "data_x_inbox_running",
                "data_x_inbox_completed",
                "data_x_inbox_failed",
                "data_x_inbox_receipts",
            ]
        ),
        "receipts_writable": bool(checks.get("receipt_writable", {}).get("ok")),
        "repo_writable": bool(checks.get("repo_writable", {}).get("ok")),
        "diagnostics_available": True,
        "prompt_executor_available": bool(checks.get("xv7_prompt_script", {}).get("ok")),
    }
    if not all(essentials.values()):
        status = "fail"
        next_action = "Fix failed readiness checks, then rerun `python scripts\\xv7_x.py readiness --save`."
        first_blocker = next((name for name, ok in essentials.items() if not ok), "readiness_failed")
    elif dirty_count:
        status = "warn"
        next_action = "Review `git status --short`, then commit, stash, or intentionally continue with the dirty branch."
        first_blocker = "dirty_repo_warning"
    elif latest_diagnosis.get("overall_status") in {"warn", "fail"}:
        status = str(latest_diagnosis.get("overall_status"))
        next_action = str(latest_diagnosis.get("recommended_next_action", "Review latest diagnosis."))
        first_blocker = str(latest_diagnosis.get("first_blocker", {}).get("blocker_id", "diagnosis_warning"))
    else:
        status = "pass"
        next_action = "X is ready to receive and apply structured prompt packages."
        first_blocker = "none"
    return {
        "receipt_type": "x_native_readiness",
        "created_at": utc_now(),
        "timestamp": utc_now(),
        "host_profile": os.environ.get("X_HOST_PROFILE", "omega"),
        "repo_root": str(root),
        "current_branch": checks.get("git_branch", {}).get("output", ""),
        "dirty_status_count": dirty_count,
        "readiness_status": status,
        "first_blocker": first_blocker,
        "checks": essentials,
        "latest_diagnosis_status": latest_diagnosis.get("overall_status", "unknown"),
        "latest_apply_status": latest_apply.get("status", "unknown"),
        "recommended_next_action": next_action,
    }


def receipt_path(root: Path, prefix: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / RECEIPT_DIR / f"{stamp}_{prefix}.json"


def save_receipt(root: Path, receipt: dict[str, Any], prefix: str) -> Path:
    target = receipt_path(root, prefix)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = target.parent / f"latest_{prefix}.json"
    latest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["proof_receipt_path"] = str(latest)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def detail_for(result: dict[str, Any]) -> str:
    detail = (
        result.get("error")
        or result.get("output")
        or result.get("path")
        or result.get("version")
        or result.get("summary")
        or ""
    )
    if isinstance(detail, list):
        detail = "; ".join(str(item) for item in detail)
    return str(detail)


def print_self(model: dict[str, Any]) -> None:
    print("X Native Self")
    print(f"Name: {model['name']}")
    print(f"Owner: {model['owner']}")
    print(f"Host profile: {model['host_profile']}")
    print(f"Native mode: {model['native_mode']}")
    print(f"Repo root: {model['repo_root']}")
    print(f"Mission: {model['mission']}")
    print("Baseline capabilities:")
    for item in model["baseline"]:
        print(f"- {item}")


def print_doctor(receipt: dict[str, Any]) -> None:
    print("X Doctor")
    print(f"Created: {receipt['created_at']}")
    print(f"Host profile: {receipt['self']['host_profile']}")
    print(f"Native mode: {receipt['self']['native_mode']}")
    print(f"Repo root: {receipt['self']['repo_root']}")
    print("Checks:")
    for name, result in receipt["checks"].items():
        severity = str(result.get("severity") or "").lower()
        status = "FAIL" if severity == "fail" else ("WARN" if severity == "warn" else "PASS")
        detail = detail_for(result)
        print(f"- {name}: {status}" + (f" ({detail})" if detail else ""))


def print_diagnosis(receipt: dict[str, Any], proof_path: Path | None = None) -> None:
    print(f"X Diagnosis: {str(receipt['overall_status']).upper()}")
    print()
    print(f"Host: {receipt['host_profile']}")
    print(f"Repo: {receipt['repo_root']}")
    print(f"Branch: {receipt.get('git_branch') or 'unknown'}")
    print()
    print("Passing:")
    for name in receipt["passing_checks"]:
        print(f"- {name}")
    print()
    print("Warnings:")
    if receipt["warning_checks"]:
        for name in receipt["warning_checks"]:
            result = receipt["checks"].get(name, {})
            detail = detail_for(result)
            print(f"- {name}" + (f": {detail}" if detail else ""))
    else:
        print("- none")
    print()
    print("Failing:")
    if receipt["failing_checks"]:
        for name in receipt["failing_checks"]:
            result = receipt["checks"].get(name, {})
            detail = detail_for(result)
            print(f"- {name}" + (f": {detail}" if detail else ""))
    else:
        print("- none")
    print()
    print("First blocker:")
    print(receipt["first_blocker"]["blocker_id"])
    print()
    print("Probable cause:")
    print(receipt["probable_cause"])
    print()
    print("Recommended next action:")
    print(receipt["recommended_next_action"])
    if proof_path:
        print()
        print("Proof:")
        print(proof_path)


def print_readiness(receipt: dict[str, Any], proof_path: Path | None = None) -> None:
    print(f"X Readiness: {str(receipt['readiness_status']).upper()}")
    print(f"Host: {receipt['host_profile']}")
    print(f"Repo: {receipt['repo_root']}")
    print(f"Branch: {receipt.get('current_branch') or 'unknown'}")
    print(f"Dirty files: {receipt['dirty_status_count']}")
    print("Checks:")
    for name, ok in receipt["checks"].items():
        print(f"- {name}: {'PASS' if ok else 'FAIL'}")
    print(f"Latest diagnosis status: {receipt['latest_diagnosis_status']}")
    print(f"Latest apply status: {receipt['latest_apply_status']}")
    print(f"First blocker: {receipt['first_blocker']}")
    print("Recommended next action:")
    print(receipt["recommended_next_action"])
    if proof_path:
        print(f"Proof: {proof_path}")


def print_paths(root: Path) -> None:
    print("X Native Paths")
    for label, path in {
        "repo_root": root,
        "prompt_inbox": root / "data/x_inbox",
        "pending": root / "data/x_inbox/pending",
        "running": root / "data/x_inbox/running",
        "completed": root / "data/x_inbox/completed",
        "failed": root / "data/x_inbox/failed",
        "receipts": root / RECEIPT_DIR,
        "runtime_tmp": root / TMP_DIR,
    }.items():
        print(f"{label}: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="X Native self and doctor CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--save", action="store_true")
    diagnose = sub.add_parser("diagnose")
    diagnose.add_argument("--save", action="store_true")
    readiness = sub.add_parser("readiness")
    readiness.add_argument("--save", action="store_true")
    sub.add_parser("repo")
    sub.add_parser("proof")
    sub.add_parser("paths")
    args = parser.parse_args(argv)

    root = repo_root()
    try:
        if args.command == "self":
            print_self(build_self_model(root))
        elif args.command == "doctor":
            receipt = run_doctor(root)
            saved: Path | None = None
            if args.save:
                saved = save_receipt(root, receipt, "doctor")
            print_doctor(receipt)
            if saved:
                print(f"Saved proof receipt: {saved}")
                print(f"Latest doctor receipt: {root / RECEIPT_DIR / 'latest_doctor.json'}")
        elif args.command == "diagnose":
            receipt = run_diagnose(root)
            saved = save_receipt(root, receipt, "diagnose") if args.save else None
            proof = root / RECEIPT_DIR / "latest_diagnose.json" if args.save else None
            print_diagnosis(receipt, proof)
            if saved:
                print(f"Saved diagnosis receipt: {saved}")
        elif args.command == "readiness":
            receipt = run_readiness(root)
            saved = save_receipt(root, receipt, "readiness") if args.save else None
            proof = root / RECEIPT_DIR / "latest_readiness.json" if args.save else None
            print_readiness(receipt, proof)
            if saved:
                print(f"Saved readiness receipt: {saved}")
        elif args.command == "repo":
            receipt = run_doctor(root)
            print_doctor({
                **receipt,
                "checks": {
                    key: value
                    for key, value in receipt["checks"].items()
                    if key.startswith("repo_") or key.startswith("git_")
                },
            })
        elif args.command == "proof":
            receipts = sorted((root / RECEIPT_DIR).glob("*.json"))
            print("X Proof Ledger")
            print(f"Receipt directory: {root / RECEIPT_DIR}")
            print(f"Receipt count: {len(receipts)}")
            for path in receipts[-12:]:
                print(f"- {path.name}")
        elif args.command == "paths":
            print_paths(root)
    except Exception as exc:  # Keep doctor/reporting failures in-band.
        print(f"X Native CLI completed with warning: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
