# ctx-dispatch-router

Press **⌘⇧D** (**Super+Shift+D** on Linux), select a region of the screen, and the screenshot goes to the right repo on its own
(applications, college notes, plans...). Claude Code picks the destination and inserts the content
following that destination's CLAUDE.md. `repo` destinations get a `dispatch:` commit (revertible);
`folder` destinations are plain folders without git.

## Installation (macOS)

Requirements: Python 3, Claude Code (`claude`) logged in, and Xcode Command Line Tools (`swiftc`).

```bash
./install.sh
```

The script installs PyYAML, creates `/Applications/CtxDispatch.app`, and registers the hotkey as a
LaunchAgent that starts at login. On the first capture, macOS asks for **Screen Recording** permission
for CtxDispatch. Grant it and capture again.

Then:

1. Copy `destinations.yaml` to `destinations.dev.yaml` (or `destinations.local.yaml`) and edit it with
   your destinations (`nome`, `tipo: repo|folder`, `path`, `criterio` with "Vai" and "NÃO vai"). The first
   file that exists wins, with no merging: `.dev.yaml`, then `.local.yaml`, then the versioned
   `destinations.yaml`. Both overrides are in `.gitignore`, so personal paths and criteria stay on your machine.
2. In each destination, paste `templates/insercao-claude-md.md` into its CLAUDE.md and fill in the
   `EDITE` parts (file and format). A destination without CLAUDE.md always ends up pending.

## Installation (Linux, GNOME)

Requirements: GNOME (Wayland or X11), Python 3 with `python3-yaml` and `python3-gi`, `notify-send`, and
Claude Code (`claude`) logged in. Ubuntu ships all of them except Claude Code and possibly `python3-yaml`.

```bash
./install.sh
```

The script registers **Super+Shift+D** as a GNOME custom shortcut (it shows up in Settings → Keyboard).
Captures go through `xdg-desktop-portal`, so no screenshot tool is needed. Other desktops need their own
shortcut pointing at `router.py capture`, with `CLAUDE_BIN` set to the absolute path of `claude`.
Then follow steps 1 and 2 above. The hotkey runs `router.py` from this checkout, so keep this branch
checked out here.

## Usage

| Command | What it does |
|---|---|
| ⌘⇧D | captures the region (Esc cancels), processes it in the background and shows a notification |
| `./router.py run img.png --dry-run` | phase 1 only: shows the decision without moving or inserting anything |
| `./router.py run img.png` | full pipeline for an existing image |
| `./router.py review` | reviews pending captures: approve, change destination, discard, open the image |
| `./router.py status [-n 10]` | outcome of the latest runs, with changed files and commit |

Outcomes (in the notification and in `status`; the labels themselves are in Portuguese):

| | Meaning |
|---|---|
| ✅ `inserido` | something was written to the destination (files listed, plus the commit for repos) |
| ➖ `sem alteração` | right destination, but nothing changed (e.g. it already existed) |
| ⏸ `pendente` | not inserted by decision: `nenhum`, medium/low confidence, missing path or CLAUDE.md |
| ❌ `erro` | not inserted because of a failure (claude failed, changed files without committing...) |

Notifications don't show while Focus/Do Not Disturb is on. `status` always shows the outcome.

Where each capture ends up:
- **`inbox/done/`**: inserted successfully.
- **`inbox/pending/`**: something blocked the insertion. The `.json` next to it holds the decision and the reason.
- **`log.jsonl`**: history with the commit hash.
- **`run.log`**: errors from background runs.

Undo an insertion: `git revert <hash>` in the `repo` destination. For a `folder`, the changed files
show up in `status` and must be reverted by hand.

## Uninstall

On Linux, remove the `ctx-dispatch-router` entry in Settings → Keyboard → Custom Shortcuts. On macOS:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.ctx-dispatch-router.hotkey.plist
rm ~/Library/LaunchAgents/com.ctx-dispatch-router.hotkey.plist
rm -rf /Applications/CtxDispatch.app
```
