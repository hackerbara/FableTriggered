import argparse
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEMO_RECORDER_DIR = Path(__file__).resolve().parent
DEFAULT_MATRIX = DEMO_RECORDER_DIR / "demo_matrix.json"
DEFAULT_MATRIX_RECORDINGS_DIR = ROOT / ".development" / "demo-recordings" / "matrix"
EVENT_MARGIN_SECONDS = 1.0
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

TOP_LEVEL_KEYS = {"version", "defaults", "recipes"}
RECIPE_KEYS = {
    "id",
    "demoName",
    "enabled",
    "category",
    "purpose",
    "disabledReason",
    "app",
    "screen",
    "preparedGhostty",
    "cwd",
    "binary",
    "args",
    "recording",
    "events",
    "checkpoints",
    "publishGif",
    "leaveProcessRunning",
}
CHECKPOINT_KEYS = {"name", "atSeconds"}
_RECORD_DEMO_MODULE_PREFIX = "_demo_recorder_record_demo"


class MatrixError(RuntimeError):
    pass


@dataclass(frozen=True)
class Checkpoint:
    name: str
    at_seconds: float


@dataclass(frozen=True)
class Recipe:
    id: str
    demo_name: str | None
    enabled: bool
    category: str
    purpose: str
    disabled_reason: str | None
    app: dict[str, Any]
    screen: dict[str, Any]
    prepared_ghostty: dict[str, Any]
    cwd: Path | None
    binary: Path | None
    args: tuple[str, ...] | None
    recording: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    checkpoints: tuple[Checkpoint, ...]
    publish_gif: Path | None
    leave_process_running: bool


@dataclass(frozen=True)
class Matrix:
    version: int
    defaults: dict[str, Any]
    recipes: tuple[Recipe, ...]


def parse_matrix(path: Path) -> Matrix:
    raw = _load_json(path)
    unknown = set(raw) - TOP_LEVEL_KEYS
    if unknown:
        raise MatrixError(f"unknown matrix keys: {', '.join(sorted(unknown))}")
    if raw.get("version") != 1:
        raise MatrixError("matrix version must be 1")
    defaults = _require_dict(raw.get("defaults"), "defaults")
    recipes_raw = raw.get("recipes")
    if not isinstance(recipes_raw, list):
        raise MatrixError("recipes must be an array")

    recipes: list[Recipe] = []
    seen_ids: set[str] = set()
    for index, recipe_raw in enumerate(recipes_raw):
        recipe = _parse_recipe(_require_dict(recipe_raw, f"recipe {index}"), defaults=defaults)
        if recipe.id in seen_ids:
            raise MatrixError(f"duplicate recipe id: {recipe.id}")
        seen_ids.add(recipe.id)
        recipes.append(recipe)
    return Matrix(version=1, defaults=defaults, recipes=tuple(recipes))


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def materialize_recorder_config(matrix: Matrix, recipe: Recipe) -> dict[str, Any]:
    defaults = matrix.defaults
    app = deep_merge(_require_dict(defaults.get("app"), "defaults.app"), recipe.app)
    screen = deep_merge(_require_dict(defaults.get("screen"), "defaults.screen"), recipe.screen)
    recording = deep_merge(_require_dict(defaults.get("recording"), "defaults.recording"), recipe.recording)
    prepared_ghostty = deep_merge(
        {
            "requireAlreadyRunning": True,
            "requireSingleWindowIfDetectable": True,
            "allowMultipleWindows": False,
            "assumeCleanShellPrompt": True,
        },
        deep_merge(_require_dict(defaults.get("preparedGhostty", {}), "defaults.preparedGhostty"), recipe.prepared_ghostty),
    )
    cwd = recipe.cwd or _optional_path(defaults.get("cwd"), "defaults.cwd")
    if cwd is None:
        raise MatrixError(f"recipe {recipe.id} has no cwd and defaults.cwd is missing")
    if recipe.binary is None:
        raise MatrixError(f"recipe {recipe.id} has no binary to materialize")

    raw_args: tuple[str, ...] | list[Any]
    if recipe.args is not None:
        raw_args = recipe.args
    else:
        default_args = defaults.get("args", [])
        if not isinstance(default_args, list):
            raise MatrixError("defaults.args must be an array of strings")
        raw_args = default_args
    args = list(raw_args)
    if not all(isinstance(arg, str) for arg in args):
        raise MatrixError("materialized command args must be strings")

    return {
        "demoName": recipe.demo_name or recipe.id,
        "app": app,
        "screen": screen,
        "preparedGhostty": prepared_ghostty,
        "command": {
            "cwd": str(cwd),
            "path": str(recipe.binary),
            "args": args,
        },
        "recording": recording,
        "events": list(recipe.events),
        "publish": {
            "enabled": False,
            "outputGif": str(recipe.publish_gif) if recipe.publish_gif else None,
        },
    }

def load_record_demo_module() -> ModuleType:
    return _load_record_demo_module()


def validate_with_record_demo(config_path: Path) -> None:
    record_demo = load_record_demo_module()
    try:
        config = record_demo.parse_config(config_path)
        record_demo.validate_config(config)
    except record_demo.RecorderError as exc:
        raise MatrixError(str(exc)) from exc


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_generated_config(matrix: Matrix, recipe: Recipe, output: Path) -> dict[str, Any]:
    config = materialize_recorder_config(matrix, recipe)
    write_json(output, config)
    validate_with_record_demo(output)
    return config


def validated_recorder_config(matrix: Matrix, recipe: Recipe) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="demo-matrix-dry-run-") as temp:
        output = Path(temp) / f"{recipe.id}.json"
        return write_generated_config(matrix, recipe, output)


def select_recipe(matrix: Matrix, recipe_id: str, *, include_disabled: bool) -> Recipe:
    for recipe in matrix.recipes:
        if recipe.id == recipe_id:
            if recipe.enabled or include_disabled:
                return recipe
            raise MatrixError(f"recipe is disabled: {recipe_id}")
    raise MatrixError(f"unknown recipe id: {recipe_id}")


def enabled_recipes(matrix: Matrix) -> tuple[Recipe, ...]:
    return tuple(recipe for recipe in matrix.recipes if recipe.enabled)


def list_rows(matrix: Matrix) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for recipe in matrix.recipes:
        rows.append(
            {
                "id": recipe.id,
                "enabled": recipe.enabled,
                "category": recipe.category,
                "purpose": recipe.purpose,
                "binaryExists": bool(recipe.binary and recipe.binary.exists() and recipe.binary.is_file()),
                "disabledReason": recipe.disabled_reason,
            }
        )
    return rows


def print_list(matrix: Matrix) -> None:
    for row in list_rows(matrix):
        state = "enabled" if row["enabled"] else "disabled"
        binary = "binary:yes" if row["binaryExists"] else "binary:no"
        reason = f" disabledReason={row['disabledReason']}" if row.get("disabledReason") else ""
        print(f"{row['id']}\t{state}\t{row['category']}\t{binary}\t{row['purpose']}{reason}")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def make_matrix_run_dir(base: Path = DEFAULT_MATRIX_RECORDINGS_DIR) -> Path:
    run_dir = base / timestamp()
    suffix = 1
    candidate = run_dir
    while candidate.exists():
        suffix += 1
        candidate = base / f"{run_dir.name}-{suffix}"
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def checkpoint_argv(raw: Path, output: Path, at_seconds: float) -> list[str]:
    return ["ffmpeg", "-y", "-ss", str(at_seconds), "-i", str(raw), "-frames:v", "1", str(output)]


def extract_checkpoint(raw: Path, output: Path, at_seconds: float) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        checkpoint_argv(raw, output, at_seconds),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else f"exit code {result.returncode}"
        raise MatrixError(f"checkpoint extraction failed for {output}: {stderr}")
    _ensure_existing_nonempty(output, "checkpoint frame")
    return output


def summary_record(
    recipe: Recipe,
    generated_config: Path,
    metadata: dict[str, Any],
    checkpoints: dict[str, Path],
) -> dict[str, Any]:
    launch = metadata.get("launch") if isinstance(metadata.get("launch"), dict) else {}
    launch_verified = bool(metadata.get("launchVerified") or launch.get("verified"))
    review_status = str(metadata.get("reviewStatus") or "needs-human-review")
    published = metadata.get("published")
    return {
        "id": recipe.id,
        "status": "recorded",
        "recordingStatus": str(metadata.get("recordingStatus") or "recorded"),
        "launchStatus": "verified" if launch_verified else "unverified",
        "launchVerified": launch_verified,
        "reviewStatus": review_status,
        "needsReview": review_status != "approved",
        "publishStatus": "published" if published else "not-published",
        "generatedConfig": str(generated_config),
        "runDir": _required_metadata_path(metadata, "runDir"),
        "raw": _required_metadata_path(metadata, "raw"),
        "gif": _required_metadata_path(metadata, "gif"),
        "published": published,
        "launch": launch or None,
        "checkpoints": {name: str(path) for name, path in sorted(checkpoints.items())},
        "publishGif": str(recipe.publish_gif) if recipe.publish_gif else None,
    }

def write_summary_markdown(summary_path: Path, summary: dict[str, Any]) -> Path:
    markdown_path = summary_path.with_suffix(".md")
    lines = [
        "# Demo matrix summary",
        "",
        f"- Matrix: `{summary['matrix']}`",
        f"- Batch: `{summary['batchDir']}`",
        "",
        "> This summary proves media files were generated. It does not approve publication. Open the GIF and checkpoint PNGs before publishing.",
        "",
        "| Recipe | Recording | Launch | Review | GIF | Publish target |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in summary["records"]:
        lines.append(
            f"| `{record.get('id')}` | {record.get('recordingStatus', record.get('status'))} | {record.get('launchStatus')} | {record.get('reviewStatus')} | `{record.get('gif')}` | `{record.get('publishGif')}` |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return markdown_path

def run_recipe(matrix: Matrix, recipe: Recipe, batch_dir: Path) -> dict[str, Any]:
    generated_config = batch_dir / "generated-configs" / f"{recipe.id}.json"
    write_generated_config(matrix, recipe, generated_config)

    record_demo = load_record_demo_module()
    try:
        parsed = record_demo.parse_config(generated_config)
        record_demo.validate_config(parsed)
        metadata = record_demo.run_recording(parsed, generated_config, cli_publish=False)
    except record_demo.RecorderError as exc:
        raise MatrixError(str(exc)) from exc

    raw = Path(_required_metadata_path(metadata, "raw"))
    gif = Path(_required_metadata_path(metadata, "gif"))
    _ensure_existing_nonempty(raw, "raw recording")
    _ensure_existing_nonempty(gif, "gif")

    checkpoints: dict[str, Path] = {}
    for checkpoint in recipe.checkpoints:
        output = batch_dir / "checkpoints" / f"{recipe.id}-{checkpoint.name}.png"
        checkpoints[checkpoint.name] = extract_checkpoint(raw, output, checkpoint.at_seconds)

    return summary_record(recipe, generated_config, metadata, checkpoints)


def write_batch_summary(batch_dir: Path, matrix_path: Path, records: list[dict[str, Any]]) -> Path:
    batch_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "matrix": str(matrix_path),
        "batchDir": str(batch_dir),
        "records": records,
    }
    summary_path = batch_dir / "summary.json"
    write_json(summary_path, summary)
    write_summary_markdown(summary_path, summary)
    return summary_path


def publish_from_summary(summary_path: Path, recipe_id: str) -> Path:
    summary = _load_json_labeled(summary_path, "summary")
    records = summary.get("records")
    if not isinstance(records, list):
        raise MatrixError("summary.records must be an array")
    for raw_record in records:
        record = _require_dict(raw_record, "summary record")
        if record.get("id") != recipe_id:
            continue
        if record.get("reviewStatus") != "approved":
            raise MatrixError(f"summary record for {recipe_id} is not review approved")
        if record.get("launchVerified") is not True:
            raise MatrixError(f"summary record for {recipe_id} does not have verified launch")
        gif = _path_from_record(record, "gif")
        publish_gif = _path_from_record(record, "publishGif")
        _ensure_existing_nonempty(gif, "gif")
        _validate_publish_gif(publish_gif, recipe_id=recipe_id)
        publish_gif.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gif, publish_gif)
        return publish_gif
    raise MatrixError(f"recipe not found in summary: {recipe_id}")

def _required_metadata_path(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise MatrixError(f"recording metadata missing {key}")
    return value


def _path_from_record(record: dict[str, Any], key: str) -> Path:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise MatrixError(f"summary record missing {key}")
    return Path(value)


def _ensure_existing_nonempty(path: Path, label: str) -> None:
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        raise MatrixError(f"{label} is missing or empty: {path}")


def _load_json_labeled(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MatrixError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MatrixError(f"invalid JSON in {path}: {exc}") from exc
    return _require_dict(data, label)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run curated ClaudeMonkey demo recorder recipes")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX, help="Path to demo_matrix.json")
    parser.add_argument("--list", action="store_true", help="List matrix recipes")
    parser.add_argument("--id", dest="recipe_id", help="Run or dry-run one recipe id")
    parser.add_argument("--include-disabled", action="store_true", help="Allow --id to select a disabled recipe")
    parser.add_argument("--all-enabled", action="store_true", help="Run all enabled recipes in matrix order")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print generated recorder configs without recording")
    parser.add_argument("--publish-from-summary", type=Path, help="Copy one reviewed GIF from a batch summary to its publishGif target")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        _validate_cli_modes(args)
        if args.publish_from_summary:
            published = publish_from_summary(args.publish_from_summary, args.recipe_id)
            print(json.dumps({"published": str(published)}, indent=2, sort_keys=True))
            return 0

        matrix = parse_matrix(args.matrix)
        if args.list:
            print_list(matrix)
            return 0
        if args.dry_run:
            if args.recipe_id:
                recipe = select_recipe(matrix, args.recipe_id, include_disabled=args.include_disabled)
                print(json.dumps(validated_recorder_config(matrix, recipe), indent=2, sort_keys=True))
                return 0
            if args.all_enabled:
                configs = [validated_recorder_config(matrix, recipe) for recipe in enabled_recipes(matrix)]
                print(json.dumps(configs, indent=2, sort_keys=True))
                return 0
            raise MatrixError("--dry-run requires --id or --all-enabled")
        if args.recipe_id or args.all_enabled:
            print("Privacy reminder: verify the desktop is ready before recording; this CLI will not publish GIFs.")
            batch_dir = make_matrix_run_dir()
            write_json(batch_dir / "matrix.snapshot.json", _load_json(args.matrix))
            if args.recipe_id:
                recipes = [select_recipe(matrix, args.recipe_id, include_disabled=args.include_disabled)]
            else:
                recipes = list(enabled_recipes(matrix))
            records = [run_recipe(matrix, recipe, batch_dir) for recipe in recipes]
            write_batch_summary(batch_dir, args.matrix, records)
            print(json.dumps({"batchDir": str(batch_dir), "records": records}, indent=2, sort_keys=True))
            return 0
        raise MatrixError("v1 CLI requires --list, --dry-run, --id, --all-enabled, or --publish-from-summary")
    except MatrixError as exc:
        print(f"demo-matrix: {exc}", file=sys.stderr)
        return 2


def _validate_cli_modes(args: argparse.Namespace) -> None:
    if args.list:
        ignored_with_list = [
            "--id" if args.recipe_id else None,
            "--all-enabled" if args.all_enabled else None,
            "--dry-run" if args.dry_run else None,
            "--include-disabled" if args.include_disabled else None,
            "--publish-from-summary" if args.publish_from_summary else None,
        ]
        ignored_with_list = [option for option in ignored_with_list if option is not None]
        if ignored_with_list:
            raise MatrixError(f"conflicting CLI options with --list: {', '.join(ignored_with_list)}")

    selected_modes = [
        "--list" if args.list else None,
        "--dry-run" if args.dry_run else None,
        "--publish-from-summary" if args.publish_from_summary else None,
    ]
    selected_modes = [mode for mode in selected_modes if mode is not None]
    if len(selected_modes) > 1:
        raise MatrixError(f"conflicting CLI modes: {', '.join(selected_modes)}")

    if args.publish_from_summary:
        if not args.recipe_id:
            raise MatrixError("--publish-from-summary requires --id")
        if args.all_enabled:
            raise MatrixError("--publish-from-summary publishes exactly one --id, not --all-enabled")

    selected_targets = [
        "--id" if args.recipe_id else None,
        "--all-enabled" if args.all_enabled else None,
    ]
    selected_targets = [target for target in selected_targets if target is not None]
    if len(selected_targets) > 1:
        target_label = "dry-run targets" if args.dry_run else "recording targets"
        raise MatrixError(f"conflicting {target_label}: {', '.join(selected_targets)}")
    if args.dry_run and not selected_targets:
        raise MatrixError("--dry-run requires exactly one of --id or --all-enabled")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MatrixError(f"matrix not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MatrixError(f"invalid JSON in {path}: {exc}") from exc
    return _require_dict(data, "matrix")


def _parse_recipe(raw: dict[str, Any], *, defaults: dict[str, Any]) -> Recipe:
    unknown = set(raw) - RECIPE_KEYS
    if unknown:
        raise MatrixError(f"unknown recipe keys: {', '.join(sorted(unknown))}")

    recipe_id = _require_string(raw.get("id"), "recipe.id")
    _ensure_safe_id(recipe_id, "recipe.id")
    enabled = _require_bool(raw.get("enabled", False), f"recipe {recipe_id}.enabled")
    leave_process_running = _require_bool(
        raw.get("leaveProcessRunning", False), f"recipe {recipe_id}.leaveProcessRunning"
    )
    disabled_reason = _optional_string(raw.get("disabledReason"), f"recipe {recipe_id}.disabledReason")
    binary = _optional_path(raw.get("binary"), f"recipe {recipe_id}.binary")
    cwd = _optional_path(raw.get("cwd", defaults.get("cwd")), f"recipe {recipe_id}.cwd")

    if enabled:
        if binary is None:
            raise MatrixError(f"recipe {recipe_id} binary is required when enabled")
        if not binary.exists() or not binary.is_file():
            raise MatrixError(f"recipe {recipe_id} binary does not exist or is not a file: {binary}")
        if cwd is None or not cwd.exists() or not cwd.is_dir():
            raise MatrixError(f"recipe {recipe_id} cwd does not exist or is not a directory: {cwd}")
    elif binary is None and disabled_reason is None:
        raise MatrixError(f"recipe {recipe_id} disabledReason is required when disabled recipe omits binary")

    recording = _merged_recording(defaults, raw)
    record_seconds = _record_seconds(recording)
    events = _parse_events(raw.get("events", []), recipe_id=recipe_id)
    _validate_events(
        events,
        enabled=enabled,
        record_seconds=record_seconds,
        leave_process_running=leave_process_running,
    )
    checkpoints = _parse_checkpoints(raw.get("checkpoints"), record_seconds=record_seconds)
    publish_gif = _optional_path(raw.get("publishGif"), f"recipe {recipe_id}.publishGif")
    _validate_publish_gif(publish_gif, recipe_id=recipe_id)

    return Recipe(
        id=recipe_id,
        demo_name=_optional_string(raw.get("demoName"), f"recipe {recipe_id}.demoName"),
        enabled=enabled,
        category=_require_string(raw.get("category"), f"recipe {recipe_id}.category"),
        purpose=_require_string(raw.get("purpose"), f"recipe {recipe_id}.purpose"),
        disabled_reason=disabled_reason,
        app=_merged_object(defaults, raw, "app"),
        screen=_merged_object(defaults, raw, "screen"),
        prepared_ghostty=_merged_object(defaults, raw, "preparedGhostty"),
        cwd=cwd,
        binary=binary,
        args=_parse_args(raw.get("args", defaults.get("args")), recipe_id=recipe_id),
        recording=recording,
        events=events,
        checkpoints=checkpoints,
        publish_gif=publish_gif,
        leave_process_running=leave_process_running,
    )


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MatrixError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MatrixError(f"{label} must be a non-empty string")
    return value


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, label)


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise MatrixError(f"{label} must be a boolean")
    return value


def _optional_path(value: Any, label: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise MatrixError(f"{label} must be a non-empty string when present")
    return Path(value).expanduser()


def _ensure_safe_id(value: str, label: str) -> None:
    if SAFE_ID_RE.fullmatch(value) is None:
        raise MatrixError(f"{label} is not path-safe: {value!r}")


def _merged_object(defaults: dict[str, Any], recipe: dict[str, Any], key: str) -> dict[str, Any]:
    base = defaults.get(key, {})
    override = recipe.get(key, {})
    return {**_require_dict(base, f"defaults.{key}"), **_require_dict(override, f"recipe.{key}")}


def _merged_recording(defaults: dict[str, Any], recipe: dict[str, Any]) -> dict[str, Any]:
    return _merged_object(defaults, recipe, "recording")


def _record_seconds(recording: dict[str, Any]) -> float:
    return _require_finite_number(recording.get("recordSeconds"), "recording.recordSeconds", positive=True)


def _parse_args(value: Any, *, recipe_id: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise MatrixError(f"recipe {recipe_id}.args must be an array of strings")
    return tuple(value)


def _parse_events(value: Any, *, recipe_id: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        raise MatrixError(f"recipe {recipe_id}.events must be an array")
    events: list[dict[str, Any]] = []
    for index, event in enumerate(value):
        events.append(dict(_require_dict(event, f"event {index}")))
    return tuple(events)


def _validate_events(
    events: tuple[dict[str, Any], ...], *, enabled: bool, record_seconds: float, leave_process_running: bool
) -> None:
    _validate_record_demo_events(events)
    total_wait = 0.0
    for index, event in enumerate(events):
        if event.get("type") == "wait":
            total_wait += _require_finite_number(event.get("seconds"), f"event {index} wait.seconds", nonnegative=True)
    if enabled and not leave_process_running:
        if total_wait + EVENT_MARGIN_SECONDS >= record_seconds:
            raise MatrixError("wait schedule must leave EVENT_MARGIN_SECONDS before recording end")
        if not events or events[-1].get("type") != "key" or events[-1].get("key") != "ctrl-c":
            raise MatrixError("enabled recipes with leaveProcessRunning=false must define events ending with ctrl-c")


def _parse_checkpoints(value: Any, *, record_seconds: float) -> tuple[Checkpoint, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise MatrixError("checkpoints must be an array")
    checkpoints: list[Checkpoint] = []
    seen: set[str] = set()
    for index, checkpoint_raw in enumerate(value):
        checkpoint = _require_dict(checkpoint_raw, f"checkpoint {index}")
        unknown = set(checkpoint) - CHECKPOINT_KEYS
        if unknown:
            raise MatrixError(f"unknown checkpoint keys: {', '.join(sorted(unknown))}")
        name = _require_string(checkpoint.get("name"), f"checkpoint {index}.name")
        _ensure_safe_id(name, f"checkpoint {index}.name")
        if name in seen:
            raise MatrixError(f"duplicate checkpoint name: {name}")
        seen.add(name)
        at_seconds = _require_finite_number(checkpoint.get("atSeconds"), f"checkpoint time for {name}", nonnegative=True)
        if at_seconds >= record_seconds:
            raise MatrixError(f"checkpoint time must be >= 0 and < recordSeconds for {name}")
        checkpoints.append(Checkpoint(name=name, at_seconds=at_seconds))
    return tuple(checkpoints)


def _validate_publish_gif(path: Path | None, *, recipe_id: str) -> None:
    if path is None:
        return
    allowed_root = (ROOT / "assets" / "demos").resolve()
    resolved = path.resolve()
    try:
        is_allowed = resolved.is_relative_to(allowed_root)
    except AttributeError:
        is_allowed = allowed_root == resolved or allowed_root in resolved.parents
    if not is_allowed:
        raise MatrixError(f"recipe {recipe_id} publishGif must be under {allowed_root}: {path}")


def _require_finite_number(value: Any, label: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise MatrixError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        if positive:
            raise MatrixError(f"{label} must be a finite positive number")
        if label.startswith("checkpoint time"):
            raise MatrixError("checkpoint time must be finite")
        raise MatrixError(f"{label} must be finite")
    if positive and number <= 0:
        raise MatrixError(f"{label} must be a finite positive number")
    if nonnegative and number < 0:
        raise MatrixError(f"{label} must be non-negative")
    return number


def _validate_record_demo_events(events: tuple[dict[str, Any], ...]) -> None:
    record_demo = _load_record_demo_module()
    try:
        record_demo.validate_events(events)
    except record_demo.RecorderError as exc:
        raise MatrixError(str(exc)) from exc


def _load_record_demo_module() -> ModuleType:
    path = (DEMO_RECORDER_DIR / "record_demo.py").resolve()
    module_name = _record_demo_module_name(path)
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise MatrixError(f"unable to load record_demo.py from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _record_demo_module_name(path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    return f"{_RECORD_DEMO_MODULE_PREFIX}_{digest}"


if __name__ == "__main__":
    raise SystemExit(main())
