from __future__ import annotations

import argparse
import hashlib
import json
import platform as platform_module
import shutil
import sys
from pathlib import Path
from typing import Any

from claude_monkey import __version__
from claude_monkey.builder import BuildRequest, build_patchset
from claude_monkey.config import Profile, load_config, save_config
from claude_monkey.install import (
    install_shim_transaction,
    restore_install_transaction,
    use_official,
)
from claude_monkey.manifest import Manifest, load_manifest_dict
from claude_monkey.paths import StatePaths, default_paths
from claude_monkey.smoke import run_command


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
    set_prompt.add_argument("--id", default="default")
    set_prompt.add_argument("--name")
    set_prompt.add_argument("--mode", choices=("append", "replace"), default="append")
    set_prompt.add_argument("--from-file", action="store_true")
    sub.add_parser("clear-prompt")

    build = sub.add_parser("build")
    build.add_argument("--source")
    build.add_argument("--package", action="append", dest="packages")
    build.add_argument("--output-dir")
    build.add_argument("--source-version")
    build.add_argument("--source-version-output")
    build.add_argument("--platform", default=sys.platform)
    build.add_argument("--arch", default=platform_module.machine() or "unknown")
    build.add_argument("--skip-identity-check", action="store_true")
    build.add_argument("--unverified-candidate", action="store_true")
    build.add_argument("--skip-signing", action="store_true")
    build.add_argument("--skip-smoke", action="store_true")
    build.add_argument("--activate", action="store_true")

    install = sub.add_parser("install-shim")
    install.add_argument("--target")
    install.add_argument("--state-dir")
    install.add_argument("--dry-run", action="store_true")

    uninstall = sub.add_parser("uninstall-shim")
    uninstall.add_argument("--target")
    uninstall.add_argument("--state-dir")
    uninstall.add_argument("--record")
    uninstall.add_argument("--force", action="store_true")

    rollback = sub.add_parser("rollback")
    rollback.add_argument("--target")
    rollback.add_argument("--state-dir")
    rollback.add_argument("--record")
    rollback.add_argument("--force", action="store_true")

    official = sub.add_parser("use-official")
    official.add_argument("--official")
    return parser


def active_profile(config):
    return config.profiles.setdefault(config.activeProfile, Profile(enabledPatches=[]))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _package_roots(paths: StatePaths) -> list[Path]:
    return [paths.patches_dir, _repo_root() / "packages"]


def _load_manifest(package_dir: Path) -> Manifest:
    return load_manifest_dict(json.loads((package_dir / "patch.json").read_text()))


def _resolve_package(package_id_or_path: str, paths: StatePaths) -> Path:
    raw = Path(package_id_or_path).expanduser()
    if raw.exists():
        return raw
    for root in _package_roots(paths):
        candidate = root / package_id_or_path
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"patch package not found: {package_id_or_path}")


def _enabled_package_dirs(args: argparse.Namespace, paths: StatePaths, config) -> list[Path]:
    if args.packages:
        return [_resolve_package(item, paths) for item in args.packages]
    profile = active_profile(config)
    return [_resolve_package(item, paths) for item in profile.enabledPatches]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _discover_source(source_arg: str | None) -> Path | None:
    if source_arg:
        return Path(source_arg).expanduser()
    env_source = __import__("os").environ.get("CLAUDE_MONKEY_SOURCE")
    if env_source:
        return Path(env_source).expanduser()
    found = shutil.which("claude")
    return Path(found) if found else None


def _source_version_output(source: Path, explicit_output: str | None) -> str | None:
    if explicit_output:
        return explicit_output
    result = run_command([str(source), "--version"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or result.stderr.strip() or None


def _source_version(explicit_version: str | None, version_output: str | None) -> str | None:
    if explicit_version:
        return explicit_version
    if not version_output:
        return None
    first = version_output.split(maxsplit=1)[0]
    return first or None


def _default_output_dir(paths: StatePaths, config, source_version: str) -> Path:
    return paths.state_dir / "patchsets" / source_version / config.activeProfile


def _print_report_summary(report) -> None:
    print(f"status={report.status}")
    print(f"sourceSha256={report.sourceSha256}")
    print(f"enabledPatches={','.join(report.enabledPatches)}")
    if report.failureReason:
        print(f"failureReason={report.failureReason}")


def handle_build(args: argparse.Namespace, paths: StatePaths, config) -> int:
    source = _discover_source(args.source)
    if source is None:
        print("build requires --source or a claude executable on PATH", file=sys.stderr)
        return 2
    if not source.exists():
        print(f"source does not exist: {source}", file=sys.stderr)
        return 2
    version_output = _source_version_output(source, args.source_version_output)
    source_version = _source_version(args.source_version, version_output)
    if version_output is None or source_version is None:
        print(
            "build requires --source-version-output/--source-version or a working --version",
            file=sys.stderr,
        )
        return 2
    try:
        package_dirs = _enabled_package_dirs(args, paths, config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not package_dirs:
        print("build requires enabled patches or at least one --package", file=sys.stderr)
        return 2
    manifests = [(package_dir, _load_manifest(package_dir)) for package_dir in package_dirs]
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else _default_output_dir(
        paths, config, source_version
    )
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=output_dir,
            manifests=manifests,
            source_version=source_version,
            source_version_output=version_output,
            source_sha256=_file_sha256(source),
            source_size_bytes=source.stat().st_size,
            platform=args.platform,
            arch=args.arch,
            skip_identity_check=args.skip_identity_check,
            unverified_candidate=args.unverified_candidate,
            run_signing=not args.skip_signing,
            run_smoke=not args.skip_smoke,
            activate=args.activate,
            current_path=paths.current_path,
        )
    )
    if report.status in {"verified", "unverified_candidate"}:
        config.activePatchSet = str(output_dir)
        save_config(paths.config_path, config)
    _print_report_summary(report)
    return 0 if report.status in {"verified", "unverified_candidate"} else 1


def _record_path(args: argparse.Namespace, state_dir: Path) -> Path:
    return Path(args.record).expanduser() if args.record else state_dir / "install-record.json"


def _target_from_args_or_record(args: argparse.Namespace, record_path: Path) -> Path | None:
    if args.target:
        return Path(args.target).expanduser()
    if not record_path.exists():
        return None
    raw: dict[str, Any] = json.loads(record_path.read_text())
    target = raw.get("targetPath")
    return Path(target) if isinstance(target, str) else None


def handle_restore(args: argparse.Namespace, paths: StatePaths) -> int:
    state_dir = Path(args.state_dir).expanduser() if args.state_dir else paths.state_dir
    record_path = _record_path(args, state_dir)
    target = _target_from_args_or_record(args, record_path)
    if target is None:
        print("restore requires --target or an install record with targetPath", file=sys.stderr)
        return 2
    restored = restore_install_transaction(target, record_path, force=args.force)
    print(f"restored={str(restored).lower()}")
    return 0 if restored else 1


def handle_set_prompt(args: argparse.Namespace, paths: StatePaths, config) -> int:
    profile_dir = paths.state_dir / "prompts"
    profile_dir.mkdir(parents=True, exist_ok=True)
    if args.from_file:
        source_path = Path(args.prompt).expanduser()
        if not source_path.exists():
            print(f"prompt file does not exist: {source_path}", file=sys.stderr)
            return 2
    else:
        source_path = profile_dir / f"{args.id}.md"
        source_path.write_text(args.prompt)
    profile_json = profile_dir / f"{args.id}.json"
    profile_json.write_text(
        json.dumps(
            {
                "id": args.id,
                "name": args.name or args.id,
                "mode": args.mode,
                "sourcePath": str(source_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    active_profile(config).promptProfile = args.id
    save_config(paths.config_path, config)
    print(f"set prompt profile {args.id}")
    return 0


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
        if paths.current_path.exists() or paths.current_path.is_symlink():
            print(f"current={paths.current_path.resolve()}")
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
    if args.command == "list-patches":
        for root in _package_roots(paths):
            if root.exists():
                for patch_json in sorted(root.glob("*/patch.json")):
                    print(patch_json.parent.name)
        return 0
    if args.command == "list-prompts":
        prompt_dir = paths.state_dir / "prompts"
        if prompt_dir.exists():
            for prompt_json in sorted(prompt_dir.glob("*.json")):
                print(prompt_json.stem)
        return 0
    if args.command == "set-prompt":
        return handle_set_prompt(args, paths, config)
    if args.command == "clear-prompt":
        active_profile(config).promptProfile = None
        save_config(paths.config_path, config)
        print("cleared active prompt profile")
        return 0
    if args.command == "build":
        return handle_build(args, paths, config)
    if args.command == "install-shim":
        state_dir = Path(args.state_dir).expanduser() if args.state_dir else paths.state_dir
        if not args.target:
            print("install-shim requires --target", file=sys.stderr)
            return 2
        record = install_shim_transaction(Path(args.target).expanduser(), state_dir, args.dry_run)
        print(f"installRecord={record}")
        print(f"dryRun={str(args.dry_run).lower()}")
        return 0
    if args.command in {"uninstall-shim", "rollback"}:
        return handle_restore(args, paths)
    if args.command == "use-official":
        if not args.official:
            print("use-official requires --official", file=sys.stderr)
            return 2
        official = Path(args.official).expanduser()
        if not official.exists():
            print(f"official path does not exist: {official}", file=sys.stderr)
            return 2
        use_official(paths.current_path, official)
        config.activePatchSet = None
        save_config(paths.config_path, config)
        print(f"current={paths.current_path.resolve()}")
        return 0
    if args.command == "doctor":
        print(f"stateDir={paths.state_dir}")
        print(f"sourceDiscovery={_discover_source(None) or 'missing'}")
        return 0
    parser.print_help()
    return 0
