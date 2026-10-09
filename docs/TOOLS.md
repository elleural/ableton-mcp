# AbletonMCP tools

Generated from the code by `scripts/gen_tool_docs.py`; do not edit by hand. 84 tools.
Conventions for every tool (addressing, units, errors) are in [PRD.md section 8](PRD.md#8-conventions-contract-for-every-tool).

## Status and overview

### `get_status()` *(read-only)*

Start here. Connection, Live and Remote Script versions, the open set (name, path), transport
(playing, position, tempo, loop), any open Live dialog with its message, active background jobs,
and capabilities: ffmpeg (needed by analyze_audio and create_release) and macOS UI automation
(needed by save_set, new_set and export_audio; `fix` says how to enable it).

When Live is unreachable it still answers, with connected: false and how to fix it. If `dialog`
is set, Live is waiting for an answer: respond_to_dialog.

### `get_song_overview(detail=False)` *(read-only)*

One-call map of the project: tempo, meter, key and scale, swing, loop, song length; every track
(index, name, kind, colour, mute/solo/arm, devices, non-empty Session slots with name and length,
arrangement clip count and extent); returns and master; scenes (name, tempo, signature, empty);
locators; the selection. Times come as beats plus "bar.beat.sixteenth".

detail=True adds every set_song setting, mixer levels (dB), pan and sends, device classes and
on/off, clip colours and arrangement clip lists. Use get_track or get_notes for more.

### `undo(steps=1)`

Undo the last `steps` actions in Live (1..100). Every AbletonMCP call that changes the set is one
undo step, so undo() reverts the previous call. Returns how many steps were undone plus can_undo and
can_redo. Live's history is shared with the user's own edits in Live.

### `redo(steps=1)`

Redo `steps` actions previously undone with undo (1..100). Returns how many were redone plus
can_undo and can_redo. Any new change clears the redo history.

### `respond_to_dialog(button)` *(destructive)*

Press a button on the dialog Live is showing (get_status reports its message and button count).

button: an index (0 = first button), or a name where Live's layout is known: "ok" on one-button
dialogs; "save", "dont_save" or "cancel" on Live's save-changes prompt. Destructive: "dont_save"
discards unsaved work, so confirm with the user first.

## Project lifecycle

### `open_set(path, discard_unsaved=False)` *(destructive)*

Open a Live Set (.als) in the running Live, replacing the current set. No UI permission needed.

If the current set has unsaved changes Live asks to save them: with discard_unsaved=False (default)
nothing is discarded, the prompt stays open and the call fails with what to do; discard_unsaved=True
answers "Don't Save". Destructive with discard_unsaved: confirm with the user first. Waits until the
set has loaded and returns it; then call get_song_overview.

### `new_set(discard_unsaved=False)` *(destructive)*

[UI automation] Start a new empty Live Set (File > New Live Set), replacing the current one.

Unsaved changes are refused unless discard_unsaved=True (then Live's save prompt is answered
"Don't Save"). Needs macOS UI automation: get_status shows whether it is available and how to enable
it. Destructive with discard_unsaved: confirm with the user first.

### `save_set(path=None)` *(destructive)*

[UI automation] Save the current Live Set; with `path`, save it as a new file ("~/Music/My Song.als").

Without path the set must already have a file. Save-as never overwrites an existing file; Live may
put the set in a new "<name> Project" folder. Verified through Live's file path or the file's
modification time. Needs macOS UI automation (see get_status).

### `export_audio(path, start, end)`

[UI automation, EXPERIMENTAL] Render the arrangement from `start` to `end` (beats or
"bar.beat.sixteenth") with Live's own offline File > Export Audio/Video, to `path` (".wav").

Sets the arrangement loop to the range (Live exports the loop brace) and restores it afterwards. The
file format and rendered track follow the Export dialog's last settings. Never overwrites a file.
Prefer bounce, which needs no UI permission. Needs macOS UI automation (see get_status).

## Song, transport, scenes, locators, grooves, selection

### `set_song(tempo=None, time_signature=None, key=None, scale=None, scale_mode=None, swing=None, groove_amount=None, metronome=None, loop=None, loop_start=None, loop_length=None, loop_end=None, punch_in=None, punch_out=None, launch_quantization=None, record_quantization=None, follow=None, record_mode=None, session_record=None, arrangement_overdub=None, session_automation_record=None, link=None, tempo_follower=None)`

Set song-wide settings in one undo step; returns every setting as Live now reports it.

tempo 20..999 BPM; time_signature "3/4"; key a root ("F#") or root plus scale ("A minor"); scale one of
Live's scales ("Minor", "Dorian", ...); swing 0..1; groove_amount 0..1.31; loop_start/loop_end times and
loop_length a length ("8 bars"), giving the arrangement loop (also the export range);
launch_quantization "none".."1/32" ("1 bar", "1/16"); record_quantization "none", "1/16", "1/8T"...;
follow = arrangement follows the playhead. record_mode arms arrangement recording. Example:
set_song(tempo=124, key="A minor", time_signature="4/4"). No arguments: read the settings.

### `transport(action, position=None)`

Control playback. action: "play" (from `position` if given), "continue", "stop", "jump" (to
`position`), "jump_to_next_locator", "jump_to_prev_locator", "play_selection", "stop_all_clips",
"back_to_arrangement" (stop Session clips overriding the arrangement and resume it), "tap_tempo",
"capture_midi" (recently played MIDI into a clip), "capture_scene" (playing clips into a new scene).

position: beats, "bar.beat.sixteenth" or a locator name. While stopped, play/jump move the start
marker. Returns the action plus the transport state read on Live's next tick.
Example: transport("play", position="17.1.1").

### `create_scene(index=-1, name=None, color=None, tempo=None, time_signature=None)`

Create a Session scene (a song section) at `index` (-1 = at the end), optionally named and coloured
(Live colour index 0..69 or "#RRGGBB"). tempo (BPM) and time_signature ("3/4") make Live switch to them
when the scene fires. Example: create_scene(name="Chorus", tempo=128).

### `set_scene(scene, name=None, color=None, tempo=None, time_signature=None)`

Change a scene (index or name): name, color (0..69 or "#RRGGBB"), tempo in BPM, time_signature
("7/8"). Pass tempo="off" or time_signature="off" so the scene keeps the song's tempo or meter.

### `fire_scene(scene, force_legato=False)`

Launch a scene (index or name): every clip in its row starts at the launch quantization, and its
tempo or time signature applies. Starts the transport. force_legato launches clips immediately in
legato. Audition with get_meters; stop with transport("stop_all_clips") or transport("stop").

### `delete_scene(scene)` *(destructive)*

Delete a scene (index or name) together with every clip in its row. Destructive: confirm with the
user before deleting their material. A set keeps at least one scene.

### `duplicate_scene(scene)`

Duplicate a scene (index or name) with its clips into a new scene right below it, and select it.
Returns the new scene; later scene indices shift by one.

### `create_locator(time, name=None)`

Add an arrangement locator (cue point) at `time` (beats or "bar.beat.sixteenth"), optionally named.
The transport must be stopped. Live snaps locators to the 1/16 grid, and only places them within the
song length. Locators are indexed in time order. Example: create_locator("17.1.1", "Chorus").

### `set_locator(locator, name)`

Rename a locator, addressed by index (time order) or by name. To move one, delete it and create it
again at the new time.

### `delete_locator(locator)` *(destructive)*

Delete a locator, addressed by index (time order) or by name. The transport must be stopped; the
playhead is put back afterwards.

### `get_grooves()` *(read-only)*

The groove pool: each groove's index, name, base grid and amounts (percent), plus the global groove
amount (0..1.31). Assign a groove to a clip with set_clip(groove=...).

### `set_groove(groove, name=None, base=None, quantize=None, random=None, timing=None, velocity=None)`

Edit a groove of the groove pool (index or name). base is the grid: "1/4", "1/8", "1/8T", "1/16",
"1/16T" or "1/32". Amounts are percent: quantize, timing and random 0..100, velocity -100..100.
The global amount is set_song(groove_amount=...).

### `select(track=None, scene=None, device=None, slot=None, view=None)`

Select in Live's UI so the user sees what you are working on: a track, a scene, a clip slot of
`track` (shows its clip in the Detail view), or a device of `track` (index, name or rack path); and
show a view: "Session", "Arrangement", "Detail", "Clip", "Devices" or "Browser". Pass slot or scene,
not both. With no arguments, returns the current selection and focused view.

### `show_message(text)`

Show a short message in Live's status bar (bottom of the window), e.g. to tell the user what the
agent is doing. It does not open a dialog.

## Tracks, mixer and routing

### `create_track(kind, name=None, index=-1, color=None, device=None)`

Create a track: kind "midi", "audio" or "return", optionally named, coloured and with a first device.

index: position among regular tracks (-1 = end; returns always go last). color: Live colour index
0..69 or "#RRGGBB". device: any device by name, case-insensitive ("Operator", "eq eight", "DS Kick");
native devices are inserted directly, Max for Live and pack devices are loaded through the browser.
Instruments and MIDI effects need a MIDI track. Returns the new track's ref, routing and arm state
(MIDI tracks can come up armed). Example: create_track("midi", "Bass", device="Operator").

### `get_track(track, detail=False)` *(read-only)*

Read one track: kind, colour, mute/solo/arm, monitoring, group membership, freeze state, input and
output routing, mixer (volume dB, pan, sends in dB by return letter), top-level devices (index, name,
class, on), non-empty Session slots, arrangement clip count and extent, and take lanes.

detail=True adds everything else: every slot and arrangement clip, full mixer, meters and flags.
track: index, name, "return:A" or "master".

### `set_track(track, name=None, color=None, arm=None, monitoring=None, fold=None, collapsed=None, input=None, input_channel=None, output=None, output_channel=None, show_chains=None)`

Change a track: name, colour, arm, monitoring ("in", "auto", "off"), fold (group tracks), collapsed
(Arrangement), show_chains (Instrument Rack), and input/output routing.

Routing takes display names from get_routing_options, matched case-insensitively ("Main", "Sends Only",
"Resampling", "No Input", a track name such as "Drum Bus" or a track index); channels like "1/2",
"Post FX" or a MIDI channel number. Set the type and its channel in one call.
Example: set_track("Vox", input="Ext. In", input_channel="1", monitoring="auto").

### `delete_track(track)` *(destructive)*

Delete a regular or return track with all its clips and devices. The master cannot be deleted.

Deleting a return also removes every track's send to it, and later returns move up a letter.
Destructive: confirm with the user before deleting their own work (undo reverts it).

### `duplicate_track(track, name=None)`

Duplicate a regular track with its devices, clips and mixer settings; the copy goes right after it
and is selected. Optionally name the copy. Live cannot duplicate return or master tracks.

### `get_routing_options(track)` *(read-only)*

Current input and output routing of a track, with the available types and channels.

Channels belong to the current type: after choosing another type with set_track, read again to see
its channels. Return, group and master tracks have output routing only.

### `create_bus(name, sources, color=None)`

Create a bus, Live's substitute for group tracks: a new audio track (monitoring "In", input
"No Input") at the end of the set, with every source track's output routed into it.

Mix the bus like any track (set_mixer, add_device). name must be unique. Sources need audio
output (a MIDI track needs an instrument). Reverting takes two undo steps.
Example: create_bus("Drum Bus", ["Kick", "Snare", "Hats"], color="#FF8800").

### `get_mixer(tracks=None)` *(read-only)*

Mixer state of every regular, return and master track (or only `tracks`) in one call: volume_db,
pan (-1..1 plus display), sends in dB keyed by return letter, mute, solo, arm, active (track
activator), crossfade, pan_mode and split pans; the master adds crossfader and cue_volume_db.
"-inf" means silence.

### `set_mixer(track, volume_db=None, volume=None, pan=None, sends=None, mute=None, solo=None, active=None, crossfade=None, pan_mode=None, left_pan=None, right_pan=None, crossfader=None, cue_volume_db=None)`

Set a track's mixer in one call and get the resulting mixer state back.

volume_db: up to +6, or "-inf" (or volume: raw 0..1). pan: -1..1 or "25L"/"C"/"50R". sends:
{return letter, index or name: dB up to 0, or "-inf"}. mute/solo (solo is not exclusive), active
(track activator), crossfade "A"/"none"/"B", pan_mode "stereo"/"split" with left_pan/right_pan.
Master only: crossfader (-1 = A .. 1 = B) and cue_volume_db.
Example: set_mixer("Bass", volume_db=-6, pan=-0.2, sends={"A": -18}).

### `get_meters(tracks=None)` *(read-only)*

Momentary peak levels of every track, return and master (or only `tracks`), read from Live's meters.

Output levels are post-fader dBFS: peak_db (max of left/right, held 1 s), left_db, right_db, plus Live's
raw 0..1 values (dBFS = 76 * raw - 70, so "-inf" means below -70 dBFS and 6.0 the meter top).
over_0db flags a peak at or above 0 dBFS. Audio tracks add input levels; MIDI tracks show MIDI activity
(0..1). Meters only move while the transport plays.

## Devices and racks

### `add_device(track, name, position=-1, chain=None)`

Insert a native Live device by name on a track, or into a rack chain.

name: case-insensitive ("Operator", "eq eight", "Drum Rack"). position: device index (-1 = end).
chain: a path to a rack chain alternating device and chain segments: "Instrument Rack/0",
"Drum Rack/C1" (a drum note gets a new chain if the pad is empty) or "Audio Effect Rack/new".
Instruments and MIDI effects need a MIDI track or MIDI rack chain. Max for Live devices listed with
Live's devices (LFO, DS Kick, ...) load through the browser. Presets and packs: load_from_browser.
Example: add_device("Bass", "Saturator").

### `get_devices(track)` *(read-only)*

Device tree of a track: every device with path ("1/0/0"), name_path ("Drum Rack/Kick/Simpler"),
class, type and on/off; racks with chains (recursively), visible macros and variation count; Drum Racks
with their non-empty pads (note, note name, pad and chain names). Pass a path as `device` to other tools.

### `get_device(track, device, parameters=True, detail=False)` *(read-only)*

One device in detail: parameters (index, value, display, range, items), type-specific properties
with their options (Simpler mode, Wavetable oscillators, Compressor sidechain routing, plug-in presets,
...), rack chains with mixer, pads, macros, variations and chain selector, and Simpler's sample
(file, markers, warping, slices).

device: index, name or path ("Drum Rack/C1/Simpler", "1/0/0"). parameters=False skips the parameter
list; detail=True adds parameter metadata, hidden macros, full option lists and sample detail.

### `set_device_parameters(track, device, values)`

Set several device parameters in one call; returns each new value and display string.

values: {parameter name or index: value}. Numbers are raw values (min/max from get_device). Strings are
display values with units ("-6 dB", "800 Hz", "1.2 kHz", "250 ms", "2.5 s", "30 %", "25L") or item
names of switches and choosers ("Sine", "On"). Names match exactly, then by original name, then a
unique substring. Failures are listed in "errors" without stopping the others.
Example: set_device_parameters("Bass", "Auto Filter", {"Frequency": "800 Hz", "Resonance": 0.4}).

### `set_device(track, device, enabled=None, name=None, collapsed=None, compare_b=None, properties=None)`

Change a device: enabled (on/off), name, collapsed, compare_b (A/B compare slot B) and the
type-specific properties get_device lists.

properties: {name: value}; option properties take an option name or index ("playback_mode":
"one_shot", "voice_mode": "Mono", "selected_preset_index": "Init"); routing properties take display
names ("input_routing_type": "Kick" for a Compressor sidechain). "sample.<name>" sets Simpler's sample
("sample.warping": true, "sample.warp_mode": "complex"); "view.<name>" sets view properties.
Failures are listed per property.

### `device_action(track, device, action, args=None)` *(destructive)*

Run a type-specific device function; args holds its named arguments.

Racks: insert_chain(index, name, note), add_macro, remove_macro, randomize_macros, store_variation,
recall_variation(index), recall_last_variation, delete_variation(index). Drum Racks: copy_pad(source,
destination), delete_chains(pad), to_midi_track(pad, name). Simpler: crop, reverse, warp_as(beats),
warp_double, warp_half, replace_sample(file_path), guess_playback_length, insert_slice/remove_slice
(time in frames or seconds), move_slice(time, to), clear_slices, reset_slices, to_drum_rack.
Looper: record, overdub, play, stop, clear, undo, double_length, half_length, double_speed, half_speed,
export_to_clip_slot(track, slot). Wavetable: get_modulation(target, source), set_modulation(target,
source, value), add_parameter_to_modulation_matrix(parameter). Plug-ins: parameter_names(begin, end).
A/B devices: save_ab_slot.

### `delete_device(track, device)` *(destructive)*

Delete a device (a rack with everything in it) from its track or chain; returns what remains.

Destructive: confirm with the user before deleting their own work (undo reverts it).

### `duplicate_device(track, device)`

Duplicate a device (racks with their contents) right after itself in its track or chain.

Live will not duplicate a track's instrument: use duplicate_track, or another Instrument Rack chain.

### `move_device(track, device, to_track=None, to_position=None, to_chain=None)`

Move a device within its chain, to another track, or into a rack chain.

to_track: destination track (default: the same track). to_position: index in the destination
(omitted or -1 = end). to_chain: a chain path in the destination track ("Drum Rack/C1",
"Audio Effect Rack/0", "Instrument Rack/new"). Live picks the nearest valid position (MIDI effects stay
before the instrument); instruments and MIDI effects cannot go onto audio tracks.

### `set_chain(track, device, chain, name=None, color=None, mute=None, solo=None, volume_db=None, pan=None, in_note=None, out_note=None, choke_group=None)`

Change a rack chain: name, colour, mute, solo, volume_db ("-inf" allowed), pan (-1..1 or "25L"), and
for Drum Rack chains in_note (the pad that plays it, as a note name or number: this moves the chain to
another pad), out_note and choke_group (0 = none, 1..16).

device: the rack (index, name or path). chain: index, name, drum note ("C1") or "return:0" for a
return chain. Example: set_chain("Drums", "Drum Rack", "C1", volume_db=-3, choke_group=1).

### `set_sidechain(track, source=None, channel='Post FX', threshold_db=-24.0, ratio=4.0, attack_ms=1.0, release_ms=120.0, enabled=True, device=None, model=None, sidechain_eq=None)`

Duck `track` whenever `source` plays: sidechain compression, e.g. a bass or pad pumping to the kick.

Uses `device`, else the track's first Compressor (only its sidechain is routable), else a new one at the end.
source: the trigger track, with audio output (for a kick in a drum track, that track). channel: "Post FX"
(default), "Pre FX" or "Post Mixer". Sets S/C On, threshold (dB), ratio, attack and release (ms);
enabled=False turns it off. model: "Peak", "RMS" or "Expand". sidechain_eq filters the trigger: "off", or
{"type", "freq" (Hz), "q", "gain" (dB)}; types: Low pass, High pass, Bell, Peak, Low Shelf, High Shelf.
A Compressor this adds gets Peak and a 120 Hz low pass, for a kick (other triggers: "off"); an existing one
keeps what you omit.
Example: set_sidechain("Bass", "Drums", threshold_db=-30, ratio=6, release_ms=150).

## Browser

### `search_browser(query, category='all', limit=25, refresh=False)` *(read-only)*

Search Live's browser by name: devices, presets, drum kits, samples, clips, plug-ins, Max for Live
devices and packs. Every word must appear in the name (or the path). Ranked results give name, path,
uri, category, kind (device, preset, rack_preset, sample, clip, max_device, plugin, folder),
is_loadable and is_device.

category: "all" or instruments, audio_effects, midi_effects, sounds, drums, samples, clips, plugins,
max_for_live, packs, user_library, current_project, user_folders. The index builds in the background
("truncated" until complete) and follows newly installed packs; refresh=True forces a rescan.
Load a result with load_from_browser(track, uri=...).

### `browse(path='', limit=100, offset=0)` *(read-only)*

List a browser folder. path "" lists the categories; "drums/Drum Hits/Kick" lists that folder (names
match case-insensitively, file extensions optional). Items give name, path, uri, kind, is_loadable and
is_device; page large folders with limit and offset.

### `load_from_browser(track, uri=None, path=None, query=None, position=None, drum_pad=None, slot=None)` *(destructive)*

Load a browser item onto a track, chosen by exactly one of uri or path (from search_browser or
browse) or query (the best loadable match).

Targets: by default devices and presets go on the track (an instrument, instrument preset or drum kit
replaces the track's instrument; a sample on a MIDI track becomes a Simpler). position: device index
to insert at. drum_pad: a note ("C1", 36) or pad name on the track's Drum Rack. slot: Session scene
index for a sample on an audio track (default: the first empty slot). Clips (.alc) load as a new track.
Returns the new or replaced devices, the pad or slot, and any created tracks.

## Clips and notes

### `create_clip(track, slot=None, at=None, length=None, name=None, color=None, file_path=None, notes=None, pattern=None)` *(destructive)*

Create a clip: MIDI in an empty Session `slot` (0-based scene index) or on the arrangement `at` a time; audio
from `file_path` on audio tracks. Optionally fill it in the same call: notes (as write_notes) and/or pattern (drum
steps, as write_drum_pattern).

length: MIDI only, beats or "N bars" (default 4 beats; a bare number is beats). at: beats, "bar.beat.sixteenth"
("9.1.1") or a locator name. MIDI ranges that overlap arrangement clips are refused (audio reports what it trimmed).
color: index 0..69 or "#RRGGBB". Returns the new clip (as get_clip).
Example: create_clip("Drums", slot=0, length="1 bar", pattern={"kick": "x---x---x---x---"}).

### `get_clip(track, slot=None, arrangement_clip=None, notes=False, limit=200)` *(read-only)*

Every property of one clip: name, colour, length (beats and bars), loop and markers, signature, launch mode and
quantization, legato, mute, velocity amount, groove, grid, playing state and automated parameters.

Audio clips add gain_db, pitch, warping, warp mode, file and warp markers. Arrangement clips give start and end in
beats and bars. notes=True adds up to `limit` notes (or use get_notes with filters).

### `set_clip(track, slot=None, arrangement_clip=None, name=None, color=None, looping=None, loop_start=None, loop_end=None, start_marker=None, end_marker=None, signature=None, launch_mode=None, launch_quantization=None, legato=None, muted=None, velocity_amount=None, groove=None, grid=None, grid_triplet=None, gain_db=None, pitch_coarse=None, pitch_fine=None, warping=None, warp_mode=None, ram_mode=None)`

Set clip properties; only the ones you pass change. Returns the clip as get_clip.

Times are clip beats or "bar.beat.sixteenth" (1.1.1 = clip start; seconds for unwarped audio). signature "3/4".
launch_mode: trigger, gate, toggle, repeat. launch_quantization: global, none, "1 bar", "1/4", ... grid: "1/16", ...
groove: groove pool name or index. Audio only: gain_db (-inf..+24), pitch_coarse (-48..48 semitones),
pitch_fine (-50..49 cents), warping, warp_mode (beats, tones, texture, repitch, complex, complex_pro), ram_mode.
Example: set_clip(track="Keys", slot=0, loop_end="3.1.1", launch_quantization="1 bar").

### `delete_clip(track, slot=None, arrangement_clip=None)` *(destructive)*

Delete a Session or arrangement clip. Destructive: confirm with the user before deleting their own material.

### `duplicate_clip(track, slot=None, arrangement_clip=None, to_track=None, to_slot=None, to_time=None, move=False)` *(destructive)*

Copy (or move=True) a clip: Session -> Session slot, Session -> arrangement, or arrangement -> arrangement.

to_slot: empty Session slot (default: next empty slot below, same track). to_time: arrangement time in beats or
"bar.beat.sixteenth" (arrangement sources default to right after themselves). to_track defaults to the same track.
Clip envelopes travel with the copy. Occupied slots and overlapping arrangement ranges are refused.
Example: duplicate_clip(track="Drums", slot=0, to_time="9.1.1").

### `fire_clip(track, slot)`

Launch the clip in a Session slot (starts at the next launch-quantization boundary; Live starts the transport).

Check the result with get_clip (state) or get_meters; stop with stop_clip or transport.

### `stop_clip(track, quantized=True)`

Stop the playing or triggered Session clips on a track (quantized=False stops immediately).

### `get_notes(track, slot=None, arrangement_clip=None, pitches=None, pitch_min=None, pitch_max=None, start=None, end=None, note_ids=None, limit=200)` *(read-only)*

Notes of a MIDI clip with note_id, pitch, name (C3 = 60), start, duration, velocity, probability,
velocity_deviation, release_velocity and mute, sorted by time.

Optional filters (combined): pitches (list), pitch_min/pitch_max (numbers or names), start/end (notes starting in
[start, end), clip beats or "bar.beat.sixteenth"), note_ids. Use the ids with edit_notes, delete_notes or
transform_notes. Example: get_notes(track="Bass", slot=0, start="2.1.1", end="3.1.1").

### `write_notes(track, notes, slot=None, arrangement_clip=None, mode='add', start=None, end=None)` *(destructive)*

Write MIDI notes into a clip. mode: "add", "replace" (clears the clip first) or "replace_range" (clears notes
starting in [start, end); defaults to the span of the new notes).

Each note: pitch (60 or "C3"), start (clip beats or "1.3.1"; 1.1.1 = clip start), duration (beats, "1/8", "1/16T"),
optional velocity=100, probability=1, velocity_deviation=0, release_velocity=64, mute=false. Chords:
"pitches": [...] or "chord": "Am7" (+ octave, inversion, voicing). music_theory progression "notes" fit as-is.
Example: [{"pitch": "C3", "start": 0, "duration": 1}, {"chord": "F", "start": 4, "duration": 4}].

### `edit_notes(track, edits, slot=None, arrangement_clip=None)`

Change existing notes by note_id (from get_notes), keeping their ids.

Each edit: {"note_id": 12, ...} plus any of pitch, start, duration, velocity, probability, velocity_deviation,
release_velocity, mute. Example: edit_notes(track="Keys", slot=0, edits=[{"note_id": 12, "velocity": 90, "pitch": "E3"}]).
For relative changes on many notes use transform_notes.

### `delete_notes(track, slot=None, arrangement_clip=None, note_ids=None, pitches=None, pitch_min=None, pitch_max=None, start=None, end=None, all=False)` *(destructive)*

Delete notes from a MIDI clip by note_ids, pitches, pitch_min/pitch_max and/or a start/end time range
(notes starting in [start, end)), or every note with all=True. Filters combine; at least one is required.

### `transform_notes(track, operation, slot=None, arrangement_clip=None, note_ids=None, pitches=None, pitch_min=None, pitch_max=None, start=None, end=None, semitones=None, steps=None, grid=None, amount=None, swing=None, timing=None, velocity=None, seed=None, factor=None, offset=None, value=None, random=None)`

Transform notes in place (ids kept). Filters as in get_notes select the notes (default: all).

operation and its options:
transpose: semitones, or steps (scale degrees in the song's key and scale).
quantize: grid ("1/16", "1/8T"), amount 0..1 (default 1), swing 0..1 (delays every second grid line).
humanize: timing (+/- beats, or "10ms"), velocity (+/- spread), seed.
velocity: factor (multiply), offset (add), value (set), random (+/- spread), seed.
legato; reverse (within start/end or the loop); stretch: factor (around start or loop start); shift: offset (beats).

### `write_drum_pattern(track, pattern, slot=None, arrangement_clip=None, steps_per_beat=4, velocities=None, swing=0.0, mode='replace')` *(destructive)*

Write drums from step strings, repeated across the clip's loop: {"Kick": "x---x---x---x---", "Snare": "----x-------x---"}.

Steps: "x" hit, "X" accent, "o" ghost, "-" or "." rest (spaces and "|" ignored); steps_per_beat=4 means 16ths.
Drum names match the track's Drum Rack pads (case-insensitive, "kick" finds "Kick 808"), else General MIDI
(kick 36, snare 38, clap 39, closed hat 42, open hat 46, crash 49, ride 51, toms); notes like "C1" or 36 work too.
velocities: {"x": 100, "X": 127, "o": 60}. swing 0..1 delays every second step. mode: "replace" (those drums' notes) or "add".

### `clip_action(track, action, slot=None, arrangement_clip=None, args=None)` *(destructive)*

Run a clip function. Actions and args:
crop (keeps the loop, or the marker range); duplicate_loop (doubles the loop and its content);
duplicate_region {start, length, destination, pitch?, transpose?} (MIDI);
quantize {grid "1/16", amount 0..1, pitch?} (MIDI notes, or audio warp markers; uses the song's swing);
add_warp_marker {beat_time, sample_time? seconds}, move_warp_marker {beat_time, distance}, remove_warp_marker {beat_time};
audio_to_midi {type: melody|harmony|drums, name?}, drum_rack_from_audio {name?}, simpler_track_from_audio {name?}
(these create a new track and return it).

## Automation

### `write_automation(track, parameter, slot=None, arrangement_clip=None, device=None, points=None, shape=None, start=None, end=None, clear_range=True, units='display')` *(destructive)*

Automate a parameter inside a clip (clip envelope) from points or a shape; returns sampled values.

parameter: "volume", "pan", "send:A", or a device parameter with `device`. Times are clip beats or
"bar.beat.sixteenth" (1.1.1 = clip start). points: [{time, value}]; two points at one time make a jump.
shape: {type: ramp|sine|triangle|square|saw|steps, from, to, period ("1 bar"), steps: [values]} over
start..end (default: the clip loop). units "display": dB, Hz, ms, %, pan -1..1, item names; "raw":
internal values. clear_range replaces breakpoints in the range. Envelopes loop with the clip and
travel into the arrangement; arrangement clips can only edit envelopes they already carry.
Example: write_automation("Pad", "volume", slot=0, shape={"type": "ramp", "from": -24, "to": 0}).

### `get_automation(track, slot=None, arrangement_clip=None, parameter=None, device=None, samples=16)` *(read-only)*

List the parameters a clip automates; with `parameter`, also its breakpoints and `samples` values
across the clip loop, in display units (dB, Hz, pan ...). Works for Session clips and for the envelopes
arrangement clips carry. Example: get_automation("Pad", slot=0, parameter="volume").

### `clear_automation(track, slot=None, arrangement_clip=None, parameter=None, device=None)` *(destructive)*

Remove a clip's envelope for one parameter, or every envelope when `parameter` is omitted.
Works for Session and arrangement clips. Example: clear_automation("Pad", slot=0, parameter="volume").

## Arrangement

### `get_arrangement(start=None, end=None, tracks=None, limit=200)` *(read-only)*

The arrangement timeline: each track's clips (index for arrangement_clip refs, name, start and end in
beats and bars, length, looping, type, colour, envelopes), plus locators, loop region and song length.

start/end keep only clips overlapping that range (beats or "bar.beat.sixteenth"); tracks limits the
tracks. At most `limit` clips are listed. Example: get_arrangement(start="9.1.1", end="17.1.1").

### `arrange_from_scenes(sections, start='1.1.1', clear=False, tracks=None, locators=True)` *(destructive)*

Build the arrangement from scenes: sections play one after another from `start`, each placing
every track's clip from its scene for the section's length.

sections: [{scene (index or name), bars (or length: beats / "8 bars"), name?}]. Looping clips loop
to fill a section exactly, at any length; one-shot clips play once. Clip envelopes travel along.
A track's range is overwritten where it has a clip; clear=True first empties the whole range on the
tracks taking part (those with a clip in a listed scene, or `tracks`). locators=True adds a locator per
section, named after it; the transport is stopped first if it is playing. Arrangement clips are
independent copies: write notes and automation in the Session clips BEFORE arranging (or re-run with
clear=True after editing them). Returns undo_steps. Example: arrange_from_scenes([{"scene": "Intro",
"bars": 4}, {"scene": "Verse", "bars": 8}]). Verify with get_arrangement.

### `clear_arrangement(tracks=None, start=None, end=None, mode='trim', all_tracks=False)` *(destructive)*

Delete arrangement clips by track and time range. Destructive: confirm before deleting the user's work.

mode "trim" (default) empties exactly start..end: clips inside are deleted and clips crossing an edge
are cut there. "overlapping" deletes every clip touching the range, whole; "inside" deletes only clips
entirely within it. Omit start/end for the whole timeline. Pass tracks, or all_tracks=True to clear
every track. Times are beats, "bar.beat.sixteenth" or a locator name.
Example: clear_arrangement(tracks=["Bass"], start="Chorus", end="Outro").

## Export, analysis and release

### `bounce(start=0, end=None, tail='2 s', stems=None, include_returns=False, name=None, output_dir=None)` *(destructive)*

Render the arrangement to WAV in real time (resampling inside Live): the master plus optional stems.

start/end: beats, "bar.beat.sixteenth" or a locator name; end defaults to the last arrangement event
rounded up to a bar. tail: time after end for reverb and delay tails: beats, "1 bar", or seconds ("2 s").
stems: "all" (unmuted tracks with audio), or track names or indices ("return:A" works); include_returns
adds every return. Files go to output_dir (default ~/Music/AbletonMCP/Bounces/<name>/) as
"<name> - Master.wav" and "<name> - <stem>.wav", replacing same-named files. The song plays audibly;
transport, loop, metronome and arm states are restored. Returns a job: poll get_bounce_status(wait=50)
until phase is "done" (polling is required: it delivers the files and removes the temporary tracks).
Example: bounce(stems=["Drums", "Bass"], name="Demo").

### `get_bounce_status(wait=0)`

Progress of the current bounce; when recording ends, deliver the files and return their paths.

wait: seconds (0-50) to long-poll until the bounce finishes. While running: phase, progress (0-1) and
eta_seconds. When done: folder, manifest (bounce.json) and files [{stem, path, duration_seconds,
peak_dbfs, silent}]; delivery trims each take sample-exactly to the range and removes the temporary
"[bounce]" tracks. failed carries error; cancelled after cancel_bounce. Next: analyze_audio(path).

### `cancel_bounce()`

Cancel a running bounce: recording stops, transport and arm states are restored, and the temporary
"[bounce]" tracks are removed. With no bounce running, removes leftover "[bounce]" tracks.

### `analyze_audio(path=None, sections=None, images=False, take=None, strict=False, spec=None)` *(read-only)*

Measure audio so you can judge a mix without hearing it: a file (path) or a listening-loop take.

path: loudness (LUFS, LU, dBTP), levels, stereo, spectrum (% per band), a loudness curve, dropouts and notes;
sections: "locators" or [{name, start, end}] in seconds. take (id or "latest", from capture): the spec's
checks on tier sums T1..T5 (game-style looping): loudness -14 LUFS / -1 dBTP, key, mono sub, stems+returns
cancel the mix, tempo consistency; reports tier ladder, masking, analyser bands, phone survival.
strict adds delivery-file checks (duration, seam, start, 48 kHz/24-bit). images=True adds two PNGs.

### `create_release(source, title, artist, album=None, year=None, genre=None, track_number=None, artwork=None, target_lufs=-14.0, true_peak=-1.0, formats=None, output_dir=None, stems=None)` *(destructive)*

Master and package a finished song: normalise a bounced master, encode, tag, embed artwork, write release.json.

Loudness goes to target_lufs (-14 for streaming) with true peak at most true_peak dBTP: linear gain when
peaks allow, else a 4x-oversampled true-peak limiter. formats (default all): wav24, wav16 (triangular
dither), flac (24-bit), mp3 (320 kbps CBR), aac (256 kbps .m4a). artwork: JPEG or PNG, embedded in
FLAC/MP3/M4A. stems: "auto" (the bounce's other files) or paths, copied unprocessed to Stems/. Output:
~/Music/AbletonMCP/Releases/<artist> - <title>/, replacing same-named files. release.json holds tempo,
key, loudness per file and sha256 checksums.

## Listening loop

### `capture(set=None, variation=None, tempo=None, tempos=None, mode='tap', bars=None, note=None, spec=None, wait=300, cancel=False, analyze=True)`

Record the set's stems and mix in real time (audible) into a take, then analyze it (listening loop).

Plans from the spec (default "nova"): each part's Session clip for the tempo's band is fired and recorded
from its track output with every return and the main mix; the second cycle is kept, so tails are folded.
tempo (default: the set's middle tempo) or tempos=[...]/"all" for a sweep (one take per tempo).
variation: "A", "B" or all. mode "solo" records each part soloed (with return effects; slower).
bars shortens the loop for quick checks. note: what changed (ledger). Leaves the set as found.
Waits up to `wait` s (max 600); call capture() with no arguments to keep waiting for it or get its result.

### `analyze_notes(set=None, band=None, parts=None, tempo=None, spec=None, image=True)` *(read-only)*

Check the stem clips' notes against the spec (no audio, under a second): run after every note edit.

Fails: set.names, set.unwarped, notes.in_key (A minor, G# over E), notes.chord_tones (bass), notes.clash
(stems a semitone apart), notes.shared_stem (the shared pad over every progression), notes.loop_length.
Warns: grid, lead rests. Reports kick pattern, density, motif. band: "LOW"/"MID"/"HIGH" or a tempo
(default every band). parts: ids like "bassA". image adds a piano roll coloured by chord-tone status.

### `compare(a='latest', b='best', blind=False, variation=None, spec=None)` *(read-only)*

Differences between two takes, or a take and the spec: what improved, regressed or is within noise.

a: take id or "latest"; b: take id, "best" (the kept take of a's set, tempo and variation), "spec",
"refs" (the top tier against the range of every stored reference's full sections), "refs:sparse" (tier T2
against their sparse sections), "refs:<kind>:<tier>" (any tier), or "ref:<name>[:<section>]" (one
reference, default section "full"). Against references, dynamics are information only.
Spectral metrics are loudness-matched. Keep a change only when nothing regressed beyond noise.
blind=True returns an X/Y packet without ids or statuses for a fresh judge subagent (the key is saved).

### `takes(action='list', take=None, set=None, tempo=None, variation=None, limit=10, notes=True, parameters=True, dry_run=False)` *(destructive)*

The take history (ledger), the kept best take, and restoring an earlier take's notes and parameters.

action "list": newest takes (filter by set, tempo, variation) with verdicts and which is best.
"keep": mark `take` as the best of its set, tempo and variation (compare(b="best") uses it).
"restore": write `take`'s snapshot back into its part tracks: clip notes, device parameters, mixer
(one undo step). Devices added or removed since are listed, not undone; plugin state is not covered.
Destructive: restore overwrites the current notes and settings (dry_run=True previews).

## Listening loop: references and meter

### `ref(action='status', name=None, uri=None, file=None, sections=None, refresh=False, position=None, wait=300.0)` *(destructive)*

References the soundtrack is compared against: measured once, kept as numbers, never as audio.

action:
- "measure": play Spotify track(s) in the Spotify app (uri: spotify:track:..., an open.spotify.com/track
  link, or a list) and measure each through the audio interface's loopback. Takes as long as the music;
  waits up to `wait` s, then call ref() again. Cached per track (refresh=True re-measures).
  sections={"drop": [72, 102]} measures only those spans (seconds). Stop Live first.
- "add": measure a file Frederic owns (file=path; sections optional).
- "list": stored references, their sections (track, full, sparse) and the shared envelope.
- "play" (uri, position s) / "pause": the Spotify app, for listening.
- "setup": what is left of the one-time setup (Spotify's normalisation and crossfade off, volume 100,
  macOS alerts through another output). Only Frederic confirms it: `uv run ears ref setup --confirm`.
- "status" (default) / "cancel": the running measurement. "delete": remove reference `name`.
Then compare(take, "refs") compares a take's top tier against all references.

### `meter(seconds=10.0, source='live')` *(read-only)*

Measure what the Mac is playing now, for `seconds` (at most 120), in memory; numbers only.

source "live": Live's output through the same loopback as the references (start playback first, e.g.
fire_scene); includes integrated loudness and true peak. source "external": another player such as
Spotify; level-independent numbers only (its level depends on the player's volume and normalisation).

## Music theory

### `music_theory(operation, key=None, scale=None, chord=None, progression=None, notes=None, octave=3, octaves=1, inversion=0, voicing='close', beats_per_chord=4.0, voice_leading=False)` *(read-only)*

Music theory without touching Live (C3 = 60). operation:
scale: key ("A", "F# dorian") + scale (any Live scale name, "minor", "blues"...) -> notes, pitches from `octave`.
chord: chord symbol ("Am7", "F#m7b5", "C7sus4", "Cadd9", "C/E"), or a numeral ("V7") with key; inversion, voicing
(close, open, drop2, drop3, spread), octave -> pitches.
progression: key ("C", "A minor") + numerals ("ii7-V7-Imaj7", "i-bVI-bIII-bVII", "V7/V") or chord symbols;
beats_per_chord, voice_leading -> chords plus "notes" ready for write_notes.
notes: note names or numbers -> MIDI number, names, frequency. list: available scales, chords, voicings.

## Object-model escape hatch

### `lom_get(path, properties=None)` *(read-only)*

Read an object of Live's object model by path, with all property values or only `properties`.

Paths use Max for Live style: "live_set tracks 0 mixer_device volume", "live_set view selected_track",
"live_app view". Lists are summarised as counts and names. Use the curated tools first; this reaches
anything they do not cover.

### `lom_set(path, property, value)` *(destructive)*

Set a writable property of the object at `path`. Pass {"path": "..."} as value to refer to an object.

### `lom_call(path, method, args=None)` *(destructive)*

Call a function of the object at `path` with positional `args` ({"path": "..."} refers to an object).

Example: lom_call("live_set", "create_scene", [-1]). Returns the result, with a path for any object returned.

### `lom_describe(path='live_set')` *(read-only)*

List the properties (with whether each is writable) and functions available at `path`, with Live's docs.

### `reload_remote_script(full=False)`

Developer tool: hot-reload the Remote Script's code inside Live without restarting it.

full=True also reloads the script's shell module. A module that fails to import is reported and the
previous code keeps running.
