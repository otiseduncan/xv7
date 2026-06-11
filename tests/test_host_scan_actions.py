from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from core.operator.actions.host_scan import scan_ports


class _Response:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self) -> dict:
        return self._payload


class _Client:
    def __init__(self, response: _Response | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, _url: str, headers: dict[str, str]):
        assert "X-XV7-Bridge-Token" in headers
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def test_scan_ports_reports_bridge_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "core.operator.actions.host_scan.httpx.Client",
        lambda timeout: _Client(error=httpx.ConnectError("connection refused")),
    )

    result = scan_ports(action_id="OP-20260611-0991", repo_root=tmp_path)
    assert result.status == "failed"
    assert "bridge is not running" in result.stderr_summary.lower()
    assert result.data.get("bridge_available") is False


def test_scan_ports_maps_success_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    response = _Response(
        200,
        {
            "status": "success",
            "summary": "ok",
            "data": {"ports": [{"local_port": 3000}]},
            "stderr": "",
            "exit_code": 0,
            "truncated": False,
        },
    )
    monkeypatch.setattr(
        "core.operator.actions.host_scan.httpx.Client",
        lambda timeout: _Client(response=response),
    )

    result = scan_ports(action_id="OP-20260611-0992", repo_root=tmp_path)
    assert result.status == "success"
    assert result.data.get("bridge_available") is True
    assert result.data.get("scan") == "ports"
    assert isinstance(result.data.get("result"), dict)
