from __future__ import annotations

import asyncio
import logging
import struct
import time
from typing import Any

from ._env import LmdbEnvironment, is_map_resized
from ._store import _STAMP_SIZE, Store, store_registry

_log = logging.getLogger(__name__)

_STAMP = struct.Struct("<d")

# Keys removed per write transaction. Small on purpose: LMDB grants one writer
# per file, so a long sweeping write transaction would make every other process
# block its own event loop when its turn to write comes. That is the single way
# the "call straight through, no executor" decision could go wrong, so the batch
# size is part of the design and not a tuning knob.
# Số khoá xoá trong mỗi giao dịch ghi. Nhỏ có chủ đích: LMDB cho một người ghi
# trên mỗi file, nên một giao dịch ghi dài quét cả bảng sẽ khiến mọi tiến trình
# khác CHẶN EVENT LOOP của chính nó khi tới lượt ghi. Đó là cách duy nhất khiến
# quyết định "gọi thẳng, không executor" có thể hỏng.
_BATCH = 500


class StoreCleanupJob:
    """Removes expired entries so the store stops growing.

    Correctness does not depend on it: an expired entry is already invisible to
    get() and already counts as free for set_if_absent(). It only reclaims
    space, which is why it belongs to the "running it twice is merely wasteful"
    class of background work and needs no distributed lock.
    Tính đúng đắn không phụ thuộc vào nó: bản ghi hết hạn đã vô hình với get()
    và đã được tính là trống với set_if_absent(). Nó chỉ thu hồi chỗ, nên thuộc
    hạng "chạy hai lần chỉ THỪA" và không cần khoá phân tán.

    Register it like any scheduled job:

        # config/scheduler.py
        configure_scheduler(jobs=[IntervalJob(StoreCleanupJob, minutes=10)])

    ✅ Since 0.8 the scheduler is an adapter with scaling="singleton", so this
    runs on the PRIMARY process only - with nothing to declare here. Not because
    two processes would produce a wrong result (they would not), but because
    writing to LMDB is exclusive per file, so N processes sweeping means N-1 of
    them queueing for a write lock that serves no request.
    ✅ Từ 0.8, scheduler là adapter hạng đơn nhất nên việc này **chỉ chạy ở
    primary**, và không phải khai gì ở đây cả. Không phải vì hai tiến trình cho
    kết quả sai (không sai), mà vì ghi LMDB là độc quyền theo file: N tiến trình
    cùng dọn nghĩa là N-1 tiến trình xếp hàng chờ khoá ghi cho một việc không
    phục vụ request nào.

    ⭐ Đây là chỗ hạng adapter trả công: **không cờ nào trong object**, không ai
    phải nhớ tự kiểm. Framework chỉ `start()` nó ở primary, và một object không
    được gọi thì không chạy.
    """

    def __init__(self, env: LmdbEnvironment) -> None:
        self._env = env

    async def run(self) -> None:
        removed = 0
        for store in store_registry.stores():
            removed += await self._sweep_table(store)
        if removed:
            _log.info("store: cleanup removed %d expired entries", removed)

    async def _sweep_table(self, store: Store[Any]) -> int:
        removed = 0
        for part in range(store.parts):
            try:
                env = self._env.env_for(store.name, part, store.parts)
            except Exception:
                # A table this process never opened, or a store that cannot be
                # reached right now. Cleanup is opportunistic - log and move on
                # rather than take the whole job down with it.
                _log.warning(
                    "store: cleanup skipped table %r part %d", store.name, part, exc_info=True
                )
                continue
            removed += await self._sweep_partition(env, store.name, part)
        return removed

    async def _sweep_partition(self, env: Any, table: str, part: int) -> int:
        """Sweep one file batch by batch, stopping the moment a batch makes no progress.

        The batch loop MUST have a guaranteed exit, and "keep going until nothing
        expired is left" is not one: _delete_batch swallows a failed write
        transaction and returns 0, while the next scan still reports the very
        same keys as expired - so a store that cannot be written to would spin
        this loop forever at full CPU, silently. The same shape occurs harmlessly
        when every key in a batch was rewritten between the scan and the delete.
        Requiring one deletion per round covers both: progress is bounded by the
        number of keys, so the loop always terminates.
        Vòng lặp theo lô BẮT BUỘC phải có lối ra đảm bảo, và "chạy tới khi không
        còn gì hết hạn" thì không phải: _delete_batch nuốt một giao dịch ghi
        hỏng rồi trả 0, trong khi lần quét sau vẫn báo đúng những khoá đó là hết
        hạn - nên một kho không ghi được sẽ quay vòng này mãi mãi, đốt trọn một
        nhân, IM LẶNG. Cùng hình dạng đó xảy ra một cách vô hại khi mọi khoá
        trong lô vừa bị ghi lại giữa lúc quét và lúc xoá. Đòi mỗi vòng phải xoá
        được ít nhất một khoá thì phủ cả hai: tiến độ bị chặn bởi số khoá, nên
        vòng lặp luôn kết thúc.

        📌 Lỗi này do phép ĐỐI CHỨNG tìm ra, không phải do đọc lại code: lúc gỡ
        thử một phép kiểm ra để xem test nào đỏ, bộ test không đỏ mà TREO.
        """
        removed = 0
        while True:
            expired = self._collect_expired(env, table, part)
            if not expired:
                return removed
            deleted = self._delete_batch(env, expired, table, part)
            if deleted == 0:
                _log.warning(
                    "store: cleanup stopped early on table %r part %d - a batch of "
                    "%d expired keys deleted none of them. Either they were all "
                    "rewritten just now (harmless, the next run picks them up), or "
                    "the store cannot be written to.",
                    table,
                    part,
                    len(expired),
                )
                return removed
            removed += deleted
            # Yield between batches so a large table cannot monopolise the loop.
            await asyncio.sleep(0)

    def _collect_expired(self, env: Any, table: str, part: int) -> list[bytes]:
        """Read up to one batch of expired keys, holding the read transaction briefly.

        Nothing is awaited inside: an LMDB read transaction pins the snapshot it
        opened, so pages freed after it started cannot be reused while it lives.
        A transaction held across an await lives for the duration of the wait,
        not the work, and the store grows even though the data did not.
        Không await bên trong: một giao dịch đọc LMDB ghim ảnh chụp của nó, nên
        trang được giải phóng sau đó không thể tái dùng khi nó còn sống. Giao
        dịch bắc qua một `await` sống theo thời gian CHỜ chứ không theo thời
        gian làm việc, và kho phình lên dù dữ liệu thì không.
        """
        now = time.time()
        try:
            with env.begin(write=False, buffers=True) as txn:
                found: list[bytes] = []
                cursor = txn.cursor()
                for raw_key, raw_value in cursor:
                    if len(raw_value) < _STAMP_SIZE:
                        continue
                    if _STAMP.unpack_from(raw_value, 0)[0] <= now:
                        found.append(bytes(raw_key))
                        if len(found) >= _BATCH:
                            break
                return found
        except Exception as exc:  # noqa: BLE001 - re-raised as a warning below
            if is_map_resized(exc):
                self._env.adopt_external_size(env, self._env._file_path(table, part))  # noqa: SLF001
                return []
            _log.warning(
                "store: cleanup could not scan table %r part %d", table, part, exc_info=True
            )
            return []

    def _delete_batch(self, env: Any, keys: list[bytes], table: str, part: int) -> int:
        """Delete one batch, re-checking each key inside the write transaction.

        The re-check matters: between the scan and this write another process
        may have written the key afresh, and deleting it then would throw away a
        live entry - a rate-limit counter reset to zero, or a claimed lock handed
        back. Reading again under the write lock closes that window.
        Phép kiểm lại quan trọng: giữa lúc quét và lúc ghi này, tiến trình khác
        có thể đã ghi lại khoá đó, xoá đi là vứt một bản ghi còn sống - bộ đếm
        hãm nhịp về 0, hoặc một khoá đã chiếm bị trả lại.
        """
        now = time.time()
        deleted = 0
        try:
            with env.begin(write=True, buffers=True) as txn:
                for raw_key in keys:
                    stored = txn.get(raw_key)
                    if stored is None or len(stored) < _STAMP_SIZE:
                        continue
                    if _STAMP.unpack_from(stored, 0)[0] > now:
                        continue  # rewritten since the scan - leave it alone
                    if txn.delete(raw_key):
                        deleted += 1
        except Exception:  # noqa: BLE001 - cleanup must not take the app down
            _log.warning(
                "store: cleanup could not delete from table %r part %d",
                table,
                part,
                exc_info=True,
            )
        return deleted
