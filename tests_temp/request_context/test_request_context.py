"""
Test RequestContext:
  - set / get / delete / clear / all
  - default value khi key không tồn tại
  - __contains__ (in operator)
  - isolation giữa các async task
  - nhiều key độc lập nhau
"""
import asyncio
from typing import Any

import pytest

from core.context import request_context


# ---------------------------------------------------------------------------
# set / get
# ---------------------------------------------------------------------------

def test_get_returns_none_by_default():
    assert request_context.get("missing") is None


def test_get_returns_custom_default():
    assert request_context.get("missing", default="fallback") == "fallback"


def test_set_and_get():
    request_context.set("trace_id", "abc-123")
    assert request_context.get("trace_id") == "abc-123"


def test_set_overwrites_existing():
    request_context.set("lang", "en")
    request_context.set("lang", "vi")
    assert request_context.get("lang") == "vi"


def test_set_accepts_any_value_type():
    request_context.set("user_id", 42)
    request_context.set("flags", {"beta": True})
    request_context.set("tags", ["a", "b"])

    assert request_context.get("user_id") == 42
    assert request_context.get("flags") == {"beta": True}
    assert request_context.get("tags") == ["a", "b"]


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def test_delete_removes_key():
    request_context.set("key", "value")
    request_context.delete("key")
    assert request_context.get("key") is None


def test_delete_nonexistent_key_is_noop():
    request_context.delete("nonexistent")  # không raise


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

def test_clear_removes_all_keys():
    request_context.set("a", 1)
    request_context.set("b", 2)
    request_context.clear()

    assert request_context.get("a") is None
    assert request_context.get("b") is None


# ---------------------------------------------------------------------------
# all()
# ---------------------------------------------------------------------------

def test_all_returns_copy_of_dict():
    request_context.set("x", 10)
    request_context.set("y", 20)

    snapshot = request_context.all()
    assert snapshot == {"x": 10, "y": 20}

    # Thay đổi snapshot không ảnh hưởng context thật
    snapshot["x"] = 999
    assert request_context.get("x") == 10


def test_all_returns_empty_dict_when_clear():
    assert request_context.all() == {}


# ---------------------------------------------------------------------------
# __contains__
# ---------------------------------------------------------------------------

def test_contains_operator():
    request_context.set("locale", "vi-VN")
    assert "locale" in request_context
    assert "missing" not in request_context


# ---------------------------------------------------------------------------
# __len__
# ---------------------------------------------------------------------------

def test_len_empty():
    assert len(request_context) == 0


def test_len_after_set():
    request_context.set("a", 1)
    request_context.set("b", 2)
    assert len(request_context) == 2


def test_len_after_delete():
    request_context.set("x", 10)
    request_context.delete("x")
    assert len(request_context) == 0


def test_len_after_clear():
    request_context.set("y", 99)
    request_context.clear()
    assert len(request_context) == 0


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------

def test_repr_empty():
    assert repr(request_context) == "RequestContext({})"


def test_repr_with_data():
    request_context.set("trace_id", "xyz")
    assert repr(request_context) == "RequestContext({'trace_id': 'xyz'})"


# ---------------------------------------------------------------------------
# Isolation giữa các async task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_task_isolation():
    """Task A set context không ảnh hưởng Task B."""
    results: dict[str, Any] = {}

    async def task_a():
        request_context.set("trace_id", "trace-A")
        await asyncio.sleep(0)
        results["a"] = request_context.get("trace_id")

    async def task_b():
        await asyncio.sleep(0)
        results["b"] = request_context.get("trace_id")  # chưa set → None

    await asyncio.gather(task_a(), task_b())

    assert results["a"] == "trace-A"
    assert results["b"] is None
