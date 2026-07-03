# Claude interactive xterm harness design

Date: 2026-07-02
Status: draft approved for user review
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

- `@wterm/ghostty` provides a stronger VT emulation core, but the currently published wterm DOM input handler is keyboard/paste-oriented; click handling focuses the hidden textarea rather than translating mouse events into PTY input.
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
  runId?: string;
  liveClaude?: boolean;
}
```

The backend must not bake in `claude`. Test cases select either a fixture executable or a Claude binary path.

### 4.2 Browser terminal page

The browser page owns terminal behavior:

- construct `@xterm/xterm` with deterministic rows, columns, font, and scrollback;
- connect xterm `onData` and `onBinary` to the backend;
- write PTY output into xterm;
- expose a narrow test-only API on `window.__claudeHarness` for snapshots and cell geometry;
- optionally load xterm's serialize addon for textual/framebuffer snapshots.

The page is not a product UI. It is an instrumented terminal fixture.

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

`clickCell(row, col)` converts a terminal cell coordinate into browser pixel coordinates using measured xterm geometry, then calls Playwright mouse APIs. It does not synthesize mouse escape bytes directly.

### 4.4 Protocol injection layer

Protocol injection is allowed but marked separately from real-user actions:

```ts
await harness.sendRaw("\x1b[A");
await harness.sendSgrMouse({ row: 12, col: 40, button: "left", action: "press" });
```

This is useful for low-level fixture tests or app-handler tests, but a test using this layer must not claim it proves browser click behavior.

## 5. Mouse model

Terminal mouse behavior depends on the application enabling a mouse reporting mode.

The harness should expose and assert xterm's mode state before mouse-sensitive assertions:

```ts
await harness.expectMouseTracking("vt200" | "drag" | "any" | "none");
```

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

The harness should prefer SGR mouse mode where possible, but it must not assume every application will use SGR mode. xterm may use binary paths for legacy reports; therefore `onBinary` must be wired to the backend as bytes.

## 6. Assertions

V1 assertions come from xterm and the raw PTY log.

Screen assertions:

- visible text contains or matches regex;
- visible text does not contain or match regex;
- specific row contains expected text;
- cursor row/column equals expected coordinates;
- active buffer state distinguishes normal vs alternate screen if exposed;
- mouse/paste/focus modes equal expected values.

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

For live interactive tests, the harness should:

- print the target Claude path and version first;
- use a temporary working directory unless a test explicitly requires this repo;
- record the effective environment and argv with secrets redacted;
- write run artifacts under `.development/harness-runs/<run-id>/`;
- fail closed if the target executable is missing;
- kill the child process on timeout;
- never mutate the live Claude binary.

## 9. Repository shape

A minimal v1 implementation should add a bounded Node/TypeScript test harness without disturbing the existing Python package surface.

Proposed layout:

```text
terminal-harness/
  package.json
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

Risk: dependency footprint is larger than the existing Python repo.
Mitigation: keep the Node harness under a bounded `terminal-harness/` directory and do not make it part of the published Python package until needed.

## 13. Definition of done for v1

The harness v1 is done when:

- fixture tests launch through `node-pty` and render in xterm under Playwright;
- tests can type, press arrows, press enter, and click cells;
- fixture mouse mode can be detected and clicked through real browser events;
- visible text, cursor position, mouse mode, and raw log assertions work;
- failure artifacts include raw PTY logs and screenshots;
- real Claude tests are present but skipped unless explicitly gated;
- documentation explains the distinction between real-user input and protocol injection.
