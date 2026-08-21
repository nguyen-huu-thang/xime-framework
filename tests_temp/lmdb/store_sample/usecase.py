"""Use case nhận bảng qua constructor injection, y hệt một repository."""

from __future__ import annotations

from .tables import LoginRateLimit, WebhookDedup

MAX_FAILURES = 3


class TooManyFailures(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class LoginUseCase:
    def __init__(self, rate_limit: LoginRateLimit) -> None:
        self._rate_limit = rate_limit

    async def login(self, username: str, ip: str, password: str) -> str:
        key = f"{username}|{ip}"

        failures = await self._rate_limit.get(key) or 0
        if failures >= MAX_FAILURES:
            # Thoát TRƯỚC khi incr: ghi là đặt lại hạn, nên đếm tiếp trong lúc
            # đang bị khoá sẽ đẩy hạn ra xa mãi.
            raise TooManyFailures()

        if password != "dung-mat-khau":
            await self._rate_limit.incr(key)
            raise InvalidCredentials()

        await self._rate_limit.delete(key)
        return username


class WebhookUseCase:
    def __init__(self, dedup: WebhookDedup) -> None:
        self._dedup = dedup
        self.handled: list[str] = []

    async def handle(self, event_id: str) -> bool:
        if not await self._dedup.set_if_absent(event_id, b"1"):
            return False
        self.handled.append(event_id)
        return True
