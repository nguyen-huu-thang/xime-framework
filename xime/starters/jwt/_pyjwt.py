"""Lazy access to PyJWT.

This package must import cleanly WITHOUT the [jwt] extra installed. The web
adapter reads `xime.starters.jwt._config` on every start-up just to find out
whether `configure_jwt()` was ever called, and importing a submodule executes
this package's `__init__` first. A module-level `import jwt` in the signer /
verifier therefore crashed every web application that had not installed the
extra - including ones that never touch JWT at all. Fixed 2026-07-30; see the
audit note C1 in `.claude/docs/kiem-toan-0.7.md`.

Nạp PyJWT lười. Package này PHẢI import được khi chưa cài extra [jwt]: web
adapter đọc `_config` ở mọi lần khởi động chỉ để xem `configure_jwt()` có được
gọi hay không, mà import submodule thì `__init__` của package chạy trước. Vì thế
`import jwt` ở mức module từng làm sập mọi web app không cài extra, kể cả app
không đụng gì tới JWT.
"""

from __future__ import annotations

from typing import Any


def pyjwt() -> Any:
    """Return the `jwt` module, or raise with a message that points the right way.

    The distribution is called **PyJWT** while the import name is `jwt`. PyPI
    also carries an unrelated, near-abandoned package literally named `jwt`, so
    the bare `ModuleNotFoundError: No module named 'jwt'` leads people to
    `pip install jwt` - which installs the wrong library and then fails in a way
    that is hard to trace back. Say the right command explicitly.

    Tên distribution là **PyJWT** nhưng tên import là `jwt`. Trên PyPI còn có
    một package tên đúng là `jwt` (khác hẳn, gần như bỏ hoang), nên lỗi trần
    `No module named 'jwt'` dẫn người dùng cài nhầm thư viện.

    After the first call this costs a `sys.modules` lookup, which is negligible
    next to the cost of signing or verifying a token.
    """
    try:
        import jwt
    except ImportError:
        raise RuntimeError(
            "The JWT starter requires PyJWT. Run: pip install 'xime[jwt]'\n"
            "Note: the PyPI distribution is named 'PyJWT'. `pip install jwt` "
            "installs a different, unrelated package and will not work."
        ) from None
    return jwt
