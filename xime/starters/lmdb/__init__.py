"""Inter-process store on LMDB, for state that has no durable source.

What belongs here: rate-limit counters, passkey challenges, webhook
deduplication - state that several processes of one application must agree on,
that would be wrong to keep in one process's memory, and that the application
still works without after a reboot.
Thứ thuộc về đây: bộ đếm hãm nhịp, thử thách passkey, chống lặp webhook -
trạng thái mà nhiều tiến trình của một app phải thống nhất, sai nếu giữ trong
bộ nhớ một tiến trình, và app vẫn chạy đúng khi nó rỗng sau lúc máy khởi động
lại.

⛔ Scope is ONE machine, always. Several machines are handled by sharding, not
by a shared store.
⛔ Phạm vi là MỘT máy, luôn luôn. Nhiều máy đã giải bằng chia shard.

Usage:

    # config/dependency.py
    dependency.scan("xime.starters.lmdb", "app.infrastructure.store")

    # app/infrastructure/store/LoginRateLimit.py
    from xime.starters.lmdb import CounterStore

    class LoginRateLimit(CounterStore, name="login-rate-limit", ttl=900, parts=4):
        '''Counts failed logins per (account, ip).'''

    # application.yml
    lmdb:
      path: /dev/shm/my-service-store   # Linux: straight on RAM
      map_size: 64MB                    # starting size of EACH partition file
      total_max: 1GB                    # hard ceiling across the whole store

Install with: pip install 'xime[lmdb]'
"""

from ._cleanup import StoreCleanupJob
from ._config import LmdbConfig as LmdbConfig
from ._env import LmdbEnvironment
from ._errors import StoreError as StoreError
from ._errors import StoreFullError as StoreFullError
from ._errors import StoreUnavailableError as StoreUnavailableError
from ._store import DEFAULT_TTL, NEVER, CounterStore, Store, store_registry

# ⚠ In a starter package, `__all__` is NOT just the export list: it is also what
# the DI scanner registers for dependency.scan("xime.starters.lmdb") - it honours
# `__all__` exclusively when a package declares one. So a concrete class listed
# here becomes a singleton the container has to BUILD.
# ⚠ Trong một package starter, `__all__` KHÔNG chỉ là danh sách export: nó còn
# là thứ DI scanner đăng ký khi app gọi dependency.scan(...). Nên một class
# concrete nằm ở đây là một singleton container phải DỰNG.
#
# That is why `LmdbConfig` and the exception classes are imported above but NOT
# listed: `from xime.starters.lmdb import LmdbConfig` still works, while the
# container is not asked to build them. Leaving `LmdbConfig` in this list is not
# a cosmetic slip - it is a dataclass whose first field is `path: str`, so DI
# goes looking for a binding for `str` and startup dies with "Unregistered
# Dependency: str". Measured 2026-08-20, on the first test that went through
# real DI instead of building objects by hand - the same shape as the 0.7.0
# audit finding on `ModbusClient(device: str)`.
# Đó là lý do `LmdbConfig` và các lớp ngoại lệ được import ở trên nhưng KHÔNG
# nằm trong danh sách: import vẫn chạy, còn container thì không bị bắt dựng
# chúng. Để `LmdbConfig` ở đây không phải lỗi thẩm mỹ - nó là dataclass có
# trường đầu `path: str`, nên DI đi tìm binding cho `str` và khởi động chết.
#
# Store and CounterStore stay listed and stay harmless: they are abstract, so
# the scanner skips them. There is a test guarding exactly that.
#
# The four names kept out are imported above in the redundant-alias form
# (`X as X`, PEP 484), which states "intentional re-export" to both a reader and
# a linter - without it they look like leftover imports.
# Bốn tên bị giữ ngoài danh sách được import ở trên bằng dạng alias trùng tên
# (`X as X`, PEP 484) - nó nói rõ "re-export có chủ đích"; không có nó thì chúng
# trông như import thừa.
#
#   LmdbEnvironment : owns every open LMDB file and the memory budget; opens
#                     files lazily, closes them in pre_destroy.
#   StoreCleanupJob : optional, removes expired entries. Register it with
#                     configure_scheduler() if you want it to run.
__all__ = [
    "LmdbEnvironment",
    "StoreCleanupJob",
    "Store",
    "CounterStore",
    "NEVER",
    "DEFAULT_TTL",
    "store_registry",
]
