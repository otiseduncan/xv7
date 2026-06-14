from __future__ import annotations

import pytest

from core.brain.answer_contract import AnswerContract
from core.brain.artifact_fidelity_manager import ArtifactFidelityManager


PROMPT = "generate a small HTML artifact for Soggy Doggy grooming using black yellow and green"

VALID_HTML = """<!doctype html>
<html>
<head>
<title>Soggy Doggy</title>
<style>
:root{--accent:#070707;--accent-2:#facc15;--accent-3:#22c55e;}
body{background:#070707;color:#facc15;}
.button{border-color:#22c55e;}
</style>
</head>
<body>
<h1>Soggy Doggy</h1>
<p>Pet grooming bath trim fur care and paw tidy services.</p>
<p>Requested palette: black yellow green.</p>
</body>
</html>"""


def test_extract_prompt_fidelity_contract() -> None:
    contract = ArtifactFidelityManager.extract_prompt_fidelity_contract(PROMPT)

    assert contract["requested_business_name"] == "Soggy Doggy"
    assert contract["requested_business_type"] == "grooming"
    assert contract["requested_colors"] == ["black", "green", "yellow"]
    assert contract["artifact_intent"] == "small HTML artifact"
    assert contract["source_prompt"] == PROMPT


def test_forbidden_terms_include_stale_businesses_history_and_colors() -> None:
    contract = {
        "requested_business_name": "Tony Tavern",
        "requested_colors": ["black", "yellow"],
    }

    forbidden = ArtifactFidelityManager.prompt_fidelity_forbidden_terms(
        contract=contract,
        metadata={
            "history_business_names": ["Tony Tavern", "Soggy Doggy", "Flow Flowers"],
            "previous_colors": ["purple", "black", "green"],
        },
    )

    assert "Soggy Doggy" in forbidden
    assert "Flow Flowers" in forbidden
    assert "Tony Tavern" not in forbidden
    assert "purple" in forbidden
    assert "green" in forbidden
    assert "black" not in forbidden


def test_validate_accepts_valid_artifact() -> None:
    report = ArtifactFidelityManager.validate_artifact_prompt_fidelity(
        PROMPT,
        VALID_HTML,
        metadata={},
    )

    assert report["passed"] is True
    assert report["status"] == "passed"
    assert report["failures"] == []


@pytest.mark.parametrize(
    ("content", "expected_failure"),
    [
        (f"```html\n{VALID_HTML}\n```", "no_markdown_fences"),
        (
            VALID_HTML.replace("</body>", '<script src="app.js"></script></body>'),
            "no_remote_scripts",
        ),
        (
            VALID_HTML.replace(
                "</body>", '<img src="https://example.test/a.png"></body>'
            ),
            "no_remote_assets",
        ),
        (
            VALID_HTML.replace("Soggy Doggy", "Fresh Paws"),
            "requested_business_name_missing",
        ),
        (
            VALID_HTML.replace(
                "Pet grooming bath trim fur care and paw tidy services.",
                "Friendly appointments.",
            ),
            "requested_business_type_missing",
        ),
        (
            VALID_HTML.replace("green", "blue").replace("#22c55e", "#2563eb"),
            "requested_color_missing:green",
        ),
        (
            VALID_HTML.replace(
                """<style>
:root{--accent:#070707;--accent-2:#facc15;--accent-3:#22c55e;}
body{background:#070707;color:#facc15;}
.button{border-color:#22c55e;}
</style>""",
                """<style>
:root{--accent:#070707;}
body{background:#070707;color:#f5f5f5;}
.button{border-color:#111;}
</style>""",
            ),
            "requested_palette_not_applied_to_css",
        ),
        (
            VALID_HTML.replace("</body>", "<p>Flow Flowers</p></body>"),
            "forbidden_term_present:Flow Flowers",
        ),
    ],
)
def test_validate_rejects_invalid_artifacts(
    content: str, expected_failure: str
) -> None:
    report = ArtifactFidelityManager.validate_artifact_prompt_fidelity(
        PROMPT,
        content,
        metadata={"history_business_names": ["Flow Flowers"]},
    )

    assert report["passed"] is False
    assert expected_failure in report["failures"]


def test_repair_artifact_prompt_fidelity_restores_identity_services_and_colors() -> (
    None
):
    report = ArtifactFidelityManager.validate_artifact_prompt_fidelity(
        PROMPT,
        "<html><head><title>Flow Flowers</title></head><body><h1>Flow Flowers</h1><p>White, purple, and green studio style with clean grooming stations.</p></body></html>",
        metadata={},
    )

    repaired = ArtifactFidelityManager.repair_artifact_prompt_fidelity(
        prompt=PROMPT,
        artifact_content="```html\n"
        "<html><head><title>Flow Flowers</title></head><body><h1>Flow Flowers</h1><p>White, purple, and green studio style with clean grooming stations.</p></body></html>"
        "\n```",
        fidelity_report=report,
    )

    assert "```" not in repaired
    assert "<title>Soggy Doggy</title>" in repaired
    assert "<h1>Soggy Doggy</h1>" in repaired
    assert "Flow Flowers" not in repaired
    assert "Professional pet grooming services" in repaired
    assert 'id="xv7-fidelity-repair"' in repaired
    assert "requested palette: black green yellow" in repaired


def test_repair_inserts_missing_title_and_h1() -> None:
    repaired = ArtifactFidelityManager.repair_artifact_prompt_fidelity(
        prompt=PROMPT,
        artifact_content="<html><head></head><body><p>Pet bath trim fur paw.</p></body></html>",
        fidelity_report={
            "requested_business_name": "Soggy Doggy",
            "requested_business_type": "grooming",
            "requested_colors": [],
        },
    )

    assert "<title>Soggy Doggy</title>" in repaired
    assert "<h1>Soggy Doggy</h1>" in repaired


def test_build_local_artifact_prompt_includes_constraints_and_hints() -> None:
    prompt = ArtifactFidelityManager.build_local_artifact_prompt(
        question=PROMPT,
        filename="index.html",
        language="html",
        previewable=True,
        apply_requested=False,
        business_name="Soggy Doggy",
        style_hints={"colors": ["black", "yellow", "green"], "styles": ["modern"]},
        layout_hints=["hero, services, booking"],
        strict_retry=False,
    )

    assert "filename index.html" in prompt
    assert f"Request summary: {PROMPT}" in prompt
    assert "Business/site name: Soggy Doggy" in prompt
    assert "Requested colors: black, yellow, green" in prompt
    assert "Requested style/font mood: modern" in prompt
    assert "Requested layout/content hints: hero, services, booking" in prompt
    assert "Return ONLY raw source code" in prompt
    assert "No file writes, no repo mutation, no apply behavior." in prompt
    assert (
        "No remote assets, no remote scripts, no remote fonts, no remote images."
        in prompt
    )
    assert "complete single-file document including <!doctype html>" in prompt


def test_answer_contract_fidelity_wrappers_call_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "extract_prompt_fidelity_contract",
        classmethod(lambda cls, question: {"contract": question}),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "color_hex_map",
        staticmethod(lambda: {"black": ["#000"]}),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "service_terms_for_business_type",
        staticmethod(lambda business_type: (f"term:{business_type}",)),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "prompt_fidelity_forbidden_terms",
        classmethod(lambda cls, contract, metadata: ["forbidden"]),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "validate_artifact_prompt_fidelity",
        classmethod(
            lambda cls, prompt, artifact_content, metadata: {"validated": prompt}
        ),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "repair_artifact_prompt_fidelity",
        classmethod(
            lambda cls, prompt, artifact_content, fidelity_report: f"repair:{prompt}"
        ),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "remediation_for_validation_reason",
        staticmethod(lambda reason: f"remediate:{reason}"),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "build_local_artifact_prompt",
        classmethod(lambda cls, **kwargs: f"local:{kwargs['filename']}"),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "strip_markdown_fences",
        staticmethod(lambda content: f"strip:{content}"),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "extract_first_tag_text",
        staticmethod(lambda content, tag: f"text:{tag}"),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "replace_first_tag_text",
        staticmethod(lambda content, tag, replacement: f"replace:{tag}:{replacement}"),
    )
    monkeypatch.setattr(
        ArtifactFidelityManager,
        "insert_before_tag",
        staticmethod(
            lambda content, closing_tag, snippet: f"insert:{closing_tag}:{snippet}"
        ),
    )

    assert AnswerContract._extract_prompt_fidelity_contract("prompt") == {
        "contract": "prompt"
    }
    assert AnswerContract._color_hex_map() == {"black": ["#000"]}
    assert AnswerContract._service_terms_for_business_type("grooming") == (
        "term:grooming",
    )
    assert AnswerContract._prompt_fidelity_forbidden_terms(
        contract={},
        metadata={},
    ) == ["forbidden"]
    assert AnswerContract.validate_artifact_prompt_fidelity("p", "c", {}) == {
        "validated": "p"
    }
    assert (
        AnswerContract._repair_artifact_prompt_fidelity(
            prompt="p",
            artifact_content="c",
            fidelity_report={},
        )
        == "repair:p"
    )
    assert AnswerContract._remediation_for_validation_reason("x") == "remediate:x"
    assert (
        AnswerContract._build_local_artifact_prompt(
            question="q",
            filename="index.html",
            language="html",
            previewable=True,
            apply_requested=False,
            business_name="Biz",
            style_hints={"colors": [], "styles": []},
            layout_hints=[],
            strict_retry=False,
        )
        == "local:index.html"
    )
    assert AnswerContract._strip_markdown_fences("x") == "strip:x"
    assert AnswerContract._extract_first_tag_text("x", "title") == "text:title"
    assert (
        AnswerContract._replace_first_tag_text("x", "h1", "Name") == "replace:h1:Name"
    )
    assert (
        AnswerContract._insert_before_tag("x", "body", "<p />") == "insert:body:<p />"
    )
