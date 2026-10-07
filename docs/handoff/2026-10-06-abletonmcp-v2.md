# Handoff: AbletonMCP 2 (2026-10-06)

AbletonMCP was rewritten so an agent can take a song from an empty Live Set to release files. The PRD
is [../PRD.md](../PRD.md), the plan [../PLAN.md](../PLAN.md), verified Live behaviour
[../spikes.md](../spikes.md), and the generated tool reference [../TOOLS.md](../TOOLS.md).

## State

- **78 tools:** status and project, song and transport, tracks and mixer, devices and browser, clips, notes and theory, automation, arrangement, export and release, and lom escape hatches.
- **Remote Script:**
  - A stable shell that serves commands on Live's main thread from a 10 ms timer (round trip median about 40 ms).
  - Hot reload with `reload_remote_script`; `--full` also reloads the shell.
  - Every mutating command is one undo step.
- **Tests:**
  - Offline unit and contract: 930 pass (`uv run pytest tests/unit tests/contract`).
  - Live suite: all pass against Live 12.4.6 (`uv run pytest tests/live`), including the end-to-end test `tests/live/test_e2e_release.py`. It composes a short track, arranges it, bounces master and stems in real time, and releases WAV, FLAC and MP3 at -14 LUFS.
- **Install and diagnose:** `uv run ableton-mcp install` (links the Remote Script into the User Library) and `uv run ableton-mcp doctor`.

## Wiring on Fred's Mac (after this PR merges)

- Remote Script: `~/Music/Ableton/User Library/Remote Scripts/AbletonMCP` links to the main checkout. Re-point it with `uv run ableton-mcp install --force` from that checkout.
- Claude Code: the user-scope MCP server `ableton` runs `uv run --quiet --directory /Users/fred/Documents/GitHub/ableton-mcp ableton-mcp`.
- UI automation (`save_set`, `new_set`, `export_audio`) needs Accessibility for the Claude app. Without it the agent asks the user to press Cmd+S.
- The repository is standalone: the old fork was archived as `elleural/ableton-mcp-fork-archive`.

## Review findings deferred (from the three M4 reviews)

All high-severity findings were fixed:

- the browser-reachable socket
- substring name resolution for destructive tools
- a bounce recording over armed tracks
- the save-prompt button order, now verified on Live
- clamped raw values
- sidechain
- automation-before-arranging docs

What remains:

- **Naming consistency (UX M9 and M10).**
  - Time parameters are named `at`, `to_time`, `time` and `position`.
  - `enabled` and `on`, and `mute` and `muted`, mean the same thing.
  - Arrangement clips appear under both `index` and `arrangement_clip` in outputs.
  - `slot` takes indices only, while scene tools also take names.
  - Unify these in one pass and update the tests.
- **Workflow speed.**
  - Batch mixer moves (`set_mixer(levels={...})`).
  - Audition a Session scene without arranging (`bounce(scene=...)`).
  - Report "track cannot make sound" warnings in `get_song_overview`.
  - Make section-level mix moves easier (UX M12–M14).
- **Automation.**
  - `clear_range` deletes the neighbouring segment's boundary event, because Live's range delete is inclusive.
  - Read-back of jumps shows the first value.
  - Quantize with swing 1.0 is not idempotent.
- **Safety, low.**
  - A colour is validated after other writes.
  - `edit_notes` can merge notes silently.
  - A bounce can stall if Live stops ticking.
  - A command can still apply after its caller timed out.
  - Output files are replaced silently.
- **`duplicate_clip`** skips the overlap check when the source is unwarped audio.
- **Not verified:** Windows; saving through UI automation (blocked by permissions here); and whether the 3/4 vs 4/4 clip-meter handling is right in note tools (it is fixed in automation).

The full reports were written to the session scratchpad; the items above are the actionable remainder.
