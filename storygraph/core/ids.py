"""Stable ID helpers."""

from __future__ import annotations

import re
from uuid import uuid4


_INVALID_ID_CHARS = re.compile(r"[^a-zA-Z0-9_:-]+")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def slug_id(prefix: str, value: str) -> str:
    slug = _INVALID_ID_CHARS.sub("_", value.strip().lower()).strip("_")
    return f"{prefix}_{slug or uuid4().hex[:8]}"

