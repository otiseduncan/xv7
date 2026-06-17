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


def test_answer_contract_intent_helpers_delegate_to_intent_router() -> None:
    prompts = [
        *ROUTING_CASES,
        "Use script font for the headline",
        "Keep the layout but make the colors black and gold",
        "Rewrite the homepage headline",
        "What changed?",
        "Undo the last change",
    ]

    for prompt in prompts:
        contract_normalized = AnswerContract._normalize(prompt)
        router_normalized = IntentRouter.normalize(prompt)

        assert contract_normalized == router_normalized
        assert AnswerContract._has_explicit_artifact_intent(
            contract_normalized
        ) == IntentRouter.has_explicit_artifact_intent(router_normalized)
        assert AnswerContract._is_preview_artifact_request(
            contract_normalized
        ) == IntentRouter.is_preview_artifact_request(router_normalized)
        assert AnswerContract.is_code_artifact_request(
            contract_normalized
        ) == IntentRouter.is_code_artifact_request(router_normalized)
        assert AnswerContract._is_sandbox_build_request(
            contract_normalized
        ) == IntentRouter.is_sandbox_build_request(router_normalized)
        assert AnswerContract._is_repo_mutation_build_prompt(
            contract_normalized
        ) == IntentRouter.is_repo_mutation_build_prompt(router_normalized)
        assert AnswerContract._artifact_refinement_mode(
            contract_normalized
        ) == IntentRouter.artifact_refinement_mode(router_normalized)
        assert AnswerContract._looks_like_artifact_edit(
            contract_normalized
        ) == IntentRouter.looks_like_artifact_edit(router_normalized)
        assert AnswerContract._prioritize_artifact_over_build_guard(
            contract_normalized
        ) == IntentRouter.prioritize_artifact_over_build_guard(router_normalized)


def test_intent_router_classifies_command_language_contract() -> None:
    assert (
        IntentRouter.classify(
            "Generate a website preview for Harry's Hot Dog Cart"
        ).kind
        == IntentKind.SITE_BUNDLE
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
        == IntentKind.SANDBOX_BUILD
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


def test_conceptual_website_questions_stay_out_of_artifact_lanes() -> None:
    prompts = [
        "What makes a good website preview?",
        "How should a website preview be evaluated?",
        "Why are my generated websites looking like templates?",
        "What should we improve in the website builder?",
    ]

    for prompt in prompts:
        normalized = IntentRouter.normalize(prompt)
        decision = IntentRouter.classify(prompt)

        assert decision.kind == IntentKind.NORMAL_QUESTION
        assert decision.has_explicit_artifact_intent is False
        assert decision.is_preview_artifact_request is False
        assert decision.is_code_artifact_request is False
        assert decision.is_site_bundle_request is False
        assert decision.is_sandbox_build_request is False
        assert decision.is_artifact_edit_request is False
        assert IntentRouter.is_conceptual_website_question(normalized) is True


def test_preview_and_explicit_export_routing_boundary() -> None:
    assert (
        IntentRouter.classify(
            "generate a preview of a modern one-page website for Harrys Hot Dog Cart"
        ).kind
        == IntentKind.SITE_BUNDLE
    )
    assert (
        IntentRouter.classify("generate a website for Harrys Hot Dog Cart").kind
        == IntentKind.SITE_BUNDLE
    )
    assert (
        IntentRouter.classify("write this to the sandbox").kind
        == IntentKind.SANDBOX_BUILD
    )


def test_website_command_semantics_routing_matrix() -> None:
    preview_cases = [
        "generate a website for Harry's Hot Dog Cart",
        "generate a preview of a website for Harry's Hot Dog Cart",
        "show me a preview of the website",
        "preview a website for Harry's Hot Dog Cart",
    ]
    sandbox_cases = [
        "build me a website for Harry's Hot Dog Cart",
        "write the website to sandbox",
        "create the website files for Harry's Hot Dog Cart",
        "export the approved website",
    ]

    for prompt in preview_cases:
        decision = IntentRouter.classify(prompt)
        assert decision.kind == IntentKind.SITE_BUNDLE
        assert decision.is_site_bundle_request is True
        assert decision.is_sandbox_build_request is False

    for prompt in sandbox_cases:
        decision = IntentRouter.classify(prompt)
        assert decision.kind == IntentKind.SANDBOX_BUILD
        assert decision.is_sandbox_build_request is True


def test_explicit_chat_display_overrides_build_sandbox_routing() -> None:
    decision = IntentRouter.classify(
        "build me a website called pickles and display it in the chat green and yellow colors"
    )

    assert decision.kind == IntentKind.SITE_BUNDLE
    assert decision.is_site_bundle_request is True
    assert decision.is_sandbox_build_request is False


def test_explicit_sandbox_build_phrases_still_route_to_sandbox() -> None:
    assert (
        IntentRouter.classify("build me a website for Harry's Hot Dog Cart").kind
        == IntentKind.SANDBOX_BUILD
    )
    assert (
        IntentRouter.classify("write the website to sandbox").kind
        == IntentKind.SANDBOX_BUILD
    )
    assert (
        IntentRouter.classify("export the approved website").kind
        == IntentKind.SANDBOX_BUILD
    )


def test_fresh_website_build_with_colors_does_not_route_to_refinement() -> None:
    decision = IntentRouter.classify(
        "build a website Smokey Joe's CBD and vape using red grey and black colors"
    )

    assert decision.kind in {IntentKind.SANDBOX_BUILD, IntentKind.SITE_BUNDLE}
    assert decision.kind != IntentKind.ARTIFACT_EDIT
    assert decision.is_artifact_edit_request is False


def test_plain_artifact_generation_routes_to_code_artifact_even_with_user_typo() -> (
    None
):
    for prompt in [
        "generate a artifact Smokey Joe's CBD and vape using red grey and black colors",
        "generate an artifact Smokey Joe's CBD and vape using red grey and black colors",
    ]:
        decision = IntentRouter.classify(prompt)

        assert decision.kind == IntentKind.CODE_ARTIFACT
        assert decision.is_code_artifact_request is True
        assert decision.is_artifact_edit_request is False


def test_true_refinement_without_active_artifact_still_classifies_as_edit() -> None:
    for prompt in [
        "revise this site and make the colors red grey and black",
        "change the website colors to red grey and black",
        "undo the last change",
        "what changed?",
    ]:
        decision = IntentRouter.classify(prompt)
        assert decision.kind == IntentKind.ARTIFACT_EDIT


def test_saved_preview_preference_does_not_override_current_explicit_build_command() -> (
    None
):
    prompt = (
        "Saved preference: preview first, write files only when I say build or export. "
        "Now build me a website for Harry's Hot Dog Cart."
    )

    assert IntentRouter.classify(prompt).kind == IntentKind.SANDBOX_BUILD


def test_operator_project_command_detection_for_verbal_and_slash() -> None:
    assert (
        IntentRouter.is_operator_project_command_request(
            IntentRouter.normalize("initialize the new repository and push to github")
        )
        is True
    )
    assert (
        IntentRouter.is_operator_project_command_request(
            IntentRouter.normalize(
                "finish the github push for X:\\xoduz-sandbox\\earthx-github-proof"
            )
        )
        is True
    )
    assert (
        IntentRouter.is_operator_project_command_request(
            IntentRouter.normalize("/push github")
        )
        is True
    )
    assert (
        IntentRouter.is_operator_project_command_request(
            IntentRouter.normalize("generate a website for Harry's Hot Dogs")
        )
        is False
    )
    assert (
        IntentRouter.is_operator_project_command_request(
            IntentRouter.normalize("create a new repo named github poop project")
        )
        is True
    )
    assert (
        IntentRouter.is_operator_project_command_request(
            IntentRouter.normalize("push to github new repo x push proof")
        )
        is True
    )
