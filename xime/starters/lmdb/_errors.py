from __future__ import annotations

from xime.core.exception.framework import XimeException


class StoreError(XimeException):
    """Base class for every failure raised by the LMDB store.

    Store failures are reported as EXCEPTIONS, not as a third outcome in the
    return type. The reason is `incr` and `set_if_absent`: an exception is
    fail-closed by nature (forgetting to catch it makes the request fail, so
    nobody claims the lock), while a forgotten branch of a three-way return
    value is fail-open in silence - a rate limiter that lets everything through.
    An application that wants fail-soft behaviour catches this itself; that is a
    decision for the application, never a framework default.
    Lỗi kho báo bằng NGOẠI LỆ, không phải kết cục thứ ba trong kiểu trả về. Lý
    do nằm ở `incr` và `set_if_absent`: ngoại lệ là fail-closed tự nhiên (quên
    bắt thì request lỗi, không ai chiếm được khoá), còn quên một nhánh của kiểu
    trả về ba kết cục là fail-open im lặng - hãm nhịp hoá ra cho qua tất. App
    nào muốn fail-soft thì tự bắt; đó là quyết định của app, không phải mặc
    định của framework.
    """


class StoreUnavailableError(StoreError):
    """The store could not be read or written because the backend failed.

    Wraps the underlying `lmdb.Error` so application code never has to import
    lmdb to catch it, and so the failure is distinguishable from a programming
    mistake such as a bad key type.
    Bọc `lmdb.Error` để code ứng dụng không phải import lmdb mới bắt được, và
    để phân biệt sự cố hạ tầng với lỗi lập trình (ví dụ khoá sai kiểu).
    """


class StoreFullError(StoreError):
    """A partition needs to grow but the store already holds `lmdb.total_max`.

    Distinct from StoreUnavailableError because it demands a different action:
    the operator must raise `lmdb.total_max`, not investigate a broken disk. It
    is reached only after the automatic doubling described in the design has
    been refused, and the framework logs CRITICAL at that point.
    Tách khỏi StoreUnavailableError vì nó đòi một hành động khác: người vận
    hành phải nâng `lmdb.total_max`, không phải đi tìm ổ đĩa hỏng. Chỉ tới đây
    sau khi việc tự nới gấp đôi bị từ chối, và framework log CRITICAL lúc đó.
    """
