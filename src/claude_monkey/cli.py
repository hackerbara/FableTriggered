from __future__ import annotations

import argparse

from claude_monkey import __version__
from claude_monkey.config import load_config, save_config
from claude_monkey.paths import default_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claude-monkey")
    parser.add_argument("--version", action="store_true", help="print ClaudeMonkey version")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor")
    sub.add_parser("list-patches")
    sub.add_parser("status")
    enable = sub.add_parser("enable")
    enable.add_argument("patch_id")
    disable = sub.add_parser("disable")
    disable.add_argument("patch_id")
    sub.add_parser("list-prompts")
    set_prompt = sub.add_parser("set-prompt")
    set_prompt.add_argument("prompt")
    sub.add_parser("clear-prompt")
    sub.add_parser("build")
    sub.add_parser("install-shim")
    sub.add_parser("uninstall-shim")
    sub.add_parser("rollback")
    sub.add_parser("use-official")
    return parser


def active_profile(config):
    return config.profiles.setdefault(
        config.activeProfile, type(next(iter(config.profiles.values())))(enabledPatches=[])
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    paths = default_paths()
    config = load_config(paths.config_path)
    if args.command == "status":
        print(f"stateDir={paths.state_dir}")
        print(f"patchesDir={paths.patches_dir}")
        print(f"activeProfile={config.activeProfile}")
        print(f"activePatchSet={config.activePatchSet}")
        return 0
    if args.command == "enable":
        profile = active_profile(config)
        if args.patch_id not in profile.enabledPatches:
            profile.enabledPatches.append(args.patch_id)
        save_config(paths.config_path, config)
        print(f"enabled {args.patch_id}; rebuild required")
        return 0
    if args.command == "disable":
        profile = active_profile(config)
        profile.enabledPatches = [item for item in profile.enabledPatches if item != args.patch_id]
        save_config(paths.config_path, config)
        print(f"disabled {args.patch_id}; rebuild required")
        return 0
    if args.command in {
        "doctor",
        "list-patches",
        "list-prompts",
        "set-prompt",
        "clear-prompt",
        "build",
        "install-shim",
        "uninstall-shim",
        "rollback",
        "use-official",
    }:
        print(f"{args.command}: command shell available")
        return 0
    parser.print_help()
    return 0
