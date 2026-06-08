"""Xime developer CLI.

Entry point registered in pyproject.toml:

    [project.scripts]
    xime = "xime.cli._main:main"
"""

from xime.cli._main import main

__all__ = ["main"]
