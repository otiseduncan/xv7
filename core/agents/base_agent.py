"""Base async Ollama agent bridge for xv7 orchestration."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import httpx

try:
    import yaml
except ImportError:  # pragma: no cover - handled at runtime if unavailable
    yaml = None

from core.runtime.schemas import ConversationMessage, SessionState


class BaseAgent:
