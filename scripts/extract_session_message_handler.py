from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main_path = ROOT / "core/main.py"
handler_path = ROOT / "core/api/session_message_handler.py"
main_source = main_path.read_text(encoding="utf-8")
if "bind_add_session_message" in main_source:
    raise SystemExit(0)
marker = "async def add_session_message("
index = main_source.find(marker)
if index < 0:
    raise SystemExit("message handler marker not found")
before = main_source[:index].rstrip() + "\n\n"
handler_source = main_source[index:].rstrip() + "\n"
anchor = "from core.api.session_message_routes import configure_session_message_routes\n"
if anchor not in before:
    raise SystemExit("import anchor not found")
before = before.replace(
    anchor,
    anchor + "from core.api.session_message_handler import bind_add_session_message\n",
    1,
)
main_path.write_text(before + "add_session_message = bind_add_session_message(globals())\n", encoding="utf-8")
module_header = '''# ruff: noqa
# mypy: ignore-errors
from __future__ import annotations

from typing import Any


def bind_add_session_message(shared_globals: dict[str, Any]):
    """Bind the extracted legacy message handler to main.py runtime dependencies."""
    globals().update(shared_globals)
    return add_session_message


'''
handler_path.write_text(module_header + handler_source, encoding="utf-8")
print("session message handler extracted")
