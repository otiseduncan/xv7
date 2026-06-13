from __future__ import annotations

from core.brain.patch_proposal_manager import PatchProposalManager


def _proposal(
    *,
    target_path: str = "generated-sites/demo/index.html",
    content: str = "<html></html>",
    applied: bool = False,
) -> dict[str, object]:
    return {
        "type": "artifact_patch_proposal",
        "proposal_id": "patch-test",
        "target_path": target_path,
        "content": content,
        "applied": applied,
    }


def test_build_unified_diff_for_create_uses_dev_null() -> None:
    diff = PatchProposalManager.build_unified_diff(
        target_path="generated-sites/demo/index.html",
        before_content=None,
        after_content="<html>new</html>\n",
    )

    assert "--- /dev/null" in diff
    assert "+++ b/generated-sites/demo/index.html" in diff
    assert "+<html>new</html>" in diff


def test_build_unified_diff_for_update_uses_repo_paths() -> None:
    diff = PatchProposalManager.build_unified_diff(
        target_path="generated-sites/demo/index.html",
        before_content="old\n",
        after_content="new\n",
    )

    assert "--- a/generated-sites/demo/index.html" in diff
    assert "+++ b/generated-sites/demo/index.html" in diff
    assert "-old" in diff
    assert "+new" in diff


def test_extract_patch_proposal_from_metadata_accepts_valid_payload() -> None:
    proposal = _proposal()
    metadata = {"artifact_patch_proposal": proposal}

    assert (
        PatchProposalManager.extract_patch_proposal_from_metadata(metadata) == proposal
    )


def test_extract_patch_proposal_from_metadata_rejects_invalid_payloads() -> None:
    assert PatchProposalManager.extract_patch_proposal_from_metadata({}) is None
    assert (
        PatchProposalManager.extract_patch_proposal_from_metadata(
            {"artifact_patch_proposal": {"type": "other"}}
        )
        is None
    )
    assert (
        PatchProposalManager.extract_patch_proposal_from_metadata(
            {
                "artifact_patch_proposal": {
                    "type": "artifact_patch_proposal",
                    "content": "x",
                }
            }
        )
        is None
    )
    assert (
        PatchProposalManager.extract_patch_proposal_from_metadata(
            {
                "artifact_patch_proposal": {
                    "type": "artifact_patch_proposal",
                    "target_path": "generated-sites/demo/index.html",
                }
            }
        )
        is None
    )


def test_latest_pending_patch_proposal_prefers_latest_unapplied_message() -> None:
    older = _proposal(target_path="generated-sites/old/index.html")
    applied = _proposal(target_path="generated-sites/applied/index.html", applied=True)
    newer = _proposal(target_path="generated-sites/new/index.html")
    messages = [
        {"role": "assistant", "metadata": {"artifact_patch_proposal": older}},
        {"role": "assistant", "metadata": {"artifact_patch_proposal": applied}},
        {"role": "assistant", "metadata": {"artifact_patch_proposal": newer}},
    ]

    result = PatchProposalManager.latest_pending_patch_proposal(messages, None)

    assert result == newer


def test_latest_pending_patch_proposal_falls_back_to_last_payload() -> None:
    proposal = _proposal(target_path="generated-sites/fallback/index.html")
    metadata = {"last_assistant_payload": {"artifact_patch_proposal": proposal}}

    assert PatchProposalManager.latest_pending_patch_proposal([], metadata) == proposal


def test_latest_applied_patch_proposal_prefers_latest_applied_message() -> None:
    pending = _proposal(target_path="generated-sites/pending/index.html")
    applied = _proposal(target_path="generated-sites/applied/index.html", applied=True)
    messages = [
        {"role": "assistant", "metadata": {"artifact_patch_proposal": pending}},
        {"role": "assistant", "metadata": {"artifact_patch_proposal": applied}},
    ]

    result = PatchProposalManager.latest_applied_patch_proposal(messages, None)

    assert result == applied


def test_applied_patch_with_runtime_fields_adds_receipt_fields() -> None:
    proposal = {
        **_proposal(content="abc", applied=True),
        "validation": {"status": "passed"},
        "source_artifact_id": "artifact-1",
        "applied_at": "2026-01-01T00:00:00+00:00",
    }

    result = PatchProposalManager.applied_patch_with_runtime_fields(
        proposal=proposal,
        verification={"status": "passed"},
        targeted_validation={"status": "skipped"},
        preview_path="generated-sites/demo/index.html",
    )

    assert result["applied"] is True
    assert result["applied_at"] == "2026-01-01T00:00:00+00:00"
    assert result["content_length"] == 3
    assert result["content_sha256"] == PatchProposalManager.content_sha256("abc")
    assert result["validation_status"] == "passed"
    assert result["post_apply_verification"] == {"status": "passed"}
    assert result["targeted_validation"] == {"status": "skipped"}
    assert result["preview_path"] == "generated-sites/demo/index.html"


def test_build_patch_proposal_payload_create_shape() -> None:
    result = PatchProposalManager.build_patch_proposal_payload(
        question="make a patch",
        target_path="generated-sites/demo/index.html",
        content="<html>new</html>\n",
        language="html",
        source_artifact_id="artifact-1",
        before_content=None,
        proposal_id="patch-fixed",
        validation={"status": "passed"},
    )

    assert result["type"] == "artifact_patch_proposal"
    assert result["proposal_id"] == "patch-fixed"
    assert result["operation"] == "create"
    assert result["requires_confirmation"] is True
    assert result["applied"] is False
    assert result["validation"] == {"status": "passed"}
    assert result["source_artifact_id"] == "artifact-1"
    assert "--- /dev/null" in str(result["diff"])


def test_build_patch_proposal_payload_update_shape() -> None:
    result = PatchProposalManager.build_patch_proposal_payload(
        question="update patch",
        target_path="generated-sites/demo/index.html",
        content="new\n",
        language="html",
        before_content="old\n",
        proposal_id="patch-fixed",
    )

    assert result["operation"] == "update"
    assert result["validation"] == {"status": "not_run"}
    assert "--- a/generated-sites/demo/index.html" in str(result["diff"])
