"""Website business type inference helpers for generated site artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

DEFAULT_BUSINESS_TYPE = "general_business"


@dataclass(frozen=True)
class WebsiteBusinessType:
    """Normalized business type inference payload."""

    kind: str
    label: str
    confidence: str
    matched_hints: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "label": self.label,
            "confidence": self.confidence,
            "matched_hints": list(self.matched_hints),
        }


class WebsiteBusinessTypeManager:
    """Pure helpers for inferring coarse website business categories."""

    BUSINESS_TYPES: ClassVar[dict[str, dict[str, object]]] = {
        "food_cart": {
            "label": "Food cart",
            "hints": ("hot dog", "hotdog", "food cart", "food truck", "cart"),
        },
        "restaurant": {
            "label": "Restaurant",
            "hints": ("restaurant", "cafe", "menu", "catering", "diner"),
        },
        "vape_cbd": {
            "label": "Vape and CBD shop",
            "hints": ("vape", "cbd", "smoke shop", "dispensary"),
        },
        "automotive_adas": {
            "label": "Automotive ADAS service",
            "hints": (
                "adas",
                "calibration",
                "diagnostic",
                "diagnostics",
                "auto repair",
                "body shop",
            ),
        },
        "church_ministry": {
            "label": "Church or ministry",
            "hints": ("church", "ministry", "bible", "sermon", "fellowship"),
        },
        "cybersecurity_it": {
            "label": "Cybersecurity or IT service",
            "hints": (
                "cybersecurity",
                "cyber security",
                "it service",
                "automation",
                "network security",
            ),
        },
        "retail": {
            "label": "Retail business",
            "hints": ("shop", "store", "retail", "products", "inventory"),
        },
        DEFAULT_BUSINESS_TYPE: {
            "label": "General business",
            "hints": (),
        },
    }

    @staticmethod
    def normalize_text(value: str | None) -> str:
        """Return lowercase searchable text with normalized whitespace."""

        text = str(value or "").casefold().replace("&", " and ")
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _contains_hint(cls, normalized_prompt: str, hint: str) -> bool:
        normalized_hint = cls.normalize_text(hint)
        if not normalized_hint:
            return False
        pattern = re.compile(rf"(?<!\w){re.escape(normalized_hint)}(?!\w)")
        return bool(pattern.search(normalized_prompt))

    @classmethod
    def detect_hints(cls, prompt: str | None) -> list[str]:
        """Return unique matched hint phrases in priority order."""

        normalized_prompt = cls.normalize_text(prompt)
        matches: list[str] = []
        seen: set[str] = set()
        for config in cls.BUSINESS_TYPES.values():
            hints = config.get("hints", ())
            for hint in hints:
                if not isinstance(hint, str):
                    continue
                key = cls.normalize_text(hint)
                if key in seen:
                    continue
                if cls._contains_hint(normalized_prompt, hint):
                    seen.add(key)
                    matches.append(hint)
        return matches

    @classmethod
    def infer_business_type(cls, prompt: str | None) -> WebsiteBusinessType:
        """Infer the first matching business type from prompt hints."""

        normalized_prompt = cls.normalize_text(prompt)
        matched_hints = cls.detect_hints(prompt)
        for kind, config in cls.BUSINESS_TYPES.items():
            if kind == DEFAULT_BUSINESS_TYPE:
                continue
            hints = tuple(str(hint) for hint in config.get("hints", ()))
            local_matches = tuple(
                hint for hint in hints if cls._contains_hint(normalized_prompt, hint)
            )
            if local_matches:
                confidence = "high" if len(local_matches) > 1 else "medium"
                return WebsiteBusinessType(
                    kind=kind,
                    label=str(config.get("label", kind.replace("_", " ").title())),
                    confidence=confidence,
                    matched_hints=local_matches,
                )

        default_config = cls.BUSINESS_TYPES[DEFAULT_BUSINESS_TYPE]
        return WebsiteBusinessType(
            kind=DEFAULT_BUSINESS_TYPE,
            label=str(default_config["label"]),
            confidence="low",
            matched_hints=tuple(matched_hints),
        )

    @classmethod
    def build_business_type_payload(cls, prompt: str | None) -> dict[str, object]:
        """Build a JSON-safe business type payload."""

        return cls.infer_business_type(prompt).as_dict()
