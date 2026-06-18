"""X Native prompt inbox and structured package executor.

This CLI receives prompt packages, previews deterministic repo actions, applies
allowed file operations, runs a small command allowlist, and saves proof
receipts. It intentionally does not provide unrestricted shell execution.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INBOX_ROOT = Path("data/x_inbox")
PENDING = INBOX_ROOT / "pending"
RUNNING = INBOX_ROOT / "running"
COMPLETED = INBOX_ROOT / "completed"
FAILED = INBOX_ROOT / "failed"
RECEIPTS = INBOX_ROOT / "receipts"

BREAK_GLASS_WORDS = (
    "wipe",
    "format",
    "partition",
    "delete drive",
    "firmware",
    "bootloader",
    "destructive",
)
WRITE_WORDS = ("edit", "write", "patch", "create file", "update file")
DIAGNOSTIC_PHRASES = (
    "diagnose",
    "self-diagnostic",
    "what is wrong",
    "what's wrong",
    "doctor",
    "health check",
    "inspect yourself",
    "status check",
)
FILE_ACTIONS = {"CREATE_FILE", "UPDATE_FILE", "APPEND_FILE", "REPLACE_TEXT"}
SHELL_OPERATORS = ("&&", "||", ";", "|", ">", "<", "`", "$(")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / ".git").exists() or (parent / "docker-compose.yml").exists():
            return parent
    return Path.cwd().resolve()


def ensure_dirs(root: Path) -> None:
    for path in [PENDING, RUNNING, COMPLETED, FAILED, RECEIPTS]:
        (root / path).mkdir(parents=True, exist_ok=True)


def task_id() -> str:
    return "x-task-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def classify(prompt: str) -> tuple[str, bool]:
    text = prompt.lower()
    if any(word in text for word in BREAK_GLASS_WORDS):
        return "break_glass", True
    if any(word in text for word in WRITE_WORDS) or "x_actions:" in text:
        return "developer_write", False
    return "inspect_or_plan", False


def task_path(root: Path, folder: Path, ident: str) -> Path:
    return root / folder / f"{ident}.json"


def receipt_path(root: Path, ident: str, suffix: str = "receipt") -> Path:
    return root / RECEIPTS / f"{ident}_{suffix}.json"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload.setdefault("receipt_path", str(path))
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_receipt(root: Path, path: Path, payload: dict[str, Any], latest_names: list[str] | None = None) -> None:
    write_json(path, payload)
    for name in latest_names or []:
        write_json(root / RECEIPTS / name, payload)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def submit(root: Path, source: str) -> int:
    ensure_dirs(root)
    raw_prompt = sys.stdin.read()
    ident = task_id()
    risk, requires_confirmation = classify(raw_prompt)
    task = {
        "task_id": ident,
        "source": source,
        "status": "pending",
        "created_at": utc_now(),
        "mode": "x_native",
        "host_profile": os.environ.get("X_HOST_PROFILE", "omega"),
        "raw_prompt": raw_prompt,
        "risk": risk,
        "requires_confirmation": requires_confirmation,
    }
    path = task_path(root, PENDING, ident)
    write_json(path, task)
    print(f"Submitted prompt package: {ident}")
    print(f"Risk: {risk}")
    print(f"Requires confirmation: {requires_confirmation}")
    print(f"Task file: {path}")
    return 0


def all_task_files(root: Path) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for name, folder in [
        ("pending", PENDING),
        ("running", RUNNING),
        ("completed", COMPLETED),
        ("failed", FAILED),
    ]:
        for path in sorted((root / folder).glob("*.json")):
            items.append((name, path))
    return items


def find_task(root: Path, ident: str) -> tuple[str, Path, dict[str, Any]] | None:
    for folder, path in all_task_files(root):
        if path.stem == ident:
            return folder, path, read_json(path)
    return None


def list_tasks(root: Path) -> int:
    ensure_dirs(root)
    counts = {
        "pending": len(list((root / PENDING).glob("*.json"))),
        "running": len(list((root / RUNNING).glob("*.json"))),
        "completed": len(list((root / COMPLETED).glob("*.json"))),
        "failed": len(list((root / FAILED).glob("*.json"))),
    }
    print("X Prompt Inbox")
    for name, count in counts.items():
        print(f"{name}: {count}")
    recent = sorted(all_task_files(root), key=lambda item: item[1].stat().st_mtime)[-10:]
    if recent:
        print("Recent tasks:")
        for folder, path in recent:
            task = read_json(path)
            print(
                f"- {task.get('task_id', path.stem)} [{folder}] "
                f"risk={task.get('risk')} source={task.get('source')}"
            )
    return 0


def is_diagnostic_prompt(prompt: str) -> bool:
    text = prompt.lower()
    return any(phrase in text for phrase in DIAGNOSTIC_PHRASES)


def has_x_actions(prompt: str) -> bool:
    return "x_actions:" in prompt.lower()


def run_diagnose(root: Path) -> dict[str, Any]:
    command = [sys.executable, str(root / "scripts/xv7_x.py"), "diagnose", "--save"]
    completed = subprocess.run(
        command,
        cwd=str(root),
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    latest_path = root / RECEIPTS / "latest_diagnose.json"
    diagnosis: dict[str, Any] = read_json(latest_path) if latest_path.exists() else {}
    return {
        "ok": completed.returncode == 0,
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "diagnosis_receipt_path": str(latest_path) if latest_path.exists() else "",
        "diagnosis": diagnosis,
    }


def package_actions_text(prompt: str) -> str:
    lower = prompt.lower()
    start = lower.find("x_actions:")
    if start < 0:
        return ""
    action_text = prompt[start + len("x_actions:") :]
    success_at = action_text.lower().find("\nsuccess:")
    if success_at >= 0:
        action_text = action_text[:success_at]
    return action_text.strip()


def parse_package(prompt: str) -> list[dict[str, Any]]:
    lines = package_actions_text(prompt).splitlines()
    actions: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line:
            continue
        parts = line.split(maxsplit=1)
        action_type = parts[0].upper()
        argument = parts[1].strip() if len(parts) > 1 else ""
        if action_type == "RUN_CHECK":
            actions.append({"type": "RUN_CHECK", "command": argument})
            continue
        if action_type in {"CREATE_FILE", "UPDATE_FILE", "APPEND_FILE"}:
            content, index = read_block(lines, index, "---CONTENT---", "---END_CONTENT---")
            actions.append({"type": action_type, "path": argument, "content": content})
            continue
        if action_type == "REPLACE_TEXT":
            find_text, index = read_block(lines, index, "---FIND---", "---REPLACE---")
            replace_text, index = read_block(lines, index, None, "---END_REPLACE---")
            actions.append({
                "type": action_type,
                "path": argument,
                "find": find_text,
                "replace": replace_text,
            })
            continue
        actions.append({"type": "UNKNOWN", "raw": line})
    return actions


def read_block(lines: list[str], index: int, start_marker: str | None, end_marker: str) -> tuple[str, int]:
    if start_marker is not None:
        while index < len(lines) and lines[index].strip() != start_marker:
            index += 1
        if index >= len(lines):
            return "", index
        index += 1
    content: list[str] = []
    while index < len(lines) and lines[index].strip() != end_marker:
        content.append(lines[index])
        index += 1
    if index < len(lines) and lines[index].strip() == end_marker:
        index += 1
    return "\n".join(content) + ("\n" if content else ""), index


def safe_repo_path(root: Path, raw_path: str) -> tuple[Path | None, str]:
    if not raw_path:
        return None, "missing path"
    candidate = Path(raw_path)
    if ".." in candidate.parts:
        return None, "path traversal is not allowed"
    if ".git" in candidate.parts:
        return None, "writes into .git are not allowed"
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None, "path is outside repo root"
    return resolved, ""


def has_shell_operator(command: str) -> bool:
    return any(operator in command for operator in SHELL_OPERATORS)


def is_allowed_check(command: str) -> tuple[bool, list[str], str]:
    if has_shell_operator(command):
        return False, [], "shell operators are not allowed in RUN_CHECK"
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError as exc:
        return False, [], str(exc)
    if not tokens:
        return False, [], "empty RUN_CHECK"
    lowered = [token.lower() for token in tokens]
    if lowered[0] in {"python", "python.exe", "py"}:
        return True, tokens, ""
    exact = [
        ["git", "status", "--short"],
        ["git", "branch", "--show-current"],
        ["docker", "--version"],
        ["docker", "compose", "version"],
        ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.x.yml", "config", "--services"],
    ]
    if lowered in exact:
        return True, tokens, ""
    return False, tokens, "RUN_CHECK is not in the allowlist"


def validate_package(root: Path, task: dict[str, Any]) -> dict[str, Any]:
    prompt = str(task.get("raw_prompt", ""))
    actions = parse_package(prompt)
    unsafe: list[dict[str, str]] = []
    planned: list[dict[str, Any]] = []
    if any(word in prompt.lower() for word in BREAK_GLASS_WORDS):
        unsafe.append({"type": "PACKAGE", "reason": "break-glass/destructive wording is not allowed"})
    if not actions:
        unsafe.append({"type": "PACKAGE", "reason": "no X_ACTIONS were found"})
    for action in actions:
        action_type = action.get("type", "")
        if action_type in FILE_ACTIONS:
            target, error = safe_repo_path(root, str(action.get("path", "")))
            if error:
                unsafe.append({"type": action_type, "path": str(action.get("path", "")), "reason": error})
            planned.append({**action, "resolved_path": str(target) if target else ""})
        elif action_type == "RUN_CHECK":
            ok, tokens, error = is_allowed_check(str(action.get("command", "")))
            if not ok:
                unsafe.append({"type": "RUN_CHECK", "command": str(action.get("command", "")), "reason": error})
            planned.append({**action, "tokens": tokens})
        else:
            unsafe.append({"type": action_type, "reason": "unknown action"})
            planned.append(action)
    return {
        "task_id": task.get("task_id"),
        "risk": task.get("risk"),
        "requires_confirmation": task.get("requires_confirmation"),
        "planned_actions": planned,
        "unsafe_actions": unsafe,
        "safe": not unsafe,
    }


def preview_task(root: Path, ident: str) -> int:
    ensure_dirs(root)
    found = find_task(root, ident)
    if not found:
        print(f"Task not found: {ident}")
        return 0
    _, _, task = found
    preview = validate_package(root, task)
    receipt = {
        "receipt_type": "x_prompt_preview",
        "task_id": ident,
        "created_at": utc_now(),
        "status": "previewed" if preview["safe"] else "unsafe",
        **preview,
    }
    path = receipt_path(root, ident, "preview")
    write_receipt(root, path, receipt, ["latest_prompt_receipt.json"])
    print(f"Preview for {ident}: {'SAFE' if preview['safe'] else 'UNSAFE'}")
    for action in preview["planned_actions"]:
        detail = action.get("path") or action.get("command") or action.get("raw", "")
        print(f"- {action.get('type')}: {detail}")
    if preview["unsafe_actions"]:
        print("Unsafe actions:")
        for item in preview["unsafe_actions"]:
            print(f"- {item.get('type')}: {item.get('reason')}")
    print(f"Preview receipt: {path}")
    return 0


def apply_task(root: Path, ident: str) -> dict[str, Any]:
    ensure_dirs(root)
    found = find_task(root, ident)
    if not found:
        return {"task_id": ident, "status": "failed", "first_error": "task not found"}
    folder, source_path, task = found
    if folder not in {"pending", "running"}:
        return {"task_id": ident, "status": "failed", "first_error": f"task is already {folder}"}
    preview = validate_package(root, task)
    running_path = task_path(root, RUNNING, ident)
    completed_path = task_path(root, COMPLETED, ident)
    failed_path = task_path(root, FAILED, ident)
    if folder == "pending":
        shutil.move(str(source_path), str(running_path))
    else:
        running_path = source_path
    task["status"] = "running"
    task["started_at"] = utc_now()
    write_json(running_path, task)

    receipt: dict[str, Any] = {
        "receipt_type": "x_prompt_apply",
        "task_id": ident,
        "created_at": utc_now(),
        "status": "completed",
        "actions_applied": [],
        "files_created": [],
        "files_updated": [],
        "checks_run": [],
        "check_exit_codes": [],
        "stdout_stderr_snippets": [],
        "first_error": "",
        "recommended_next_action": "Review the applied files and proof receipts.",
        "preview": preview,
    }
    try:
        if not preview["safe"]:
            raise RuntimeError(preview["unsafe_actions"][0]["reason"])
        for action in preview["planned_actions"]:
            action_type = action.get("type")
            if action_type in {"CREATE_FILE", "UPDATE_FILE", "APPEND_FILE", "REPLACE_TEXT"}:
                target = Path(str(action["resolved_path"]))
                target.parent.mkdir(parents=True, exist_ok=True)
                if action_type == "CREATE_FILE":
                    if target.exists():
                        raise RuntimeError(f"CREATE_FILE target already exists: {target}")
                    target.write_text(str(action.get("content", "")), encoding="utf-8")
                    receipt["files_created"].append(str(target))
                elif action_type == "UPDATE_FILE":
                    target.write_text(str(action.get("content", "")), encoding="utf-8")
                    receipt["files_updated"].append(str(target))
                elif action_type == "APPEND_FILE":
                    with target.open("a", encoding="utf-8") as handle:
                        handle.write(str(action.get("content", "")))
                    receipt["files_updated"].append(str(target))
                elif action_type == "REPLACE_TEXT":
                    if not target.exists():
                        raise RuntimeError(f"REPLACE_TEXT target missing: {target}")
                    current = target.read_text(encoding="utf-8")
                    find_text = str(action.get("find", ""))
                    if find_text not in current:
                        raise RuntimeError(f"REPLACE_TEXT find text not found in {target}")
                    target.write_text(current.replace(find_text, str(action.get("replace", "")), 1), encoding="utf-8")
                    receipt["files_updated"].append(str(target))
                receipt["actions_applied"].append(action_type)
            elif action_type == "RUN_CHECK":
                tokens = action["tokens"]
                completed = subprocess.run(
                    tokens,
                    cwd=str(root),
                    text=True,
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
                snippet = ((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")).strip()
                receipt["checks_run"].append(str(action.get("command", "")))
                receipt["check_exit_codes"].append(completed.returncode)
                receipt["stdout_stderr_snippets"].append(snippet[:1000])
                if completed.returncode != 0:
                    raise RuntimeError(f"RUN_CHECK failed: {action.get('command')}")
        task["status"] = "completed"
        task["completed_at"] = utc_now()
        task["result"] = "Structured prompt package applied with proof."
        write_json(running_path, task)
        shutil.move(str(running_path), str(completed_path))
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["first_error"] = str(exc)
        receipt["recommended_next_action"] = "Fix the unsafe action or failing check, then submit a corrected prompt package."
        task["status"] = "failed"
        task["failed_at"] = utc_now()
        task["error"] = str(exc)
        write_json(running_path, task)
        shutil.move(str(running_path), str(failed_path))
    path = receipt_path(root, ident, "apply")
    write_receipt(root, path, receipt, ["latest_prompt_receipt.json", "latest_apply_receipt.json"])
    return receipt


def complete_intake_only(root: Path, ident: str, task: dict[str, Any], source: Path) -> dict[str, Any]:
    completed_path = task_path(root, COMPLETED, ident)
    task["status"] = "completed"
    task["completed_at"] = utc_now()
    task["result"] = (
        "Prompt intake works. Full arbitrary prompt execution is not implemented "
        "without X_ACTIONS."
    )
    write_json(source, task)
    shutil.move(str(source), str(completed_path))
    receipt = {
        "receipt_type": "x_prompt_intake",
        "task_id": ident,
        "created_at": utc_now(),
        "status": "completed",
        "risk": task.get("risk"),
        "requires_confirmation": task.get("requires_confirmation"),
        "message": task["result"],
        "task_file": str(completed_path),
        "diagnostic_command_was_run": False,
    }
    write_receipt(root, receipt_path(root, ident), receipt, ["latest_prompt_receipt.json"])
    return receipt


def complete_diagnostic(root: Path, ident: str, task: dict[str, Any], source: Path) -> dict[str, Any]:
    completed_path = task_path(root, COMPLETED, ident)
    diagnostic_result = run_diagnose(root)
    diagnosis = diagnostic_result.get("diagnosis", {})
    first_blocker = diagnosis.get("first_blocker", {})
    task["status"] = "completed"
    task["completed_at"] = utc_now()
    task["result"] = (
        "Prompt intake worked. Diagnostic command was run. Full arbitrary "
        "prompt execution is still not implemented."
    )
    task["diagnosis_receipt_path"] = diagnostic_result.get("diagnosis_receipt_path", "")
    task["first_blocker"] = first_blocker.get("blocker_id", "")
    task["recommended_next_action"] = diagnosis.get("recommended_next_action", "")
    write_json(source, task)
    shutil.move(str(source), str(completed_path))
    receipt = {
        "receipt_type": "x_prompt_intake",
        "task_id": ident,
        "created_at": utc_now(),
        "status": "completed",
        "risk": task.get("risk"),
        "requires_confirmation": task.get("requires_confirmation"),
        "message": task["result"],
        "task_file": str(completed_path),
        "diagnostic_command_was_run": True,
        "diagnosis_receipt_path": diagnostic_result.get("diagnosis_receipt_path", ""),
        "diagnosis_status": diagnosis.get("overall_status", ""),
        "first_blocker": first_blocker.get("blocker_id", ""),
        "recommended_next_action": diagnosis.get("recommended_next_action", ""),
    }
    write_receipt(root, receipt_path(root, ident), receipt, ["latest_prompt_receipt.json"])
    return receipt


def run_next(root: Path, apply: bool = False) -> int:
    ensure_dirs(root)
    pending = sorted((root / PENDING).glob("*.json"))
    if not pending:
        print("No pending prompt packages.")
        return 0
    source = pending[0]
    task = read_json(source)
    ident = str(task["task_id"])
    raw_prompt = str(task.get("raw_prompt", ""))
    if apply and has_x_actions(raw_prompt):
        receipt = apply_task(root, ident)
        print(f"Applied prompt package: {ident}")
        print(f"Status: {receipt.get('status')}")
        print(f"Receipt: {receipt_path(root, ident, 'apply')}")
        return 0
    if is_diagnostic_prompt(raw_prompt):
        receipt = complete_diagnostic(root, ident, task, source)
        print(f"Completed diagnostic prompt package: {ident}")
        print(f"Receipt: {receipt_path(root, ident)}")
        print(f"Diagnosis receipt: {receipt.get('diagnosis_receipt_path', '')}")
        return 0
    receipt = complete_intake_only(root, ident, task, source)
    print(f"Completed prompt package: {ident}")
    print(f"Receipt: {receipt_path(root, ident)}")
    return 0


def status(root: Path, ident: str) -> int:
    ensure_dirs(root)
    found = find_task(root, ident)
    if not found:
        print(f"Task not found: {ident}")
        return 0
    _, path, task = found
    print(json.dumps(task, indent=2, sort_keys=True))
    related = sorted((root / RECEIPTS).glob(f"{ident}_*.json"))
    for receipt in related:
        print(f"Related receipt: {receipt}")
        print(json.dumps(read_json(receipt), indent=2, sort_keys=True))
    return 0


def package_help() -> int:
    print(
        """X Prompt Package example:

TASK: Create X test note

GOAL:
Confirm X can apply a structured prompt package.

X_ACTIONS:
CREATE_FILE data/x_runtime/tmp/x_prompt_apply_test.txt
---CONTENT---
X prompt package apply test.
---END_CONTENT---

RUN_CHECK python scripts/xv7_x.py diagnose --save

SUCCESS:
The test note exists and diagnosis receipt is updated.
"""
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="X Native prompt inbox CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--source", choices=["powershell", "vscode"], required=True)
    sub.add_parser("list")
    run_next_parser = sub.add_parser("run-next")
    run_next_parser.add_argument("--apply", action="store_true")
    status_parser = sub.add_parser("status")
    status_parser.add_argument("task_id")
    preview_parser = sub.add_parser("preview")
    preview_parser.add_argument("task_id")
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("task_id")
    sub.add_parser("package-help")
    args = parser.parse_args(argv)

    root = repo_root()
    if args.command == "submit":
        return submit(root, args.source)
    if args.command == "list":
        return list_tasks(root)
    if args.command == "run-next":
        return run_next(root, apply=args.apply)
    if args.command == "status":
        return status(root, args.task_id)
    if args.command == "preview":
        return preview_task(root, args.task_id)
    if args.command == "apply":
        receipt = apply_task(root, args.task_id)
        print(f"Apply status: {receipt.get('status')}")
        print(f"Apply receipt: {receipt_path(root, args.task_id, 'apply')}")
        if receipt.get("first_error"):
            print(f"First error: {receipt['first_error']}")
        return 0
    if args.command == "package-help":
        return package_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
