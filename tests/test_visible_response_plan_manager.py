import json

from core.brain.visible_response_plan_manager import VisibleResponsePlanManager


def test_successful_artifact_response_plan() -> None:
    payload = VisibleResponsePlanManager.build_plan(
        action_name="created",
        artifact_type="website bundle",
        project_name="Harry's Hot Dog Cart",
        created_files=["index.html", "assets\\css\\styles.css"],
        changed_files=["README.md"],
        local_gate_status="passed",
        ci_gate_status="not_required",
    )

    assert payload["summary_lines"] == [
        "Action: created",
        "Artifact: website bundle",
        "Project: Harry's Hot Dog Cart",
    ]
    assert payload["created_files"] == ["index.html", "assets/css/styles.css"]
    assert payload["changed_files"] == ["README.md"]
    assert payload["gate_status"] == {"local": "passed", "ci": "not_required"}
    assert payload["ready_for_user"] is True


def test_failed_local_gate_keeps_not_ready() -> None:
    payload = VisibleResponsePlanManager.build_plan(
        action_name="created",
        local_gate_status="failed",
        ci_gate_status="not_required",
    )

    assert payload["ready_for_user"] is False
    assert payload["gate_status"]["local"] == "failed"


def test_pending_ci_keeps_not_ready() -> None:
    payload = VisibleResponsePlanManager.build_plan(
        action_name="created",
        local_gate_status="passed",
        ci_gate_status="pending",
    )

    assert payload["ready_for_user"] is False
    assert payload["gate_status"]["ci"] == "pending"


def test_file_list_dedupe_preserves_order() -> None:
    payload = VisibleResponsePlanManager.build_plan(
        created_files=["index.html", "about.html", "index.html"],
        changed_files=["app.py", "app.py", "tests/test_app.py"],
    )

    assert payload["created_files"] == ["index.html", "about.html"]
    assert payload["changed_files"] == ["app.py", "tests/test_app.py"]


def test_slash_normalization() -> None:
    payload = VisibleResponsePlanManager.build_plan(
        created_files=[r"pages\menu.html", r"assets\images\hero.png"]
    )

    assert payload["created_files"] == [
        "pages/menu.html",
        "assets/images/hero.png",
    ]


def test_warning_dedupe() -> None:
    payload = VisibleResponsePlanManager.build_plan(
        warnings=["CI pending", "CI pending", "Review actions"]
    )

    assert payload["warnings"] == ["CI pending", "Review actions"]


def test_blank_line_omission() -> None:
    payload = VisibleResponsePlanManager.build_plan(
        action_name=" ",
        artifact_type="site",
        project_name="",
        warnings=["", "  ", "real warning"],
        next_actions=["", "verify Actions"],
    )

    assert payload["summary_lines"] == ["Artifact: site"]
    assert payload["warnings"] == ["real warning"]
    assert payload["next_actions"] == ["verify Actions"]


def test_json_safe_payload() -> None:
    payload = VisibleResponsePlanManager.build_plan(
        action_name="created",
        artifact_type="website",
        project_name="Harry's Hot Dog Cart",
        created_files=["index.html"],
        warnings=["none"],
        next_actions=["verify CI"],
        local_gate_status="passed",
        ci_gate_status="passed",
    )

    assert json.loads(json.dumps(payload)) == payload
