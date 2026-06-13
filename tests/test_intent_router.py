from __future__ import annotations

from core.brain import site_bundle as sb
from core.brain.answer_contract import AnswerContract
from core.brain.intent_router import IntentKind, IntentRouter


ROUTING_CASES = [
    "Generate a website preview for Harry's Hot Dog Cart",
    "Build me a website for another business",
    "Create a HTML artifact Tony's Tavern and biker bar using black orange and yellow as the colors",
    "Create a 5 page website for Tony's Tavern biker bar using black orange and yellow",
    "Revise this site and make the colors black and gold",
    "Create a website in the repo and commit it",
    "Write this to the repo",
    "Generate files for a Vite frontend project",
    "Show me a preview of this landing page",
]


def test_intent_router_matches_current_answer_contract_routing_helpers() -> None:
    for prompt in ROUTING_CASES:
        normalized = AnswerContract._normalize(prompt)
        decision = IntentRouter.classify(prompt)

        assert decision.normalized_question == normalized
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
        IntentRouter.classify(
            "Generate a website preview for Harry's Hot Dog Cart"
        ).kind
        == IntentKind.CODE_ARTIFACT
    )
    assert (
        IntentRouter.classify("Build me a website for another business").kind
        == IntentKind.SANDBOX_BUILD
    )
    assert (
        IntentRouter.classify(
            "Create a HTML artifact Tony's Tavern and biker bar using black orange and yellow as the colors"
        ).kind
        == IntentKind.CODE_ARTIFACT
    )
    assert (
        IntentRouter.classify(
            "Create a 5 page website for Tony's Tavern biker bar using black orange and yellow"
        ).kind
        == IntentKind.SITE_BUNDLE
    )
    assert (
        IntentRouter.classify(
            "Revise this site and make the colors black and gold"
        ).kind
        == IntentKind.ARTIFACT_EDIT
    )
    assert (
        IntentRouter.classify("Create a website in the repo and commit it").kind
        == IntentKind.PROTECTED_REPO_MUTATION
    )
    assert (
        IntentRouter.classify("Write this to the repo").kind
        == IntentKind.PROTECTED_REPO_MUTATION
    )
    assert (
        IntentRouter.classify("Generate files for a Vite frontend project").kind
        == IntentKind.SANDBOX_BUILD
    )
    assert (
        IntentRouter.classify("Show me a preview of this landing page").kind
        == IntentKind.CODE_ARTIFACT
    )
    assert (
        IntentRouter.classify("What verified status is loaded?").kind
        == IntentKind.NORMAL_QUESTION
    )
