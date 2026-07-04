# HarnessMonkey - UserScripts for Claude Code
![capy-onsen-terminal](assets/demos/capyclaude.gif)
A reference example of a personal UserScript-style modification manager for Claude Code that handles applying/unapplying selected patches, command line options, and prompts to your selected `claude` location via a shim, patch engine, and re-packer.

Provides a Python CLI tool, (ugly) GUI, and menubar manager. Reference for Mac only currently.

## Example scripts

| Package | What it does | Demo |
|---------|--------------|------|
| [`fable-fallback`](packages/fable-fallback) | Un-hides Fable→Opus safety-classifier downgrade events: warning banner in resumed chats, marker in the `/resume` picker. The original reason this repo exists. | ![demo](assets/demos/fable-fallback.gif) |
| [`hidden-context-drawer`](packages/hidden-context-drawer) | Adds a footer "Hidden Context" drawer so you can read the model-visible attachment context (reminders, timestamps, token accounting) the harness normally hides from you. | ![demo](assets/demos/hidden-context-drawer.gif) |
| [`normal-channel-hidden-context`](packages/normal-channel-hidden-context) | Same hidden context, different delivery: projects it straight into the transcript as inline warning rows. Conflicts with the drawer — pick one. | ![demo](assets/demos/normal-channel-hidden-context.gif) |
| [`reminders-manager`](packages/reminders-manager) | A second footer drawer with live on/off toggles for seven recurring reminder/accounting attachment families. Runtime control instead of build-time suppression. | ![demo](assets/demos/reminders-manager.gif) |
| [`upstream-attachment-suppression`](packages/upstream-attachment-suppression) | Statically suppresses those same seven attachment families upstream, before they're ever generated. The "just make it all quiet" option. Conflicts with `reminders-manager` — pick one. | ![demo](assets/demos/upstream-attachment-suppression.gif) |
| [`hotrod-dragons`](packages/hotrod-dragons) | Two heraldic fire-breathing pixel-art dragons flanking your terminal, with animated flames. Does nothing. Improves everything. Needs a truecolor terminal. | ![demo](assets/demos/hotrod-dragons.gif) |
| [`dvd-cursor-goblin`](packages/dvd-cursor-goblin) | A `[DVD]` overlay that follows your mouse around the terminal like a lost screensaver. | ![demo](assets/demos/dvd-cursor-goblin.gif) |
| [`dvd-cursor-terminal-art-spike`](packages/dvd-cursor-terminal-art-spike) | Spike: the DVD cursor as box-drawing glyph art instead of plain text. | ![demo](assets/demos/dvd-cursor-terminal-art-spike.gif) |
| [`dvd-cursor-real-art-spike`](packages/dvd-cursor-real-art-spike) | Spike: the DVD cursor as an actual inline PNG via iTerm2 image escapes, with a text fallback. | ![demo](assets/demos/dvd-cursor-real-art-spike.gif) |
| [`reminder-suppression`](packages/reminder-suppression) | Superseded — kept as historical reference for Claude Code 2.1.198. Use `upstream-attachment-suppression` instead. | — |

### Why these scripts?

I was tired of four things with Claude Code:
1. Not being able to see all the tokens the model sees
2. The automated reminders that fire and make Claude anxious and jumpy
3. Not nearly enough vibes
4. Needing an alias to pass my [system prompt](tk lessanxiousclaude link) and --dangerously-skip-permissions 

So these are ideas to improve my personal Claude situation, and maybe yours too. But you should think of scripts that speak to you!

## Is this a good idea?

Probably not! Don't violate your TOS, don't get hacked, don't crash your computer hard -- all important things to focus on in your life. Injecting arbitrary web-provided JS into an opaque agent harness with powerful permissions may interfere with these goals! 

(I am neither a lawyer nor cybersecurity expert though so don't listen to me...)

## How do I install?

TK UV something? Requires: Mac Arm, Python, Xcode?

TK Installing the scripts into your ~

## How do I use it?

1. **Install the shim** - Click Install from the menubar or GUI page and select your system claude or another location if you want to be saner / use an alias.
2. **Select patches** - Choose your desired patches (if none show available you may have a more recent binary, ask an agent to update your local patches for your latest version)
3. **Apply and rebuild** - Select the rebuild option. You will see a success/failure message. Your next `claude` invocation will contain the latest patches.

## How do I make my own scripts?

Point a reasonably powerful agent at any of the examples as a starter and explain what you want.

Turns out LLMs can speak React crazy-well, even when minified. Making it the perfect choice for a mod-able TUI app :)

## Does this automatically patch new versions?

Nope. Just fails closed safely. Every Claude Code update will break the version pins until packages get re-verified against the new binary. When it breaks, throw your agent at re-authoring the package for the new version and carry on.

## Troubleshooting

Ummm, yep, there's a lot of trouble to shoot in this endeavor! Scripts and things are guaranteed to break over time. It's designed so you can ask your favorite local agent to help keep the duct tape and hot glue running. 

Please do that instead of asking me, whenever possible. It's part of the fun.

TK doctor command exists to back you out of sticky situations.

<3 Hackerbara
