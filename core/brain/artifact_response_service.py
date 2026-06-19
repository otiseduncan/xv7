from __future__ import annotations

import re
from typing import Any

from core.brain import site_bundle as sb
from core.brain.artifact_response_flows import (
    ArtifactResponseCommitFlow,
    ArtifactResponsePatchFlow,
)
from core.brain.intent_router import IntentRouter
from core.brain.sandbox_writer import SandboxWriteManager
from core.runtime.model_registry import (
    configured_ollama_base_url_candidates,
    resolve_model_for_runtime_role,
)


class ArtifactResponseService:
    """Builds artifact-lane responses while preserving AnswerContract behavior."""

    @staticmethod
    async def build_code_artifact_response(
        contract: Any,
        question: str,
        *,
        session_messages: list[Any] | None = None,
        session_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized = contract._normalize(question)
        memory_hints = contract._session_memory_hints(session_metadata or {})
        artifact_history = contract._artifact_history(
            session_messages,
            session_metadata,
        )
        latest_artifact = artifact_history[-1]["artifact"] if artifact_history else None
        source_artifact_label = (
            "latest session artifact" if latest_artifact is not None else None
        )
        is_generation = contract.is_code_artifact_request(normalized)
        is_site_bundle_generation = (
            sb.is_site_bundle_request(normalized)
            or IntentRouter.is_explicit_chat_site_display_request(normalized)
        )
        is_sandbox_build = contract._is_sandbox_build_request(normalized)
        has_artifact_edit_intent = contract._looks_like_artifact_edit(normalized)
        has_explicit_artifact_generation_language = bool(
            contract.EXPLICIT_ARTIFACT_INTENT_PATTERN.search(normalized)
        )
        if (
            latest_artifact is not None
            and has_artifact_edit_intent
            and not has_explicit_artifact_generation_language
        ):
            # Active-artifact edit prompts may still mention "html"/"css" but should stay in revision flow.
            is_generation = False
            is_site_bundle_generation = False
        is_patch_proposal_request = contract._is_patch_proposal_request(normalized)
        is_patch_apply_request = contract._is_patch_apply_request(normalized)
        is_post_apply_verify_request = contract._is_post_apply_verify_request(
            normalized
        )
        is_post_apply_preview_request = contract._is_post_apply_preview_request(
            normalized
        )
        is_post_apply_targeted_validation_request = (
            contract._is_post_apply_targeted_validation_request(normalized)
        )
        is_post_apply_full_test_guard_request = (
            contract._is_post_apply_full_test_guard_request(normalized)
        )
        if memory_hints.get("preview_first") and is_site_bundle_generation:
            is_sandbox_build = True
            is_site_bundle_generation = False
        refinement_mode = (
            contract._artifact_refinement_mode(normalized)
            if (not is_patch_proposal_request and has_artifact_edit_intent)
            else None
        )
        is_refinement_request = (
            latest_artifact is not None
            and refinement_mode is not None
            and not contract.SMS_EXPLICIT_SEND_PATTERN.search(normalized)
            and not is_generation
            and not is_site_bundle_generation
        )
        is_commit_proposal_request = contract._is_commit_proposal_request(normalized)
        is_commit_approval_request = contract._is_commit_approval_request(normalized)
        allow_commit_lane = (
            is_commit_proposal_request or is_commit_approval_request
        ) and not (
            is_generation
            or is_site_bundle_generation
            or is_refinement_request
            or contract._looks_like_artifact_edit(normalized)
        )

        patch_flow_response = ArtifactResponsePatchFlow.handle_patch_flow(
            contract=contract,
            normalized=normalized,
            latest_artifact=latest_artifact,
            source_artifact_label=source_artifact_label,
            session_messages=session_messages,
            session_metadata=session_metadata,
            is_patch_proposal_request=is_patch_proposal_request,
            is_patch_apply_request=is_patch_apply_request,
            is_post_apply_verify_request=is_post_apply_verify_request,
            is_post_apply_preview_request=is_post_apply_preview_request,
            is_post_apply_targeted_validation_request=is_post_apply_targeted_validation_request,
        )
        if patch_flow_response is not None:
            return patch_flow_response
        commit_flow_response = ArtifactResponseCommitFlow.handle_commit_flow(
            contract=contract,
            question=question,
            normalized=normalized,
            latest_artifact=latest_artifact,
            source_artifact_label=source_artifact_label,
            session_messages=session_messages,
            session_metadata=session_metadata,
            is_post_apply_full_test_guard_request=is_post_apply_full_test_guard_request,
            is_post_apply_verify_request=is_post_apply_verify_request,
            is_post_apply_preview_request=is_post_apply_preview_request,
            is_post_apply_targeted_validation_request=is_post_apply_targeted_validation_request,
            is_generation=is_generation,
            is_site_bundle_generation=is_site_bundle_generation,
            is_refinement_request=is_refinement_request,
            is_sandbox_build=is_sandbox_build,
            allow_commit_lane=allow_commit_lane,
            is_commit_proposal_request=is_commit_proposal_request,
            is_commit_approval_request=is_commit_approval_request,
        )
        if commit_flow_response is not None:
            return commit_flow_response

        if (
            refinement_mode is not None
            and latest_artifact is None
            and not is_generation
            and not is_site_bundle_generation
            and not is_sandbox_build
        ):
            return {
                "visible_text": contract._artifact_needs_context_message(),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "artifact_refinement_unavailable",
                    "artifact_validation": "failed",
                    "failure_reason": "no_active_artifact",
                },
            }

        # ─── Sandbox website build/export ──────────────────────────────────────────
        if is_sandbox_build and not is_patch_apply_request:
            latest_bundle_artifact = (
                latest_artifact
                if isinstance(latest_artifact, dict)
                and latest_artifact.get("artifact_type") == "site_bundle"
                else None
            )
            if latest_bundle_artifact is not None and re.search(
                r"\b(it|this|approved|current|latest|the website|the site)\b",
                normalized,
            ):
                _biz = contract._format_business_name(
                    str(latest_bundle_artifact.get("title") or "Website"),
                    "Local Business Website",
                )
                _slug = contract._safe_slug(
                    str(latest_bundle_artifact.get("slug") or _biz),
                    fallback="site-bundle",
                )
                _entry = str(latest_bundle_artifact.get("entry") or "index.html")
                latest_bundle_payload = latest_bundle_artifact.get("site_bundle") or {}
                _files = (
                    list(latest_bundle_payload.get("files") or [])
                    if isinstance(latest_bundle_payload, dict)
                    else []
                )
                if not _files:
                    return {
                        "visible_text": "I do not have an active website bundle to export to the sandbox yet. Generate a preview first or ask me to build a named website.",
                        "code_artifact": {},
                        "artifact_patch_proposal": {},
                        "site_bundle": latest_bundle_artifact,
                        "context_receipt": {
                            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: sandbox-build",
                            "context_receipts": [],
                            "record_ids": [],
                        },
                        "provenance": {
                            "artifact_generation": "sandbox_build_unavailable",
                            "artifact_validation": "failed",
                            "failure_reason": "empty_active_bundle",
                        },
                    }
                _sandbox_bundle_artifact = latest_bundle_artifact
            else:
                _biz = contract._format_business_name(
                    contract._extract_artifact_name(question), "Local Business Website"
                )
                _style = contract._extract_style_hints(question)
                _slug = contract._safe_slug(_biz, fallback="site-bundle")
                _entry = "index.html"
                _pages = sb.default_pages_for_business(_biz, question)
                _files = sb.build_bundle_files(
                    business_name=_biz,
                    slug=_slug,
                    pages=_pages,
                    style_hints=_style,
                    question=question,
                )
                _design_spec = sb.build_design_spec_payload(
                    business_name=_biz,
                    slug=_slug,
                    pages=_pages,
                    style_hints=_style,
                    question=question,
                )
                _passed, _failures = sb.validate_bundle(
                    bundle_files=_files,
                    entry=_entry,
                    business_name=_biz,
                    style_hints=_style,
                )
                if not _passed:
                    return {
                        "visible_text": "I could not generate a valid sandbox website. "
                        + "; ".join(_failures),
                        "code_artifact": {},
                        "artifact_patch_proposal": {},
                        "site_bundle": {},
                        "context_receipt": {
                            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: sandbox-build",
                            "context_receipts": [],
                            "record_ids": [],
                        },
                        "provenance": {
                            "artifact_generation": "sandbox_build_failed",
                            "artifact_validation": "failed",
                            "failure_reason": "; ".join(_failures),
                        },
                    }
                _bundle_id = f"{_slug}-bundle"
                _rev = len(artifact_history) + 1
                _sandbox_bundle_artifact = {
                    "artifact_type": "site_bundle",
                    "artifact_id": _bundle_id,
                    "revision_id": f"{_bundle_id}:r{_rev}",
                    "revision_number": _rev,
                    "title": _biz,
                    "slug": _slug,
                    "entry": _entry,
                    "source_prompt": question.strip(),
                    "design_spec": _design_spec,
                    "site_bundle": {"files": _files},
                }

            written_relative, written_absolute = contract._write_sandbox_bundle(
                project_slug=_slug,
                bundle_files=_files,
            )
            display_paths = [
                SandboxWriteManager.display_path_for_write_target(path)
                for path in written_absolute
            ]
            preview_path = f"/generated-sites/{_slug}/{_entry}"
            return {
                "visible_text": (
                    f"Built {len(written_relative)} website file(s) in the sandbox under {_slug}/. "
                    f"Entry: {preview_path}. "
                    f"Sandbox root: {contract._sandbox_display_root()}."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "site_bundle": {
                    **_sandbox_bundle_artifact,
                    "sandbox_project_slug": _slug,
                    "sandbox_relative_path": f"{_slug}/{_entry}",
                    "sandbox_written_paths": written_relative,
                    "sandbox_display_paths": display_paths,
                    "preview_path": preview_path,
                },
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: sandbox-build",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "sandbox_build",
                    "artifact_validation": "passed",
                    "slug": _slug,
                    "entry": _entry,
                    "files_written": written_relative,
                    "sandbox_display_paths": display_paths,
                    "preview_path": preview_path,
                },
            }

        # Non-artifact chat prompts must fall through to normal answer routing.
        if (
            not is_generation
            and not is_site_bundle_generation
            and not is_sandbox_build
            and refinement_mode is None
        ):
            return None

        # ─── Site bundle generation ─────────────────────────────────────────────────
        if is_site_bundle_generation and not is_refinement_request:
            _biz = contract._format_business_name(
                contract._extract_artifact_name(question), "Local Business Website"
            )
            _style = contract._extract_style_hints(question)
            _slug = contract._safe_slug(_biz, fallback="site-bundle")
            _pages = sb.default_pages_for_business(_biz, question)
            _files = sb.build_bundle_files(
                business_name=_biz,
                slug=_slug,
                pages=_pages,
                style_hints=_style,
                question=question,
            )
            _design_spec = sb.build_design_spec_payload(
                business_name=_biz,
                slug=_slug,
                pages=_pages,
                style_hints=_style,
                question=question,
            )
            _passed, _failures = sb.validate_bundle(
                bundle_files=_files,
                entry="index.html",
                business_name=_biz,
                style_hints=_style,
            )
            if not _passed:
                return {
                    "visible_text": "I could not generate a valid site bundle. "
                    + "; ".join(_failures),
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "site_bundle": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: site-bundle-draft",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_generation": "site_bundle_generation_failed",
                        "artifact_validation": "failed",
                        "failure_reason": "; ".join(_failures),
                    },
                }
            _bundle_id = f"{_slug}-bundle"
            _rev = len(artifact_history) + 1
            _bundle_artifact: dict[str, Any] = {
                "artifact_type": "site_bundle",
                "artifact_id": _bundle_id,
                "revision_id": f"{_bundle_id}:r{_rev}",
                "revision_number": _rev,
                "title": _biz,
                "slug": _slug,
                "entry": "index.html",
                "source_prompt": question.strip(),
                "design_spec": _design_spec,
                "site_bundle": {"files": _files},
            }
            _html_pages = [p for p in _pages if p.endswith(".html")]
            return {
                "visible_text": (
                    f"Here is a {len(_html_pages)}-page site bundle for {_biz}. "
                    f'Files: {", ".join(_pages)}. Use "generate a patch for this site" to prepare files for writing.'
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "site_bundle": _bundle_artifact,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: site-bundle-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "site_bundle",
                    "artifact_validation": "passed",
                    "revision_number": _rev,
                    "business_name": _biz,
                    "slug": _slug,
                    "file_count": len(_files),
                },
            }

        if (
            is_refinement_request
            and latest_artifact is not None
            and str(latest_artifact.get("artifact_type") or "") == "site_bundle"
        ):
            latest_bundle = latest_artifact.get("site_bundle")
            latest_files_raw: list[dict[str, Any]] = []
            if isinstance(latest_bundle, dict):
                files_candidate = latest_bundle.get("files")
                if isinstance(files_candidate, list):
                    for item in files_candidate:
                        if isinstance(item, dict):
                            latest_files_raw.append(item)
            latest_files = [
                item
                for item in latest_files_raw
                if sb.is_safe_bundle_path(str(item.get("path") or ""))
            ]
            existing_pages = [
                str(item.get("path") or "")
                for item in latest_files
                if str(item.get("path") or "")
            ]
            source_prompt = str(latest_artifact.get("source_prompt") or question)
            _biz = contract._format_business_name(
                str(
                    latest_artifact.get("title")
                    or contract._extract_artifact_name(source_prompt)
                ),
                "Local Business Website",
            )
            _slug = contract._safe_slug(
                str(latest_artifact.get("slug") or _biz), fallback="site-bundle"
            )
            _pages = sb.merge_requested_pages(
                existing_pages or sb.default_pages_for_business(_biz, source_prompt),
                question,
            )

            _base_style = contract._extract_style_hints(source_prompt)
            _follow_style = contract._extract_style_hints(question)
            _style = {
                "colors": _follow_style.get("colors") or _base_style.get("colors", []),
                "styles": list(
                    dict.fromkeys(
                        [
                            *(_base_style.get("styles") or []),
                            *(_follow_style.get("styles") or []),
                        ]
                    )
                ),
            }
            if not _style.get("colors"):
                css_text = ""
                for item in latest_files:
                    if str(item.get("path") or "").endswith(".css"):
                        css_text = str(item.get("content") or "")
                        break
                if css_text:
                    colors_from_css: list[str] = []
                    for var_name in ("bg", "accent", "text"):
                        match = re.search(rf"--{var_name}:\s*([^;]+);", css_text)
                        if match:
                            colors_from_css.append(match.group(1).strip())
                    if colors_from_css:
                        _style["colors"] = colors_from_css

            typo_style = contract._typography_style_request(normalized)
            if typo_style and typo_style not in _style.get("styles", []):
                _style.setdefault("styles", []).append(typo_style)

            _render_prompt = f"{source_prompt}\nRevision request: {question}"
            _files = sb.build_bundle_files(
                business_name=_biz,
                slug=_slug,
                pages=_pages,
                style_hints=_style,
                question=_render_prompt,
            )
            _design_spec = sb.build_design_spec_payload(
                business_name=_biz,
                slug=_slug,
                pages=_pages,
                style_hints=_style,
                question=_render_prompt,
            )
            _passed, _failures = sb.validate_bundle(
                bundle_files=_files,
                entry=str(latest_artifact.get("entry") or "index.html"),
                business_name=_biz,
                style_hints=_style,
            )
            if not _passed:
                return {
                    "visible_text": (
                        "I could not complete the requested site bundle refinement safely, so I preserved the current bundle unchanged. "
                        + "; ".join(_failures)
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "site_bundle": latest_artifact,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: site-bundle-draft",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_generation": "site_bundle_refinement_failed",
                        "artifact_validation": "failed",
                        "failure_reason": "; ".join(_failures),
                    },
                }

            _bundle_id = str(latest_artifact.get("artifact_id") or f"{_slug}-bundle")
            _rev = len(artifact_history) + 1
            revised_bundle_artifact: dict[str, Any] = {
                **latest_artifact,
                "artifact_type": "site_bundle",
                "artifact_id": _bundle_id,
                "revision_id": f"{_bundle_id}:r{_rev}",
                "revision_number": _rev,
                "title": _biz,
                "slug": _slug,
                "entry": str(latest_artifact.get("entry") or "index.html"),
                "source_prompt": source_prompt,
                "latest_prompt": question.strip(),
                "design_spec": _design_spec,
                "site_bundle": {"files": _files},
            }

            return {
                "visible_text": (
                    "Updated the active site bundle revision and preserved all pages/content. "
                    'Use "generate a patch for this site" to prepare files for writing.'
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "site_bundle": revised_bundle_artifact,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: site-bundle-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "site_bundle_refinement",
                    "artifact_validation": "passed",
                    "revision_number": _rev,
                    "business_name": _biz,
                    "slug": _slug,
                    "file_count": len(_files),
                },
            }

        next_revision_number = len(artifact_history) + 1

        if refinement_mode == "undo" and latest_artifact is not None:
            if len(artifact_history) < 2:
                return {
                    "visible_text": "I do not have an earlier artifact revision to restore in this session.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_generation": "artifact_undo",
                        "source_artifact": "previous_session_revision",
                        "artifact_validation": "failed",
                        "failure_reason": "no_previous_revision",
                    },
                }
            restored_artifact = dict(artifact_history[-2]["artifact"])
            restored_artifact.update(
                {
                    "revision_id": f"{restored_artifact.get('artifact_id')}:r{next_revision_number}",
                    "revision_number": next_revision_number,
                    "source_prompt": question.strip(),
                }
            )
            return {
                "visible_text": f"I restored the previous {str(restored_artifact.get('language') or 'HTML').upper()} artifact for {restored_artifact.get('filename', 'index.html')}.",
                "code_artifact": restored_artifact,
                "artifact_patch_proposal": {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "artifact_undo",
                    "source_artifact": "previous_session_revision",
                    "revision_number": next_revision_number,
                },
            }

        if refinement_mode == "explain" and latest_artifact is not None:
            previous_artifact = (
                artifact_history[-2]["artifact"] if len(artifact_history) >= 2 else None
            )
            return {
                "visible_text": contract._artifact_change_summary(
                    latest_artifact, previous_artifact
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "artifact_change_summary",
                    "source_artifact": "latest session artifact",
                    "source_artifact_key": "latest_session_artifact",
                },
            }

        if is_refinement_request and latest_artifact is not None:
            filename = str(latest_artifact.get("filename") or "index.html")
            language = str(
                latest_artifact.get("language")
                or contract._code_artifact_language(normalized)
            )
            previewable = bool(latest_artifact.get("previewable", language == "html"))
            apply_requested = False
            business_name = contract._extract_business_name_from_html(
                str(latest_artifact.get("content") or "")
            )
            business_name = contract._format_business_name(
                business_name,
                "Local Business Website" if language == "html" else "Draft Artifact",
            )
            style_hints = contract._extract_style_hints(question)
            layout_hints = contract._extract_layout_hints(question)
        else:
            language = contract._code_artifact_language(normalized)
            filename = contract._extract_requested_filename(question, language)
            previewable = contract._extract_requested_previewable(question, language)
            apply_requested = contract._extract_apply_intent(question)
            business_name = contract._format_business_name(
                contract._extract_artifact_name(question),
                "Local Business Website" if language == "html" else "Draft Artifact",
            )
            style_hints = contract._extract_style_hints(question)
            layout_hints = contract._extract_layout_hints(question)

        artifact_content: str = ""
        provenance: dict[str, Any]
        typography_refinement_payload: dict[str, Any] | None = None
        if is_refinement_request and latest_artifact is not None:
            typography_style = (
                contract._typography_style_request(normalized)
                if refinement_mode == "typography_only"
                else None
            )
            if typography_style:
                artifact_content, typography_refinement_payload, typ_ok, typ_reason = (
                    contract._deterministic_typography_refinement_content(
                        source_artifact=latest_artifact,
                        requested_style=typography_style,
                    )
                )
                typography_business_name = (
                    contract._extract_business_name_from_html(
                        str(latest_artifact.get("content") or "")
                    )
                    or ""
                )
                valid, reason = contract._validate_artifact_content(
                    content=artifact_content,
                    language=str(latest_artifact.get("language") or "html"),
                    business_name=typography_business_name,
                    style_hints={"colors": [], "styles": []},
                    requested_question="",
                )
                if not typ_ok or not valid:
                    return {
                        "visible_text": (
                            "I could not safely apply the typography refinement, so I preserved the current artifact unchanged."
                        ),
                        "code_artifact": {},
                        "artifact_patch_proposal": {},
                        "context_receipt": {
                            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                            "context_receipts": [],
                            "record_ids": [],
                        },
                        "provenance": {
                            "artifact_generation": "typography_refinement_failed",
                            "artifact_validation": "failed",
                            "source_artifact": source_artifact_label
                            or "latest session artifact",
                            "source_artifact_key": "latest_session_artifact",
                            "revision_mode": "typography_only",
                            "failure_reason": typ_reason if not typ_ok else reason,
                            "typography_refinement": {
                                **(typography_refinement_payload or {}),
                                "status": "failed",
                            },
                        },
                    }
                provenance = {
                    "artifact_generation": "deterministic_typography_refinement",
                    "artifact_validation": "passed",
                    "source_artifact": source_artifact_label
                    or "latest session artifact",
                    "source_artifact_key": "latest_session_artifact",
                    "revision_mode": "typography_only",
                    "revision_number": next_revision_number,
                    "typography_refinement": typography_refinement_payload,
                }
            else:
                try:
                    revision_source_artifact = dict(latest_artifact)
                    revision_source_artifact["_revision_mode"] = (
                        refinement_mode or "full_revision"
                    )
                    (
                        artifact_content,
                        model_used,
                        model_endpoint,
                    ) = await contract._revise_artifact_with_local_model(
                        question=question,
                        source_artifact=revision_source_artifact,
                    )
                    provenance = {
                        "artifact_generation": "local_model_revision",
                        "model_used": model_used,
                        "model_endpoint": model_endpoint,
                        "artifact_validation": "passed",
                        "source_artifact": source_artifact_label
                        or "latest session artifact",
                        "source_artifact_key": "latest_session_artifact",
                        "revision_mode": refinement_mode or "full_revision",
                        "revision_number": next_revision_number,
                    }
                except Exception as exc:
                    fallback_reason = str(exc).strip() or "artifact_revision_failed"
                    artifact_content = (
                        contract._deterministic_revision_fallback_content(
                            question=question,
                            source_artifact=latest_artifact,
                            revision_mode=refinement_mode or "full_revision",
                        )
                    )
                    valid, reason = contract._validate_revision_candidate(
                        content=artifact_content,
                        source_artifact=latest_artifact,
                        requested_question=question,
                    )
                    model_resolution = resolve_model_for_runtime_role("code")
                    if not valid:
                        return {
                            "visible_text": (
                                "I could not complete the requested artifact revision safely, so I preserved the current artifact unchanged. "
                                "The requested edit failed validation."
                            ),
                            "code_artifact": {},
                            "artifact_patch_proposal": {},
                            "context_receipt": {
                                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                                "context_receipts": [],
                                "record_ids": [],
                            },
                            "provenance": {
                                "artifact_generation": "artifact_refinement_failed",
                                "artifact_validation": "failed",
                                "source_artifact": source_artifact_label
                                or "latest session artifact",
                                "source_artifact_key": "latest_session_artifact",
                                "revision_mode": refinement_mode or "full_revision",
                                "failure_reason": reason,
                            },
                        }
                    provenance = {
                        "artifact_generation": "deterministic_prompt_template_fallback",
                        "model_used": model_resolution.model_tag or "unknown",
                        "fallback_reason": f"artifact revision fallback: {fallback_reason}",
                        "fallback_prevalidation": (
                            "passed" if valid else f"failed:{reason}"
                        ),
                        "source_artifact": source_artifact_label
                        or "latest session artifact",
                        "source_artifact_key": "latest_session_artifact",
                        "revision_mode": refinement_mode or "full_revision",
                        "revision_number": next_revision_number,
                    }
        else:
            try:
                generation_result = await contract._generate_artifact_with_local_model(
                    question=question,
                    filename=filename,
                    language=language,
                    previewable=previewable,
                    apply_requested=apply_requested,
                    business_name=business_name,
                    style_hints=style_hints,
                    layout_hints=layout_hints,
                )
                if len(generation_result) == 3:
                    artifact_content, model_used, model_endpoint = generation_result
                else:
                    artifact_content, model_used = generation_result  # type: ignore[misc]
                    model_endpoint = configured_ollama_base_url_candidates()[0]
                provenance = {
                    "artifact_generation": "local_model",
                    "model_used": model_used,
                    "model_endpoint": model_endpoint,
                    "artifact_validation": "passed",
                    "revision_number": next_revision_number,
                }
            except Exception as exc:
                fallback_reason = str(exc).strip() or "local_model_error"
                artifact_content = contract._default_code_artifact_content(
                    filename, language, question
                )
                valid, reason = contract._validate_artifact_content(
                    content=artifact_content,
                    language=language,
                    business_name=business_name,
                    style_hints=style_hints,
                    requested_question=question,
                )
                if not valid:
                    return {
                        "visible_text": (
                            "I could not generate a safe artifact draft right now. "
                            "Please try again with a slightly simpler prompt and I will keep the requested business identity intact."
                        ),
                        "code_artifact": {},
                        "artifact_patch_proposal": {},
                        "context_receipt": {
                            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                            "context_receipts": [],
                            "record_ids": [],
                        },
                        "provenance": {
                            "artifact_generation": "artifact_generation_failed",
                            "artifact_validation": "failed",
                            "failure_reason": "fallback_validation_failed",
                            "revision_number": next_revision_number,
                        },
                    }
                model_resolution = resolve_model_for_runtime_role("code")
                provenance = {
                    "artifact_generation": "deterministic_prompt_template_fallback",
                    "model_used": model_resolution.model_tag or "unknown",
                    "fallback_reason": fallback_reason,
                    "revision_number": next_revision_number,
                }

        fidelity_context = contract._prompt_fidelity_history_metadata(
            session_messages,
            session_metadata,
        )
        if business_name:
            fidelity_context["requested_business_name_override"] = business_name
        if is_refinement_request and latest_artifact is not None:
            fidelity_source_prompt = str(
                latest_artifact.get("source_prompt") or question
            )
            fidelity_context["requested_business_type_override"] = (
                contract._artifact_business_category(
                    fidelity_source_prompt,
                    business_name,
                )
            )
        fidelity_prompt = question
        if refinement_mode == "typography_only" and latest_artifact is not None:
            fidelity_prompt = str(latest_artifact.get("source_prompt") or question)

        prompt_fidelity = contract.validate_artifact_prompt_fidelity(
            fidelity_prompt,
            artifact_content,
            fidelity_context,
        )
        prompt_fidelity_payload = {
            "status": str(prompt_fidelity.get("status") or "failed"),
            "requested_business_name": str(
                prompt_fidelity.get("requested_business_name") or ""
            ).strip(),
            "requested_business_type": str(
                prompt_fidelity.get("requested_business_type") or ""
            ).strip(),
            "requested_colors": [
                str(item).strip()
                for item in (prompt_fidelity.get("requested_colors") or [])
                if str(item).strip()
            ],
            "forbidden_terms_checked": [
                str(item).strip()
                for item in (prompt_fidelity.get("forbidden_terms_checked") or [])
                if str(item).strip()
            ],
            "repair_attempted": False,
        }

        if not bool(prompt_fidelity.get("passed")):
            repaired_content = contract._repair_artifact_prompt_fidelity(
                prompt=question,
                artifact_content=artifact_content,
                fidelity_report=prompt_fidelity,
            )
            repaired_fidelity = contract.validate_artifact_prompt_fidelity(
                fidelity_prompt,
                repaired_content,
                fidelity_context,
            )
            if bool(repaired_fidelity.get("passed")):
                artifact_content = repaired_content
                prompt_fidelity_payload = {
                    "status": "repaired",
                    "requested_business_name": str(
                        repaired_fidelity.get("requested_business_name") or ""
                    ).strip(),
                    "requested_business_type": str(
                        repaired_fidelity.get("requested_business_type") or ""
                    ).strip(),
                    "requested_colors": [
                        str(item).strip()
                        for item in (repaired_fidelity.get("requested_colors") or [])
                        if str(item).strip()
                    ],
                    "forbidden_terms_checked": [
                        str(item).strip()
                        for item in (
                            repaired_fidelity.get("forbidden_terms_checked") or []
                        )
                        if str(item).strip()
                    ],
                    "repair_attempted": True,
                }
            else:
                failure_reason = ", ".join(
                    repaired_fidelity.get("failures")
                    or prompt_fidelity.get("failures")
                    or ["prompt_fidelity_failed"]
                )
                return {
                    "visible_text": (
                        "I generated an artifact, but it failed prompt-fidelity validation because it still contained stale template or palette content. "
                        "I did not return the unsafe artifact."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        **provenance,
                        "artifact_generation": "artifact_prompt_fidelity_blocked",
                        "artifact_validation": "failed",
                        "failure_reason": failure_reason,
                        "prompt_fidelity": {
                            **prompt_fidelity_payload,
                            "status": "failed",
                            "repair_attempted": True,
                        },
                    },
                }

        provenance["prompt_fidelity"] = prompt_fidelity_payload
        provenance["artifact_validation"] = prompt_fidelity_payload.get(
            "status", "passed"
        )
        if typography_refinement_payload is not None:
            provenance["typography_refinement"] = typography_refinement_payload

        return {
            "visible_text": (
                f"Here is a revised {language.upper()} artifact for {filename}."
                if is_refinement_request
                else f"Here is a draft {language.upper()} artifact for {filename}."
            ),
            "code_artifact": {
                "type": "code_artifact",
                "filename": filename,
                "language": language,
                "previewable": previewable,
                "applied": False,
                "content": artifact_content,
                "artifact_id": (
                    latest_artifact.get("artifact_id")
                    if latest_artifact is not None
                    else f"{contract._slugify_artifact_name(filename)}-artifact"
                ),
                "revision_id": f"{(latest_artifact.get('artifact_id') if latest_artifact is not None else contract._slugify_artifact_name(filename) + '-artifact')}:r{next_revision_number}",
                "revision_number": next_revision_number,
                "source_prompt": question.strip(),
                "prompt_fidelity": prompt_fidelity_payload,
                "typography_refinement": typography_refinement_payload or {},
            },
            "artifact_patch_proposal": {},
            "context_receipt": {
                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                "context_receipts": [],
                "record_ids": [],
            },
            "provenance": provenance,
        }
