"""Bảng của một app mẫu - khai đúng như tài liệu người dùng hướng dẫn."""

from __future__ import annotations

from xime.starters.lmdb import CounterStore, Store


class LoginRateLimit(
    CounterStore,
    name="login-rate-limit",
    ttl=900,
    parts=4,
):
    """Đếm số lần đăng nhập sai theo (tài khoản, IP)."""


class WebhookDedup(Store, name="webhook-dedup", ttl=86400):
    """Chống xử lý lặp một sự kiện webhook."""
