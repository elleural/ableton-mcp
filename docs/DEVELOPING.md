# Developing AbletonMCP 2

Read [PRD.md](PRD.md) (what to build, the tool catalogue and conventions), [PLAN.md](PLAN.md) (who owns
which files), and [spikes.md](spikes.md) (verified Live behaviour) first. Live's full API is in
[reference/live_api_12.4.6.md](reference/live_api_12.4.6.md), which is authoritative for what exists.
Semantics are in [reference/lom_docs_12.4.5.md](reference/lom_docs_12.4.5.md).

## How a tool call flows

```
MCP tool (MCP_Server/tools/x.py)  ──call("cmd", **params)──►  connection (JSON line, request id)
   ──TCP 127.0.0.1:9877──►  Remote Script shell (__init__.py)  ──►  core.dispatch: validate params
   ──►  queued to Live's main thread  ──►  handler(ctx, **params) in one undo step  ──►  JSON result
```

## Remote Script side (`AbletonMCP_Remote_Script/`, runs inside Live, Python 3.11)

### Adding a command

```python
from .. import refs, values
from ..core import command
from ..errors import CommandError


@command("set_mixer")                       # readonly=True for reads; timeout=... seconds if slow
def set_mixer(ctx, track, volume_db=None, pan=None, sends=None):
    song = ctx.song                         # never cache song(); fetch it per call
    owner = refs.track(song, track)         # raises CommandError listing valid tracks
    if volume_db is not None:
        values.set_volume_db(owner.mixer_device.volume, volume_db)
    ...
    return {...}                            # JSON-safe; read state back so the caller can verify
```

**Rules**

- Handlers run on Live's main thread, and a mutating handler runs inside one undo step. Keep each handler under about 1 s. Long work belongs to a ticker (below).
- Parameters are keyword arguments, validated against the signature before running. Unknown or missing parameters are rejected with the signature, and `None` means "not given".
- Raise `CommandError(code, message, hint=None)` for anything the caller can fix. Codes: `not_found`, `invalid_argument`, `unsupported`, `live_error`, `timeout`, `busy`. Messages must name the valid alternatives. Any other exception becomes `live_error`, with the traceback in Live's `Log.txt`.
- Import `Live` only inside functions where possible. At module level, the offline stub covers it.
- Never reuse attribute names of `_Framework.ControlSurface` on the control surface (spikes.md).
- Python 3.11 syntax is fine. Do not cache Live objects across calls, because they go stale when the set changes.

**Context (`ctx`)**

- `ctx.song` is the live Song and `ctx.app` is the Application.
- `ctx.state` is a dict that survives `reload_remote_script`. Use it for async job state.
- `ctx.log(msg)` writes to Live's Log.txt, and `ctx.show_message(msg)` writes to the status bar.

**Async work.** `@ticker` registers `func(ctx)`, which runs on the main thread about 10 times per second.
Use it for state machines such as the bounce engine. Keep job state in `ctx.state`, start the job from
one command, and expose a status command.

**Live API gotchas (spikes.md)**

- Routing lists are empty in the tick a track is created; configure routing on a later tick.
- New MIDI tracks may come up armed.
- Arrangement clips cannot hold editable envelopes.
- `insert_device` needs exact browser names.
- Return track names include `A-`.

### Shared helpers (lead-owned; use them, do not copy them)

`refs`, which resolves references and raises a helpful `CommandError`:

| Helper | Purpose |
|---|---|
| `track(song, ref)` | Index, name, `"master"`, `"return:A"`, or a bare return name |
| `tracks(song, refs=None)` | Several tracks |
| `track_ref(song, t)` | The canonical ref (`3`, `"return:A"`, `"master"`) |
| `track_label(song, t)` | `{track, name, kind}` |
| `track_kind(song, t)` | midi / audio / group / return / master |
| `return_letter(i)` / `return_bare_name(name)` | Return-track letters and names |
| `scene(song, ref)`, `locators(song)`, `locator(song, ref)`, `groove(song, ref)` | Locators are sorted by time |
| `clip_slot(song, track, slot)` | A clip slot |
| `clip(song, track, slot=None, arrangement_clip=None)` | Exactly one of the two |
| `arrangement_clips(track)` | Sorted by start time |
| `clip_ref(song, clip)` | `{track, slot}` or `{track, arrangement_clip}` |
| `device(song, track, device_ref)` | Returns `(device, container, index)`. Paths like `"Drum Rack/Kick/Simpler"` or `[0, 1, 0]`; chain segments accept an index, name or drum note |
| `chain(rack, ref)` | A rack chain |
| `device_path(device)` | `{path: "1/0/1", name_path: "Rack/Chain/Device"}` |
| `native_device_names(app)` | `{category: [names]}` of native devices, cached |
| `native_device_name(app, name)` | Exact `insert_device` spelling for a case-insensitive name, or not_found with suggestions; pack and Max for Live devices go through the browser |
| `parameter(device, ref)` | A device parameter |
| `mixer_parameter(song, track, ref)` | volume, pan, `send:A`, activator, crossfader, cue_volume, tempo, left_pan, right_pan |
| `resolve_parameter(song, track, device_ref, parameter_ref)` | Device parameter, or mixer when `device_ref` is None |
| `send_index(song, ref)` | Send index from a ref |
| `same(a, b)` / `index_of(sequence, obj)` | Identity of Live objects. Never use `is` or `==` on Live wrappers |

`values`, for units, enums and JSON:

| Helper | Purpose |
|---|---|
| `parse_time(song, v)` | Beats, or a `"bar.beat.sixteenth"` string |
| `parse_length(song, v)` | Beats, or `"8 bars"` |
| `format_time` / `time_out(song, beats)` | Gives `{beats, bar}` |
| `bar_length` / `beat_length` | In the song's meter |
| `parse_pitch(v)` / `pitch_name(p, flats=False)` | C3 = 60 |
| `parse_root_note(v)` | 0..11 |
| `parameter_out(param, index=None, detail=False)` | JSON for a parameter |
| `set_parameter(param, value)` | Number = raw, string = display value or item name |
| `set_display_number(param, x)` | Write in display units |
| `display_number(param)` | Read in display units |
| `volume_db(param)` / `set_volume_db(param, db)` | `"-inf"` is allowed |
| `parse_pan(v)` | -1..1, or `"25L"` / `"C"` / `"50R"` |
| `Enum.parse` / `Enum.name` | Enums: `SONG_QUANTIZATION`, `CLIP_LAUNCH_QUANTIZATION`, `RECORD_QUANTIZATION`, `QUANTIZE_GRID`, `GRID_QUANTIZATION`, `LAUNCH_MODE`, `WARP_MODE`, `MONITORING`, `CROSSFADE_ASSIGN`, `PANNING_MODE`, `DEVICE_TYPE`, `GROOVE_BASE` |
| `color_out(obj)` / `apply_color(obj, index or "#RRGGBB")` | Colours |
| `jsonable(v)` | Live values to JSON |

### Command journal (crash forensics)

`journal.py` writes `~/Library/Logs/AbletonMCP/live-commands.log` from inside Live: a `start` line when a request
arrives (with the client that sent it: `ableton-mcp:<pid>`, `pytest:<pid>`, ...), `run` when Live's main thread
begins it, one `item` per batch command, the capture and bounce engines' `phase` changes, and `end` with status
and duration. Every line is flushed at once, so when Live dies the last `run` or `item` without an `end` is what
was running. Big parameters are summarised (`<list 500>`), never copied. `ableton-mcp journal` shows the recent
lines and what is in flight; `ableton-mcp journal --crash` stops at Live's last FatalError in its `Log.txt`.
`ABLETON_MCP_JOURNAL` moves it or turns it off (`off`; the offline tests do).

The one crash so far (2026-10-07, `std::out_of_range` in `LSong::OnSceneTransactionCounterChanged`) came while a
single batch deleted tracks, a return track and scenes in one tick. Until it is understood, delete structural
objects one per call; `scripts/repro_scene_crash.py` (saved sets only) rebuilds that state to narrow it down.

## MCP server side (`MCP_Server/`, Python ≥ 3.10, mcp 2.x `MCPServer`)

```python
from ..app import call, tool


@tool(read_only=True)
def get_mixer(tracks: list[int | str] | None = None) -> dict:
    """Volume (dB), pan, sends, mute, solo and arm for every track (or the given tracks) in one call."""
    return call("get_mixer", tracks=tracks)


@tool(destructive=True)
def delete_track(track: int | str) -> dict:
    """Delete a regular or return track. Destructive: confirm with the user before deleting their work."""
    return call("delete_track", track=track)
```

**Rules**

- Tool names and parameters follow PRD §7 and §8. The tool's parameter names should match the handler's, and the contract test checks every `call()`.
- Annotations:
  - Use `@tool(read_only=True)` for reads.
  - Use `destructive=True` for anything that deletes or overwrites material.
  - Use `idempotent=True` for setters that can be repeated safely.
- Type parameters with builtins: `int | str` for references, `float | str` for time, `list[dict] | None`. **No `from __future__ import annotations`** in tool modules.
- Docstrings are what the agent reads. Start with what the tool does and when to use it. Then give units, accepted values and one short example, and note follow-up tools if useful.
- Keep each docstring under about 120 words. Detail that every tool shares lives in the server instructions (`app.INSTRUCTIONS`).
- Return the handler's dict, reshaped only if useful. Outputs are compact JSON: include indices and names, and keep lists bounded (counts plus the first N, or a `detail` flag).
- Pure-Python logic belongs in the MCP server, never in Live: music theory, step-pattern parsing, ffmpeg, files. Examples are `MCP_Server/theory.py` and `MCP_Server/audio/`.
- `call(command, timeout=None, **params)` drops None-valued params and turns Remote Script errors into MCP tool errors. For long commands pass `timeout=` (seconds).

## Testing

| Layer | Where | Runs | Notes |
|---|---|---|---|
| Unit | `tests/unit/` | `uv run pytest tests/unit` | Pure logic; use small fakes. Offline stubs for `_Framework` and `Live` are installed by `tests/conftest.py` |
| Contract | `tests/contract/` | `uv run pytest tests/contract` | Must stay green: every `call()` matches a registered command and its params; tools are documented; ≤ 80 tools |

Remote Script command names must be unique across all handler modules (a duplicate makes the second module fail to load). Name a command after its tool, and prefix internal helper commands with your area, e.g. `bounce_status`.
| Live | `tests/live/test_<ws>.py` | `uv run pytest tests/live/test_<ws>.py -x` | Real Live. Fixtures below |

Live test fixtures (`tests/live/conftest.py`):

- `live` is an `AbletonConnection`. The session is skipped if Live is unreachable.
- `scratch` creates `[test:<ws>] …` tracks, return tracks and scenes through the generic LOM commands, and deletes them afterwards even if the test fails.
  - `scratch.track(label, kind="midi" | "audio")` returns the track **name**. Address tracks by that name, because indices shift while other builders work.
  - `scratch.return_track(label)` and `scratch.scene(label)` work the same way.
- `song_state` snapshots tempo, meter, loop, metronome, record modes, key and scale, and restores them afterwards.
- The whole live session holds an exclusive lock (`.live-test.lock`), so builders never run live tests concurrently. Keep live test files short, ideally under 60 s.

Call your MCP tool functions directly in live tests (`from MCP_Server.tools.tracks import set_mixer`). The
decorator returns the plain function, so you get dicts back, and this tests both halves at once.

**Reloading your Remote Script changes into Live**

```bash
python3 -m py_compile AbletonMCP_Remote_Script/handlers/<yours>.py      # catch syntax errors first
uv run python -m tests.live.reload                                       # under the shared lock; non-zero on import failure
```

`uv run ableton-mcp-debug send <command> '<json params>'` sends one command by hand.
`... send get_commands` lists what is registered.

## Definition of done for a workstream

1. Every tool of your PRD §7 area exists, with exactly the catalogue's names, unless your report justifies a change. Each tool has a backing handler and a good docstring.
2. Unit tests cover your pure logic, and live tests exercise **every command you registered**, including the main error paths and cleanup.
3. `uv run pytest tests/unit tests/contract` is green, and `uv run pytest tests/live/test_<ws>.py` is green against the running Live.
4. You changed only files you own (PLAN.md). You did not commit, stash, reset or reformat anything.
5. Your final report lists:
   - tools and commands added
   - test results, with counts
   - deviations from the PRD and why
   - Live quirks discovered, for spikes.md
   - core-helper changes you need from the lead
   - new dependencies needed in `pyproject.toml`
