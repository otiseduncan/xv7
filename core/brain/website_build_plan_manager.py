"""Website build planning composition helpers.

This module is intentionally standalone during the Code 22 split. It composes
already-normalized planning outputs into a deterministic JSON-safe payload and
does not render HTML, write files, or call external tools.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict


class ProjectPlan(TypedDict):
    name: str
    slug: str


class StylePlan(TypedDict, total=False):
    colors: list[str]
    tone: str
    typography: str
    notes: list[str]


class CallsToActionPlan(TypedDict, total=False):
    primary: str
    secondary: list[str]


class ContactPlan(TypedDict, total=False):
    phone: str
    email: str
    address: str
    hours: str


class SeoPlan(TypedDict, total=False):
    title: str
    description: str
    keywords: list[str]


class ContentBlockPlanItem(TypedDict, total=False):
    id: str
    slug: str
    kind: str
    label: str
    source: str


class ContentBlockPlan(TypedDict, total=False):
    profile: str
    blocks: list[ContentBlockPlanItem]


class PageRoute(TypedDict):
    slug: str
    path: str
    route: str


class BundlePlan(TypedDict, total=False):
    entrypoint: str
    html_files: list[str]
    asset_files: list[str]
    page_routes: list[PageRoute]
    warnings: list[str]


class WebsiteBuildPlanPayload(TypedDict):
    project: ProjectPlan
    business_type: str
    pages: list[str]
    sections: list[str]
    style: StylePlan
    calls_to_action: CallsToActionPlan
    contact: ContactPlan
    seo: SeoPlan
    content_blocks: ContentBlockPlan
    bundle: BundlePlan
    warnings: list[str]
    ready: bool


class WebsiteBuildPlanManager:
    """Compose deterministic website build plan payloads."""

    @staticmethod
    def _clean_string(value: str | None) -> str:
        return str(value or "").strip()

    @classmethod
    def _dedupe_strings(cls, values: Sequence[str] | None) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values or ():
            normalized = cls._clean_string(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    @classmethod
    def _dedupe_warnings(cls, values: Sequence[str] | None) -> list[str]:
        return cls._dedupe_strings(values)

    @staticmethod
    def _style_plan(style_plan: StylePlan | None) -> StylePlan:
        if style_plan is None:
            return {}
        style: StylePlan = {}
        colors = WebsiteBuildPlanManager._dedupe_strings(style_plan.get("colors"))
        notes = WebsiteBuildPlanManager._dedupe_strings(style_plan.get("notes"))
        if colors:
            style["colors"] = colors
        tone = WebsiteBuildPlanManager._clean_string(style_plan.get("tone"))
        if tone:
            style["tone"] = tone
        typography = WebsiteBuildPlanManager._clean_string(style_plan.get("typography"))
        if typography:
            style["typography"] = typography
        if notes:
            style["notes"] = notes
        return style

    @staticmethod
    def _cta_plan(cta_plan: CallsToActionPlan | None) -> CallsToActionPlan:
        if cta_plan is None:
            return {}
        plan: CallsToActionPlan = {}
        primary = WebsiteBuildPlanManager._clean_string(cta_plan.get("primary"))
        secondary = WebsiteBuildPlanManager._dedupe_strings(cta_plan.get("secondary"))
        if primary:
            plan["primary"] = primary
        if secondary:
            plan["secondary"] = secondary
        return plan

    @staticmethod
    def _contact_plan(contact_plan: ContactPlan | None) -> ContactPlan:
        if contact_plan is None:
            return {}
        plan: ContactPlan = {}
        phone = WebsiteBuildPlanManager._clean_string(contact_plan.get("phone"))
        email = WebsiteBuildPlanManager._clean_string(contact_plan.get("email"))
        address = WebsiteBuildPlanManager._clean_string(contact_plan.get("address"))
        hours = WebsiteBuildPlanManager._clean_string(contact_plan.get("hours"))
        if phone:
            plan["phone"] = phone
        if email:
            plan["email"] = email
        if address:
            plan["address"] = address
        if hours:
            plan["hours"] = hours
        return plan

    @staticmethod
    def _seo_plan(seo_plan: SeoPlan | None) -> SeoPlan:
        if seo_plan is None:
            return {}
        plan: SeoPlan = {}
        title = WebsiteBuildPlanManager._clean_string(seo_plan.get("title"))
        description = WebsiteBuildPlanManager._clean_string(seo_plan.get("description"))
        keywords = WebsiteBuildPlanManager._dedupe_strings(seo_plan.get("keywords"))
        if title:
            plan["title"] = title
        if description:
            plan["description"] = description
        if keywords:
            plan["keywords"] = keywords
        return plan

    @staticmethod
    def _content_block_plan(
        content_block_plan: ContentBlockPlan | None,
    ) -> ContentBlockPlan:
        if content_block_plan is None:
            return {"profile": "", "blocks": []}
        blocks: list[ContentBlockPlanItem] = []
        seen: set[str] = set()
        for block in content_block_plan.get("blocks", []):
            key = block.get("id") or block.get("slug") or block.get("kind")
            if not key or key in seen:
                continue
            seen.add(key)
            planned_block: ContentBlockPlanItem = {}
            block_id = WebsiteBuildPlanManager._clean_string(block.get("id"))
            slug = WebsiteBuildPlanManager._clean_string(block.get("slug"))
            kind = WebsiteBuildPlanManager._clean_string(block.get("kind"))
            label = WebsiteBuildPlanManager._clean_string(block.get("label"))
            source = WebsiteBuildPlanManager._clean_string(block.get("source"))
            if block_id:
                planned_block["id"] = block_id
            if slug:
                planned_block["slug"] = slug
            if kind:
                planned_block["kind"] = kind
            if label:
                planned_block["label"] = label
            if source:
                planned_block["source"] = source
            blocks.append(planned_block)
        return {
            "profile": WebsiteBuildPlanManager._clean_string(
                content_block_plan.get("profile")
            ),
            "blocks": blocks,
        }

    @staticmethod
    def _bundle_plan(bundle_plan: BundlePlan | None) -> BundlePlan:
        if bundle_plan is None:
            return {
                "entrypoint": "",
                "html_files": [],
                "asset_files": [],
                "page_routes": [],
                "warnings": [],
            }
        page_routes: list[PageRoute] = []
        for route in bundle_plan.get("page_routes", []):
            page_route: PageRoute = {
                "slug": WebsiteBuildPlanManager._clean_string(route.get("slug")),
                "path": WebsiteBuildPlanManager._clean_string(route.get("path")),
                "route": WebsiteBuildPlanManager._clean_string(route.get("route")),
            }
            if page_route["slug"] or page_route["path"] or page_route["route"]:
                page_routes.append(page_route)
        return {
            "entrypoint": WebsiteBuildPlanManager._clean_string(
                bundle_plan.get("entrypoint")
            ),
            "html_files": WebsiteBuildPlanManager._dedupe_strings(
                bundle_plan.get("html_files")
            ),
            "asset_files": WebsiteBuildPlanManager._dedupe_strings(
                bundle_plan.get("asset_files")
            ),
            "page_routes": page_routes,
            "warnings": WebsiteBuildPlanManager._dedupe_warnings(
                bundle_plan.get("warnings")
            ),
        }

    @classmethod
    def build_plan(
        cls,
        *,
        project_name: str | None = None,
        project_slug: str | None = None,
        business_type: str | None = None,
        pages: Sequence[str] | None = None,
        sections: Sequence[str] | None = None,
        style_plan: StylePlan | None = None,
        cta_plan: CallsToActionPlan | None = None,
        contact_plan: ContactPlan | None = None,
        seo_plan: SeoPlan | None = None,
        content_block_plan: ContentBlockPlan | None = None,
        bundle_plan: BundlePlan | None = None,
        warnings: Sequence[str] | None = None,
    ) -> WebsiteBuildPlanPayload:
        project = {
            "name": cls._clean_string(project_name),
            "slug": cls._clean_string(project_slug),
        }
        content_blocks = cls._content_block_plan(content_block_plan)
        bundle = cls._bundle_plan(bundle_plan)

        plan_warnings = [
            *cls._dedupe_warnings(warnings),
            *bundle["warnings"],
        ]
        if not project["slug"]:
            plan_warnings.append("missing project slug")
        normalized_pages = cls._dedupe_strings(pages)
        if not normalized_pages:
            plan_warnings.append("missing pages")
        if not content_blocks["blocks"]:
            plan_warnings.append("missing content blocks")
        if not bundle["entrypoint"]:
            plan_warnings.append("missing bundle entrypoint")

        return {
            "project": project,
            "business_type": cls._clean_string(business_type),
            "pages": normalized_pages,
            "sections": cls._dedupe_strings(sections),
            "style": cls._style_plan(style_plan),
            "calls_to_action": cls._cta_plan(cta_plan),
            "contact": cls._contact_plan(contact_plan),
            "seo": cls._seo_plan(seo_plan),
            "content_blocks": content_blocks,
            "bundle": bundle,
            "warnings": cls._dedupe_warnings(plan_warnings),
            "ready": bool(
                project["slug"]
                and normalized_pages
                and content_blocks["blocks"]
                and bundle["entrypoint"]
            ),
        }
