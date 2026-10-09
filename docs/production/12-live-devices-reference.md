# Live 12 devices reference: what each device is for, key parameters, pro settings, pitfalls

Audience: AI agents that drive Ableton Live 12.4.6 Suite through the AbletonMCP server and cannot hear. Keep this file open while you call `get_device`, `set_device_parameters`, `set_device`, `add_device` and `set_chain`. Deeper material lives next door: synthesis and instruments in [02-synthesis-and-live-instruments.md](02-synthesis-and-live-instruments.md), recipes by role in [03-sound-design-recipes.md](03-sound-design-recipes.md), kick and bass in [04-drums-and-low-end.md](04-drums-and-low-end.md), gain staging and meters in [05-gain-staging-and-metering.md](05-gain-staging-and-metering.md), mixing workflow in [06-mixing.md](06-mixing.md), limiting and delivery in [07-mastering-and-loudness.md](07-mastering-and-loudness.md), arrangement and voicing in [08-arrangement-and-composition.md](08-arrangement-and-composition.md), game stems in [10-game-audio-adaptive-music.md](10-game-audio-adaptive-music.md), judging audio without ears in [11-listening-without-ears.md](11-listening-without-ears.md).

How this was built: device behaviour comes from the [Live 12 manual](https://www.ableton.com/en/live-manual/12/) (Audio Effect Reference, Instrument Reference, Racks, Routing). Parameter names, item lists and raw ranges were checked on 2026-10-08 against [reference/live-12.4.6-device-parameters.json](reference/live-12.4.6-device-parameters.json) (every native audio effect, instrument and MIDI effect added to a scratch track in the running Live 12.4.6 and read back with `get_device`; readable form in [reference/live-12.4.6-device-parameters.md](reference/live-12.4.6-device-parameters.md); regenerate with `scripts/dump_device_parameters.py`), and against take snapshots recorded on this Mac. "Start" values are starting points, never targets; where a number comes from the manual it is linked, otherwise it is common practice and marked "convention".

Trust tags on every device card:

- **[12.4.6]** parameter names and item lists verified against the reference dump from this install. The dump holds raw ranges and default displays; display ranges that only the manual states (for example `HP Freq` 20 Hz to 2 kHz) are linked to it.
- **[manual]** behaviour described by the manual; no parameter list was available (Drum Sampler, the DS drum synths and the Legacy devices were not dumped).

Cards that earlier carried a [12.0] tag (names taken from Ableton's Live 12.0 Remote Script tables) were re-verified against the dump: section 1.6 lists the names that changed. The `original_name` fallback in `set_device_parameters` may absorb a rename, but do not rely on it (a unique substring only helps when your string is shorter than the real name).

Contents: [five things](#if-you-remember-five-things) · [device index](#device-index) · [1 setting parameters](#1-setting-parameters-names-units-display-strings-raw-values) · [2 dynamics](#2-dynamics) · [3 EQ and filters](#3-eq-and-filters) · [4 saturation and distortion](#4-saturation-and-distortion) · [5 modulation and space](#5-modulation-and-space) · [6 instruments](#6-instruments-key-parameters-only) · [7 racks](#7-racks-macros-chain-selector-addressing) · [8 recipes](#8-recipes-by-job) · [9 checklists](#9-checklists) · [sources](#sources) · [open questions](#open-questions--where-sources-disagree)

## If you remember five things

1. **Read before you write.** Call `get_device` first. Names, item lists and raw scales differ per device and per Live build, and the device may be a "Legacy" twin (`Auto Filter Legacy`, `Erosion Legacy`) with different parameters. Never build a call from memory alone.
2. **Send display strings, then read the echo.** `"-6 dB"`, `"800 Hz"`, `"30 %"`, item names for choosers. Numbers are raw, and the raw scale changes from device to device. A display value outside the range, or a beat fraction such as `"1/8"`, does not raise an error: it can land on the wrong value. Compare the returned `display` with what you asked for, every time ([section 1](#1-setting-parameters-names-units-display-strings-raw-values)).
3. **One device, one change, then measure and ask.** Mode and type parameters first, amounts second. Keep the previous version (Live's device A/B via `set_device(compare_b=...)`, or a muted twin track) and let the producer judge a loudness-matched A/B. The 2026-10-08 failure was many changes at once on every track.
4. **Dynamics, distortion and modulation are the dangerous devices.** Limiter belongs last on Main only, never as a gain stage on stems. Saturation on whole chords makes intermodulation that reads as "out of tune". Chorus on noise sounds flangy. Broad EQ cuts and new faders on every track at once sound like "garbage". Adding a device to a sound the producer approved needs his yes first.
5. **Low end stays mono and space lives on returns.** Utility `Bass Mono` goes last in the chain (about 120-200 Hz), width comes from unison or stereo spread rather than chorus, and reverb and delay run at Dry/Wet 100 % on return tracks with the lows cut. And not everything is a parameter: sidechain sources, EQ Eight modes, Roar routing, Hybrid Reverb impulse responses and Hi-Quality switches live in properties or menus ([1.5](#15-things-that-are-not-parameters)).

## Device index

Class names are what `get_devices` reports as `class_name` (from [docs/spikes.md](../spikes.md) and the snapshots). A "legacy" class is the older device that old sets and some library presets still load.

| Device | `class_name` | Section |
| --- | --- | --- |
| Compressor, Glue Compressor, Drum Buss | `Compressor2`, `GlueCompressor`, `DrumBuss` | 2.1-2.3 |
| Multiband Dynamics, Gate, Limiter, Utility | `MultibandDynamics`, `Gate`, `Limiter`, `StereoGain` | 2.4-2.7 |
| EQ Eight, EQ Three, Channel EQ | `Eq8`, `FilterEQ3`, `ChannelEq` | 3.1-3.3 |
| Auto Filter | `AutoFilter2` (legacy `AutoFilter`) | 3.4 |
| Spectral Resonator, Corpus, Resonators | `Transmute`, `Corpus`, `Resonator` | 3.5-3.7 |
| Saturator, Roar, Pedal, Overdrive, Amp, Cabinet | `Saturator`, `Roar`, `Pedal`, `Overdrive`, `Amp`, `Cabinet` | 4.1-4.5 |
| Erosion, Redux | `Erosion2` (legacy `Erosion`), `Redux2` (legacy `Redux`) | 4.6-4.7 |
| Vinyl Distortion, Dynamic Tube | `Vinyl`, `Tube` | 4.8-4.9 |
| Chorus-Ensemble, Phaser-Flanger, Auto Pan-Tremolo | `Chorus2` (legacy `Chorus`), `PhaserNew` (legacy `Phaser`, `Flanger`), `AutoPan2` (legacy `AutoPan`) | 5.1-5.3 |
| Echo, Delay, Grain Delay, Filter Delay, Beat Repeat | `Echo`, `Delay`, `GrainDelay`, `FilterDelay`, `BeatRepeat` | 5.4-5.8 |
| Hybrid Reverb, Reverb, Spectral Time, Shifter, Vocoder | `Hybrid`, `Reverb`, `Spectral`, `Shifter`, `Vocoder` | 5.9-5.13 |
| Wavetable, Drift, Operator, Analog | `InstrumentVector`, `Drift`, `Operator`, `UltraAnalog` | 6.1-6.4 |
| Meld, Simpler, Sampler, Drum Sampler | `InstrumentMeld`; `OriginalSimpler`; `MultiSampler`; see `get_devices` | 6.5-6.7 |
| Drum, Instrument, Audio Effect, MIDI Effect Rack | `DrumGroupDevice`, `InstrumentGroupDevice`, `AudioEffectGroupDevice`, `MidiEffectGroupDevice` | 7 |

## 1. Setting parameters: names, units, display strings, raw values

The tool, as described in [docs/TOOLS.md](../TOOLS.md): `set_device_parameters(track, device, values)` takes `{parameter name or index: value}`, applies the entries in order, returns each new value with its display string, lists failures in `errors` without stopping the rest, and raises only if nothing was set. Device paths alternate device and chain segments (`"Drum Rack/Kick/Simpler"`, `"0/0/1"`); see [section 7](#7-racks-macros-chain-selector-addressing).

### 1.1 How a parameter name is resolved

- Case-insensitive exact match on the parameter's `name`, then on its `original_name`, then a **unique** substring. Two matches are an error, never a guess. An integer-like reference selects by index.
- Substring matching is a trap on devices with many similar names. EQ Eight has `1 Frequency A` through `8 Frequency B`; always send the full name. Echo's mix parameter is `Dry Wet` (no slash) and the device also has `Clip Dry`, so `"Dry"` is ambiguous and `"Dry/Wet"` finds nothing. Grain Delay calls it `DryWet`; Corpus, Spectral Resonator and Spectral Time say `Dry Wet` like Echo. Hybrid Reverb, Chorus-Ensemble, Auto Filter, Roar and most others use `Dry/Wet`.
- Some parameters rename themselves with the device state. Utility's `Stereo Width` becomes `Mid/Side Balance` when the width control is switched to Mid/Side in the UI. Spectral Time has two switches, `Device On` and its own `On`. Max for Live pack instruments use the names from their own patch, and some repeat or pad them: Poli and Bass repeat `Attack`, `Decay`, `Sustain` and `Release` (Poli also `Rate`, `LFO`, `Filter Env`, `Amp Env`, `Key`, `Velocity` and `Aftertouch`), Corpus has two `Width` parameters (the filter width and the output width), and Poli's `Saw  Tune` has two spaces. A repeated name is an error ("use an index") and inner spacing counts in a match, so for those read the index from `get_device`.
- Two devices with the same name on one track (two Utility instances) make a name path ambiguous: use the index path from `get_devices`.

### 1.2 What a value can be

| You pass | What the server does | Examples | Gotcha |
| --- | --- | --- | --- |
| JSON number | raw value; outside `min..max` it is an error | `{"Macro 1": 64}`, Glue Compressor `{"Threshold": -18}` | the raw scale is device specific (table 1.3); `0.5` on a 0..1 parameter is not "50 %" of the display |
| string with a unit | parsed to a display number (kHz and s are converted to Hz and ms), written through `display_value`, read back, and found by bisection if it did not land | `"800 Hz"`, `"1.2 kHz"`, `"-6 dB"`, `"30 %"`, `"250 ms"`, `"2.5 s"`, `"25L"` | out-of-range values clamp to the nearest end without an error (1.4); a string without a unit, such as `"0.25"`, is still a display number |
| string on a chooser or switch (quantized parameter) | case-insensitive exact match against the item names | `"Analog Clip"`, `"High Pass 48dB"`, `"On"`, `"Medium"` | copy the strings from `get_device` `items` (the stepped Glue Compressor `Attack`, `Release` and `Ratio` show no items in the dump: send their raw step as a number; where items are shown, `".1"` is not `"0.1"`). A number sent to a chooser is a raw index, not the label: Delay `L 16th` has the labels 1, 2, 3, 4, 5, 6, 8, 16 for raw 0..7, so a `3` selects the label "4" |
| `true` / `false` | maximum / minimum | `{"Soft Clip On": true}` | switches only |
| `"-inf dB"` | goes to the minimum | `{"Output": "-inf dB"}` | not every parameter reaches minus infinity |

### 1.3 The raw scale is not one thing

| Family | Examples [12.4.6] | What to do |
| --- | --- | --- |
| 0..1 normalised, curved display | Compressor `Threshold`, `Ratio`, `Attack`, `Release`; Limiter `Input Gain`, `Ceiling`, `Release`; EQ Eight `n Frequency A`, `n Q A`; Saturator `Drive`; most Wavetable, Drift, Echo, Reverb, Hybrid parameters | never derive a raw value from a display number; pass display strings |
| raw is the real unit | Glue Compressor `Threshold` (-40..0 dB), `Range` (0..70 dB), `Output` (0..20 dB); Compressor `Output` (-36..36 dB), `Knee` (0..18 dB), `S/C EQ Gain` (-15..15 dB); EQ Eight `n Gain A` (-15..15 dB), `Output` (-12..12 dB); Pedal `Output` (-20..20 dB); Simpler `Volume` (-36..36 dB), `Transpose` (-48..48 st) | numbers or strings both work |
| integer steps with a label | Echo `L Synced` (-6..0), `L 16th` (1..16); Auto Filter `LFO Rate` (0..21), `LFO 16th` (1..64); Roar `FB Note` (12..84); Redux `Bit Depth` (1..16); Operator `Algorithm` | send the integer, read the display, adjust; never send fractions |
| rack knobs | `Macro 1..16`, `Chain Selector` | raw 0..127. A macro mapped to a single parameter takes that parameter's name and shows its unit (`Filter Cutoff` reads "3.26 kHz", `Reverb` reads "31 %") but its raw range is still 0..127; a macro mapped to several parameters shows plain 0..127. Send a display string and check the echo, or send a raw number |
| Max for Live instruments | Poli / Dark Throne: `LPF` 20..21000 (Hz), `Volume` -70..10 (dB), `Res` 0..100 | real units, different per device; read `min`/`max` |
| legacy devices | `Auto Filter Legacy`: `Frequency` raw 20..135 (not Hz), `Resonance` 0..1.25, `Drive` 0..24 | use display strings, or replace the device with the Live 12 version |

### 1.4 Display quirks that bite

- **Silent clamping.** A string that parses to a number outside the display range is not rejected; the bisection fallback lands on the end of the range. Drum Buss `Transients` displays `-1..1` as a plain fraction ("0.25", no percent sign), so `"25 %"` parses to 25, overshoots the range, lands on the maximum, and the echo reads `1.00`. The correct call is `"0.25"`. Always compare the echoed `display`.
- **Unitless displays.** A number with a blank unit means the display scale is the number itself: Reverb `Input Width`, `ER Spin Amount`, `ER Shape`, `HiShelf Gain`, `Chorus Amount`, `Room Size`, `Stereo Image` (degrees, no symbol); Hybrid `DH Shape`, `Pr Sixth`; Roar `Shaper n Bias`, `Flt n Res`; Echo `HP Res`; Drift `LP Res`, `Osc 1 Shape`. Send `"0.4"` for 0.40 (a string, so it is a display value, not a raw one).
- **Fractions and note values.** `"1/8"`, `"1/4"` and `"1/16"` all parse to the number 1 (and `"3/16"` to 3), which defeats the read-back check (a fix is pending in a separate task; until it lands, treat this as true). For non-quantized beat divisions (Echo `L Synced`, Auto Filter `LFO Rate`, Auto Pan `Rate`, Roar `FB Synced`) send the raw integer step and read the label back; step through the range once to learn the mapping. Quantized lists with labels (Delay `L 16th`, Chorus-Ensemble `Delay Taps`) take the label as a string.
- **Time units.** Strings in `s` or `ms` both work (`"1.2 s"` equals `"1200 ms"`), and frequencies accept `kHz`. Pan reads `"25L"`, `"C"`, `"50R"`.
- **Same name, different meaning by state.** LFO `Rate` shows Hz, seconds, a note value or sixteenths depending on its Time Mode; Echo `L Time` is only audible while `L Sync` is Off. Set the mode first.
- **Disabled parameters raise an error** ("macro-mapped or controlled by Max"). A parameter mapped to a rack macro is disabled; move the macro instead. Some parameters are inactive by design and Live may report them as disabled (Limiter `Release` while `Auto` is On, Limiter `Threshold` and `Output` while `Maximize On` is Off): set the controlling switch first.

### 1.5 Things that are not parameters

- **Properties** are set with `set_device(track, device, properties={...})`. `get_device` lists them with their options. Useful ones from the Live Object Model: EQ Eight `global_mode` (the option strings are the API enum names `stereo`, `left_right`, `mid_side`; "M/S" matches none of them), `edit_mode` (`a`, `b`), `oversample`; Roar `routing_mode_index` (its options are the entries of `routing_mode_list`: Single, Serial, Parallel, Multi Band, Mid Side, Feedback, Delay) and `env_listen`; Hybrid Reverb impulse-response properties (`ir_category_index`, `ir_file_index`, `ir_attack_time`, `ir_decay_time`, `ir_size_factor`, `ir_time_shaping_on`); Wavetable `unison_mode` (API strings `none`, `classic`, `slow_shimmer` = the UI's Shimmer, `fast_shimmer` = Noise, `phase_sync`, `position_spread`, `random_note`; a plain "Shimmer" is ambiguous and fails), `unison_voice_count`, `poly_voices`, `filter_routing`, `oscillator_n_effect_mode` (`none`, `frequency_modulation` = FM, `sync_and_pulse_width` = Classic, `warp_and_fold` = Modern), wavetable category and index; Drift `voice_mode_index`, `voice_count_index`; Meld `selected_engine`, `unison_voices`, `mono_poly`, `poly_voices`; Shifter `pitch_mode_index`; Spectral Resonator `pitch_mode`, `mod_mode`, `mono_poly`, `polyphony`; Simpler `playback_mode`, `sample.*`. Sources: [Live Object Model](https://docs.cycling74.com/apiref/lom/), [docs/reference/lom_docs_12.4.5.md](../reference/lom_docs_12.4.5.md) and the enum names in [docs/reference/live_api_12.4.6.md](../reference/live_api_12.4.6.md). Exact property keys and option names are listed by `get_device`; do not guess them. List-type properties carry an `_index` suffix in the API (`routing_mode_index`, `voice_mode_index`, `voice_count_index`, `ir_category_index`, `ir_file_index`, `pitch_mode_index`) next to a `_list` of their options; `set_device` also accepts the name without the suffix (it falls back to `<name>_index`), so `voice_mode` and `routing_mode` work, but the real key is the one `get_device` prints.
- **Sidechain routing.** Only Compressor exposes its external source to the API. `set_sidechain(track, source, channel, threshold_db, ratio, attack_ms, release_ms)` drives it. Glue Compressor, Gate, Multiband Dynamics, Auto Filter, Roar, Shifter, Corpus and Spectral Resonator have sidechain inputs that a human must route in the UI.
- **Context-menu options** (Hi-Quality on Saturator, Pedal, Dynamic Tube, Delay, Wavetable and Drift; Oversampling on Glue Compressor; Equal-Loudness on Delay and Echo; Mono Sidechain; Zero Dry Signal Latency) are not in the parameter list. Exceptions: EQ Eight's oversampling is the property `oversample`, and Saturator's Pre-DC Filter appears as the parameter `Pre Dc Filter`. For the rest, ask the producer, or leave the default.
- **Max for Live devices and packs** (Poli, Bass, Granulator III, PitchLoop89, DS drum synths, LFO, Envelope Follower, Shaper) cannot be created by name with the native insert; `add_device` falls back to the browser. `Drum Sampler` inserts as `DrumSampler` (handled for you). See [docs/spikes.md](../spikes.md).
- **Live's device A/B** (`set_device(compare_b=True)`) swaps the whole device state: park the old settings in A, edit B, flip back to restore.

### 1.6 Manual label to API name (where they differ)

The manual and the UI use short labels; the API uses the names below (12.4.6). When a card says "Gain" or "Makeup" and `get_device` shows something else, trust `get_device`.

| Device | Manual or UI label | API name |
| --- | --- | --- |
| Compressor | Out; Lin/Log; Peak/RMS/Expand; Lookahead; Auto | `Output`; `Env Mode`; `Model`; `LookAhead`; `Auto Release On/Off` |
| Glue Compressor | Makeup; Soft Clip | `Output`; `Peak Clip In` |
| Limiter | Gain; Maximize | `Input Gain`; `Maximize On` (Threshold and Output apply while it is on) |
| Utility | Gain; Width; Phase L/R; DC | `Output`; `Stereo Width`; `Left Inv`, `Right Inv`; `DC Filter` |
| Saturator | Curve Type; Amt Lo; Amt Hi; Frequency; Width | `Type`; `Color Amt Low`; `Color Amt Hi`; `Color Freq`; `Color Width` |
| Drum Buss | Comp; Damp; Boom, Freq, Decay; Output Gain | `Compressor On`; `Damping Freq`; `Boom Amt`, `Boom Freq`, `Boom Decay`; `Output` |
| Auto Filter | Freq; Res; Filter Circuit; Clip; Amt (LFO) | `Frequency`; `Resonance`; `Circuit`; `Soft Clip On`; `LFO Amount` |
| Pedal | Gain | `Drive` |
| Roar | Tone Amount; Compression Amount; Output Gain | `Tone Amt`; `Comp Amt`; `Output` |
| Hybrid Reverb | Send; Stereo; Algorithm; Mod | `Send Gain`; `Width`; `Algo Type`; `Modulation` |
| Reverb | Decay; Size; Stereo; Reflect, Diffuse | `Decay Time`; `Room Size`; `Stereo Image`; `Reflect Level`, `Diffuse Level` |
| Echo | Dry/Wet; Input; Stereo; Gate Threshold | `Dry Wet`; `Input Gain`; `Stereo Width`; `Gate Thr` |
| Chorus-Ensemble | Taps; Gain | `Delay Taps`; `Output` |
| EQ Eight | Gain (global) | `Output` |
| Wavetable | Semi; Wave Position | `Osc n Transp`; `Osc n Pos` |
| Multiband Dynamics | Master Output; Output Gain | `Output`; per band `Output Gain (Low)`, `(Mid)`, `(High)` |
| Channel EQ | Gain | `Output` |
| Amp | Gain | `Input Gain` |
| Phaser-Flanger | Output Gain; FB Inv; Flange Time | `Output`; `FB Invert`; `Flanger Time` |
| Spectral Resonator | Input Send Gain; HF/LF Damp; Pch. Mod; Uni. Amt | `Send Gain`; `High Damp`, `Low Damp`; `Pitch Mod`; `Unison Amount` |
| Spectral Time | Delay Dly. Unit; Delay Time Seconds, Divisions, Sixteenths | `Delay Mode`; `Delay Time`, `Delay Synced`, `Delay 16th` |
| Vocoder | Output Level; Filter Bandwidth | `Output`; `Filter Width` |

The last seven rows are renames against the Live 12.0 Remote Script tables, which are where those cards' names used to come from.

### 1.7 A safe edit loop

1. `get_device(track, device)`: names, `items`, current display strings, `is_enabled`. Add `detail=True` when you need defaults.
2. Write down the single intended change and the expected measurement (for example "bass stem crest factor drops about 2 dB, nothing else moves").
3. `set_device_parameters`: type or mode first (`Mode`, `Filter Type`, `Routing`), amounts second, level compensation last.
4. Read the echoed `display` for every key. Fix mismatches before anything else.
5. Bounce or capture, then `analyze_audio` and compare against the previous take at matched loudness ([11-listening-without-ears.md](11-listening-without-ears.md)). Hand the producer a labelled A/B.
6. Keep or restore. Take snapshots from the listening loop hold every device parameter and can be restored, so reverting is cheap.

## 2. Dynamics

> **For an agent (dynamics).** Gain reduction is not readable through the API. Estimate it by bouncing with the device on and off and comparing `analyze_audio` crest factor, loudness range and integrated LUFS: bus glue of 1-3 dB should cost about 1-3 dB of crest factor; limiting that drops crest factor by 6 dB or more, or flattens loudness range, is squash. Set `Output`/`Makeup` so the processed signal matches the bypassed one within 0.2 LU (0.3 LU at most) before anyone compares the two, because louder usually sounds better. Stop and ask before touching dynamics on a sound the producer already approved, and before any limiter other than the safety limiter on Main.

### 2.1 Compressor (`Compressor2`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#compressor)

**For.** General dynamics control, ducking, parallel compression, and (in Expand mode) restoring transients. It is the only device whose external sidechain source the API can route, so it is the kick-ducking tool.

**Flow.** Optional sidechain EQ, then the level detector (`Model` Peak or RMS, `Env Mode` Lin or Log), then threshold, ratio and knee, then attack and release smoothing, then `Makeup`/`Output`, then `Dry/Wet`. `LookAhead` delays the audio by 0, 1 or 10 ms so the gain change can start before the transient; Live compensates the latency.

**Parameters.** `Threshold` (dB), `Ratio` (shows "4.00 : 1"), `Attack` (ms), `Release` (ms), `Auto Release On/Off`, `Knee` (0..18 dB), `Model` (Peak, RMS, Expand), `Expansion Ratio`, `Env Mode` (Lin, Log), `LookAhead` (0 ms, 1 ms, 10 ms), `Makeup` (switch), `Output` (-36..36 dB), `Dry/Wet`. Sidechain: `S/C On`, `S/C Gain`, `S/C Mix`, `S/C Listen`, `S/C EQ On`, `S/C EQ Type`, `S/C EQ Freq`, `S/C EQ Q`, `S/C EQ Gain`. The source chooser is a property (`input_routing_type`, `input_routing_channel`), set by `set_sidechain` or `set_device(properties=...)`.

**What the manual says.** An attack of 10-50 ms lets the first part of a sound through and keeps dynamics; very short attacks take the life out and can buzz. Short releases pump. More than about 6 dB of gain reduction changes the sound for good, so keep it small on busy material. Peak reacts to short peaks (limiting tasks); RMS is slower and usually more musical. Expand mode raises what is above the threshold (a ratio of 1:2 turns each dB above the threshold into 2 dB), so it restores punch. The manual describes only this above-threshold (upward) behaviour; for downward expansion use Gate or the Below thresholds of Multiband Dynamics. Log mode releases faster after heavily compressed peaks and is usually less noticeable. Automatic makeup is off while an external sidechain is active. To duck from a mixed drum track, enable the sidechain EQ with the low-pass type, tune frequency and Q until only the kick remains, and use Listen to check ([manual: Compressor tips](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#compressor)).

**Start (convention unless linked).**

- *Ducking a bass or pad to the kick:* `set_sidechain("Bass", "Kick", channel="Post FX")`, then `Model` Peak, `Ratio` 6:1 or more, `Attack` 0.1-1 ms, `Release` 80-200 ms (a sixteenth to an eighth at the song tempo: 60000 / BPM / 4 up to / 2 ms), `Knee` 0-3 dB, `LookAhead` 1 ms, threshold set for 3-6 dB of reduction at the kick (see 8.1 for how to pick it). Check the result by measurement: bounce the ducked stem and compare its short-term loudness around the kick onsets with the same passage bypassed.
- *Level control on a synth or bass:* `Model` RMS, `Ratio` 2:1-3:1, `Attack` 10-30 ms, `Release` 100-300 ms or `Auto Release On/Off` On, `Knee` 6 dB, no more than 3-4 dB of reduction.
- *Parallel (New York) compression:* high ratio, 15-20 dB of reduction, mixed back under the dry path ([Sound On Sound](https://www.soundonsound.com/techniques/parallel-compression?page=2) suggests 20 dB as a start). In Live: `Ratio` 10:1 or more, low threshold, `Dry/Wet` 20-40 %.
- *Peak control:* `Ratio` high, `Attack` 0.01-1 ms, `Release` 50-100 ms. Prefer Limiter when the goal is a hard ceiling.

**Pitfalls.** The tap point matters: `Post Mixer` follows the source track's fader, so moving the kick fader changes the ducking depth; `Post FX` (default) and `Pre FX` do not. A freshly added Compressor has `S/C EQ On` On with a high-pass at 80 Hz on the key (Glue Compressor, Gate and Auto Filter start with their sidechain EQ Off at 200 Hz), which makes it less sensitive to a kick's sub; `set_sidechain` does not touch the sidechain EQ. A louder output is not a better compressor, so match loudness. `Output` is the makeup in 12.4.6 (not `Output Gain`). Do not leave the `Makeup` switch on and also raise `Output`: that compensates twice. `LookAhead` adds latency (Live compensates it); 1 ms is enough for most ducking, 10 ms gives a cleaner duck on fast material. See [04-drums-and-low-end.md](04-drums-and-low-end.md) for the kick-bass relationship.

### 2.2 Glue Compressor (`GlueCompressor`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#glue-compressor)

**For.** Bus compression: drum group, music group, Main. Analog-modelled with Cytomic, based on an 80s console bus compressor. Cytomic's plug-in version of the same design is a VCA feedback compressor whose diode-style detector attacks slower on small signals than on large ones ([Cytomic The Glue](https://cytomic.com/product/glue/)). Stepped controls make it fast to set and hard to ruin.

**Parameters.** `Threshold` (raw is dB, -40..0), `Ratio` (three steps, 2, 4 and 10, ascending from raw 0), `Attack` (seven steps, about 0.01 to 30 ms, ascending), `Release` (seven steps, about 0.1 to 1.2 s plus Auto, ascending; confirm the exact lists by reading the display of each step), `Range` (raw 0..70 dB, displayed as a positive number, "70.0 dB" by default; 0 disables compression), `Output` (makeup, 0..20 dB; called `Makeup` in 12.0), `Dry/Wet`, `Peak Clip In` (the Soft Clip switch), `S/C On`, `S/C Gain`, `S/C Mix`, `S/C EQ On/Type/Freq/Q/Gain`. Attack, release and ratio are stepped: the reference dump records no item list for them (raw ranges 0..6, 0..6 and 0..2 for `Attack`, `Release`, `Ratio`), so send the raw integer step as a number and read the display back; if `get_device` does list items, pass the item text exactly (earlier snapshots show `1`, `.1`, `.6` and `4`, and `".1"` is not `"0.1"`). There is no knee control; the knee sharpens as the ratio rises. Oversampling is a menu option.

**Manual details.** The `Range` figures from the manual were first recorded here with a minus sign; the API shows the knob as a positive number, so a negative string such as "-20 dB" clamps to 0 and switches compression off. Read in API terms, a `Range` of about 60 to 70 dB imitates the hardware and 15 to 40 dB works as an alternative to Dry/Wet. Auto release uses a slow base time plus a fast reaction to transients and suits gentle taming but can be too slow for sudden changes. Soft Clip caps the output at about -0.5 dB, distorts the signal when active, and is not a transparent limiter ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#glue-compressor)).

**Start (convention; the `Ratio`, `Attack` and `Release` values below are display values, so send the matching raw step and check the display).**

- *Main or music bus:* `Ratio` 2, `Attack` 10 ms (30 ms keeps more punch, 1-3 ms tightens), `Release` Auto or 0.2-0.4, `Range` at default, threshold for 1-2 dB of reduction on the loudest passages, `Output` to match the bypassed level.
- *Drum bus:* `Ratio` 4, `Attack` 3-10 ms, `Release` 0.2 or Auto, 2-4 dB of reduction.
- *Gentler than the ratio allows:* lower `Range` to 15-25 dB (positive in the API, see above), or `Dry/Wet` 50 %.

**Pitfalls.** Do not put it on every stem to "glue" them; glue is a bus job. `Peak Clip In` colours and flattens peaks; leave it off unless the colour is wanted. Do not follow it with a gain boost that the limiter then has to catch. Its sidechain input is not routable through the API (human task).

### 2.3 Drum Buss (`DrumBuss`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#drum-buss)

**For.** Weight and cohesion on a drum group: optional fixed compressor, three distortion types, a mid-high enhancer, a transient control and a tuned low-end resonator.

**Parameters.** `Trim`, `Compressor On`, `Drive`, `Drive Type` (Soft = waveshaping, Medium = limiting, Hard = clipping with bass boost), `Crunch` (sine-shaped distortion on mid-highs), `Damping Freq` (low-pass after the distortion), `Transients` (-1..1, displayed as a fraction; works above about 100 Hz; positive adds attack and sustain, negative adds attack and shortens sustain), `Boom Freq`, `Boom Amt`, `Boom Decay`, `Boom Audition` (solo the low-end resonator), `Output`, `Dry/Wet`. The manual places `Trim` and the compressor before the distortion.

**Start (convention).** Group of kick, snare, hats and percussion: `Compressor On` On, `Drive Type` Medium, `Drive` 15-30 %, `Crunch` 10-25 %, `Damping Freq` 9-12 kHz (lower only if the top sounds fizzy), `Transients` "0.10" to "0.25" for punch or slightly negative for tight, `Boom Freq` tuned to the kick fundamental (about 45-60 Hz; read the peak third-octave band of the kick stem, then use `Boom Audition`), `Boom Amt` 15-35 %, `Boom Decay` 40-60 %, `Output` -1 to -3 dB, `Dry/Wet` 100 % (50-70 % for a parallel feel).

**Pitfalls.** Boom adds real sub energy that competes with the bass: check the low third-octave bands and mono-sum loss after every change. `Transients` is unitless in the API (see 1.4). The compressor and distortion raise the level, so compensate with `Output`/`Trim` before judging. One Drum Buss on the group, not one per drum.

### 2.4 Multiband Dynamics (`MultibandDynamics`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#multiband-dynamics)

**For.** Three independent bands, each with an upper (Above) and lower (Below) threshold, so one instance can do downward and upward compression and expansion at once. Mastering-oriented, also the de-esser and the "OTT-like" upward-compression tool.

**Parameters.** Global: `Output` (-24..24 dB; `Master Output` in the 12.0 tables), `Amount`, `Time Scaling`, `Soft Knee On/Off`, `Peak/RMS Mode` (items RMS, Peak), `Low-Mid Crossover`, `Mid-High Crossover`, `S/C On`, `S/C Mix`, `S/C Gain`. Per band, with the band in brackets as part of the name (Low, Mid or High, for example `Band Activator (Mid)`): `Band Activator`, `Input Gain` (+/-24 dB), `Above Threshold` and `Below Threshold` (-80..0 dB), `Above Ratio` (raw -1..1, displayed like "1 : 1.00"), `Below Ratio` (raw -3..1), `Attack Time`, `Release Time`, `Output Gain` (+/-24 dB). `Amount` at 0 % makes every ratio 1. Read the echoed display of every ratio: its format is not the usual "4:1".

**Start (convention unless linked).** The manual's de-essing recipe: only the upper band, crossover around 5 kHz, subtle reduction, fast attack and release, soloing the band while tuning. Tame low-mid build-up: Mid band `Above Ratio` 1.5-2:1 for 2-3 dB. Upward effects: keep `Amount` at 20-40 % and watch noise.

**Pitfalls.** Upward compression and upward expansion raise quiet detail, reverb tails and noise; the manual warns that upward expansion can make transients very loud and that a limiter after it can undo the gain. Band output gains change the spectral balance; verify third-octave bands before and after. Crossovers add phase shift, so keep the number of active bands low.

### 2.5 Gate (`Gate`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#gate)

**For.** Removing noise between hits, shortening tails, and rhythmic gating of a held sound with an external trigger (a pad opened by a drum loop is the manual's example). Flip reverses the logic.

**Parameters.** `Threshold`, `Return` (hysteresis, 0..24 dB), `FlipMode` (Normal, Flip), `LookAhead` (items 0 ms, 1.5 ms, 10 ms; 1.5 ms is the default), `Attack`, `Hold`, `Release`, `Floor` (raw -75..0 dB; check that the bottom reads -inf), `S/C On`, `S/C Gain`, `S/C Mix`, `S/C Listen`, `S/C EQ On/Type/Freq/Q/Gain`.

**Start (convention).** `Return` 3-6 dB to stop chatter, `Attack` 0.1-1 ms, `Hold` 10-50 ms, `Release` 30-150 ms, `Floor` -inf dB for a hard cut or -20 to -30 dB for a natural one, `LookAhead` 1.5 ms.

**Pitfalls.** Too-short attack clicks. Threshold above the quiet part of the hits chops decays. A sidechained gate needs UI routing; the API cannot set it. Do not gate sustained pads except as a deliberate rhythm effect.

### 2.6 Limiter (`Limiter`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#limiter)

**For.** A mastering-grade peak limiter whose job is to stop the output exceeding a ceiling. Use it as the last device on Main. It is not a stem processor and not a loudness knob for individual tracks.

**Parameters.** `Input Gain` (dB), `Ceiling` (dB), `Release` (ms), `Auto` (auto-release; disables `Release`), `Link` (percent of gain reduction shared between channels), `M/S Link`, `Lookahead` (1.5 ms, 3 ms, 6 ms), `Routing` (L/R or M/S), `Mode` (Standard, Soft Clip, True Peak), `Maximize On`, `Threshold` and `Output` (used while Maximize is on). With Maximize on, the `Ceiling` control becomes `Threshold` and `Input Gain` becomes `Output` in the UI; lowering the threshold raises the level by the inverse amount. Set `Maximize On` before `Threshold` and `Output`. The ranges in the Max DSP object are gain -24..24 dB, ceiling -24..0 dB, release up to 3 s ([abl.device.limiter~](https://docs.cycling74.com/reference/abl.device.limiter~)).

**Manual details.** Shorter lookahead allows more gain reduction but can distort, especially on bass; longer lookahead catches fast peaks and adds latency. Soft Clip rounds peaks near the ceiling and flashes an LED when it clips; True Peak prevents inter-sample peaks; M/S routing keeps the stereo image but adds latency. Any device after the limiter can add gain, so keep it last and keep the Main fader at or below 0 dB.

**Start (convention).** Safety limiter on Main: `Mode` True Peak, `Ceiling` -1.0 dB (see [07-mastering-and-loudness.md](07-mastering-and-loudness.md) for the delivery target), `Lookahead` 3 ms (6 ms for bass-heavy material), `Auto` On or `Release` 50-150 ms, `Link` 100 %, `Input Gain` set so the reduction stays around 1-3 dB. Example: `set_device_parameters("master", "Limiter", {"Mode": "True Peak", "Ceiling": "-1.0 dB", "Lookahead": "3 ms", "Auto": "On", "Input Gain": "0 dB"})`.

**Pitfalls.** The failure of 2026-10-08 was a True Peak limiter on every stem with +12 dB of input gain into -14 dB ceilings: the stem was pushed 12 dB into a ceiling 14 dB below full scale, up to 26 dB of reduction on a stem that peaks near 0 dBFS, and the pad's body and transients were destroyed. Keep stems unlimited and let the Main limiter and the delivery chain deal with peaks. If the target loudness needs much more than about 6 dB of reduction, the material is too peaky for that target: fix peaks upstream, lower the target, or ask ([05-gain-staging-and-metering.md](05-gain-staging-and-metering.md) and [07-mastering-and-loudness.md](07-mastering-and-loudness.md) for the arithmetic). Reading gain reduction is not possible; use crest factor and loudness range before and after.

### 2.7 Utility (`StereoGain`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#utility)

**For.** Gain, width, mono, bass-mono, balance, polarity and muting; the most useful small device in the set.

**Parameters.** `Output` (the gain knob: -inf to +35 dB in the manual; raw -1..1, so send dB strings), `Stereo Width` (0..200 %, displayed as percent; it becomes `Mid/Side Balance` when the UI is switched to Mid/Side), `Mono`, `Bass Mono`, `Bass Freq` (50-500 Hz), `Balance` (-1..1, "C", "25L"), `Left Inv`, `Right Inv`, `Channel Mode` (Left, Stereo, Right, Swap), `Mute`, `DC Filter`.

**Start (convention).**

- Bass mono on pads, leads and wide layers: `Bass Mono` On, `Bass Freq` "120 Hz" to "200 Hz" (the project's approved base pad used 120 Hz). Place it last in the chain, after chorus, reverb and any widener, or the low end widens again.
- Width: 100 % is neutral; 110-150 % widens sparingly; anything above 150 % on content below 300 Hz is risky. Prefer widening through unison or stereo spread in the synth.
- Level matching for A/B: put Utility first in a track's chain and set `Output` to bring the processed version to the bypassed loudness.
- Mono check: `Mono` On on Main, then `analyze_audio` for mono-sum loss (see [11-listening-without-ears.md](11-listening-without-ears.md)); remember to turn it off.

**Pitfalls.** Bass Mono is a crossover, so it changes phase near the corner frequency; set it as high as the sound needs and no higher. `Stereo Width` acts on the signal inside the device: widening before a reverb is different from widening after. Polarity flips (`Left Inv`, `Right Inv`) cancel in mono. Gain automation on Utility leaves the track fader free for balance ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#utility)).

## 3. EQ and filters

> **For an agent (EQ and filters).** You cannot see the curve, so verify every EQ move with third-octave balance from `analyze_audio` on a bounce taken before and after: the band you touched should move by about the amount you set (a 3 dB bell at Q 1 moves its centre band by 2-3 dB), the others by well under 1 dB. Keep each move to 3 dB or less, work on one track at a time, and match loudness with `Output` before comparing. Filters on pads change the identity of the sound; ask before high-passing anything whose character is a low root.

### 3.1 EQ Eight (`Eq8`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#eq-eight)

**For.** Corrective and tonal EQ with up to eight filters per channel; Mid/Side and Left/Right modes for width work.

**Flow.** Eight bands run in series. In Stereo mode the A set processes both channels. In L/R mode band set A is the left channel and B the right; in M/S mode A is mid and B is side (inferred from the [Live Object Model](https://docs.cycling74.com/apiref/lom/eq8device/) `edit_mode` table, where 0 is L or M and 1 is R or S; confirm with `get_device` after switching). `edit_mode` selects which set the UI edits. Switching the mode is a property, not a parameter.

**Parameters.** `Output` (-12..12 dB), `Scale` (display "100 %"; multiplies every gain, 0 % flattens the curve), `Adaptive Q`. For each band n = 1..8: `n Filter On A`, `n Filter Type A`, `n Frequency A`, `n Gain A` (-15..15 dB), `n Q A`, and the same with suffix `B`. Filter types: `High Pass 48dB`, `High Pass 12dB`, `Low Shelf`, `Bell`, `Notch`, `High Shelf`, `Low Pass 12dB`, `Low Pass 48dB`. Gain works on the shelves and the bell only. There is no 24 dB cut: the cuts are 12 or 48 dB per octave. Properties: `global_mode` (API strings `stereo`, `left_right`, `mid_side`), `edit_mode` (`a`, `b`), `oversample` (processes at twice the sample rate for smoother behaviour near the top of the spectrum, at a small CPU cost). With `Adaptive Q` on, Q rises as the boost or cut grows, which keeps the level more consistent, like classic analog EQs.

**Start (convention).**

| Job | Settings | Note |
| --- | --- | --- |
| Remove sub-rumble | band 1 `High Pass 12dB` at 20-30 Hz | `High Pass 48dB` if the source has real rumble |
| Non-bass layers, hats, percussion | band 1 `High Pass 12dB` at 100-300 Hz (hats up to 300-500 Hz) | do **not** do this to a pad whose character is a low root |
| Mud | band 3 `Bell` at 200-400 Hz, -1 to -3 dB, Q 0.7-1.2 | measure first; cut only if the third-octave bands are heavy there |
| Resonance or ring | `Bell` Q 4-8, -2 to -4 dB at the offending band | find it from the third-octave peak, then sweep one step each side |
| Tilt / air | `High Shelf` at 8-12 kHz, +1 to +2 dB; `Low Shelf` at 100-200 Hz, +/-1 to 2 dB | small moves, then loudness-match |
| Keep the low end mono without Utility | `global_mode` M/S, side set (B) band 1 `High Pass 12dB` at 120-200 Hz | the mid set (A) stays untouched |

Example: `set_device_parameters("Bass", "EQ Eight", {"1 Filter Type A": "High Pass 12dB", "1 Frequency A": "28 Hz", "1 Filter On A": "On"})`.

**Pitfalls.** Always send full parameter names (see 1.1). Every boost raises the level and every cut lowers it, so the ear prefers whichever is louder: set `Output` to compensate. Cuts are not free in a mix: removing 2 dB at 250 Hz from every track changes what masks what, and the producer called broad cuts on every track at once "garbage". Change one track, measure, ask. `Scale` is a global lever; do not use it as a shortcut. Filters introduce phase shift; a steep high-pass on a kick or bass shifts its phase relationship with the other low-end part ([04-drums-and-low-end.md](04-drums-and-low-end.md)).

### 3.2 EQ Three (`FilterEQ3`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#eq-three)

**For.** DJ-style three-band isolator: low, mid and high bands that can each be killed. Not for subtle mixing.

**Parameters.** `GainLo`, `GainMid`, `GainHi` (from minus infinity to +6 dB), `FreqLo`, `FreqHi` (crossovers; the snapshots read 250 Hz and 2.50 kHz), `LowOn`, `MidOn`, `HighOn` (band kill switches), `Slope` (24 or 48 dB). The filters are tuned to sound like an analog filter cascade, and 48 dB shows slight colouring even at 0 dB.

**Use.** Make a "no-lows" copy of a loop for a build-up, strip the highs for a transition, or duck one band by automating a kill switch. Pass `Slope` as the item "24" or "48".

### 3.3 Channel EQ (`ChannelEq`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#channel-eq)

**For.** A fast console-style tilt EQ.

**Parameters.** `Highpass On` (80 Hz), `Low Gain` (shelf at 100 Hz, +/-15 dB, adaptive), `Mid Gain` (+/-12 dB) with `Mid Freq` (120 Hz to 7.5 kHz), `High Gain` (+/-15 dB), `Output` (the output gain; `Gain` in the 12.0 tables).

**Pitfalls.** Turning `High Gain` below 0 dB also lowers a built-in low-pass from 20 kHz toward 8 kHz at -15 dB, so a "small high cut" darkens more than a shelf would. The manual suggests using it after a reverb to shape the tail, or on Drum Rack pads, and adding Saturator after it for desk-like nonlinearity.

### 3.4 Auto Filter (`AutoFilter2`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#auto-filter)

**For.** The Live 12.2 rebuild ([release notes](https://www.ableton.com/en/release-notes/live-12/)): ten filter types, four analog-style circuits, a stereo LFO, an envelope follower with sidechain input, drive, output level and dry/wet. Use it for static tone shaping, slow movement and filter-based transitions.

**Parameters.**

- Filter: `Filter Type` (Low-pass, High-pass, Band-pass, Notch, Morph, DJ, Comb, Resampling, Notch+LP, Vowel), `Frequency`, `Resonance`, `Filter Morph` (for Morph, Comb, Notch+LP, Vowel), `Filter Slope` (items `12dB` or `24dB` for low-pass, high-pass, band-pass, notch), `Morph Slope` (items `6dB`, `12dB`, `24dB`, `48dB`), `Circuit` (SVF clean, DFM feedback-distortion, MS2 Sallen-Key with soft clipping, PRD ladder without resonance limiting), `Drive`, `Control` (DJ filter replaces `Frequency`), `Pitch` and `Formant` (Vowel replaces `Frequency`/`Resonance`).
- LFO: `LFO Amount`, `LFO Wave` (Sine, Triangle, Saw, Square, Ramp Up, Ramp Down, Wander, `S & H` with spaces), `LFO T Mode` (Rate, Time, Synced, Triplet, Dotted, Sixteenth), `LFO Freq`, `LFO Time`, `LFO Rate` (note-value step), `LFO 16th`, `LFO Phase`, `LFO Offset` (tempo-synced modes only), `LFO S Mode` (Phase or Spin), `LFO Spin`, `LFO Morph`, `LFO Smoothing`, `LFO Q Mode` (None, Steps, S&H), `LFO Steps`, `LFO S&H`.
- Envelope: `Env Amount` (signed), `Env Attack`, `Env Hold On`, `Env Release`, `Env S&H On`, `Env S&H`.
- Global: `Output`, `Soft Clip On` (the Clip switch), `Dry/Wet`. Sidechain: `S/C On`, `S/C Gain`, `S/C Mix`, `S/C EQ On/Type/Freq/Q/Gain` (the external source is a UI choice).

Circuits only act on Low-pass, High-pass, Band-pass, Notch and Morph. The DJ type goes from low-pass at negative `Control` values to high-pass at positive ones, with extra resonance near the extremes.

**Start (convention).**

- *Smooth top roll-off on a pad:* `Filter Type` Low-pass, `Filter Slope` 12dB (24dB for a steeper roll), `Circuit` SVF, `Frequency` "2 kHz" to "3 kHz", `Resonance` 0-10 %, `Drive` 0 %. The references the producer likes roll off smoothly above about 2 kHz with little noise.
- *Slow stereo movement:* `LFO Amount` 8-25 %, `LFO Wave` Sine, `LFO T Mode` Rate with `LFO Freq` 0.05-0.2 Hz (or Time with `LFO Time` 5-20 s, or a synced division of two to four bars), `LFO S Mode` Phase with `LFO Phase` 90-180 deg.
- *Transition sweep:* `Filter Type` DJ, automate `Control` with `write_automation`.

Example: `set_device_parameters("Pad", "Auto Filter", {"Filter Type": "Low-pass", "Circuit": "SVF", "Filter Slope": "12dB", "Frequency": "2.5 kHz", "Resonance": "8 %", "Drive": "0 %"})`.

**Pitfalls.** Resonance above about 30 % on a low-pass sweep creates level spikes; use `Output` and `Soft Clip On`. `Drive` is distortion: on chords it creates intermodulation (see 4.1), so keep it at 0 for clean material. `Auto Filter Legacy` has different names and a raw frequency of 20..135; do not mix them up. Loading Core Library presets may bring the legacy device.

### 3.5 Spectral Resonator (`Transmute`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#spectral-resonator)

**For.** Imposes tuned resonant partials on any input: tonal washes on pads, pitched drums, vocoder-like effects, reverb-like drones.

**Parameters.** `Freq. Hz` or `Note` (the internal pitch, in Hertz or as a note), `Transpose` (-48..48 st, MIDI mode), `Transp Scale` (scale degrees), `Glide`, `Decay`, `Stretch` (spacing of the partials; 100 % gives odd harmonics only), `Shift` (spectrum of the input, in semitones), `Quantize`, `High Damp`, `Low Damp`, `Mod Rate`, `Pitch Mod`, `Harmonics`, `Unison` and `Unison Amount`, `Send Gain` (`Input Send Gain` in the 12.0 tables), `Dry Wet` (no slash), `Use Scale`. The pitch mode (Internal or MIDI), the Hz-or-note dial and the modulation mode (None, Chorus, Wander, Granular) are properties, not parameters: `pitch_mode`, `frequency_dial_mode`, `mod_mode`, `mono_poly`, `polyphony` (2, 4, 8, 16), `midi_gate`, `pitch_bend_range`. A MIDI sidechain source is a UI setting.

**Start (convention).** Return track, `Dry Wet` 100 %, send low (-18 to -12 dB). Internal mode with `Freq. Hz` (or `Note`) at the key's root, `Decay` 1-3 s, `Stretch` 0 %, `Unison` 2-3. The manual's reverb-like recipe: a low pitch, a high `Unison Amount`, Wander modulation with a small `Mod Rate` and `Pitch Mod`.

**Pitfalls.** Anything not in the key turns dissonant fast, and the resonances ring through the chord; with polyphony and unison the CPU cost climbs. The spectral devices add latency (Live compensates).

### 3.6 Corpus (`Corpus`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#corpus)

**For.** Physical-model resonator: turns drums, noise or pads into pitched, struck or blown bodies. Seven body types: Beam, Marimba, String, Membrane, Plate, Pipe, Tube.

**Parameters.** `Resonance Type`, `Resonator Quality` (Eco, Low, Med, High), `Tune` (Hz), `Transpose`, `Fine`, `Spread`, `Decay`, `Material`, `Brightness`, `Inharmonics`, `Radius`, `Opening`, `Ratio`, `Hit`, `Listening L`, `Listening R`, `Bleed`, `Gain`, `Dry Wet` (no slash), `Filter On/Off`, `Mid Freq`, the LFO controls (`LFO On/Off`, `LFO Shape`, `LFO Sync`, `LFO Rate`, `LFO Sync Rate`, `LFO Stereo Mode`, `Spin`, `Phase`, `Offset`, `LFO Amount`), `MIDI Frequency`, `MIDI Mode` (Last, Low), `PB Range` and the Note Off controls (`Note Off`, `Off Decay`). Two parameters are called `Width`: the first is the filter width (unitless, raw 0.5..9) and the second the output stereo width (%); address them by index. Pipe and Tube have no Material or Inharmonics.

**Start (convention).** On a return or as an insert at 30-60 % wet with `Bleed` 30-50 % to keep the source's attack. Tune it to the key with `Tune` (or a MIDI sidechain from the UI). Short `Decay` for percussion, long for drones.

**Pitfalls.** The resonator can peak hard; the Gain stage has a limiter, but lower the input first. Poorly tuned Corpus is a clear source of "wrong notes".

### 3.7 Resonators (`Resonator`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#resonators)

**For.** Five parallel tuned resonators behind a filter; plucked-string to vocoder-like tones, tuned in semitones, scale degrees or a tuning system.

**Parameters.** Global: `Filter On`, `Filter Type` (items `low pass`, `high pass`, `band pass`, `notch`: no hyphens, so "low-pass" does not match), `Frequency`, `Mode` (items `Mode A` realistic, `Mode B` for low notes), `Decay` (0..100), `Const` (equal decay for all pitches), `Color` (0..100), `Width`, `Dry/Wet`, `Output` (-15..15 dB), `Use Current Scale`. Resonator I: `I On`, `I Note` (a note, C2 by default), `I Note Scale Degrees`, `I Tune`, `I Gain`. Resonators II-V: `II On`, `II Pitch` (+/-24 semitones), `II Pitch Scale Degrees`, `II Tune`, `II Gain`, and so on to `V`.

**Start (convention).** A stable ring from open intervals: I at the key's root, II +12, III +19 (a fifth above the octave), IV +7, V 0, `Decay` 30-60, `Dry/Wet` 20-40 %. In the low register stick to octaves and fifths: thirds there sound muddy and out of tune (see the low-register rule in [docs/handoff/2026-10-08-nova-v2-paused.md](../handoff/2026-10-08-nova-v2-paused.md)).

## 4. Saturation and distortion

> **For an agent (saturation and distortion).** Distortion adds harmonics, raises level and, on chords, adds notes that were never played. Measure with `analyze_audio` before and after at matched loudness: third-octave energy above 2 kHz rising by more than 2-3 dB, a falling crest factor, or growing spectral flatness means more than "warmth". Keep a clean path (`Dry/Wet` 30-60 % unless the device is an amp-style effect), compensate `Output` for the extra gain, and never add distortion to a sound the producer has approved as clean without asking. On 2026-10-08 the producer's live reactions to the pad included "too distorted" (a Saturator followed by a squashing limiter); the sound he wants is big, heavy and clean.

### 4.1 Saturator (`Saturator`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#saturator)

**For.** Waveshaping: warmth, glue, controlled clipping, bass harmonics, wavefolding.

**Flow.** `Drive` gain, then the Color filters (an EQ curve applied before the shaper and applied inverted after it, so low frequencies can skip the saturation without losing their level), then the curve, then `Post Clip Mode`, then `Output`, then `Dry/Wet`.

**Parameters.** `Type` (Analog Clip, Soft Sine, Bass Shaper, Medium Curve, Hard Curve, Sinoid Fold, Digital Clip, Waveshaper), `Drive` (dB), `Threshold` (the Bass Shaper's threshold, 0 to -50 dB), `Color On`, `Color Amt Low`, `Color Freq`, `Color Width`, `Color Amt Hi` (the dump shows raw 0..1 and a default display of 0.0 %; whether the display goes negative is [verify]: set a negative string and read the echo), `Post Clip Mode` (No Clip, Soft Clip, Hard Clip), `Output` (dB), `Dry/Wet`, `Pre Dc Filter`, and for the Waveshaper type `WS Drive`, `WS Linearity`, `WS Curve`, `WS Damp`, `WS Period`, `WS Depth`. Curves per the manual: Analog Clip is linear below the clipping point and smooth around it; Digital Clip is a hard, immediate clip; Soft Sine, Medium and Hard are different saturation characters; Sinoid Fold is a wavefolder; Bass Shaper is like Analog Clip but with a smoother harmonic spectrum when low frequencies are driven hard, which is why it suits 808s and sub basses; low Bass Shaper threshold values clip softly, high values clip hard. With Soft Clip or Hard Clip as the post clip, the output never exceeds the `Output` level, which tames boosts from negative Color values.

**Start (convention).**

| Job | Type | Drive | Notes |
| --- | --- | --- | --- |
| Warmth on a drum group, bass or bus | Analog Clip or Soft Sine | 2-5 dB | `Output` -1 to -3 dB; `Dry/Wet` 30-60 % if you want parallel |
| Harmonics on a sub or 808 | Bass Shaper | 6-12 dB | `Threshold` low (-30 to -50 dB) for soft clipping; `Output` -3 to -6 dB |
| Shave a drum peak | Digital Clip | 1-4 dB | clipping, not saturation: it adds odd harmonics at once |
| Texture on a lead or percussion | Medium Curve or Hard Curve | 3-8 dB | high-frequency content aliases; consider Hi-Quality (menu) |
| Sound design | Sinoid Fold, Waveshaper | per taste | check `Output`, they get loud |

Example: `set_device_parameters("Perc", "Saturator", {"Type": "Analog Clip", "Drive": "4 dB", "Output": "-2 dB", "Dry/Wet": "50 %"})`.

**Why chords go out of tune.** A nonlinear curve generates harmonics of every note and also sum and difference tones between the notes, which is intermodulation distortion ([Wikipedia: Intermodulation](https://en.wikipedia.org/wiki/Intermodulation)). Those extra tones are not in the chord; the difference tones land low in the spectrum, where notes are dense, and a listener hears them as dissonance or a detuned instrument. This is what happened to the pad when whole chords were saturated. Remedies, strongest first: (1) saturate per voice inside the synth, using its filter or oscillator drive (voice filters act before the voices are summed, so notes do not intermodulate); (2) keep `Drive` at 3 dB or less on polyphonic material; (3) use Color with a negative `Color Amt Low` so the low chord tones skip the shaper; (4) run it in parallel at 20-30 %; (5) if distortion is wanted, distort only a root plus fifth (plus octave) layer and keep thirds and extensions in a clean layer, because fifths intermodulate onto harmonic positions while thirds make a messier set ([08-arrangement-and-composition.md](08-arrangement-and-composition.md), section 2.3); (6) do not use it at all on a sound whose brief is "clean".

**Pitfalls.** Drive without output compensation is the classic mistake: the muted `pad` track in the NOVA set still holds Analog Clip at 7 dB drive and -4 dB output, the stage the producer reacted to as "too distorted". `Soft Clip` post clip is a safety, not a limiter. Hi-Quality (the manual's name for its anti-aliasing mode; EQ Eight and Glue Compressor call theirs Oversampling) is a menu option, so aliasing on bright sources may need the producer's click.

### 4.2 Roar (`Roar`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#roar)

**For.** A multi-stage saturation and colouring device: up to three shaper-plus-filter stages in seven routings, a feedback loop with a compressor, modulation sources and external sidechain. Presets ship in the Core Library; start from one rather than from an init patch.

**Flow.** Input (`Drive`, `Tone Amt`/`Tone Freq`, optional `Color On` compensation that mirrors the tone filter after the shapers), then the routing (Single, Serial, Parallel, Multi Band, Mid Side, Feedback, Delay), then the stages, then `Comp Amt` (compression on the output and the feedback), then `Output` followed by a hard clip, then `Dry/Wet`. Routing is the property `routing_mode_index` (options in `routing_mode_list`). Each stage has `Stage n On`, `Shaper n On`, `Shaper n Type` (twelve curves: Soft Sine, Digital Clip, Bit Crusher, Diode Clipper, Tube Preamp, Half Wave Rectifier, Full Wave Rectifier, Polynomial, Fractal, Tri Fold, Noise Injection, Shards), `Shaper n Amt`, `Shaper n Bias`, `Shaper n Level`, and a filter `Flt n On`, `Flt n Type` (LP, BP, HP, Notch, Peak, Morph, Comb, Resampling, Dispersion), `Flt n Freq`, `Flt n Res`, `Flt n Morph`, `Flt n Peak`, `Flt n Pre On` (filter before the shaper). Feedback: `Feedback`, `FB Time Mode` (Time, Synced, Triplet, Dotted, Note), `FB Time`, `FB Synced`, `FB Note`, `FB Freq`, `FB Width`, `FB Invert`, `Fb Gate On`. Modulation: `LFO 1/2` (`Rate Mode`, `Rate`, `Synced Rate`, `16th`, `Wave`, `Morph`, `Smooth`), `Env` (`Gain`, `Attack`, `Hold On`, `Release`, `Thresh`, `Freq`, `Width`), `Noise` (`Rate Mode`, `Rate`, `Synced Rate`, `16th`, `Type`, `Smooth`), `Global Mod Amt`. (The full names carry the prefix, for example `LFO 1 Rate Mode`, `LFO 2 Wave`, `Env Thresh`, `Noise Type`; the bare words are not unique.) Global: `Comp Amt`, `Comp Hp On`, `Output`, `Dry/Wet`. Sidechain: `S/C On`, `S/C Gain`, `S/C Mix`.

**Start (convention).**

- *Gentle colour on a synth or bus:* Single, Shaper 1 Soft Sine or Tube Preamp, `Shaper 1 Amt` 10-25 %, `Output` -1 to -3 dB, `Dry/Wet` 30-60 %.
- *Grit on a drum group without losing the kick:* Multi Band, the low band's stage switched off, mid band Diode Clipper or Soft Sine at 15-30 %, high band Tube Preamp at 10-25 %. The three stages map to Low, Mid and High in this routing (probably `Stage 1` = Low; confirm after toggling by reading `get_device`), with crossovers `Low Mid X-Over` (about 200 Hz) and `Mid High X-Over` (about 2 kHz).
- *Keep the sub clean through heavy distortion:* positive `Tone Amt` (about 20-40 %) so the shapers see fewer lows, with `Color On` to put the low end back afterwards.
- *Pitched feedback ring:* Feedback routing, `FB Time Mode` Note, `FB Note` on a scale degree, `Feedback` 10-30 %, `Fb Gate On` On.

**Pitfalls.** The modulation matrix cells are not in the parameter list: modulation routing is a UI task. Bias at extremes silences the signal; feedback can run away; `Output` and `Drive` both change level. Large presets load heavy CPU. The envelope follower and the feedback pitch can take an external sidechain or MIDI source, again only by UI. See the [Ableton Roar article](https://www.ableton.com/en/blog/roar-meet-live-12s-new-processing-powerhouse/) for use cases (drums, pads, vocals, bass).

### 4.3 Pedal (`Pedal`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#pedal)

**For.** Guitar-pedal distortion that works on synths and drums: Overdrive (warm), Distortion (tight, aggressive), Fuzz (unstable, "broken amp").

**Parameters.** `Type`, `Drive` (the Gain control; 0 % still distorts), `Output` (-20..20 dB), `Bass` (peak at 100 Hz), `Mid` with `Mid Freq` (items `Low`, `Mid`, `High` for 500 Hz, 1 kHz, 2 kHz), `Treble` (shelf at 3.3 kHz), `Sub` (low shelf below 250 Hz), `Dry/Wet`. Bass, Mid and Treble run -100..100 %. The EQ is adaptive.

**Manual recipes.** Techno kick: a long-decay kick, Distortion type, `Sub` On, raise `Drive`; for more attack move `Mid Freq` right and raise `Mid`; for more thump raise `Bass`; cut `Treble` to remove air. Drum-group fizzle: Fuzz, `Drive` 50 %, `Sub` Off, Bass and Mid at -100 %, Treble 100 %, `Output` -20 dB, then raise `Dry/Wet` from 0 slowly. Sub warmer: Overdrive, `Sub` On, raise `Bass`, then raise `Drive` slowly ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#pedal)).

**Pitfalls.** Level jumps are large: set `Output` first. Feed it a compressed signal for a more even result. Not a clean-and-big tool; see [04-drums-and-low-end.md](04-drums-and-low-end.md) for kick distortion with sub protection.

### 4.4 Overdrive (`Overdrive`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#overdrive)

**For.** Band-limited distortion: a band-pass filter before the drive keeps the lows and the top clean. Dynamics are preserved even at high drive.

**Parameters.** `Filter Freq`, `Filter Width` (unitless, raw 0.5..9), `Drive`, `Tone`, `Preserve Dynamics`, `Dry/Wet`. `Drive`, `Tone` and `Dry/Wet` have a raw range of 0..100 (real percent), unlike most devices, so a raw `0.3` is 0.3 %; send strings. 0 % drive is not zero distortion.

**Start (convention).** Body for a bass or lead: `Filter Freq` 300 Hz-1.5 kHz, narrow `Filter Width`, `Drive` 20-40 %, `Tone` about 50 %, `Dry/Wet` 30-60 %. Because the band-pass sits before the distortion, a band that excludes the sub keeps the sub from ever reaching it: that is the point of using it on bass.

### 4.5 Amp and Cabinet (`Amp`, `Cabinet`) [12.4.6] · [Amp](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#amp), [Cabinet](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#cabinet)

**For.** Physical-modelled guitar amplifiers (developed with Softube) and speaker cabinets for grit on synths, drums and bass.

**Parameters.** Amp: `Amp Type` (Clean, Boost, Blues, Rock, Lead, Heavy, Bass), `Input Gain` (`Gain` in the 12.0 tables), `Bass`, `Middle`, `Treble`, `Presence`, `Volume`, `Dual Mono`, `Dry/Wet`. The tone knobs, `Input Gain` and `Volume` display on a unitless 0..10 scale (5.00 and 9.00 by default). Cabinet: `Cabinet Type` (1x12, 2x12, 4x12, 4x10, 4x10 Bass), `Microphone Position` (Near On-Axis, Near Off-Axis, Far), `Microphone Type` (Condenser, Dynamic), `Dual Mono`, `Dry/Wet`.

**Notes.** The tone controls interact non-linearly with each other and with the gain, and raising one can lower another. Dual (stereo) mode doubles CPU. A cabinet after the amp removes fizz and narrows the top; several Cabinet instances in a rack with different mics can be blended.

**Start (convention).** Industrial grit on a perc or synth bus: Amp `Rock` or `Lead`, `Input Gain` about 3-5 (the 0..10 display, no percent sign), then Cabinet with `Far` and `Condenser`, `Dry/Wet` 30-50 % on both. Not suitable for the clean pad.

### 4.6 Erosion (`Erosion2`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#erosion)

**For.** Digital degradation by modulating a very short delay with a sine and filtered noise; added texture, air and grit. Live 12.4 redesigned it (latency about 2 ms instead of 5 ms) and old sets load `Erosion Legacy` ([release notes](https://www.ableton.com/en/release-notes/live-12/)).

**Parameters.** `Amount`, `Frequency`, `Filter Width` (noise band; inactive at Noise Blend 0 %), `Noise Blend` (0 % sine only, 100 % noise only), `Stereo Width` (0 % mono modulation to 100 % stereo). Legacy: `Mode`, `Frequency`, `Width`, `Amount`.

**Start (convention).** Hi-hats or percussion at `Amount` 5-15 %, `Frequency` 4-8 kHz, `Noise Blend` 0-40 %. The noise setting adds air and rasp, exactly what the producer did not want on the pad.

### 4.7 Redux (`Redux2`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#redux)

**For.** Downsampling and bit reduction: jagged, 8-bit style grit.

**Parameters.** `Sample Rate`, `Jitter`, `Bit Depth` (1..16), `Quantizer Shape`, `DC Shift`, `Pre-Filter On`, `Post-Filter On`, `Post-Filter` (octaves relative to half the sample rate), `Dry/Wet`.

**Start (convention).** Hats, percussion, small accents: `Bit Depth` 8-12, `Sample Rate` 8-16 kHz, `Jitter` 0-20 %, `Post-Filter On` On, `Dry/Wet` 20-50 %. Turn on the Pre-Filter to cut aliasing before the downsample.

### 4.8 Vinyl Distortion (`Vinyl`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#vinyl-distortion)

**For.** Vinyl playback distortion plus crackle: the Tracing Model adds even harmonics, the Pinch Effect adds odd harmonics (out of phase between channels, so it widens), Soft or Hard mode, stereo or mono Pinch.

**Parameters.** `Tracing On`, `Tracing Drive`, `Tracing Freq.`, `Tracing Width`, `Pinch On`, `Pinch Soft On` (items Soft, Hard), `Pinch Mono On` (items Stereo, Mono), `Pinch Width`, `Pinch Drive`, `Pinch Freq.`, `Global Drive`, `Crackle Density`, `Crackle Volume`.

**Pitfall.** Crackle is noise; keep it low and never on a bus that carries a stem the game will loop.

### 4.9 Dynamic Tube (`Tube`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#dynamic-tube)

**For.** Tube-style saturation whose bias follows the input level (envelope), so loud passages can distort more or less than quiet ones.

**Parameters.** `Tube Type` (A, B, C), `Drive` (+/-15 dB), `Bias`, `Tone`, `Envelope` (negative values expand and reduce distortion on loud parts; positive values increase it), `Attack`, `Release` (inactive at Envelope 0), `Output`, `Dry/Wet`. Hi-Quality reduces aliasing and is a menu option.

**Start (convention).** Tube A for gentle, level-dependent warmth: `Drive` low, `Bias` low, `Envelope` slightly negative so peaks stay cleaner.

## 5. Modulation and space

> **For an agent (modulation and space).** Put reverbs and delays on return tracks at `Dry/Wet` 100 % (the manual says so for Echo, Delay, Hybrid Reverb, Chorus-Ensemble, Phaser-Flanger and most others) and control the amount with the send level (`set_mixer(..., sends={"A": -18})`). Cut the lows of the wet signal. After any chorus, phaser, widener or reverb, check mono-sum loss and stereo correlation with `analyze_audio`; wide, comb-filtered or out-of-phase material shows up as mono-sum loss. A reverb that is too long or too loud shows up as a collapsed loudness range and filled gaps between notes. Chorus, flanging and reverb modulation on noise or detuned layers sound "flangy" or "wavy": add them only on request and in small steps.

### 5.1 Chorus-Ensemble (`Chorus2`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#chorus-ensemble)

**For.** Thickening and gentle motion. Modes: Chorus (two modulated delays), Ensemble (a three-delay design after a 70s chorus pedal, richer and smoother), Vibrato (pitch modulation with no delay layering). Live 12.4 renamed the old Classic mode to Chorus and added `Delay Time` and `Delay Taps` ([release notes](https://www.ableton.com/en/release-notes/live-12/)).

**Parameters.** `Mode`, `Rate` (Hz), `Amount`, `Feedback` (off in Vibrato), `FB Invert`, `Delay Time` (items Auto, 7 ms, 10 ms, 20 ms, 35 ms, 50 ms; Auto scales with the modulation, a fixed time stays constant), `Delay Taps` (items 1, 2), both for **Chorus mode only** (the manual calls them the two additional parameters of Chorus mode; in Ensemble and Vibrato they are not active, although they stay in the parameter list), `HP On`, `HP Freq` (20 Hz to 2 kHz; the modulation is reduced below it), `Width` (0-200 %: balance of mid and side in the wet signal), `Warmth` (slight distortion and filtering), `Output`, `Dry/Wet` (off in Vibrato). Vibrato adds `Offset` and `Shape` (sine to triangle).

**Start (convention).** Widening a pad: `Mode` Ensemble, `Rate` 0.3-0.8 Hz, `Amount` 15-35 %, `Feedback` 0 %, `HP On` On at `HP Freq` 150-300 Hz, `Width` 100 %, `Warmth` 0-20 %, `Dry/Wet` 25-40 %. In Chorus mode only, a fixed `Delay Time` (20 ms, say) keeps the pitch steadier than Auto, which suits bass and guitar per the manual; Ensemble has no such control. The manual's surf-guitar tip (Ensemble at 1-1.8 Hz with `Amount` 100 %) is an effect, not a pad setting.

**Pitfalls.** Faster rates, high `Amount` or any `Feedback` bring flanging and comb filters: "flangy" is exactly this. Never put it on the bass register or on mostly-noise sounds. Chorus widens and detunes, so it competes with unison width the synth already provides; check mono-sum loss afterward. Put `Bass Mono` after it.

### 5.2 Phaser-Flanger (`PhaserNew`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#phaser-flanger)

**For.** Phaser (all-pass notches), Flanger (modulated comb with feedback) and Doubler (stacked short delays) in one device, with two LFOs and an envelope follower.

**Parameters.** `Mode` (Phaser, Flanger, Doubler), `Mod Freq` (Hz) or `Mod Rate` (when `Mod Sync` is On), `Amount`, `Feedback`, `FB Invert` (`FB Inv` in the 12.0 tables), `Notches` (Phaser), `Center Freq` and `Spread` (Phaser), `Flanger Time` (`Flange Time` in the 12.0 tables), `Doubler Time`, `Warmth`, `Output` (`Output Gain` in the 12.0 tables), `Dry/Wet`, `Mod Wave`, `Mod Blend`, `Duty Cycle`, `Spin Enabled`, `Spin`, `Mod Phase`, `Lfo Blend` (LFO2 mix), `Mod Sync 2`, `Mod Rate 2`, `Mod Freq 2`, `Env Enabled`, `Env Amount`, `Env Attack`, `Env Release`, `Safe Freq` (Safe Bass high-pass, 5 Hz to 3 kHz).

**Start (convention).** Hats or a pad: Phaser, `Notches` 4-6, `Mod Freq` 0.1-0.4 Hz, `Amount` 20-40 %, `Feedback` 20-40 %, `Safe Freq` 150-300 Hz, `Dry/Wet` 30-50 %. Doubler for a mono source: small `Amount`, `Feedback` 0 %.

**Pitfalls.** Feedback raises the level quickly (the manual warns about sudden volume increases). Comb filtering lowers mono compatibility. Older sets contain the legacy `Phaser` and `Flanger` devices with different names (`LFO Amount`, `Frequency`, `Env. Modulation`).

### 5.3 Auto Pan-Tremolo (`AutoPan2`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#auto-pan-tremolo)

**For.** Panning (two LFOs move the signal across the stereo field) or Tremolo (one LFO modulates the level). Redesigned in Live 12.3; the old device became Auto Pan Legacy ([release notes](https://www.ableton.com/en/release-notes/live-12/)).

**Parameters.** `Mode` (Panning, Tremolo), `Amount`, `Waveform` (Sine, Triangle, Shark Tooth, Saw Up, Saw Down, Square, Random, Wander, `S & H` with spaces), `Invert`, `Time Mode` (Rate in Hz, Time in s, Synced, Triplet, Dotted, 16th), `Frequency`, `Time`, `Rate` (note-value step), `16th`, `Phase`, `Offset`, `Stereo Mode` (Phase or Spin), `Spin`, `Panning Shape`, `Tremolo Shape`, `Attack Time`, `Dyn Mod` (LFO speed follows input level), `Harmonic` (alternates low and high bands around 600 Hz), `Vintage`.

**Start (convention).** Slow pad movement: Panning, Sine, `Amount` 10-25 %, `Frequency` 0.1-0.3 Hz. Rhythmic gate: Tremolo, Square, a sixteenth or eighth `Rate`, `Amount` 50-100 %.

**Pitfalls.** Panning motion collapses in mono, and Tremolo modulates level (it raises short-term loudness variation). Set `Time Mode` first, because `Frequency`, `Time` and `Rate` apply only in their own mode.

### 5.4 Echo (`Echo`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#echo)

**For.** The main delay: two delay lines with filters, modulation, ducking, tape-style noise and wobble, and a reverb in the loop.

**Parameters.** Time: `Channel Mode` (Stereo, Ping Pong, Mid/Side), `L Sync`, `R Sync`, `L Time`, `R Time` (ms, used when Sync is Off), `L Synced`, `R Synced` (note-value step), `L Sync Mode`, `R Sync Mode` (the items read Synced, Triplet, Dotted, 16th), `L 16th`, `R 16th`, `L Offset`, `R Offset`, `Link`, `Repitch`, `Repitch Smoothing Time`. Level: `Feedback`, `FB Invert`, `Input Gain`, `Output`, `Clip Dry`, `Dry Wet` (no slash), `Stereo Width`. Filter: `Filter On`, `HP Freq`, `HP Res`, `LP Freq`, `LP Res`. Dynamics: `Gate On`, `Gate Thr`, `Gate Release`, `Duck On`, `Duck Thr`, `Duck Release`. Character: `Noise On/Amt/Mrph`, `Wobble On/Amt/Mrph`. Modulation: `Mod Wave`, `Mod Freq`, `Mod Sync`, `Mod Rate`, `Mod Phase`, `Env Mix`, `Dly < Mod`, `Flt < Mod`, `Mod 4x`. Reverb: `Reverb Level`, `Reverb Decay`, `Reverb Loc` (Pre, Post, Feedback).

**Start (convention).** Return track: `Dry Wet` "100 %", `Channel Mode` Ping Pong, `L Sync` and `R Sync` On with `L Sync Mode` Dotted and a note-value step for an eighth (set the integer step and read the label), `Feedback` 30-45 %, `Filter On` On with `HP Freq` 200-400 Hz and `LP Freq` 3-5 kHz so repeats get darker and thinner, `Duck On` On so the repeats stay out of the dry phrase (tune `Duck Thr` and `Duck Release` by measuring that the dry level is not masked), `Reverb Level` 10-25 %.

**Pitfalls.** The parameter is `Dry Wet`, not `Dry/Wet`. `L Time` only matters when `L Sync` is Off. High `Feedback` builds up fast and can self-oscillate. `Repitch` On makes the pitch glide when times change (tape-like); Off crossfades. `Stereo Width` above 100 % hurts mono. Echo switches itself off about eight seconds after silence unless Noise and Gate are both on. Equal-Loudness for Dry/Wet is a menu option.

### 5.5 Delay (`Delay`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#delay)

**For.** Simple tempo or millisecond delays (1 ms to 5 s) with a band-pass filter before the line and an LFO on time and filter. Extended in Live 12.4 (more LFO modes, seven waveforms, `LFO Morph`).

**Parameters.** `Smoothing` (Fade, Repitch, Jump), `Link`, `Ping Pong`, `L Sync`, `R Sync`, `L Time`, `R Time`, `L 16th`, `R 16th` (labels 1, 2, 3, 4, 5, 6, 8, 16 for raw 0-7), `L Offset`, `R Offset` (swing), `Feedback`, `Freeze`, `Filter On`, `Filter Freq`, `Filter Width`, `LFO Mode` (Rate, Time, Synced, Triplet, Dotted, 16th), `LFO Freq`, `LFO Time`, `LFO Synced`, `LFO 16th`, `LFO Wave` (Sine, Triangle, Ramp Up, Ramp Down, Square, `S & H` with spaces, Wander), `LFO Morph`, `LFO > Delay`, `LFO > Filter`, `Dry/Wet`.

**Start (convention).** Prefer Echo for musical delays. Delay is the tool for the manual's two recipes: a glitch (Stereo Link on, sync step 6, `Feedback` 50 %, band-pass at 2.86 kHz, width 2.50, S&H LFO at 0.93 Hz, `LFO > Delay` 66 %, `LFO > Filter` 19 %, Fade smoothing, Ping Pong off, `Dry/Wet` 50-80 %) and a chorus (left 12 ms, right 30 ms, `Feedback` 0 %, triangle LFO at 0.65 Hz, `LFO > Delay` 58 %, Repitch, Ping Pong on, `Dry/Wet` 45-65 %).

**Pitfalls.** The filter is a band-pass in front of the delay, so a narrow setting makes the repeats thin. Changing the time while audio plays glitches in Jump mode.

### 5.6 Grain Delay (`GrainDelay`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#grain-delay)

**For.** Granular smearing and pitch-shifting delay for textures and glitches.

**Parameters.** `Frequency` (grain size follows it), `Spray` (random time per grain), `Pitch` (-36..12), `Random` (random pitch), `Feedback` (0-95 %), `DryWet` (no slash), `Delay Mode` (sync), `Beat Delay` (sixteenths), `Beat Swing`, `Time Delay` (ms).

**Start and pitfalls (convention).** Return track, `Pitch` +12 or -12 (an octave stays consonant), `Random` 0, `Spray` low, `Feedback` 20-40 %. Random pitch and high spray scramble the harmony; a pad should stay in key. Very high feedback runs away. The name is `DryWet`.

### 5.7 Filter Delay (`FilterDelay`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#filter-delay)

**For.** Three delay lines (left, left plus right, right), each behind its own linked low-pass and high-pass pair, for frequency-split rhythmic echoes.

**Parameters.** For n = 1..3: `n Input On`, `n Filter On`, `n Filter Freq`, `n Filter Width`, `n Delay Mode` (items Off, On; chooses between `n Time Delay` and `n Beat Delay`, On is the default), `n Time Delay` (ms), `n Beat Delay` (labels 1, 2, 3, 4, 5, 6, 8, 16), `n Beat Swing`, `n Feedback`, `n Pan`, `n Volume` (up to +6 dB); `Dry`.

**Start.** On a return set `Dry` to minimum. Pitfall: runaway feedback.

### 5.8 Beat Repeat (`BeatRepeat`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#beat-repeat)

**For.** Stutters, glitches and rhythmic repetition of the incoming audio, synced to the song tempo.

**Parameters.** `Interval` (1/32 to 4 bars), `Offset`, `Chance`, `Gate` (total length in sixteenths), `Grid` (slice size), `Variation`, `Variation Type` (Trigger, 1/4, 1/8, 1/16, Auto), `Block Triplets`, `Pitch` (0..12 st), `Pitch Decay`, `Filter On`, `Filter Freq`, `Filter Width`, `Mix Type` (items Mix, Ins, Gate), `Volume`, `Decay`, `Repeat` (momentary).

**Start (convention).** Return track with `Mix Type` Gate (only the repetitions pass), `Interval` 1 bar, `Offset` 0, `Gate` 4/16-8/16, `Grid` 1/16, `Chance` 30-70 %, `Pitch` 0. Pitfalls: `Repeat` On repeats until switched off; do not use it on stems that must loop seamlessly in the game, because the repeats depend on the transport position.

### 5.9 Hybrid Reverb (`Hybrid`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#hybrid-reverb)

**For.** Large and designed spaces: convolution reverb, five algorithmic reverbs, an EQ and a vintage degrader in one device. The right reverb for pads and drones.

**Flow.** Input (`Send Gain`, predelay with its own feedback) → engines (`Routing`: Serial, Parallel, Algorithm, Convolution; `Blend` between them as "100/0" to "0/100") → four-band EQ (before or after the algorithm via `EQ Pre Algo`) → output (`Width`, `Vintage`, `Bass Mono` below 180 Hz, `Dry/Wet`).

**Parameters.**

- Input: `Send Gain`, `Predelay Sync`, `Predelay` (ms), `Predelay 16th`, `Predelay FB`, `Predel. FB 16th`. The manual puts natural predelay at 1-25 ms.
- Algorithm: `Algo Type` (Dark Hall, Quartz, Shimmer, Tides, Prism), `Algo Delay`, `Decay` (time to -60 dB), `Size`, `Freeze`, `Freeze In`, `Damping`, `Diffusion`, `Modulation`; Dark Hall `DH Shape`, `DH BassMult`, `DH Bass X`; Quartz `Qz Low Damp`, `Qz Distance`; Shimmer `Sh Shimmer`, `Sh Pitch Shift`; Tides `Ti Tide`, `Ti Rate`, `Ti Waveform`, `Ti Phase`; Prism `Pr High Mult`, `Pr Low Mult`, `Pr X Over`, `Pr Sixth`, `Pr Seventh`.
- Convolution: properties `ir_category_index`, `ir_file_index` (lists `ir_category_list`, `ir_file_list`), `ir_attack_time`, `ir_decay_time`, `ir_size_factor`, `ir_time_shaping_on`. Categories: Early Reflections, Real Places, Chambers and Large Rooms, Made for Drums, Halls, Plates, Springs, Bigger Spaces, Textures, User. Your own IR files go into the User category by dragging them onto the waveform in the UI (they are forgotten if the device is removed).
- EQ: `EQ On`, `EQ Pre Algo`, `EQ Lo Type` (Cut or Shelf), `EQ Lo Freq`, `EQ Lo Gain`, `EQ Lo Slope` (6 to 96 dB/oct), `EQ Peak 1 Freq/Gain/Q`, `EQ Peak 2 Freq/Gain/Q`, `EQ Hi Type`, `EQ Hi Freq`, `EQ Hi Gain`, `EQ Hi Slope`.
- Output: `Width`, `Vintage` (Off, Subtle, Old, Older, Extreme), `Bass Mono`, `Dry/Wet`.

**Start (convention).** Return track: `Algo Type` Dark Hall, `Routing` Algorithm, `Decay` 3-6 s, `Size` 70-100 %, `Damping` 40-60 %, `Modulation` 0-20 %, `Predelay` 10-25 ms, `EQ On` On with `EQ Lo Type` Cut at `EQ Lo Freq` 200-300 Hz, `EQ Hi Gain` -2 to -4 dB, `Bass Mono` On, `Width` 100-120 %, `Dry/Wet` 100 %. As an insert use `Dry/Wet` 15-30 %. The NOVA project's approved "base pad" used Dark Hall at 5 s, `Size` 100 %, `Modulation` 0 and 30 % wet; a good sign that low modulation is the way to keep a pad clean.

Example: `set_device_parameters("return:A", "Hybrid Reverb", {"Algo Type": "Dark Hall", "Routing": "Algorithm", "Decay": "4 s", "Size": "90 %", "Damping": "50 %", "Modulation": "10 %", "Predelay": "15 ms", "EQ Lo Type": "Cut", "EQ Lo Freq": "250 Hz", "Bass Mono": "On", "Dry/Wet": "100 %"})`.

**Pitfalls.** Small `Size` with long `Decay` makes metallic, gong-like ringing (manual). Shimmer adds a pitched layer at `Sh Pitch Shift`; use +12 (octave) or +7 (fifth) and keep it in key. `Modulation` adds chorus-like movement and was part of the "wavy" sound complaints; start at zero. Convolution adds latency and CPU. High `Vintage` degrades the sound audibly. `Freeze` sustains forever, so release it.

### 5.10 Reverb (`Reverb`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#reverb)

**For.** The classic Live reverb: early reflections, a diffusion network with shelving decay, chorus and freeze; lighter on CPU than Hybrid Reverb. Good for small rooms, plates and drum spaces.

**Parameters.** Input: `In Lo Cut On`, `In Hi Cut On`, `Input Freq`, `Input Width` (unitless). The input filter is one band: the two switches choose which of its edges act, and `Input Freq` (centre, 830 Hz by default) and `Input Width` set where they sit; there are no separate low-cut and high-cut frequencies. Early reflections: `ER Spin On`, `ER Spin Rate`, `ER Spin Amount`, `ER Shape`. Diffusion: `Diff. Hi On/Type/Freq`, `HiShelf Gain`, `Diff. Lo On/Freq`, `LowShelf Gain`, `Diffusion`, `Scale`. Chorus: `Chorus On`, `Chorus Rate`, `Chorus Amount`. Global: `Predelay`, `Decay Time`, `Room Size`, `Size Smoothing` (None, Slow, Fast), `Freeze On`, `Flat On`, `Cut On`, `Stereo Image` (0 to 120 degrees), `Density` (four steps from Sparse to High), `Reflect Level`, `Diffuse Level`, `Dry/Wet`.

**Start (convention).** Return track at 100 % wet: `Predelay` 5-20 ms, `Decay Time` 0.8-2 s for drums, `In Lo Cut On` and `In Hi Cut On` both On with `Input Freq` and `Input Width` set so the band runs from roughly 200-300 Hz to 6-8 kHz (read the wet return in `analyze_audio` to check; the two edges cannot be set separately), `Density` High, `Chorus On` Off, `Stereo Image` 80-120.

**Pitfalls.** Several displays have no unit (1.4). Extremely small `Room Size` sounds metallic. Chorus inside the reverb is another modulation source: leave it off when the sound should stay clean.

### 5.11 Spectral Time (`Spectral`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#spectral-time)

**For.** Spectral freeze plus a spectral delay with tilt, spray and frequency shift: sustained clouds from any sound, smeared echoes.

**Parameters.** `Frozen`, `Delay On`, `Delay Mode` (items Time, Synced, 16th, 16th Triplet, 16th Dotted), `Delay Time` (ms), `Delay Synced` (note-value step), `Delay 16th` (sixteenths), `Delay Feedback`, `Delay Frequency Shift`, `Delay Tilt`, `Delay Spray`, `Delay Mask`, `Delay Stereo Spread`, `Delay Mix`, `Send Gain`, `Dry Wet` (no slash). The Freezer controls have their own names: `Mode` (Manual, Retrigger), `Retrigger Mode` (Onsets, Sync), `Unit` (Milliseconds, ModulationBeat), `Sync Interval`, `S.Rate ms`, `Fade Type` (Crossfade, Envelope), `Fade In`, `XFade %`, `Fade Out`, `Sensitivity`. The device has two switches, `Device On` and `On`. The Resolution control is not in the parameter list.

**Start and pitfalls (convention).** Return track at 100 % wet for sustained texture. Latency and CPU are significant; a lower Resolution (a menu option, ask the producer) gives lower latency at the cost of accuracy. Frozen material is inharmonic if the source is.

### 5.12 Shifter (`Shifter`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#shifter)

**For.** Pitch shifting (`Mode` Pitch), frequency shifting (Freq) and ring modulation (Ring), with a delay, LFO and envelope follower.

**Parameters.** `Mode`, `Pitch Coarse` (-24..24 st), `Pitch Fine`, `Pitch Window`, `FShift Coarse`, `Mod Fine`, `RM Coarse`, `RM Drive`, `RM Drive Gain`, `Wide`, `Delay On`, `Delay Sync`, `Delay Time`, `Delay Synced`, `Delay Feedback`, `Tone`, LFO (`Lfo Waveform`, `Lfo Sync`, `Lfo Rate Hz`, `Lfo S. Rate`, `Lfo Amount Hz`, `Lfo Amount St`, ...), `Env On/Attack/Release/Amount Hz/Amount St`, `MidiPitch Glide`, `Dry/Wet`. Properties: `pitch_mode_index` (Internal or MIDI; also accepted as `pitch_mode`), `pitch_bend_range`.

**Start (convention).** Octave layer: Pitch mode, `Pitch Coarse` 12, `Dry/Wet` 10-20 %. Phasing: Freq mode, shift under about 2 Hz at 50 % wet (manual). Ring mode under about 20 Hz is a tremolo.

**Pitfalls.** Frequency shifting and ring modulation are inharmonic: on a pad they make "wrong notes" by design. Pitch shifting chords adds artifacts. Not for a clean pad.

### 5.13 Vocoder (`Vocoder`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#vocoder)

**For.** Imposes the spectral envelope of a modulator (the track the device sits on) onto a carrier (noise, an external track, itself, or a pitch-tracked oscillator). Not in Live Intro or Lite.

**Parameters.** `Formant Shift`, `Attack Time`, `Release Time`, `Unvoiced Level`, `Unvoiced Sensitivity`, `Unvoiced Speed` (Fast, Slow), `Gate Threshold`, `Filter Width` (`Filter Bandwidth` in the 12.0 tables), `Upper Filter Band`, `Lower Filter Band`, `Precise/Retro`, `Envelope Depth` (100 % is classic), `Enhance`, `Mono/Stereo` (Mono, Stereo, L/R), `Output` (`Output Level` in the 12.0 tables), `Dry/Wet`, plus carrier-specific `Noise Rate`, `Noise Crackle`, `Oscillator Pitch`, `Oscillator Waveform` (Saw, Pulse10, Pulse25, Pulse48), `Upper Pitch Detection`, `Lower Pitch Detection` and `Ext. In Gain`.

**Notes.** An External carrier needs the "Audio From" choosers set in the UI (Post FX of the synth track is best); the API cannot route it. Bright, harmonic carriers (saw) are the most intelligible. Modulator as carrier with Depth 100 % and Enhance on turns it into a formant shifter.

### 5.14 Not covered in depth

Auto Shift (real-time pitch correction and tracking, new in 12.1), Looper, Spectrum, Tuner, Align Delay, Re-Enveloper, Spectral Blur (parameter names for these are in the reference dump), External Audio Effect, Frequency Shifter (legacy). The Max for Live LFO, Envelope Follower and Shaper devices can modulate other devices' parameters but load only through the browser and are routed in the UI.

## 6. Instruments (key parameters only)

Deeper coverage, synthesis theory and patch recipes: [02-synthesis-and-live-instruments.md](02-synthesis-and-live-instruments.md) and [03-sound-design-recipes.md](03-sound-design-recipes.md). Names below are the 12.4.6 strings from the reference dump unless marked. Most synth filters are per voice, which matters for distortion (see 4.1). Instruments only exist on MIDI tracks; a track holds one instrument.

> **For an agent (instruments).** Iterate on the preset or patch the producer chose: change one family at a time (filter, then amp envelope, then unison) and keep the previous patch on a muted twin. Do not pick or replace a sound by spectral distance to a full-mix reference: that is how a hollow Max for Live preset won on 2026-10-08. Use `analyze_audio` to diagnose (third-octave balance, stereo width per band, key and tempo estimates, noise floor) and the producer's ear to decide. Ask before switching oscillator types, unison modes or voice modes, because these change the character, not just the amount.

### 6.1 Wavetable (`InstrumentVector`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/#wavetable)

Two wavetable oscillators, a sub oscillator, two filters (circuits Clean, OSR, MS2, SMP, PRD; types low-pass, high-pass, band-pass, notch, Morph), three envelopes, two LFOs, unison. Voice count rose to 16 in Live 12.4.

Key parameters: `Osc 1 On`, `Osc 1 Pos`, `Osc 1 Transp` (st), `Osc 1 Detune` (ct), `Osc 1 Effect 1`, `Osc 1 Effect 2`, `Osc 1 Pan`, `Osc 1 Gain` (and the same for `Osc 2`); `Sub On`, `Sub Tone`, `Sub Gain`, `Sub Transpose`; `Flt 1 On`, `Flt 1 Type`, `Flt 1 LP/HP` (circuit), `Flt 1 Slope`, `Flt 1 Freq`, `Flt 1 Res`, `Flt 1 Drive`, `Flt 1 Morph` (and `Flt 2`); `Amp Attack`, `Amp Decay`, `Amp Sustain`, `Amp Release` with slopes; `Env 2` and `Env 3` (Attack ... Final, Loop Mode); `LFO 1`/`LFO 2` (Shape, Amount, Rate, Sync, Retrigger); `Unison Amount`, `Transpose`, `Glide`, `Volume`, `Time`, `Global Mod Amount`. Properties: `unison_mode` (UI names None, Classic, Shimmer, Noise, Phase Sync, Position Spread, Random Note; the API strings are in 1.5, where Shimmer is `slow_shimmer` and Noise is `fast_shimmer`), `unison_voice_count`, `poly_voices`, `mono_poly`, `filter_routing` (Serial, Parallel, Split), `oscillator_n_effect_mode` (UI names None, FM, Classic, Modern; API strings in 1.5), `oscillator_n_wavetable_category` and index. The modulation matrix is reached through `device_action`: `get_modulation`, `set_modulation`, `add_parameter_to_modulation_matrix`.

Watch: the unison modes Shimmer and Noise are noisy by design, and Noise unison is the opposite of "clean". The Sub follows the played note; a sub transposed down puts chord thirds in the 55-65 Hz zone (the Dark Throne problem). Hi-Quality is a menu option.

### 6.2 Drift (`Drift`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/#drift)

A simple, CPU-light subtractive synth: two oscillators, noise, a low-pass (Type I 12 dB DFM, Type II 24 dB MS2) and a high-pass, two envelopes (Envelope 2 can cycle), an LFO and a three-slot mod matrix.

Key parameters: `Osc 1 Wave` (Sine, Triangle, Shark Tooth, Saturated, Saw, Pulse, Rectangle), `Osc 1 Shape`, `Osc 1 Oct`, `Osc 2 Wave` (Sine, Triangle, Saturated, Saw, Rectangle), `Osc 2 Detune`, `Osc 2 Oct`, `Osc 1 Gain`, `Osc 2 Gain`, `Noise On`, `Noise Gain`, `LP Freq`, `LP Res`, `LP Type`, `HP Freq`, `Key > LPF`, `Env 1 Attack/Decay/Sustain/Release`, `Env 2 ...`, `Spread`, `Strength`, `Thickness`, `Drift`, `Glide Time`, `Legato On`, `Vel > Vol`, `Volume`, `Transpose`. Properties: `voice_mode_index` (Poly, Mono, Stereo, Unison; also accepted as `voice_mode`), `voice_count_index` (`voice_count`), `pitch_bend_range`, modulation sources and targets.

Watch: `Drift` detunes every voice slightly at random (pitch and filter), which is exactly the "out of tune pad" risk when high; keep it low for clean stacked chords. Oscillator gains above the default (-6 dB) push the filter into saturation, which is distortion on every voice.

### 6.3 Operator (`Operator`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/#operator)

Four oscillators with eleven algorithms (`Algorithm` 0-10), per-oscillator envelopes, a filter, LFO, pitch envelope and a shaper. 32 voices since Live 12.2 ([release notes](https://www.ableton.com/en/release-notes/live-12/)); the voice count itself is a UI control, not in the parameter list.

Key parameters: `Algorithm`, `Osc-A On`, `Osc-A Level`, `Osc-A Wave`, `A Coarse`, `A Fine`, `A Fix On`, `Osc-A Feedb`, `Ae Attack/Decay/Sustain/Release` (and B, C, D); `Filter On`, `Filter Type`, `Filter Freq`, `Filter Res`, `Filter Drive`; `Shaper Type`, `Shaper Mix`, `Shaper Drive`; `LFO ...`, `Pe ...`; `Spread`, `Tone`, `Volume`, `Transpose`, `Glide Time`. Modulator levels set the brightness; integer `Coarse` ratios stay harmonic and non-integer ones are inharmonic (bells, metal); oscillators set to fixed frequency ignore the played note.

### 6.4 Analog (`UltraAnalog`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/#analog)

A physical-model virtual analog synth (with Applied Acoustics Systems): two oscillators and noise feed two multimode filters (serial or parallel), each with its own amplifier and envelope, plus two LFOs.

Key parameters: `OSC1 On/Off`, `OSC1 Shape`, `OSC1 Octave`, `OSC1 Semi`, `OSC1 Detune`, `OSC1 PW`, `OSC1 Level` (and `OSC2`), `Noise On/Off`, `Noise Level`, `Noise Color`, `F1 On/Off`, `F1 Type`, `F1 Freq`, `F1 Resonance`, `F1 Drive` (and `F2`), `FEG1 Attack/Decay/Sustain/Rel`, `AEG1 Attack/Decay/Sustain/Rel`, `Unison On/Off`, `Unison Voices`, `Unison Detune`, `Voices`, `Volume`. Oscillator shapes: sine, sawtooth, rectangle, white noise; each oscillator also has a Sub or Sync mode.

### 6.5 Meld (`InstrumentMeld`) [12.4.6] · [manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/#meld)

Two independent macro-oscillator engines (A and B; 25 oscillator types in 12.4.6, seven of them scale-aware and marked ♭♯ in the list: the Chord oscillator arrived in 12.2, and the manual text still counts 24 and six), each with its own filter (17 types), envelopes, two LFOs and a matrix. Parameter names are in the reference dump (129 parameters). Per engine they carry an `A ` or `B ` prefix: `A On`, `A Osc Type`, `A Osc Shape`, `A Osc Tone` (the two macro knobs), `A Keytracking`, `A Octave`, `A Transpose`, `A Detune`, `A Filter Type`, `A Filter Freq`, `A Amp Attack`, `A Mod Attack`, `A Volume`, `A Pan` (and `B`). The shared section has `Drive` (global saturation), `Limiter On` (a limiter that runs per voice, after the global Drive), `Voice Spread`, `Volume`, `Mono Legato`, `Scale Aware`, `Link Envelopes` and `Engine B Delay`; the device switch is `Device On`. Properties: `selected_engine` (A or B), `unison_voices` (off, 2, 3, 4: the UI's Stacked Voices), `mono_poly`, `poly_voices` (2 to 12). Engine macro knobs change meaning with the oscillator type; check the display after switching types.

### 6.6 Simpler and Sampler (`OriginalSimpler`, `MultiSampler`) [12.4.6] · [Simpler](https://www.ableton.com/en/live-manual/12/live-instrument-reference/#simpler), [Sampler](https://www.ableton.com/en/live-manual/12/live-instrument-reference/#sampler)

Simpler plays one sample in Classic, One-Shot or Slicing mode, with warp, a filter, three envelopes and an LFO. Sampler is the multisample sibling with key and velocity zones and a deeper modulation system.

Simpler key parameters: `S Start`, `S Length`, `S Loop On`, `S Loop Length`, `S Loop Fade`, `Snap`, `Transpose`, `Detune`, `Volume`, `Pan`, `Spread`, `Ve Attack/Decay/Sustain/Release`, `Ve Mode`, `Fade In`, `Fade Out`, `Trigger Mode`, `F On`, `Filter Type`, `Filter Circuit - LP/HP`, `Filter Slope`, `Filter Freq`, `Filter Res`, `Filter Drive`, `Fe On`, `Fe < Env`, `Filt < Key`, `Filt < Vel`, `L On`, `L Rate`. Properties and sample options via `set_device`: `playback_mode` (classic, one_shot, slicing), `slicing_playback_mode`, `sample.warping`, `sample.warp_mode`; actions via `device_action`: `crop`, `reverse`, `warp_as`, `insert_slice`, `to_drum_rack`. Sampler adds `Key Zone Shift`, `Sample Selector`, `Time`, `Time < Key` and three LFOs. A Simpler default root note is C3 (Live's convention, MIDI 60).

### 6.7 Drum Sampler · [manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/#drum-sampler)

A one-shot player built for Drum Rack pads (Simpler stays the default for dropped samples unless a pad is saved as the default). Sample Start, Length and Gain (-70 to 24 dB), an AHD envelope (`Hold` can be infinite), Transpose +/-48 st, Detune +/-50 ct, nine playback effects (Stretch, Loop, Pitch Env, Punch, 8-Bit, FM, Ring Mod, Sub Osc, Noise) with two controls each, a filter (12 or 24 dB low-pass, 24 dB high-pass, peak), Volume +/-36 dB, Pan, velocity-to-volume and a modulation slot. It inserts under the name `DrumSampler`. Parameter names were neither in the snapshots nor in the reference dump: read them with `get_device`.

### 6.8 Granulator III (Max for Live pack device) [12.4.6]

A Robert Henke granular instrument with Classic, Loop and Cloud modes, MPE support and real-time audio capture, 59 presets in the pack ([Ableton pack page](https://www.ableton.com/en/packs/granulator-iii/)). It is a Max for Live device: load it with `load_from_browser`, read its parameter names and real-unit ranges with `get_device` (the reference dump lists 117 of them: `Mode` {Classic, Loop, Cloud}, `Density` 2..20, `Grain Size` 2..2000 ms, `Position` and `Scan`, `Variation` %, `Spread` in semitones 0..12, `Transpose` +/-24 st, `Flt Type`, `Flt Freq`, `Env 1`/`Env 2` times, `Volume`), and expect values in the patch's own units. Use it for evolving textures, not for a clean harmonic pad.

## 7. Racks: macros, chain selector, addressing

[Manual: Racks](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/). Four kinds: Instrument Rack (instruments plus MIDI and audio effects), Drum Rack (one chain per MIDI note), Audio Effect Rack, MIDI Effect Rack. Chains run in parallel and their outputs are summed; devices inside a chain run in series. A Drum Rack chain receives a single assigned note, can use up to six return chains with send levels, and has 16 choke groups. A rack is addressed and edited like a device.

**Addressing.**

- `get_devices(track)` returns every device with `path` (`"1/0/0"`) and `name_path` (`"Drum Rack/Kick/Simpler"`), racks with their chains, visible macros and variation counts, and Drum Racks with non-empty pads. Copy the path you need.
- A `device` argument is an index, a name, or a path that alternates device and chain segments and ends with a device: `"Drum Rack/Kick/Saturator"`, `"Instrument Rack/0/Operator"`, `"0/0/1"`. Chain segments accept an index, a name, a Drum Rack note (`"C1"`; Live's convention puts C1 at MIDI 36, the lowest pad) and `"return:0"` for a Drum Rack return chain (return-chain devices were not yet addressable by path at the last spike, see [docs/spikes.md](../spikes.md)).
- Chain names change when the first device or sample changes (a chain is named after its first device), and two chains can share a name; prefer the note or the index for Drum Rack pads.
- `add_device(track, "Saturator", chain="Drum Rack/C1")` inserts into a pad's chain (the chain is created if the pad is empty); `chain="Audio Effect Rack/new"` makes a chain. `set_chain(track, rack, chain, volume_db=..., pan=..., mute=..., solo=..., in_note=..., out_note=..., choke_group=...)` edits the chain; `device_action` runs `insert_chain`, `add_macro`, `remove_macro`, `randomize_macros`, `store_variation`, `recall_variation`, `copy_pad`, `delete_chains`, `to_midi_track`.

**Macros.** Up to 16 macro knobs; eight are shown by default, and the visible count changes in steps of two. The parameter list shows `Macro 1` ... `Macro 16`, raw 0..127. Once a macro is mapped to a single parameter it takes that parameter's name and unit (`Filter Cutoff` shows "3.26 kHz"); mapped to several, it reverts to a generic name and a 0-127 scale. A parameter that is mapped to a macro becomes disabled, so write to the macro instead. Core Library racks name their macros for the job: for example the drum-bus racks expose `DrBuss Amount`, `DrBuss Drive`, `DrBuss Transient`, `Comp Amount`, `Low Gain`, `Mid Gain`, `Mid Freq`, `Hi Gain`, `Squash`, `Over Drive`. Macro variations store and recall all macro values (`store_variation`, `recall_variation`); a macro can be excluded from randomization and from variations in the UI.

**Chain selector.** Instrument and Audio Effect Racks have a `Chain Selector` (raw 0..127). Each chain has a chain-select zone; only chains whose zone overlaps the selector value produce output. By default a zone is one value long, which makes a rack a preset bank: chain 0 at 0, chain 1 at 1, and so on. Fade ranges at the zone edges crossfade the chain levels. Zone positions are not exposed to the API, so a bank must be built in the UI or loaded from the library; the agent can only move the selector. Drum Racks have no zones or selector.

**Pitfalls.** Mapped macros hide the inner parameter (the error says macro-mapped). Duplicating a rack duplicates its contents; a track's instrument cannot be duplicated on its own. MIDI effects must precede the instrument, and instruments and MIDI effects cannot go onto audio tracks. Racks inside racks make paths long; use `get_devices` instead of guessing. Rack mixer sliders (`set_chain`) and the devices inside are separate gain stages.

## 8. Recipes by job

Each recipe lists the steps in order. Do one at a time, per the safe edit loop in 1.7, and leave anything the producer has approved as it is unless he says otherwise.

### 8.1 Duck a bass or pad to the kick

1. Read the kick's level while it plays: `get_meters(["Kick"])` and note `peak_db` (say -6 dB). The sidechain threshold compares against the kick, not against the bass. The meter reads after the kick's fader, while a Post FX tap sees the kick before it: if the kick fader is at -3.4 dB, add 3.4 dB back to the reading.
2. `set_sidechain("Bass", "Kick", channel="Post FX", threshold_db=<kick peak - 7>, ratio=6, attack_ms=0.5, release_ms=<ms>)`. The steady-state reduction is about (kick peak - threshold) x (1 - 1/ratio): 7 dB above the threshold at 6:1 gives about 6 dB. Short kicks give less because of attack and release, so start there and measure.
3. Pick the release from the tempo: ms per beat = 60000 / BPM. A sixteenth is a quarter of that, an eighth half. At 120 BPM: 125 ms and 250 ms. At 128: about 117 and 234. At 140: about 107 and 214. A release of one sixteenth to one eighth lets the bass recover before the next kick.
4. Refine: `set_device_parameters("Bass", "Compressor", {"Model": "Peak", "Knee": "0 dB", "LookAhead": "1 ms"})`.
5. Check: bounce the bass stem with and without the duck; the dips should line up with kick onsets and be no deeper than planned.
6. Ask the producer before using more than about 6-8 dB of ducking, or ducking on a sound he has approved.

### 8.2 Glue a drum bus

1. `create_bus("Drum Bus", [...])`; keep the stems unprocessed.
2. Add Drum Buss: `{"Compressor On": "On", "Drive Type": "Medium", "Drive": "20 %", "Crunch": "15 %", "Transients": "0.15", "Boom Freq": "55 Hz", "Boom Amt": "25 %", "Boom Decay": "50 %", "Output": "-2 dB"}`. Tune `Boom Freq` to the kick's fundamental (read the peak third-octave band from `analyze_audio`).
3. Add Glue Compressor: `Ratio` 4, `Attack` and `Release` as raw steps whose displays you read back (about 10 ms and 0.2 or Auto), threshold for 2-4 dB of reduction, `Output` to match level.
4. Add EQ Eight only for a measured problem.
5. Check: low-band balance (boom must not add more than 1-2 dB in the sub bands unless intended), mono-sum loss, crest factor drop of about the reduction.
6. Ask for a labelled A/B (bus on versus off, level matched) before leaving it on.

### 8.3 Pad: big, heavy, clean

The producer's reference: one low root (about 41-49 Hz) under a saw-like harmonic stack up to roughly 2 kHz, very wide above 200 Hz, little noise, smooth roll-off above 2 kHz. Iterate on the approved base pad rather than replacing it.

1. Source in the synth, not in effects: a saw-based oscillator pair, a low root, a few cents of detune (Wavetable `Osc 2 Detune` a few ct, or Drift `Osc 2 Detune`; read the unit), noise off. Width from voice-level unison or stereo spread (Wavetable `unison_mode` Classic with `Unison Amount` 15-30 %; Drift `voice_mode` Stereo or Unison with moderate `Spread`/`Strength`), not from chorus on the output.
2. Roll off with the synth filter or Auto Filter: Low-pass 12dB at 2-3 kHz, `Resonance` 0-10 %, `Circuit` SVF.
3. Voicing: below about 130 Hz (Live C2) only roots, fifths and octaves; major thirds from about 165 Hz (E2), minor thirds and seconds higher still; the lowest sounding note is the chord root. Thirds lower than that sound muddy or out of tune ([08-arrangement-and-composition.md](08-arrangement-and-composition.md)).
4. Utility last: `Bass Mono` On, `Bass Freq` 120-150 Hz.
5. Space on a return: 8.4.
6. Do not add Saturator, Roar, Chorus-Ensemble, Limiter or a bus compressor to the pad unless asked. If a little colour is wanted, use per-voice filter drive in the synth, or Saturator at 1-2 dB with a negative `Color Amt Low`, in parallel.
7. Check on the solo pad stem: strong low root, harmonics falling off after about 2 kHz, stereo width high above 200 Hz, mono-sum loss small, no noise floor rise.
8. Ask: present as a labelled, loudness-matched A/B against the base pad.

### 8.4 Reverb return for pads and synths

Create the return with `create_track("return", "Reverb", device="Hybrid Reverb")` and feed it with `set_mixer(track, sends={"A": -18})`. Hybrid Reverb as in 5.9: Dark Hall, `Decay` 3-6 s, `Size` 70-100 %, `Damping` 40-60 %, `Modulation` 0-20 %, `Predelay` 10-25 ms, low cut 200-300 Hz, `Bass Mono` On, `Dry/Wet` 100 %. Sends of -18 to -12 dB are a start; raise by 2 dB at a time. For drums use a short Reverb or Hybrid Prism with `Decay` under 1.5 s and a high-pass above 300 Hz. Check: loudness range (it should not collapse), mono-sum loss, and that the gaps between notes are not filled.

### 8.5 Echo return

Echo as in 5.4 at `Dry Wet` 100 %, Ping Pong, dotted-eighth or eighth, `Feedback` 30-45 %, HP 200-400 Hz, LP 3-5 kHz, `Duck On`. Send from leads and arps at -15 to -10 dB. Check: the tail should decay by the next phrase; an echo that never clears is a feedback or send problem.

### 8.6 Safety chain on Main

Optional gentle bus compression, then the limiter last: Glue Compressor `Ratio` 2, `Release` Auto, 1-2 dB of reduction or none; Limiter `Mode` True Peak, `Ceiling` -1.0 dB, `Lookahead` 3 ms, `Auto` On, `Input Gain` for 1-3 dB of reduction. Keep the Main fader at or below 0 dB. Do not put limiters on stems or groups. Loudness work is in [07-mastering-and-loudness.md](07-mastering-and-loudness.md); for the game's adaptive stems see [10-game-audio-adaptive-music.md](10-game-audio-adaptive-music.md).

### 8.7 Grit on percussion without a mess

Parallel is safer than serial. Option A: Saturator on the track at `Dry/Wet` 30-50 %, `Type` Analog Clip, `Drive` 3-5 dB, `Output` -1 to -3 dB. Option B: Roar in Multi Band, high band only, 15-25 %, `Dry/Wet` 40 %. Option C: Pedal (Distortion, `Sub` On) on a kick, as in the manual recipe. Check: third-octave energy above 2 kHz and crest factor against the clean version; ask before it ships.

### 8.8 Width and mono safety

Widen in the synth (unison, stereo spread), then Utility `Stereo Width` 100-130 % at most, then Utility `Bass Mono` On at 120-200 Hz as the last device. Check with `analyze_audio`: stereo width and correlation per band, and mono-sum loss on the Main bounce. If mono-sum loss rises after a change, undo the widener first.

### 8.9 Typical device order

| Track | Order (left to right) |
| --- | --- |
| Pad or synth | instrument (voice filter/drive) → Auto Filter (only if needed) → EQ Eight (only for a measured problem) → light Compressor (RMS) → [modulation only on request] → Utility (width, `Bass Mono` last) → sends to returns |
| Bass | instrument → EQ Eight (high-pass 25-30 Hz) → Saturator or Pedal (optional) → Compressor (ducked by the kick via `set_sidechain`) |
| Kick and drums | sample or Drum Rack → EQ Eight → light Saturator (optional); no limiter |
| Drum bus | Drum Buss → Glue Compressor → EQ Eight (optional) |
| Reverb return | Hybrid Reverb or Reverb at 100 % wet |
| Delay return | Echo at 100 % wet → EQ Eight (optional) |
| Main | EQ Eight (gentle) → Glue Compressor (optional, 1-2 dB) → Limiter (last) |

## 9. Checklists

**Before changing a device**

- `get_device` read; the parameter names, `items` and displays are on screen, not remembered.
- One change defined, with a prediction of what the measurement will show.
- The previous state is safe: device A/B slot, muted twin track, or a take snapshot.
- Only the track the producer named is touched.
- Level compensation planned (`Output`, `Makeup`, Utility `Output`).

**After changing a device**

- The echoed `display` matches the request, every key.
- A bounce or capture compared with the previous take: loudness matched within 0.2 LU (0.3 LU at most), the targeted band moved by the intended amount, other bands under 1 dB, crest factor and loudness range not collapsed, mono-sum loss not worse ([11-listening-without-ears.md](11-listening-without-ears.md)).
- The result is labelled for the producer: what changed, which take is A and which is B.

**Stop and ask the human when**

- A sound he approved would be replaced, or any effect would be added to it.
- Any limiter, clipper or heavy compressor (more than about 3 dB of reduction) would go on anything but the Main safety limiter.
- Distortion, chorus, flanging, widening or reverb modulation is wanted on a pad or other clean sound.
- A change affects several tracks at once (bus or Main processing, global EQ).
- A device option lives in a menu or a UI-only routing (sidechain on Glue, Gate or Auto Filter; Hi-Quality; Roar's modulation matrix; Vocoder carrier).
- The measurement and the described target disagree. Measurements diagnose; the producer's ear decides.

## Sources

Primary, from Ableton:

- [Live 12 manual: Live Audio Effect Reference](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/): every effect card above (anchors per device).
- [Live 12 manual: Live Instrument Reference](https://www.ableton.com/en/live-manual/12/live-instrument-reference/): Wavetable, Drift, Operator, Analog, Meld, Simpler, Sampler, Drum Sampler.
- [Live 12 manual: Instrument, Drum and Effect Racks](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/): macros, chain select zones, Drum Rack chains, variations.
- [Live 12 manual: Routing and I/O](https://www.ableton.com/en/live-manual/12/routing-and-i-o/): Pre FX, Post FX and Post Mixer tapping points used by sidechains.
- [Live 12 release notes](https://www.ableton.com/en/release-notes/live-12/): device changes in 12.2 (Auto Filter, Roar, Resonators, Spectral Resonator, Operator 32 voices, Meld Chord oscillator, sidechain headers), 12.3 (Auto Pan-Tremolo), 12.4 (Erosion, Chorus-Ensemble, Delay, Wavetable voices).
- [Ableton blog: Roar, Live 12's processing powerhouse](https://www.ableton.com/en/blog/roar-meet-live-12s-new-processing-powerhouse/) and the Ableton pack pages for [Pedal](https://www.ableton.com/en/packs/pedal/) and [Granulator III](https://www.ableton.com/en/packs/granulator-iii/): use cases only, few numbers.

Technical and API:

- [reference/live-12.4.6-device-parameters.json](reference/live-12.4.6-device-parameters.json) and its [readable form](reference/live-12.4.6-device-parameters.md): the parameter names, raw ranges, items and default displays this file was checked against (dumped from the running Live 12.4.6 on 2026-10-08 by `scripts/dump_device_parameters.py`).
- [Cycling '74: Live Object Model](https://docs.cycling74.com/apiref/lom/) (mirrored in [docs/reference/lom_docs_12.4.5.md](../reference/lom_docs_12.4.5.md), with the 12.4.6 enum names in [docs/reference/live_api_12.4.6.md](../reference/live_api_12.4.6.md)): device properties such as `global_mode`, `oversample`, `routing_mode_index`, impulse-response properties.
- [Cycling '74: abl.device.limiter~](https://docs.cycling74.com/reference/abl.device.limiter~): Limiter ranges and modes as a Max DSP object.
- Ableton's Remote Script bank tables as mirrored on GitHub (third party, medium evidence for names, now superseded by the reference dump where they differ): [Live 12.0 default_bank_definitions.py](https://github.com/gluon/AbletonLive12_MIDIRemoteScripts/blob/master/ableton/v3/control_surface/default_bank_definitions.py) and [Live 11 _Generic/Devices.py](https://github.com/gluon/AbletonLive11_MIDIRemoteScripts/blob/master/_Generic/Devices.py).
- This repository: [docs/TOOLS.md](../TOOLS.md) (tool semantics), [docs/spikes.md](../spikes.md) (display_value units, device insertion rules, name resolution), `AbletonMCP_Remote_Script/values.py` and `refs.py` (how value strings and parameter names are parsed and matched), and take snapshots recorded with Live 12.4.6 on this Mac (the verified parameter names, ranges and display strings).

Practice and theory:

- [Cytomic: The Glue](https://cytomic.com/product/glue/): design of the compressor that Live's Glue Compressor was built with (feedback VCA, diode-style detector).
- [Sound On Sound: Parallel compression, page 2](https://www.soundonsound.com/techniques/parallel-compression?page=2): very high ratio, about 20 dB of reduction, mixed with the direct signal.
- [iZotope Learn: What is sidechain compression](https://www.izotope.com/en/learn/what-is-sidechain-compression.html): the idea and uses; few numbers.
- [Wikipedia: Intermodulation](https://en.wikipedia.org/wiki/Intermodulation): why distorting several simultaneous notes creates sum and difference tones.
- Project context: [docs/handoff/2026-10-08-nova-v2-paused.md](../handoff/2026-10-08-nova-v2-paused.md) (the producer's reactions and the approved base pad).

## Open questions / where sources disagree

- **Names after 12.0 (resolved for the dumped devices).** The cards that were built from the Live 12.0 Remote Script tables were re-checked against the reference dump on 2026-10-08; the renames are in 1.6. Still not dumped, so still manual-level: Drum Sampler, the DS drum synths, the rack devices and the Legacy twins (`Auto Filter Legacy`, `Erosion Legacy`, legacy Phaser and Flanger). Run `get_device` and update this file when you see a difference after a Live update.
- **Item lists seen only in part (mostly settled).** The reference dump records these in full, so they are no longer unobserved: Limiter `Mode` = Standard, Soft Clip, True Peak; Saturator `Post Clip Mode` = No Clip, Soft Clip, Hard Clip; EQ Eight filter types including Notch and Low Pass 48dB; Utility `Channel Mode` = Left, Stereo, Right, Swap; Echo `L Sync Mode` = Synced, Triplet, Dotted, 16th (the "Notes" mode of the manual reads "Synced"). It does not record item lists for the stepped Glue Compressor `Attack`, `Release` and `Ratio`, Hybrid Reverb `Vintage` and `EQ Lo Slope`, or the beat-division parameters: check those with `get_device` `items`.
- **Beat-division mapping.** For the non-quantized stepped parameters (Echo `L Synced`, Auto Filter `LFO Rate`, Roar `FB Synced`) the integer-to-note-value mapping was not recorded. It has to be probed once per device.
- **Disabled-by-state parameters.** Whether Live flags Limiter `Release` as disabled while `Auto` is on, and `Threshold` and `Output` while `Maximize On` is off, was not tested; the manual only says the controls are deactivated or replaced.
- **Display ranges.** The manual gives few extremes (Utility gain, Channel EQ, Glue Range, Reverb stereo 120 degrees). Attack and release extremes for Compressor, Gate and others, EQ Eight Q, Saturator Drive, were not documented in the sources used.
- **Starting values are convention.** Practitioners disagree on Glue Compressor attack (10 ms for glue, 30 ms for punch, 1-3 ms for tight), on high-passing pads at all, and on the Bass Mono corner (100, 120, 150 or 200 Hz). The values here are hypotheses to be confirmed by a labelled A/B with the producer, not defaults. The Sound On Sound compression overview mentions Limiter options of 1.5, 3 and 10 ms, while the Live 12 manual and the 12.4.6 snapshots show a 1.5, 3 and 6 ms lookahead; the manual and snapshot win.
- **What the API cannot do (as far as found).** Toggle Utility's Mid/Side width mode; edit Roar's modulation matrix; set rack chain-select zones; route a sidechain on any device but Compressor; reach context-menu options other than those listed in 1.5. A human or UI automation (`ableton-mcp doctor`) would have to do these.
- **Not covered here.** Auto Shift, Looper, Spectrum, Tuner, Align Delay, Re-Enveloper, Spectral Blur, External Audio Effect, Frequency Shifter and the Granulator III parameters are not described in depth; the reference dump lists the names of all of them except External Audio Effect and Frequency Shifter.
- **Meld oscillator count.** The Live 12 manual text counts 24 oscillator types and six scale-aware ones; the running 12.4.6 lists 25 and seven (the Chord oscillator was added in 12.2). This file follows the running Live.

