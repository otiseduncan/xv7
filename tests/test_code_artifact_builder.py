from __future__ import annotations

import pytest

from core.brain.answer_contract import AnswerContract
from core.brain.code_artifact_builder import CodeArtifactBuilder


@pytest.mark.parametrize(
    ("question", "language"),
    [
        ("generate a small artifact", "html"),
        ("generate css", "css"),
        ("generate javascript", "javascript"),
        ("generate js", "javascript"),
        ("generate typescript", "typescript"),
        ("generate ts", "typescript"),
        ("generate python", "python"),
    ],
)
def test_language_detection(question: str, language: str) -> None:
    assert CodeArtifactBuilder.code_artifact_language(question) == language


@pytest.mark.parametrize(
    ("language", "filename"),
    [
        ("html", "index.html"),
        ("css", "styles.css"),
        ("javascript", "app.js"),
        ("typescript", "app.ts"),
        ("python", "main.py"),
    ],
)
def test_filename_defaults(language: str, filename: str) -> None:
    assert CodeArtifactBuilder.code_artifact_filename(language) == filename


def test_requested_filename_extraction() -> None:
    assert (
        CodeArtifactBuilder.extract_requested_filename(
            "Generate HTML filename=landing.html",
            "html",
        )
        == "landing.html"
    )
    assert (
        CodeArtifactBuilder.extract_requested_filename("Generate HTML", "html")
        == "index.html"
    )


@pytest.mark.parametrize(
    ("question", "language", "previewable"),
    [
        ("Generate HTML previewable=true", "html", True),
        ("Generate HTML previewable=false", "html", False),
        ("Generate HTML", "html", True),
        ("Generate CSS", "css", False),
    ],
)
def test_previewable_extraction(
    question: str, language: str, previewable: bool
) -> None:
    assert (
        CodeArtifactBuilder.extract_requested_previewable(question, language)
        is previewable
    )


@pytest.mark.parametrize(
    ("question", "apply_requested"),
    [
        ("Generate an artifact and do not apply it", False),
        ("Generate an artifact and apply it to the repo", True),
        ("Generate a normal artifact", False),
    ],
)
def test_apply_intent(question: str, apply_requested: bool) -> None:
    assert CodeArtifactBuilder.extract_apply_intent(question) is apply_requested


@pytest.mark.parametrize(
    ("question", "name"),
    [
        ("Generate a website preview for Harry's Hot Dog Cart", "Harry's Hot Dog Cart"),
        (
            "Create a HTML artifact Tony's Tavern and biker bar using black orange and yellow as the colors",
            "Tony's Tavern",
        ),
        ('Generate a website for "Riverbend Kayak"', "Riverbend Kayak"),
    ],
)
def test_business_name_extraction(question: str, name: str) -> None:
    assert CodeArtifactBuilder.extract_artifact_name(question) == name


@pytest.mark.parametrize(
    ("question", "name", "category"),
    [
        ("website for Harry's Hot Dog Cart", "Harry's Hot Dog Cart", "hot_dog_cart"),
        ("artifact Tony's Tavern and biker bar", "Tony's Tavern", "biker_bar"),
        ("site for Paws grooming", "Paws", "grooming"),
        ("site for Flow florist", "Flow", "florist"),
        ("site for Mirror detailing", "Mirror", "detailing"),
        ("site for KeyPro locksmith", "KeyPro", "locksmith"),
        ("site for Riverbend", "Riverbend", "generic"),
    ],
)
def test_business_category(question: str, name: str, category: str) -> None:
    assert CodeArtifactBuilder.artifact_business_category(question, name) == category


def test_style_hints_extract_colors_and_styles() -> None:
    hints = CodeArtifactBuilder.extract_style_hints(
        "Use black orange #ffcc00 with a modern neon bold style"
    )

    assert hints["colors"] == ["black", "orange", "#ffcc00"]
    assert hints["styles"] == ["bold", "modern", "neon"]


def test_default_content_for_core_languages() -> None:
    html_content = CodeArtifactBuilder.default_code_artifact_content(
        "index.html",
        "html",
        "Generate a website preview for Harry's Hot Dog Cart",
    )
    assert "<!doctype html>" in html_content
    assert "<html" in html_content
    assert "Harry's Hot Dog Cart" in html_content

    assert (
        CodeArtifactBuilder.default_code_artifact_content(
            "styles.css",
            "css",
            "Generate CSS",
        )
        == """body {
    margin: 0;
    font-family: system-ui, sans-serif;
}
"""
    )
    assert 'const brand = "Harry' in CodeArtifactBuilder.default_code_artifact_content(
        "app.js",
        "javascript",
        "Generate JavaScript for Harry's Hot Dog Cart",
    )
    assert (
        'const brand: string = "Harry'
        in CodeArtifactBuilder.default_code_artifact_content(
            "app.ts",
            "typescript",
            "Generate TypeScript for Harry's Hot Dog Cart",
        )
    )
    assert 'print("Harry' in CodeArtifactBuilder.default_code_artifact_content(
        "main.py",
        "python",
        "Generate Python for Harry's Hot Dog Cart",
    )


def test_answer_contract_wrappers_match_code_artifact_builder() -> None:
    prompt = (
        "Create a HTML artifact Tony's Tavern and biker bar using black orange and yellow as the colors "
        "filename=landing.html previewable=true"
    )
    normalized = AnswerContract._normalize(prompt)
    language = "html"

    assert AnswerContract._code_artifact_language(
        normalized
    ) == CodeArtifactBuilder.code_artifact_language(normalized)
    assert AnswerContract._code_artifact_filename(
        language
    ) == CodeArtifactBuilder.code_artifact_filename(language)
    assert AnswerContract._clean_artifact_label(
        " Tony's Tavern. "
    ) == CodeArtifactBuilder.clean_artifact_label(" Tony's Tavern. ")
    assert AnswerContract._extract_artifact_name(
        prompt
    ) == CodeArtifactBuilder.extract_artifact_name(prompt)
    assert AnswerContract._artifact_business_category(
        prompt, "Tony's Tavern"
    ) == CodeArtifactBuilder.artifact_business_category(prompt, "Tony's Tavern")
    assert AnswerContract._artifact_style_profile(
        prompt, "biker_bar"
    ) == CodeArtifactBuilder.artifact_style_profile(prompt, "biker_bar")
    assert AnswerContract._format_business_name(
        "", "Fallback"
    ) == CodeArtifactBuilder.format_business_name("", "Fallback")
    assert AnswerContract._build_business_site_template(
        prompt
    ) == CodeArtifactBuilder.build_business_site_template(prompt)
    assert AnswerContract._default_code_artifact_content(
        "index.html", language, prompt
    ) == CodeArtifactBuilder.default_code_artifact_content(
        "index.html", language, prompt
    )
    assert AnswerContract._extract_requested_filename(
        prompt, language
    ) == CodeArtifactBuilder.extract_requested_filename(prompt, language)
    assert AnswerContract._extract_requested_previewable(
        prompt, language
    ) == CodeArtifactBuilder.extract_requested_previewable(prompt, language)
    assert AnswerContract._extract_apply_intent(
        prompt
    ) == CodeArtifactBuilder.extract_apply_intent(prompt)
    assert AnswerContract._extract_style_hints(
        prompt
    ) == CodeArtifactBuilder.extract_style_hints(prompt)
    assert AnswerContract._extract_layout_hints(
        prompt
    ) == CodeArtifactBuilder.extract_layout_hints(prompt)
    assert AnswerContract._artifact_intent_label(
        prompt
    ) == CodeArtifactBuilder.artifact_intent_label(prompt)
