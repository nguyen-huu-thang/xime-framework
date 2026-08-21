from __future__ import annotations

import argparse
import importlib
import os
import pkgutil
import sys


def build_parser() -> argparse.ArgumentParser:
    """Dựng parser và TRẢ VỀ - không chạy gì.

    Tách khỏi `main()` để test soi được **mọi dòng lệnh `xime ...` viết trong
    tài liệu** mà không phải thực thi chúng. Nó ra đời từ một lỗi thật: tài
    liệu, README và header của mọi `application.yml` do `xime init` sinh ra
    đều bảo chạy `xime config --print`, một cờ CLI **chưa từng tồn tại**.
    """
    parser = argparse.ArgumentParser(prog="xime", description="Xime developer CLI")
    sub = parser.add_subparsers(dest="group", required=True)

    grpc = sub.add_parser("grpc", help="Code-First gRPC tooling")
    grpc_sub = grpc.add_subparsers(dest="command", required=True)

    gen = grpc_sub.add_parser("generate", help="Generate .proto (+ Python stubs) from controllers")
    gen.add_argument("--config", default="config", help="config package to import (default: config)")
    gen.add_argument("--no-protoc", action="store_true", help="skip protoc (emit .proto only)")

    chk = grpc_sub.add_parser("check", help="Fail if generated .proto is out of date")
    chk.add_argument("--config", default="config", help="config package to import (default: config)")

    cli = grpc_sub.add_parser(
        "client",
        help="Generate a typed client SDK from .proto files (+ contract.json sidecar)",
    )
    cli.add_argument("--proto", required=True, help="directory containing the .proto files")
    cli.add_argument("--out", required=True, help="output package directory (e.g. clients/trust)")
    cli.add_argument(
        "--package",
        default=None,
        help="emit a pip-installable layout with pyproject.toml under --out, "
        "using this distribution name (e.g. trust-client)",
    )
    cli.add_argument(
        "--package-version",
        default="0.1.0",
        help="initial version written into the generated SDK's pyproject.toml "
        "(default: 0.1.0; this is the SDK's own version, not the framework's)",
    )

    check = sub.add_parser("check", help="Static checks over an application")
    check_sub = check.add_subparsers(dest="command", required=True)

    ml = check_sub.add_parser(
        "module-level",
        help="Find non-deterministic calls that run at module level "
        "(module-level code runs once PER PROCESS)",
    )
    ml.add_argument(
        "--main",
        default=None,
        help="entry point to start from (default: app/main.py, main.py or src/main.py)",
    )
    ml.add_argument("--root", default=".", help="project root (default: .)")

    cc = check_sub.add_parser(
        "config",
        help="Compare application.yml against the framework's configuration surface",
    )
    cc.add_argument(
        "--file",
        default="resources/application.yml",
        help="config file to check (default: resources/application.yml)",
    )

    cfg = sub.add_parser(
        "config",
        help="Print application.yml with every framework key and its default",
    )
    # `--print` là hành động MẶC ĐỊNH, nhận vào để dòng lệnh viết trong tài
    # liệu chạy được: `xime config --print` xuất hiện ở tài liệu vn/en, ở cả
    # hai README, trong README của dự án do `xime init` sinh, trong một thông
    # báo lỗi lúc chạy của starter lmdb, và trong **header của mọi
    # application.yml đã sinh ra** - tức những file nằm trên đĩa người dùng và
    # không bao giờ được sửa lại. Bỏ chữ đó khỏi tài liệu thì mọi file cũ đều
    # trỏ tới một lệnh không tồn tại; nhận nó thì mọi câu kia thành đúng.
    #
    # Loại trừ lẫn nhau với `--example` thay vì để một cái âm thầm thắng: hai
    # cờ này hỏi hai file khác nhau, nên đưa cả hai là câu hỏi không có nghĩa.
    which = cfg.add_mutually_exclusive_group()
    which.add_argument(
        "--print",
        dest="print_",
        action="store_true",
        help="print the annotated application.yml to stdout (the default action)",
    )
    which.add_argument(
        "--example",
        action="store_true",
        help="print the bare application.yml.example instead (required keys only)",
    )
    cfg.add_argument(
        "--project",
        default=None,
        help="project name used in generated placeholders",
    )

    ini = sub.add_parser("init", help="Create a new Xime project tree")
    ini.add_argument("name", help="project name (lowercase, letters, digits, '-')")
    ini.add_argument(
        "--dir",
        default=None,
        help="where to create it (default: ./<name>); use '.' for the current directory",
    )
    ini.add_argument(
        "--force",
        action="store_true",
        help="overwrite files that already exist",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.group == "init":
        return _init(args.name, args.dir, force=args.force)
    if args.group == "config":
        return _config_print(args.project, example=args.example)
    if args.group == "check" and args.command == "config":
        return _check_config(args.file)
    if args.group == "check" and args.command == "module-level":
        return _check_module_level(args.root, args.main)
    if args.group == "grpc" and args.command == "generate":
        return _grpc_generate(args.config, run_protoc=not args.no_protoc)
    if args.group == "grpc" and args.command == "check":
        return _grpc_check(args.config)
    if args.group == "grpc" and args.command == "client":
        return _grpc_client(args.proto, args.out, args.package, args.package_version)

    parser.print_help()
    return 2


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def _init(name: str, directory: str | None, *, force: bool) -> int:
    """Sinh cay thu muc. Dung truoc khi ghi de, tru khi --force."""
    from pathlib import Path

    from xime import __version__
    from xime.cli._init import build_plan, validate_name, write

    problem = validate_name(name)
    if problem is not None:
        print(f"Invalid Project Name\n  Name  : {name!r}\n  Detail: {problem}")
        return 2

    root = Path(directory).resolve() if directory else (Path.cwd() / name).resolve()
    plan = build_plan(root, name, __version__)

    clashes = plan.existing()
    if clashes and not force:
        print("Refusing To Overwrite\n")
        for relative in clashes:
            print(f"  exists  {relative}")
        print(
            f"\n{len(clashes)} file(s) already exist under {root}.\n"
            "Overwriting resources/application.yml would erase a real deployment's\n"
            "configuration, and there is no way back. Pass --force if that is what\n"
            "you want, or pick an empty directory."
        )
        return 1

    for relative in write(plan):
        print(f"  create  {relative}")
    print(
        f"\nCreated {name} in {root}\n\n"
        "  cd " + str(root) + "\n"
        "  pip install -e .\n"
        "  python main.py\n\n"
        "resources/application.yml carries every framework key: the uncommented\n"
        "lines are the ones this deployment has to decide, the commented ones are\n"
        "framework defaults you can open up. Leaving them commented is what lets a\n"
        "later Xime release change a default for you."
    )
    return 0


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def _config_print(project: str | None, *, example: bool) -> int:
    """In ra stdout, KHONG ghi gi.

    Day la manh co gia tri cao nhat va rui ro gan bang 0: no phuc vu duoc ca 31
    ung dung dang co ngay hom nay, trong khi `xime init` chi giup app moi.
    """
    from xime.cli._config_render import render, render_example

    print(render_example(project) if example else render(project), end="")
    return 0


# ---------------------------------------------------------------------------
# check subcommands
# ---------------------------------------------------------------------------

def _check_config(file: str) -> int:
    """BA ma thoat: `0` sach - `1` co van de - `2` CHUA KET LUAN DUOC."""
    from pathlib import Path

    from xime.cli._config_check import check

    path = Path(file).resolve()
    result = check(path)

    if result.verdict == "inconclusive":
        print(
            f"INCONCLUSIVE - {result.unreadable}\n"
            "This is not a pass: nothing was compared."
        )
        return 2

    for finding in result.findings:
        line = f"  {finding.where}: {finding.problem}"
        if finding.hint:
            line += f"   {finding.hint}"
        print(line)

    checked = ", ".join(result.blocks_checked) or "none"
    if result.verdict == "findings":
        print(
            f"\n{len(result.findings)} problem(s) in {path}.\n"
            f"Blocks checked: {checked}"
        )
        return 1

    print(
        f"CLEAN - {path}\n"
        f"Blocks checked: {checked}\n"
        "Note: only blocks the framework fully describes are policed; a block of\n"
        "your own, or one whose key list is not complete here, is left alone."
    )
    return 0




def _check_module_level(root: str, entry: str | None) -> int:
    """BA ma thoat, khong phai hai.

    `0` sach - `1` co vi pham - `2` CHUA KET LUAN DUOC.

    Gop *"khong tim thay diem vao"* vao `0` la de mot lan chay trong CI bao xanh
    tren mot phep kiem chua he chay.
    """
    from pathlib import Path

    from xime.cli._module_level import find_entry, scan

    root_path = Path(root).resolve()
    entry_path = Path(entry).resolve() if entry else find_entry(root_path)
    if entry_path is None:
        print(
            "Cannot Locate An Entry Point\n"
            f"  Root  : {root_path}\n"
            "  Tried : app/main.py, main.py, src/main.py\n"
            "  Detail: nothing was scanned, so this is NOT a clean result.\n"
            "          Pass --main <path> to say where to start."
        )
        return 2
    if not entry_path.is_file():
        print(f"Entry point does not exist: {entry_path}")
        return 2

    result = scan(entry_path, root_path)

    for path, reason in result.unreadable:
        print(f"  unreadable  {path}  ({reason})")

    for finding in result.findings:
        try:
            shown: object = finding.path.relative_to(root_path)
        except ValueError:
            shown = finding.path
        print(f"  {shown}:{finding.line}  {finding.name}()   {finding.source}")

    scanned = len(result.scanned)
    if result.verdict == "inconclusive":
        print(
            f"\nINCONCLUSIVE - {len(result.unreadable)} file(s) could not be read.\n"
            "This is not a pass: what they contain is unknown."
        )
        return 2
    if result.verdict == "violations":
        print(
            f"\n{len(result.findings)} non-deterministic call(s) at module level, "
            f"across {scanned} file(s).\n"
            "Module-level code runs once per process, so every process gets its own\n"
            "value while the code reading it assumes the cluster shares one.\n"
            "Move them into post_construct(), run_once() or a function."
        )
        return 1

    print(
        f"CLEAN - {scanned} file(s) scanned, no watched call at module level.\n"
        "Note: this checks a list of NAMES, so it cannot see a helper of your own\n"
        "that calls one of them underneath."
    )
    return 0


# ---------------------------------------------------------------------------
# grpc subcommands
# ---------------------------------------------------------------------------

def _grpc_generate(config_package: str, run_protoc: bool) -> int:
    from xime.adapters.grpc.codefirst import generate
    from xime.adapters.grpc.codefirst._config import codefirst_registry

    _load_config(config_package)
    packages = codefirst_registry.get_packages()
    if not packages:
        print("No code-first packages registered. Call configure_grpc_codefirst(...) in your config.")
        return 1

    result = generate(
        packages=packages,
        output_dir=codefirst_registry.output_dir(),
        lock_file=codefirst_registry.lock_file(),
        run_protoc=run_protoc,
    )
    for path in result.written:
        print(f"  proto  {path}")
    for path in result.protoc_outputs:
        print(f"  stub   {path}")
    print(f"Generated {len(result.written)} proto file(s).")
    return 0


def _grpc_check(config_package: str) -> int:
    from xime.adapters.grpc.codefirst import check
    from xime.adapters.grpc.codefirst._config import codefirst_registry

    _load_config(config_package)
    packages = codefirst_registry.get_packages()
    if not packages:
        print("No code-first packages registered. Call configure_grpc_codefirst(...) in your config.")
        return 1

    result = check(
        packages=packages,
        output_dir=codefirst_registry.output_dir(),
        lock_file=codefirst_registry.lock_file(),
    )
    if result.ok:
        print("Proto is up to date.")
        return 0

    print("Proto Out Of Date\n")
    for path in result.missing:
        print(f"  missing : {path}")
    for path in result.stale:
        print(f"  stale   : {path}")
    print("\nPlease run:\n  xime grpc generate")
    return 1


def _grpc_client(
    proto_dir: str,
    out_dir: str,
    package: str | None = None,
    package_version: str = "0.1.0",
) -> int:
    from xime.adapters.grpc.client import generate_client_sdk

    result = generate_client_sdk(
        proto_dir, out_dir, package=package, package_version=package_version
    )
    for path in result.written:
        print(f"  sdk    {path}")
    for path in result.skipped_methods:
        print(f"  skip   {path}  (client-streaming requires the contract.json sidecar)")
    print(f"Generated client SDK in {out_dir}.")
    return 0


# ---------------------------------------------------------------------------
# Config loading - import the config package so configure_*() side effects run
# ---------------------------------------------------------------------------

def _load_config(config_package: str) -> None:
    """Import every submodule of the config package to trigger configure_* calls.

    Mirrors Application._import_config_siblings: a configure_grpc_codefirst() call
    living anywhere in config/ populates the registry.
    Giống Application: import mọi submodule của config/ để chạy configure_*.
    """
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        pkg = importlib.import_module(config_package)
    except ImportError as exc:
        raise SystemExit(
            f"Cannot import config package '{config_package}': {exc}\n"
            f"Run from the project root, or pass --config <package>."
        ) from exc

    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        return  # a single module, already imported
    for _, name, _ in pkgutil.iter_modules(pkg_path):
        importlib.import_module(f"{config_package}.{name}")


if __name__ == "__main__":
    raise SystemExit(main())
