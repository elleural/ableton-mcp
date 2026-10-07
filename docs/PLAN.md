# AbletonMCP 2 — Execution Plan

Implements [PRD.md](PRD.md). Branch: `claude/ableton-mcp-toolkit-c6f16c`, one PR.

## Milestones

| # | Milestone | Owner | Exit criteria |
|---|---|---|---|
| M1 | **Core and spikes** | Lead (main session) | Both halves have a new core: registry, main-thread dispatch, framing, reload, refs and units, generic LOM, MCP 2.x app and connection. Test harness in place: contract test, live fixture with lock. Open questions answered in `docs/spikes.md`. Domain module stubs created. `docs/DEVELOPING.md` written. |
| M2 | **Domain build-out** | Five parallel workstreams (A–E) | Each workstream ships its Remote Script handlers, MCP tools, unit tests and live tests, all green against the running Live. |
| M3 | **Integration** | Lead | Full live suite and E2E acceptance test green. v1 monolith removed. README and server instructions rewritten. `install` and `doctor` CLI done. |
| M4 | **Review and ship** | Reviewers plus lead | Per-area review findings verified and fixed. PR opened. Handoff note in `docs/handoff/`. Remote Script symlink re-pointed to the main checkout after merge. |

## Workstreams (M2), with file ownership

Each workstream owns its files exclusively. Core files belong to the lead. A workstream that needs a
core change implements it locally in its own module and reports it.

| WS | Scope (PRD §7) | Remote Script (`AbletonMCP_Remote_Script/handlers/`) | MCP server (`MCP_Server/`) | Tests |
|---|---|---|---|---|
| **A** Song and project | 7.1, 7.2, scenes and locators from 7.7, 7.8 | `status.py`, `song.py` | `tools/status.py`, `tools/song.py`, `tools/project.py`, `ui_automation.py` | `tests/unit/test_song_*.py`, `tests/live/test_song.py` |
| **B** Tracks and mixer | 7.3 | `tracks.py` | `tools/tracks.py` | `tests/unit/test_tracks_*.py`, `tests/live/test_tracks.py` |
| **C** Clips, notes, automation, arrangement, theory | 7.5, 7.6, rest of 7.7, `music_theory` | `clips.py`, `arrangement.py` | `tools/clips.py`, `tools/arrangement.py`, `tools/theory.py`, `theory.py` | `tests/unit/test_clips_*.py`, `tests/unit/test_theory.py`, `tests/live/test_clips.py`, `tests/live/test_arrangement.py` |
| **D** Devices and browser | 7.4 | `devices.py`, `browser.py` | `tools/devices.py`, `tools/browser.py` | `tests/unit/test_devices_*.py`, `tests/live/test_devices.py`, `tests/live/test_browser.py` |
| **E** Export and release | 7.9 | `bounce.py` | `tools/export.py`, `audio/` (analysis, release, images) | `tests/unit/test_audio_*.py`, `tests/live/test_export.py` |

**Lead-owned core:**

- `AbletonMCP_Remote_Script/{__init__,core,refs,values,lom,introspection}.py` and `handlers/__init__.py`
- `MCP_Server/{server,app,connection}.py`, `tools/__init__.py`, `tools/lom.py`
- `tests/contract/`, `tests/live/conftest.py`, `tests/conftest.py`
- `pyproject.toml` (workstreams list any dependencies they need in their report)

## Shared-Live protocol (M2)

There is one Live instance and five builders. To share it safely:

1. **Lock.** Live tests and hot reloads run under an exclusive lock. The live pytest fixture takes `fcntl.flock` on `$TMPDIR/ableton-mcp-live.lock` for the whole session. Reload through `uv run python -m tests.live.reload`, which also takes the lock.
2. **Scratch only.** Tests create tracks and scenes named `[test:<ws>] …` and delete them in teardown, even on failure. They never modify pre-existing tracks, scenes, returns or the master. Global song state they touch (tempo, loop, metronome, transport) is snapshotted and restored.
3. **Resolve by name, not index.** Other builders may add or remove tracks between your calls. Within a test, look up scratch tracks by name.
4. **Isolated imports.** A handler module that fails to import is reported by reload and skipped, without breaking the others. Still run `python -m py_compile` on a module before reloading.
5. **Version control.** Never commit, stash, reset or reformat files you do not own. The lead commits at integration.
6. **Audio.** Tests that play or record audio are audible. Keep them short (8 bars at most, except the E2E test).

## Sequencing

```
M1 core ──► spikes ──► DEVELOPING.md ──► M2: A ┐
                                          B ┤
                                          C ├──► M3 integration ──► M4 review ──► PR
                                          D ┤
                                          E ┘ (E needs B's routing only through refs/lom, so it is not blocked)
```

## Model tiers (cost policy)

- **Lead (this session):** core, spikes, design synthesis, integration, final fixes.
- **Workstreams A–E:** `opus` subagents, spec-driven from PRD, DEVELOPING.md and spikes.md.
- **Reviewers in M4:** `sonnet` per-area review and per-finding verification. The lead synthesises and fixes.
- **Shared context goes through files**, never pasted into prompts:
  - `docs/PRD.md`, `docs/PLAN.md`, `docs/DEVELOPING.md` and `docs/spikes.md`
  - The Live API digest, saved to `docs/reference/live_api_12.4.6.md`
