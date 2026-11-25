"""Public contract tests for engine.sqlid.quote."""

from __future__ import annotations

import pytest

from engine.sqlid.quote import (
    build_order_by,
    check_allowlist,
    check_direction,
    order_batch,
    quote_identifier,
    quote_segment,
)


def test_single_segment_identifier_is_quoted() -> None:
    assert quote_segment("users") == '"users"'
    assert quote_identifier(["users"]) == '"users"'
    assert quote_segment('user"name') == '"user""name"'


def test_allowlist_accepts_configured_field() -> None:
    assert check_allowlist(["users"], ["users"]) is True
    assert check_allowlist(["Users"], ["Users"]) is True


def test_order_direction_is_limited_to_fixed_literals() -> None:
    assert check_direction("ASC") == "ASC"
    assert check_direction("desc") == "DESC"
    with pytest.raises(ValueError):
        check_direction("ASC, (SELECT 1)")


def test_injected_field_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_order_by(['name" OR 1=1 --'], ["name"])


def test_batch_requests_are_independent() -> None:
    requests = [
        {"id": "first", "fields": ["name"]},
        {"id": "second", "fields": ["created_at"]},
    ]
    result = order_batch(requests, ["name", "created_at"])
    assert result["first"] == 'ORDER BY "name" ASC'
    assert result["second"] == 'ORDER BY "created_at" ASC'