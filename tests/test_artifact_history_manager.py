from __future__ import annotations

from core.brain.artifact_history_manager import ArtifactHistoryManager


def _artifact(
    filename: str = "index.html",
    content: str = "<html><head><title>Demo</title></head><body><h1>Demo</h1></body></html>",
    **extra: object,
) -> dict[str, object]:
    return {
        "filename": filename,
        "language": "html",
        "previewable": True,
        "content": content,
        **extra,
    }


def test_extract_business_name_from_html_prefers_title_then_h1() -> None:
    assert (
        ArtifactHistoryManager.extract_business_name_from_html(
            "<html><head><title>Harry&apos;s Hot Dog Cart</title></head>"
            "<body><h1>Other</h1></body></html>"
        )
        == "Harry's Hot Dog Cart"
    )
    assert (
        ArtifactHistoryManager.extract_business_name_from_html(
            "<html><body><h1><span>Tony's Tavern</span></h1></body></html>"
        )
        == "Tony's Tavern"
    )


def test_extract_artifact_from_metadata_prioritizes_site_bundle() -> None:
    bundle = {
        "artifact_type": "site_bundle",
        "files": [{"path": "index.html", "content": "<html></html>"}],
    }
    metadata = {
        "site_bundle": bundle,
        "code_artifact": _artifact(content="<html><body>Single</body></html>"),
    }

    assert ArtifactHistoryManager.extract_artifact_from_metadata(metadata) == bundle


def test_extract_artifact_from_metadata_normalizes_code_artifact() -> None:
    metadata = {
        "code_artifact": _artifact(
            filename="landing.html",
            content="<html><body><h1>Landing</h1></body></html>",
            artifact_id="art-1",
            source_prompt="Generate a website for Landing",
            sandbox_project_slug="landing",
        )
    }

    artifact = ArtifactHistoryManager.extract_artifact_from_metadata(metadata)

    assert artifact is not None
    assert artifact["type"] == "code_artifact"
    assert artifact["filename"] == "landing.html"
    assert artifact["language"] == "html"
    assert artifact["artifact_id"] == "art-1"
    assert artifact["sandbox_project_slug"] == "landing"


def test_artifact_history_reads_metadata_and_assistant_messages() -> None:
    session_metadata = {
        "artifact_history": [
            {"artifact": _artifact(filename="first.html", artifact_id="first")},
        ]
    }
    session_messages = [
        {
            "role": "user",
            "metadata": {"code_artifact": _artifact(filename="ignored.html")},
        },
        {
            "role": "assistant",
            "metadata": {
                "code_artifact": _artifact(filename="second.html", artifact_id="second")
            },
        },
    ]

    history = ArtifactHistoryManager.artifact_history(
        session_messages, session_metadata
    )

    assert [item["artifact"]["filename"] for item in history] == [
        "first.html",
        "second.html",
    ]
    assert [item["source"] for item in history] == [
        "session_metadata.artifact_history",
        "assistant_message",
    ]


def test_latest_assistant_artifact_prefers_history_then_last_payload() -> None:
    session_metadata = {
        "artifact_history": [
            {"artifact": _artifact(filename="first.html")},
        ]
    }
    session_messages = [
        {
            "role": "assistant",
            "metadata": {"code_artifact": _artifact(filename="latest.html")},
        }
    ]

    artifact, source = ArtifactHistoryManager.latest_assistant_artifact(
        session_messages,
        session_metadata,
    )

    assert artifact is not None
    assert artifact["filename"] == "latest.html"
    assert source == "latest session artifact"

    fallback_artifact, fallback_source = (
        ArtifactHistoryManager.latest_assistant_artifact(
            None,
            {
                "last_assistant_payload": {
                    "code_artifact": _artifact(filename="fallback.html")
                }
            },
        )
    )

    assert fallback_artifact is not None
    assert fallback_artifact["filename"] == "fallback.html"
    assert fallback_source == "previous assistant artifact"


def test_prompt_fidelity_history_metadata_dedupes_names_and_colors() -> None:
    session_messages = [
        {
            "role": "assistant",
            "metadata": {
                "code_artifact": _artifact(
                    source_prompt=(
                        "Generate a website for Harry's Hot Dog Cart using red and white"
                    ),
                    prompt_fidelity={
                        "requested_business_name": "Harry's Hot Dog Cart",
                        "requested_colors": ["red", "white", "red"],
                    },
                )
            },
        },
        {
            "role": "assistant",
            "metadata": {
                "code_artifact": _artifact(
                    source_prompt="Create a site for Tony's Tavern using black and gold",
                    prompt_fidelity={
                        "requested_business_name": "Tony's Tavern",
                        "requested_colors": ["black"],
                    },
                )
            },
        },
    ]

    metadata = ArtifactHistoryManager.prompt_fidelity_history_metadata(
        session_messages,
        None,
    )

    assert metadata["history_business_names"] == [
        "Harry's Hot Dog Cart",
        "Tony's Tavern",
    ]
    assert metadata["previous_colors"] == ["red", "white", "black", "gold"]
