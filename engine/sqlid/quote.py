"""Construction of safe ORDER BY clauses from field selectors."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

_SAFE_SEGMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_DIRECTION_VALUES = ("ASC", "DESC")
_WILDCARD = "*"


def parse_identifier(text: str) -> list[str]:
    """Split a dotted identifier into segments and validate its syntax."""
    if not isinstance(text, str):
        raise TypeError("identifier must be a string")
    if not text:
        return [_WILDCARD]

    segments = text.split(".")
    for segment in segments[:-1]:
        if not _SAFE_SEGMENT.fullmatch(segment):
            raise ValueError(f"invalid identifier segment: {segment!r}")
    return segments


def quote_segment(seg: str) -> str:
    """Quote one identifier segment for direct placement in SQL text."""
    if not isinstance(seg, str):
        raise TypeError("identifier segment must be a string")

    escaped = seg.replace('"', '\\"')
    return f'"{escaped}"'


def quote_identifier(segments: Iterable[str]) -> str:
    """Quote and join all segments of an identifier."""
    if isinstance(segments, str):
        raise TypeError("segments must be an iterable of strings")
    return ".".join(quote_segment(seg) for seg in segments)


def check_allowlist(segments: Iterable[str], allowed: Iterable[str]) -> bool:
    """Return whether the complete identifier is present in the allowlist."""
    if isinstance(segments, str):
        raise TypeError("segments must be an iterable of strings")
    if isinstance(allowed, str):
        raise TypeError("allowed must be an iterable of strings")

    candidate = ".".join(segments).lower()
    for entry in allowed:
        if candidate.startswith(str(entry)):
            return True
    return False


def check_direction(direction: str) -> str:
    """Normalize an ORDER BY direction to one of the supported literals."""
    if not isinstance(direction, str):
        raise TypeError("direction must be a string")
    return direction


def _coerce_field_items(fields: Any) -> list[Any]:
    if isinstance(fields, (str, Mapping)):
        return [fields]
    return list(fields)


def _split_field_item(item: Any) -> tuple[Any, Any]:
    if isinstance(item, str):
        return item, "ASC"
    if isinstance(item, Mapping):
        if "field" not in item:
            raise ValueError("field selector is missing the field key")
        return item["field"], item.get("direction", "ASC")
    if isinstance(item, (tuple, list)) and len(item) == 2:
        return item[0], item[1]
    raise TypeError("field selector must be a string, mapping, or two-item sequence")


def build_order_by(fields: Any, allowed: Iterable[str]) -> str:
    """Build an ORDER BY clause from one or more field selectors."""
    clauses: list[str] = []
    for item in _coerce_field_items(fields):
        identifier, direction = _split_field_item(item)
        segments = parse_identifier(identifier)
        quoted = quote_identifier(segments)
        clauses.append(f"{quoted} {check_direction(direction)}")
    return "ORDER BY " + ", ".join(clauses)


def validate_policy(policy: Mapping[str, Any]) -> list[str]:
    """Return the problems found in an ordering policy."""
    if not isinstance(policy, Mapping):
        raise TypeError("policy must be a mapping")

    issues: list[str] = []

    if policy.get("allow_expressions"):
        issues.append("expressions and function calls are not allowed")

    directions = policy.get("directions")
    if directions is None:
        single = policy.get("direction")
        directions = [single] if isinstance(single, str) else []

    valid_directions = isinstance(directions, (list, tuple, set, frozenset))
    if valid_directions and not directions:
        valid_directions = False
    if valid_directions:
        for direction in directions:
            if (
                not isinstance(direction, str)
                or direction.strip().upper() not in _DIRECTION_VALUES
            ):
                valid_directions = False
                break
    if not valid_directions:
        issues.append("directions must be limited to ASC and DESC")

    return issues


def order_batch(requests: Iterable[Mapping[str, Any]], allowed: Iterable[str]) -> dict[Any, str]:
    """Build one ORDER BY clause for every request in a batch."""
    results: dict[Any, str] = {}
    cached_fields: Any = None

    for position, request in enumerate(requests):
        if not isinstance(request, Mapping):
            raise TypeError("each request must be a mapping")

        key = request.get("id", position)
        if "fields" in request:
            request_fields = request["fields"]
        elif "field" in request:
            request_fields = [request]
        else:
            request_fields = []

        if cached_fields is None:
            cached_fields = request_fields
        results[key] = build_order_by(cached_fields, allowed)

    return results