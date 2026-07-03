from __future__ import annotations

from pathlib import Path

import pytest

from claude_monkey.launch_profile import (
    MANAGEMENT_TOKENS,
    LaunchMergeInput,
    LaunchTarget,
    is_management_invocation,
    merge_launch_profile,
)
from claude_monkey.package_model import (
    EnvConflict,
    EnvValue,
    OptionPackage,
    PackageKind,
    PackageManifest,
    PromptPackage,
    PromptSource,
)


def manifest(
    tmp_path: Path,
    package_id: str,
    kind: PackageKind,
    *,
    prompt: PromptPackage | None = None,
    option: OptionPackage | None = None,
) -> PackageManifest:
    package_dir = tmp_path / package_id
    package_dir.mkdir(exist_ok=True)
    return PackageManifest(
        schema_version=1,
        kind=kind,
        id=package_id,
        label=package_id,
        description=package_id,
        package_dir=package_dir,
        manifest_path=package_dir / f"{package_id}.json",
        risk=None,
        compatibility=None,
        prompt=prompt,
        option=option,
        patch=None,
        raw={},
    )


def prompt_manifest(tmp_path: Path, package_id: str, mode: str) -> PackageManifest:
    source = tmp_path / package_id / "prompt.md"
    source.parent.mkdir(exist_ok=True)
    source.write_text("prompt")
    return manifest(
        tmp_path,
        package_id,
        PackageKind.PROMPT,
        prompt=PromptPackage(mode=mode, source=PromptSource(path=source)),
    )


def option_manifest(
    tmp_path: Path,
    package_id: str,
    *,
    argv: tuple[str, ...] = (),
    env: dict[str, EnvValue] | None = None,
    conflicts_with_argv: tuple[str, ...] = (),
    conflicts_with_options: tuple[str, ...] = (),
    conflicts_with_env: tuple[EnvConflict, ...] = (),
) -> PackageManifest:
    return manifest(
        tmp_path,
        package_id,
        PackageKind.OPTION,
        option=OptionPackage(
            argv=argv,
            env=env or {},
            conflicts_with_argv=conflicts_with_argv,
            conflicts_with_options=conflicts_with_options,
            conflicts_with_env=conflicts_with_env,
        ),
    )


def merge(
    *,
    user_argv: list[str] | None = None,
    process_env: dict[str, str] | None = None,
    prompt: PackageManifest | None = None,
    options: list[PackageManifest] | None = None,
) -> object:
    return merge_launch_profile(
        LaunchMergeInput(
            user_argv=user_argv or [],
            process_env=process_env or {},
            prompt=prompt,
            options=options or [],
            target=LaunchTarget(path=Path("/bin/claude"), kind="patched"),
            initial_skipped=[],
            initial_warnings=[],
        )
    )


@pytest.mark.parametrize(
    ("mode", "flag"),
    [("append", "--append-system-prompt-file"), ("replace", "--system-prompt-file")],
)
def test_prompt_append_and_replace_flag_mapping(tmp_path, mode, flag):
    prompt = prompt_manifest(tmp_path, "research", mode)

    result = merge(user_argv=["chat"], prompt=prompt)

    assert result.argv == [flag, str(prompt.prompt.source.path), "chat"]
    assert result.errors == []


def test_user_prompt_flag_skips_active_prompt(tmp_path):
    prompt = prompt_manifest(tmp_path, "research", "append")

    result = merge(user_argv=["--system-prompt", "mine"], prompt=prompt)

    assert result.argv == ["--system-prompt", "mine"]
    assert result.skipped == [
        {"kind": "prompt", "id": "research", "reason": "user_prompt_flag"}
    ]


@pytest.mark.parametrize("token", sorted(MANAGEMENT_TOKENS))
def test_management_tokens_skip_prompt_and_option_injection(tmp_path, token):
    prompt = prompt_manifest(tmp_path, "research", "append")
    option = option_manifest(tmp_path, "debug", argv=("--debug",))

    result = merge(user_argv=[token, "extra"], prompt=prompt, options=[option])

    assert result.management is True
    assert result.argv == [token, "extra"]
    assert result.target.kind == "official_management"
    assert result.skipped == [
        {"kind": "launch_profile", "id": "default", "reason": "management_invocation"}
    ]


def test_double_dash_boundary_prevents_management_detection(tmp_path):
    prompt = prompt_manifest(tmp_path, "research", "append")

    assert is_management_invocation(["--", "doctor"]) is False
    result = merge(user_argv=["--", "doctor"], prompt=prompt)

    assert result.management is False
    assert result.argv[:2] == ["--append-system-prompt-file", str(prompt.prompt.source.path)]


def test_user_argv_conflict_skips_whole_option_argv_contribution(tmp_path):
    option = option_manifest(
        tmp_path,
        "opus",
        argv=("--model", "opus"),
        conflicts_with_argv=("--model",),
    )

    result = merge(user_argv=["--model", "sonnet"], options=[option])

    assert result.argv == ["--model", "sonnet"]
    assert result.skipped == [
        {"kind": "option_argv", "id": "opus", "reason": "user_argv_conflict"}
    ]


def test_conflicts_with_options_between_enabled_options_creates_error(tmp_path):
    first = option_manifest(tmp_path, "first", conflicts_with_options=("second",))
    second = option_manifest(tmp_path, "second")

    result = merge(options=[first, second])

    assert result.errors == ["option first conflicts with enabled option second"]


def test_process_env_wins_unless_option_allows_override(tmp_path):
    option = option_manifest(
        tmp_path,
        "envs",
        env={
            "KEEP": EnvValue(value="option"),
            "OVERRIDE": EnvValue(value="option", allow_override_process_env=True),
        },
    )

    result = merge(process_env={"KEEP": "process", "OVERRIDE": "process"}, options=[option])

    assert result.env["KEEP"] == "process"
    assert result.env["OVERRIDE"] == "option"
    assert {"kind": "option_env", "id": "envs", "reason": "process_env_wins"} in result.skipped


def test_conflicts_with_env_error_blocks_merge(tmp_path):
    option = option_manifest(
        tmp_path,
        "proxy",
        conflicts_with_env=(EnvConflict(name="HTTP_PROXY", policy="error"),),
    )

    result = merge(process_env={"HTTP_PROXY": "http://proxy"}, options=[option])

    assert result.errors == ["option proxy conflicts with process env HTTP_PROXY"]


def test_value_from_env_and_secret_preview_redaction(tmp_path):
    option = option_manifest(
        tmp_path,
        "secrets",
        env={
            "API_KEY": EnvValue(value="secret-value", secret=True),
            "COPIED": EnvValue(value_from_env="SOURCE_TOKEN", secret=True),
            "MISSING": EnvValue(value_from_env="MISSING_SOURCE"),
        },
    )

    result = merge(process_env={"SOURCE_TOKEN": "copied-secret"}, options=[option])

    assert result.env["API_KEY"] == "secret-value"
    assert result.env["COPIED"] == "copied-secret"
    assert result.env_preview["API_KEY"] == "<redacted>"
    assert result.env_preview["COPIED"] == "<redacted>"
    assert "MISSING" not in result.env
    assert (
        {"kind": "option_env", "id": "secrets", "reason": "missing_value_from_env"}
        in result.skipped
    )
