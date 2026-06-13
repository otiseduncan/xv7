from __future__ import annotations

from core.brain.commit_proposal_manager import CommitProposalManager, GitStatusEntry


def test_normalize_status_path_unwraps_rename_and_backslashes() -> None:
    assert (
        CommitProposalManager.normalize_status_path(r"old\\path.txt -> generated-sites\\demo\\index.html")
        == "generated-sites/demo/index.html"
    )


def test_parse_status_lines_ignores_short_or_empty_lines() -> None:
    entries = CommitProposalManager.parse_status_lines(
        "M  core/brain/answer_contract.py\n?? generated-sites/demo/index.html\nX\n\n"
    )

    assert entries == [
        GitStatusEntry("M  core/brain/answer_contract.py", "core/brain/answer_contract.py"),
        GitStatusEntry("?? generated-sites/demo/index.html", "generated-sites/demo/index.html"),
    ]


def test_filter_safe_entries_splits_included_and_blocked_paths() -> None:
    entries = [
        GitStatusEntry("M  generated-sites/demo/index.html", "generated-sites/demo/index.html"),
        GitStatusEntry("M  data/brain/private.json", "data/brain/private.json"),
    ]

    included, excluded, change_lines = CommitProposalManager.filter_safe_entries(entries)

    assert included == ["generated-sites/demo/index.html"]
    assert excluded == ["data/brain/private.json"]
    assert change_lines == ["M generated-sites/demo/index.html"]


def test_proposed_commit_message_uses_single_file_stem() -> None:
    assert (
        CommitProposalManager.proposed_commit_message(["generated-sites/demo/index.html"])
        == "chore: update index"
    )
    assert (
        CommitProposalManager.proposed_commit_message(["a.txt", "b.txt"])
        == "chore: local repository changes"
    )


def test_visible_summary_reports_included_and_excluded_files() -> None:
    text = CommitProposalManager.visible_summary(
        "feature/test",
        ["generated-sites/demo/index.html"],
        ["data/brain/private.json"],
    )

    assert "1 file(s)" in text
    assert "feature/test" in text
    assert "Excluded blocked paths: data/brain/private.json" in text


def test_build_status_scan_proposal_matches_answer_contract_payload_shape() -> None:
    proposal = CommitProposalManager.build_status_scan_proposal(
        question="prepare commit",
        branch="code22/split-answer-contract",
        status_output=(
            "M  generated-sites/demo/index.html\n"
            "?? generated-sites/demo/assets/site.css\n"
            "M  data/brain/private.json\n"
        ),
        diff_stat="generated-sites/demo/index.html | 2 ++",
        proposal_id="commit-test",
    )

    assert proposal["type"] == "commit_proposal"
    assert proposal["proposal_id"] == "commit-test"
    assert proposal["question"] == "prepare commit"
    assert proposal["branch"] == "code22/split-answer-contract"
    assert proposal["applied"] is False
    assert proposal["committed"] is False
    assert proposal["push_performed"] is False
    assert proposal["requires_confirmation"] is True
    assert proposal["included_files"] == [
        "generated-sites/demo/index.html",
        "generated-sites/demo/assets/site.css",
    ]
    assert proposal["excluded_files"] == ["data/brain/private.json"]
    assert proposal["change_lines"] == [
        "M generated-sites/demo/index.html",
        "?? generated-sites/demo/assets/site.css",
    ]
    assert proposal["diff_stat"] == "generated-sites/demo/index.html | 2 ++"
    assert proposal["proposed_commit_message"] == "chore: local repository changes"
    assert "No files were changed" in str(proposal["visible_text"])


def test_build_status_scan_proposal_supports_injected_block_policy() -> None:
    proposal = CommitProposalManager.build_status_scan_proposal(
        question="prepare commit",
        branch="branch",
        status_output="M  generated-sites/demo/index.html\nM  other.txt",
        proposal_id="commit-test",
        is_blocked=lambda path: path.endswith("other.txt"),
    )

    assert proposal["included_files"] == ["generated-sites/demo/index.html"]
    assert proposal["excluded_files"] == ["other.txt"]


def test_build_no_git_proposal_preserves_no_git_visible_message() -> None:
    proposal = CommitProposalManager.build_no_git_proposal(
        question="prepare commit", proposal_id="commit-test"
    )

    assert proposal["type"] == "commit_proposal"
    assert proposal["proposal_id"] == "commit-test"
    assert proposal["branch"] == "unknown"
    assert proposal["git_available"] is False
    assert proposal["included_files"] == []
    assert "Git is not available" in str(proposal["visible_text"])
