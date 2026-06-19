from __future__ import annotations

import html
import re
from typing import Any

from core.brain.code_artifact_builder import CodeArtifactBuilder


class ArtifactFidelityManager:
    """Prompt fidelity contract, validation, repair, and retry prompt helpers."""

    @classmethod
    def extract_prompt_fidelity_contract(cls, question: str) -> dict[str, Any]:
        requested_business_name = CodeArtifactBuilder.clean_artifact_label(
            str(CodeArtifactBuilder.extract_artifact_name(question) or "")
        )
        requested_business_type = CodeArtifactBuilder.artifact_business_category(
            question, requested_business_name
        )
        requested_colors = CodeArtifactBuilder.extract_style_hints(question).get(
            "colors", []
        )
        return {
            "requested_business_name": requested_business_name,
            "requested_business_type": requested_business_type,
            "requested_colors": list(dict.fromkeys(requested_colors)),
            "artifact_intent": CodeArtifactBuilder.artifact_intent_label(question),
            "source_prompt": question.strip(),
        }

    @staticmethod
    def color_hex_map() -> dict[str, list[str]]:
        return {
            "black": ["#000", "#000000", "#070707", "#111"],
            "white": ["#fff", "#ffffff"],
            "yellow": ["#facc15", "#fde047", "#fbbf24"],
            "gold": ["#d4af37", "#f5d27a"],
            "green": ["#22c55e", "#16a34a"],
            "purple": ["#7c3aed", "#a855f7", "#9333ea"],
            "red": ["#dc2626", "#ef4444"],
            "blue": ["#2563eb", "#3b82f6"],
            "orange": ["#f97316", "#fb923c"],
            "pink": ["#ec4899", "#f472b6"],
            "silver": ["#c0c0c0", "#9ca3af"],
            "cyan": ["#22d3ee", "#06b6d4"],
            "teal": ["#14b8a6", "#0d9488"],
            "cream": ["#fff7d6", "#fef3c7"],
        }

    @staticmethod
    def service_terms_for_business_type(business_type: str) -> tuple[str, ...]:
        mapping = {
            "grooming": ("groom", "pet", "dog", "bath", "wash", "trim", "fur", "paw"),
            "locksmith": ("locksmith", "security", "key", "lock", "lockout", "rekey"),
            "florist": ("floral", "flower", "bouquet", "bloom"),
            "detailing": (
                "detail",
                "detailing",
                "wash",
                "vehicle",
                "interior",
                "exterior",
            ),
            "arcade": ("arcade", "game", "gaming", "score", "retro"),
            "hot_dog_cart": ("hot dog", "cart", "menu", "street", "order"),
        }
        return mapping.get(business_type, ())

    @classmethod
    def prompt_fidelity_forbidden_terms(
        cls,
        *,
        contract: dict[str, Any],
        metadata: dict[str, Any] | None,
    ) -> list[str]:
        requested_name = (
            str(contract.get("requested_business_name") or "").strip().lower()
        )
        requested_colors = {
            str(color).strip().lower()
            for color in (contract.get("requested_colors") or [])
            if str(color).strip()
        }
        forbidden: list[str] = ["White, purple, and green"]

        default_businesses = (
            "Soggy Doggy",
            "Harry's Hot Dog Cart",
            "Flow Flowers",
            "Rico's Mobile Detailing",
            "Neon Byte Arcade",
            "Crimson Turtle Locksmiths",
        )
        for name in default_businesses:
            if name.lower() != requested_name:
                forbidden.append(name)

        if isinstance(metadata, dict):
            history_names = metadata.get("history_business_names")
            if isinstance(history_names, list):
                for item in history_names:
                    token = str(item or "").strip()
                    if token and token.lower() != requested_name:
                        forbidden.append(token)

            previous_colors = metadata.get("previous_colors")
            if requested_colors and isinstance(previous_colors, list):
                for color in previous_colors:
                    token = str(color or "").strip().lower()
                    if token and token not in requested_colors:
                        forbidden.append(token)

        return list(dict.fromkeys(forbidden))

    @classmethod
    def validate_artifact_prompt_fidelity(
        cls,
        prompt: str,
        artifact_content: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        contract = cls.extract_prompt_fidelity_contract(prompt)
        if isinstance(metadata, dict):
            override_name = str(
                metadata.get("requested_business_name_override") or ""
            ).strip()
            override_type = str(
                metadata.get("requested_business_type_override") or ""
            ).strip()
            if override_name:
                contract["requested_business_name"] = override_name
            if override_type:
                contract["requested_business_type"] = override_type

        business_name = str(contract.get("requested_business_name") or "").strip()
        business_type = str(contract.get("requested_business_type") or "").strip()
        requested_colors = [
            str(color).strip().lower()
            for color in (contract.get("requested_colors") or [])
            if str(color).strip()
        ]
        content = str(artifact_content or "")
        lowered = content.lower()
        style_blocks = re.findall(
            r"<style[^>]*>(.*?)</style>", content, flags=re.IGNORECASE | re.DOTALL
        )
        style_text = "\n".join(style_blocks).lower()

        failures: list[str] = []
        if "```" in content:
            failures.append("no_markdown_fences")
        if re.search(r"<script[^>]+src\s*=", lowered):
            failures.append("no_remote_scripts")
        if re.search(
            r"https?://|//cdn\.|fonts\.googleapis|unpkg\.com|jsdelivr", lowered
        ):
            failures.append("no_remote_assets")

        if business_name and business_name.lower() not in lowered:
            failures.append("requested_business_name_missing")

        if business_name:
            title_text = cls.extract_first_tag_text(content, "title") or ""
            h1_text = cls.extract_first_tag_text(content, "h1") or ""
            if (
                business_name.lower() not in title_text.lower()
                and business_name.lower() not in h1_text.lower()
                and business_name.lower() not in lowered
            ):
                failures.append("business_identity_misaligned")

        service_terms = cls.service_terms_for_business_type(business_type)
        if service_terms and not any(
            re.search(rf"\b{re.escape(term)}\b", lowered) for term in service_terms
        ):
            failures.append("requested_business_type_missing")

        color_hex = cls.color_hex_map()
        css_color_hits = 0
        for color in requested_colors:
            has_word = bool(re.search(rf"\b{re.escape(color)}\b", lowered))
            has_hex = any(token in lowered for token in color_hex.get(color, []))
            has_css = bool(re.search(rf"\b{re.escape(color)}\b", style_text)) or any(
                token in style_text for token in color_hex.get(color, [])
            )
            if not (has_word or has_hex):
                failures.append(f"requested_color_missing:{color}")
            if has_css:
                css_color_hits += 1

        if requested_colors and css_color_hits < min(2, len(requested_colors)):
            failures.append("requested_palette_not_applied_to_css")

        forbidden_terms = cls.prompt_fidelity_forbidden_terms(
            contract=contract, metadata=metadata
        )
        for token in forbidden_terms:
            needle = str(token).strip()
            if not needle:
                continue
            if re.search(rf"\b{re.escape(needle.lower())}\b", lowered):
                failures.append(f"forbidden_term_present:{needle}")

        return {
            "passed": not failures,
            "status": "passed" if not failures else "failed",
            "failures": failures,
            "requested_business_name": contract.get("requested_business_name"),
            "requested_business_type": contract.get("requested_business_type"),
            "requested_colors": contract.get("requested_colors"),
            "artifact_intent": contract.get("artifact_intent"),
            "source_prompt": contract.get("source_prompt"),
            "forbidden_terms_checked": forbidden_terms,
            "repair_attempted": False,
        }

    @classmethod
    def repair_artifact_prompt_fidelity(
        cls,
        *,
        prompt: str,
        artifact_content: str,
        fidelity_report: dict[str, Any],
    ) -> str:
        repaired = cls.strip_markdown_fences(str(artifact_content or ""))
        requested_name = str(
            fidelity_report.get("requested_business_name") or ""
        ).strip()
        requested_type = str(
            fidelity_report.get("requested_business_type") or ""
        ).strip()
        requested_colors = [
            str(color).strip().lower()
            for color in (fidelity_report.get("requested_colors") or [])
            if str(color).strip()
        ]

        repaired = re.sub(
            r"White,\s*purple,\s*and\s*green\s+studio\s+style\s+with\s+clean\s+grooming\s+stations\.",
            "",
            repaired,
            flags=re.IGNORECASE,
        )

        if requested_name:
            title_text = cls.extract_first_tag_text(repaired, "title")
            if not title_text:
                repaired = cls.insert_before_tag(
                    repaired,
                    "head",
                    f"<title>{html.escape(requested_name, quote=False)}</title>",
                )
            elif requested_name.lower() not in title_text.lower():
                repaired = cls.replace_first_tag_text(repaired, "title", requested_name)

            h1_text = cls.extract_first_tag_text(repaired, "h1")
            if not h1_text:
                repaired = cls.insert_before_tag(
                    repaired,
                    "body",
                    f"<h1>{html.escape(requested_name, quote=False)}</h1>",
                )
            elif requested_name.lower() not in h1_text.lower():
                repaired = cls.replace_first_tag_text(repaired, "h1", requested_name)

            for token in (
                "Soggy Doggy",
                "Harry's Hot Dog Cart",
                "Flow Flowers",
                "Rico's Mobile Detailing",
                "Neon Byte Arcade",
                "Crimson Turtle Locksmiths",
            ):
                if token.lower() == requested_name.lower():
                    continue
                repaired = re.sub(
                    rf"\b{re.escape(token)}\b",
                    requested_name,
                    repaired,
                    flags=re.IGNORECASE,
                )

        if requested_type == "grooming" and not re.search(
            r"\b(groom|pet|dog|bath|wash|trim|fur|paw)\b", repaired, flags=re.IGNORECASE
        ):
            repaired = cls.insert_before_tag(
                repaired,
                "body",
                '<p class="muted">Professional pet grooming services including bath, trim, fur care, and paw tidy appointments.</p>',
            )

        if requested_colors:
            palette = cls.color_hex_map()
            primary = requested_colors[0]
            secondary = (
                requested_colors[1]
                if len(requested_colors) > 1
                else requested_colors[0]
            )
            tertiary = (
                requested_colors[2]
                if len(requested_colors) > 2
                else requested_colors[-1]
            )
            primary_hex = palette.get(primary, ["#2563eb"])[0]
            secondary_hex = palette.get(secondary, ["#22c55e"])[0]
            tertiary_hex = palette.get(tertiary, ["#f3f4f6"])[0]
            palette_comment = " ".join(requested_colors)
            style_patch = (
                '<style id="xv7-fidelity-repair">'
                f"/* requested palette: {palette_comment} */"
                f":root{{--accent:{primary_hex};--accent-2:{secondary_hex};--accent-3:{tertiary_hex};}}"
                "body{background:linear-gradient(135deg,var(--accent),var(--accent-2));}"
                ".hero,.panel{border-color:var(--accent-2);}"
                ".button.primary{background:linear-gradient(135deg,var(--accent),var(--accent-2));}"
                ".button.secondary{border:1px solid var(--accent-2);}"
                "</style>"
            )
            repaired = cls.insert_before_tag(repaired, "head", style_patch)

            non_requested_colors = {
                "white",
                "purple",
                "pink",
                "cream",
                "red",
                "blue",
                "orange",
                "silver",
                "gold",
                "yellow",
                "green",
                "black",
            } - set(requested_colors)
            replacement = requested_colors[0]
            for color in sorted(non_requested_colors):
                repaired = re.sub(
                    rf"\b{re.escape(color)}\b",
                    replacement,
                    repaired,
                    flags=re.IGNORECASE,
                )

        return repaired

    @classmethod
    def build_local_artifact_prompt(
        cls,
        *,
        question: str,
        filename: str,
        language: str,
        previewable: bool,
        apply_requested: bool,
        business_name: str,
        style_hints: dict[str, list[str]],
        layout_hints: list[str],
        strict_retry: bool,
        retry_requirements: list[str] | None = None,
    ) -> str:
        retry_requirements = retry_requirements or []
        retry_line = "Output only source code that satisfies all constraints below."
        if strict_retry:
            retry_line = "This is a retry because the first draft failed validation. Missing requirements: fix every missing requirement explicitly."
            if retry_requirements:
                retry_line += (
                    " Missing requirements: " + "; ".join(retry_requirements) + "."
                )

        category = CodeArtifactBuilder.artifact_business_category(
            question, business_name
        )
        category_brief = {
            "locksmith": "Locksmith direction: urgent trust-first security layout with lockout CTA, trust badges, and service cards.",
            "florist": "Florist direction: elegant floral tone with bouquet-oriented sections and refined typography.",
            "detailing": "Detailing direction: automotive shine/finish framing with package cards and conversion-focused CTAs.",
            "arcade": "Arcade direction: neon retro atmosphere with game-grid energy and high-score language.",
            "hot_dog_cart": "Hot dog cart direction: street-food clarity with menu highlights and quick-order focus.",
            "generic": "Direction: adapt visual language to the specific business request.",
        }.get(
            category,
            "Direction: adapt visual language to the specific business request.",
        )
        colors = ", ".join(style_hints.get("colors", [])) or "none specified"
        styles = ", ".join(style_hints.get("styles", [])) or "none specified"
        layout = "; ".join(layout_hints) or "none specified"

        return (
            f"Generate one {language} code artifact for filename {filename}.\n"
            f"Request summary: {question.strip()}\n"
            f"Business/site name: {business_name}\n"
            f"Requested colors: {colors}\n"
            f"Requested style/font mood: {styles}\n"
            f"Requested layout/content hints: {layout}\n"
            f"Industry direction: {category_brief}\n"
            f"Previewable requested: {str(previewable).lower()}\n"
            f"Apply to repo requested: {str(apply_requested).lower()} (must remain false in artifact metadata and never mutate repo)\n"
            "Hard constraints:\n"
            "- Return ONLY raw source code; no markdown fences and no explanation.\n"
            "- No file writes, no repo mutation, no apply behavior.\n"
            "- No tracking code.\n"
            "- No remote assets, no remote scripts, no remote fonts, no remote images.\n"
            "- No external script tags.\n"
            "- Must include the exact business/site name text in visible content.\n"
            "- Must reflect requested colors/style when provided.\n"
            "- Avoid generic repeated hero copy; do not reuse the same hero phrase/layout across different industries.\n"
            "- Must not include unrelated business names from earlier prompts.\n"
            "- If language is html: return a complete single-file document including <!doctype html>, inline CSS, and no external dependencies.\n"
            f"{retry_line}\n"
        )

    @staticmethod
    def remediation_for_validation_reason(reason: str) -> str:
        mapping = {
            "empty_content": "return non-empty source code",
            "markdown_fence_detected": "remove markdown code fences",
            "content_length_out_of_bounds": "keep output concise but complete",
            "external_script_tag_detected": "remove external script tags",
            "remote_url_detected": "remove all remote URLs/assets",
            "business_name_missing": "include the exact business name text",
            "color_hints_missing": "include requested color cues in CSS/style",
            "style_hints_missing": "include requested mood/style keywords in copy or CSS",
            "stale_business_leak_detected": "remove unrelated prior business names",
            "html_shell_missing": "return complete HTML document shell",
            "inline_css_missing": "include inline <style> CSS",
            "generic_business_name_fallback_detected": "use the requested business name instead of Local Business Website",
            "crimson_locksmith_language_missing": "include locksmith/security/key/lock/emergency/lockout language",
            "crimson_urgency_trust_copy_missing": "include urgent and trustworthy service copy",
            "crimson_color_black_missing": "include black/dark styling cues",
            "crimson_color_red_missing": "include red accent styling cues",
            "crimson_color_silver_missing": "include silver/gray/metal styling cues",
            "crimson_irrelevant_copy_detected": "remove irrelevant non-locksmith business copy",
            "grooming_language_missing": "include pet grooming, dog, bath, trim, fur, or paw language",
            "grooming_irrelevant_copy_detected": "remove unrelated non-grooming business copy",
            "generic_hero_reuse_detected": "replace generic repeated hero phrasing with industry-specific copy",
            "revision_content_unchanged": "modify content per requested revision and return full replacement",
        }
        return mapping.get(reason, f"fix validation issue: {reason}")

    @staticmethod
    def strip_markdown_fences(content: str) -> str:
        stripped = content.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def extract_first_tag_text(content: str, tag: str) -> str | None:
        match = re.search(
            rf"<{tag}[^>]*>(.*?)</{tag}>", content, flags=re.IGNORECASE | re.DOTALL
        )
        if not match:
            return None
        raw = re.sub(r"<[^>]+>", "", match.group(1))
        value = html.unescape(re.sub(r"\s+", " ", raw)).strip()
        return value or None

    @staticmethod
    def replace_first_tag_text(content: str, tag: str, replacement: str) -> str:
        escaped = html.escape(replacement, quote=False)
        pattern = re.compile(
            rf"(<{tag}[^>]*>)(.*?)(</{tag}>)", flags=re.IGNORECASE | re.DOTALL
        )
        return pattern.sub(rf"\1{escaped}\3", content, count=1)

    @staticmethod
    def insert_before_tag(content: str, closing_tag: str, snippet: str) -> str:
        pattern = re.compile(rf"</{re.escape(closing_tag)}>", flags=re.IGNORECASE)
        if pattern.search(content):
            return pattern.sub(f"{snippet}</{closing_tag}>", content, count=1)
        return content + snippet
