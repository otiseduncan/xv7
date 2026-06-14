"""Website contact-information planning helpers.

This module is intentionally standalone in Code 22. It does not mutate the
runtime answer contract; it gives contact extraction and contact CTA planning a
small, testable manager before any future delegation work.
"""

from __future__ import annotations

import re
from typing import Final


_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w.+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![\w+-])"
)
_PHONE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)"
)
_ADDRESS_HINT_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(address|location|located at|visit us|come see us|storefront)\b",
    re.IGNORECASE,
)
_CONTACT_FORM_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(contact form|lead form|quote form|booking form|intake form)\b",
    re.IGNORECASE,
)
_SOCIAL_HINT_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(facebook|instagram|tiktok|linkedin|youtube|social media|social links?)\b",
    re.IGNORECASE,
)


class WebsiteContactPlanManager:
    """Extract and normalize website contact details from prompts."""

    @staticmethod
    def dedupe_preserve_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = value.strip().rstrip(".,;:!?)]}")
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result

    @staticmethod
    def extract_emails(prompt: str) -> list[str]:
        return WebsiteContactPlanManager.dedupe_preserve_order(
            [match.group(1) for match in _EMAIL_RE.finditer(prompt)]
        )

    @staticmethod
    def normalize_phone_number(value: str) -> str:
        digits = re.sub(r"\D+", "", value)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            return value.strip()
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

    @staticmethod
    def extract_phone_numbers(prompt: str) -> list[str]:
        numbers = [
            WebsiteContactPlanManager.normalize_phone_number(match.group(0))
            for match in _PHONE_RE.finditer(prompt)
        ]
        return WebsiteContactPlanManager.dedupe_preserve_order(numbers)

    @staticmethod
    def has_address_hint(prompt: str) -> bool:
        return bool(_ADDRESS_HINT_RE.search(prompt))

    @staticmethod
    def wants_contact_form(prompt: str) -> bool:
        return bool(_CONTACT_FORM_RE.search(prompt))

    @staticmethod
    def wants_social_links(prompt: str) -> bool:
        return bool(_SOCIAL_HINT_RE.search(prompt))

    @staticmethod
    def build_mailto(email: str) -> str:
        return f"mailto:{email.strip()}"

    @staticmethod
    def build_tel(phone_number: str) -> str:
        digits = re.sub(r"\D+", "", phone_number)
        if len(digits) == 10:
            return f"tel:+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"tel:+{digits}"
        return "#contact"

    @staticmethod
    def infer_contact_methods(prompt: str) -> list[str]:
        methods: list[str] = []
        if WebsiteContactPlanManager.extract_emails(prompt):
            methods.append("email")
        if WebsiteContactPlanManager.extract_phone_numbers(prompt):
            methods.append("phone")
        if WebsiteContactPlanManager.has_address_hint(prompt):
            methods.append("address")
        if WebsiteContactPlanManager.wants_contact_form(prompt):
            methods.append("form")
        if WebsiteContactPlanManager.wants_social_links(prompt):
            methods.append("social")
        return methods or ["contact"]

    @staticmethod
    def build_plan(prompt: str) -> dict[str, object]:
        emails = WebsiteContactPlanManager.extract_emails(prompt)
        phones = WebsiteContactPlanManager.extract_phone_numbers(prompt)
        methods = WebsiteContactPlanManager.infer_contact_methods(prompt)
        primary_email = emails[0] if emails else ""
        primary_phone = phones[0] if phones else ""
        return {
            "emails": emails,
            "phone_numbers": phones,
            "primary_email": primary_email,
            "primary_phone": primary_phone,
            "mailto": WebsiteContactPlanManager.build_mailto(primary_email)
            if primary_email
            else "#contact",
            "tel": WebsiteContactPlanManager.build_tel(primary_phone)
            if primary_phone
            else "#contact",
            "has_address_hint": WebsiteContactPlanManager.has_address_hint(prompt),
            "wants_contact_form": WebsiteContactPlanManager.wants_contact_form(prompt),
            "wants_social_links": WebsiteContactPlanManager.wants_social_links(prompt),
            "methods": methods,
        }
