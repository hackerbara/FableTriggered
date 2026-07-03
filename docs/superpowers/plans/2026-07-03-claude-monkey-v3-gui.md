# ClaudeMonkey v3 GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rumps menu bar with a PySide6 tray + manager window + single progress dialog, per `docs/superpowers/specs/2026-07-03-claude-monkey-v3-gui-design.md`.

**Architecture:** Pure-Python view-models (`window_model`, `progress_model`) decide everything; thin Qt files render. All mutations go through the `claude-monkey` CLI with `--json`. New: a progress-event protocol produced by instrumented builder/install transactions and streamed over stderr JSONL; kind-specific `add-*`/`remove-*` package commands.

**Tech Stack:** PySide6, pyobjc-framework-Cocoa (macOS only), Pillow (dev), pytest + pytest-qt.

## Global Constraints

- Python `>=3.11`; ruff `line-length = 100`, `select = ["E","F","I","UP","B"]` — run `ruff check src tests` before every commit.
- `[gui]` extra is exactly: `PySide6` and `pyobjc-framework-Cocoa ; sys_platform == "darwin"`. rumps is removed.
- The GUI never touches managed files directly — every mutation is a CLI subprocess with `--json`.
- With `--progress`, a command's **stdout must be byte-identical** to a run without it; all progress events go to stderr as one JSON object per line.
- Adding a package never activates/enables it.
- Package storage (phase 1): `~/.claude-monkey/patches/<id>/`, `~/.claude-monkey/prompts/<id>/`, `~/.claude-monkey/options/<id>/`. `~/.claude-patches` must not appear in new code.
- Qt tests run with `QT_QPA_PLATFORM=offscreen` (set in the test file via `os.environ.setdefault` before importing PySide6).
- **Concurrency caution:** phase 1 (package model, spec `2026-07-02-claude-monkey-v3-enhancements-design.md` §§2–15) is being implemented in parallel. Task 0 gates this plan on phase 1 being merged. Tasks 4–7 touch `cli.py`/`menubar_state.py`, which phase 1 also modifies — do not start them until Task 0 passes.
- Where a step says `# ADAPT:`, the exact symbol name comes from the phase-1 code as recorded in Task 0's contract notes; the surrounding logic is fixed.

## Phase-1 contracts this plan assumes (from old-V3 spec §§7, 10, 11, 13)

- Commands: `list-patches|list-prompts|list-options --json`; `enable-patch|disable-patch <id> --json`; `set-prompt <id> --json`, `clear-prompt --json`; `enable-option <id> [--confirm] --json`, `disable-option <id> --json`.
- Mutating envelope: `{schemaVersion, ok, status, summary, error:{message,code}|null, warnings:[]}`; high-risk enable without `--confirm` → `ok:false`, `error.code:"confirmation_required"`.
- List payloads: top-level `patches`/`prompts`/`options` arrays of `{id,label,kind,enabled|active,valid,compatibilityStatus,riskLevel,errors}`.
- `status --json` includes `activePrompt`, `desiredPatchIds`, `activePatchIds`, `activeOptionIds`, `highRiskOptions`, `compatibilityStatus`, `rebuildRequired`, `latestBuildReportPath`.
- Config: `~/.claude-monkey/config.json` with `profiles.default.{prompt, patches, options}`.

---

### Task 0: Phase-1 gate + contract notes

**Files:**
- Create: `docs/superpowers/plans/2026-07-03-phase1-contract-notes.md`

**Interfaces:**
- Produces: the contract-notes doc every `# ADAPT:` marker in later tasks reads from.

- [ ] **Step 1: Verify phase 1 is merged and the CLI surface exists**

Run each; every one must exit 0 and emit JSON:

```bash
python3 -m claude_monkey list-patches --json
python3 -m claude_monkey list-prompts --json
python3 -m claude_monkey list-options --json
python3 -m claude_monkey status --json
```

Expected: `list-options` succeeds (it does not exist in v2 — if it fails with "invalid choice", **phase 1 has not landed; STOP and report**). `status --json` contains `activeOptionIds`.

- [ ] **Step 2: Record phase-1 symbols in contract notes**

Read the phase-1 source and write `docs/superpowers/plans/2026-07-03-phase1-contract-notes.md` recording, with `file:line` citations:
1. The module + function that loads/validates a package manifest envelope (used by discovery) — name, signature, exception type on invalid.
2. The function/constant that yields the per-kind package roots under `~/.claude-monkey`.
3. How the active profile is read/written (module + function for `config.json` access).
4. The exact `status --json` key set (paste one real redacted payload).
5. Which functions `list-patches`/`list-options` use to build item records.

- [ ] **Step 3: Verify existing test suite is green before building on it**

Run: `python3 -m pytest tests/ -x -q`
Expected: PASS. If phase 1 left failures, STOP and report.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-07-03-phase1-contract-notes.md
git commit -m "docs: record phase-1 contract notes for GUI plan"
```

---

### Task 1: Dependencies + progress event core

**Files:**
- Modify: `pyproject.toml:12-24`
- Create: `src/claude_monkey/progress.py`
- Test: `tests/test_progress_events.py`

**Interfaces:**
- Produces: `ProgressEvent` helpers and `StageTracker` used by Tasks 2–4:
  - `plan_event(stages: tuple[tuple[str, str], ...]) -> dict`
  - `stage_event(stage_id: str, status: str, message: str | None = None) -> dict`
  - `log_event(stage_id: str | None, line: str) -> dict`
  - `class StageTracker: __init__(self, on_event: Callable[[dict], None] | None)`, methods `plan(stages)`, `start(stage_id)`, `done()`, `skip(stage_id, message=None)`, `fail(message)`, `log(line)`; every method is a no-op when `on_event is None`; callback exceptions are swallowed.

- [ ] **Step 1: Update pyproject extras**

In `pyproject.toml` replace the `gui` extra and extend `dev`:

```toml
dev = [
  "pytest>=8.2",
  "pytest-qt>=4.4",
  "ruff>=0.5",
  "Pillow>=10.0"
]
gui = [
  "PySide6>=6.7",
  "pyobjc-framework-Cocoa>=10.0 ; sys_platform == 'darwin'"
]
```

(Entry-point retarget happens in Task 19, when the target exists.)

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_progress_events.py
from claude_monkey.progress import StageTracker, log_event, plan_event, stage_event


def test_event_shapes():
    assert plan_event((("a", "A"),)) == {
        "event": "plan",
        "stages": [{"id": "a", "label": "A"}],
    }
    assert stage_event("a", "running") == {"event": "stage", "id": "a", "status": "running"}
    assert stage_event("a", "failed", "boom") == {
        "event": "stage", "id": "a", "status": "failed", "message": "boom",
    }
    assert log_event("a", "hi") == {"event": "log", "stage": "a", "line": "hi"}


def test_tracker_lifecycle_and_fail_targets_current_stage():
    seen: list[dict] = []
    t = StageTracker(seen.append)
    t.plan((("a", "A"), ("b", "B")))
    t.start("a")
    t.done()
    t.start("b")
    t.fail("boom")
    assert [e.get("status") for e in seen[1:]] == ["running", "done", "running", "failed"]
    assert seen[-1] == {"event": "stage", "id": "b", "status": "failed", "message": "boom"}


def test_tracker_none_callback_and_swallowed_exceptions():
    t = StageTracker(None)
    t.plan((("a", "A"),)); t.start("a"); t.done(); t.fail("x"); t.log("y")  # no raise

    def bad(_e): raise RuntimeError("listener bug")
    t2 = StageTracker(bad)
    t2.start("a")  # must not raise
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_progress_events.py -q`
Expected: FAIL — `ModuleNotFoundError: claude_monkey.progress`

- [ ] **Step 4: Implement `src/claude_monkey/progress.py`**

```python
from __future__ import annotations

from collections.abc import Callable

OnEvent = Callable[[dict], None] | None


def plan_event(stages: tuple[tuple[str, str], ...]) -> dict:
    return {"event": "plan", "stages": [{"id": i, "label": l} for i, l in stages]}


def stage_event(stage_id: str, status: str, message: str | None = None) -> dict:
    event: dict = {"event": "stage", "id": stage_id, "status": status}
    if message is not None:
        event["message"] = message
    return event


def log_event(stage_id: str | None, line: str) -> dict:
    return {"event": "log", "stage": stage_id, "line": line}


class StageTracker:
    def __init__(self, on_event: OnEvent) -> None:
        self._on_event = on_event
        self.current: str | None = None

    def _emit(self, event: dict) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(event)
        except Exception:  # noqa: BLE001 - progress must never break the operation
            pass

    def plan(self, stages: tuple[tuple[str, str], ...]) -> None:
        self._emit(plan_event(stages))

    def start(self, stage_id: str) -> None:
        self.current = stage_id
        self._emit(stage_event(stage_id, "running"))

    def done(self) -> None:
        if self.current is not None:
            self._emit(stage_event(self.current, "done"))
            self.current = None

    def skip(self, stage_id: str, message: str | None = None) -> None:
        self._emit(stage_event(stage_id, "skipped", message))

    def fail(self, message: str) -> None:
        if self.current is not None:
            self._emit(stage_event(self.current, "failed", message))
            self.current = None

    def log(self, line: str) -> None:
        self._emit(log_event(self.current, line))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_progress_events.py -q && ruff check src tests`
Expected: PASS, no lint errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/claude_monkey/progress.py tests/test_progress_events.py
git commit -m "feat: progress event core + PySide6 gui extra"
```

---

### Task 2: Builder stage instrumentation

**Files:**
- Modify: `src/claude_monkey/builder_v15.py` (dataclass `BuildRequestV15`; function `build_patchset_v15`, currently lines 367–543)
- Test: `tests/test_builder_progress.py`

**Interfaces:**
- Consumes: `StageTracker` from Task 1.
- Produces: `BUILD_STAGES: tuple[tuple[str, str], ...]` module constant; `BuildRequestV15` gains field `on_event: Callable[[dict], None] | None = None`. Stage order: `resolve → repack → sign → inspect → smoke → activate`.

- [ ] **Step 1: Write the failing tests**

Reuse the fixture helpers `tests/test_builder_v15.py` already uses to build a request against a fake source binary (import the same helpers; do not duplicate fixture construction). Collect events via `on_event=events.append`.

```python
# tests/test_builder_progress.py  (fixture imports per tests/test_builder_v15.py)
from claude_monkey.builder_v15 import BUILD_STAGES, build_patchset_v15


def _stage_seq(events):
    return [(e["id"], e["status"]) for e in events if e["event"] == "stage"]


def test_success_emits_plan_then_stages_in_table_order(successful_build_request, tmp_path):
    events: list[dict] = []
    request = successful_build_request(on_event=events.append, activate=False)
    report = build_patchset_v15(request)
    assert report.status == "verified"
    assert events[0]["event"] == "plan"
    assert [s["id"] for s in events[0]["stages"]] == [i for i, _ in BUILD_STAGES]
    seq = _stage_seq(events)
    assert ("resolve", "done") in seq and ("smoke", "done") in seq
    assert seq[-1] == ("activate", "skipped")   # activate=False


def test_manifest_failure_fails_resolve_stage(bad_manifest_build_request):
    events: list[dict] = []
    report = build_patchset_v15(bad_manifest_build_request(on_event=events.append))
    assert report.status == "failed"
    failed = [e for e in events if e.get("status") == "failed"]
    assert failed and failed[-1]["id"] == "resolve"


def test_none_on_event_changes_nothing(successful_build_request):
    report = build_patchset_v15(successful_build_request(on_event=None, activate=False))
    assert report.status == "verified"
```

(If `tests/test_builder_v15.py` exposes no reusable request factory, first extract one into `tests/builder_fixtures.py` and refactor `test_builder_v15.py` to use it — pure test refactor, same assertions.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_builder_progress.py -q`
Expected: FAIL — `ImportError: cannot import name 'BUILD_STAGES'`

- [ ] **Step 3: Implement instrumentation**

In `builder_v15.py` add near the top:

```python
from claude_monkey.progress import StageTracker

BUILD_STAGES: tuple[tuple[str, str], ...] = (
    ("resolve", "Resolve patches"),
    ("repack", "Repack binary"),
    ("sign", "Sign"),
    ("inspect", "Inspect signed binary"),
    ("smoke", "Smoke test"),
    ("activate", "Activate"),
)
```

Add to the `BuildRequestV15` dataclass: `on_event: Callable[[dict], None] | None = None`.

Thread a tracker through `build_patchset_v15` at these existing seams (line refs to current code):

- Function entry: `tracker = StageTracker(request.on_event)`, `tracker.plan(BUILD_STAGES)`, `tracker.start("resolve")` — before `request.output_dir.mkdir` (line 368).
- `_select_packages` failure return (line 372): `tracker.fail(failure.failureReason)` before `return failure`.
- Immediately before `repack = repack_changed_modules(...)` (line 422): `tracker.done()`, `tracker.start("repack")`.
- After `report.verificationResults = verification_results` (line 467): `tracker.done()`.
- Signing block (lines 469–476): `run_signing` true → `tracker.start("sign")`; on `_apply_signing_v15` returning False → `tracker.fail("signing failed")` before the return; on success → `tracker.done()`. Else branch → `tracker.skip("sign", "signing skipped")`.
- Inspection (lines 477–490): `tracker.start("inspect")` before `output.read_bytes()`; failure return → `tracker.fail("post-sign inspection failed")`; else `tracker.done()`.
- Smoke (lines 491–504): mirror sign: start/fail("smoke test failed")/done, or `tracker.skip("smoke", "smoke skipped")`.
- Activation (lines 523–533): `request.activate` and activated → `start("activate")` + `done()`; `request.activate` and blocked → `start("activate")` + `fail("activation blocked: " + ", ".join(report.activationBlockers))`; not `request.activate` → `tracker.skip("activate", "activation not requested")`.
- The final `except Exception as exc:` (line 536): `tracker.fail(str(exc))` first.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_builder_progress.py tests/test_builder_v15.py tests/test_cli_v15.py -q && ruff check src tests`
Expected: PASS — existing builder/CLI tests unaffected (`on_event` defaults to `None`).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/builder_v15.py tests/test_builder_progress.py
git commit -m "feat: emit progress stage events from build_patchset_v15"
```

---

### Task 3: Shim transaction stage instrumentation

**Files:**
- Modify: `src/claude_monkey/install.py` (`install_shim_transaction` lines 174–212, `restore_install_transaction` lines 225–260)
- Test: `tests/test_install_progress.py`

**Interfaces:**
- Consumes: `StageTracker` from Task 1.
- Produces: `SHIM_STAGES: tuple[tuple[str, str], ...] = (("preflight", "Preflight checks"), ("record", "Write install record"), ("swap", "Swap shim"))`; both transactions gain keyword-only `on_event: Callable[[dict], None] | None = None`.

- [ ] **Step 1: Write the failing tests**

Follow the tmp-dir fixture style of `tests/test_install.py` (user-writable target under `tmp_path`, no authorization path):

```python
# tests/test_install_progress.py
from claude_monkey.install import SHIM_STAGES, install_shim_transaction, restore_install_transaction


def _stage_seq(events):
    return [(e["id"], e["status"]) for e in events if e["event"] == "stage"]


def test_install_emits_three_stages(tmp_path):
    events: list[dict] = []
    target = tmp_path / "bin" / "claude"
    record = install_shim_transaction(
        target, tmp_path / "state", dry_run=False, on_event=events.append
    )
    assert record.exists()
    assert events[0]["event"] == "plan"
    assert _stage_seq(events) == [
        ("preflight", "running"), ("preflight", "done"),
        ("record", "running"), ("record", "done"),
        ("swap", "running"), ("swap", "done"),
    ]


def test_dry_run_stops_after_preflight(tmp_path):
    events: list[dict] = []
    install_shim_transaction(
        tmp_path / "claude", tmp_path / "state", dry_run=True, on_event=events.append
    )
    assert _stage_seq(events) == [("preflight", "running"), ("preflight", "done")]


def test_restore_missing_record_fails_preflight(tmp_path):
    events: list[dict] = []
    ok = restore_install_transaction(
        tmp_path / "claude", tmp_path / "record.json", force=False, on_event=events.append
    )
    assert ok is False
    assert _stage_seq(events)[-1] == ("preflight", "failed")


def test_none_on_event_unchanged(tmp_path):
    record = install_shim_transaction(tmp_path / "claude", tmp_path / "state", dry_run=False)
    assert record.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_install_progress.py -q`
Expected: FAIL — `ImportError: cannot import name 'SHIM_STAGES'`

- [ ] **Step 3: Implement**

In `install.py`: add `SHIM_STAGES` constant and the `on_event` kwarg. `install_shim_transaction` mapping:

- `preflight` wraps: refusal check + `_existing_managed_record` + `previous` computation (lines 176–189). `ProtectedTargetRestoreUnavailable` → `tracker.fail(str(exc))` then re-raise. `dry_run` → `done()` then return (line 202–203).
- `record` wraps: state-dir mkdir + `_cache_previous_source` + `record_path.write_text` (lines 190–204).
- `swap` wraps: `_write_shim_to_target` (line 206); the existing `except Exception` cleanup block (lines 207–211) gets `tracker.fail(str(exc))` before re-raise.

`restore_install_transaction`: `preflight` wraps the record-existence/owner/target checks (lines 226–233, each `return False` → `fail("<specific reason>")` first, e.g. `"no install record"`, `"record owned by another tool"`, `"target is not the managed shim"`); `record` wraps `previous_type` validation; `swap` wraps the removal/restore branches, `done()` before `return True`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_install_progress.py tests/test_install.py -q && ruff check src tests`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/install.py tests/test_install_progress.py
git commit -m "feat: emit progress stage events from shim transactions"
```

---

### Task 4: CLI `--progress` flag

**Files:**
- Modify: `src/claude_monkey/cli.py` (the `build`, `install-shim`, `uninstall-shim` argparse parsers and their handlers — locate by parser name; phase 1 may have moved lines)
- Test: `tests/test_cli_progress_contract.py`

**Interfaces:**
- Consumes: `on_event` params from Tasks 2–3; `BUILD_STAGES`/`SHIM_STAGES`.
- Produces: `--progress` flag on the three commands; `claude_monkey.cli._progress_emitter(enabled: bool) -> Callable[[dict], None] | None` writing one sorted-key JSON object per line to stderr with `flush=True`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_progress_contract.py
import json

from claude_monkey import cli


def _fake_build(monkeypatch, tmp_path):
    """Monkeypatch build_patchset_v15 to a fake that emits two events and succeeds."""
    def fake(request):
        if request.on_event:
            request.on_event({"event": "stage", "id": "resolve", "status": "running"})
            request.on_event({"event": "stage", "id": "resolve", "status": "done"})
        return _minimal_verified_report(tmp_path)  # helper mirroring tests/test_cli_v15.py fakes
    monkeypatch.setattr(cli, "build_patchset_v15", fake)  # ADAPT: patch where cli imports it


def test_stdout_byte_identical_with_and_without_progress(monkeypatch, tmp_path, capsys):
    _fake_build(monkeypatch, tmp_path)
    cli.main(["build", "--json"])            # ADAPT: plus whatever source/state args the fake needs
    plain = capsys.readouterr().out
    cli.main(["build", "--json", "--progress"])
    with_progress = capsys.readouterr()
    assert with_progress.out == plain
    lines = [l for l in with_progress.err.splitlines() if l.strip()]
    events = [json.loads(l) for l in lines]
    assert {"event": "stage", "id": "resolve", "status": "done"} in events


def test_progress_lines_are_valid_json_objects(monkeypatch, tmp_path, capsys):
    _fake_build(monkeypatch, tmp_path)
    cli.main(["build", "--json", "--progress"])
    for line in capsys.readouterr().err.splitlines():
        if line.strip():
            assert isinstance(json.loads(line), dict)
```

Mirror the fake-request/fake-report helper style already used in `tests/test_cli_v15.py` for constructing `_minimal_verified_report` and the argv the build handler needs; do not invent a new fixture pattern.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cli_progress_contract.py -q`
Expected: FAIL — `--progress` is an unrecognized argument.

- [ ] **Step 3: Implement**

In `cli.py`:

```python
def _progress_emitter(enabled: bool):
    if not enabled:
        return None

    def emit(event: dict) -> None:
        print(json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)

    return emit
```

- Add `parser.add_argument("--progress", action="store_true")` to the `build`, `install-shim`, and `uninstall-shim` subparsers.
- Build handler: pass `on_event=_progress_emitter(args.progress)` into `BuildRequestV15`.
- Install/uninstall handlers: pass `on_event=_progress_emitter(args.progress)` through to `install_shim_transaction` / `restore_install_transaction`. Never enable the emitter for `--dry-run` handlers' JSON output paths beyond what the transaction itself emits.

- [ ] **Step 4: Run tests + full contract suite**

Run: `python3 -m pytest tests/test_cli_progress_contract.py tests/test_cli_json_contracts.py tests/test_cli.py -q && ruff check src tests`
Expected: PASS — existing stdout contracts untouched.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/cli.py tests/test_cli_progress_contract.py
git commit -m "feat: add --progress JSONL stage events to build and shim commands"
```

---

### Task 5: `add-patch` / `add-option` / `add-prompt` commands

**Files:**
- Create: `src/claude_monkey/packages_admin.py`
- Modify: `src/claude_monkey/cli.py` (new subparsers + dispatch)
- Test: `tests/test_packages_admin.py`, extend `tests/test_cli_json_contracts.py`

**Interfaces:**
- Consumes: phase-1 manifest loader/validator (per Task 0 contract notes) and per-kind package roots.
- Produces:
  - `add_package(source: Path, kind: str, home: Path) -> dict` — validates, copies to `<home>/<bucket>/<manifest.id>`, returns the mutating envelope dict (`ok`, `summary`, `warnings`, `error`). Never activates.
  - `scaffold_prompt_package(source_file: Path, package_id: str, name: str | None) -> dict` — in-memory manifest dict for a bare `.md` file.
  - CLI: `add-patch <dir> --json`, `add-option <dir> --json`, `add-prompt <path> [--id ID] [--name NAME] --json`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_packages_admin.py
import json

from claude_monkey.packages_admin import add_package, scaffold_prompt_package


def _write_pkg(tmp_path, folder, manifest):
    pkg = tmp_path / folder
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps(manifest))
    return pkg


PATCH_MANIFEST = {
    "schemaVersion": 1, "kind": "patch", "id": "demo-patch",
    "label": "Demo", "description": "d", "patch": {"engine": "bun_graph_repack", "targets": []},
}


def test_add_copies_to_manifest_id_dir(tmp_path):
    src = _write_pkg(tmp_path, "src-folder-name", PATCH_MANIFEST)
    home = tmp_path / "home"
    result = add_package(src, "patch", home)
    assert result["ok"] is True
    assert (home / "patches" / "demo-patch" / "manifest.json").exists()
    assert any("basename" in w for w in result["warnings"])  # renamed from src-folder-name


def test_add_rejects_id_collision(tmp_path):
    home = tmp_path / "home"
    src = _write_pkg(tmp_path, "demo-patch", PATCH_MANIFEST)
    assert add_package(src, "patch", home)["ok"] is True
    again = add_package(src, "patch", home)
    assert again["ok"] is False and again["error"]["code"] == "package_exists"


def test_add_rejects_kind_mismatch(tmp_path):
    src = _write_pkg(tmp_path, "demo-patch", PATCH_MANIFEST)
    result = add_package(src, "option", tmp_path / "home")
    assert result["ok"] is False and result["error"]["code"] == "kind_mismatch"


def test_add_rejects_invalid_manifest(tmp_path):
    pkg = tmp_path / "bad"; pkg.mkdir()
    (pkg / "manifest.json").write_text("{not json")
    result = add_package(pkg, "patch", tmp_path / "home")
    assert result["ok"] is False and result["error"]["code"] == "invalid_package"


def test_scaffold_prompt_package(tmp_path):
    md = tmp_path / "my notes.md"; md.write_text("be helpful")
    manifest = scaffold_prompt_package(md, "my-notes", None)
    assert manifest["kind"] == "prompt" and manifest["id"] == "my-notes"
    assert manifest["prompt"] == {"mode": "append", "source": {"path": "prompt.md"}}
```

CLI-level: add contract tests to `tests/test_cli_json_contracts.py` in its existing style covering `add-patch <dir> --json` (envelope shape on success + `invalid_package` failure) and `add-prompt bare.md --json` creating `prompts/<id>/prompt.md` — and asserting `list-prompts` afterwards shows it **not active**.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_packages_admin.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `packages_admin.py`**

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path

_BUCKETS = {"patch": "patches", "prompt": "prompts", "option": "options"}


def _envelope(ok: bool, summary: str, *, code: str | None = None, warnings=None) -> dict:
    return {
        "schemaVersion": 1, "ok": ok, "status": "ok" if ok else "error",
        "summary": summary,
        "error": None if ok else {"message": summary, "code": code},
        "warnings": list(warnings or []),
    }


def _load_manifest(package_dir: Path) -> dict:
    # ADAPT: delegate to the phase-1 loader recorded in the contract notes
    # (it enforces §3.1: id slug, kind enum, exactly-one-manifest, local paths,
    # sha shapes). Only if phase 1 exposes no importable entry point, fall back
    # to raising ValueError from json.loads + the §3.1 checks implemented here.
    raise NotImplementedError


def add_package(source: Path, kind: str, home: Path) -> dict:
    try:
        manifest = _load_manifest(source)
    except Exception as exc:
        return _envelope(False, f"invalid package: {exc}", code="invalid_package")
    if manifest.get("kind") != kind:
        return _envelope(
            False, f"manifest kind {manifest.get('kind')!r} does not match {kind!r}",
            code="kind_mismatch",
        )
    package_id = manifest["id"]
    dest = home / _BUCKETS[kind] / package_id
    if dest.exists():
        return _envelope(False, f"package already installed: {package_id}", code="package_exists")
    warnings = []
    if source.name != package_id:
        warnings.append(f"source basename {source.name!r} renamed to manifest id {package_id!r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)
    return _envelope(True, f"installed {kind} package {package_id}", warnings=warnings)


def scaffold_prompt_package(source_file: Path, package_id: str, name: str | None) -> dict:
    return {
        "schemaVersion": 1, "kind": "prompt", "id": package_id,
        "label": name or package_id, "description": f"Imported from {source_file.name}",
        "prompt": {"mode": "append", "source": {"path": "prompt.md"}},
    }
```

CLI wiring: three subparsers; `add-prompt` detects a file (vs dir) argument, derives `--id` default from the filename slugified (`re.sub(r"[^a-z0-9._-]+", "-", stem.lower()).strip("-")`), writes the scaffold manifest + copies the file as `prompt.md` into a temp dir, then routes through `add_package`. Print the envelope with the existing `print_json` (`cli_json.py:96`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_packages_admin.py tests/test_cli_json_contracts.py -q && ruff check src tests`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/packages_admin.py src/claude_monkey/cli.py tests/test_packages_admin.py tests/test_cli_json_contracts.py
git commit -m "feat: add-patch/add-option/add-prompt package install commands"
```

---

### Task 6: `remove-patch` / `remove-prompt` / `remove-option` commands

**Files:**
- Modify: `src/claude_monkey/packages_admin.py`, `src/claude_monkey/cli.py`
- Test: extend `tests/test_packages_admin.py`, `tests/test_cli_json_contracts.py`

**Interfaces:**
- Consumes: phase-1 active-profile reader (Task 0 notes).
- Produces: `remove_package(package_id: str, kind: str, home: Path, profile: dict) -> dict` where `profile` is `{"prompt": str|None, "patches": [...], "options": [...]}`. CLI: `remove-patch|remove-prompt|remove-option <id> --json`.

- [ ] **Step 1: Write the failing tests**

```python
def test_remove_refuses_profile_referenced_patch(tmp_path):
    home = tmp_path / "home"
    (home / "patches" / "p1").mkdir(parents=True)
    result = remove_package("p1", "patch", home, {"prompt": None, "patches": ["p1"], "options": []})
    assert result["ok"] is False and result["error"]["code"] == "package_in_use"
    assert (home / "patches" / "p1").exists()


def test_remove_allows_baked_in_but_not_desired(tmp_path):
    # active in the built binary but no longer in the profile -> removable
    home = tmp_path / "home"
    (home / "patches" / "p1").mkdir(parents=True)
    result = remove_package("p1", "patch", home, {"prompt": None, "patches": [], "options": []})
    assert result["ok"] is True and not (home / "patches" / "p1").exists()


def test_remove_refuses_active_prompt_and_enabled_option(tmp_path):
    home = tmp_path / "home"
    (home / "prompts" / "pr").mkdir(parents=True)
    (home / "options" / "op").mkdir(parents=True)
    profile = {"prompt": "pr", "patches": [], "options": ["op"]}
    assert remove_package("pr", "prompt", home, profile)["error"]["code"] == "package_in_use"
    assert remove_package("op", "option", home, profile)["error"]["code"] == "package_in_use"


def test_remove_missing_package(tmp_path):
    result = remove_package("nope", "patch", tmp_path / "home",
                            {"prompt": None, "patches": [], "options": []})
    assert result["ok"] is False and result["error"]["code"] == "package_missing"
```

- [ ] **Step 2: Run to verify failure** — `python3 -m pytest tests/test_packages_admin.py -q` → FAIL (`remove_package` not defined).

- [ ] **Step 3: Implement**

```python
def _profile_references(package_id: str, kind: str, profile: dict) -> bool:
    if kind == "patch":
        return package_id in (profile.get("patches") or [])
    if kind == "prompt":
        return profile.get("prompt") == package_id
    return package_id in (profile.get("options") or [])


def remove_package(package_id: str, kind: str, home: Path, profile: dict) -> dict:
    target = home / _BUCKETS[kind] / package_id
    if not target.is_dir():
        return _envelope(False, f"no installed {kind} package: {package_id}", code="package_missing")
    if _profile_references(package_id, kind, profile):
        return _envelope(
            False,
            f"{kind} package {package_id} is referenced by the active profile; "
            "disable/deselect it first",
            code="package_in_use",
        )
    shutil.rmtree(target)
    return _envelope(True, f"removed {kind} package {package_id}")
```

CLI wiring reads the active profile via the phase-1 config reader (Task 0 notes) and passes it in. Refusal never inspects `activePatchIds` — build-baked state does not block removal (spec: protection is for the *next* build/launch).

- [ ] **Step 4: Run tests** — `python3 -m pytest tests/test_packages_admin.py tests/test_cli_json_contracts.py -q && ruff check src tests` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/packages_admin.py src/claude_monkey/cli.py tests/test_packages_admin.py tests/test_cli_json_contracts.py
git commit -m "feat: remove-* package commands with profile-referenced refusal"
```

---

### Task 7: `menubar_state` v3 extensions

**Files:**
- Modify: `src/claude_monkey/menubar_state.py`
- Test: extend `tests/test_menubar_state.py`

**Interfaces:**
- Consumes: phase-1 `status --json` + `list-options --json` payloads (Task 0 notes; shapes above).
- Produces: `parse_menu_state(status, patches, prompts, options)` — note the **new fourth argument** (dict payload of `list-options --json`; `None` tolerated → empty). `MenuState` gains: `option_items: tuple[OptionItem, ...]` with `OptionItem(option_id, label, enabled, valid, compatibility_status, risk_level, requires_confirmation)`; `high_risk_warnings: tuple[str, ...]`; `shim_installed: bool` (true iff the install record path exists per the status payload).

- [ ] **Step 1: Write the failing tests** (style of existing `tests/test_menubar_state.py` — fake payload dicts):

```python
def test_parse_options_and_risk(fake_status, fake_patches, fake_prompts):
    options = {"schemaVersion": 1, "options": [{
        "id": "dangerous-permissions", "label": "Dangerous permissions", "kind": "option",
        "enabled": True, "valid": True, "compatibilityStatus": "compatible",
        "riskLevel": "high", "requiresConfirmation": True, "errors": [],
    }]}
    state = parse_menu_state(fake_status, fake_patches, fake_prompts, options)
    item = state.option_items[0]
    assert item.option_id == "dangerous-permissions"
    assert item.risk_level == "high" and item.requires_confirmation is True


def test_high_risk_warnings_from_status(fake_status_with_high_risk, fake_patches, fake_prompts):
    state = parse_menu_state(fake_status_with_high_risk, fake_patches, fake_prompts, None)
    assert "Dangerous permissions enabled" in state.high_risk_warnings


def test_options_none_tolerated(fake_status, fake_patches, fake_prompts):
    state = parse_menu_state(fake_status, fake_patches, fake_prompts, None)
    assert state.option_items == ()
```

- [ ] **Step 2: Run to verify failure** — signature error. If phase 1 **already** added options parsing (check first), reduce this task to adding whatever of `option_items`/`high_risk_warnings`/`shim_installed` is missing; the tests above must pass either way.

- [ ] **Step 3: Implement** — follow the existing `PatchItem`/`PromptItem` parsing pattern verbatim (defensive `.get` with typed defaults). `high_risk_warnings` maps `status["highRiskOptions"][*]["warning"]`.

- [ ] **Step 4: Run** — `python3 -m pytest tests/test_menubar_state.py -q && ruff check src tests` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/menubar_state.py tests/test_menubar_state.py
git commit -m "feat: parse option packages and risk warnings into MenuState"
```

---

### Task 8: `gui/commands.py` — argv builders

**Files:**
- Create: `src/claude_monkey/gui/__init__.py` (empty), `src/claude_monkey/gui/commands.py`
- Test: `tests/test_gui_commands.py`

**Interfaces:**
- Produces (all return `list[str]`, no `claude-monkey` prefix — `CommandRunner` adds it):
  - `command_for_patch_toggle(patch_id, *, enabled)` → `["disable-patch"|"enable-patch", id, "--json"]`
  - `command_for_option_toggle(option_id, *, enabled, confirm=False)` → enable path appends `--confirm` when `confirm`
  - `command_for_prompt(prompt_id | None)` → `["set-prompt", id, "--json"]` or `["clear-prompt", "--json"]`
  - `command_for_rebuild_apply()` → `["build", "--json", "--activate", "--progress"]`
  - `command_for_install_shim(target, *, dry_run=False)`, `command_for_uninstall_shim(*, target=None, record=None, dry_run=False)` — real runs append `--progress`; dry runs append `--dry-run` and never `--progress`
  - `command_for_add_package(path, kind)`, `command_for_remove_package(package_id, kind)`
  - `command_for_add_prompt_file(path, package_id, name | None)`

- [ ] **Step 1: Write the failing tests** — table-driven, asserting exact argv lists for every builder above, including: prompt selection takes an **id** (no `--from-file`, no path expansion); dry-run excludes `--progress`; option confirm flag placement `["enable-option", id, "--confirm", "--json"]`.

```python
from pathlib import Path

from claude_monkey.gui import commands as c


def test_toggles():
    assert c.command_for_patch_toggle("p", enabled=False) == ["enable-patch", "p", "--json"]
    assert c.command_for_patch_toggle("p", enabled=True) == ["disable-patch", "p", "--json"]
    assert c.command_for_option_toggle("o", enabled=False, confirm=True) == [
        "enable-option", "o", "--confirm", "--json"]


def test_prompt_and_rebuild():
    assert c.command_for_prompt(None) == ["clear-prompt", "--json"]
    assert c.command_for_prompt("research") == ["set-prompt", "research", "--json"]
    assert c.command_for_rebuild_apply() == ["build", "--json", "--activate", "--progress"]


def test_shim_commands_progress_vs_dry_run(tmp_path):
    t = tmp_path / "claude"
    assert "--progress" in c.command_for_install_shim(t)
    dry = c.command_for_install_shim(t, dry_run=True)
    assert "--dry-run" in dry and "--progress" not in dry
```

- [ ] **Step 2: Run to verify failure**, **Step 3: implement the builders** (pure functions, `str(path)` conversion only), **Step 4: run + ruff** → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/__init__.py src/claude_monkey/gui/commands.py tests/test_gui_commands.py
git commit -m "feat: gui argv builders for phase-1 CLI surface"
```

---

### Task 9: `gui/window_model.py` — pure view-models

**Files:**
- Create: `src/claude_monkey/gui/window_model.py`
- Test: `tests/test_gui_window_model.py`

**Interfaces:**
- Consumes: `MenuState` (Task 7), `install_plan_for_target`/`managed_user_target` from `menubar_install.py`.
- Produces:
  - `@dataclass(frozen=True) TrayModel(status_lines: tuple[str, ...], running_label: str | None, mutating_enabled: bool, show_install_shim: bool, prompt_items, patch_items, option_items)`
  - `build_tray_model(state: MenuState | None, busy_command: str | None) -> TrayModel`
  - `patch_menu_label(patch) -> str`, `patch_item_enabled(patch, *, mutating_enabled) -> bool`, `option_item_enabled(option, *, mutating_enabled) -> bool` (option rule: mutating + valid; enabling a `requires_confirmation` option is *allowed* — the confirm dialog handles it)
  - `default_install_target(state) -> Path` and `install_target_choices(state) -> tuple[tuple[str, Path], ...]` (ported from `menubar.py:34-39,138-157`, minus the clipboard path)
  - `class InstallTargetSelection: target(state) -> Path`, `select(path)`, `user_selected: bool` — the shared tray/window state object
  - `remove_enabled(item_kind: str, package_id: str, state: MenuState) -> tuple[bool, str]` — `(False, reason)` when profile-referenced (mirrors Task 6 rule for UI display)

- [ ] **Step 1: Write the failing tests** — port the label/enable assertions from `tests/test_menubar_app_model.py` that cover `build_menu_labels`, `patch_menu_label`, `patch_menu_item_enabled`, `default_install_target`, `install_target_choices` (adapt names; keep the assertion values). Add new coverage:

```python
def test_tray_hides_install_shim_when_installed(state_with_shim, state_without_shim):
    assert build_tray_model(state_with_shim, None).show_install_shim is False
    assert build_tray_model(state_without_shim, None).show_install_shim is True


def test_busy_disables_mutating_and_shows_running(state_without_shim):
    model = build_tray_model(state_without_shim, "build")
    assert model.mutating_enabled is False
    assert model.running_label == "Running: build"


def test_none_state_yields_error_model():
    model = build_tray_model(None, None)
    assert model.mutating_enabled is False
    assert model.status_lines[0].startswith("ClaudeMonkey: Error")


def test_remove_enabled_reflects_profile(state_without_shim):  # state has patch "p1" desired
    ok, reason = remove_enabled("patch", "p1", state_without_shim)
    assert ok is False and "profile" in reason
```

- [ ] **Step 2: Run to verify failure**, **Step 3: implement** (pure module; no Qt imports anywhere in this file — enforce with a test: `assert "PySide6" not in Path(window_model.__file__).read_text()`), **Step 4: run + ruff** → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/window_model.py tests/test_gui_window_model.py
git commit -m "feat: pure tray/window view-models"
```

---

### Task 10: `gui/progress_model.py` — stage-event state machine

**Files:**
- Create: `src/claude_monkey/gui/progress_model.py`
- Test: `tests/test_gui_progress_model.py`

**Interfaces:**
- Produces:
  - `@dataclass StageRow(stage_id: str, label: str, status: str = "pending", message: str | None = None)` — status ∈ pending/running/done/failed/skipped
  - `class ProgressModel:` attrs `rows: list[StageRow]`, `log_lines: list[str]`, `outcome: str | None` (None while running, then "success"/"failure"); methods `apply_event(event: dict) -> None`, `apply_result(payload: dict) -> None`
  - Unknown stage ids in events append a new row (GUI never crashes on protocol drift); `log` events append to `log_lines`; raw strings arrive as `{"event":"log","stage":None,"line":...}` (Task 11 wraps them).

- [ ] **Step 1: Write the failing tests**

```python
from claude_monkey.gui.progress_model import ProgressModel


PLAN = {"event": "plan", "stages": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]}


def test_happy_path():
    m = ProgressModel()
    for e in (PLAN, {"event": "stage", "id": "a", "status": "running"},
              {"event": "stage", "id": "a", "status": "done"},
              {"event": "log", "stage": "b", "line": "working"},
              {"event": "stage", "id": "b", "status": "done"}):
        m.apply_event(e)
    m.apply_result({"ok": True, "summary": "built"})
    assert [r.status for r in m.rows] == ["done", "done"]
    assert m.log_lines == ["working"] and m.outcome == "success"


def test_failure_marks_stage_and_outcome():
    m = ProgressModel()
    m.apply_event(PLAN)
    m.apply_event({"event": "stage", "id": "a", "status": "failed", "message": "boom"})
    m.apply_result({"ok": False, "summary": "failed"})
    assert m.rows[0].status == "failed" and m.rows[0].message == "boom"
    assert m.outcome == "failure"


def test_unknown_stage_id_appends_row():
    m = ProgressModel()
    m.apply_event(PLAN)
    m.apply_event({"event": "stage", "id": "zz", "status": "running"})
    assert m.rows[-1].stage_id == "zz"


def test_result_without_any_stage_failure_but_not_ok():
    m = ProgressModel()
    m.apply_event(PLAN)
    m.apply_event({"event": "stage", "id": "a", "status": "running"})
    m.apply_result({"ok": False, "summary": "died"})  # process died mid-stage
    assert m.rows[0].status == "failed" and m.outcome == "failure"
```

- [ ] **Step 2–4: fail → implement → pass + ruff.** Implementation is a dict-keyed row index + the rule from the last test: `apply_result(ok=False)` force-fails the currently `running` row if no row failed.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/progress_model.py tests/test_gui_progress_model.py
git commit -m "feat: progress checklist state machine"
```

---

### Task 11: `CommandRunner.run_streaming` + cancel

**Files:**
- Modify: `src/claude_monkey/menubar_commands.py`
- Test: `tests/test_menubar_commands.py` (extend)

**Interfaces:**
- Consumes: nothing new; parallel to existing `run_background` (`menubar_commands.py:209-229`).
- Produces:
  - `run_streaming(name: str, args: list[str], *, on_event: Callable[[dict], None]) -> StreamingHandle` — Popen with `start_new_session=True`; a reader thread parses stderr lines: valid JSON objects → `on_event(obj)`; anything else → `on_event({"event":"log","stage":None,"line":<raw>})`. stdout captured bounded (reuse `_BoundedTextCapture`). On exit, the final payload is built exactly like `run_json` does and queued via the existing results queue.
  - `@dataclass StreamingHandle(process, cancel(grace_seconds: float = 5.0))` — `cancel` sends SIGTERM to the **process group** (`os.killpg(os.getpgid(pid), SIGTERM)`), then SIGKILL to the group after `grace_seconds` if still alive (do the wait+escalate on a daemon thread; `cancel` returns immediately).
  - Mutating lock: `run_streaming` acquires the same `_mutating_lock` non-blocking and raises `MutatingCommandBusy`, releasing only when the process exits.

- [ ] **Step 1: Write the failing tests** — drive a real subprocess with a tiny inline Python script (no fakes of Popen):

```python
FAKE_CLI = [sys.executable, "-c", (
    "import json,sys,time;"
    "print(json.dumps({'event':'stage','id':'a','status':'running'}),file=sys.stderr,flush=True);"
    "print('garbage line',file=sys.stderr,flush=True);"
    "print(json.dumps({'schemaVersion':1,'ok':True,'status':'ok','summary':'done'}))"
)]


def test_run_streaming_events_and_result(tmp_path):
    runner = CommandRunner(cli_argv=FAKE_CLI[:2], logs_dir=tmp_path)  # argv trick: see note
    events: list[dict] = []
    handle = runner.run_streaming("build", FAKE_CLI[2:], on_event=events.append)
    handle.process.wait(timeout=10)
    deadline = time.time() + 5
    results = []
    while not results and time.time() < deadline:
        results = runner.drain_results(); time.sleep(0.05)
    assert events[0] == {"event": "stage", "id": "a", "status": "running"}
    assert {"event": "log", "stage": None, "line": "garbage line"} in events
    assert results[0][1]["ok"] is True


def test_cancel_kills_process_group(tmp_path):
    sleeper = ["-c", "import time; time.sleep(60)"]
    runner = CommandRunner(cli_argv=[sys.executable], logs_dir=tmp_path)
    handle = runner.run_streaming("build", sleeper, on_event=lambda e: None)
    handle.cancel(grace_seconds=1.0)
    assert handle.process.wait(timeout=10) != 0


def test_run_streaming_respects_mutating_lock(tmp_path):
    runner = CommandRunner(cli_argv=[sys.executable], logs_dir=tmp_path)
    handle = runner.run_streaming("build", ["-c", "import time; time.sleep(5)"],
                                  on_event=lambda e: None)
    with pytest.raises(MutatingCommandBusy):
        runner.run_streaming("build", ["-c", "pass"], on_event=lambda e: None)
    handle.cancel(grace_seconds=0.5)
    handle.process.wait(timeout=10)
```

(`cli_argv` note: `CommandRunner` prefixes `cli_argv` to args — pass `[sys.executable]` as the "CLI" and the `-c` script as args.)

- [ ] **Step 2–4: fail → implement → pass.** Also run the full existing file: `python3 -m pytest tests/test_menubar_commands.py -q && ruff check src tests`.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/menubar_commands.py tests/test_menubar_commands.py
git commit -m "feat: streaming command runner with process-group cancel"
```

---

### Task 12: Icon generation + `gui/icons.py`

**Files:**
- Create: `scripts/generate_icons.py`, `src/claude_monkey/gui/icons.py`
- Create (generated, committed): `assets/monkey-tray-18.png`, `assets/monkey-tray-36.png`, `assets/monkey-color-128.png`, `assets/monkey-color-256.png`, `assets/monkey-color-512.png`
- Test: `tests/test_icons.py`

**Interfaces:**
- Produces: `gui.icons.tray_icon() -> QIcon` (mask mode set), `gui.icons.app_icon() -> QIcon`; `ASSETS_DIR: Path`.

- [ ] **Step 1: Write `scripts/generate_icons.py`** — Pillow, fully deterministic (no timestamps, fixed geometry). Monkey-face glyph: head circle, two ear circles, face inset; tray = opaque black shapes on transparent (template mask), color = brown `#8B5E3C` head / tan `#D9B38C` face with dark eyes/nostrils. Geometry as fractions of size `s`:

```python
# head: ellipse((0.18s, 0.22s) - (0.82s, 0.88s))
# ears: circles centered (0.16s, 0.34s) and (0.84s, 0.34s), radius 0.14s
# tray variant: face inset ellipse((0.30s, 0.42s) - (0.70s, 0.86s)) punched to transparent
# color variant: face inset filled tan; eyes r=0.045s at (0.40s, 0.52s)/(0.60s, 0.52s);
#                nostrils r=0.02s at (0.46s, 0.70s)/(0.54s, 0.70s)
```

Sizes: tray 18 and 36; color 128/256/512. Script writes all five files under `assets/` and prints each path.

- [ ] **Step 2: Write the failing tests**

```python
import subprocess
import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def test_generator_writes_expected_files(tmp_path):
    subprocess.run([sys.executable, "scripts/generate_icons.py"], check=True)
    for name, size in [("monkey-tray-18.png", 18), ("monkey-tray-36.png", 36),
                       ("monkey-color-512.png", 512)]:
        img = Image.open(ASSETS / name)
        assert img.size == (size, size) and img.mode == "RGBA"


def test_tray_icon_is_monochrome_with_alpha():
    img = Image.open(ASSETS / "monkey-tray-18.png").convert("RGBA")
    colors = {px[:3] for px in img.getdata() if px[3] > 0}
    assert colors == {(0, 0, 0)}  # template: pure black + alpha only
```

- [ ] **Step 3: Run generator + tests** — `python3 scripts/generate_icons.py && python3 -m pytest tests/test_icons.py -q` → PASS.

- [ ] **Step 4: Implement `gui/icons.py`**

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"


def tray_icon() -> QIcon:
    icon = QIcon()
    for size in (18, 36):
        icon.addFile(str(ASSETS_DIR / f"monkey-tray-{size}.png"))
    icon.setIsMask(True)  # macOS template behavior; harmless on Windows
    return icon


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (128, 256, 512):
        icon.addFile(str(ASSETS_DIR / f"monkey-color-{size}.png"))
    return icon
```

- [ ] **Step 5: Commit** (delete `assets/claude-monkey-menubar-template.png` — superseded placeholder)

```bash
git rm assets/claude-monkey-menubar-template.png
git add scripts/generate_icons.py assets/*.png src/claude_monkey/gui/icons.py tests/test_icons.py
git commit -m "feat: generated monkey icons (tray template + color) and loader"
```

---

### Task 13: `gui/app.py` — application shell

**Files:**
- Create: `src/claude_monkey/gui/app.py`
- Test: `tests/test_gui_app.py`

**Interfaces:**
- Consumes: `CommandRunner` (incl. Task 11), `icons`, `window_model`; tray/window/progress classes from Tasks 14–16 are wired here **in Task 19** — this task builds the shell with the tray only.
- Produces:
  - `class CommandBridge(QObject)` with `progress_event = Signal(str, dict)` and `command_finished = Signal(str, dict)`; method `pump(runner)` (QTimer at 250ms draining `runner.drain_results()` → `command_finished`) — worker `on_event` callbacks emit `progress_event` directly (queued connection makes it thread-safe).
  - `apply_macos_accessory_policy() -> None` — the AppKit activation-policy call ported verbatim from `menubar.py:294-310`, guarded by `sys.platform == "darwin"` and try/except.
  - `class SingleInstance: __init__(self, key: str)`, `is_primary: bool`, `activated = Signal()` — `QLocalServer` named `claude-monkey-gui-<uid>`; secondary connects, sends `b"raise"`, and the caller exits 0; primary listens and emits `activated` on any connection (call `QLocalServer.removeServer(key)` before `listen` to clear stale sockets).
  - `refuse_root() -> bool` (port of `menubar.py:606-607`), `main() -> int`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gui_app.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from claude_monkey.gui.app import CommandBridge, SingleInstance, refuse_root  # noqa: E402


def test_refuse_root(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    assert refuse_root() is True
    monkeypatch.setattr(os, "geteuid", lambda: 501)
    assert refuse_root() is False


def test_single_instance_second_is_not_primary(qapp):
    a = SingleInstance("claude-monkey-test-si")
    b = SingleInstance("claude-monkey-test-si")
    assert a.is_primary is True and b.is_primary is False


def test_bridge_signals_deliver_across_threads(qtbot, qapp):
    bridge = CommandBridge()
    got: list = []
    bridge.progress_event.connect(lambda name, e: got.append((name, e)))
    import threading
    t = threading.Thread(
        target=lambda: bridge.progress_event.emit("build", {"event": "log", "line": "x"})
    )
    t.start(); t.join()
    qtbot.waitUntil(lambda: len(got) == 1, timeout=2000)
    assert got[0][0] == "build"
```

- [ ] **Step 2–4: fail → implement → pass.** `main()`: refuse root (stderr message + exit 1); `QApplication` with `setQuitOnLastWindowClosed(False)`; `apply_macos_accessory_policy()`; `SingleInstance` (secondary → print "already running" → return 0); construct `CommandRunner(logs_dir=Path.home() / ".claude-monkey" / "logs")`, bridge, tray (Task 14). Run: `python3 -m pytest tests/test_gui_app.py -q && ruff check src tests`.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/app.py tests/test_gui_app.py
git commit -m "feat: Qt app shell with bridge, single-instance, accessory policy"
```

---

### Task 14: `gui/tray.py`

**Files:**
- Create: `src/claude_monkey/gui/tray.py`
- Test: `tests/test_gui_tray.py`

**Interfaces:**
- Consumes: `TrayModel`/`build_tray_model` (Task 9), `icons.tray_icon()`, `commands` builders (Task 8).
- Produces: `class Tray(QObject)`:
  - `__init__(self, *, on_action: Callable[[str, dict], None])` — every menu action funnels to `on_action(action_id, kwargs)`; action ids: `"open_window"`, `"set_prompt"` (`prompt_id`), `"toggle_patch"` (`patch_id`, `enabled`), `"toggle_option"` (`option_id`, `enabled`, `requires_confirmation`), `"rebuild"`, `"install_shim"`, `"refresh"`, `"quit"`.
  - `render(self, model: TrayModel) -> None` — rebuilds the QMenu from the model. **No decisions in this file**: visibility of "Install shim…" reads `model.show_install_shim`; item enablement reads model fields.

- [ ] **Step 1: Write the failing tests** — construct `Tray` offscreen with a recording `on_action`; render a `TrayModel` fixture; walk `tray.menu.actions()` asserting: status lines disabled; "Install shim…" present/absent per `show_install_shim`; triggering the rebuild action calls `on_action("rebuild", {})`; busy model disables the Prompts/Patches/Options submenus and shows `Running: build`.

- [ ] **Step 2–4: fail → implement → pass + ruff.** Implementation: `QSystemTrayIcon(tray_icon())` + `QMenu`; submenu items are checkable `QAction`s with `setData` carrying ids; one `_on_triggered` dispatcher maps to `on_action`.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/tray.py tests/test_gui_tray.py
git commit -m "feat: tray renderer over TrayModel"
```

---

### Task 15: `gui/progress_dialog.py`

**Files:**
- Create: `src/claude_monkey/gui/progress_dialog.py`
- Test: `tests/test_gui_progress_dialog.py`

**Interfaces:**
- Consumes: `ProgressModel` (Task 10).
- Produces: `class ProgressDialog(QDialog)`:
  - `__init__(self, *, title: str, confirm_text: str, confirm_button: str, cancel_allowed_during_run: bool)` — phase CONFIRM: shows `confirm_text` (dry-run summary / patch set), buttons `[confirm_button] [Cancel]`.
  - Signals: `confirmed = Signal()`, `cancel_requested = Signal()`.
  - `start_running(self)` → phase RUNNING; `apply_event(self, event: dict)` and `finish(self, payload: dict, *, report_path: str | None, logs_dir: str)` → phase RESULT.
  - RUNNING widgets: stage checklist (QListWidget rows: `✔ done / ⟳ running / ✖ failed / – skipped / ○ pending` prefix + label + message), a "Details" `QToolButton` toggling a `QPlainTextEdit` log pane (collapsed by default), Cancel button — hidden when `cancel_allowed_during_run=False`, disabled once a `swap` stage starts otherwise.
  - RESULT: summary label (failed stage message in red via palette), buttons `[Open report]` (only when `report_path`), `[Open logs]`, `[Close]`; open buttons emit `open_path_requested = Signal(str)`.
  - Close is blocked (`closeEvent` ignored) during RUNNING unless cancel is allowed.

- [ ] **Step 1: Write the failing tests** — offscreen: construct; assert CONFIRM shows the text; `confirmed` emitted on button click (use `qtbot.mouseClick`); `start_running` + a plan/stage event sequence renders 3 rows with correct prefixes; `apply_event({"id": "swap", "status": "running"})` disables Cancel; `finish` with `ok:false` shows failure summary and `[Open logs]`; `cancel_allowed_during_run=False` hides Cancel entirely during RUNNING.

- [ ] **Step 2–4: fail → implement → pass + ruff.**

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/progress_dialog.py tests/test_gui_progress_dialog.py
git commit -m "feat: confirm/progress/result dialog"
```

---

### Task 16: `gui/settings_window.py` — window skeleton + Overview + Logs pages

**Files:**
- Create: `src/claude_monkey/gui/settings_window.py`
- Test: `tests/test_gui_settings_window.py`

**Interfaces:**
- Consumes: `MenuState`, `window_model`.
- Produces: `class SettingsWindow(QMainWindow)`:
  - Sidebar `QListWidget` (Overview, Patches, Prompts, Options, Install, Logs & Reports) + `QStackedWidget`.
  - `render(self, state: MenuState | None) -> None` — repopulates all pages from state; `None` → disconnected banner + Retry button (emits `refresh_requested = Signal()`).
  - Signals: `action = Signal(str, dict)` (same action-id vocabulary as Tray, plus `"uninstall_shim"`, `"add_package"` (`kind`, `path`), `"remove_package"` (`kind`, `package_id`), `"add_prompt_file"` (`path`, `package_id`, `name`), `"set_install_target"` (`path`), `"open_path"` (`path`)).
  - `show_banner(self, page: str, message: str) -> None` — dismissible inline error banner.
  - Overview page: status/version/prompt/patch-set labels, high-risk warnings list, Rebuild button (`action("rebuild", {})`), last build summary + Open report.
  - Logs page: three open buttons + read-only `QPlainTextEdit` tail (last 200 lines of `menubar.log`; filename kept deliberately for continuity).
  - Window close → `hide()` (never quits).

- [ ] **Step 1: Write the failing tests** — offscreen: sidebar has 6 entries; `render(fake_state)` fills Overview labels; `render(None)` shows the disconnected banner and Retry emits `refresh_requested`; clicking Rebuild emits `action("rebuild", {})`; `closeEvent` hides instead of destroying (`window.isVisible() is False` after `close()`, object alive).

- [ ] **Step 2–4: fail → implement → pass + ruff.** Pages are separate small `QWidget` subclasses in the same file (split into `gui/pages/` only if the file exceeds ~500 lines).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/settings_window.py tests/test_gui_settings_window.py
git commit -m "feat: settings window skeleton with overview and logs pages"
```

---

### Task 17: Patches / Prompts / Options pages

**Files:**
- Modify: `src/claude_monkey/gui/settings_window.py`
- Test: extend `tests/test_gui_settings_window.py`

**Interfaces:**
- Consumes: `window_model.remove_enabled`, item models from `MenuState`.
- Produces (all wired through the `action` signal — the window never runs commands):
  - Patches page: `QTableWidget` (checkbox | label | compatibility text); checkbox toggle → `action("toggle_patch", ...)`; rows disabled per `patch_item_enabled`. "Add Patch Package…" → folder picker (`QFileDialog.getExistingDirectory`) → `action("add_package", {"kind": "patch", "path": ...})`. "Remove" enabled per `remove_enabled`, tooltip = refusal reason when disabled.
  - Prompts page: `QListWidget`, "none" first, radio behavior; click → `action("set_prompt", {"prompt_id": id_or_None})`; "Add Prompt…" → file picker + small `QDialog` with id (pre-slugged from filename) and name fields → `action("add_prompt_file", ...)`. Adding **never** emits `set_prompt`.
  - Options page: table like Patches plus risk badge column (`high` rendered with warning color); enabling an item whose `requires_confirmation` is true first shows `QMessageBox.question` with the option label + `statusWarning`; accept → `action("toggle_option", {..., "confirmed": True})`, reject → checkbox reverts.

- [ ] **Step 1: Write the failing tests** — offscreen, with fake `MenuState` fixtures: toggling a patch row emits the right action payload; incompatible patch row is disabled; prompt click emits `set_prompt` with id; add-prompt dialog result emits `add_prompt_file` and **no** `set_prompt`; high-risk option toggle with `QMessageBox.question` monkeypatched to `Yes` emits `confirmed: True`, monkeypatched to `No` emits nothing and the checkbox reverts; `remove_enabled=False` row's Remove button is disabled with the reason as tooltip.

- [ ] **Step 2–4: fail → implement → pass + ruff.**

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/settings_window.py tests/test_gui_settings_window.py
git commit -m "feat: patches, prompts, and options pages"
```

---

### Task 18: Install page

**Files:**
- Modify: `src/claude_monkey/gui/settings_window.py`
- Test: extend `tests/test_gui_settings_window.py`

**Interfaces:**
- Consumes: `install_target_choices`, `InstallTargetSelection`, `install_plan_for_target`.
- Produces: Install page — target combo (choices from `install_target_choices` + "Browse…" via `QFileDialog.getSaveFileName`), protected/user-writable status label per `install_plan_for_target`, shim status line ("Installed at <path>" from `state.shim_target_path` / "Not installed"), Install and Uninstall buttons (each enabled per shim state) emitting `action("install_shim", {})` / `action("uninstall_shim", {})`; target changes emit `action("set_install_target", {"path": ...})`.

- [ ] **Step 1: Write the failing tests** — shim-installed state disables Install and enables Uninstall (and vice versa); combo selection emits `set_install_target`; protected target shows "protected" in the status label.

- [ ] **Step 2–4: fail → implement → pass + ruff.**

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/gui/settings_window.py tests/test_gui_settings_window.py
git commit -m "feat: install page with target picker and shim controls"
```

---

### Task 19: Controller wiring + cutover (delete rumps)

**Files:**
- Modify: `src/claude_monkey/gui/app.py`, `pyproject.toml:24`
- Delete: `src/claude_monkey/menubar.py`, `assets/` placeholder already removed in Task 12
- Modify: `tests/test_menubar_app_model.py` → delete (ported in Tasks 8–9; alert-plan tests retired with the mechanism), `tests/test_menubar_install.py` stays (module survives)
- Test: `tests/test_gui_controller.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `class Controller` in `gui/app.py` — the single `on_action` handler:
  - `refresh()`: `run_json` for `status`/`list-patches`/`list-prompts`/`list-options` (non-mutating) → `parse_menu_state` → `tray.render(build_tray_model(state, busy))` + `window.render(state)`; failures → error model + disconnected banner.
  - Quick ops (`toggle_patch`, `toggle_option`, `set_prompt`, `add_package`, `add_prompt_file`, `remove_package`): `runner.run_background` with argv from `gui/commands.py`; on `command_finished` → refresh; `ok:false` → `window.show_banner(page, message)`.
  - Long ops (`rebuild`, `install_shim`, `uninstall_shim`): run the dry-run/confirm data fetch (`run_json`, non-mutating), open `ProgressDialog` (`cancel_allowed_during_run` = False when the dry-run payload has `authorizationRequired: true`); `confirmed` → `runner.run_streaming(name, argv, on_event=lambda e: bridge.progress_event.emit(name, e))`; bridge signals → `dialog.apply_event` / `dialog.finish`; `cancel_requested` → `handle.cancel()`. **Every long op owns exactly one open ProgressDialog regardless of trigger source (tray or window).**
  - `open_path` → `runner.open_path` (existing).
  - `quit` → cancel any live handle, `QApplication.quit()`.
- Entry point: `claude-monkey-menubar = "claude_monkey.gui.app:main"`.

- [ ] **Step 1: Write the failing tests** — offscreen, with a stub runner (recording argv, injectable results): `rebuild` action opens a ProgressDialog and, after `confirmed`, `run_streaming` was called with `["build", "--json", "--activate", "--progress"]`; a `toggle_patch` action calls `run_background` with `["enable-patch", ...]` and a failed result surfaces a banner; `install_shim` with `authorizationRequired: true` dry-run constructs the dialog with `cancel_allowed_during_run=False`.

- [ ] **Step 2: Implement + delete**

```bash
git rm src/claude_monkey/menubar.py tests/test_menubar_app_model.py
```

Retarget the entry point in `pyproject.toml`. Reinstall: `python3 -m pip install -e '.[gui,dev]'`.

- [ ] **Step 3: Run everything**

Run: `python3 -m pytest tests/ -q && ruff check src tests`
Expected: PASS — nothing imports `claude_monkey.menubar` anymore (verify: `grep -rn "claude_monkey.menubar\b" src tests` → only `menubar_state|menubar_commands|menubar_install` hits).

- [ ] **Step 4: Commit**

```bash
git add -u
git add src/claude_monkey/gui/app.py pyproject.toml tests/test_gui_controller.py
git commit -m "feat: controller wiring; retire rumps menu bar"
```

---

### Task 20: Final verification + manual smoke

**Files:** none new.

- [ ] **Step 1: Full suite + lint**

Run: `python3 -m pytest tests/ -q && ruff check src tests`
Expected: PASS, zero lint errors.

- [ ] **Step 2: Manual smoke (macOS, real run — cannot be CI'd)**

```bash
python3 -m pip install -e '.[gui,dev]'
claude-monkey-menubar
```

Checklist (record results in the final report):
1. Tray icon appears; **no Dock icon** appears.
2. Second `claude-monkey-menubar` invocation exits immediately ("already running") and the window raises.
3. Open ClaudeMonkey… → window opens; all six pages populate.
4. Toggle a patch → menu + window stay consistent; no dialogs.
5. Rebuild / Apply… → ONE window: confirm → live stage checklist (resolve → repack → sign → inspect → smoke → activate) → result. No follow-on alerts.
6. Cancel a rebuild mid-`repack` → process dies; next rebuild succeeds.
7. Add a prompt from a bare `.md` → appears in list, NOT activated; click → activated.
8. Quit from tray → process exits.

- [ ] **Step 3: Update README GUI section** (install command, `claude-monkey-menubar` behavior, screenshot placeholder removed — text only).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: v3 GUI usage"
```

---

## Plan self-review notes (kept for the record)

- **Spec coverage:** tray (T14), window pages (T16–18), progress protocol producer (T2–4), one-dialog flow + cancel semantics (T11, T15, T19), add/remove content (T5–6), icons (T12), Dock suppression + single instance + root refusal (T13), state extensions (T7), rumps retirement + test port/retire split (T19), manual smoke incl. Dock check (T20). Error handling: unparseable lines (T11), died-without-JSON (T10 last test + T11 final payload), disconnected banner (T16), inline banners (T19).
- **Known deliberate deferrals to execution time:** exact phase-1 symbol names (`# ADAPT:` markers, resolved via Task 0's contract notes) — inventing them now against concurrently-written code would be worse than the marker.
- **Type consistency check:** action-id vocabulary defined once (T14) and reused (T16–19); `on_event` signature identical across T1–4, T11; stage-id vocabulary `resolve/repack/sign/inspect/smoke/activate` + `preflight/record/swap` consistent across T2, T3, T10, T15, T20.

