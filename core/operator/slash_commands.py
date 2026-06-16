"""Slash command registry for XV7 operator mode.

This module defines all available slash commands, their risk levels,
implementation status, and confirmation requirements.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SlashCommandSpec:
    """Specification for a slash command."""
    slash: str
    category: str
    risk_level: str
    mode: str
    requires_typed_confirmation: bool = False
    confirmation_phrase: str | None = None
    reversible: bool = True
    implemented: bool = True


def build_slash_command_registry() -> dict[str, SlashCommandSpec]:
    """Build the complete slash command registry.
    
    Returns a dictionary mapping slash command names to their specifications.
    """
    return {
        "/scan-system": SlashCommandSpec(
            "/scan-system", "read_only_scan", "low", "read_only"
        ),
        "/scan-cpu": SlashCommandSpec(
            "/scan-cpu", "read_only_scan", "low", "read_only"
        ),
        "/scan-gpu": SlashCommandSpec(
            "/scan-gpu", "read_only_scan", "low", "read_only"
        ),
        "/scan-disk": SlashCommandSpec(
            "/scan-disk", "read_only_scan", "low", "read_only"
        ),
        "/scan-network": SlashCommandSpec(
            "/scan-network", "read_only_scan", "low", "read_only"
        ),
        "/scan-ports": SlashCommandSpec(
            "/scan-ports", "read_only_scan", "low", "read_only"
        ),
        "/scan-processes": SlashCommandSpec(
            "/scan-processes", "read_only_scan", "low", "read_only"
        ),
        "/scan-services": SlashCommandSpec(
            "/scan-services", "read_only_scan", "low", "read_only"
        ),
        "/scan-docker": SlashCommandSpec(
            "/scan-docker", "read_only_scan", "low", "read_only"
        ),
        "/scan-vscode": SlashCommandSpec(
            "/scan-vscode", "read_only_scan", "low", "read_only"
        ),
        "/scan-repo": SlashCommandSpec(
            "/scan-repo", "read_only_scan", "low", "read_only"
        ),
        "/list-disk": SlashCommandSpec(
            "/list-disk", "read_only_scan", "low", "read_only"
        ),
        "/list-disks": SlashCommandSpec(
            "/list-disks", "read_only_scan", "low", "read_only"
        ),
        "/list-drives": SlashCommandSpec(
            "/list-drives", "read_only_scan", "low", "read_only"
        ),
        "/list-files": SlashCommandSpec(
            "/list-files", "read_only_scan", "low", "read_only"
        ),
        "/read-file": SlashCommandSpec(
            "/read-file", "read_only_scan", "low", "read_only"
        ),
        "/search-files": SlashCommandSpec(
            "/search-files", "read_only_scan", "low", "read_only"
        ),
        "/run-tests": SlashCommandSpec(
            "/run-tests", "read_only_scan", "low", "read_only"
        ),
        "/build-task": SlashCommandSpec(
            "/build-task", "planning", "low", "operator"
        ),
        "/build": SlashCommandSpec(
            "/build", "project_workflow", "medium", "operator"
        ),
        "/export": SlashCommandSpec(
            "/export", "project_workflow", "medium", "operator"
        ),
        "/write": SlashCommandSpec(
            "/write", "project_workflow", "medium", "operator"
        ),
        "/commit": SlashCommandSpec(
            "/commit", "git_mutation", "medium", "operator"
        ),
        "/push": SlashCommandSpec(
            "/push", "git_mutation", "destructive", "operator"
        ),
        "/github": SlashCommandSpec(
            "/github", "git_mutation", "destructive", "operator"
        ),
        "/publish": SlashCommandSpec(
            "/publish", "git_mutation", "destructive", "operator"
        ),
        "/vscode-open-workspace": SlashCommandSpec(
            "/vscode-open-workspace",
            "vscode_read_only",
            "low",
            "read_only",
            implemented=False,
        ),
        "/vscode-open-file": SlashCommandSpec(
            "/vscode-open-file",
            "vscode_read_only",
            "low",
            "read_only",
            implemented=False,
        ),
        "/vscode-search": SlashCommandSpec(
            "/vscode-search",
            "vscode_read_only",
            "low",
            "read_only",
            implemented=False,
        ),
        "/vscode-diagnostics": SlashCommandSpec(
            "/vscode-diagnostics",
            "vscode_read_only",
            "low",
            "read_only",
            implemented=False,
        ),
        "/delete-file": SlashCommandSpec(
            "/delete-file", "mutation", "destructive", "operator"
        ),
        "/rename-file": SlashCommandSpec(
            "/rename-file", "mutation", "medium", "operator"
        ),
        "/move-file": SlashCommandSpec(
            "/move-file", "mutation", "medium", "operator", implemented=False
        ),
        "/copy-file": SlashCommandSpec(
            "/copy-file", "mutation", "medium", "operator", implemented=False
        ),
        "/write-file": SlashCommandSpec(
            "/write-file", "mutation", "medium", "operator"
        ),
        "/append-file": SlashCommandSpec(
            "/append-file", "mutation", "medium", "operator"
        ),
        "/create-folder": SlashCommandSpec(
            "/create-folder", "mutation", "medium", "operator"
        ),
        "/delete-folder": SlashCommandSpec(
            "/delete-folder",
            "mutation",
            "destructive",
            "operator",
            implemented=False,
        ),
        "/apply-patch": SlashCommandSpec(
            "/apply-patch", "mutation", "medium", "operator"
        ),
        "/restart-container": SlashCommandSpec(
            "/restart-container", "runtime_mutation", "medium", "operator"
        ),
        "/stop-container": SlashCommandSpec(
            "/stop-container",
            "runtime_mutation",
            "destructive",
            "operator",
            implemented=False,
        ),
        "/start-container": SlashCommandSpec(
            "/start-container",
            "runtime_mutation",
            "medium",
            "operator",
            implemented=False,
        ),
        "/rebuild-container": SlashCommandSpec(
            "/rebuild-container",
            "runtime_mutation",
            "destructive",
            "operator",
            implemented=False,
        ),
        "/restart-service": SlashCommandSpec(
            "/restart-service",
            "runtime_mutation",
            "destructive",
            "operator",
            implemented=False,
        ),
        "/kill-process": SlashCommandSpec(
            "/kill-process",
            "runtime_mutation",
            "destructive",
            "operator",
            implemented=False,
        ),
        "/git-add": SlashCommandSpec(
            "/git-add", "git_mutation", "medium", "operator", implemented=False
        ),
        "/git-commit": SlashCommandSpec(
            "/git-commit", "git_mutation", "medium", "operator", implemented=False
        ),
        "/git-push": SlashCommandSpec(
            "/git-push",
            "git_mutation",
            "destructive",
            "operator",
            implemented=False,
        ),
        "/git-stash": SlashCommandSpec(
            "/git-stash", "git_mutation", "medium", "operator", implemented=False
        ),
        "/git-restore": SlashCommandSpec(
            "/git-restore",
            "git_mutation",
            "destructive",
            "operator",
            implemented=False,
        ),
        "/vscode-apply-patch": SlashCommandSpec(
            "/vscode-apply-patch",
            "vscode_mutation",
            "medium",
            "operator",
            implemented=False,
        ),
        "/vscode-write-file": SlashCommandSpec(
            "/vscode-write-file",
            "vscode_mutation",
            "medium",
            "operator",
            implemented=False,
        ),
        "/vscode-create-file": SlashCommandSpec(
            "/vscode-create-file",
            "vscode_mutation",
            "medium",
            "operator",
            implemented=False,
        ),
        "/format-drive": SlashCommandSpec(
            "/format-drive",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="FORMAT {target}",
            reversible=False,
            implemented=False,
        ),
        "/partition-info": SlashCommandSpec(
            "/partition-info",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="PARTITION INFO",
            reversible=False,
            implemented=False,
        ),
        "/git-reset-hard": SlashCommandSpec(
            "/git-reset-hard",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="RESET HARD",
            reversible=False,
            implemented=False,
        ),
        "/git-clean": SlashCommandSpec(
            "/git-clean",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="GIT CLEAN",
            reversible=False,
            implemented=False,
        ),
        "/delete-folder-recursive": SlashCommandSpec(
            "/delete-folder-recursive",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="DELETE {target}",
            reversible=False,
            implemented=False,
        ),
        "/stop-service": SlashCommandSpec(
            "/stop-service",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="STOP SERVICE",
            reversible=False,
            implemented=False,
        ),
        "/start-service": SlashCommandSpec(
            "/start-service",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="START SERVICE",
            reversible=False,
            implemented=False,
        ),
        "/change-firewall-rule": SlashCommandSpec(
            "/change-firewall-rule",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="CHANGE FIREWALL",
            reversible=False,
            implemented=False,
        ),
        "/registry-edit": SlashCommandSpec(
            "/registry-edit",
            "high_risk",
            "high",
            "operator",
            requires_typed_confirmation=True,
            confirmation_phrase="REGISTRY EDIT",
            reversible=False,
            implemented=False,
        ),
    }


def get_implemented_read_only_tools() -> list[str]:
    """Get list of implemented read-only tools."""
    registry = build_slash_command_registry()
    return [
        slash
        for slash, spec in registry.items()
        if spec.mode == "read_only" and spec.implemented
    ]


def get_implemented_operator_tools() -> list[str]:
    """Get list of implemented operator (mutation) tools."""
    registry = build_slash_command_registry()
    return [
        slash
        for slash, spec in registry.items()
        if spec.mode == "operator" and spec.implemented
    ]


def get_stubbed_roadmap_tools() -> list[str]:
    """Get list of stubbed roadmap tools (declared but not implemented)."""
    registry = build_slash_command_registry()
    return [
        slash
        for slash, spec in registry.items()
        if not spec.implemented
    ]


def get_tool_capability_summary() -> dict[str, Any]:
    """Get a summary of current tool capabilities and implementation status."""
    registry = build_slash_command_registry()
    
    read_only_impl = [s for s, spec in registry.items() if spec.mode == "read_only" and spec.implemented]
    read_only_stub = [s for s, spec in registry.items() if spec.mode == "read_only" and not spec.implemented]
    operator_impl = [s for s, spec in registry.items() if spec.mode == "operator" and spec.implemented]
    operator_stub = [s for s, spec in registry.items() if spec.mode == "operator" and not spec.implemented]
    
    return {
        "implemented_read_only_tools": sorted(read_only_impl),
        "stubbed_read_only_tools": sorted(read_only_stub),
        "implemented_operator_tools": sorted(operator_impl),
        "stubbed_operator_tools": sorted(operator_stub),
        "total_implemented": len(read_only_impl) + len(operator_impl),
        "total_stubbed": len(read_only_stub) + len(operator_stub),
    }
