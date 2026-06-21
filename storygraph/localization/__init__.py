"""Localization resources for bundled StoryGraph fixtures."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


DEFAULT_DEMO_LOCALE = "en-US"
SUPPORTED_DEMO_LOCALES = {"en-US", "zh-CN"}


def load_demo_locale(locale: str | None = None) -> dict[str, Any]:
    normalized = _normalize_locale(locale)
    resource = resources.files(__name__).joinpath(f"demo.{normalized}.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def _normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_DEMO_LOCALE
    normalized = locale.replace("_", "-")
    if normalized in SUPPORTED_DEMO_LOCALES:
        return normalized
    language = normalized.split("-", 1)[0].lower()
    if language == "zh":
        return "zh-CN"
    return DEFAULT_DEMO_LOCALE
