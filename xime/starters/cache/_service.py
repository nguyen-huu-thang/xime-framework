from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheService(Protocol):
    """
    Backend-neutral contract for a key/value cache.

    ⭐ Từ 0.8 có ba chỗ để đặt trạng thái dùng chung, và chúng **không thay thế
    nhau**. Ranh giới gọn nhất:

    > **Mọi thứ framework tự cấp - `RefData`, `Store`, `ProcessLink` - là MỘT
    > MÁY, luôn luôn. Cần nhiều máy cùng thấy thì đó là lựa chọn của ứng dụng,
    > và nó đi qua `CacheService`.**

    ⚠ Đừng đọc `Store` (LMDB) như bản thay thế của cái này. `Store` đóng đúng
    **một tầng** của một lỗ hổng: hãm nhịp giữ trong RAM tiến trình thì hạn mức
    bị nhân theo **số tiến trình**, và `Store` đưa nó về một bảng chung **trên
    một máy**. Chạy hai máy sau bộ cân bằng tải thì hạn mức lại nhân theo **số
    máy** - cùng cách hỏng, chỉ nhỏ hơn. Và **chia shard không giải được**:
    shard cắt theo `org_id`, còn hãm nhịp khoá theo IP hoặc tên đăng nhập.

    ⛔ Chiều ngược lại cũng đúng: đừng dùng cái này cho thứ `Store` làm được -
    một vòng mạng cho mỗi lần đọc là giá thật trả cho thứ nằm sẵn trong RAM
    cùng máy. Bảng chọn đầy đủ: `docs/{vn,en}/starters.md`.

    Define this once; bind a concrete backend in config/dependency.py, e.g.

        dependency.bind({ CacheService: RedisCacheService })

    and inject CacheService wherever caching is needed:

        class TokenService:
            def __init__(self, cache: CacheService) -> None:
                self._cache = cache

    Values are raw bytes by design. The framework does not impose a
    serialization policy - callers encode/decode (JSON, pickle, msgpack, plain
    UTF-8) however their domain requires. This keeps the contract small and the
    backend dumb.
    Giá trị là bytes thô có chủ đích. Framework không áp đặt serialize - caller
    tự encode/decode. Giữ contract gọn và backend "ngu".

    TTL is expressed in whole seconds; None means the entry never expires.
    TTL tính bằng giây nguyên; None nghĩa là không hết hạn.
    """

    async def get(self, key: str) -> bytes | None:
        """Return the stored value, or None if the key is absent/expired."""
        ...

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        """Store value under key. If ttl is given, the entry expires after
        that many seconds; otherwise it persists until deleted."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the key. A no-op if the key does not exist."""
        ...

    async def exists(self, key: str) -> bool:
        """Return True if the key is present (and not expired)."""
        ...
