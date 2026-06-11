from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status


@dataclass(frozen=True)
class BridgeSettings:
    token: str
    timeout_seconds: int
    max_output_chars: int
    repo_root: Path


def load_settings() -> BridgeSettings:
    token = os.getenv("XV7_LOCAL_BRIDGE_TOKEN", "xv7-local-bridge-token")
    timeout = int(os.getenv("XV7_LOCAL_BRIDGE_TIMEOUT_SECONDS", "10"))
    max_chars = int(os.getenv("XV7_LOCAL_BRIDGE_MAX_OUTPUT_CHARS", "12000"))
    repo_root = Path(os.getenv("XV7_LOCAL_BRIDGE_REPO_ROOT", str(Path.cwd()))).resolve()
    return BridgeSettings(
        token=token,
        timeout_seconds=max(2, min(timeout, 60)),
        max_output_chars=max(1000, min(max_chars, 200000)),
        repo_root=repo_root,
    )


app = FastAPI(title="xv7-local-bridge")


def _truncate(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    return value[:max_chars], True


def _run_powershell(script: str, settings: BridgeSettings) -> dict[str, Any]:
    cmd = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        script,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.timeout_seconds,
            check=False,
            cwd=str(settings.repo_root),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"scan timed out after {settings.timeout_seconds}s",
            "exit_code": 124,
            "truncated": False,
        }

    stdout, stdout_trunc = _truncate(proc.stdout or "", settings.max_output_chars)
    stderr, stderr_trunc = _truncate(proc.stderr or "", settings.max_output_chars)
    return {
        "ok": proc.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "truncated": stdout_trunc or stderr_trunc,
    }


def _run_cmd(args: list[str], settings: BridgeSettings) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=settings.timeout_seconds,
            check=False,
            cwd=str(settings.repo_root),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"scan timed out after {settings.timeout_seconds}s",
            "exit_code": 124,
            "truncated": False,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"command not found: {args[0]}",
            "exit_code": 127,
            "truncated": False,
        }

    stdout, stdout_trunc = _truncate(proc.stdout or "", settings.max_output_chars)
    stderr, stderr_trunc = _truncate(proc.stderr or "", settings.max_output_chars)
    return {
        "ok": proc.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "truncated": stdout_trunc or stderr_trunc,
    }


def _parse_json_stdout(payload: dict[str, Any]) -> dict[str, Any]:
    stdout = str(payload.get("stdout", "")).strip()
    if not stdout:
        return {}
    try:
        parsed = json.loads(stdout)
        if isinstance(parsed, dict):
            return parsed
        return {"items": parsed}
    except Exception:
        return {"raw": stdout}


def _scan_system(settings: BridgeSettings) -> dict[str, Any]:
    script = """
$ErrorActionPreference = 'SilentlyContinue'
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$bios = Get-CimInstance Win32_BIOS
[pscustomobject]@{
  os_name = $os.Caption
  os_version = $os.Version
  hostname = $env:COMPUTERNAME
  manufacturer = $cs.Manufacturer
  model = $cs.Model
  architecture = $os.OSArchitecture
  user = $env:USERNAME
  total_ram_bytes = [int64]$cs.TotalPhysicalMemory
  free_ram_kb = [int64]$os.FreePhysicalMemory
  uptime_seconds = [int]((Get-Date) - $os.LastBootUpTime).TotalSeconds
  bios = $bios.SMBIOSBIOSVersion
} | ConvertTo-Json -Depth 4 -Compress
"""
    return _run_powershell(script, settings)


def _scan_cpu(settings: BridgeSettings) -> dict[str, Any]:
    script = """
$ErrorActionPreference = 'SilentlyContinue'
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$counter = (Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples | Select-Object -First 1
[pscustomobject]@{
  name = $cpu.Name
  cores = [int]$cpu.NumberOfCores
  logical_processors = [int]$cpu.NumberOfLogicalProcessors
  max_clock_mhz = [int]$cpu.MaxClockSpeed
  current_clock_mhz = [int]$cpu.CurrentClockSpeed
  load_percent = [int]$counter.CookedValue
  temperature_c = $null
} | ConvertTo-Json -Depth 4 -Compress
"""
    return _run_powershell(script, settings)


def _scan_gpu(settings: BridgeSettings) -> dict[str, Any]:
    nvidia = _run_cmd(
        [
            "nvidia-smi",
            "--query-gpu=name,temperature.gpu,utilization.gpu,clocks.current.graphics,memory.used,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ],
        settings,
    )
    if nvidia.get("ok") and str(nvidia.get("stdout", "")).strip():
        rows = []
        for raw in str(nvidia.get("stdout", "")).splitlines():
            parts = [item.strip() for item in raw.split(",")]
            if len(parts) < 7:
                continue
            rows.append(
                {
                    "name": parts[0],
                    "temperature_c": parts[1],
                    "utilization_percent": parts[2],
                    "graphics_clock_mhz": parts[3],
                    "memory_used_mb": parts[4],
                    "memory_total_mb": parts[5],
                    "driver_version": parts[6],
                }
            )
        return {
            "ok": True,
            "stdout": json.dumps({"gpus": rows}),
            "stderr": "",
            "exit_code": 0,
            "truncated": False,
        }

    script = """
$ErrorActionPreference = 'SilentlyContinue'
$gpus = Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM
$gpus | ConvertTo-Json -Depth 4 -Compress
"""
    fallback = _run_powershell(script, settings)
    if not fallback.get("stderr"):
        fallback["stderr"] = "Live GPU temperature/speed unavailable; nvidia-smi not found."
    return fallback


def _scan_disk(settings: BridgeSettings) -> dict[str, Any]:
    script = """
$ErrorActionPreference = 'SilentlyContinue'
$drives = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
  [pscustomobject]@{
    drive = $_.DeviceID
    label = $_.VolumeName
    filesystem = $_.FileSystem
    size_bytes = [int64]$_.Size
    free_bytes = [int64]$_.FreeSpace
    percent_free = if ($_.Size -gt 0) { [math]::Round(($_.FreeSpace / $_.Size) * 100, 2) } else { 0 }
  }
}
[pscustomobject]@{
  disk_count = @($drives).Count
  drives = $drives
} | ConvertTo-Json -Depth 6 -Compress
"""
    return _run_powershell(script, settings)


def _scan_network(settings: BridgeSettings) -> dict[str, Any]:
    script = """
$ErrorActionPreference = 'SilentlyContinue'
$items = Get-NetIPConfiguration | ForEach-Object {
  [pscustomobject]@{
    interface = $_.InterfaceAlias
    ipv4 = ($_.IPv4Address | ForEach-Object { $_.IPAddress })
    gateway = ($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop })
    dns = $_.DNSServer.ServerAddresses
  }
}
$adapters = Get-NetAdapter | Select-Object Name, Status, MacAddress, LinkSpeed
[pscustomobject]@{
  interfaces = $items
  adapters = $adapters
} | ConvertTo-Json -Depth 6 -Compress
"""
    return _run_powershell(script, settings)


def _scan_ports(settings: BridgeSettings) -> dict[str, Any]:
    script = """
$ErrorActionPreference = 'SilentlyContinue'
$ports = Get-NetTCPConnection -State Listen | Select-Object -First 200 LocalAddress, LocalPort, OwningProcess
$withName = $ports | ForEach-Object {
  $procName = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName
  [pscustomobject]@{
    local_address = $_.LocalAddress
    local_port = $_.LocalPort
    pid = $_.OwningProcess
    process = $procName
  }
}
$withName | ConvertTo-Json -Depth 5 -Compress
"""
    return _run_powershell(script, settings)


def _scan_processes(settings: BridgeSettings) -> dict[str, Any]:
    script = """
$ErrorActionPreference = 'SilentlyContinue'
$procs = Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 Name, Id, CPU, PM, WS
$procs | ConvertTo-Json -Depth 4 -Compress
"""
    return _run_powershell(script, settings)


def _scan_services(settings: BridgeSettings) -> dict[str, Any]:
    script = """
$ErrorActionPreference = 'SilentlyContinue'
$running = Get-Service | Where-Object { $_.Status -eq 'Running' } | Select-Object -First 80 Name, DisplayName, StartType, Status
$stoppedAuto = Get-Service | Where-Object { $_.Status -ne 'Running' -and $_.StartType -eq 'Automatic' } | Select-Object -First 40 Name, DisplayName, StartType, Status
[pscustomobject]@{
  running = $running
  stopped_automatic = $stoppedAuto
} | ConvertTo-Json -Depth 6 -Compress
"""
    return _run_powershell(script, settings)


def _scan_docker(settings: BridgeSettings) -> dict[str, Any]:
    version_result = _run_cmd(["docker", "version", "--format", "{{json .}}"], settings)
    ps_result = _run_cmd(["docker", "ps", "--format", "{{json .}}"], settings)
    compose_result = _run_cmd(["docker", "compose", "ps", "--format", "json"], settings)

    available = bool(version_result.get("ok"))
    payload = {
        "docker_available": available,
        "docker_version": str(version_result.get("stdout", "")).strip(),
        "containers": [line for line in str(ps_result.get("stdout", "")).splitlines() if line.strip()],
        "compose": [line for line in str(compose_result.get("stdout", "")).splitlines() if line.strip()],
        "limitation": "" if available else "Docker CLI unavailable on host.",
    }
    return {
        "ok": available,
        "stdout": json.dumps(payload),
        "stderr": "" if available else str(version_result.get("stderr", "Docker CLI unavailable on host.")),
        "exit_code": 0 if available else int(version_result.get("exit_code") or 127),
        "truncated": bool(version_result.get("truncated") or ps_result.get("truncated") or compose_result.get("truncated")),
    }


def _scan_vscode(settings: BridgeSettings) -> dict[str, Any]:
    status_result = _run_cmd(["code", "--status"], settings)
    extensions_result = _run_cmd(["code", "--list-extensions"], settings)

    available = status_result.get("exit_code") != 127
    extensions = [line for line in str(extensions_result.get("stdout", "")).splitlines() if line.strip()]
    payload = {
        "vscode_cli_available": bool(available and status_result.get("ok")),
        "status_excerpt": str(status_result.get("stdout", ""))[:2000],
        "extension_count": len(extensions),
        "extensions_sample": extensions[:20],
        "limitation": "" if available else "VS Code CLI unavailable on host.",
    }
    return {
        "ok": bool(available),
        "stdout": json.dumps(payload),
        "stderr": "" if available else str(status_result.get("stderr", "VS Code CLI unavailable on host.")),
        "exit_code": 0 if available else int(status_result.get("exit_code") or 127),
        "truncated": bool(status_result.get("truncated") or extensions_result.get("truncated")),
    }


SCAN_HANDLERS = {
    "system": _scan_system,
    "cpu": _scan_cpu,
    "gpu": _scan_gpu,
    "disk": _scan_disk,
    "network": _scan_network,
    "ports": _scan_ports,
    "processes": _scan_processes,
    "services": _scan_services,
    "docker": _scan_docker,
    "vscode": _scan_vscode,
}


def _auth(settings: BridgeSettings, x_xv7_bridge_token: str | None = Header(default=None)) -> None:
    if not x_xv7_bridge_token or x_xv7_bridge_token != settings.token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bridge token")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _scan(scan_name: str, settings: BridgeSettings) -> dict[str, Any]:
    handler = SCAN_HANDLERS[scan_name]
    raw = handler(settings)
    parsed = _parse_json_stdout(raw)
    return {
        "status": "success" if raw.get("ok") else "failed",
        "scan": scan_name,
        "exit_code": raw.get("exit_code"),
        "summary": str(raw.get("stderr") or "ok" if raw.get("ok") else "failed"),
        "data": parsed,
        "stderr": raw.get("stderr", ""),
        "truncated": bool(raw.get("truncated")),
    }


@app.post("/scan/system")
def scan_system(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("system", load_settings())


@app.post("/scan/cpu")
def scan_cpu(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("cpu", load_settings())


@app.post("/scan/gpu")
def scan_gpu(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("gpu", load_settings())


@app.post("/scan/disk")
def scan_disk(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("disk", load_settings())


@app.post("/scan/network")
def scan_network(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("network", load_settings())


@app.post("/scan/ports")
def scan_ports(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("ports", load_settings())


@app.post("/scan/processes")
def scan_processes(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("processes", load_settings())


@app.post("/scan/services")
def scan_services(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("services", load_settings())


@app.post("/scan/docker")
def scan_docker(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("docker", load_settings())


@app.post("/scan/vscode")
def scan_vscode(
    _auth_ok: None = Depends(lambda x_xv7_bridge_token=Header(default=None): _auth(load_settings(), x_xv7_bridge_token)),
) -> dict[str, Any]:
    return _scan("vscode", load_settings())
