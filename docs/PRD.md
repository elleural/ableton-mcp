# AbletonMCP 2 — Product Requirements

| | |
|---|---|
| Status | Approved 2026-10-06 (owner: Fred Laruelle) |
| Target | Ableton Live 12.4 (verified on 12.4.6, embedded Python 3.11.6), macOS first, Windows best-effort |
| Execution plan | [PLAN.md](PLAN.md) |

## 1. Summary

AbletonMCP lets an AI agent operate Ableton Live over the Model Context Protocol (MCP). Version 2 is a
ground-up redesign around one outcome:

> **An agentic composer can take a song from an empty Live Set to release-ready audio files —
> composed, arranged, mixed, mastered, rendered, analysed, encoded and tagged — without a human
> touching Live.**

Version 1 mirrors fragments of Live's object model as ~75 thin commands. Version 2 replaces it with a
workflow-shaped toolkit of about 75 tools that speak in musical units (bars, note names, dB). It adds
what Live's API cannot do (rendering, loudness analysis, encoding, packaging), gives the agent "ears"
through audio analysis, and keeps a generic object-model escape hatch so nothing in Live is out of reach.

## 2. Users and jobs to be done

**Primary user: an LLM agent acting as composer, producer and engineer** (Claude in Claude Code or
Claude Desktop). It reasons in musical terms, cannot hear, cannot see Live's UI, and loses track of
indices as a session changes. It needs state it can read, actions it can verify, and errors that say
how to recover.

**Secondary user: a human producer** who supervises or co-writes. They need the agent's work visible
in Live, undoable, and confined to what they asked for.

| # | Job | What "done" looks like |
|---|---|---|
| J1 | Set up a project | New or existing set; tempo, meter, key and scale set |
| J2 | Design sounds | Instruments, effects, presets and samples found by name and loaded; parameters set in real units |
| J3 | Write music | MIDI clips with melodies, chords, bass and drums; notes edited, transposed, quantised, humanised |
| J4 | Structure the song | Scenes as sections; an arrangement timeline with named locators |
| J5 | Mix | Levels in dB, panning, sends and returns, buses, sidechain, automation |
| J6 | Master and release | Master and stems rendered; loudness measured and normalised; WAV/FLAC/MP3/AAC encoded and tagged; release folder and manifest |
| J7 | Listen and iterate | Meters, loudness and spectral analysis, optional spectrogram images; undo |

## 3. Goals and non-goals

**Goals**

- **G1 End-to-end.** J1–J7 are completable through MCP tools alone. UI automation is an optional accelerator, never a requirement.
- **G2 Agent-native ergonomics.** Name-based addressing, musical units, compact JSON, actionable errors, one undo step per call.
- **G3 Complete by construction.** Curated tools cover the workflow; generic `lom_*` tools reach every property and function Live exposes.
- **G4 Robust.** All Live access happens on Live's main thread. Long operations are asynchronous. The bridge reconnects by itself and survives set changes and script reloads.
- **G5 Verified.** Every Remote Script command is exercised by live integration tests, and an end-to-end acceptance test renders a real release.
- **G6 Easy to install and diagnose.** One command installs the Remote Script and registers the MCP server; `doctor` explains what is missing.

**Non-goals (v2)**

- Uploading to distributors or streaming services. Output is a release-ready folder.
- Editing audio waveforms (cut, split, consolidate), freezing or flattening, and true group tracks. The API has none of these; buses via routing replace groups.
- Writing arrangement automation lanes. The API cannot; clip envelopes carried into the arrangement are the supported path.
- Controlling plug-in GUIs or Live's preferences.
- Real-time performance control with tight latency guarantees.
- UI automation on Windows.

## 4. Assessment of v1 (2026-10-06)

The v1 toolkit connects and works for basic tasks, but it is not complete or fit for an autonomous composer.

- **Coverage.** Live 12.4.6 exposes 91 classes, 608 properties (270 writable) and 261 functions to
  Remote Scripts, measured by runtime introspection. v1 reaches roughly one-tenth of the writable
  properties and one-sixth of the functions.
- **Missing for music-making.** No reading of MIDI notes; no volume, pan, mute, solo or arm; no deleting
  tracks, clips or scenes; no clip properties (loop, markers, warp, launch); no Song.View selection;
  no racks, chains or drum pads; no routing, sidechain or returns management; no arrangement clip
  creation; no undo; no save or export.
- **Broken.** `write_automation` calls `Clip.get_automation_envelope` and `Envelope.set_automation`,
  neither of which exists, so it always fails. `clear_arrangement` calls a nonexistent `Clip.delete()`
  and silently deletes nothing. Browser loading by URI never searches samples, plug-ins, Max for Live,
  packs or the User Library.
- **Unsafe.** Read commands touch Live's API from the socket thread rather than the main thread. Notes
  use the deprecated `set_notes`, which loses probability and velocity deviation.
- **Hard to evolve.** One 2,400-line Remote Script with a giant `if/elif` dispatcher, duplicated
  command allowlists on both sides, blanket `except` that turns errors into success strings, and fixed
  100 ms sleeps.
- **Misleading install docs.** `uvx ableton-mcp` installs the upstream PyPI package, not this fork.

**Decision:** rewrite both halves with a new architecture. Useful v1 behaviour is ported and fixed.

## 5. Design principles

1. **Workflow-shaped, not object-shaped.** Tools match what a producer does (`write_drum_pattern`, `arrange_from_scenes`, `bounce`), not one tool per Live property.
2. **Few, composable, rich tools.** Target about 75 tools. Multi-property setters and list inputs replace dozens of single-purpose calls.
3. **Musical units in, musical units out.** Time as beats or `bar.beat.sixteenth`, pitch as MIDI numbers or note names, volume in dB, pan from −1 to +1, quantisation as `"1/16"`.
4. **Names over indices.** Tracks, devices, parameters, scenes, locators and grooves can be addressed by name. Indices still work; outputs always include both.
5. **One call, one undo step.** Every mutating call is wrapped in a single Live undo step.
6. **Fail loudly and helpfully.** Errors are real MCP errors (`isError`), and the message names the valid alternatives ("Track 'Bas' not found. Tracks: Drums, Bass, Keys").
7. **Never freeze Live.** Main-thread work is short. Rendering and other long jobs run asynchronously behind status polling.
8. **Verify by reading back.** Mutations return the resulting state, so the agent can confirm without a second call.
9. **Safe by default.** Nothing outside what a call names is touched. Bounces restore transport state and remove their temporary tracks. Destructive tools say so in their annotations.
10. **Complete by construction.** Anything without a curated tool is reachable through `lom_get` / `lom_set` / `lom_call` / `lom_describe`.

## 6. End-to-end workflow

```
J1 setup      get_status → new_set / open_set → set_song(tempo, time_signature, key, scale)
J2 sounds     create_track(kind, name, device) → search_browser / load_from_browser / add_device
              → set_device_parameters (real units) → set_device / device_action
J3 write      create_clip → write_notes (note names, chords via music_theory) / write_drum_pattern
              → transform_notes (quantise, humanise, transpose) → fire_scene to audition, get_meters
J4 structure  scenes as sections → arrange_from_scenes([{scene, bars}, …]) → create_locator per section
J5 mix        set_mixer(volume_db, pan, sends) → create_bus → sidechain via set_device(routing)
              → write_automation (clip envelopes travel into the arrangement)
J6 master     add_device on "master" (EQ Eight, Glue Compressor, Limiter) → bounce(stems=…)
              → get_bounce_status → analyze_audio → adjust → re-bounce
              → create_release(title, artist, formats, target_lufs) → save_set
J7 iterate    get_song_overview / get_arrangement / get_notes / analyze_audio(images) / undo
```

## 7. Tool catalogue (contract)

`clip ref` means exactly one of `slot` (Session slot index) or `arrangement_clip` (index into the
track's arrangement clips, sorted by start time). **[UI]** marks tools that need optional macOS
UI automation. **[async]** marks tools that return a job to poll.

### 7.1 Status and project

| Tool | Purpose |
|---|---|
| `get_status` | Connection, Live and script versions, set name and path, transport, open dialog, capabilities (ffmpeg, UI automation), active jobs |
| `get_song_overview` | One-call project map: tempo, meter, key; tracks with type, devices and clips; returns; master chain; scenes; locators; arrangement length |
| `undo` / `redo` | Step Live's undo history (`steps`) |
| `save_set` **[UI]** | Save, or save-as to `path`; verified through `Song.file_path` |
| `new_set` **[UI]** | New empty set; unsaved changes are refused unless `discard_unsaved` |
| `open_set` | Open an `.als` file through the OS; handles Live's save prompt through the dialog API |
| `respond_to_dialog` | Press a button on Live's current dialog (the message comes from `get_status`) |

### 7.2 Song and transport

| Tool | Purpose |
|---|---|
| `set_song` | Tempo, time signature, key and scale (root, name, scale mode), swing, groove amount, metronome, loop on/off and region, punch in/out, launch and record quantisation, follow, record modes |
| `transport` | `play` (optionally from a position), `continue`, `stop`, `jump`, `jump_to_next_locator` / `jump_to_prev_locator`, `play_selection`, `stop_all_clips`, `back_to_arrangement`, `tap_tempo`, `capture_midi`, `capture_scene` |

### 7.3 Tracks, mixer and routing

| Tool | Purpose |
|---|---|
| `create_track` | `kind` = midi / audio / return; name, index, colour, optional device to insert |
| `get_track` | Full detail: mixer, routing, devices, clip slots, arrangement clips, take lanes, freeze state |
| `set_track` | Name, colour, arm, monitoring, fold, collapse, input and output routing (by display name), show chains |
| `delete_track` / `duplicate_track` | Regular or return tracks |
| `get_routing_options` | Available input and output types and channels for a track |
| `create_bus` | Audio bus track with source tracks' outputs routed into it (the group-track substitute) |
| `get_mixer` | Every track's volume (dB), pan, sends, mute, solo and arm in one call |
| `set_mixer` | `volume_db`, `pan`, `sends` (by return letter or name, in dB), mute, solo, activator, crossfade, pan mode |
| `get_meters` | Momentary output and input levels per track and master |

### 7.4 Browser and devices

| Tool | Purpose |
|---|---|
| `search_browser` | Name search across instruments, effects, sounds, drums, samples, plug-ins, Max for Live, packs and the User Library; returns URIs |
| `browse` | List a browser folder by path |
| `load_from_browser` | Load by `uri`, `path` or `query` onto a track, a device position, a drum pad (note) or a Session slot (samples) |
| `add_device` | Insert a native Live device by name (`Track.insert_device`), optionally into a rack chain |
| `get_devices` | Device tree for a track, including racks, chains and drum pads, with addressable paths |
| `get_device` | Device detail: parameters (value, display string, range, items), type-specific properties, macros, variations, chains, pads |
| `set_device_parameters` | Set many parameters at once; numbers are raw values, strings are display values or quantised items |
| `set_device` | On/off, name, collapsed, A/B compare, type-specific properties (Simpler mode, Wavetable oscillators, Compressor sidechain routing, plug-in preset, …) |
| `device_action` | Type-specific functions: rack chains, macros, variations and pads; Simpler crop, reverse, warp and replace sample; Looper transport; and similar |
| `delete_device` / `duplicate_device` / `move_device` | Device chain edits, including moves across tracks and into chains |
| `set_chain` | Rack or drum chain name, colour, mute, solo, volume (dB), pan, in/out note, choke group |

### 7.5 Clips and notes

| Tool | Purpose |
|---|---|
| `create_clip` | MIDI clip in a Session slot or at an arrangement time; audio clip from `file_path` |
| `get_clip` / `set_clip` | All clip properties: name, colour, loop, markers, launch mode and quantisation, legato, mute, gain, pitch, warping and warp mode, groove, signature |
| `delete_clip` / `duplicate_clip` | Session ↔ Session, Session → arrangement, arrangement → arrangement (copy or move) |
| `fire_clip` / `stop_clip` | Launch a slot; stop a track's clips |
| `get_notes` | Notes with ids, pitch and name, start, duration, velocity, probability, velocity deviation, release velocity, mute |
| `write_notes` | Add, replace all, or replace a time range; accepts note names |
| `edit_notes` / `delete_notes` | Modify notes by id; delete by id or range |
| `transform_notes` | Transpose, quantise (grid, amount), humanise (timing, velocity), velocity scale, legato, reverse, stretch, with pitch and time filters |
| `write_drum_pattern` | Step strings per drum (`"Kick": "x---x---x---x---"`), resolved through the Drum Rack's pad names with a GM fallback; accent, swing and velocity options |
| `clip_action` | Crop, duplicate loop, duplicate region, audio quantise, warp markers |

### 7.6 Automation

| Tool | Purpose |
|---|---|
| `write_automation` | Clip envelope for any device or mixer parameter, from points or a shape (ramp, sine, triangle, square, steps); optionally clears the range first |
| `get_automation` / `clear_automation` | Read envelope events and values; clear one or all envelopes |

### 7.7 Scenes and arrangement

| Tool | Purpose |
|---|---|
| `create_scene` / `set_scene` / `fire_scene` / `delete_scene` / `duplicate_scene` | Scene lifecycle, plus per-scene tempo and time signature |
| `get_arrangement` | Timeline per track: clips with start and end in beats and bars, locators, loop, song length |
| `arrange_from_scenes` | Lay out sections (`[{scene, bars}]`) by tiling each scene's clips into the arrangement, with locators named after sections |
| `create_locator` / `set_locator` / `delete_locator` | Cue points by time and name |
| `clear_arrangement` | Delete arrangement clips by track and time range |

### 7.8 Grooves, selection and feedback

| Tool | Purpose |
|---|---|
| `get_grooves` / `set_groove` | Groove pool; assign a groove to a clip with `set_clip(groove=…)` |
| `select` | Select a track, scene, device or clip, and focus Session, Arrangement or Detail views |
| `show_message` | Message in Live's status bar |

### 7.9 Export, analysis and release

| Tool | Purpose |
|---|---|
| `bounce` **[async]** | Real-time render of an arrangement range to WAV, for the master and optional stems, by resampling inside Live |
| `get_bounce_status` / `cancel_bounce` | Progress with long-poll `wait`; file paths when done |
| `analyze_audio` | Integrated loudness (LUFS), loudness range, true and sample peak, RMS, crest factor, clipping, DC, stereo correlation, spectral balance, loudness per section; optional spectrogram and waveform images |
| `create_release` | Normalise to target LUFS and true-peak ceiling; encode WAV 24/16 (dithered), FLAC, MP3 320, AAC; tag metadata and artwork; write `release.json` |
| `export_audio` **[UI]** | Experimental: drive Live's own offline Export dialog |

### 7.10 Theory and escape hatch

| Tool | Purpose |
|---|---|
| `music_theory` | Scale notes, chord tones and voicings, Roman-numeral progressions to pitches, note-name conversion |
| `lom_get` / `lom_set` / `lom_call` | Read, write or call anything by object-model path (`live_set tracks 0 mixer_device volume`) |
| `lom_describe` | Properties and functions available at a path, with docstrings, from runtime introspection |
| `reload_remote_script` | Developer tool: hot-reload the Remote Script without restarting Live |

## 8. Conventions (contract for every tool)

**Addressing**

- `track`: an integer is a regular track index. A string is `"master"`, `"return:<letter|index|name>"`, or a case-insensitive exact name of a regular or return track. Ambiguous or missing names are errors that list the candidates.
- `device`: an integer index, a name (device name, then class display name), or a path through racks such as `"Drum Rack/Kick/Simpler"` or `[0, 1, 0]`. Segments alternate device and chain. A chain segment is an index, a chain name, or a drum note (`"C1"`, `36`).
- `parameter`: an index or a name (exact, then original name, then unique substring). With no `device`, mixer names apply: `volume`, `pan`, `send:A`, `activator`, `crossfader`, `cue_volume`, `tempo`.
- `scene`, `locator`, `groove`: an index or a name.

**Units**

- Time: a number is beats (quarter notes). A string is `"bar.beat.sixteenth"`, 1-based, in the song's meter (`"17.1.1"`). Lengths are beats, or a string such as `"8 bars"`. Outputs give both.
- Pitch: a MIDI number, or a note name in Live's convention where C3 is 60 (`"F#2"`, `"Bb3"`).
- Volume: dB (`"-inf"` allowed, maximum +6). Pan: −1 to +1. Sends: dB. Raw values are accepted where documented.
- Enums use Live's display names: `"1/16"`, `"1 bar"`, `"complex_pro"`, `"gate"`, `"auto"`.
- Colour: a Live colour index (0–69) or `"#RRGGBB"`.

**Behaviour**

- Output is compact JSON objects with indices and names. Verbose detail is opt-in.
- Errors carry `code` (`not_found`, `invalid_argument`, `unsupported`, `live_error`, `timeout`, `busy`), `message` and `hint`.
- Every mutating call is one Live undo step. Read-only tools carry `readOnlyHint`; destructive tools carry `destructiveHint`.

## 9. Architecture

```
Agent ── MCP (stdio) ── MCP server (Python ≥3.10, mcp 2.x MCPServer) ── TCP 127.0.0.1:9877 ── Remote Script (inside Live, Python 3.11)
                         ├─ tools/          thin: normalise → call → shape
                         ├─ connection      request ids, reconnect, version check
                         ├─ audio/          ffmpeg analysis, images, release pipeline
                         ├─ ui_automation   macOS System Events (optional)
                         └─ theory          pure-Python music theory
```

**Remote Script.** A small, stable `__init__.py` holds the ControlSurface and socket server. Everything
else lives in reloadable modules:

- `core`: registry, dispatch and main-thread execution.
- `refs`: addressing.
- `values`: units and serialisation.
- `lom`: generic access.
- `handlers/*`: domain commands.
- `bounce`: render engine.

Behaviour:

- All Live access runs on the main thread through `schedule_message`. Socket threads only frame and queue.
- Framing is newline-delimited JSON with request ids, plus a tolerant parser for legacy clients.
- `reload_remote_script` is fail-safe. A module that fails to import is reported and its commands are skipped, and the server keeps running.
- Nothing caches `song()`, so the script survives new and opened sets.

**Bounce engine (export without UI).** Live has no render API. The engine:

1. Creates temporary audio tracks: one with input "Resampling" for the master, and one per stem, fed from that track's post-mixer output.
2. Arms only those tracks, saves transport state, and returns playback to the arrangement.
3. Disables loop and metronome, records the range plus a tail in real time, and stops.
4. Collects the recorded files and restores the saved state.

The MCP server then copies and trims the files into the output folder and removes the temporary tracks.
Progress is polled.

**Release pipeline.** This uses ffmpeg, present on the target machine through Homebrew, with numpy
for measurements.

1. Analyse with EBU R128 (integrated loudness, loudness range, true peak) plus statistics and band energies.
2. Normalise: linear gain where possible, true-peak limited otherwise.
3. Dither to 16-bit.
4. Encode: WAV, FLAC, MP3 320 CBR and AAC 256.
5. Tag, embed artwork, and write `release.json` with tempo, key, duration, loudness and checksums.

**UI automation (optional, macOS).** AppleScript through System Events drives menu items and native file
panels for save, new set and offline export. It needs Automation and Accessibility permission for the
host app. `get_status` and `doctor` report availability. These tools fail fast with instructions when
it is unavailable.

**Packaging.** `ableton-mcp` runs the server. `ableton-mcp install` links the Remote Script into the
User Library and can register the MCP server with Claude Code and Claude Desktop. `ableton-mcp doctor`
checks Live, the port, the script version, ffmpeg and permissions.

## 10. Platform limits and workarounds

| Capability | Live API | v2 approach |
|---|---|---|
| Render / export audio | None | Real-time resampling bounce (API only); optional UI-automated offline export |
| Save / new set | None | UI automation; `open_set` via the OS; Live dialogs via the dialog API |
| Group tracks | None | Audio bus tracks via output routing (`create_bus`) |
| Freeze, flatten, consolidate | None | Not supported; bounce covers rendering needs |
| Arrangement automation lanes (track-level) | None | Session clip envelopes, carried into the arrangement by `duplicate_clip` and `arrange_from_scenes`. They stay editable there, but new ones cannot be created on arrangement clips |
| Arrangement tempo changes | None | Scene tempos in Session; one global tempo for the arrangement render |
| Resizing arrangement clips | `end_time` is read-only, but on an unlooped clip `loop_end` sets the extent | `arrange_from_scenes` sizes one looping clip per track per section (spikes.md) |
| Count-in | Read-only | Detected and reported before a bounce |

## 11. Quality and acceptance

**Test layers**

1. Offline unit tests for pure logic: time, pitch, dB, enums, theory, patterns and path parsing.
2. Offline contract tests: every MCP tool targets a registered Remote Script command with matching parameters. Runs in CI without Live.
3. Live integration suites per domain against a running Live. They create scratch tracks prefixed `[test]`, clean up after themselves, and serialise through a lock so parallel runs never collide.
4. End-to-end acceptance against a live set:
   1. Set 124 BPM in A minor.
   2. Build drums from a pattern, a bassline and chords, as two scenes.
   3. Arrange 16 bars with locators.
   4. Mix with a reverb send and a master limiter.
   5. Bounce the master and two stems, and analyse.
   6. Create a release at −14 LUFS in WAV, MP3 and FLAC with tags.

   It passes when every file exists, durations match within 50 ms, integrated loudness is within
   ±1 LU of target, true peak is at most −1 dBTP, and the set is left as found.

**Success metrics**

- The E2E scenario passes unattended.
- 100% of registered commands are exercised by live tests.
- No main-thread command takes more than 2 s.
- The agent never needs `lom_*` for J1–J7.
- The tool catalogue stays at or below 80 tools, and server instructions at or below 600 words.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Live API quirks (display values, insert_device names, recording behaviour) | Phase-0 spikes on the real Live before building; findings in `docs/spikes.md` |
| Real-time bounce glitches on CPU-heavy sets | Preflight CPU check and warning; optional UI offline export; report dropouts if detected (clipping and silence scans) |
| UI automation fragility and permissions | Strictly optional, with capability detection, timeouts and verification through the API (`file_path`, `open_dialog_count`) |
| mcp 2.x is new | Thin adapter layer; fall back to `mcp<2` (1.30) if a blocker appears |
| Parallel development against one Live | File ownership per workstream; lock-serialised live tests; scratch-track isolation |
| Agent misuse damaging user content | Name-scoped operations, destructive annotations, undo per call, bounce cleanup |

## 13. Open questions (resolved by Phase-0 spikes)

1. Does setting `DeviceParameter.display_value` accept display units (dB, Hz)? If not, use a monotonic search over `str_for_value`.
2. Which names does `Track.insert_device` accept, and does it work on chains, returns and master?
3. Does `Track.create_midi_clip` create arrangement clips that accept notes and properties like Session clips?
4. Resampling: is the input type named "Resampling"? Where do recordings land for unsaved sets? Is there a pre-roll or latency offset to trim?
5. Does opening or creating a set re-instantiate the control surface?
6. Do `Envelope.insert_step` and `create_event` give the shapes we need?
7. What are the targets of `Browser.load_item` when a drum pad or a clip slot is selected?
