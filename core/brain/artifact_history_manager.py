from __future__ import annotations

import html
import re
from typing import Any

from core.brain.artifact_fidelity_manager import ArtifactFidelityManager


class ArtifactHistoryManager:
    """Helpers for extracting current and prior generated artifacts from session state."""

    @staticmethod
    def extract_business_name_from_html(content: str) -> str | None:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", content, flags=re.IGNORECASE | re.DOTALL
        )
        if title_match:
            value = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip()
            if value:
                return value

        h1_match = re.search(
            r"<h1[^>]*>(.*?)</h1>", content, flags=re.IGNORECASE | re.DOTALL
        )
        if h1_match:
            raw = re.sub(r"<[^>]+>", "", h1_match.group(1))
            value = html.unescape(re.sub(r"\s+", " ", raw)).strip()
            if value:
                return value

        return None

    @staticmethod
    def extract_artifact_from_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(metadata, dict):
            return None

        site_bundle = metadata.get("site_bundle")
        if (
            isinstance(site_bundle, dict)
            and site_bundle.get("artifact_type") == "site_bundle"
        ):
            return dict(site_bundle)

        artifacts: list[Any] = []
        code_artifacts = metadata.get("code_artifacts")
        if isinstance(code_artifacts, list):
            artifacts.extend(code_artifacts)

        single = metadata.get("code_artifact")
        if isinstance(single, dict):
            artifacts.append(single)

        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            filename = str(artifact.get("filename", "")).strip()
            content = artifact.get("content")
            if filename and isinstance(content, str) and content.strip():
                return {
                    "type": "code_artifact",
                    "filename": filename,
                    "language": str(artifact.get("language") or "html").strip()
                    or "html",
                    "previewable": bool(artifact.get("previewable", True)),
                    "applied": bool(artifact.get("applied", False)),
                    "content": content,
                    "artifact_id": artifact.get("artifact_id"),
                    "revision_id": artifact.get("revision_id"),
                    "revision_number": artifact.get("revision_number"),
                    "source_prompt": artifact.get("source_prompt"),
                    "prompt_fidelity": artifact.get("prompt_fidelity"),
                    "delivery_mode": artifact.get("delivery_mode"),
                    "sandbox_root": artifact.get("sandbox_root"),
                    "sandbox_project_slug": artifact.get("sandbox_project_slug"),
                    "sandbox_relative_path": artifact.get("sandbox_relative_path"),
                    "sandbox_target_path": artifact.get("sandbox_target_path"),
                    "created_at": artifact.get("created_at"),
                    "message_id": artifact.get("message_id"),
                }

        return None

    @classmethod
    def artifact_history(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []

        if isinstance(session_metadata, dict):
            stored_history = session_metadata.get("artifact_history")
            if isinstance(stored_history, list):
                for index, item in enumerate(stored_history):
                    artifact: dict[str, Any] | None = None
                    if isinstance(item, dict):
                        raw_artifact = item.get("artifact")
                        if isinstance(raw_artifact, dict):
                            artifact = dict(raw_artifact)
                        else:
                            artifact = cls.extract_artifact_from_metadata(item)
                    if artifact is not None:
                        history.append(
                            {
                                "artifact": artifact,
                                "source": "session_metadata.artifact_history",
                                "index": index,
                            }
                        )

        if isinstance(session_messages, list):
            for index, message in enumerate(session_messages):
                if not isinstance(message, dict):
                    continue
                if str(message.get("role", "")).lower() != "assistant":
                    continue
                metadata = message.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                artifact = cls.extract_artifact_from_metadata(metadata)
                if artifact is not None:
                    history.append(
                        {
                            "artifact": artifact,
                            "source": "assistant_message",
                            "index": index,
                        }
                    )

        return history

    @classmethod
    def prompt_fidelity_history_metadata(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        history_names: list[str] = []
        previous_colors: list[str] = []

        for item in cls.artifact_history(session_messages, session_metadata):
            artifact = item.get("artifact") if isinstance(item, dict) else None
            if not isinstance(artifact, dict):
                continue

            fidelity = artifact.get("prompt_fidelity")
            if isinstance(fidelity, dict):
                name = str(fidelity.get("requested_business_name") or "").strip()
                if name:
                    history_names.append(name)
                colors = fidelity.get("requested_colors")
                if isinstance(colors, list):
                    for color in colors:
                        token = str(color or "").strip().lower()
                        if token:
                            previous_colors.append(token)

            prompt = str(artifact.get("source_prompt") or "").strip()
            if prompt:
                extracted = ArtifactFidelityManager.extract_prompt_fidelity_contract(prompt)
                name = str(extracted.get("requested_business_name") or "").strip()
                if name:
                    history_names.append(name)
                for color in extracted.get("requested_colors") or []:
                    token = str(color or "").strip().lower()
                    if token:
                        previous_colors.append(token)

        return {
            "history_business_names": list(dict.fromkeys(history_names)),
            "previous_colors": list(dict.fromkeys(previous_colors)),
        }

    @classmethod
    def latest_assistant_artifact(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        history = cls.artifact_history(session_messages, session_metadata)
        if history:
            return history[-1]["artifact"], "latest session artifact"

        if isinstance(session_metadata, dict):
            last_payload = session_metadata.get("last_assistant_payload")
            if isinstance(last_payload, dict):
                artifact = cls.extract_artifact_from_metadata(last_payload)
                if artifact is not None:
                    return artifact, "previous assistant artifact"

        return None, None
