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
5. **Timing is sample-aligned.** A note at beat 4 at 120 BPM appears at 2.0001 s in the file, so file sample 0 is the recording start time and no offset trim is needed.
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

## Not yet spiked (owner)

- New, open and save set, and whether the control surface is re-instantiated (WS-A).
- `Browser.load_item` targets: drum pad, clip slot, hotswap (WS-D).
