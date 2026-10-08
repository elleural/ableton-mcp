# Listening loop — build plan

Implements [listening-loop-prd.md](listening-loop-prd.md) (the PRD) in this repository. Status and
verified Live behaviour go to [spikes.md](spikes.md) and `docs/handoff/`.

**Status (2026-10-07): phases 0, 1, 2 and the agent protocol are built and verified** on Live 12.4.6 with
the NOVA set; calibration in [listening-loop-calibration.md](listening-loop-calibration.md), state and
next steps in [handoff/2026-10-07-listening-loop.md](handoff/2026-10-07-listening-loop.md). Phases 3
(listeners) and 4 (references, meter) wait for the answers to PRD §15.

## 1. Inventory (PRD §2, first action)

The PRD was written without seeing this MCP. What exists (2026-10-07, `main` at 52c0610):

- **Language and wiring.** Python throughout. The MCP server (`MCP_Server/`, mcp 2.x) sends JSON lines over
  TCP 127.0.0.1:9877 to the Remote Script (`AbletonMCP_Remote_Script/`), which runs handlers on Live's main
  thread from a 10 ms timer, one undo step per mutating command. Long jobs are `@ticker` state machines
  with their state in `ctx.state` (survives hot reload). Details: [DEVELOPING.md](DEVELOPING.md).
- **Live.** 12.4.6 Suite, embedded Python 3.11.6, audio at 44.1 kHz on this Mac (the PRD's 48 kHz is a
  delivery format; C5 warns).
- **Tools.** 78, budget 80 (contract test). Relevant ones: `bounce` / `get_bounce_status` /
  `cancel_bounce` (a proven real-time *arrangement* recorder: master by Resampling, stems by each track's
  `Post Mixer` tap, sample-exact offsets from the recorded clip's markers), `analyze_audio` (ffmpeg
  EBU R128 + numpy statistics + spectrogram PNG), `get_notes`, `get_mixer`, `get_device`.
- **The real set.** Live has the NOVA set open (unsaved), composed by the soundtrack session
  (`tetris-nova` worktree `tetris-nova-soundtrack-0e150b`, handoff `docs/handoff/soundtrack-handoff.md`):
  - one set for NEON, MAINFRAME (`mf_` tracks) and the one-shots (`cm_` tracks);
  - **variations on separate tracks** (`bassA`, `bassB`, …; clips named `A`, `B`), not clips on one track;
  - Session scenes per tempo band (`NEON-LOW` 100–120, `NEON-MID` 130–150, `NEON-HIGH` 160–180, plus
    `NEON-FILL`, `TITLE`, `MF-MID`, `MF-LOW`, `MF-FILL`, `COMMON`); only `kick` and `perc` have per-band
    clips, the other stems live in the MID row;
  - reverbs and delays are per-track inserts; returns `A-Reverb`, `B-Delay` exist;
  - the composer rendered by arranging scenes and bouncing the arrangement, then cut and trimmed in post
    (`tools/music/cut_stems.py`). Shipped masters (48 kHz, 24-bit) are in that worktree's
    `public/music/masters/`.
- **Answers the set gives to PRD §15 q7.** MAINFRAME B plays `Am|Dm|G|E` (progression C); D is not used
  in NEON; the pad is shared by A and B.

## 2. Decisions and deviations from the PRD

| Topic | Decision | Why |
| --- | --- | --- |
| Capture mechanism | **Session recording**: temporary `cap:*` audio tracks, armed, monitoring Off, output `Sends Only`; source clip slots and the capture slots fired in one main-thread tick; recording stopped by stopping the transport after the planned beats plus a margin; `ears` cuts the kept cycle from the clip markers | Live's Python `ClipSlot.fire()` takes **no record length** (PRD §6.6 assumed one), so length comes from stopping, as in the arrangement bounce. Session recording leaves the arrangement untouched (arrangement record would log every clip launch into the user's tracks). Fallback if the spike fails: arrange the needed clips past the last event and reuse the bounce engine |
| Capture tracks | Temporary, created per capture and deleted afterwards (the PRD proposed persistent ones plus `capture_setup`) | Stricter C2 (no trace), no stale routing, one tool fewer. Costs about two ticks of routing time |
| Tracks outside the pass | Muted for the pass (tap) or left unsoloed (solo), restored afterwards | Their arrangement clips would otherwise play into `cap:mix` |
| Variation layout | Supports both: one track per variation (`bassA`, the real set) and one track with clips `A`/`B` (PRD §7.1) | The real set uses the first |
| Passes | One pass captures every variation when they sit on separate tracks and no stem uses a send; otherwise one pass per variation | Fewer real-time seconds; returns and mix stay attributable |
| Tool surface | 4 new tools (`capture`, `analyze_notes`, `compare`, `takes`) plus `analyze_audio(take=…, strict=…)`; budget raised from 80 to 90 for the listening loop's phases | Keeps the catalogue small: `capture_setup` folds into `capture`; status and cancel are `capture(wait=…)` / `capture(cancel=True)`; `ledger`/`keep`/`restore` are `takes(action=…)` |
| `ears` | A standalone top-level package in this distribution (`ears`, CLI `ears`), importing nothing from `MCP_Server` or the Remote Script; the MCP tools import it | No subprocess hop; CI tests it without Live; it is the acceptance script |
| Dependencies | numpy, scipy (filters, resampling), matplotlib (images, imported lazily) | BS.1770 in numpy/scipy works on in-memory tier sums; ffmpeg stays for decoding and a cross-check |
| Spec | `specs/nova.spec.json` in this repo, selected by `spec="nova"`, a path, `EARS_SPEC`, or `<ears home>/spec.json` | Versioned with the checks that read it |
| ears home | `EARS_HOME`, else `<set folder>/ears` for a saved set, else `~/Music/AbletonMCP/Ears/<set name or untitled>` | PRD §4: beside the Live set, not in git |

## 3. Tool surface (MCP)

| Tool | Does |
| --- | --- |
| `capture(set, variation, tempo, tempos, mode, bars, note, wait, cancel)` | Plans passes from the spec, records them in Live, ingests a take per tempo, returns take ids and warnings. Long-polls up to `wait` s; call again with no arguments to keep waiting |
| `analyze_notes(set, band, parts)` | Notes ear (PRD §7) on the current clips; report plus piano-roll image |
| `analyze_audio(path, take, strict, …)` | Existing tool; `take=` runs the measurement ear (PRD §8) with tier sums, `strict=` adds the file checks |
| `compare(a, b, blind)` | Deltas between takes (`"best"` accepted), or a take against `"spec"` or `"ref:<name>:<section>"` |
| `takes(action, take, …)` | `list` (ledger), `keep` (best pointer), `restore` (notes and parameters from a take's snapshot) |

Phase 3 adds `listen` and `ab_test`; Phase 4 adds `ref` (add, play) and `meter`.

## 4. Package layout and ownership

```
ears/                    standalone analysis package (no MCP / Live imports)
  spec.py                spec loading, parts, bands, progressions                     lead
  report.py              check results, verdict, compact and full reports             lead
  audio.py               read/write WAV, decode via ffmpeg, mono/stereo helpers       lead
  loudness.py            BS.1770-4 integrated/short-term/momentary, LRA, true peak    lead
  strict.py              file.duration, file.seam, file.start, file.format            lead
  tiers.py               tiling with the game's crossfade, tier sums                  lead
  measure.py             key, bands, mono sub, masking, onsets, reactivity, phone     agent M
  analyze.py             measurement ear: runs the audio checks on a take             lead
  theory.py, notes.py    notes ear                                                    agent N
  images.py              PNGs                                                         agent I
  take.py, ledger.py     take folders, ingestion, ledger, best pointers               lead
  compare.py             deltas, blind packets, spec and reference comparisons        lead
  refs.py                reference files and the envelope                             lead
  fixtures/              synthetic stems and snapshots with planted defects           lead + N
  calibration.py         planted-defect run, repeatability                            lead
  cli.py                 `ears` CLI                                                    lead
specs/nova.spec.json                                                                  lead
AbletonMCP_Remote_Script/handlers/capture.py     session capture engine               lead
AbletonMCP_Remote_Script/handlers/listening.py   snapshot and restore commands        agent R
MCP_Server/tools/listening.py                    the four tools                       lead
tests/ears/              offline tests (CI)        tests/live/test_capture.py, test_listening.py
```

## 5. Data formats (shared contract)

**Snapshot** (`listening_snapshot`, also `snapshot.json` in a take):
`{song: {tempo, time_signature, set_name, set_path, live_version}, scenes: [{index, name}],
tracks: [{index, name, kind, mute, solo, arm, mixer: {volume_db, pan, sends: {A: dB|null}},
devices: [{path, name, class_name, type, active, parameters?: [{index, name, value, min, max, quantized, display}]}],
clips: [{slot, scene, name, is_midi, length, looping, loop_start, loop_end, start_marker, end_marker,
warping, muted, notes?: [{id, pitch, start, duration, velocity, mute, probability, velocity_deviation}]}]}],
returns: [same as tracks, plus letter], master: {mixer, devices}}`. Times in beats; `volume_db` null for −inf.

**Check result** (`ears.report.Check`): `{check, status, subject, summary, items?, value?, target?}` with
`status` in `pass | fail | warn | info | skip`. A check's level (PRD tables) decides whether a violation is
`fail` or `warn`; report-level checks give `info`.

**Report:** full JSON on disk; the compact form (about 1,500 tokens at most) carries `verdict`
("1 fail, 2 warn, 29 pass"), the first fails and warns, the largest deltas, image paths and `full_report`.

**Take folder:** `takes/<set>-<bpm>-<variation>-<nnnn>/` with `take.json` (C6 provenance, offsets, gains,
formats, warnings, parts → files), `stems/<part>.wav`, `returns/<name>.wav`, `mix.wav`, `snapshot.json`,
`report.json`, `images/`. `variation` is `A`, `B` or `AB`.

## 6. Phases in this session

| Phase | Scope | Exit |
| --- | --- | --- |
| 0 | Inventory (above); capture spike on scratch tracks: recording, arming, routing, alignment, offset and gain per route, cancellation, solo, `create_audio_clip` | Findings in `spikes.md`; C2–C4 measured |
| 1 | `ears` core, spec, notes ear, measurement ear, tier sums, strict mode, compare, report format, CI | CI green on fixtures; every PRD §13.2 defect caught in fixture form; the shipped masters analysed in strict mode; one real take |
| 2 | Solo mode, tempo sweeps, images, ledger, snapshot, `keep`, `restore` | One call gives a full report for a tempo; `restore` round-trips; §13.1 repeatability recorded |
| 5 (part) | Agent protocol (PRD §12) in the server instructions and a skill file | Protocol reachable from any client |

Phases 3 (listeners) and 4 (references by meter, Spotify) need Frederic's answers (PRD §15 q2–q5) and go
to the next session with a handoff. `ref_add` for owned files is built here only as far as `audio.balance`
and `compare` need a reference envelope.

## 7. Model tiers

Lead (main loop): spec and report contracts, measurement core, capture spike and engine, integration,
review synthesis. Agent N (notes ear), I (images), M (spectral measurements): Sonnet. Agent R
(snapshot/restore in the Remote Script): Opus. Review of the finished branch: Opus. Live work is
serialised through the live-test lock (`.live-test.lock`).
