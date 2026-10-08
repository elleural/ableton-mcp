# NOVA — Listening Loop: PRD and Build Handoff

**Status:** v0.1 — 2026-10-07 — specification only. Nothing here is built, and the existing Ableton MCP has not been inspected (§2).
**Companion to:** `soundtrack-prd.md` v1.0, which says what the music must be. This document specifies the tools that let the composing agent check its own work against that brief.
**Audience:** first the coding agent that builds the tools, then the composition agent that uses them (§12 is written for it).
**Deliverable:** new tools on the Ableton MCP, a standalone analysis package behind them, a spec file derived from the soundtrack PRD, and a calibration report that says which checks can be trusted.
**Repo path:** copy to `docs/listening-loop-prd.md` in the repository the tools are built in.

Two markers are used throughout. **[verify]** means the behavior comes from documentation and has not been run in Live. **†** means a tolerance or severity proposed here, to be tuned during calibration (§13).

---

## 1. Problem and approach

The composition agent (Claude Fable 5.1, working in Ableton Live through the MCP) cannot hear what it makes: current Claude models accept text and images as input, not audio. Today it composes blind, and the first real check is the acceptance script and the human listening pass at the very end (`soundtrack-prd.md` §7.5, §10).

The listening loop closes that gap with four parts:

1. **Capture.** Audio comes out of Live without a person exporting it.
2. **Three kinds of evidence.** Exact checks on the notes, exact measurements on the audio, and fuzzy judgments from audio models ("listeners").
3. **Comparison.** Every result is a difference: from the previous take, from the spec, or from a reference.
4. **Calibration.** Each check proves it can detect planted defects before the agent relies on it.

A **take** is one capture of the set's state: stems, mix, a snapshot of the notes and parameters, and the reports made from them.

## 2. Handoff: start here

**State on 2026-10-07**

- The soundtrack PRD is the only description of the MCP in the project. Its repository, language and tool list were not available when this was written.
- No audio has been captured through the MCP. Everything marked [verify] is untested.
- The game design is being reworked (`claude/pivot-concepts.md`), but the audio system carries over, so the soundtrack PRD is still the brief.

**First three actions**

1. Inventory the MCP: its tools, its language, how the server talks to the Remote Script, and the installed Live version. Write the findings to `docs/handoff/`.
2. Run the capture spike (§6.5). It resolves every [verify] in §6.
3. In parallel, start the analysis package (§7–§9). It needs no Live.

**Settled decisions**

| Decided | Because |
| --- | --- |
| The agent judges from numbers, images and a second model's text | Claude models do not take audio input |
| Capture records inside Live, in real time | Live's API exposes no export call |
| No microphone anywhere in the chain | The audio is already digital; a microphone adds the speakers and the room |
| Notes are checked before audio | The stems are MIDI-driven, so harmony and rhythm can be checked exactly, at no cost |
| Results are differences, not scores | A delta or a target range is something the agent can act on |
| Fuzzy scores never gate | An agent that optimizes a predictor finds what the predictor likes |
| The verdict on a change comes from a fresh, blind subagent | The composer should not grade its own work |
| References are lossless files Frederic owns; streamed audio is measured live and never stored | Repeatable numbers, and the streaming service's terms |
| Analysis is a standalone Python package with a CLI | The MCP's language is unknown; CI must run without Live; it doubles as the acceptance script |
| The human listening check stays the release gate | Soundtrack PRD §10 |

**Hard rules**

1. Audio from a streaming service is measured live and never stored (§11.2).
2. The external audio model receives only audio the agent itself made (§10).
3. Capture leaves the Live set's contents and settings as it found them (§6.4).
4. Tools return compact reports; full data stays on disk (§9).
5. A fuzzy score never decides pass or fail (§10).

## 3. Goals and non-goals

**Goals**

- **G1.** One tool call returns stems and mix for the set's current state at a given tempo, with no human action.
- **G2.** Every requirement of the soundtrack PRD that can be checked from the set, the notes or the audio is a named check with a stated result level (§7, §8). Two things stay outside: Opus encoding, decoding and the size budget belong to the game's build, and the listening check belongs to Frederic.
- **G3.** The agent can compare two takes, or a take against the spec or a reference, and get differences it can act on.
- **G4.** Every fuzzy score is either validated against planted defects and Frederic's own blind picks, or switched off.
- **G5.** The analysis runs from the command line with no Live present, so CI covers it and the engineer can run it as the acceptance script of soundtrack PRD §7.5.

**Non-goals**

- Replacing the human listening check.
- Sample-exact deliverables. Shipped stems still come from Live's Export; capture is for listening and measurement.
- Driving Live's Export dialog by UI automation.
- A microphone or any room measurement.
- Recording or storing audio from a streaming service.
- Training or fine-tuning a model.

## 4. Architecture

```
Composition agent (Fable 5.1)
   │  MCP tool calls  ⇄  compact JSON reports + PNG images
   ▼
Ableton MCP server (exists)        new thin tools: capture · analyze · compare · listen · ref · meter
   │ existing bridge                      │ subprocess or import
   ▼                                      ▼
Remote Script inside Live          ears  (standalone Python package + CLI)
  Live API calls only:               notes checks · audio measurements · tier sums
  routing, arming, firing,           compare · images · ledger · listeners · meter
  reading notes and file paths            │
   │                                      ▼
   └── Live records WAV files ──►  <ears home>/takes · refs · calibration · ledger.jsonl
```

Three rules shape the layout:

1. **The Remote Script makes Live API calls and nothing else.** It runs in Live's embedded Python on Live's main thread: no numpy, no waiting, no file analysis.
2. **All analysis lives in `ears`** (working name), an ordinary Python package with a CLI (`ears analyze <take>`). The MCP tools are thin wrappers around it. This works whatever language the MCP server is written in, lets CI test the analysis without Live, and gives the engineer the acceptance script.
3. **Musical requirements are data.** A spec file holds key, progressions, tempos, loop lengths, layer tiers and targets, and every check reads it. When the soundtrack PRD changes, the spec file changes and the code does not.

Spec file, abridged (`nova.spec.json`, values from the soundtrack PRD; each tier adds its stems to the tier before):

```json
{
  "key": "A minor", "a4_hz": 440, "meter": "4/4", "grid": 16,
  "progressions": {
    "A": ["Am","Am","Dm","Dm"], "B": ["Am","F","Dm","E"],
    "C": ["Am","Dm","G","E"],   "D": ["Am","F","C","G"]
  },
  "sets": {
    "neon":      { "tempos": [100,110,120,130,140,150,160,170,180], "variations": { "A": "A", "B": "B" } },
    "mainframe": { "tempos": [100,110,120,130] }
  },
  "stems": {
    "kick": { "bars": 2, "pitched": false }, "perc": { "bars": 4, "pitched": false },
    "pad":  { "bars": 16 },
    "bass": { "bars": 8, "variations": ["A","B"] }, "arp": { "bars": 8, "variations": ["A","B"] },
    "lead": { "bars": 8, "variations": ["A","B"], "rest_share": 0.4 }
  },
  "tiers": { "T1": ["pad","arp"], "T2": ["bass"], "T3": ["kick"], "T4": ["perc"], "T5": ["lead"] },
  "fills": { "levelup_fill": { "bars": 1 } },
  "loops": { "title": { "bars": 32, "bpm": 100 }, "zone_drone": { "seconds": 32 } },
  "targets": { "lufs_i": -14, "true_peak_dbtp": -1, "tail_ms": 50, "sample_rate": 48000, "bit_depth": 24 },
  "style": { "toward": ["dark cinematic synthwave film score"], "away": ["festival EDM"] }
}
```

A set's `variations` map says which progression each variation's clips play. The brief leaves three things unstated that the spec file must state before the notes checks can cover them: which progressions MAINFRAME's A and B play, at which tempos D replaces A in NEON, and whether the pad is shared (§15, question 7). Until then v1 checks NEON against A and B.

Data layout under a configurable `<ears home>` (default: beside the Live set, not in git):

```
takes/<set>-<bpm>-<variation>-<nnnn>/   take.json · stems/*.wav · mix.wav · snapshot.json · report.json · images/
refs/<name>.json                         numbers only (§11)
calibration/                             fixtures and results (§13)
ledger.jsonl                             one line per take (§9)
```

## 5. Tool surface

Names are proposals; match the MCP's existing naming.

| Tool | Does | Returns | Phase |
| --- | --- | --- | --- |
| `capture_setup` | Creates the capture tracks once | Routes found, warnings | 0 |
| `capture(mode, tempo?, variation?, bars?)` | Records stems and mix into a new take | Take id, files, offset and gain applied, warnings | 0–2 |
| `analyze_notes(scope?)` | Notes checks on the current clips (§7) | Report, piano-roll image | 1 |
| `analyze_audio(take or path, strict?)` | Measurements and tier sums (§8) | Report, images | 1–2 |
| `compare(a, b, blind?)` | Differences between two takes (`"best"` is accepted), or a take and the spec or a reference (`"ref:<name>:<section>"`) | Deltas | 1 |
| `ledger(query?)`, `keep(take)`, `restore(take)` | History; marks a take as the current best; re-applies an earlier take's notes and parameters | Entries; what was restored | 2 |
| `listen(take, question)` | An audio model answers a question about the agent's own take | Text | 3 |
| `ab_test(a, b, criterion)` | Blind, order-swapped A/B by an audio model | Verdict, or "no reliable difference" | 3 |
| `ref_add(file, sections)` | Measures a reference file Frederic owns | Per-section numbers | 4 |
| `ref_play(uri, position)` | Starts a streamed reference on the desktop player | Player state | 4 |
| `meter(seconds, source)` | Measures what is playing now, in memory | Numbers only | 4 |

## 6. Capture

### 6.1 Why recording

Live's API exposes no export call, so other Ableton MCPs either ask the user to export by hand or record through routing. This design records inside Live, in real time.

The analysis side only ever takes file paths. If recording through the API fails in the spike, hand-exported files dropped into a watched folder work with everything in §7–§11 unchanged.

v1 assumes the stems are Session clips launched as scenes (soundtrack PRD §7.1 puts variations in clips named `A` and `B`). If the sets are built in Arrangement, the spike says so and capture uses Arrangement recording instead.

### 6.2 One-time setup: `capture_setup`

Creates one audio track per source, idempotently, named `cap:<source>`:

| Capture track | Input | Tap |
| --- | --- | --- |
| `cap:<stem>` for each stem in the spec (a stem may be a group track) | That stem's track | Post Mixer [verify] |
| `cap:<return>` for each return track | That return track [verify it is selectable] | Post Mixer |
| `cap:mix` | Resampling | — |

- Each capture track's output goes to `Sends Only` with all sends at minimum, so it can never feed back into the mix whatever its monitor setting. The Live Object Model reference lists no monitoring switch on a track, so the design does not depend on one.
- Pick routing values by matching `display_name` in the track's `available_*` lists. Do not hard-code identifiers.
- Capture tracks are armed only while a capture runs.

### 6.3 Two modes

| Mode | How | Gives | Time at 140 BPM |
| --- | --- | --- | --- |
| `tap` (default) | One pass; every capture track records at once | Each stem at its track output, each return, and the mix, all from the same performance | 55 s for variation A; 82 s for A and B |
| `solo` | One pass per stem: solo it and record `cap:mix` | Each stem with its share of the return effects and the master chain, as Live's per-track export would render it | 2.6 min for A; 4.0 min for A and B |

- **Length.** A pass records two cycles of the longest loop in it, so the second cycle already holds the tail of the first (the folded tail of soundtrack PRD §6). `ears` keeps the second cycle. A `bars` argument shortens a pass for quick checks.
- **Other pieces.** `title` (soundtrack PRD §4) and `zone_drone` (§5) are loops and are captured like stems: two cycles, the second kept. `levelup_fill` is one bar, captured at every tempo of its set. The remaining one-shots of §5 are captured once, by length in seconds, with their natural tail.
- **When `tap` is enough.** If no stem sends to a shared return, the tap stems are the stems. The tool reads each stem's sends; where one is above minimum it warns that the tap stem lacks that effect and that tier sums built from it are approximate.
- **Self-check.** In `tap` mode the stems plus the returns must cancel against `cap:mix` (residual 40 dB† or more below the mix). A larger residual means something reaches the master that was not captured: a master effect, or a track missing from the spec. This is also the direct test that the stems sum to the full mix.

### 6.4 Procedure and requirements

Procedure [verify each step in the spike]:

1. Save the settings it will change: tempo, global quantization, and solo, mute and arm of every track.
2. Stop the transport and all clips; set song time to 0; set global quantization to one bar; set the tempo if one was asked for.
3. Arm the capture tracks. In one main-thread call, fire the source clips and fire each capture track's empty slot with a record length in beats.
4. Poll until every slot has finished recording. Read each new clip's file path, sample rate and markers.
5. Delete the temporary clips, disarm, and restore the settings saved in step 1. Do this on error too.
6. `ears` copies the files into the take folder, cuts the second cycle on bar lines computed from the tempo and the clip's markers, and writes `take.json` and the snapshot (§9).

Requirements:

- **C1. Non-blocking in Live.** The Remote Script exposes start and status calls; the MCP tool does the waiting. A pass runs from under a minute to several minutes (§12), so if the client's tool timeout is shorter, split the tool into `capture_start` and `capture_result`.
- **C2. No trace.** After a capture, the set's contents and settings are as before apart from the `cap:` tracks. The transport is left stopped; capture does not resume playback.
- **C3. Bar alignment.** After the offset measured in the spike is applied, bar 1 sits within ±5 ms† of the cut. The take records the offset applied.
- **C4. Unity gain.** A calibration file played through an empty track is captured within ±0.1 dB of the source.
- **C5. Format.** The take records the actual sample rate and bit depth, and warns when they are not the spec's 48 kHz and 24-bit.
- **C6. Provenance.** `take.json` records set name, tempo, variation, mode, bars, Live version, and every warning.
- **C7. Steady tempo.** Capture reads the tempo at the start and end of a pass and fails the take if it moved. The brief allows no tempo automation (§7.1), and the API offers no other way to see it.

### 6.5 Capture spike (Phase 0 exit)

Run each of these on the installed Live and write down the result. Before anything else, confirm that the calls in §6.6 exist under those names in the Remote Script's Python API.

1. **Recording.** Does firing an empty slot of an armed audio track with a record length record exactly that many beats? Is the clip's file path a finished file once the clip stops recording?
2. **Arming.** Can several tracks be armed at once through the API when the exclusive-arm preference is on?
3. **Routing.** Are `Sends Only`, `Resampling`, other tracks and return tracks present in the routing lists? Which tap names exist?
4. **Start alignment.** With the transport stopped and global quantization at one bar, do source clips and record slots fired in the same call start on the same beat? If not, which quantization setting makes them?
5. **Offset and gain.** Generate a calibration file (impulse, sweep, tone at −18 dBFS), load it on an empty track, and capture it by tap and by Resampling. Measure offset in samples and gain error per route. Repeat with a latency-inducing device on another track to see whether delay compensation moves the capture.
6. **Cancellation.** Does the `tap` self-check of §6.3 pass on a simple set?
7. **Solo mode.** Does recording `cap:mix` with one stem soloed give that stem with its return effects? Does sidechain pumping keyed from the kick survive the solo?
8. **Loading files.** Is `create_audio_clip` available on this Live version? It is needed for the calibration file and the reference track (§11.1).
9. **Timeouts.** What is the client's tool timeout against a four-minute pass?

### 6.6 Live API calls the design relies on

Names are from the Live Object Model reference; the Remote Script's Python API is expected to mirror them [verify].

| Need | Call |
| --- | --- |
| Route a capture track | `Track.input_routing_type`, `input_routing_channel`, `output_routing_type`, chosen from the `available_*` lists |
| Arm | `Track.arm` (`can_be_armed`) |
| Record a fixed length | `ClipSlot.fire(record_length)` on an empty slot of an armed track; alternative `Song.trigger_session_record(record_length)` |
| Know when it is done | `Clip.is_recording`, `ClipSlot.has_clip` |
| Find the audio | `Clip.file_path`, `sample_rate`, `sample_length`, `warp_markers`, `start_marker` |
| Read notes | `Clip.get_notes_extended(from_pitch, pitch_span, from_time, time_span)`, `loop_start`, `loop_end`, `name` |
| See which sends are in use | `MixerDevice.sends` (one per return track) |
| Solo and mute | `Track.solo` (setting it bypasses exclusive solo), `Track.mute` |
| Tempo, transport, quantization | `Song.tempo`, `is_playing`, `current_song_time`, `clip_trigger_quantization`, `stop_all_clips` |
| Load a file | `ClipSlot.create_audio_clip(path)` |
| Clean up | `ClipSlot.delete_clip()` |

## 7. Notes ear

Reads the MIDI notes of the stem clips through the MCP. It needs no audio and runs in under a second, so it is the first check after any note edit.

Scope:

- Unpitched stems (`kick`, `perc`) are excluded from pitch checks.
- Notes are read from clips. Where a MIDI effect generates or changes notes (Arpeggiator, Chord, Random, Scale), the clip is not what sounds. The tool lists the MIDI effects on each stem, marks that stem's results "before MIDI effects", and takes its rhythm from audio onsets instead (§8).
- Muted notes are ignored. Notes with a probability below 1 are reported, because they make takes differ.

Result levels: **fail** breaks the soundtrack PRD or a rule derived from it here; **warn** is probably unintended and the composer decides; **report** is information. In the "Brief §" column, "derived" marks a rule that is this document's reading of the cited section, not its wording.

| Check | Passes when | Brief § | Level |
| --- | --- | --- | --- |
| `set.names` | Stem tracks are named exactly as the spec's stems, and variation clips are named `A` and `B` | 7.1 | fail |
| `set.unwarped` | Stem clips are MIDI, or audio with warping off | 6, 7.1 | fail |
| `notes.in_key` | Every pitch is in A natural minor, plus G♯ over an E chord | 2 | fail† |
| `notes.chord_tones` | Notes starting on beats 1 and 3† are tones of that bar's chord, in the progression the spec assigns to the clip's variation. The share of sounding time spent on chord tones is reported per stem. This is the test that every stem of a variation follows one progression | 2, derived | fail for bass, warn elsewhere† |
| `notes.clash` | No two stems of a variation hold pitches a semitone apart, in any octave, for a sixteenth or longer | 2, derived | fail† |
| `notes.shared_stem` | A stem shared between variations (the pad) holds no pitch a semitone away from a chord tone of any progression its set can play in that bar | 4, derived | fail† |
| `notes.loop_length` | The clip's loop length equals the stem's bar count in the spec | 4 | fail |
| `notes.grid` | Onsets sit on the sixteenth grid | derived | warn† |
| `notes.lead_rests` | The lead is silent for 40% of sixteenth steps, ±10 points† | 4 | warn |
| `notes.kick_pattern` | The kick pattern found in each tempo band, beside the brief's description (half-time at 100–120, four-on-the-floor at 130–150; none is named for 160–180) | 2 | report |
| `notes.density` | Onsets per bar per stem, by tempo | 2 | report |
| `notes.motif` | Similarity of interval-and-rhythm sequences between a stem's clips at different tempo bands | 2 | report |

`notes.shared_stem` bears on a choice the soundtrack PRD leaves open (§4: share the pad, or render it per variation). In the fourth bar of the progression, variation A has Dm (D F A) and variation B has E (E G♯ B), which share no chord tone. Under this rule only D and B are safe over both chords, so a shared pad has to thin out to those two notes in that bar, rest, or be rendered per variation. The spec example and the timings in §12 assume a shared pad.

## 8. Measurement ear

Runs on a take, or on any audio files given by path. Loudness must follow ITU-R BS.1770 / EBU R128, since the brief's target is in LUFS; `ffmpeg`'s `ebur128` filter and `librosa` cover the list below, but the libraries are the builder's choice.

**Tier sums.** Built offline by adding stems, each tiled to the longest loop: T1 pad + arp, T2 + bass, T3 + kick, T4 + perc, T5 + lead (soundtrack PRD `layerRules`). One set of sums per variation. If the game can mix variations between stems, add those combinations to the spec file.

| Check | Passes when | Brief § | Level |
| --- | --- | --- | --- |
| `audio.loudness` | T5 measures −14 LUFS integrated, ±0.5 LU†, and true peak is at or below −1 dBTP | 6 | fail |
| `audio.tier_ladder` | Integrated loudness of T1 to T5 and the size of each step; a tier quieter than the one below it points to cancellation | 1 | report; warn on a drop |
| `audio.tempo_consistency` | Each stem's loudness stays within ±1 LU† across the tempos of its set | 6 | fail |
| `audio.key` | The chroma key estimate is A minor | 7.5 | fail for the mix, warn per stem |
| `audio.mono_sub` | Below 120 Hz (the bass crossover in `requirements.md` §9.5), the mono sum loses at most 1 dB† against stereo | 6 | fail |
| `audio.sum_null` | The `tap` self-check of §6.3 passes | 1 | fail |
| `audio.balance` | Energy per band, per stem and per tier, against the reference envelope when one exists (§11) | — | warn outside the envelope |
| `audio.masking` | For each pair of stems in a tier, where both carry energy in the same third-octave band at the same time; the largest overlaps are listed | — | report |
| `audio.onsets` | Onset times against the sixteenth grid, for stems whose notes pass through MIDI effects | derived | report |
| `audio.reactivity` | The game's analyser simulated over each tier sum: mean and movement in each of its four bands | — | report |
| `audio.phone` | The same measurements after a phone-speaker simulation (high-pass at 200 Hz†, mono); share of each stem and one-shot that survives | — | report |

Notes on two of these:

- **`audio.reactivity`** exists because the game world is driven by four analyser bands: 20–80 Hz, 80–500 Hz, 500 Hz–4 kHz and 4–10 kHz. A band that never moves gives dead visuals. Simulate the analyser as `requirements.md` §9.2 specifies it: FFT size 2048, `smoothingTimeConstant` 0.5, `minDecibels` −90, `maxDecibels` −20, byte magnitudes averaged over the band's bins and divided by 255, then a one-pole envelope with 20 ms attack and 200 ms release, read once per frame. The result is approximate, because the game's analyser also sees its compressor, limiter and sound effects.
- **`audio.phone`** is the cheap stand-in for testing on a device. It matters most for the one-shots: the `zone_drop` sweep from 80 to 35 Hz is below what most phone speakers reproduce.

**Strict mode** (`strict: true`) is for files exported from Live for delivery. It adds the file checks of soundtrack PRD §6 and §7.5, all at fail level:

| Check | Passes when | Brief § |
| --- | --- | --- |
| `file.duration` | Length is bars × 240 / BPM + 0.050 s, ±1 ms | 6, 7.5 |
| `file.seam` | The brief's seam test passes (crossfading end to start, the peak at the seam is within 1 dB of the surrounding RMS), and a click detector† finds nothing | 7.5 |
| `file.start` | No padding before bar 1: where the clip has a note on beat 1, its transient is at the start of the file | 6 |
| `file.format` | 48 kHz, 24-bit, stereo | 6 |

Opus encoding, decode in Chromium and the size budget stay in the game's build.

**Images.** The agent can read images, so each report can carry up to two PNGs, at most 1,200 px wide, returned as MCP image content and saved in the take: stem spectrograms stacked on one time axis with bar lines and chord labels; a piano roll colored by chord-tone status; a band-balance chart against the reference envelope; a zoom on the loop seam in strict mode. Spectrograms are for structure (where the energy sits, when a layer enters, a click), not for judging how something sounds.

**Speed.** `analyze_audio` on a `tap` take returns in under 20 seconds†, listeners excluded.

## 9. Compare, reports and the ledger

**Reports.** Every tool returns a compact report, about 1,500 tokens at most: one verdict line, the fails, the warns, the largest deltas, image paths, and the path of the full JSON on disk. The agent's context is the scarce resource. Illustrative shape:

```json
{
  "take": "neon-140-A-0031",
  "verdict": "1 fail, 2 warn, 29 pass",
  "fail": [
    { "check": "notes.chord_tones", "stem": "bass", "where": "bar 3, beat 1",
      "found": "G2", "expected": "a tone of Dm (D F A)" }
  ],
  "warn": ["..."],
  "deltas_vs": "neon-140-A-0030",
  "deltas": [
    { "metric": "T5 integrated loudness", "from": -15.1, "to": -14.2, "target": -14.0, "status": "improved" }
  ],
  "images": ["takes/neon-140-A-0031/images/stems.png"],
  "full_report": "takes/neon-140-A-0031/report.json"
}
```

**`compare(a, b)`**

- Loudness-matches the two sides before any spectral or listener comparison, so level does not pass for quality.
- Marks each delta improved, regressed or within noise. Noise is the take-to-take spread measured in §13.1; until that has been run, a default floor of 0.5 dB† applies.
- With `blind: true`, returns a packet for a judge that must not know which take is new: the takes are labeled X and Y in random order, and take ids, times and the improved or regressed statuses are left out.
- Accepts the spec or a reference section as `b`. Against a mastered reference, crest factor and loudness range are information only: a mastered track is denser than an unlimited stem sum, and the brief's −14 LUFS and −1 dBTP win.

**Ledger.** `ledger.jsonl` gets one line per take: id, time, set, tempo, variation, mode, the agent's one-line note on what changed, the verdict line, and the snapshot path. It also holds one `best` pointer per set, tempo and variation: the take the agent last decided to keep. `keep(take)` moves the pointer, and `compare` accepts `"best"` in place of a take id.

**Snapshot and restore.** The snapshot holds the notes of every stem clip, the mixer values and every device parameter value. `restore(take)` writes notes and parameter values back. Devices added or removed since are listed, not undone, and plugin state that is not exposed as parameters is not covered; for changes of that kind the agent asks for the set to be saved under a new name first.

## 10. Listeners

Phase 3. Each is off until it passes calibration (§13).

| Listener | Runs | Hears | Gives | Role |
| --- | --- | --- | --- | --- |
| Text-and-audio embedding (CLAP) | Locally | Own takes; reference files Frederic owns | Similarity to the spec's `style` prompts; distance to references | Tripwire for style drift |
| Cross-modal embedding (CLaMP 3) | Locally | The MIDI of the agent's clips | Similarity of the notes to the same prompts, before any audio exists | Early style check |
| Aesthetic predictor (Audiobox Aesthetics) | Locally | Own takes | Production quality, production complexity, content enjoyment, content usefulness | Tie-breaker |
| Audio LLM (`listen`, `ab_test`) | External API (Gemini) | Own takes only | A text answer; an A/B verdict | Open-ended critique |

Rules:

- **L1.** No listener output is a pass or fail. They raise questions and break ties.
- **L2.** `ab_test` loudness-matches two unlabeled clips, runs twice with the order swapped, and gives a verdict only when both runs agree. Otherwise it returns "no reliable difference".
- **L3.** Whether a new take is better is decided by a fresh subagent that does not know which take is new. It is given only the blind packet from `compare` (§9), the `ab_test` result and the listener notes, all labeled X and Y.
- **L4.** The audio LLM hears a reduced signal. Gemini downsamples audio to 16 Kbps and folds stereo to one channel, at 32 tokens per second. Ask it musical questions (does the lead tire over eight bars, does the drop land) and ask for timestamps. Never ask it about width, sub weight or fine timbre.
- **L5.** The external API receives only audio the agent made. Reference audio never goes to it.
- **L6.** Model ids and API keys live in config and the environment, never in the ledger. Record each local model's license in the README before enabling it; several music models are non-commercial. Music Flamingo is the local alternative to the external audio LLM, subject to the same license check.

## 11. References

### 11.1 Files Frederic owns

- `ref_add(file, sections)` reads a purchased lossless file directly, with no capture pass, and stores per-section measurements in `refs/<name>.json`. Sections are named time ranges (intro, drop, breakdown).
- The **reference envelope** is the range of each metric across the references, per section type. `audio.balance` and `compare` use it.
- Compare T5 against a reference's full sections and the lower tiers against its sparser ones. References are full mixes.
- For Frederic's own A/B, the tool can load the file onto a `REF` track in Live.

### 11.2 Streamed references: a meter, not a recorder

For a track that is only available on Spotify, the tools measure it while it plays and keep the numbers.

- `ref_play(uri, position)` drives the Spotify desktop app by AppleScript (`play track`, `set player position`, `pause`) [verify]. macOS asks once for permission to control Spotify.
- `meter(seconds, source)` reads the audio interface's loopback input into memory for that many seconds, computes the measurement set of §8, returns numbers, and discards the buffer.

Requirements:

- **M1.** No audio from an external source reaches disk, cache, logs or a tool result. Only derived numbers do. The external path contains no file writer, and a test watches the filesystem during `meter` to prove it.
- **M2.** `source: "external"` computes measurements only. The audio LLM cannot be reached from that path at all. Embeddings sit behind a config flag that is off by default; only Frederic sets it (§15, question 4), and no tool the agent can call changes it.
- **M3.** Both sides use one chain: the agent's take is played in Live and metered through the same loopback with `source: "live"`.
- **M4.** The absolute level of an external source is uncalibrated, because it depends on the player's volume and normalization. External comparisons are therefore loudness-matched and about shape: band balance, dynamics, stereo width, onset density, tempo and key. An external result carries no absolute loudness figure.
- **M5.** Results are cached per section in `refs/<name>.json`, so each section plays once.
- **M6.** One-time setup by Frederic: Spotify volume at maximum, normalization off, crossfade off, and macOS alert sounds sent to a different output.

Hardware: every 4th Gen Scarlett has loopback (inputs 3–4 on the Solo and 2i2). In the 3rd Gen only the 4i4, 8i6, 18i8 and 18i20 do. Without it, use a virtual loopback device or stay with §11.1.

Calibration: a tone played from Live at a known level reads within ±0.1 dB through `meter`. [verify] that a second process can read the interface's inputs while Live holds the device.

## 12. Protocol for the composition agent

Package this section as a skill or a `CLAUDE.md` section in the MCP repository (Phase 5).

1. After every note edit, run `analyze_notes`. Clear the fails before rendering anything.
2. After a batch of sound or mix changes, run `capture` (tap, one tempo) and `analyze_audio`. Clear the fails.
3. Before keeping a change, run `compare(new, "best")`. If nothing regressed beyond noise, `keep` the new take. Otherwise `restore` the best one.
4. Work at one tempo in the middle of the set (140 BPM for NEON). Check the set's lowest and highest tempo before calling a stem set done. Sweep every tempo only at milestones.
5. At milestones, add a `solo` capture, the reference comparison, `listen`, and an `ab_test` judged by a fresh subagent.
6. Claim only what the evidence supports. Passing every check does not mean it sounds good. A subjective claim needs an A/B verdict or Frederic's ear.
7. The human listening check of soundtrack PRD §10 stays the release gate.

Real-time cost of a capture, before a few seconds of overhead per pass:

| | 100 BPM | 140 BPM | 180 BPM | All nine NEON tempos |
| --- | --- | --- | --- | --- |
| `tap`, variation A | 77 s | 55 s | 43 s | 8.5 min |
| `tap`, A and B | 115 s | 82 s | 64 s | 12.8 min |
| `solo`, variation A | 3.7 min | 2.6 min | 2.0 min | 24.5 min |
| `solo`, A and B | 5.6 min | 4.0 min | 3.1 min | 37.3 min |

`tap` records 32 bars for A (two cycles of the 16-bar pad) and 16 more for B. `solo` records two cycles of each stem's own loop: 92 bars for A and 48 more for B. Both assume a shared pad. If the pad is rendered per variation, the B pass is as long as the A pass, and A and B together take 110 s in `tap` mode or 4.9 min in `solo` mode at 140 BPM.

## 13. Calibration

### 13.1 Repeatability

Capture one unchanged state three times and measure the spread of every metric. That spread is the noise floor: `compare` reports smaller deltas as "within noise". It is needed because free-running oscillators and the lead's random pitch modulation make every pass slightly different.

### 13.2 Planted defects

| Defect | Must be caught by |
| --- | --- |
| Bass a semitone off for one bar | `notes.in_key`, `notes.chord_tones` |
| D major where Dm belongs (an F♯) | `notes.in_key`, `notes.chord_tones` |
| Two stems a semitone apart for a beat | `notes.clash` |
| Kick late by a thirty-second note (54 ms at 140 BPM) | `notes.grid` |
| Lead with no rests | `notes.lead_rests` |
| +6 dB at 3 kHz on the arp | `audio.balance`, `compare` |
| Sub out of phase between channels | `audio.mono_sub` |
| One stem 3 dB louder at one tempo | `audio.tempo_consistency` |
| Reverb on the master only | `audio.sum_null` |
| Click at the loop seam; tail not folded | `file.seam` |
| File 5 ms short | `file.duration` |

Each defect exists twice: as a synthetic fixture generated in code, which CI runs, and planted once in the real Live set. In fixture form `audio.balance` runs against a synthetic reference envelope, and `compare` against the clean fixture. For each listener, record whether its score moves the right way on each audible defect.

### 13.3 Agreement with Frederic

Twenty pairs of takes, picked blind by Frederic with a small local tool that plays each pair in random order and logs the choice. A listener is enabled as a tie-breaker only if it agrees with him on at least 15 of the 20; random guessing does that about 2% of the time.

### 13.4 Output

`docs/listening-loop-calibration.md`: one row per check and listener, with the defects it catches, its agreement rate, its noise floor, the tuned value of every † tolerance, and whether it is enabled.

## 14. Phases and acceptance

| Phase | Build | Done when |
| --- | --- | --- |
| 0. Inventory and capture spike | MCP inventory; `capture_setup`; `capture` in `tap` mode on one scene | Findings written to `docs/handoff/`; C2 to C4 measured; every [verify] in §6 resolved or replaced by a fallback |
| 1. Analysis core (parallel with 0) | `ears` package and CLI; spec file; notes ear; measurement ear with tier sums and strict mode; `compare`; report format | CI green on synthetic fixtures; every defect in §13.2 caught in fixture form; one real take analyzed |
| 2. Full capture | `solo` mode; tempo sweeps; images; ledger, snapshot, `keep` and `restore` | One call gives a full report for a tempo; `restore` round-trips notes and parameters; §13.1 recorded |
| 3. Listeners | Embeddings; aesthetic scores; `listen`; `ab_test`; blind `compare`; the blind A/B tool for Frederic | The calibration report says which listeners are enabled |
| 4. References | `ref_add` and the envelope; `ref_play` and `meter` | `compare` works against an owned reference; tests for M1, M2, M4 and M5 pass in CI; M3 and the calibration tone pass in a scripted run on the Mac; M6 confirmed by Frederic; both [verify] items of §11.2 resolved |
| 5. Protocol | §12 as a skill; final handoff | A fresh composition session uses the loop unprompted on a test stem |

## 15. Open questions for Frederic

1. **The MCP.** Where is its repository, what language is it in, and which Live version and edition is installed? Phase 0 cannot start without the repository.
2. **The Scarlett.** Which model and generation? It decides whether `meter` can use hardware loopback.
3. **External audio model.** May your own takes be sent to the Gemini API? It needs a key. Default: off.
4. **Embeddings on streamed audio.** Default: off. Spotify's developer policy bars ingesting its content into a machine-learning or AI model; whether that reaches an in-memory embedding on your own machine is your call.
5. **References.** Which three or four tracks, in which form (owned file or streamed), and which sections?
6. **Reverb and delay.** Per-stem inserts or shared returns? Inserts make `tap` captures equal to the stems. Shared returns need `solo` mode, and they also decide how each shipped stem carries its reverb.
7. **Gaps in the brief.** Which progressions do MAINFRAME's A and B play (the brief calls C "CIRCUIT only")? At which tempos does D replace A in NEON? Is the pad shared or rendered per variation (§7)? The notes checks need all three in the spec file.
8. **Tolerances.** Everything marked † is a starting value.

## 16. Process

Frederic's global agent rules (`~/.claude/CLAUDE.md`) apply. For this job that means:

- A new worktree for the session, and one branch per phase off freshly pulled main.
- Merge main into the branch before the PR; never rebase. PR, checks, merge. Delegate CI watching.
- A handoff in `docs/handoff/` after each phase. Load the repository's build skills before building.
- CI covers `ears` with synthetic fixtures and needs no Live. Live-dependent behavior is checked by a scripted run on the Mac, with the results committed in the handoff. Listening and device loops get their own lightweight session.

Suggested routing under those rules:

| Work | Model and effort |
| --- | --- |
| Measurement core (loudness, true peak, seam, alignment) and capture timing | Main-loop frontier model, high |
| Remote Script capture, snapshot and restore, the meter process | Opus, high |
| Notes checks, CLI, report formatting, fixtures, images | Sonnet, high; escalate on any failure |
| Review of each phase | Opus, high |
| Handoff documents | Sonnet, medium |

## 17. Sources

- [Claude models overview](https://platform.claude.com/docs/en/models/overview) — input modalities
- Live Object Model: [ClipSlot](https://docs.cycling74.com/apiref/lom/clipslot/), [Clip](https://docs.cycling74.com/apiref/lom/clip/), [Track](https://docs.cycling74.com/apiref/lom/track/), [Song](https://docs.cycling74.com/apiref/lom/song/), [MixerDevice](https://docs.cycling74.com/apiref/lom/mixerdevice/)
- Prior art: [ableton-for-ai](https://pypi.org/project/ableton-for-ai) (hand-exported stems, summaries and spectrograms), [an Ableton MCP with routing capture](https://glama.ai/mcp/servers/shymbsx7uh) (notes that the API cannot trigger export), [jterrats/ableton-live-mcp](https://glama.ai/mcp/servers/jterratsdev/ableton-live-mcp/tree) (audio and mix analysis tools)
- [Gemini API: audio understanding](https://ai.google.dev/gemini-api/docs/audio) — token rate, downsampling, channel handling
- [Meta Audiobox Aesthetics](https://arxiv.org/html/2502.05139v1), [CLaMP 3](https://arxiv.org/abs/2502.10362v3), [Music Flamingo](https://research.nvidia.com/labs/adlr/MF)
- [Focusrite: which Scarlett interfaces have loopback](https://support.focusrite.com/hc/de/articles/207546775-Does-the-Scarlett-range-have-loopback), [Scarlett 4th Gen loopback](https://support.focusrite.com/hc/en-gb/articles/13229216604562)
- [Spotify Developer Policy](https://developer.spotify.com/policy/), [Spotify User Guidelines](https://www.spotify.com/sa-en/legal/user-guidelines/), [Spotify AppleScript commands](https://playbooks.com/skills/openclaw/skills/spotify-applescript)
- Project documents: `soundtrack-prd.md`, `requirements.md` §9.2 and §9.5, `claude/pivot-concepts.md`
