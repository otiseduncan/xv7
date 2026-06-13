from __future__ import annotations

from core.brain.revision_receipt_manager import RevisionReceiptManager


def test_next_revision_number_defaults_to_one() -> None:
    assert RevisionReceiptManager.next_revision_number(None) == 1
    assert RevisionReceiptManager.next_revision_number({}) == 1


def test_next_revision_number_increments_existing_revision() -> None:
    assert RevisionReceiptManager.next_revision_number({"revision_number": 4}) == 5
    assert RevisionReceiptManager.next_revision_number({"revision_number": "7"}) == 8


def test_next_revision_number_tolerates_invalid_values() -> None:
    assert RevisionReceiptManager.next_revision_number({"revision_number": "bad"}) == 1


def test_has_content_change_compares_exact_content() -> None:
    assert RevisionReceiptManager.has_content_change("old", "new") is True
    assert RevisionReceiptManager.has_content_change("same", "same") is False


def test_build_revision_receipt_prefers_revised_metadata() -> None:
    receipt = RevisionReceiptManager.build_revision_receipt(
        previous_artifact={
            "artifact_id": "artifact-1",
            "filename": "index.html",
            "language": "html",
            "revision_id": "rev-old",
            "revision_number": 2,
        },
        revised_artifact={"filename": "home.html", "language": "html"},
        previous_content="old",
        revised_content="new",
        revision_id="rev-new",
    )

    assert receipt == {
        "artifact_id": "artifact-1",
        "filename": "home.html",
        "language": "html",
        "revision_id": "rev-new",
        "previous_revision_id": "rev-old",
        "revision_number": 3,
        "changed": True,
    }


def test_build_revision_receipt_handles_missing_previous_artifact() -> None:
    receipt = RevisionReceiptManager.build_revision_receipt(
        previous_artifact=None,
        revised_artifact={"artifact_id": "artifact-2", "filename": "index.html"},
        previous_content="",
        revised_content="<html></html>",
        revision_id="rev-new",
    )

    assert receipt["artifact_id"] == "artifact-2"
    assert receipt["filename"] == "index.html"
    assert receipt["previous_revision_id"] is None
    assert receipt["revision_number"] == 1
    assert receipt["changed"] is True


def test_visible_revision_summary_for_changed_artifact() -> None:
    assert RevisionReceiptManager.visible_revision_summary(
        filename="index.html", revision_number=3, changed=True
    ) == "Updated index.html. Revision 3 is ready for review."


def test_visible_revision_summary_for_unchanged_artifact() -> None:
    text = RevisionReceiptManager.visible_revision_summary(
        filename="index.html", revision_number=3, changed=False
    )

    assert "did not alter the artifact content" in text
    assert "Revision 3" in text
