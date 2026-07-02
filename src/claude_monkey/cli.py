from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claude-monkey")
    parser.add_argument("--version", action="store_true", help="print ClaudeMonkey version")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor")
    sub.add_parser("list-patches")
    sub.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    from claude_monkey import __version__

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.command in {"doctor", "list-patches", "status"}:
        print(f"{args.command}: command shell available")
        return 0
    parser.print_help()
    return 0
