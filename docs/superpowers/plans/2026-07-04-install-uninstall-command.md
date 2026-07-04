# `install` / `uninstall` Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `uv run claude-monkey install` gets a fresh clone from "synced" to "manager in the menubar, all packages loaded (disabled), back at every login" — one command. `--cli` skips the menubar app; `uninstall` reverses the LaunchAgent.

**Architecture:** A new CLI subcommand pair in `cli.py` composing three existing pieces: state-dir creation (`StatePaths`), package copying (`add_package` — the validated path `add-patch` already uses), and a new small `launch_agent.py` module (plist render + `launchctl` calls, injectable command runner for tests, same pattern as `smoke.py`'s `runner=run_command`).

**Tech Stack:** Python stdlib only (`plistlib`, `pathlib`). No new dependencies.

**Runbook context:** Task 1.7a of `docs/superpowers/plans/2026-07-04-harnessmonkey-launch-runbook.md`. The README (`HarnessMonkey-README.md`) already documents these verbs — the README is the contract; build to it.

## Global Constraints

- Use CURRENT names everywhere (`claude-monkey`, `claude_monkey`, `~/.claude-monkey`, plist label `com.hackerbara.claude-monkey`): the Phase-2 rename sweep converts them mechanically. Do NOT write "harnessmonkey" into code.
- Resolution stays state-dir-only: install COPIES packages; the repo never becomes a live package source (`tests/test_no_repo_package_source_v3.py` guards this — do not weaken it).
- Shim install remains an in-GUI/user step. `install` must NOT touch the user's `claude` binary or call `install-shim`.
- All `launchctl`/filesystem effects must be injectable/parameterizable so tests never touch the real `~/Library` or launchd.
- Idempotence: running `install` twice is safe (re-copy skips/overwrites cleanly per `add_package` semantics; LaunchAgent rewrite + reload, not duplicate).

---

### Task 1: GUI dependencies become default

**Files:**
- Modify: `pyproject.toml` (move `PySide6>=6.7` and `pyobjc-framework-Cocoa>=10.0 ; sys_platform == 'darwin'` from `[project.optional-dependencies] gui` into `[project] dependencies`; delete the now-empty `gui` extra)

- [ ] **Step 1:** Edit as above.
- [ ] **Step 2:** `uv sync && uv run python -c "import PySide6; print('ok')"` → `ok`. `rg -n "extra gui|--extra" README* HarnessMonkey-README.md docs/ src/` → update any stragglers that instruct `--extra gui` (the canonical README already assumes plain `uv sync`).
- [ ] **Step 3:** `uv run pytest -q` → current baseline (no regressions).
- [ ] **Step 4: Commit** — `git commit -m "build: GUI deps are default; plain uv sync suffices"`

---

### Task 2: `launch_agent.py` module

**Files:**
- Create: `src/claude_monkey/launch_agent.py`
- Test: `tests/test_launch_agent.py`

**Interfaces:**
- Produces:
  - `LAUNCH_AGENT_LABEL = "com.hackerbara.claude-monkey"`
  - `render_plist(gui_executable: Path) -> bytes` — plist with `Label`, `ProgramArguments: [str(gui_executable)]`, `RunAtLoad: True`, `ProcessType: "Interactive"`.
  - `agent_plist_path(home: Path) -> Path` — `<home>/Library/LaunchAgents/com.hackerbara.claude-monkey.plist`
  - `install_agent(gui_executable: Path, home: Path, runner=run_command) -> CommandResult` — mkdir -p LaunchAgents, write plist, `runner(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)])` (ignore failure — not loaded is fine), then `runner(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)])`.
  - `uninstall_agent(home: Path, runner=run_command) -> CommandResult` — bootout (ignore failure), delete plist if present.
  - `gui_executable() -> Path` — `Path(sys.executable).parent / "claude-monkey-menubar"`, i.e. the venv console script next to the running interpreter. Raise `FileNotFoundError` with a clear message if missing.

- [ ] **Step 1: Failing tests**

```python
import plistlib
from pathlib import Path
from claude_monkey.launch_agent import (
    LAUNCH_AGENT_LABEL, render_plist, agent_plist_path, install_agent, uninstall_agent,
)

class FakeRunner:
    def __init__(self): self.calls = []
    def __call__(self, argv):
        self.calls.append(argv)
        return type("R", (), {"ok": True, "returncode": 0, "stdout": "", "stderr": ""})()

def test_render_plist_shape():
    data = plistlib.loads(render_plist(Path("/venv/bin/claude-monkey-menubar")))
    assert data["Label"] == LAUNCH_AGENT_LABEL
    assert data["ProgramArguments"] == ["/venv/bin/claude-monkey-menubar"]
    assert data["RunAtLoad"] is True

def test_install_agent_writes_plist_and_bootstraps(tmp_path):
    runner = FakeRunner()
    install_agent(Path("/venv/bin/claude-monkey-menubar"), home=tmp_path, runner=runner)
    plist = agent_plist_path(tmp_path)
    assert plist.exists()
    assert any(c[:2] == ["launchctl", "bootstrap"] for c in runner.calls)

def test_uninstall_agent_removes_plist(tmp_path):
    runner = FakeRunner()
    install_agent(Path("/x"), home=tmp_path, runner=runner)
    uninstall_agent(home=tmp_path, runner=runner)
    assert not agent_plist_path(tmp_path).exists()
    assert any(c[:2] == ["launchctl", "bootout"] for c in runner.calls)

def test_install_agent_is_idempotent(tmp_path):
    runner = FakeRunner()
    install_agent(Path("/x"), home=tmp_path, runner=runner)
    install_agent(Path("/x"), home=tmp_path, runner=runner)  # no raise, plist rewritten
    assert agent_plist_path(tmp_path).exists()
```

- [ ] **Step 2: Run — expect FAIL** (`ModuleNotFoundError`)
- [ ] **Step 3: Implement** the module per the interface block (use `plistlib.dumps`; reuse `run_command`/`CommandResult` from where `smoke.py` imports them — read `smoke.py:50-62` for the exact import path first).
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit** — `git commit -m "feat: LaunchAgent module for the menubar manager"`

---

### Task 3: `install` subcommand

**Files:**
- Modify: `src/claude_monkey/cli.py` (parser block ~line 112 area; handler near `handle_add_package` ~line 1435; dispatch table ~line 1556)
- Test: `tests/test_cli_install.py`

**Interfaces:**
- Consumes: `add_package(source, kind, state_dir)` (existing), Task 2's `install_agent`/`gui_executable`.
- Produces: `claude-monkey install [--cli] [--json]`; exit 0 on success; per-package copy report; skips LaunchAgent under `--cli`.

- [ ] **Step 1: Failing tests** (follow `tests/test_cli_v3_packages.py`'s existing pattern for invoking `cli.main` with monkeypatched `StatePaths`/home — read it first; sketch):

```python
def test_install_copies_all_repo_packages_disabled(tmp_path, monkeypatch, capsys):
    # point state dir + repo root at fixtures; run cli.main(["install", "--cli"])
    # assert: every packages/<pkg> now under state patches/, and
    # `list-patches --json` shows them all with enabled == False
    ...

def test_install_cli_flag_skips_launch_agent(tmp_path, monkeypatch):
    # monkeypatch launch_agent.install_agent with a recorder; run with --cli
    # assert recorder not called
    ...

def test_install_default_installs_launch_agent(tmp_path, monkeypatch):
    # recorder called exactly once with the venv gui executable
    ...

def test_install_reports_per_package_failure_and_exits_nonzero(tmp_path, monkeypatch):
    # one malformed package dir among valid ones → exit code 1, valid ones still copied
    ...
```

Write these as REAL tests against the actual fixture conventions in `tests/test_cli_v3_packages.py` — the `...` bodies above are structure, not implementation; filling them requires that file's helpers.

- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement** — parser: `install_cmd = sub.add_parser("install"); install_cmd.add_argument("--cli", action="store_true"); install_cmd.add_argument("--json", action="store_true")`. Handler: ensure state dirs (reuse whatever `StatePaths` bootstrap `doctor` uses — read `handle_doctor`); iterate `sorted((repo_root/"packages").iterdir())` for dirs containing `patch.json`, call `add_package(dir, "patch", paths.state_dir)`, collect `{id: ok/error}`; unless `--cli`: `install_agent(gui_executable(), home=Path.home())`; print summary + next step ("Menubar: click the monkey → Install to set up your shim"); exit 1 if any package failed or agent install failed.
- [ ] **Step 4: Run — expect PASS**; full suite at baseline.
- [ ] **Step 5: Commit** — `git commit -m "feat: install command — state dir, copy-all packages, LaunchAgent"`

---

### Task 4: `uninstall` subcommand

**Files:**
- Modify: `src/claude_monkey/cli.py`
- Test: `tests/test_cli_install.py`

**Interfaces:**
- Produces: `claude-monkey uninstall [--json]` — unloads + removes the LaunchAgent only. Prints that state dir and shim are untouched and how to go further (`uninstall-shim`; delete `~/.claude-monkey` manually).

- [ ] **Step 1: Failing test** — `uninstall` calls `uninstall_agent` once; leaves a populated fake state dir untouched; exit 0 even when no plist existed (idempotent).
- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement** (parser + handler + dispatch).
- [ ] **Step 4: Run — expect PASS**; full suite at baseline.
- [ ] **Step 5: Manual smoke on this machine** (the one thing tests can't prove): `uv run claude-monkey install` → monkey appears in menubar; `launchctl print gui/$(id -u)/com.hackerbara.claude-monkey` shows it loaded; `uv run claude-monkey uninstall` → gone. Report results in the commit message.
- [ ] **Step 6: Commit** — `git commit -m "feat: uninstall command (LaunchAgent removal)"`

---

## Self-review notes

- README contract check: README says `harnessmonkey install` / `install --cli` / `uninstall` — matches these verbs post-rename. README says "all the scripts loaded and switched off" — Task 3 asserts disabled-by-default. README says "comes back on login" — `RunAtLoad` covers login; it does NOT keep-alive on crash (no `KeepAlive` key — deliberate, a crashing GUI shouldn't loop; revisit post-launch).
- `gui_executable()` resolves the venv script, so the LaunchAgent survives terminal closure and reboots but is tied to the clone location — acceptable for a source-first install; document nothing extra (README's "clone" framing already implies the checkout persists).
- Runbook 1.7a checks off when this plan completes.
