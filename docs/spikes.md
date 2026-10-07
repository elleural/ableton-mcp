# Phase-0 spike findings (Live 12.4.6, Python 3.11.6, 2026-10-06)

Results of running experiments against the real Live. These answer PRD §13 and are binding for implementation.

## Devices

- `Track.insert_device(name, index=-1)` and `Chain.insert_device` insert **any native Live device**, returning the Device.
  - Names are the exact, case-sensitive browser names (`"Operator"`, `"EQ Eight"`, `"Glue Compressor"`). `"operator"` and the class name `"Eq8"` fail with `ValueError: Device X not found.`
  - Tools must resolve user input case-insensitively against the browser's device names (instruments, audio_effects, midi_effects) and pass the exact name.
  - Pack and Max for Live devices (`"Bass"`, `"Poli"`, `"Granulator III"`) are not native. Load them through the browser.
  - Instruments and MIDI effects can only go on MIDI tracks (`RuntimeError: Can not insert device 'Operator': Only audio effects can be inserted ...`). Audio effects go anywhere.
  - Class names differ from display names. Examples:

    | Display name | Class name |
    |---|---|
    | Wavetable | `InstrumentVector` |
    | Simpler | `OriginalSimpler` |
    | Sampler | `MultiSampler` |
    | Drum Rack | `DrumGroupDevice` |
    | Analog | `UltraAnalog` |
    | Electric | `LoungeLizard` |
    | Compressor | `Compressor2` |
    | Utility | `StereoGain` |
    | Auto Filter | `AutoFilter2` |
    | Spectral Resonator | `Transmute` |
    | Hybrid Reverb | `Hybrid` |
- `insert_device(name, 0)` inserts at the front.
- `RackDevice.insert_chain()` returns the new Chain. Racks start with 0 chains, and a chain is auto-named after its first device.
- `Track.duplicate_device(i)` on an instrument fails ("Can not duplicate instrument"), because a track holds one instrument.
- `track.devices` does **not** include the mixer device. An empty track has `[]`.
- `refs.device_path` on a device inside a rack chain gives `"1/0/1"` and `"Instrument Rack/Operator/Reverb"` (chain named after its first device).

## Parameters: `display_value` accepts real units

| Parameter | Write | Read back |
|---|---|---|
| Volume | `display_value = -6.0` | value 0.70, "-6.0 dB" |
| Pan | `display_value = -25` | value -0.5, "25L" (display units are -50..50) |
| Send | `display_value = -12` | "-12.0 dB" |
| Auto Filter Frequency | `display_value = 800` | "800 Hz" (Hz, even when the display says kHz) |
| Quantized ("Device On") | `display_value` | the index (1.0) |

Use `display_value` for unit-based writes. `values.value_for_display_number` (bisection) stays as a fallback. For quantized parameters, match `value_items`. Raw `value` is the normalised internal value.

## Tracks

- Return tracks are named **with their letter prefix**: `"A-Reverb"`, `"B-Delay"`. Name resolution must also accept the bare name (`"Reverb"`).
- Routing lists (`available_input_routing_types`, …) are **empty (`[""]`) in the same main-thread tick a track is created**. They populate by the next tick, so routing must be configured in a later command or tick.
- Display names in the default set:
  - Audio track inputs: `Ext. In`, `Resampling`, `3-Audio`, `4-Audio`, `A-Reverb`, `B-Delay`, `Main`, `No Input`.
  - Audio track outputs: `Ext. Out`, `Main`, other audio tracks, `Sends Only`.
  - Track-number prefixes such as `1-MIDI` are part of the display name.
  - A MIDI track with no instrument has no audio output, so it is not offered as an audio input source.
- New MIDI tracks can come up **armed** (Live auto-arm). Anything that records must disarm the other tracks first.

## Clips and notes

- `Track.create_midi_clip(start, length)` creates an arrangement clip (looping, loop 0..length).
- `Live.Clip.MidiNoteSpecification(pitch=, start_time=, duration=, velocity=, mute=, probability=, velocity_deviation=, release_velocity=)` takes keyword arguments. `add_new_notes(tuple)` returns note ids. `get_notes_extended` returns MidiNote with every field. `apply_note_modifications` edits by id.
- `Track.duplicate_clip_to_arrangement(clip, time)` accepts Session and arrangement clips, so moving a clip is duplicate plus `Track.delete_clip`. `arrangement_clips` come back ordered by start time.
- **The arrangement extent cannot be resized.**
  - Setting `end_marker` or `loop_end` on an arrangement clip changes its content length (`length`), but `end_time` stays fixed.
  - Long sections are built by tiling copies.
- `Clip.quantize(5, 1.0)` works. The grid argument uses the `Song.RecordingQuantization` values (5 = 1/16), so use `values.QUANTIZE_GRID`.
- `ClipSlot.create_audio_clip` on a MIDI track errors "Audio clips can only be created on audio tracks".

## Automation

- **Arrangement clips cannot hold editable envelopes.** `automation_envelope` returns None, and `create_automation_envelope` raises "Not a session clip or parameter belongs to another track".
- Session clips:
  - `create_automation_envelope(param)` and `insert_step(start, length, value)` work.
  - `Live.Envelope.EnvelopeEvent(time, value)` (positional or keyword; optional control coefficients for curves) plus `create_event(event)` work.
  - `value_at_time` returns parameter units.
  - `events_in_range` returns `(time, value)`, but for volume the stored value is an internal scale (0.25 reads back 0.036). Read with `value_at_time`; write in parameter units.
- Envelopes travel with `duplicate_clip_to_arrangement` (`has_envelopes` True on the copy), so automate in Session clips and then place them. The copy's envelope cannot be edited afterwards.

## Rendering by resampling (the bounce engine)

1. Create an audio track. On a **later tick**, set `input_routing_type` to the `Resampling` RoutingType, set monitoring to Off (2), and arm it.
2. **Disarm every other track.** An armed MIDI track records over its own clip.
3. Set `song.loop = False`, `metronome = False`, `current_song_time = start`, `record_mode = True`, then `start_playing()`. Song properties read back in the same tick still show the old state.
4. Stop with `stop_playing()` and `record_mode = False`. The recorded clip is in `track.arrangement_clips` and has a `file_path`. For an unsaved set, recordings land in `~/Music/Ableton/Live Recordings/<date time> Temp Project/Samples/Recorded/<track name> 0001 [<timestamp>].wav` (44.1 kHz, the Live sample rate).
5. **Timing: do not assume file sample 0 is the recording start.**
   - A first run measured no offset (a note at beat 4 landed at 2.0001 s).
   - WS-E later measured a **pre-roll** of 8704 samples (0.197 s at 120 BPM), likely after the audio interface changed. Pre-roll depends on device latency.
   - Locate the start with the clip itself. The bounce start sits at `clip.start_marker`, so the sample offset for arrangement time t is `clip.beat_to_sample_time(start_marker + (t - clip.start_time))`.
   - With that, bounces are sample-exact: master and stem are bit-identical and the lengths are exact.
6. `count_in_duration` was 0 (None). If it is non-zero, report it, because a count-in delays playback.

## Undo

`song.begin_undo_step()` / `end_undo_step()` around a command works. A command that creates a track, renames it and inserts a device is reverted by **one** `song.undo()`.

## Remote Script infrastructure lessons

- `_Framework.ControlSurface` already defines `_tasks` (a TaskGroup). Never reuse ControlSurface attribute names. The shell uses `_mcp_tasks`.
- Hot reload must strip submodule attributes from the package, including orphans that are no longer in `sys.modules`. Otherwise `from . import x` keeps returning stale modules. This is covered by `tests/unit/test_reload.py`.
- Live writes `__pycache__/*.cpython-311.pyc` next to the sources, and `.gitignore` covers it.

## Command latency: `Live.Base.Timer`

- `update_display` runs at about 10 Hz. Before the fix, round trips were quantised to 100 ms steps (median 299 ms with five builders active).
- `Live.Base.Timer(callback, interval_ms, repeat=False, start=False)` fires on Live's main thread.
  - At `interval=10` it measured a median gap of 10.3 ms and a maximum of 22 ms. Asking for 1 ms still gives about 10 ms.
  - An exception escaping the callback stops the timer for good.
- The shell drains the command queue from a 10 ms timer:
  - The callback is a lambda that looks up `self._on_task_timer` on every call, so reloads take effect.
  - The callback never raises.
  - `update_display` restarts the timer if it ever stops.
  - Tickers (async jobs) stay on `update_display`, at about 10 Hz.

## Song, transport, locators (WS-A)

- Writes to song properties take effect on the next tick. Reads in the same tick are stale for `current_song_time`, `punch_in`, `punch_out`, `loop` and `is_playing`. Example: `set_or_delete_cue` called in the same tick as a playhead write acts at the *old* position.
- Play from a position:
  - Setting `current_song_time` and then calling `continue_playing` while stopped ignores the moved playhead.
  - Instead, move the start marker (`start_time`) and call `start_playing` on the next tick. A jump while stopped also moves the start marker.
- The playhead cannot move past `song_length`. Cue points snap to 1/16 (152.4 becomes 152.5) and must lie within `song_length`. Locator edits need the transport stopped, so they are two-phase commands (`{"pending": ...}`, then re-call).
- Groove amounts:
  - `quantization_amount`, `timing_amount` and `random_amount` run 0–100.
  - `velocity_amount` runs −100 to 100.
  - `Song.groove_amount` tops out at 1.3125.
- `Song.back_to_arranger = False` stops the overriding Session clip while the transport keeps running.
- `capture_and_insert_scene` adds an unnamed scene after the selected scene.
- Four `tap_tempo` calls start playback.
- Next and previous locator jumps also stop at the loop edges.
- Live does not record empty undo steps, and its undo labels are only "Undo Custom Action".
- UI automation on this Mac: Accessibility is off for `claude.app`, and Automation of System Events is granted. Menu scripting needs both, so `ui_automation.status()` reports it unavailable without running osascript (no prompts).
- Not yet verified (gated test `ABLETON_MCP_TEST_UI=1`):
  - opening, creating and saving sets
  - the save-prompt button order
  - whether commands run while a modal dialog is open
  - whether opening a set re-creates the control surface

## Tracks, routing, mixer, meters (WS-B)

- **Meters are linear in dB:** `dBFS = 76 * raw - 70`.
  - Accurate to within 0.01 dB from -69.5 to +6 dBFS, for both output and input meters.
  - Raw 0 means -70 dBFS or lower. Raw 1 means +6 dBFS or higher.
  - `output_meter_level` is the maximum of left and right, held for about 1 s.
  - Measured with a sine WAV of known peak and the track volume swept.
- Routing timing, more precise than the earlier note:
  - A new track is missing from *other* tracks' routing lists until the next tick.
  - Its own lists are ready only if it was the first track created in that tick; later ones show `[""]`.
  - A MIDI track's output list reads empty in the tick an instrument is inserted.
  - `create_bus` is therefore two-phase: create, then route through the internal command `tracks_route_to_bus`. That makes it two undo steps.
- Setting a routing type refreshes its channel list immediately, so type and channel can be set in one call.
- Routing display names equal the track names. The "N-" prefix belongs to default names such as "6-Audio" and is not added by Live. Duplicate names are listed twice, and `RoutingType.attached_object` is the Track.
- A bus track only passes routed audio with monitoring "In". Use "No Input" as the bus input, so the interface input is not monitored.
- Return tracks:
  - Live re-adds the letter on every rename ("C-X" becomes "C-C-X"), so resolve and rename with `refs.return_bare_name`.
  - `duplicate_track` raises IndexError for return tracks.
  - Sends from a return to another return report state 1 (inactive).
- At the minimum, volume and send `display_value` read -70, not -inf. `values.volume_db` reports -inf there.
- `can_show_chains` needs an Instrument Rack with at least two chains.
- Packs add Max for Live devices to the browser's device categories, with `BrowserItem.source` set to the pack name. Examples: Bass and Poli from "Creative Extensions", "Granulator III", "PitchLoop89". `insert_device` rejects them, so `refs.native_device_names` keeps only built-in devices.
- When the audio interface disconnects, Live switches to "No Device": the transport freezes, Ext. In and Out disappear from the routing lists, and commands slow to about 0.3 s.

## Clips and notes (WS-C)

- `Clip.gain` is raw 0..1, where 0.4 = 0 dB.
  - Above 0.4: dB = 40·(g−0.4), reaching +24 dB at 1.0.
  - From about 0.03 to 0.4: dB = 42x − 200x², where x = g−0.4. That gives about −42.9 dB at 0.03.
  - Below that the curve steepens, reaching −inf at about 1e-4. Outside 0..1 raises "Gain is out of range". The tools invert the formula and bisect the display string below −43 dB.
- Loop and marker setters only behave while the clip is looping. Unlooped, the `loop_*` setters move the markers and the `start_marker` setter is ignored. `crop` keeps the region from `start_marker` to `loop_end`.
- Notes:
  - A note added at an existing pitch and start replaces it. A same-pitch overlap truncates the earlier note.
  - Velocity must be above 0 and at most 127.
  - `apply_note_modifications` accepts only the `MidiNoteVector` Live returned, not a Python list. Unknown ids raise "All given IDs must be present in clip".
- Fire and `stop_all_clips` take effect a tick later.
- Conversions:
  - `audio_to_midi_clip` is deferred. Its new track appears after the source and is polled by `clips_conversion_status`.
  - Drum-rack and Simpler conversions are synchronous. They append the track at the end, with no clip.
  - All three select the new track.
- Warp markers: `WarpMarker(sample_time=seconds, beat_time=beats)`, while `beat_to_sample_time` returns frames. Audio quantize regenerates the markers.
- Arrangement:
  - Overlapping inserts trim existing clips.
  - Copying between MIDI and audio tracks raises "Incompatible track types for clip duplication".
  - Session-to-arrangement copies span the loop for looping clips, and the markers for unlooped ones.
- Grooves: a clip's groove cannot be set back to None, and new MIDI clips come with the pool's groove assigned.
- Audio clips:
  - `warp_mode` must be one of `available_warp_modes`.
  - The same file came up warped once and unwarped another time, so set warping explicitly.

## Bounce engine (WS-E)

- `Song.back_to_arranger` can only be set to False, so the bounce cannot re-light "Back to Arrangement". It warns at start instead.
- Identify stem sources by `RoutingType.attached_object`, which is the Track.
  - Track, return and Main sources offer the channels `Pre FX`, `Post FX` and `Post Mixer`.
  - `Resampling` has one unnamed channel.
- Under heavy load (about 2 s per command), a new track's routing lists stayed empty for more than 5 s. The engine waits up to 15 s.
- The API can arm several tracks at once even with Exclusive Arm on.
- Live turns ":" into "_" in recording file names, and a recording adds two take lanes to the track.
- `Application.average_process_usage` is a percentage.
- ffmpeg:
  - `aac_at` accepts only 16-bit input.
  - `ebur128` reports silence as -70 LUFS and true peak to 0.1 dB.
- Timings:
  - A 2-bar bounce (4.4 s of audio) takes 7.1–7.7 s end to end.
  - For a 4-minute song: analysis 1.8 s, images 0.6 s, and a five-format release with limiting 19.7 s.
- A Remote Script reload during recording is safe: the ticker job state lives in `ctx.state`, and the bounce finishes and restores everything.

## Devices and browser (WS-D)

- `DeviceParameter.display_value` uses canonical units: Hz for frequencies, **ms for times** ("1.20 s" reads 1200).
  - `values.parse_display_number` normalizes "s" and "kHz" to these units.
  - `values.set_display_number` verifies the read-back and bisects when it does not match.
- `insert_device` rejects Max for Live devices, even the built-in ones that the browser lists as "Built-in":
  - effects: Align Delay, Envelope Follower, LFO, Shaper
  - MIDI effects: Envelope MIDI, Expression Control, MIDI Monitor, MPE Control, Note Echo, Shaper MIDI
  - drum synths: DS Clang, DS Clap, DS Cymbal, DS FM, DS HH, DS Kick, DS Snare, DS Tom
  - all pack devices
  - These load through `Browser.load_item`. `add_device` and `create_track(device=...)` fall back to it automatically.
- "Drum Sampler" inserts only under the name "DrumSampler".
- Meld's on/off parameter has the original name "On", not "Device On".
- A/B compare swaps the whole device state. Rack macros add and remove in steps of 2.
- Simpler's `reverse` and `crop` write new files and rename the device.
- Any read of a deleted device raises a Boost `ArgumentError`, not `AttributeError`.
- `Browser.load_item` targets:
  - It acts synchronously on the selected track.
  - Insert position: select the neighbour device and set `Track.View.device_insert_mode` to 1. The mode sticks, so reset it afterwards. Its getter returns True only for mode 0.
  - Drum pad: set `RackDevice.View.selected_drum_pad`, then load.
  - Session slot: set `Song.View.highlighted_clip_slot`. This only works while Session view is focused.
  - Loading an instrument replaces the track's instrument (in place when the type matches). A sample loaded onto a MIDI track becomes a Simpler.
  - `.alc` clips create a new track.
  - Hot-swap mode redirects loads, so exit it first.
- Browser size and scan time (main thread):
  - Core Library alone: 20.3k items in 0.6 s, cold.
  - With 12 packs: 48.2k items in 0.5 s, or 0.8 s when spread over 20 ms ticks (about 4 s wall clock).
  - The `full_refresh` listener never fired during testing. A pack-list poll and TTLs keep the search index fresh.

## Not yet spiked (owner)

- New, open and save set, and whether the control surface is re-instantiated (WS-A).
- `Browser.load_item` targets: drum pad, clip slot, hotswap (WS-D).
