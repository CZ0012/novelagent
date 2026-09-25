"""Exact UTF-16 spans shared by browser selection and source adoption."""

from storygraph.core.errors import ContractError


def utf16_span(text: str, start: int, end: int, expected_text: str) -> tuple[int, int]:
    if isinstance(start, bool) or isinstance(end, bool) or start < 0 or end <= start:
        raise ContractError("Invalid text selection span.")
    encoded = text.encode("utf-16-le")
    if end * 2 > len(encoded):
        raise ContractError("Text selection is outside its saved source.")
    try:
        prefix = encoded[: start * 2].decode("utf-16-le")
        selected = encoded[start * 2 : end * 2].decode("utf-16-le")
    except UnicodeError as exc:
        raise ContractError("Text selection splits a Unicode character.") from exc
    if selected != expected_text:
        raise ContractError("Text selection no longer matches its saved source.")
    return len(prefix), len(prefix) + len(selected)
