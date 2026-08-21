"""Bề mặt API công khai: một tên chỉ được mang MỘT nghĩa, và lỗi phải bắt được.

⛔ Nhóm này ra đời từ một lỗi thật, tìm ra khi rà trước lúc phát hành 0.8.0.
`xime.core.link` và `xime.core.refdata` **cùng xuất khẩu một cái tên**
`LayoutMismatch`, là **hai lớp khác nhau**:

    from xime.core.link import LayoutMismatch
    from xime.core.refdata import LayoutMismatch   # che mất cái trên, im lặng

Sau hai dòng đó `except LayoutMismatch:` bắt đúng một trong hai, cái còn lại đi
xuyên qua. Không lỗi lúc import, không cảnh báo, không test nào đỏ. Đây là
luật 03 ở tầng **từ vựng**: một tên mang hai nghĩa.

Và cùng lúc, cả hai kế thừa thẳng `Exception`, nên `except XimeException:` -
lớp nền mà framework bảo người dùng bắt - **không bắt được chúng**, và
`except LinkError:` / `except RefDataError:` cũng không.

⚠ Đây là loại lỗi không ai gặp cho tới ngày một ứng dụng dùng cả hai package,
tức đúng ngày nó khó gỡ nhất. 0.8 là bản **alpha cuối**, nên sót một cái tên là
sót vĩnh viễn hoặc phải phá tương thích ở Beta.
"""

from __future__ import annotations

import importlib

import pytest

from xime.core.exception.framework import XimeException

# Package công khai có `__all__` riêng, tức có không gian tên người dùng nhập
# vào cùng một module.
PACKAGES = [
    "xime.core.link",
    "xime.core.refdata",
    "xime.core.lifecycle",
    "xime.starters.lmdb",
]


def _exports(name: str) -> dict[str, object]:
    module = importlib.import_module(name)
    return {n: getattr(module, n) for n in module.__all__}


def test_no_two_packages_export_the_same_name_for_different_things() -> None:
    seen: dict[str, tuple[str, object]] = {}
    clashes: list[str] = []
    for package in PACKAGES:
        for name, obj in _exports(package).items():
            if name in seen:
                where, first = seen[name]
                if first is not obj:
                    clashes.append(
                        f"{name!r}: {where} xuất {first!r}, {package} xuất {obj!r}"
                    )
                continue
            seen[name] = (package, obj)
    assert not clashes, (
        "hai package công khai cùng xuất một tên cho hai thứ khác nhau - "
        "nhập cả hai vào một module là một cái che mất cái kia, im lặng:\n  "
        + "\n  ".join(clashes)
    )


@pytest.mark.parametrize("package", PACKAGES)
def test_every_exported_exception_is_a_xime_exception(package: str) -> None:
    stray = [
        name
        for name, obj in _exports(package).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseException)
        and not issubclass(obj, XimeException)
    ]
    assert not stray, (
        f"{package} xuất ngoại lệ không nằm dưới XimeException: {stray}. "
        "Người dùng được dạy bắt XimeException làm lưới cuối; một lớp đứng "
        "ngoài cây đó đi xuyên qua lưới mà không có gì báo."
    )


@pytest.mark.parametrize(
    "package,base",
    [
        ("xime.core.link", "LinkError"),
        ("xime.core.refdata", "RefDataError"),
    ],
)
def test_every_exception_of_a_package_sits_under_that_packages_base(
    package: str, base: str
) -> None:
    exports = _exports(package)
    root = exports[base]
    assert isinstance(root, type)
    stray = [
        name
        for name, obj in exports.items()
        if isinstance(obj, type)
        and issubclass(obj, BaseException)
        and not issubclass(obj, root)
    ]
    assert not stray, (
        f"{package} có lớp nền {base} nhưng {stray} không nằm dưới nó - "
        f"`except {base}:` sẽ bỏ lọt chúng."
    )
