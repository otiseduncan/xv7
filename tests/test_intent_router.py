from __future__ import annotations

from core.brain import site_bundle as sb
from core.brain.answer_contract import AnswerContract
from core.brain.intent_router import IntentKind, IntentRouter


ROUTING_CASES = [
    "Generate a website for Harry's Hot Dog Cart. Use red, yellow, white, and black.",
    "Build a website for Harry's Hot Dog Cart. Use red, yellow, white, and black.",
    "Create a multi-page website for Riverbend Kayak & Paddle Co with Menu, Specials, About, and Contact.",
    "Revise this site and make the Specials section more premium.",
    "Create a website in the repo and commit it.",
    "Generate a small HTML code artifact for Flow Flowers with filename index.html and previewable true.",
]


def test_intent_router_matches_current_answer_contract_routing_helpers() -> None:
    for prompt in ROUTING_CASES:
        normalized = AnswerContract._normalize(prompt)
        decision = IntentRouter.classify(prompt)

        assert decision.normalized_text == normalized
        assert (
            decision.has_explicit_artifact_intent
            == AnswerContract._has_explicit_artifact_intent(normalized)
        )
        assert (
            decision.is_preview_artifact_request
            == AnswerContract._is_preview_artifact_request(normalized)
        )
        assert (
            decision.is_code_artifact_request
            == AnswerContract.is_code_artifact_request(normalized)
        )
        assert decision.is_site_bundle_request == sb.is_site_bundle_request(normalized)
        assert (
            decision.is_sandbox_build_request
            == AnswerContract._is_sandbox_build_request(normalized)
        )
        assert (
            decision.is_artifact_edit_request
            == AnswerContract._looks_like_artifact_edit(normalized)
        )
        assert (
            decision.is_repo_mutation_build_prompt
            == AnswerContract._is_repo_mutation_build_prompt(normalized)
        )
        assert (
            decision.prioritize_artifact_over_build_guard
            == AnswerContract._prioritize_artifact_over_build_guard(normalized)
        )


def test_intent_router_classifies_command_language_contract() -> None:
    assert (
        IntentRouter.classify("Generate a website for Harry's Hot Dog Cart.").kind
        == IntentKind.CODE_ARTIFACT
    )
    assert (
        IntentRouter.classify("Create a multi-page website for Riverbend Kayak.").kind
        == IntentKind.SITE_BUNDLE
    )
    assert (
        IntentRouter.classify("Build a website for Harry's Hot Dog Cart.").kind
        == IntentKind.SANDBOX_BUILD
    )
    assert (
        IntentRouter.classify("Write a sandbox project for a Vite landing page.").kind
        == IntentKind.SANDBOX_BUILD
    )
    assert (
        IntentRouter.classify("Revise this site and add a Specials section.").kind
        == IntentKind.ARTIFACT_EDIT
    )
    assert (
        IntentRouter.classify("Create a website in the repo and commit it.").kind
        == IntentKind.PROTECTED_REPO_MUTATION
    )
