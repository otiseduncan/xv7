from __future__ import annotations

from core.operator.schema import OperatorActionResult


def build_operator_answer(action_name: str, result: OperatorActionResult) -> str:
    if action_name in {"build_task", "patch_plan"}:
        data = result.data if isinstance(result.data, dict) else {}
        goal = str(data.get("goal", "")).strip() or "(missing goal)"
        reason = str(data.get("reason", "")).strip()
        likely_files = data.get("likely_files", [])
        if not isinstance(likely_files, list):
            likely_files = []
        likely_files = [str(item) for item in likely_files if str(item).strip()]
        tests_to_run = data.get("tests_to_run", [])
        if not isinstance(tests_to_run, list):
            tests_to_run = []
        tests_to_run = [str(item) for item in tests_to_run if str(item).strip()]
        risk = str(data.get("risk", "unknown")).strip() or "unknown"
        risk_reason = (
            str(data.get("risk_reason", "No risk notes available.")).strip()
            or "No risk notes available."
        )
        workspace_summary = (
            data.get("workspace_summary", {})
            if isinstance(data.get("workspace_summary", {}), dict)
            else {}
        )
        branch = str(workspace_summary.get("branch", "unknown")).strip() or "unknown"
        dirty_count = int(workspace_summary.get("dirty_file_count", 0) or 0)

        inspect_text = ", ".join(likely_files[:10]) if likely_files else "(none)"
        change_text = ", ".join(likely_files[:10]) if likely_files else "(none)"
        tests_text = ", ".join(tests_to_run[:8]) if tests_to_run else "(none)"
        validation_text = tests_text
        next_step = (
            "prepare a patch payload"
            if bool(data.get("mutation_required", False))
            else "use VS Code/Copilot to implement the plan"
        )

        return (
            "Build Plan\n"
            f"Task summary: {goal}\n"
            f"Reason: {reason or 'No specific scope reason was available.'}\n"
            f"Files/directories inspected or recommended for inspection: {inspect_text}\n"
            f"Likely files to change: {change_text}\n"
            f"Tests to add/update: {tests_text}\n"
            f"Validation commands: {validation_text}\n"
            f"Risk notes: risk={risk}; {risk_reason}; branch={branch}; dirty_file_count={dirty_count}.\n"
            "No files were changed. No tests were run. No commit or push occurred.\n"
            f"Next valid operator step: {next_step} or use VS Code/Copilot to implement the plan."
        )

    if action_name == "docker_compose_ps" and result.status == "failed":
        return (
            "Container status cannot be proven from inside xv7-core because Docker CLI/socket is unavailable. "
            "No action was run beyond the read-only availability check."
        )
    if action_name.startswith("scan_") and result.status == "failed":
        limitation = str(result.data.get("limitation") or "").strip()
        limitation_lower = limitation.lower()
        if (
            "bridge is not running" in limitation_lower
            or "local host scan bridge" in limitation_lower
        ):
            return "I can check that through the local host scan bridge, but the bridge is not running yet."
        if limitation:
            return f"Host scan failed: {limitation}"
        return (
            "Host scan failed. "
            f"Safe detail: {result.stderr_summary or 'no stderr detail available.'}"
        )
    if action_name == "operator_validation_report":
        passed = bool(result.data.get("passed", False))
        commands = result.data.get("selected_commands", [])
        command_count = len(commands) if isinstance(commands, list) else 0
        if passed:
            return (
                f"Validation passed for {command_count} allowlisted command(s). "
                "No files were changed. No commit or push occurred."
            )
        first_failure = str(result.data.get("first_failure_command") or "unknown")
        return (
            f"Validation failed. First failing command: {first_failure}. "
            "No files were changed. No commit or push occurred."
        )
    if action_name == "operator_patch_report":
        changed_files = result.data.get("changed_files", [])
        changed_count = len(changed_files) if isinstance(changed_files, list) else 0
        if result.status == "denied":
            return (
                "Patch request was denied by safety policy. "
                f"Safe detail: {result.stderr_summary or 'no detail available.'} "
                "No commit or push occurred."
            )
        mode = str(result.data.get("mode") or "preview")
        if mode == "preview":
            return (
                f"Patch preview completed for {changed_count} changed file(s). "
                "No files were changed. No commit or push occurred."
            )
        return (
            f"Patch apply completed for {changed_count} changed file(s). "
            "No commit or push occurred."
        )
    if action_name == "operator_commit_report":
        candidate_files = result.data.get("candidate_files", [])
        committed_files = result.data.get("committed_files", [])
        skipped_files = result.data.get("skipped_files", [])
        commit_message = str(result.data.get("commit_message") or "").strip()
        commit_sha = str(result.data.get("commit_sha") or "").strip()
        pushed = bool(result.data.get("pushed", False))
        mode = str(result.data.get("mode") or "preview")
        if result.status == "denied" and result.safety.requires_approval:
            return (
                "Commit/push request requires explicit approval before mutation. "
                "No merge was performed."
            )
        if result.status == "denied":
            return (
                "Commit/push request was blocked by safety policy. "
                f"Safe detail: {result.stderr_summary or 'no detail available.'}"
            )
        if mode == "preview" and result.status == "success":
            return (
                f"Commit/push preview prepared with {len(candidate_files)} candidate file(s), "
                f"{len(skipped_files)} skipped file(s), and commit message '{commit_message}'. "
                "Approval is required before commit or push."
            )
        if result.status == "success":
            return (
                f"Commit workflow completed for {len(committed_files)} file(s); "
                f"commit_sha={commit_sha or 'n/a'}; pushed={str(pushed).lower()}. "
                "No merge was performed."
            )
        return (
            "Commit/push workflow failed. "
            f"Safe detail: {result.stderr_summary or 'no stderr detail available.'}"
        )
    if action_name == "operator_repair_report":
        if result.status == "denied":
            return (
                "Repair cycle was denied by safety policy. "
                f"Safe detail: {result.stderr_summary or 'no detail available.'} "
                "No commit or push occurred."
            )
        if result.status == "failed":
            first_failure = str(result.data.get("first_failure_command") or "unknown")
            return (
                f"Repair cycle did not complete successfully. First failure: {first_failure}. "
                "A concrete approved patch is required when no safe patch is supplied. "
                "No commit or push occurred."
            )
        return (
            "Repair cycle completed. "
            "No commit or push occurred; commit/push still require separate approval."
        )
    if action_name == "operator_github_proof_project":
        if result.status == "success":
            commit_sha = str(result.data.get("commit_sha") or "").strip() or "n/a"
            pushed = bool(result.data.get("pushed", False))
            project_path = str(result.data.get("project_path") or result.target)
            branch = str(result.data.get("branch") or "").strip() or "unknown"
            publish_profile = (
                result.data.get("publish_profile", {})
                if isinstance(result.data.get("publish_profile", {}), dict)
                else {}
            )
            profile_owner = (
                str(publish_profile.get("github_owner") or "").strip() or "unknown"
            )
            profile_source = (
                str(result.data.get("publish_profile_source") or "").strip()
                or "unknown"
            )
            remotes = result.data.get("remotes", [])
            remote_count = len(remotes) if isinstance(remotes, list) else 0
            status_lines = result.data.get("status_lines", [])
            status_count = len(status_lines) if isinstance(status_lines, list) else 0
            return (
                f"Sandbox project workflow completed at {project_path}; "
                f"branch={branch}; commit_sha={commit_sha}; remotes={remote_count}; "
                f"status_entries={status_count}; pushed={str(pushed).lower()}; "
                f"publish_profile_owner={profile_owner}; publish_profile_source={profile_source}."
            )
        if result.status == "pending":
            return (
                "Operator GitHub workflow is staged pending confirmation. "
                f"Detail: {result.stderr_summary or 'confirmation is required.'}"
            )
        failed_command = str(result.data.get("failed_command") or "").strip()
        repo_before = (
            result.data.get("repo_before", {})
            if isinstance(result.data.get("repo_before", {}), dict)
            else {}
        )
        branch = str(repo_before.get("branch") or "").strip() or "unknown"
        remotes = repo_before.get("remotes", [])
        remote_count = len(remotes) if isinstance(remotes, list) else 0
        status_lines = repo_before.get("status_lines", [])
        status_count = len(status_lines) if isinstance(status_lines, list) else 0
        if bool(result.data.get("missing_remote")):
            suggested_name = (
                str(result.data.get("suggested_repo_name") or "").strip()
                or "github-proof-project"
            )
            return (
                "The sandbox project is ready locally, but it has no GitHub remote. "
                f"Tell me the repo target or say create a new GitHub repo named {suggested_name}."
            )
        if bool(result.data.get("gh_missing")):
            return (
                "GitHub CLI is not installed in the runtime. "
                "I can still push using an existing git remote/SSH, or you need to install/configure gh for repo creation."
            )
        if bool(result.data.get("git_identity_missing")):
            return (
                "Git author identity is not configured for this sandbox project. "
                "Set XV7_GIT_USER_NAME and XV7_GIT_USER_EMAIL (or git user.name/user.email) and retry."
            )
        if failed_command:
            return (
                "GitHub proof project workflow failed. "
                f"Failed command: {failed_command}. "
                f"Detail: {result.stderr_summary or 'no stderr detail available.'} "
                f"Repo state: branch={branch}; remotes={remote_count}; status_entries={status_count}."
            )
        return (
            "GitHub proof project workflow failed. "
            f"Detail: {result.stderr_summary or 'no stderr detail available.'} "
            f"Repo state: branch={branch}; remotes={remote_count}; status_entries={status_count}."
        )
    if result.status == "failed":
        return (
            f"Operator action {result.action_name} failed. "
            f"Safe detail: {result.stderr_summary or 'no stderr detail available.'}"
        )
    if result.status == "denied":
        return "The requested operator action was denied by read-only safety policy."

    if action_name in {"repo_status", "operator_status_report"}:
        branch = str(result.data.get("branch", "unknown"))
        clean = bool(result.data.get("clean", False))
        clean_text = "clean" if clean else "not clean"
        sync = str(result.data.get("sync", "unknown"))
        upstream = result.data.get("upstream")
        if upstream:
            return (
                f"Repo is on {branch} tracking {upstream}; "
                f"working tree is {clean_text}; sync={sync}."
            )
        return f"Repo is on {branch}; working tree is {clean_text}; sync={sync}."
    if action_name == "repo_recent_commits":
        commits = result.data.get("commits", [])
        if not commits:
            return "No recent commit lines were returned."
        return "Recent commits:\n" + "\n".join(f"- {item}" for item in commits)
    if action_name == "list_project_files":
        files = result.data.get("files", [])
        listed = files[:20]
        return "Project files (first 20):\n" + "\n".join(f"- {item}" for item in listed)
    if action_name == "read_project_file":
        if result.status == "denied":
            return "Read denied: requested path is outside repo root."
        if result.status == "failed":
            return "File read failed: target file was not found."
        path = str(result.data.get("path", "unknown"))
        content = str(result.data.get("content", "")).strip()
        return f"Read {path}:\n{content}"
    if action_name == "runtime_health":
        health = result.data.get("health", {}) if isinstance(result.data, dict) else {}
        runtime_ok = (
            bool(result.data.get("runtime_status"))
            if isinstance(result.data, dict)
            else False
        )
        checked_from = (
            result.data.get("checked_from", "unknown")
            if isinstance(result.data, dict)
            else "unknown"
        )
        return (
            f"Runtime health check: checked_from={checked_from}; "
            f"health={health.get('status', 'unknown')}; runtime_status_loaded={runtime_ok}."
        )
    if action_name == "docker_compose_ps":
        containers = result.data.get("containers", [])
        if not containers:
            return "No running containers were reported by docker compose ps."
        names = []
        for item in containers[:10]:
            if isinstance(item, dict):
                names.append(str(item.get("Name", "unknown")))
        return "Containers reported by compose: " + ", ".join(names)
    if action_name == "operator_environment":
        git_available = bool(result.data.get("git_available", False))
        docker_cli_available = bool(result.data.get("docker_cli_available", False))
        docker_socket_available = bool(
            result.data.get("docker_socket_available", False)
        )
        return (
            "Operator environment (read-only): "
            f"git_available={git_available}, "
            f"docker_cli_available={docker_cli_available}, "
            f"docker_socket_available={docker_socket_available}."
        )
    if action_name == "scan_system":
        scan = result.data.get("result", {})
        if isinstance(scan, dict):
            os_name = str(scan.get("os_name") or "unknown")
            hostname = str(scan.get("hostname") or "unknown")
            uptime = scan.get("uptime_seconds")
            return (
                f"System info: host={hostname}; os={os_name}; uptime_seconds={uptime}."
            )
        return "Host system scan completed."
    if action_name == "scan_cpu":
        scan = result.data.get("result", {})
        if isinstance(scan, dict):
            name = str(scan.get("name") or "unknown")
            load = scan.get("load_percent")
            speed = scan.get("current_clock_mhz")
            return (
                f"CPU status: {name}; load_percent={load}; current_clock_mhz={speed}."
            )
        return "CPU scan completed."
    if action_name == "scan_gpu":
        scan = result.data.get("result", {})
        if isinstance(scan, dict):
            gpus = scan.get("gpus")
            if isinstance(gpus, list) and gpus:
                first = gpus[0] if isinstance(gpus[0], dict) else {}
                name = str(first.get("name") or "unknown")
                temp = first.get("temperature_c")
                util = first.get("utilization_percent")
                return f"GPU status: {name}; temperature_c={temp}; utilization_percent={util}; gpu_count={len(gpus)}."
        return "GPU scan completed."
    if action_name == "scan_disk":
        scan = result.data.get("result", {})
        if isinstance(scan, dict):
            drives = scan.get("drives")
            if isinstance(drives, list):
                count = len(drives)
                preview = []
                for item in drives[:4]:
                    if isinstance(item, dict):
                        drive = str(item.get("drive") or "?")
                        free_bytes = item.get("free_bytes")
                        preview.append(f"{drive} free_bytes={free_bytes}")
                preview_text = "; ".join(preview)
                return f"Disk status: drives={count}. {preview_text}".strip()
        return "Disk scan completed."
    if action_name == "scan_network":
        return "Network scan completed."
    if action_name == "scan_ports":
        return "Port scan completed."
    if action_name == "scan_processes":
        return "Process scan completed."
    if action_name == "scan_services":
        return "Service scan completed."
    if action_name == "scan_docker":
        return "Docker host scan completed."
    if action_name == "scan_vscode":
        return "VS Code host scan completed."
    if action_name == "logs_summary":
        logs = result.data.get("logs", [])
        if not logs:
            return "No log files found to summarize."
        parts = []
        for item in logs:
            if isinstance(item, dict):
                parts.append(
                    f"{item.get('file', 'unknown')} (lines={item.get('line_count', 0)})"
                )
        return "Log summary: " + "; ".join(parts)
    if action_name == "memory_audit":
        counts = result.data.get("status_counts", {})
        return (
            "Memory audit: "
            f"active={counts.get('active', 0)}, "
            f"deleted={counts.get('deleted', 0)}, "
            f"superseded={counts.get('superseded', 0)}."
        )
    return "Operator action completed."
