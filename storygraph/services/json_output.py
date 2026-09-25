"""Strict JSON envelope normalization for compatible model text outputs."""

import re


def unwrap_json_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        match = re.fullmatch(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```", cleaned, re.DOTALL)
        if match is None or "```" in match[1]:
            raise ValueError("Model JSON output must use one complete JSON fence")
        return match[1].strip()
    return cleaned
