"""`xime init` - sinh cây thư mục và các file cơ bản của một ứng dụng Xime.

⚠ **Sinh ÍT có chủ ý.** Mỗi file trình tạo đẻ ra là một file framework **ngầm sở
hữu vĩnh viễn**: đổi cách bố trí `application/service/` về sau là phá mọi hướng
dẫn đã in. Spring Initializr sinh gần như không gì và sống tốt; `rails new` sinh
tất cả và nổi tiếng là khó đổi. Bản này theo vế thứ nhất - đủ chạy, chưa cầm tù
ai về kiến trúc.

⭐ **Hai file cấu hình, hai vai khác hẳn nhau:**

| | |
|---|---|
| `application.yml` | file thật, **đầy đủ chú thích**, nằm ngoài git (secret) |
| `application.yml.example` | cho git, **không chú thích**, chỉ khoá bắt buộc |

Chủ dự án chốt 2026-08-20 rằng bản `.example` *"không có giá trị, người dùng xoá
cũng được"* - nó chỉ để một bản clone sạch biết phải điền gì. Mọi lời giải thích
sống ở `xime config --print`, thứ **không bao giờ cũ**; chép chú thích vào một
file đi theo git là tạo ra tài liệu già đi trong im lặng.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ._config_render import render, render_example

_NAME = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


# Tên khiến dự án sinh ra KHÔNG CHẠY ĐƯỢC, hoặc chạy sai một cách im lặng.
#
# `config` và `resources` là hai thư mục trình tạo tự đặt: `module_name` biến
# tên dự án thành tên gói, và gói đó đụng vào chúng thì `build_plan` có hai khoá
# trùng nhau trong cùng một dict literal - cái sau đè cái trước, dự án ra **11
# file thay vì 12** và thiếu đúng `config/__init__.py` (nơi `import dependency`
# nằm). Không lỗi nào phát ra lúc tạo; nó nổ lúc chạy, với một thông báo không
# liên quan gì tới cái tên.
#
# `xime` thì tệ hơn: gói của dự án **che chính framework**, nên `import xime`
# trong thư mục đó trỏ về dự án. Phát hiện T8 của kiểm toán 0.8.
_TEN_CAM = frozenset({"config", "resources", "xime", "main", "test", "tests"})


def validate_name(name: str) -> str | None:
    """Trả lý do từ chối, hoặc `None` khi tên dùng được."""
    if not _NAME.match(name):
        return (
            "a project name must be lowercase, start with a letter, and contain "
            "only letters, digits and '-'"
        )
    module = module_name(name)
    if module in _TEN_CAM:
        return (
            f"{name!r} is reserved: the generated project already has a "
            f"{module!r} of its own, and the two would overwrite each other"
        )
    if module in sys.stdlib_module_names:
        return (
            f"{name!r} would create a package called {module!r}, which shadows "
            f"a module in the Python standard library"
        )
    return None


def module_name(project: str) -> str:
    """`don-hang-noi-bo` -> `don_hang_noi_bo`. Dấu gạch không hợp lệ trong tên module."""
    return project.replace("-", "_")


MAIN_PY = '''\
"""Entry point for {project}."""

from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

import config

# The three lines below live at MODULE LEVEL, not inside `if __name__`.
#
# When the app runs on several processes, each child re-runs THIS FILE to
# rebuild the application, and there `__name__` is `__mp_main__` so the `if`
# block never fires. Put `use()` inside that block and the children come up
# with no adapters and an empty DI container.
#
# Module level is for DECLARING, not for DOING: everything here runs N+1 times
# for N processes. Do not open connections, read files, or call `uuid4()`.
#     Check with: xime check module-level
app = Application()
app.add_config(config)
app.use(WebAdapter())

if __name__ == "__main__":
    app.run()
'''

CONFIG_INIT = '''\
"""ARCHITECTURE configuration - what an operator cannot choose for you.

OPERATIONAL configuration (ports, connection strings, paths) lives in
`resources/application.yml`. See every key: `xime config --print`.
"""

from config.dependency import dependency

from config import web  # noqa: F401  - imported so configure_* runs at startup

__all__ = ["dependency"]
'''

CONFIG_DEPENDENCY = '''\
"""DI container bindings."""

from xime.core.config import BindingConfig

dependency = BindingConfig()

# Controllers live in the container too - configure_controllers() only says
# which packages hold them.
dependency.scan("{module}.api")

# Scan by LAYER, not the whole tree: a class joins the container because of
# where it lives.
# dependency.scan(
#     "{module}.application.service",
#     "{module}.application.usecase",
#     "{module}.infrastructure.repository",
# )

# Interface (Protocol) -> implementation, declared explicitly.
# dependency.bind({{ UserRepository: PostgresUserRepository }})
'''

CONFIG_WEB = '''\
"""Routing, middleware, CORS."""

from xime.adapters.web import configure_controllers

# Packages (or modules) holding controller classes. The SAME string goes to
# dependency.scan() below: the container builds the instances, and routes are
# registered from them afterwards. Add a file under {module}/api/ and it is
# picked up without touching this line.
configure_controllers("{module}.api")
'''

API_INIT = '''\
"""Inbound adapters: HTTP, gRPC and socket controllers."""
'''

CONTROLLERS = '''\
"""Sample controller. Delete it as soon as you have a real route."""

from xime.adapters.web import get


class HealthController:
    @get("/ping")
    async def ping(self) -> dict[str, str]:
        return {"status": "ok"}
'''

PYPROJECT = '''\
[project]
name = "{project}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "xime>={version}",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''

GITIGNORE = '''\
__pycache__/
*.py[cod]
.venv/
dist/

# The real configuration carries secrets - do NOT commit it. The .example does.
resources/application.yml
resources/application-*.yml
!resources/application.yml.example
'''

README = '''\
# {project}

```bash
pip install -e .
python main.py
```

Operational configuration: `resources/application.yml`.
To see every key and its default:

```bash
xime config --print          # the framework's whole configuration surface
xime check config            # compare your file against it, catch typos
xime check module-level      # catch non-deterministic calls at module level
```
'''


@dataclass(frozen=True)
class Plan:
    """Những gì sẽ được ghi. Dựng trước, ghi sau - không để lại cây dở dang."""

    root: Path
    files: dict[str, str]

    def existing(self) -> list[str]:
        return sorted(rel for rel in self.files if (self.root / rel).exists())


def build_plan(root: Path, project: str, version: str) -> Plan:
    module = module_name(project)
    cap = [
        ("main.py", MAIN_PY.format(project=project)),
        ("config/__init__.py", CONFIG_INIT),
        ("config/dependency.py", CONFIG_DEPENDENCY.format(module=module)),
        ("config/web.py", CONFIG_WEB.format(module=module)),
        (f"{module}/__init__.py", f'"""{project}."""\n'),
        (f"{module}/api/__init__.py", API_INIT),
        (f"{module}/api/controllers.py", CONTROLLERS),
        ("resources/application.yml", render(project, for_init=True)),
        ("resources/application.yml.example", render_example(project)),
        ("pyproject.toml", PYPROJECT.format(project=project, version=version)),
        (".gitignore", GITIGNORE),
        ("README.md", README.format(project=project)),
    ]
    # ⛔ Danh sách CẶP rồi mới dựng dict, để khoá trùng NỔ thay vì đè im lặng.
    #
    # `validate_name` đã chặn mọi tên biết trước là gây trùng, nên lối này chỉ
    # chạy khi có một cách trùng mà chưa ai nghĩ tới - và đó chính là ca cần một
    # thông báo lỗi. Một dict literal thì cái sau luôn thắng, không một chữ nào
    # nói cho ai biết. Phát hiện T8 của kiểm toán 0.8.
    trung = [k for k, n in Counter(k for k, _ in cap).items() if n > 1]
    if trung:
        raise ValueError(
            f"xime init: the generated file list has duplicate paths {trung}. "
            f"That means two templates would write the same file and one would "
            f"be silently lost. This is a bug in build_plan, not in your input."
        )
    return Plan(root, dict(cap))


def write(plan: Plan) -> list[str]:
    """Ghi mọi file, trả danh sách đường dẫn tương đối đã ghi.

    ⚠ Người gọi phải kiểm `existing()` trước. Ghi đè một `application.yml` đang
    chạy là xoá cấu hình thật của một deployment, và không có đường lui.
    """
    written: list[str] = []
    for relative, body in plan.files.items():
        target = plan.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        written.append(relative)
    return sorted(written)
