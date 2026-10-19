"""Process stderr destination for diagnostics that must bypass a native pipe."""
from __future__ import annotations

import sys
from typing import TextIO

_destination: TextIO | None = None


def process_stderr() -> TextIO:
    return _destination if _destination is not None else sys.stderr


def set_process_stderr(destination: TextIO) -> None:
    # A native pipe has process lifetime, so this stream has the same lifetime.
    global _destination
    _destination = destination
