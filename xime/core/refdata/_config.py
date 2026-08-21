"""Khai các bảng tham chiếu - `configure_refdata()`.

Đúng khuôn `configure_*` của repo: framework **không tự quét** config, lập
trình viên gọi một hàm. Xem `rules/config-discovery.md`.

⭐ Vì sao phải khai, trong khi `Store` thì chỉ cần `dependency.scan`: mở một
file LMDB là việc riêng của từng tiến trình, còn **vùng nhớ chung thì phải có
một người cấp trước** - và người đó là tiến trình gốc, thứ **không dựng DI**.
Nó chỉ có class trong tay, nên `name` và `max_bytes` phải đọc được từ class.
"""

from __future__ import annotations

from xime.core.exception.framework import StartupException


class _RefDataRegistry:
    """Nơi `configure_refdata()` ghi vào, đọc lúc khởi động."""

    def __init__(self) -> None:
        self._classes: tuple[type, ...] = ()

    def set(self, classes: tuple[type, ...]) -> None:
        self._classes = classes

    def classes(self) -> tuple[type, ...]:
        return self._classes

    def reset(self) -> None:
        """Về mặc định. Cho test - code sản xuất không bao giờ gọi."""
        self._classes = ()


refdata_registry = _RefDataRegistry()


def configure_refdata(classes: list[type] | tuple[type, ...]) -> None:
    """Khai những bảng tham chiếu ứng dụng này dùng.

    ```python
    # config/refdata.py
    from xime.core.refdata import configure_refdata

    from app.refdata.app_registry import AppRegistryRefData
    from app.refdata.jwt_keys import JwtKeyRefData

    configure_refdata([JwtKeyRefData, AppRegistryRefData])
    ```

    Ba chi tiết cố ý:

    1. **Nhận CLASS, không nhận instance.** Framework dựng instance qua DI nên
       chúng được inject bình thường; và tiến trình gốc đọc được `name` +
       `max_bytes` từ class **trước khi** DI tồn tại. Cùng khuôn
       `configure_link(handlers=[...])` và `configure_jwt(key_provider=...)`.
    2. **Danh sách phải giống nhau ở mọi tiến trình**, vì vùng nhớ là chung.
       Tự đúng nhờ `config/` được import y hệt ở mọi tiến trình, nhưng khuôn
       vùng nhớ vẫn được kiểm lại lúc attach - *"tự đúng nhờ quy ước"* là thứ
       hỏng im lặng khi quy ước bị phá.
    3. Gọi hai lần thì lần sau **thay** lần trước, không cộng dồn - cùng hành
       vi với mọi `configure_*` khác.
    """
    from ._refdata import RefData

    resolved = tuple(classes)
    for cls in resolved:
        if not isinstance(cls, type) or not issubclass(cls, RefData):
            raise StartupException(
                f"\nNot A RefData Class\n"
                f"  Given : {cls!r}\n"
                f"  Detail: configure_refdata() takes RefData SUBCLASSES, not "
                f"instances and not other types. The parent process reads "
                f"`name` and `max_bytes` off the class before DI exists."
            )
        if getattr(cls, "__abstractmethods__", frozenset()):
            # Quên khai `name` là class vẫn abstract, và abstract thì không
            # vào DI được. Bắt ở đây để thông báo nói đúng chỗ sai, thay vì
            # một lỗi "cannot instantiate" ở giữa lượt dựng container.
            raise StartupException(
                f"\nRefData Class Without A Name\n"
                f"  Class : {cls.__name__}\n"
                f"  Detail: a concrete table declares its name as a class "
                f"parameter, for example:\n"
                f"\n"
                f'      class {cls.__name__}(RefData[MyValue], name="my-table"): ...'
            )
    refdata_registry.set(resolved)
