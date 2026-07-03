# Claude interactive xterm harness design

Date: 2026-07-02
Status: draft for user review
Project: ClaudeMonkey / Claude Code local interaction testing
Scope: Design only; no implementation in this document

## 1. Purpose

Build a test harness that can drive command-line interactive Claude Code the way a user drives it in a real terminal UI.

The harness is not only an `expect` wrapper. It must support terminal-screen assertions and real browser-generated input:

- typing and paste;
- arrow-key navigation;
- enter, escape, tab, control keys, and option/meta variants where needed;
- mouse movement, cell clicks, drag gestures, and wheel events;
- assertions over visible terminal content, cursor position, terminal modes, and raw PTY bytes.

This exists because several ClaudeMonkey patches affect Claude Code's interactive display and interaction surface. Non-interactive `claude -p --output-format stream-json` tests are useful, but they do not prove the true interactive TUI behavior.

## 2. Research conclusion

The v1 harness should be xterm.js-first.

Earlier alternatives considered Python `pty`/`pexpect`, wterm, and wterm's Ghostty/libghostty core. Those are useful in adjacent ways, but they are not the best first spine for mouse-heavy TUI testing.

Why xterm.js is the v1 spine:

- It is a mature browser terminal frontend with keyboard and mouse event handling.
- It is designed to connect to a backend process through a PTY such as `node-pty`.
- It exposes terminal modes such as `mouseTrackingMode`, `sendFocusMode`, and `bracketedPasteMode`, which are directly relevant to deciding whether mouse input should reach the application.
- It exposes visible buffer state for assertions.
- It lets Playwright drive the same DOM a user would click and type into.

Why not wterm/Ghostty in v1:

- Current research against `@wterm/dom` 0.3.0 and `@wterm/ghostty` 0.3.0 found that `@wterm/ghostty` provides a stronger VT emulation core, but the published wterm DOM input handler is keyboard/paste-oriented; click handling focuses the hidden textarea rather than translating mouse events into PTY input.
- Adding wterm would create a parallel terminal model without solving the first-order interaction need.
- If xterm.js is insufficient later, Ghostty/libghostty can be reconsidered as a replacement terminal core or a deeper compatibility test, not as v1's second oracle.

## 3. Architecture

```text
Playwright test driver
  -> real browser keyboard and mouse events
  -> xterm.js terminal page
  -> WebSocket bridge
  -> node-pty backend
  -> target process: fixture TUI or real claude executable
```

The same page and backend are used for fixture tests and real Claude tests. The default suite runs only fixtures. Real Claude runs are explicit, opt-in, and labeled as local/live smoke tests.

## 4. Components

### 4.1 PTY backend

A Node/TypeScript backend owns process lifecycle:

- spawn target executable with `node-pty`;
- set fixed terminal dimensions by default, for example 80x30;
- expose resize calls;
- forward PTY output bytes to browser clients;
- forward browser input bytes to the PTY;
- record raw byte logs, normalized text logs, timing, exit status, and errors;
- terminate children reliably on test cleanup.

Backend configuration:

```ts
interface HarnessLaunchConfig {
  command: string;
  args: string[];
  cwd: string;
  env: Record<string, string>;
  cols: number;
  rows: number;
  termName: string;
  runId?: string;
  targetKind:
    | "fixture"
    | "realClaudeReadOnly"
    | "realClaudeInteractiveLiveProfile"
    | "copiedPatchedClaude";
  profileMode: "isolatedHome" | "liveHome";
  artifactRetention: "fixtureDefault" | "realPrivateOptIn";
}
```

The backend must not bake in `claude`. Test cases select either a fixture executable or a Claude binary path.

The configured terminal name is part of the test surface. It should default to a known xterm-compatible value such as `xterm-256color`, and tests that depend on terminal identity must set it explicitly.

#### 4.1.1 Byte-preserving transport

The PTY bridge must be byte-preserving.

- Spawn `node-pty` with raw-buffer output when supported, for example `encoding: null`.
- Log PTY output as raw buffers with monotonic sequence numbers and timestamps.
- Forward PTY output to the browser as binary WebSocket frames.
- Forward xterm `onData` as UTF-8 text only when it is text.
- Forward xterm `onBinary` as bytes, for example `Buffer.from(data, "binary")`.
- If a JSON control message needs to carry bytes, base64-encode the byte payload.
- Do not let implicit JavaScript string conversion be the only representation of mouse or control bytes.

This is required because legacy mouse reports and some terminal control paths are not safe to round-trip through ordinary UTF-8 strings.

#### 4.1.2 Local server security boundary

The browser-to-PTY bridge is a local shell boundary. The browser must not be able to choose arbitrary launch parameters.

Rules:

- The browser never supplies `command`, `args`, `cwd`, or `env`.
- The server launches a preselected target for a run id created by the test runner.
- The server listens only on `127.0.0.1` and an ephemeral port.
- Each run uses an unguessable per-run token.
- The WebSocket endpoint validates the token and the browser origin.
- One client is allowed by default.
- The PTY closes when the client/test ends.
- The server must never bind to a non-loopback interface.

### 4.2 Browser terminal page

The browser page owns terminal behavior:

- construct `@xterm/xterm` with deterministic rows, columns, font, and scrollback;
- pin xterm options that affect key and mouse semantics, including `macOptionIsMeta`, `macOptionClickForcesSelection`, and `altClickMovesCursor`;
- connect xterm `onData` and `onBinary` to the backend;
- write PTY output into xterm;
- expose a narrow test-only API on `window.__claudeHarness` for snapshots and cell geometry;
- optionally load xterm's serialize addon for textual/framebuffer snapshots.

The page is not a product UI. It is an instrumented terminal fixture.

The chosen xterm option defaults must be documented in the harness README. On macOS in particular, Option/Alt and Option-click behavior can change whether input becomes terminal bytes, browser selection, or cursor movement.

### 4.3 Playwright driver

The Playwright layer is the main test API. It should drive real browser events wherever a test claims to model a user:

```ts
await harness.type("hello");
await harness.press("ArrowDown");
await harness.press("Enter");
await harness.clickCell(12, 40);
await harness.dragCells({ from: [10, 5], to: [10, 30] });
await harness.wheel({ deltaY: 240 });
await harness.expectVisible(/Resume/);
```

`clickCell(row, col)` uses 0-based terminal cell coordinates. It converts a cell coordinate into browser pixel coordinates using measured xterm geometry, clicks the center of the cell with Playwright mouse APIs, and does not synthesize mouse escape bytes directly.

### 4.4 Protocol injection layer

Protocol injection is allowed but marked separately from real-user actions:

```ts
await harness.sendRaw("\x1b[A");
await harness.sendSgrMouse({ row: 12, col: 40, button: "left", action: "press" });
```

This is useful for low-level fixture tests or app-handler tests, but a test using this layer must not claim it proves browser click behavior.

### 4.5 Readiness and settle contract

All screen assertions need an explicit settle contract.

The harness should offer:

- `waitForPtyIdle(ms)` for cases where no fixture sentinel exists;
- `waitForWriteDrain()` that resolves after all pending xterm `term.write(..., callback)` callbacks complete;
- `waitForFixtureEvent(name)` for deterministic fixtures;
- `expectVisible(...)` that waits for both write-drain and the requested screen condition before failing.

Snapshots must not read xterm's buffer until pending write callbacks have drained. Tests that require exact event order should assert against the sequenced raw input/output logs rather than only the visible screen.

## 5. Mouse model

Terminal mouse behavior depends on the application enabling a mouse reporting mode.

The harness should expose and assert xterm's mode state before mouse-sensitive assertions:

```ts
await harness.expectMouseTracking("x10" | "vt200" | "drag" | "any" | "none");
```

Mouse tracking mode is only a precondition. It does not prove the application received the intended mouse input, and it does not by itself identify whether xterm is using SGR, legacy, or another mouse encoding path.

Real-user mouse path:

1. Playwright emits browser mouse event.
2. xterm decides whether the event is normal selection/focus or terminal application input.
3. If a mouse tracking mode is active, xterm encodes the event and sends it through `onData` or `onBinary`.
4. Backend writes the bytes to the PTY.
5. The target app responds, and the PTY output updates xterm.

The harness should support these gestures in order:

1. cell click;
2. keyboard arrows and enter around menus;
3. wheel scroll;
4. drag start/move/end;
5. modifier clicks if needed.

Each real-user mouse test must prove three things:

1. Precondition: xterm's mouse tracking mode matches the test's expected mode.
2. Transport: the backend input log contains the expected mouse byte pattern after the Playwright event.
3. Application effect: the fixture or Claude screen state changes as expected.

The harness should prefer SGR mouse mode where possible, but it must not assume every application will use SGR mode. xterm may use binary paths for legacy reports; therefore `onBinary` must be wired to the backend as bytes.

Wheel behavior needs two separate assertions:

- browser scrollback wheel behavior when the terminal application has not captured the mouse;
- application mouse-wheel reports when mouse tracking is enabled.

Drag behavior likewise needs separate coverage for selection-style browser dragging and application drag/motion reports.

## 6. Assertions

V1 assertions come from xterm and the raw PTY log.

Screen assertions:

- visible text contains or matches regex;
- visible text does not contain or match regex;
- specific row contains expected text;
- cursor row/column equals expected coordinates;
- active buffer state distinguishes normal vs alternate screen if exposed;
- mouse/paste/focus modes equal expected values;
- keyboard modes such as `applicationCursorKeysMode` and `applicationKeypadMode` equal expected values before raw key-byte assertions.

Raw/log assertions:

- PTY output contains a byte sequence;
- input log contains the expected key or mouse encoding;
- process exited, timed out, or stayed alive as expected;
- artifacts were written to the run directory.

The default assertion vocabulary should be textual and cell-oriented, not screenshot-based. Screenshots are still useful failure artifacts.

## 7. Fixture strategy

Default tests must not start real Claude.

Fixture programs should be small and deterministic. They should exercise terminal behavior directly:

1. `fixture-menu`
   - draws a simple menu;
   - supports up/down arrows and enter;
   - emits stable visible labels.

2. `fixture-mouse-menu`
   - enables mouse reporting;
   - renders clickable rows;
   - updates selection on click;
   - records which cell was clicked.
   - covers vt200 click/release;
   - covers SGR mouse click/release when the fixture enables SGR mode;
   - covers the legacy/binary mouse path where feasible;
   - covers drag mode, any-motion mode, and wheel events.

3. `fixture-redraw`
   - uses cursor movement and line clearing;
   - proves visible-buffer assertions survive redraws.

4. `fixture-alt-screen`
   - enters alternate screen;
   - proves mode/buffer assertions and cleanup.

These fixtures prove the harness before it is trusted against Claude.

## 8. Real Claude safety model

Real Claude tests are opt-in and separate from the default test suite.

A real Claude test must require an explicit environment gate, for example:

```text
CLAUDE_HARNESS_REAL=1
CLAUDE_HARNESS_CLAUDE=/Users/MAC/.local/bin/claude
```

Real Claude runs may touch auth, network, settings, and session files depending on Claude Code behavior. The harness must not present them as read-only unless the specific invocation is proven read-only, such as `--version` or `--help`.

Interactive live-profile runs require a second explicit gate:

```text
CLAUDE_HARNESS_LIVE_PROFILE_MUTATION_OK=1
```

Without that second gate, the harness must refuse `targetKind: "realClaudeInteractiveLiveProfile"`.

For live interactive tests, the harness should:

- print the target Claude path and version first;
- print whether the run may mutate `~/.claude`, auth/session state, network state, and cwd;
- use a temporary working directory unless a test explicitly requires this repo;
- record the effective environment and argv with secrets redacted;
- write run artifacts under `.development/harness-runs/<run-id>/`;
- fail closed if the target executable is missing;
- kill the child process on timeout;
- never mutate the live Claude binary.

If profile isolation is not proven for the current Claude Code version, label the run as live-profile mutation, not controlled isolation. Patch-correctness tests should target copied patched binaries, never the live install.

Raw logs from real Claude can contain private conversation, file, and auth-adjacent context. Fixture raw logs are retained by default. Real-Claude raw logs are private opt-in artifacts, must live under ignored development paths, should redact secrets where possible, and must not be copied into public handoff material without explicit review.

## 9. Repository shape

A minimal v1 implementation should add a bounded Node/TypeScript test harness without disturbing the existing Python package surface.

Proposed layout:

```text
terminal-harness/
  package.json
  package-lock.json
  tsconfig.json
  playwright.config.ts
  src/
    pty-server.ts
    harness-page.ts
    test-driver.ts
    terminal-snapshot.ts
    mouse.ts
  public/
    index.html
  fixtures/
    menu.ts
    mouse-menu.ts
    redraw.ts
    alt-screen.ts
  tests/
    fixtures.spec.ts
    real-claude.spec.ts
```

This can remain a development harness rather than part of the published Python package. If it later becomes productized, it can move under a more formal package boundary.

Dependency policy:

- pin dependencies in `package.json` and commit a lockfile;
- do not require global npm installs;
- keep Playwright browser installation explicit in harness setup docs;
- keep the harness separate from the Python package's published metadata until deliberately productized;
- relate live tests to the existing pytest `local_real_smoke` marker by documenting that both are opt-in local-real checks, but the xterm harness remains Node/Playwright-owned.

## 10. Test tiers

Tier 1: unit tests for helpers

- cell-to-pixel coordinate conversion;
- raw key sequence helpers;
- SGR mouse encoder for protocol-injection mode;
- snapshot text normalization.

Tier 2: fixture integration tests

- spawn fixture TUI through `node-pty`;
- drive xterm through Playwright;
- assert visible screen/cursor/modes/logs.
- prove keyboard mode handling for normal and application cursor keys;
- prove cell click, wheel, and drag behavior through real browser events;
- prove the byte log captures the expected mouse input bytes.

Tier 3: local real-Claude smoke tests

- opt-in only;
- start real `claude` in a controlled workspace;
- prove the harness can type, navigate, interrupt, and exit;
- no claims about patch correctness unless the test installs or targets a copied patched binary explicitly.

## 11. Non-goals for v1

- No wterm/Ghostty parallel oracle.
- No image-diff screenshot testing as the primary assertion layer.
- No attempt to replace Claude Code's non-interactive `stream-json` interface.
- No automatic login, auth setup, or keychain automation.
- No mutation of live Claude binaries.
- No global installation of the harness as a CLI until the local test value is proven.

## 12. Risks and mitigations

Risk: xterm.js browser behavior differs from a native terminal.
Mitigation: this is acceptable for v1 because the desired test surface is programmable browser-driven terminal interaction. If native terminal parity becomes the core claim, add a separate native-terminal lane later.

Risk: mouse clicks do nothing because Claude or a fixture did not enable mouse tracking.
Mitigation: assert `terminal.modes.mouseTrackingMode` before expecting app-level click handling.

Risk: coordinate math drifts with font metrics or device pixel ratio.
Mitigation: measure xterm cell geometry in the browser and use cell-centered clicks.

Risk: live Claude tests mutate user state.
Mitigation: keep live tests opt-in, log target/env/argv, use temp workspaces by default, and avoid claims of read-only behavior for interactive sessions.

Risk: PTY/WebSocket transport corrupts control or mouse bytes.
Mitigation: use raw-buffer PTY output where supported, binary WebSocket frames, explicit `onBinary` forwarding, base64 for bytes in JSON messages, and sequenced raw logs.

Risk: the local PTY server becomes a local shell exposed to other browser contexts.
Mitigation: bind only to loopback on an ephemeral port, require a per-run token, validate origin, prevent browser-supplied launch parameters, and allow one client by default.

Risk: dependency footprint is larger than the existing Python repo.
Mitigation: keep the Node harness under a bounded `terminal-harness/` directory and do not make it part of the published Python package until needed.

## 13. Definition of done for v1

The harness v1 is done when:

- fixture tests launch through `node-pty` and render in xterm under Playwright;
- tests can type, press arrows, press enter, and click cells;
- tests can wheel and drag through real browser events;
- fixture mouse mode can be detected and clicked through real browser events;
- visible text, cursor position, mouse mode, keyboard mode, and raw log assertions work;
- every real-user mouse test proves mode precondition, transport bytes, and application effect;
- failure artifacts include raw PTY logs and screenshots;
- real Claude tests are present but skipped unless explicitly gated;
- live-profile Claude tests require the second mutation gate;
- documentation explains the distinction between real-user input and protocol injection.
