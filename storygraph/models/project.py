"""Project-level generation settings."""

from __future__ import annotations

from typing import Literal

from storygraph.core.errors import ContractError


OutputLanguage = Literal["zh-CN", "en-US"]
CrossLanguagePolicy = Literal["project_only", "explicit_reference"]
SUPPORTED_OUTPUT_LANGUAGES = {"zh-CN", "en-US"}
DEFAULT_OUTPUT_LANGUAGE: OutputLanguage = "zh-CN"


def validate_output_language(value: object) -> OutputLanguage:
    if value not in SUPPORTED_OUTPUT_LANGUAGES:
        raise ContractError(
            "Project output_language must be one of: zh-CN, en-US."
        )
    return value  # type: ignore[return-value]


def localized(output_language: OutputLanguage, *, zh: str, en: str) -> str:
    return zh if output_language == "zh-CN" else en
