from __future__ import annotations

from typing import Any

from core.brain import site_bundle as sb


class ArtifactResponsePatchFlow:
    @staticmethod
    def handle_patch_flow(
        *,
        contract: Any,
        normalized: str,
        latest_artifact: dict[str, Any] | None,
        source_artifact_label: str | None,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
        is_patch_proposal_request: bool,
        is_patch_apply_request: bool,
        is_post_apply_verify_request: bool,
        is_post_apply_preview_request: bool,
        is_post_apply_targeted_validation_request: bool,
    ) -> dict[str, Any] | None:
        # ─── Site bundle patch proposal ────────────────────────────────────────────
        if (
            is_patch_proposal_request
            and latest_artifact is not None
            and latest_artifact.get("artifact_type") == "site_bundle"
        ):
            slug = str(latest_artifact.get("slug") or "site-bundle")
            bundle_files_raw = latest_artifact.get("site_bundle") or {}
            bundle_files: list[dict[str, str]] = []
            if isinstance(bundle_files_raw, dict):
                bundle_files = list(bundle_files_raw.get("files") or [])
            if not bundle_files:
                return {
                    "visible_text": "I do not have any files in the active site bundle to patch.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "site_bundle": latest_artifact,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-proposal",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "proposal_unavailable",
                        "applied": False,
                        "requires_confirmation": True,
                        "failure_reason": "empty_bundle",
                    },
                }
            root = contract._workspace_root()
            bundle_proposals = sb.build_patch_proposals(
                bundle_files=bundle_files,
                slug=slug,
                root=root,
                validate_fn=contract._validate_patch_proposal,
                diff_fn=contract._build_unified_diff,
            )
            all_passed = all(
                p.get("validation", {}).get("status") == "passed"
                for p in bundle_proposals
            )
            return {
                "visible_text": (
                    f"I prepared patch proposals for all {len(bundle_proposals)} file(s) in the site bundle. "
                    'No files were written. Use "apply it" to write them.'
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "site_bundle": latest_artifact,
                "site_bundle_patch_proposals": bundle_proposals,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-proposal",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_patch": "bundle_proposed",
                    "applied": False,
                    "requires_confirmation": True,
                    "slug": slug,
                    "file_count": len(bundle_proposals),
                    "all_valid": all_passed,
                    "source_artifact": source_artifact_label
                    or "latest session artifact",
                },
            }

        # ─── Site bundle apply ──────────────────────────────────────────────────────
        if is_patch_apply_request:
            _bundle_proposals_pending = sb.latest_pending_bundle_proposals(
                session_messages, session_metadata
            )
            if _bundle_proposals_pending is not None:
                root = contract._workspace_root()
                written, errors = sb.apply_proposals(
                    proposals=_bundle_proposals_pending,
                    root=root,
                    resolve_fn=contract._resolve_safe_patch_target,
                )
                latest_bundle_art = sb.latest_bundle_artifact(
                    session_messages, session_metadata
                )
                slug = str((latest_bundle_art or {}).get("slug") or "site-bundle")
                entry = str((latest_bundle_art or {}).get("entry") or "index.html")
                preview_path = f"/generated-sites/{slug}/{entry}"
                applied_bundle_proposals = [
                    {**p, "applied": True, "preview_path": preview_path}
                    for p in _bundle_proposals_pending
                    if p.get("target_path") in written
                ]
                return {
                    "visible_text": (
                        f"Applied {len(written)} file(s) for the site bundle under generated-sites/{slug}/. "
                        + (f"Errors: {'; '.join(errors)}" if errors else "No errors.")
                        + f" Preview entry page at {preview_path}."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "site_bundle": latest_bundle_art or {},
                    "site_bundle_patch_proposals": applied_bundle_proposals,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "bundle_applied",
                        "applied": True,
                        "requires_confirmation": True,
                        "slug": slug,
                        "files_written": written,
                        "errors": errors,
                        "preview_path": preview_path,
                        "commit_created": False,
                        "push_performed": False,
                    },
                }

            latest_bundle_art = sb.latest_bundle_artifact(
                session_messages, session_metadata
            )
            if isinstance(latest_bundle_art, dict):
                slug = str(latest_bundle_art.get("slug") or "site-bundle")
                entry = str(latest_bundle_art.get("entry") or "index.html")
                bundle_files_raw = latest_bundle_art.get("site_bundle") or {}
                bundle_files_to_apply: list[dict[str, str]] = []
                if isinstance(bundle_files_raw, dict):
                    bundle_files_to_apply = list(bundle_files_raw.get("files") or [])
                if bundle_files_to_apply:
                    root = contract._workspace_root()
                    generated_proposals = sb.build_patch_proposals(
                        bundle_files=bundle_files_to_apply,
                        slug=slug,
                        root=root,
                        validate_fn=contract._validate_patch_proposal,
                        diff_fn=contract._build_unified_diff,
                    )
                    written, errors = sb.apply_proposals(
                        proposals=generated_proposals,
                        root=root,
                        resolve_fn=contract._resolve_safe_patch_target,
                    )
                    preview_path = f"/generated-sites/{slug}/{entry}"
                    applied_bundle_proposals = [
                        {**p, "applied": True, "preview_path": preview_path}
                        for p in generated_proposals
                        if p.get("target_path") in written
                    ]
                    return {
                        "visible_text": (
                            f"Applied {len(written)} file(s) for the site bundle under generated-sites/{slug}/. "
                            + (
                                f"Errors: {'; '.join(errors)}"
                                if errors
                                else "No errors."
                            )
                            + f" Preview entry page at {preview_path}."
                        ),
                        "code_artifact": {},
                        "artifact_patch_proposal": {},
                        "site_bundle": latest_bundle_art,
                        "site_bundle_patch_proposals": applied_bundle_proposals,
                        "context_receipt": {
                            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                            "context_receipts": [],
                            "record_ids": [],
                        },
                        "provenance": {
                            "artifact_patch": "bundle_applied",
                            "applied": True,
                            "requires_confirmation": True,
                            "slug": slug,
                            "files_written": written,
                            "errors": errors,
                            "preview_path": preview_path,
                            "commit_created": False,
                            "push_performed": False,
                        },
                    }

        if is_patch_proposal_request:
            if latest_artifact is None:
                return {
                    "visible_text": "I do not have an active code artifact to turn into a patch yet. Generate or paste an artifact first.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-proposal",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "proposal_unavailable",
                        "applied": False,
                        "requires_confirmation": True,
                        "failure_reason": "no_active_artifact",
                    },
                }

            proposal = contract._build_patch_proposal_from_artifact(
                artifact=latest_artifact
            )
            validation_raw = proposal.get("validation")
            validation: dict[str, Any] = (
                validation_raw if isinstance(validation_raw, dict) else {}
            )
            validation_status = str(validation.get("status") or "failed")
            return {
                "visible_text": "I prepared a patch proposal from the active artifact. No files were changed.",
                "code_artifact": {},
                "artifact_patch_proposal": proposal,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-proposal",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_patch": "proposed",
                    "applied": False,
                    "requires_confirmation": True,
                    "target_path": proposal.get("target_path"),
                    "validation": validation_status,
                    "source_artifact": source_artifact_label
                    or "latest session artifact",
                    "source_artifact_id": proposal.get("source_artifact_id"),
                },
            }

        if is_patch_apply_request:
            pending = contract._latest_pending_patch_proposal(
                session_messages, session_metadata
            )
            if pending is None:
                return {
                    "visible_text": "I do not have a pending patch proposal to apply.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_refused",
                        "applied": False,
                        "requires_confirmation": True,
                        "failure_reason": "no_pending_patch_proposal",
                    },
                }

            pending_validation_raw = pending.get("validation")
            pending_validation: dict[str, Any] = (
                pending_validation_raw
                if isinstance(pending_validation_raw, dict)
                else {}
            )
            validation_status = str(
                pending_validation.get("status") or "failed"
            ).lower()
            failures_raw = pending_validation.get("failures")
            failures: list[str] = (
                [str(item) for item in failures_raw]
                if isinstance(failures_raw, list)
                else []
            )
            if validation_status != "passed":
                reason = (
                    "; ".join(str(item) for item in failures if str(item).strip())
                    or "validation did not pass"
                )
                return {
                    "visible_text": f"I cannot apply this patch because validation failed: {reason}.",
                    "code_artifact": {},
                    "artifact_patch_proposal": pending,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_blocked",
                        "applied": False,
                        "requires_confirmation": True,
                        "target_path": pending.get("target_path"),
                        "validation": "failed",
                        "failure_reason": reason,
                    },
                }

            target_path = str(pending.get("target_path") or "").replace("\\", "/")
            operation = str(pending.get("operation") or "create")
            content = str(pending.get("content") or "")
            if operation not in {"create", "update"} or not target_path:
                return {
                    "visible_text": "I cannot apply this patch because validation failed: operation/path is not allowed.",
                    "code_artifact": {},
                    "artifact_patch_proposal": pending,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_blocked",
                        "applied": False,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "validation": "failed",
                        "failure_reason": "operation_or_target_invalid",
                    },
                }

            root = contract._workspace_root()
            target, resolve_error = contract._resolve_safe_patch_target(
                root=root, target_path=target_path
            )
            if target is None:
                return {
                    "visible_text": "I cannot apply this patch because validation failed: target path failed safety checks.",
                    "code_artifact": {},
                    "artifact_patch_proposal": pending,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_blocked",
                        "applied": False,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "validation": "failed",
                        "failure_reason": resolve_error or "unsafe_target_path",
                    },
                }

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written_content = target.read_text(encoding="utf-8")
            if written_content != content:
                return {
                    "visible_text": "I attempted to apply the patch, but post-write validation failed because the file content does not match the proposal.",
                    "code_artifact": {},
                    "artifact_patch_proposal": pending,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_failed",
                        "applied": False,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "validation": "failed",
                        "failure_reason": "post_write_content_mismatch",
                    },
                }

            preview_path = f"/{target_path}"
            applied_base = {
                **pending,
                "applied": True,
                "applied_at": contract._utc_now_iso(),
                "preview_path": preview_path,
            }
            verification = {
                "status": "passed",
                "verified": True,
                "checks": [
                    {
                        "name": "post_write_content_match",
                        "status": "passed",
                        "detail": "written content matches applied proposal",
                    },
                ],
                "failures": [],
                "verified_at": contract._utc_now_iso(),
                "content_length": len(content),
                "content_sha256": contract._content_sha256(content),
            }
            applied_proposal = contract._applied_patch_with_runtime_fields(
                proposal=applied_base,
                verification=verification,
                preview_path=preview_path,
            )
            return {
                "visible_text": (
                    f"Applied the proposed patch to {target_path}. File written locally with operation {operation}. "
                    "No commit was created, no push was performed, and tests were not run."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": applied_proposal,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_patch": "applied",
                    "applied": True,
                    "requires_confirmation": True,
                    "target_path": target_path,
                    "operation": operation,
                    "validation": "passed",
                    "commit_created": False,
                    "push_performed": False,
                    "preview_path": preview_path,
                },
            }

        return None


class ArtifactResponseCommitFlow:
    @staticmethod
    def handle_commit_flow(
        *,
        contract: Any,
        question: str,
        normalized: str,
        latest_artifact: dict[str, Any] | None,
        source_artifact_label: str | None,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
        is_post_apply_full_test_guard_request: bool,
        is_post_apply_verify_request: bool,
        is_post_apply_preview_request: bool,
        is_post_apply_targeted_validation_request: bool,
        is_generation: bool,
        is_site_bundle_generation: bool,
        is_refinement_request: bool,
        is_sandbox_build: bool,
        allow_commit_lane: bool,
        is_commit_proposal_request: bool,
        is_commit_approval_request: bool,
    ) -> dict[str, Any] | None:
        if is_post_apply_full_test_guard_request:
            latest_applied = contract._latest_applied_patch_proposal(
                session_messages, session_metadata
            )
            if latest_applied is None:
                return None
            target_path = str((latest_applied or {}).get("target_path") or "")
            return {
                "visible_text": (
                    "I did not run full tests automatically. I can only run the focused checks for the applied file in this lane. "
                    "If you want full-suite validation, ask me explicitly and I will request confirmation before running it."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": latest_applied or {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_patch": "full_test_guard",
                    "applied": bool(latest_applied),
                    "requires_confirmation": True,
                    "target_path": target_path or None,
                    "tests_run": False,
                    "commit_created": False,
                    "push_performed": False,
                },
            }

        if (
            is_post_apply_verify_request
            or is_post_apply_preview_request
            or is_post_apply_targeted_validation_request
        ):
            applied = contract._latest_applied_patch_proposal(
                session_messages, session_metadata
            )
            if applied is None:
                return {
                    "visible_text": "I do not have an applied patch to verify in this session.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "post_apply_unavailable",
                        "applied": False,
                        "requires_confirmation": True,
                        "failure_reason": "no_applied_patch",
                    },
                }

            target_path = str(applied.get("target_path") or "")
            preview_path = str(applied.get("preview_path") or f"/{target_path}")
            updated_applied = dict(applied)

            if is_post_apply_verify_request:
                verification, _verify_data = contract._verify_applied_patch_content(
                    proposal=applied,
                    include_business_name=True,
                )
                updated_applied = contract._applied_patch_with_runtime_fields(
                    proposal=applied,
                    verification=verification,
                    preview_path=preview_path,
                )
                checks_raw = verification.get("checks")
                failures_raw = verification.get("failures")
                checks_total = len(checks_raw) if isinstance(checks_raw, list) else 0
                failures_total = (
                    len(failures_raw) if isinstance(failures_raw, list) else 0
                )
                return {
                    "visible_text": (
                        f"Post-apply verification {'passed' if verification.get('status') == 'passed' else 'failed'} for {target_path}. "
                        f"Checked {checks_total} items with {failures_total} failure(s)."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": updated_applied,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "post_apply_verified",
                        "applied": True,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "preview_path": preview_path,
                        "verification_status": verification.get("status"),
                        "tests_run": False,
                        "commit_created": False,
                        "push_performed": False,
                    },
                }

            if is_post_apply_preview_request:
                updated_applied = contract._applied_patch_with_runtime_fields(
                    proposal=applied,
                    preview_path=preview_path,
                )
                return {
                    "visible_text": (
                        f"Preview path is {preview_path}. If the local app is running, open that route in your browser to view {target_path}."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": updated_applied,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "post_apply_preview",
                        "applied": True,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "preview_path": preview_path,
                        "tests_run": False,
                        "commit_created": False,
                        "push_performed": False,
                    },
                }

            if is_post_apply_targeted_validation_request:
                verification, verify_data = contract._verify_applied_patch_content(
                    proposal=applied,
                    include_business_name=False,
                )
                actual_content = str((verify_data or {}).get("actual_content") or "")
                targeted_status, targeted_checks, targeted_failures = (
                    contract._validate_patch_proposal(
                        root=contract._workspace_root(),
                        target_path=target_path,
                        content=actual_content,
                        language=str(applied.get("language") or "html"),
                        business_name="",
                        operation=str(applied.get("operation") or "update"),
                    )
                )
                targeted_validation = {
                    "status": targeted_status,
                    "checks": targeted_checks,
                    "failures": targeted_failures,
                    "validated_at": contract._utc_now_iso(),
                    "mode": "post_apply_targeted",
                }
                updated_applied = contract._applied_patch_with_runtime_fields(
                    proposal=applied,
                    verification=verification,
                    targeted_validation=targeted_validation,
                    preview_path=preview_path,
                )
                return {
                    "visible_text": (
                        f"Targeted validation {'passed' if targeted_status == 'passed' else 'failed'} for {target_path}. "
                        "Only focused file checks were run; no broad test suites were executed."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": updated_applied,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "post_apply_targeted_validation",
                        "applied": True,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "preview_path": preview_path,
                        "targeted_validation": targeted_status,
                        "tests_run": False,
                        "commit_created": False,
                        "push_performed": False,
                    },
                }

        if allow_commit_lane and is_commit_proposal_request:
            proposal = contract._build_commit_proposal(
                question=question,
                session_messages=session_messages,
                session_metadata=session_metadata,
            )
            return {
                "visible_text": str(
                    proposal.get("visible_text")
                    or "I prepared a commit proposal. No files were changed, no commit was created, and no push was performed."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "commit_proposal": proposal,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "commit_proposal": "proposed",
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                    "branch": proposal.get("branch"),
                    "proposal_id": proposal.get("proposal_id"),
                },
            }

        if allow_commit_lane and is_commit_approval_request:
            pending_commit = contract._latest_pending_commit_proposal(
                session_messages, session_metadata
            )
            if pending_commit is None:
                return {
                    "visible_text": "I do not have a pending commit proposal to approve in this session.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "commit_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "commit_proposal": "approval_refused",
                        "committed": False,
                        "push_performed": False,
                        "requires_confirmation": True,
                        "failure_reason": "no_pending_commit_proposal",
                    },
                }
            applied_commit = contract._apply_commit_proposal(proposal=pending_commit)
            return {
                "visible_text": str(
                    applied_commit.get("visible_text")
                    or "Committed the approved local changes. No push was performed."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "commit_proposal": applied_commit.get("commit_proposal", {}),
                "context_receipt": applied_commit.get("context_receipt"),
                "provenance": applied_commit.get("provenance", {}),
            }

        if (
            not is_generation
            and not is_site_bundle_generation
            and is_refinement_request
            and latest_artifact is None
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

        if (
            not is_generation
            and not is_refinement_request
            and not is_site_bundle_generation
            and not is_sandbox_build
        ):
            return None

        return None
