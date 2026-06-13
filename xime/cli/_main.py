from __future__ import annotations

import argparse
import importlib
import os
import pkgutil
import sys


def main(argv: list[str] | None = None) -> int:
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
        default="0.2.0",
        help="version written into pyproject.toml (default: 0.2.0)",
    )

    args = parser.parse_args(argv)

    if args.group == "grpc" and args.command == "generate":
        return _grpc_generate(args.config, run_protoc=not args.no_protoc)
    if args.group == "grpc" and args.command == "check":
        return _grpc_check(args.config)
    if args.group == "grpc" and args.command == "client":
        return _grpc_client(args.proto, args.out, args.package, args.package_version)

    parser.print_help()
    return 2


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
    package_version: str = "0.2.0",
) -> int:
    from xime.adapters.grpc.client import generate_client_sdk

    result = generate_client_sdk(
        proto_dir, out_dir, package=package, package_version=package_version
    )
    for path in result.written:
        print(f"  sdk    {path}")
    for path in result.skipped_methods:
        print(f"  skip   {path}  (streaming requires contract.json sidecar)")
    print(f"Generated client SDK in {out_dir}.")
    return 0


# ---------------------------------------------------------------------------
# Config loading — import the config package so configure_*() side effects run
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
