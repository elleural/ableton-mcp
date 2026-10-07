# Live Object Model documentation digest (Cycling 74 docs, Live 12.4.5)

Compiled from https://docs.cycling74.com/apiref/lom/ . Semantics and version notes for the documented subset; the runtime digest (live_api_12.4.6.md) is authoritative for what exists.

# Ableton Live Object Model (LOM) digest

- Source: https://docs.cycling74.com/apiref/lom/ and its 45 class pages (Cycling '74 docs; fetched 2026-10-06).
- Docs state: "This document refers to Ableton Live version 12.4.5".
- Totals: 45 classes, 64 children, 361 properties, 163 functions.
- Notation: `child NAME (type, access)`, `prop NAME (type, access)`, `fn NAME(params) -> returns`. Access = get/set/observe as stated in the docs; `?` after a param name = optional; `= X` = documented default; `[since Live X]` = docs version note ('Available since Live X' in the docs). `|` separates doc lines/paragraphs.
- Completeness: every item's full doc text is included. Only compaction: the identical note-dictionary key list returned by several Clip note getters is spelled out once (get_all_notes_extended) and referenced afterwards; the JSON keeps the verbatim `doc_text` for every function.

### Doc quirks worth knowing
- Version notes: the only version markers in the docs are 'Available since Live X' (11.0 x31 items, 11.0.6, 11.1, 11.1.2, and 12.3 x7 items; Groove class page: 11.0). Nothing is marked newer than 12.3 even though the index says Live 12.4.5, and there are no 'deprecated' markers anywhere.
- Replacement notes (old functions are no longer documented): Clip.get_notes_extended replaces get_notes; Clip.get_selected_notes_extended replaces get_selected_notes; Clip.remove_notes_extended replaces remove_notes; Clip.apply_note_modifications replaces modifying notes via remove_notes + set_notes. Clip.deselect_all_notes text still mentions replace_selected_notes (not documented).
- Groove lists scalar members (base, name, quantization_amount, random_amount, timing_amount, velocity_amount) under 'Children'.
- WavetableDevice: oscillator_1_wavetable_category, oscillator_2_wavetable_category, oscillator_1_wavetable_index, oscillator_2_wavetable_index have no type in the docs.
- this_device is a root-path alias (canonical path 'live_set tracks N devices M'); the docs say its class is Device; it has no members of its own.
- Types are quoted as written: symbol, unicode, long, int, float, bool, bang, dict, dictionary, dict/bang, list, 'list of X', StringVector, plus LOM class names. 'list of X' children are lists of LOM objects.
- Function parameters/returns are free text in the docs (no formal signatures); params/returns in this digest are parsed from that text, with reviewed overrides for note/dict-style APIs (see doc_text on each function for the verbatim text). Parameter types are null when the docs give none.
- Application.get_*_version examples in the docs (9.1.2) are just illustrative examples, not the documented Live version.
- Song.get_current_smpte_song_time: the docs page has a stray formatting glitch splitting the return text ('*hours:min:sec*' ... '[symbol]'); the digest rejoins it.

### Class index
- Application: 2 children, 5 properties, 6 functions
- Application.View: 0 children, 2 properties, 8 functions
- Chain: 2 children, 11 properties, 2 functions
- ChainMixerDevice: 4 children, 0 properties, 0 functions
- Clip: 1 children, 48 properties, 28 functions
- Clip.View: 0 children, 2 properties, 4 functions
- ClipSlot: 1 children, 11 properties, 7 functions
- CompressorDevice: 0 children, 4 properties, 0 functions (inherits Device per docs)
- ControlSurface: 0 children, 1 properties, 9 functions
- CuePoint: 0 children, 2 properties, 1 functions
- Device: 2 children, 11 properties, 2 functions
- Device.View: 0 children, 1 properties, 0 functions
- DeviceIO: 0 children, 5 properties, 0 functions
- DeviceParameter: 0 children, 12 properties, 3 functions
- DriftDevice: 0 children, 29 properties, 0 functions (inherits Device per docs)
- DrumCellDevice: 0 children, 1 properties, 0 functions (inherits Device per docs)
- DrumChain: 0 children, 3 properties, 0 functions (inherits Chain per docs)
- DrumPad: 1 children, 4 properties, 1 functions
- Eq8Device: 0 children, 3 properties, 0 functions (inherits Device per docs)
- Eq8Device.View: 0 children, 1 properties, 0 functions (inherits Device.View per docs)
- Groove: 6 children, 0 properties, 0 functions
- GroovePool: 1 children, 0 properties, 0 functions
- HybridReverbDevice: 0 children, 8 properties, 0 functions (inherits Device per docs)
- LooperDevice: 0 children, 5 properties, 11 functions (inherits Device per docs)
- MaxDevice: 0 children, 4 properties, 3 functions (inherits Device per docs)
- MeldDevice: 0 children, 4 properties, 0 functions (inherits Device per docs)
- MixerDevice: 9 children, 2 properties, 0 functions
- PluginDevice: 0 children, 3 properties, 0 functions (inherits Device per docs)
- RackDevice: 5 children, 7 properties, 9 functions (inherits Device per docs)
- RackDevice.View: 2 children, 2 properties, 0 functions (inherits Device.View per docs)
- RoarDevice: 0 children, 3 properties, 0 functions (inherits Device per docs)
- Sample: 0 children, 22 properties, 6 functions
- Scene: 1 children, 10 properties, 3 functions
- ShifterDevice: 0 children, 2 properties, 0 functions (inherits Device per docs)
- SimplerDevice: 1 children, 11 properties, 7 functions (inherits Device per docs)
- SimplerDevice.View: 0 children, 1 properties, 0 functions (inherits Device.View per docs)
- Song: 9 children, 48 properties, 34 functions
- Song.View: 8 children, 2 properties, 1 functions
- SpectralResonatorDevice: 0 children, 7 properties, 0 functions (inherits Device per docs)
- TakeLane: 1 children, 1 properties, 2 functions
- this_device: 0 children, 0 properties, 0 functions
- Track: 7 children, 40 properties, 10 functions
- Track.View: 1 children, 2 properties, 1 functions
- TuningSystem: 0 children, 6 properties, 0 functions
- WavetableDevice: 0 children, 15 properties, 5 functions (inherits Device per docs)

## Application
- URL: https://docs.cycling74.com/apiref/lom/application/
- Canonical path(s): `live_app`
- Description: This class represents the Live application. It is reachable by the root path `live_app`.
- Counts: 2 children, 5 properties, 6 functions

### Children
- child view (Application.View, get)
- child control_surfaces (list of ControlSurface, get/observe): A list of the control surfaces currently selected in Live's Preferences. | If None is selected in any of the slots or the script is inactive (e.g. when Push2 is selected, but no Push is connected), id 0 will be returned at those indices.

### Properties
- prop current_dialog_button_count (int, get): The number of buttons in the current message box.
- prop current_dialog_message (symbol, get): The text of the current message box (empty if no message box is currently shown).
- prop open_dialog_count (int, get/observe): The number of dialog boxes shown.
- prop average_process_usage (float, get/observe): Reports Live's average CPU load. | Note that Live's CPU meter shows the audio processing load but not Live's overall CPU usage.
- prop peak_process_usage (float, get/observe): Reports Live's peak CPU load. | Note that Live's CPU meter shows the audio processing load but not Live's overall CPU usage.

### Functions
- fn get_bugfix_version() -> the 2 in Live 9.1.2
- fn get_document() -> the current Live Set
- fn get_major_version() -> the 9 in Live 9.1.2
- fn get_minor_version() -> the 1 in Live 9.1.2
- fn get_version_string() -> the text 9.1.2 in Live 9.1.2
- fn press_current_dialog_button(index): Press the button with the given index in the current dialog box.

## Application.View
- URL: https://docs.cycling74.com/apiref/lom/application_view/
- Canonical path(s): `live_app view`
- Description: This class represents the aspects of the Live application related to viewing the application.
- Counts: 0 children, 2 properties, 8 functions

### Properties
- prop browse_mode (bool, get/observe): 1 = Hot-Swap Mode is active for any target.
- prop focused_document_view (unicode, get/observe): The name of the currently visible view in the focused Live window ('Session' or 'Arranger').

### Functions
- fn available_main_views() -> `view names` [list of symbols]: This is a constant list of view names to be used as an argument when calling other functions: `Browser Arranger Session Detail Detail/Clip Detail/DeviceChain`.
- fn focus_view(view_name): Shows named view and focuses on it. You can also pass an empty view_name “ ", which refers to the Arrangement or Session View (whichever is visible in the main window).
- fn hide_view(view_name): Hides the named view. You can also pass an empty view_name “ ", which refers to the Arrangement or Session View (whichever is visible in the main window).
- fn is_view_visible(view_name) -> [bool] Whether the specified view is currently visible
- fn scroll_view(direction: int, view_name, modifier_pressed: bool): Not all views are scrollable, and not in all directions. Currently, only the `Arranger`, `Browser`, `Session`, and `Detail/DeviceChain` views can be scrolled. | You can also pass an empty view_name `" "`, which refers to the Arrangement or Session View (whichever view is visible).
  - param direction: 0 = up, 1 = down, 2 = left, 3 = right
  - param modifier_pressed: If view_name is "Arranger" and modifier_pressed is 1 and direction is left or right, then the size of the selected time region is modified, otherwise the position of the playback cursor is moved.
- fn show_view(view_name)
- fn toggle_browse(): Displays the device chain and the browser and activates Hot-Swap Mode for the selected device. Calling this function again deactivates Hot-Swap Mode.
- fn zoom_view(direction: int, view_name, modifier_pressed: bool): Only the Arrangement and Session Views can be zoomed. For Session View, the behaviour of zoom_view is identical to scroll_view. You can also pass an empty view_name “ ", which refers to the Arrangement or Session View (whichever is visible in the main window).
  - param direction: 0 = up, 1 = down, 2 = left, 3 = right
  - param modifier_pressed: If `view_name` is 'Arrangement', `modifier_pressed` is 1, and `direction` is left or right, then the size of the selected time region is modified, otherwise the position of the playback cursor is moved. If `view_name` is Arrangement and `modifier_pressed` is 1 and `direction` is up or down, then only the height of the highlighted track is changed, otherwise the height of all tracks is changed.

## Chain
- URL: https://docs.cycling74.com/apiref/lom/chain/
- Canonical path(s): `live_set tracks N devices M chains L`; `live_set tracks N devices M return_chains L`; `live_set tracks N devices M chains L devices K chains P ...`; `live_set tracks N devices M return_chains L devices K chains P ...`
- Description: This class represents a group device chain in Live.
- Counts: 2 children, 11 properties, 2 functions

### Children
- child devices (Device, get/observe)
- child mixer_device (ChainMixerDevice, get)

### Properties
- prop color (int, get/set/observe): The RGB value of the chain's color in the form `0x00rrggbb` or (2^16 * red) + (2^8) * green + blue, where red, green and blue are values from 0 (dark) to 255 (light). | When setting the RGB value, the nearest color from the color chooser is taken.
- prop color_index (long, get/set/observe): The color index of the chain.
- prop is_auto_colored (bool, get/set/observe): 1 = the chain will always have the color of the containing track or chain.
- prop has_audio_input (bool, get)
- prop has_audio_output (bool, get)
- prop has_midi_input (bool, get)
- prop has_midi_output (bool, get)
- prop mute (bool, get/set/observe): 1 = muted (Chain Activator off)
- prop muted_via_solo (bool, get/observe): 1 = muted due to another chain being soloed.
- prop name (unicode, get/set/observe)
- prop solo (bool, get/set/observe): 1 = soloed (Solo switch on) | does not automatically turn Solo off in other chains.

### Functions
- fn delete_device(index: int): Delete the device at the given index.
- fn insert_device(device_name: symbol, target_index?: int) [since Live 12.3]: Attempts to insert the device specified by `device_name` at the given index in the chain. If no index is provided, attempts to insert the device at the end. Throws an error if insertion is not possible. | `device_name` is the name as it appears in the UI of Live. | Not all indices are valid. As can be expected, indices outside of the range defined by the current length of the device chain are invalid, but there are other limitations: for example, a MIDI effect can't be inserted after an instrument. The rule of thumb is that if an index would be invalid when inserting using the mouse, it's invalid here. | At the moment, only native Live devices can be inserted. Max for Live devices and plug-in are not supported.

## ChainMixerDevice
- URL: https://docs.cycling74.com/apiref/lom/chainmixerdevice/
- Canonical path(s): `live_set tracks N devices M chains L mixer_device`; `live_set tracks N devices M return_chains L mixer_device`
- Description: This class represents a chain's mixer device in Live.
- Counts: 4 children, 0 properties, 0 functions

### Children
- child sends (list of DeviceParameter, get/observe): [in Audio Effect Racks and Instrument Racks only] | For Drum Racks, otherwise empty.
- child chain_activator (DeviceParameter, get)
- child panning (DeviceParameter, get): [in Audio Effect Racks and Instrument Racks only]
- child volume (DeviceParameter, get): [in Audio Effect Racks and Instrument Racks only]

## Clip
- URL: https://docs.cycling74.com/apiref/lom/clip/
- Canonical path(s): `live_set tracks N clip_slots M clip`; `live_set tracks N arrangement_clips M`
- Description: This class represents a clip in Live. It can be either an audio clip or a MIDI clip in the Arrangement or Session View, depending on the track / slot it lives in.
- Counts: 1 children, 48 properties, 28 functions

### Children
- child view (Clip.View, get)

### Properties
- prop available_warp_modes (list, get): Returns the list of indexes of the Warp Modes available for the clip. Only valid for audio clips.
- prop color (int, get/set/observe): The RGB value of the clip's color in the form `0x00rrggbb` or (2^16 * red) + (2^8) * green + blue, where red, green and blue are values from 0 (dark) to 255 (light). | When setting the RGB value, the nearest color from the clip color chooser is taken.
- prop color_index (int, get/set/observe): The clip's color index.
- prop end_marker (float, get/set/observe): The end marker of the clip in beats, independent of the loop state. Cannot be set before the start marker.
- prop end_time (float, get/observe): The end time of the clip. For Session View clips, if Loop is on, this is the Loop End, otherwise it's the End Marker. For Arrangement View clips, this is always the position of the clip's rightmost edge in the Arrangement.
- prop gain (float, get/set/observe): The gain of the clip (range is 0.0 to 1.0). Only valid for audio clips.
- prop gain_display_string (symbol, get): Get the gain display value of the clip as a string (e.g. "1.3 dB"). Can only be called on audio clips.
- prop file_path (symbol, get): Get the location of the audio file represented by the clip. Only available for audio clips.
- prop groove (Groove, get/set/observe) [since Live 11.0]: Get/set/observe access to the groove associated with this clip.
- prop has_envelopes (bool, get/observe): Get/observe whether the clip has any automation.
- prop has_groove (bool, get) [since Live 11.0]: Returns true if a groove is associated with this clip.
- prop is_session_clip (bool, get): 1 = The clip is a Session clip. | A clip can be either an Arrangement or a Session clip.
- prop is_arrangement_clip (bool, get): 1 = The clip is an Arrangement clip. | A clip can be either an Arrangement or a Session clip.
- prop is_take_lane_clip (bool, get): 1 = The clip is a Take Lane clip. | Returns true if the clip is on a Take Lane. Take Lane clips are also Arrangement clips.
- prop is_audio_clip (bool, get): 0 = MIDI clip, 1 = audio clip
- prop is_midi_clip (bool, get): The opposite of `is_audio_clip`.
- prop is_overdubbing (bool, get/observe): 1 = clip is overdubbing.
- prop is_playing (bool, get/set): 1 = clip is playing or recording.
- prop is_recording (bool, get/observe): 1 = clip is recording.
- prop is_triggered (bool, get): 1 = Clip Launch button is blinking.
- prop launch_mode (int, get/set/observe) [since Live 11.0]: The Launch Mode of the Clip as an integer index. Available Launch Modes are: | 0 = Trigger (default) | 1 = Gate | 2 = Toggle | 3 = Repeat
- prop launch_quantization (int, get/set/observe) [since Live 11.0]: The Launch Quantization of the Clip as an integer index. Available Launch Quantization values are: | 0 = Global (default) | 1 = None | 2 = 8 Bars | 3 = 4 Bars | 4 = 2 Bars | 5 = 1 Bar | 6 = 1/2 | 7 = 1/2T | 8 = 1/4 | 9 = 1/4T | 10 = 1/8 | 11 = 1/8T | 12 = 1/16 | 13 = 1/16T | 14 = 1/32
- prop legato (bool, get/set/observe) [since Live 11.0]: 1 = Legato Mode switch in the Clip's Launch settings is on.
- prop length (float, get): For looped clips: loop length in beats. Otherwise it's the distance in beats from start to end marker. Makes no sense for unwarped audio clips.
- prop loop_end (float, get/set/observe): For looped clips: loop end. | For unlooped clips: clip end.
- prop loop_jump (bang, observe): Bangs when the clip play position is crossing the loop start marker (possibly projected into the loop).
- prop loop_start (float, get/set/observe): For looped clips: loop start. | For unlooped clips: clip start. | loop_start and loop_end are in absolute clip beat time if clip is MIDI or warped. The 1.1.1 position has beat time 0. If the clip is unwarped audio, they are given in seconds, 0 is the time of the first sample in the audio material.
- prop looping (bool, get/set/observe): 1 = clip is looped. Unwarped audio cannot be looped.
- prop muted (bool, get/set/observe): 1 = muted (i.e. the Clip Activator button of the clip is off).
- prop name (symbol, get/set/observe)
- prop notes (bang, observe): Observer sends bang when the list of notes changes. | Available for MIDI clips only.
- prop warp_markers (dict/bang, get/observe) [since Live 11.0]: Observing this property outputs a bang when the Warp Markers change. | Getting this property returns the Warp Markers in a dict as pairs of sample times and beat times: | `sample_time` : [float] the position in seconds in the audio sample file. | `beat_time` : [float] the beat this sample position corresponds to. | To calculate the position in the sample file that corresponds to any given Clip time in beats, Live goes through these steps: | - Find the Warp Marker with a `beat_time` below the given Clip time and the one above it. | - Get the ratio of the Clip time in beats between the beat times of these two markers. | - Get the `sample_time` for each of these two markers. | - Interpolate between these two sample times with the same ratio to get the file sample position in seconds. | The last Warp Marker in the dict is not visible in the Live interface. This hidden marker is used to calculate the BPM of the last segment. | Available for audio clips only. (note: Getting is available since Live 11.0.)
- prop pitch_coarse (int, get/set/observe): Pitch shift in semitones ("Transpose"), -48 ... 48. | Available for audio clips only.
- prop pitch_fine (float, get/set/observe): Extra pitch shift in cents ("Detune"), -50 ... 49. | Available for audio clips only.
- prop playing_position (float, get/observe): Current playing position of the clip. | For MIDI and warped audio clips, the value is given in beats of absolute clip time. The clip's beat time of 0 is where 1 is shown in the bar/beat/16th time scale at the top of the clip view. | For unwarped audio clips, the position is given in seconds, according to the time scale shown at the bottom of the clip view. | Stopped clips have a playing position of 0.
- prop playing_status (bang, observe): Observer sends bang when playing/trigger status changes.
- prop position (float, get/observe): Get and set the clip's loop position. The value will always equal loop_start, however setting this property, unlike setting loop_start, preserves the loop length.
- prop ram_mode (bool, get/set/observe): 1 = an audio clip’s RAM switch is enabled.
- prop sample_length (int, get): Length of the Clip's sample, in samples.
- prop sample_rate (float, get): Get the Clip's sample rate.
- prop signature_denominator (int, get/set/observe)
- prop signature_numerator (int, get/set/observe)
- prop start_marker (float, get/set/observe): The start marker of the clip in beats, independent of the loop state. Cannot be set behind the end marker.
- prop start_time (float, get/observe): The start time of the clip, relative to the global song time. The value is in beats. | For Arrangement View clips, this is the offset within the arrangement. For Session View clips, this is the time the clip was started. Note that what is reported is the start_time of the currently playing clip on the track, regardless of which clip. | When a Session View clip's playback position was offset by clicking in its time ruler in the Clip Detail View or moving its start marker, its start_time may be negative. This allows using the start_time as an offset when calculating the clip's current playback position based on the global song time.
- prop velocity_amount (float, get/set/observe) [since Live 11.0]: How much the velocity of the note that triggers the clip affects its volume, 0 = no effect, 1 = full effect.
- prop warp_mode (int, get/set/observe): The Warp Mode of the clip as an integer index. Available Warp Modes are: | 0 = Beats Mode | 1 = Tones Mode | 2 = Texture Mode | 3 = Re-Pitch Mode | 4 = Complex Mode | 5 = REX Mode | 6 = Complex Pro Mode | Available for audio clips only.
- prop warping (bool, get/set/observe): 1 = Warp switch is on. | Available for audio clips only. | Technical note: Internally, Live will defer the setting of this property. This has the consequence that if you are sequencing API calls from a single event, the actual order of operations may differ from what you'd intuitively expect. Most of the time this should be transparent to you, but if you run into issues, please report them.
- prop will_record_on_start (bool, get): 1 for MIDI clips which are in triggered state, with the track armed and MIDI Arrangement Overdub on.

### Functions
- fn add_new_notes(dictionary: dict) -> a list of note IDs of the added notes [since Live 11.0]: For MIDI clips only.
  - param dictionary: Key "notes" [list of note specification dictionaries]
    - key notes (list of note specification dictionaries): Note specification dictionaries have the following keys (see item_keys).
      - item key pitch (int): the MIDI note number, 0...127, 60 is C3.
      - item key start_time (float): the note start time in beats of absolute clip time.
      - item key duration (float): the note length in beats.
      - item key velocity (float, optional) default 100: the note velocity, 0 ... 127 *(100 by default)*.
      - item key mute (bool, optional) default 0: 1 = the note is deactivated *(0 by default)*.
      - item key probability (float, optional) default 1.0: the chance that the note will be played: | 1.0 = the note is always played | 0.0 = the note is never played | *(1.0 by default)*.
      - item key velocity_deviation (float, optional) default 0.0: the range of velocity values at which the note can be played: | 0.0 = no deviation; the note will always play at the velocity specified by the *velocity* property | -127.0 to 127.0 = the note will be assigned a velocity value between *velocity* and *velocity + velocity_deviation*, inclusive; if the resulting range exceeds the limits of MIDI velocity (0 to 127), then it will be clamped within those limits | *(0.0 by default)*.
      - item key release_velocity (float, optional) default 64: the note release velocity *(64 by default)*.
- fn add_warp_marker(dict: dict): Only available for warped Audio Clips. Adds the specified warp marker, if possible. | The warp marker is specified as a dict which can have a `beat_time` and a `sample_time` key, both associated with float values. | The `sample_time` key may be omitted; in this case, Live will calculate the appropriate sample time to create a warp marker at the specified beat time without changing the Clip's playback timing, similar to what would happen if you were to double-click in the upper half of the Sample Display in Clip View. | If `sample_time` is specified, certain limitations must be taken into account: | - The sample time must lie within the range *[0, s]*, where *s* is the sample's length. The `sample_length` Clip property helps with this. | - The sample time must lie between the left and right adjacents markers' respective sample times (this is a logical constraint). | - Within these constraints, there are limitations on the resulting segments' BPM. The allowed BPM range is *[5, 999]*.
  - param dict: Warp marker specification; may have a `beat_time` and a `sample_time` key, both float. `sample_time` may be omitted (Live then computes it to create a marker at that beat time without changing playback timing).
    - key beat_time (float)
    - key sample_time (float, optional): may be omitted; must lie in [0, sample length], between neighbouring markers' sample times; resulting segment BPM must be within [5, 999]
- fn apply_note_modifications(dictionary: dict) [since Live 11.0]: The list of note dictionaries passed to the function can be a subset of notes in the clip, but will be ignored if it contains any notes that are not present in the clip. | For MIDI clips only. (note: Available since Live 11.0. Replaces modifying notes with remove_notes followed by set_notes.)
  - param dictionary: Key "notes" [list of note dictionaries] as returned from `get_notes_extended`.
    - key notes (list of note dictionaries): as returned from `get_notes_extended`; may be a subset of the notes in the clip, but is ignored if it contains any notes not present in the clip
- fn clear_all_envelopes(): Removes all automation in the clip.
- fn clear_envelope(device_parameter: id): Removes the automation of the clip for the given parameter.
- fn crop(): Crops the clip: if the clip is looped, the region outside the loop is removed; if it isn't, the region outside the start and end markers.
- fn deselect_all_notes(): Call this before replace_selected_notes if you just want to add some notes. | Output: | `deselect_all_notes id 0` | For MIDI clips only.
- fn duplicate_loop(): Makes the loop two times longer by moving loop_end to the right, and duplicates both the notes and the envelopes. If the clip is not looped, the clip start/end range is duplicated. Available for MIDI clips only.
- fn duplicate_notes_by_id(list: list of note IDs) [since Live 11.1.2]: Duplicates all notes matching the given note IDs. | Provided note IDs must be associated with existing notes in the clip. Existing notes can be queried with `get_notes_extended`. | The selection of notes will be duplicated to *destination_time*, if provided. Otherwise the new notes will be inserted after the last selected note. This behavior can be observed when duplicating notes in the Live GUI. | If the *transposition_amount* is specified, the duplicated notes will be transposed by the number of semitones. | Available for MIDI clips only.
  - param list: pass a plain list of note IDs
  - alt-form param dictionary: Alternative call form: pass a dictionary instead of the list, with the keys below.
    - key note_ids (list of note IDs): as returned from `get_notes_extended`
    - key destination_time (float/int, optional)
    - key transposition_amount (int, optional)
- fn duplicate_region(region_start: float/int, region_length: float/int, destination_time: float/int, pitch?: int, transposition_amount?: int): Duplicate the notes in the specified region to the *destination_time*. Only notes of the specified pitch are duplicated or all if *pitch* is -1. If the *transposition_amount* is not 0, the notes in the region will be transposed by the *transpose_amount* of semitones. Available for MIDI clips only.
- fn fire(): Same effect as pressing the Clip Launch button.
- fn get_all_notes_extended(dict?: dict) -> a dictionary of all of the notes in the clip, regardless of where they are positioned with respect to the start/end markers and the loop start/loop end, as a list of note dictionaries [since Live 11.1]: It is possible to optionally provide a single [dict] argument to this function, containing a single key-value pair: the key is "return" and the associated value is a list of the note properties as listed above in the discussion of the returned note dictionaries, e.g. ["note_id", "pitch", "velocity"]. The effect of this will be that the returned note dictionaries will only contain the key-value pairs for the specified properties, which can be useful to improve patch performance when processing large notes dictionaries. | For MIDI clips only.
  - param dict: Optional single dict argument with one key, "return", whose value is a list of the note properties (e.g. ["note_id", "pitch", "velocity"]) to include in each returned note dictionary; useful to improve patch performance for large note dictionaries.
    - key return (list of note property names, optional): e.g. ["note_id", "pitch", "velocity"]
  - each returned note dictionary has keys:
    - note_id (int): the unique note identifier.
    - pitch (int): the MIDI note number, 0...127, 60 is C3.
    - start_time (float): the note start time in beats of absolute clip time.
    - duration (float): the note length in beats.
    - velocity (float): the note velocity, 0 ... 127.
    - mute (bool): 1 = the note is deactivated.
    - probability (float): the chance that the note will be played: | 1.0 = the note is always played; | 0.0 = the note is never played.
    - velocity_deviation (float): the range of velocity values at which the note can be played: | 0.0 = no deviation; the note will always play at the velocity specified by the *velocity* property | -127.0 to 127.0 = the note will be assigned a velocity value between *velocity* and *velocity + velocity_deviation*, inclusive; if the resulting range exceeds the limits of MIDI velocity (0 to 127), then it will be clamped within those limits.
    - release_velocity (float): the note release velocity.
- fn get_notes_by_id(list: list of note IDs) -> a dictionary of notes associated with the provided IDs, as a list of note dictionaries [since Live 11.0]: Provided note IDs must be associated with existing notes in the clip. Existing notes can be queried with `get_notes_extended`. | It is possible to optionally provide the argument to this function in the form of a dictionary instead. The dictionary must include the "note_ids" key associated with a list of [int]s, which are the ID values you would like to pass to the function. | If you use this method, you can optionally provide an additional key-value pair: the key is "return" and the associated value is a list of the note properties as listed above in the discussion of the returned note dictionaries, e.g. ["note_id", "pitch", "velocity"]. The effect of this will be that the returned note dictionaries will only contain the key-value pairs for the specified properties, which can be useful to improve patch performance when processing large notes dictionaries. | For MIDI clips only.
  - param list: a list of note IDs (must belong to existing notes in the clip)
  - alt-form param dictionary: Alternative call form: a dictionary instead of the list.
    - key note_ids (list of int): the note IDs to return
    - key return (list of note property names, optional): e.g. ["note_id", "pitch", "velocity"]; returned note dictionaries then only contain these properties
  - each returned note dictionary has the same keys as get_all_notes_extended (note_id, pitch, start_time, duration, velocity, mute, probability, velocity_deviation, release_velocity)
- fn get_notes_extended(from_pitch: int, pitch_span: int, from_time: float, time_span: float) -> a dictionary of notes that have their start times in the given area, as a list of note dictionaries [since Live 11.0]: It is possible to optionally provide the arguments to this function in the form of a single dictionary instead. The dictionary must include all of the parameter names given above as its keys; the associated values are the parameter values you wish to pass to the function. | If you use this method, you can optionally provide an additional key-value pair: the key is "return" and the associated value is a list of the note properties as listed above in the discussion of the returned note dictionaries, e.g. ["note_id", "pitch", "velocity"]. The effect of this will be that the returned note dictionaries will only contain the key-value pairs for the specified properties, which can be useful to improve patch performance when processing large notes dictionaries. | For MIDI clips only. (note: Available since Live 11.0. Replaces get_notes.)
  - param from_time: in beats
  - param time_span: in beats
  - alt-form param dictionary: Alternative call form: a single dictionary whose keys are the four parameter names above, optionally plus "return" (list of note properties to include, e.g. ["note_id", "pitch", "velocity"]).
  - each returned note dictionary has the same keys as get_all_notes_extended (note_id, pitch, start_time, duration, velocity, mute, probability, velocity_deviation, release_velocity)
- fn get_selected_notes_extended(dict?: dict) -> a dictionary of the selected notes in the clip, as a list of note dictionaries [since Live 11.0]: It is possible to optionally provide a single [dict] argument to this function, containing a single key-value pair: the key is "return" and the associated value is a list of the note properties as listed above in the discussion of the returned note dictionaries, e.g. ["note_id", "pitch", "velocity"]. The effect of this will be that the returned note dictionaries will only contain the key-value pairs for the specified properties, which can be useful to improve patch performance when processing large notes dictionaries. | For MIDI clips only. (note: Available since Live 11.0. Replaces get_selected_notes.)
  - param dict: Optional single dict argument with one key, "return", whose value is a list of the note properties (e.g. ["note_id", "pitch", "velocity"]) to include in each returned note dictionary.
    - key return (list of note property names, optional): e.g. ["note_id", "pitch", "velocity"]
  - each returned note dictionary has the same keys as get_all_notes_extended (note_id, pitch, start_time, duration, velocity, mute, probability, velocity_deviation, release_velocity)
- fn move_playing_pos(beats: float): Jumps by given amount, unquantized. | Unwarped audio clips, recording audio clips and recording non-overdub MIDI clips cannot jump.
  - param beats: relative jump distance in beats. Negative beats jump backwards.
- fn move_warp_marker(beat_time: float, beat_time_distance: float): Moves the warp marker specified by *beat_time* the specified beat time distance.
- fn quantize(quantization_grid: int, amount: float): Quantizes all notes in the clip to the quantization_grid taking the song's swing_amount into account.
- fn quantize_pitch(pitch: int, quantization_grid: int, amount: float): Same as *quantize*, but only for notes in the given pitch.
- fn remove_notes_by_id(list: list of note IDs) [since Live 11.0]: Deletes all notes associated with the provided IDs. | Provided note IDs must be associated with existing notes in the clip. Existing notes can be queried with `get_notes_extended`.
- fn remove_notes_extended(from_pitch: int, pitch_span: int, from_time: float, time_span: float) [since Live 11.0]: Deletes all notes that start in the given area. `from_time` and `time_span` are given in beats. (note: Available since Live 11.0. Replaces remove_notes.)
- fn remove_warp_marker(beat_time: float): Removes the warp marker at the given beat time.
- fn scrub(beat_time: float): Scrub the clip to a time, specified in beats. This behaves exactly like scrubbing with the mouse; the scrub will respect Global Quantization, starting and looping in time with the transport. The scrub will continue until stop_scrub() is called.
- fn select_all_notes(): Use this function to process all notes of a clip, independent of the current selection. | Output: | `select_all_notes id 0` | For MIDI clips only.
- fn select_notes_by_id(list: list of note IDs) [since Live 11.0.6]: Selects all notes associated with the provided IDs. | Note that this function will *not* print a warning or error if the list contains nonexistent IDs.
- fn set_fire_button_state(state: bool): If the state is set to 1, Live simulates pressing the clip start button until the state is set to 0, or until the clip is otherwise stopped.
- fn stop(): Same effect as pressing the stop button of the track, but only if this clip is actually playing or recording. If this clip is triggered or if another clip in this track is playing, it has no effect.
- fn stop_scrub(): Stops an active scrub on a clip.

## Clip.View
- URL: https://docs.cycling74.com/apiref/lom/clip_view/
- Canonical path(s): `live_set tracks N clip_slots M clip view`
- Description: Representing the view aspects of a Clip.
- Counts: 0 children, 2 properties, 4 functions

### Properties
- prop grid_is_triplet (bool, get/set): Get/set whether the clip is displayed with a triplet grid.
- prop grid_quantization (int, get/set): Get/set the grid quantization.

### Functions
- fn hide_envelope(): Hide the Envelopes box.
- fn select_envelope_parameter(DeviceParameter): Select the specified device parameter in the Envelopes box.
- fn show_envelope(): Show the Envelopes box.
- fn show_loop(): If the clip is visible in Live's Detail View, this function will make the current loop visible there.

## ClipSlot
- URL: https://docs.cycling74.com/apiref/lom/clipslot/
- Canonical path(s): `live_set tracks N clip_slots M`
- Description: This class represents an entry in Live's Session View matrix. | The properties `playing_status`, `is_playing` and `is_recording` are useful for clip slots of Group Tracks. These are always empty and represent the state of the clips in the tracks within the Group Track.
- Counts: 1 children, 11 properties, 7 functions

### Children
- child clip (Clip, get): `id 0` if slot is empty

### Properties
- prop color (long, get/observe): The color of the first clip in the Group Track if the clip slot is a Group Track slot.
- prop color_index (long, get/observe): The color index of the first clip in the Group Track if the clip slot is a Group Track slot.
- prop controls_other_clips (bool, get/observe): 1 for a Group Track slot that has non-deactivated clips in the tracks within its group. | Control of empty clip slots doesn't count.
- prop has_clip (bool, get/observe): 1 = a clip exists in this clip slot.
- prop has_stop_button (bool, get/set/observe): 1 = this clip stops its track (or tracks within a Group Track).
- prop is_group_slot (bool, get): 1 = this clip slot is a Group Track slot.
- prop is_playing (bool, get): 1 = playing_status != 0, otherwise 0.
- prop is_recording (bool, get): 1 = playing_status == 2, otherwise 0.
- prop is_triggered (bool, get/observe): 1 = clip slot button (Clip Launch, Clip Stop or Clip Record) or button of contained clip are blinking.
- prop playing_status (int, get/observe): 0 = all clips in tracks within a Group Track stopped or all tracks within a Group Track are empty. | 1 = at least one clip in a track within a Group Track is playing. | 2 = at least one clip in a track within a Group Track is playing or recording. | Equals 0 if this is not a clip slot of a Group Track.
- prop will_record_on_start (bool, get): 1 = clip slot will record on start.

### Functions
- fn create_audio_clip(path): Given an absolute path to a valid audio file in a supported format, creates an audio clip that references the file in the clip slot. Throws an error if the clip slot doesn't belong to an audio track or if the track is frozen.
- fn create_clip(length): Length is given in beats and must be a greater value than 0.0. Can only be called on empty clip slots in MIDI tracks.
- fn delete_clip(): Deletes the contained clip.
- fn duplicate_clip_to(target_clip_slot: ClipSlot): Duplicates the slot's clip to the given clip slot, overriding the target clip slot's clip if it's not empty.
- fn fire(record_length?, launch_quantization?): Fires the clip or triggers the Stop Button, if any. Starts recording if slot is empty and track is armed. Starts recording of armed and empty tracks within a Group Track if Preferences->Launch->Start Recording on Scene Launch is ON. If *record_length* is provided, the slot will record for the given length in beats. *launch_quantization* overrides the global quantization if provided.
- fn set_fire_button_state(state: bool): 1 = Live simulates pressing of Clip Launch button until the state is set to 0 or until the slot is stopped otherwise.
- fn stop(): Stops playing or recording clips in this track or the tracks within the group, if any. It doesn't matter on which slot of the track you call this function.

## CompressorDevice
- URL: https://docs.cycling74.com/apiref/lom/compressordevice/
- Inherits (per docs text): Device — "A CompressorDevice shares all of the children, functions and properties of a Device; listed below are the members unique to it."
- Description: This class represents a Compressor device in Live. | A CompressorDevice shares all of the children, functions and properties of a Device; listed below are the members unique to it.
- Counts: 0 children, 4 properties, 0 functions

### Properties
- prop available_input_routing_channels (dict, get/observe): The list of available source channels for the compressor's input routing in the sidechain. It's represented as a dictionary with the following key: | `available_input_routing_channels` [list] | The list contains dictionaries as described in *input_routing_channel*.
- prop available_input_routing_types (dict, get/observe): The list of available source types for the compressor's input routing in the sidechain. It's represented as a dictionary with the following key: | `available_input_routing_types` [list] | The list contains dictionaries as described in *input_routing_type*.
- prop input_routing_channel (dict, get/set/observe): The currently selected source channel for the compressor's input routing in the sidechain. It's represented as a dictionary with the following keys: | `display_name` [symbol] | `identifier` [symbol] | Can be set to all values found in the compressor's *available_input_routing_channels*.
- prop input_routing_type (dict, get/set/observe): The currently selected source type for the compressor's input routing in the sidechain. It's represented as a dictionary with the following keys: | `display_name` [symbol] | `identifier` [symbol] | Can be set to all values found in the track's *available_input_routing_types*.

## ControlSurface
- URL: https://docs.cycling74.com/apiref/lom/controlsurface/
- Canonical path(s): `control_surfaces N`
- Description: A ControlSurface can be reached either directly by the root path `control_surfaces N` or by getting a list of active control surface IDs, via calling *get control_surfaces* on an Application object. | The latter list is in the same order in which control surfaces appear in Live's Link/MIDI Preferences. Note the same order is not guaranteed when getting a control surface via the `control_surfaces N` path. | A control surface can be thought of as a software layer between the Live API and, in this case, Max for Live. Individiual controls on the surface are represented by objects that can be grabbed and released via Max for Live, to obtain and give back exclusive control (see *grab_control* and *release_control*). In this way, parts of the hardware can be controlled via Max for Live while other parts can retain their default functionality. | Additionally, Live offers a special `MaxForLive` control surface that has a *register_midi_control* function. Using this, Max for Live developers can set up entirely custom control surfaces by adding and grabbing arbitrary controls.
- Counts: 0 children, 1 properties, 9 functions

### Properties
- prop pad_layout (symbol, get/observe): The active pad layout. | On Push 2 and 3, the layout can be changed with the Note and Session buttons and depends on the loaded instrument. Layout variants can be selected by pressing the Layout button. | Available layouts are: | - Melodic mode - the device chain is empty or an Instrument is loaded | `note.melodic.64_notes` - Melodic: 64 Notes | `note.melodic.64_notes_and_macro_variations` - Melodic: 64 Notes + Macro Variations | `note.melodic.sequencer` - Melodic: Sequencer | `note.melodic.sequencer_and_32_notes` - Melodic: Sequencer + 32 Notes | - Drums mode - a Drum Rack is loaded | `note.drums.macro_variations` - Drums: Macro Variations | `note.drums.64_pads` - Drums: 64 Pads | `note.drums.loop_selector` - Drums: Loop Selector | `note.drums.16_velocities` - Drums: 16 Velocities | `note.drums.16_pitches` - Drums: 16 Pitches | - Session mode - the Session button was pressed | `session` - Session is active

### Functions
- fn get_control(name) -> the control with the given name
- fn get_control_names() -> the list of all control names
- fn grab_control(control): Take ownership of the *control*. This releases all standard functionality of the control, so that it can be used exclusively via Max for Live.
- fn grab_midi(): Forward MIDI messages received by the control surface script from the control surface to Max for Live. | Note: the control surface script will only receive those channel messages from Live's engine that it explicitly requests. For example, a script might use a specific note message to toggle transport in Live; it will thus request that this note message be forwarded to it from Live. | Messages used for purely real-time purposes, on the other hand, will often bypass the script and instead just be sent to Live's tracks; this is true, for example, of Push's pads in Note (but not Session) mode. Accordingly, the API object will not output these real-time pad messages; to work with track messages, use objects such as `midiin`.
- fn register_midi_control(name: symbol, status: int, number: int) -> the LOM ID associated with the control: (*MaxForLive* control surface only) Register a MIDI control defined by *status* and *number*. Supported status codes are *144* (note on), *176* (continuous control) and *224* (pitchbend). | Once a control is registered and grabbed via *grab_control*, Live will forward associated MIDI messages that it receives to Max for Live. Max for Live can send values to the control (e.g. to light an LED) by calling *send_value* on the control object.
- fn release_control(control): Re-establishes the standard functionality for the control.
- fn release_midi(): Stop forwarding MIDI messages received from the control surface to Max for Live.
- fn send_midi(midi_message: list of int): Send *midi_message* to the control surface.
- fn send_receive_sysex(sysex_message: list of int, timeout?: symbol, int = 0.2): Send *sysex_message* to the control surface and await a response. | If the message is followed by the word *timeout* and a float, this sets the response timeout accordingly. The default timeout value is 0.2. | If the response times out and MIDI has not been grabbed via *grab_midi*, it's not forwarded to Max for Live. If MIDI has been grabbed via Max for Live, received messages are always forwarded, but the timeout is still reported.
  - param timeout: Optional by implication (docs: if the message is followed by the word *timeout* and a float, this sets the response timeout; the default timeout value is 0.2). Docs list it without '(optional)'.

## CuePoint
- URL: https://docs.cycling74.com/apiref/lom/cuepoint/
- Canonical path(s): `live_set cue_points N`
- Description: Represents a locator in the Arrangement View.
- Counts: 0 children, 2 properties, 1 functions

### Properties
- prop name (symbol, get/set/observe)
- prop time (float, get/observe): Arrangement position of the marker in beats.

### Functions
- fn jump(): Set current Arrangement playback position to marker, quantized if song is playing.

## Device
- URL: https://docs.cycling74.com/apiref/lom/device/
- Canonical path(s): `live_set tracks N devices M`; `live_set tracks N devices M chains L devices K`; `live_set tracks N devices M return_chains L devices K`
- Description: This class represents a MIDI or audio device in Live.
- Counts: 2 children, 11 properties, 2 functions

### Children
- child parameters (list of DeviceParameter, get/observe): Only automatable parameters are accessible. See DeviceParameter to learn how to modify them.
- child view (Device.View, get)

### Properties
- prop can_have_chains (bool, get): 0 for a single device | 1 for a device Rack
- prop can_have_drum_pads (bool, get): 1 for Drum Racks
- prop class_display_name (symbol, get): Get the original name of the device (e.g. `Operator`, `Auto Filter`).
- prop class_name (symbol, get): Live device type such as `MidiChord`, `Operator`, `Limiter`, `MxDeviceAudioEffect`, or `PluginDevice`.
- prop is_active (bool, get/observe): 0 = either the device itself or its enclosing Rack device is off.
- prop name (symbol, get/set/observe): This is the string shown in the title bar of the device.
- prop type (int, get): The type of the device. Possible types are: 0 = undefined, 1 = instrument, 2 = audio_effect, 4 = midi_effect.
- prop latency_in_samples (int, get/observe): Device latency in samples.
- prop latency_in_ms (float, get/observe): Device latency in milliseconds.
- prop can_compare_ab (bool, get) [since Live 12.3]: 1 for devices that support the AB Compare feature. 0 otherwise.
- prop is_using_compare_preset_b (bool, get/set/observe) [since Live 12.3]: 1 if the device has compare preset B loaded. 0 otherwise. | (Only relevant if *can_compare_ab*, otherwise errors.)

### Functions
- fn store_chosen_bank(script_index: int, bank_index: int): (This is related to hardware control surfaces and is usually not relevant.)
- fn save_preset_to_compare_ab_slot() [since Live 12.3]: Save the device state to the other compare AB slot. | (Only relevant if *can_compare_ab*, otherwise errors.)

## Device.View
- URL: https://docs.cycling74.com/apiref/lom/device_view/
- Canonical path(s): `live_set tracks N devices M view`; `live_set tracks N devices M chains L devices K view`; `live_set tracks N devices M return_chains L devices K view`
- Description: Representing the view aspects of a Device.
- Counts: 0 children, 1 properties, 0 functions

### Properties
- prop is_collapsed (bool, get/set/observe): 1 = the device is shown collapsed in the device chain.

## DeviceIO
- URL: https://docs.cycling74.com/apiref/lom/deviceio/
- Description: This class represents an input or output bus of a Live device.
- Counts: 0 children, 5 properties, 0 functions

### Properties
- prop available_routing_channels (dictionary, get/observe): The available channels for this input/output bus. The channels are represented as a *dictionary* with the following key: | `available_routing_channels` [list] | The list contains *dictionaries* as described in *routing_channel*.
- prop available_routing_types (dictionary, get/observe): The available types for this input/output bus. The types are represented as a *dictionary* with the following key: | `available_routing_types` [list] | The list contains *dictionaries* as described in *routing_type*.
- prop default_external_routing_channel_is_none (bool, get/set) [since Live 11.0]: 1 = the default routing channel for External routing types is none.
- prop routing_channel (dictionary, get/set/observe): The current routing channel for this input/output bus. It is represented as a *dictionary* with the following keys: | `display_name` [symbol] | `identifier` [symbol] | Can be set to any of the values found in *available_routing_channels.*
- prop routing_type (dictionary, get/set/observe): The current routing type for this input/output bus. It is represented as a *dictionary* with the following keys: | `display_name` [symbol] | `identifier` [symbol] | Can be set to any of the values found in *available_routing_types.*

## DeviceParameter
- URL: https://docs.cycling74.com/apiref/lom/deviceparameter/
- Canonical path(s): `live_set tracks N devices M parameters L`
- Description: This class represents an (automatable) parameter within a MIDI or audio device. To modify a device parameter, set its `value` property or send its object ID to live.remote~.
- Counts: 0 children, 12 properties, 3 functions

### Properties
- prop automation_state (int, get/observe): Get the automation state of the parameter. | 0 = no automation. | 1 = automation active. | 2 = automation overridden.
- prop default_value (float, get): Get the default value for this parameter. | Only available for parameters that aren't quantized (see *is_quantized*).
- prop is_enabled (bool, get): 1 = the parameter value can be modified directly by the user, by sending `set` to a live.object, by automation or by an assigned MIDI message or keystroke. | Parameters can be disabled because they are macro-controlled, or they are controlled by a live-remote~ object, or because Live thinks that they should not be moved.
- prop is_quantized (bool, get): 1 for booleans and enums | 0 for int/float parameters | Although parameters like MidiPitch.Pitch appear quantized to the user, they actually have an is_quantized value of 0.
- prop max (float, get): Largest allowed value.
- prop min (float, get): Lowest allowed value.
- prop name (symbol, get): The short parameter name as shown in the (closed) automation chooser.
- prop original_name (symbol, get): The name of a Macro parameter before its assignment.
- prop state (int, get/observe): The active state of the parameter. | 0 = the parameter is active and can be changed. | 1 = the parameter can be changed but isn't active, so changes won't have an audible effect. | 2 = the parameter cannot be changed.
- prop value (float, get/set/observe): The internal value between min and max. Use display_value for the value as visible in the GUI.
- prop display_value (float, get/set/observe): The value as visible in the GUI.
- prop value_items (StringVector, get): Get a list of the possible values for this parameter. | Only available for parameters that are quantized (see *is_quantized*).

### Functions
- fn re_enable_automation(): Re-enable automation for this parameter.
- fn str_for_value(value: float) -> [symbol] String representation of the specified value
- fn __str__() -> [symbol] String representation of the current parameter value

## DriftDevice
- URL: https://docs.cycling74.com/apiref/lom/driftdevice/
- Inherits (per docs text): Device — "A DriftDevice has all the properties, functions and children of a Device."
- Description: This class represents an instance of a Drift device in Live. | A DriftDevice has all the properties, functions and children of a Device.
- Counts: 0 children, 29 properties, 0 functions

### Properties
- prop mod_matrix_filter_source_1_index (int, get/set/observe): The index of the available sources for modulating the Filter Frequency for the first modulation slot.
- prop mod_matrix_filter_source_1_list (StringVector, get): The list of the available sources for modulating the Filter Frequency for the first modulation slot.
- prop mod_matrix_filter_source_2_index (int, get/set/observe): The index of the available sources for modulating the Filter Frequency for the second modulation slot.
- prop mod_matrix_filter_source_2_list (StringVector, get): The list of the available sources for modulating the Filter Frequency for the second modulation slot.
- prop mod_matrix_lfo_source_index (int, get/set/observe): The index of the available sources for modulating the LFO Amount.
- prop mod_matrix_lfo_source_list (StringVector, get): The list of the available sources for modulating the LFO Amount.
- prop mod_matrix_pitch_source_1_index (int, get/set/observe): The index of the available sources for modulating the Pitch for the first modulation slot.
- prop mod_matrix_pitch_source_1_list (StringVector, get): The list of the available sources for modulating the Pitch for the first modulation slot.
- prop mod_matrix_pitch_source_2_index (int, get/set/observe): The index of the available sources for modulating the Pitch for the second modulation slot.
- prop mod_matrix_pitch_source_2_list (StringVector, get): The list of the available sources for modulating the Pitch for the second modulation slot.
- prop mod_matrix_shape_source_index (int, get/set/observe): The index of the available sources for modulating Shape.
- prop mod_matrix_shape_source_list (StringVector, get): The list of the available sources for modulating Shape.
- prop mod_matrix_source_1_index (int, get/set/observe): The index of the available sources for the first custom modulation slot.
- prop mod_matrix_source_1_list (StringVector, get): The list of the available sources for the first custom modulation slot.
- prop mod_matrix_source_2_index (int, get/set/observe): The index of the available sources for the second custom modulation slot.
- prop mod_matrix_source_2_list (StringVector, get): The list of the available sources for the second custom modulation slot.
- prop mod_matrix_source_3_index (int, get/set/observe): The index of the available sources for the third custom modulation slot.
- prop mod_matrix_source_3_list (StringVector, get): The list of the available sources for the third custom modulation slot.
- prop mod_matrix_target_1_index (int, get/set/observe): The index of the available targets for the first custom modulation slot.
- prop mod_matrix_target_1_list (StringVector, get): The list of the available targets for the first custom modulation slot.
- prop mod_matrix_target_2_index (int, get/set/observe): The index of the available targets for the second custom modulation slot.
- prop mod_matrix_target_2_list (StringVector, get): The list of the available targets for the second custom modulation slot.
- prop mod_matrix_target_3_index (int, get/set/observe): The index of the available targets for the third custom modulation slot.
- prop mod_matrix_target_3_list (StringVector, get): The list of the available targets for the third custom modulation slot.
- prop pitch_bend_range (int, get/set/observe): The amount for the MIDI Pitch Bend range in semitones.
- prop voice_count_index (int, get/set/observe): The index of the voice count parameter.
- prop voice_count_list (StringVector, get): The list of available voice count settings.
- prop voice_mode_index (int, get/set/observe): The index of the voice mode utilized by Drift.
- prop voice_mode_list (StringVector, get): The list of available voice modes.

## DrumCellDevice
- URL: https://docs.cycling74.com/apiref/lom/drumcelldevice/
- Inherits (per docs text): Device — "A DrumCell has all the properties, functions and children of a Device."
- Description: This class represents an instance of a Drum Sampler device in Live. | A DrumCell has all the properties, functions and children of a Device. Listed below are members unique to DrumCell Device.
- Counts: 0 children, 1 properties, 0 functions

### Properties
- prop gain (float, get/set/observe): The sample gain, as normalized value.

## DrumChain
- URL: https://docs.cycling74.com/apiref/lom/drumchain/
- Inherits (per docs text): Chain — "A DrumChain is a type of Chain, meaning that it has all the children, properties and functions that a Chain has."
- Description: This class represents a Drum Rack device chain in Live. | A DrumChain is a type of Chain, meaning that it has all the children, properties and functions that a Chain has. Listed below are the members unique to DrumChain.
- Counts: 0 children, 3 properties, 0 functions

### Properties
- prop in_note (int, get/set/observe) [since Live 12.3]: Get/set the MIDI note that will trigger this chain. The value -1 corresponds to the "All Notes" setting in the UI.
- prop out_note (int, get/set/observe): Get/set the MIDI note sent to the devices in the chain.
- prop choke_group (int, get/set/observe): Get/set the chain's choke group.

## DrumPad
- URL: https://docs.cycling74.com/apiref/lom/drumpad/
- Canonical path(s): `live_set tracks N devices M drum_pads L`
- Description: This class represents a Drum Rack pad in Live.
- Counts: 1 children, 4 properties, 1 functions

### Children
- child chains (Chain, get/observe)

### Properties
- prop mute (bool, get/set/observe): 1 = muted
- prop name (symbol, get/observe)
- prop note (int, get)
- prop solo (bool, get/set/observe): 1 = soloed (Solo switch on) | Does not automatically turn Solo off in other chains.

### Functions
- fn delete_all_chains()

## Eq8Device
- URL: https://docs.cycling74.com/apiref/lom/eq8device/
- Inherits (per docs text): Device — "An Eq8Device has all the properties, functions and children of a Device."
- Description: This class represents an instance of an EQ Eight device in Live. | An Eq8Device has all the properties, functions and children of a Device. Listed below are members unique to Eq8Device.
- Counts: 0 children, 3 properties, 0 functions

### Properties
- prop edit_mode (bool, get/set/observe): Access to EQ Eight's edit mode, which toggles the channel currently available for editing. The available edit modes depend on the global mode (see `global_mode`) and are encoded as follows: | In L/R mode: 0 = L, 1 = R | In M/S mode: 0 = M, 1 = S | In Stereo mode: 0 = A, 1 = B (inactive)
- prop global_mode (int, get/set/observe): Access to EQ Eight's global mode. The modes are encoded as follows: | 0 = Stereo | 1 = L/R | 2 = M/S
- prop oversample (bool, get/set/observe): Access to EQ Eight's Oversampling parameter. 0 = Off, 1 = On.

## Eq8Device.View
- URL: https://docs.cycling74.com/apiref/lom/eq8device_view/
- Inherits (per docs text): Device.View — "An Eq8Device.View has all the children, properties and functions of a Device.View."
- Description: Represents the view aspects of an Eq8Device. | An Eq8Device.View has all the children, properties and functions of a Device.View. Listed below are members unique to it.
- Counts: 0 children, 1 properties, 0 functions

### Properties
- prop selected_band (int, get/set/observe): The index of the currently selected filter band.

## Groove
- URL: https://docs.cycling74.com/apiref/lom/groove/
- Canonical path(s): `live_set groove_pool grooves N`; `live_set tracks N clip_slots M clip groove`
- Class version note: Available since Live 11.0.
- Description: This class represents a groove in Live. | All grooves are stored in Live's groove pool.
- Note: Docs list these primitive-typed members under 'Children' (not LOM objects): base, name, quantization_amount, random_amount, timing_amount, velocity_amount.
- Counts: 6 children, 0 properties, 0 functions

### Children
- child base (int, get/set): Get/set the groove's base grid (index based setter). | 0 = 1/4 | 1 = 1/8 | 2 = 1/8T | 3 = 1/16 | 4 = 1/16T | 5 = 1/32
- child name (symbol, get/set/observe): Get/set/observe the name of the groove.
- child quantization_amount (float, get/set/observe): Get/set/observe the groove's quantization amount.
- child random_amount (float, get/set/observe): Get/set/observe the groove's random amount.
- child timing_amount (float, get/set/observe): Get/set/observe the groove's timing amount.
- child velocity_amount (float, get/set/observe): Get/set/observe the groove's velocity amount.

## GroovePool
- URL: https://docs.cycling74.com/apiref/lom/groovepool/
- Canonical path(s): `live_set groove_pool`
- Description: This class represents the groove pool in Live. It provides access to the current set's list of grooves.
- Counts: 1 children, 0 properties, 0 functions

### Children
- child grooves (list of Groove, get/observe): List of grooves in the groove pool from top to bottom, can be accessed via index.

## HybridReverbDevice
- URL: https://docs.cycling74.com/apiref/lom/hybridreverbdevice/
- Inherits (per docs text): Device — "A HybridReverbDevice has all the properties, functions and children of a Device."
- Description: This class represents an instance of a Hybrid Reverb device in Live. | A HybridReverbDevice has all the properties, functions and children of a Device. Listed below are members unique to HybridReverbDevice.
- Counts: 0 children, 8 properties, 0 functions

### Properties
- prop ir_attack_time (float, get/set/observe): The attack time of the amplitude envelope for the impulse response, in seconds.
- prop ir_category_index (int, get/set/observe): The index of the selected impulse response category.
- prop ir_category_list (StringVector, get): The list of impulse response categories.
- prop ir_decay_time (float, get/set/observe): The decay time of the amplitude envelope for the impulse response, in seconds.
- prop ir_file_index (int, get/set/observe): The index of the selected impulse response files from the current category.
- prop ir_file_list (StringVector, get/observe): The list of impulse response files from the selected category.
- prop ir_size_factor (float, get/set/observe): The relative size of the impulse response, 0.0 to 1.0.
- prop ir_time_shaping_on (bool, get/set/observe): Enables transforming the current selected impulse response with an amplitude envelope and size parameter. | 1 = enabled.

## LooperDevice
- URL: https://docs.cycling74.com/apiref/lom/looperdevice/
- Inherits (per docs text): Device — "An LooperDevice has all the properties, functions and children of a Device."
- Description: This class represents an instance of a Looper device in Live. | An LooperDevice has all the properties, functions and children of a Device. Listed below are members unique to LooperDevice.
- Counts: 0 children, 5 properties, 11 functions

### Properties
- prop loop_length (float, get/observe): The length of Looper's buffer.
- prop overdub_after_record (bool, get/set/observe): 1 = Looper will switch to overdub after recording, when recording a fixed number of bars. 0 = switch to playback without overdubbing.
- prop record_length_index (int, get/set/observe): Access to the Record Length chooser entry index.
- prop record_length_list (StringVector, get): Access to the list of Record Length chooser entry strings.
- prop tempo (float, get/observe): The tempo of Looper's buffer.

### Functions
- fn clear(): Erase Looper's recorded content.
- fn double_speed(): Double the speed of Looper's playback.
- fn half_speed(): Halve the speed of Looper's playback.
- fn double_length(): Double the length of Looper's buffer.
- fn half_length(): Halve the length of Looper's buffer.
- fn record(): Record incoming audio.
- fn overdub(): Play back while adding additional layers of incoming audio.
- fn play(): Play back without overdubbing.
- fn stop(): Stop Looper's playback.
- fn undo(): Erase everything that was recorded since the last time Overdub was enabled. Calling a second time will restore the material erased by the previous undo operation.
- fn export_to_clip_slot(clip_slot: ClipSlot): Given a valid LOM ID of an empty clip slot on a non-frozen audio track, will export Looper's content to a clip in that slot. This is similar to using the Drag Me! control on the Looper device, and the same restrictions apply: the audio engine must be turned on, the Looper must actually hold audio content, the content must have a fixed length (i.e. Looper must not be recording), etc.
  - param clip_slot: The target clip slot.

## MaxDevice
- URL: https://docs.cycling74.com/apiref/lom/maxdevice/
- Inherits (per docs text): Device — "A MaxDevice is a type of Device, meaning that it has all the children, properties and functions that a Device has."
- Description: This class represents a Max for Live device in Live. | A MaxDevice is a type of Device, meaning that it has all the children, properties and functions that a Device has. Listed below are the members unique to MaxDevice.
- Counts: 0 children, 4 properties, 3 functions

### Properties
- prop audio_inputs (list of DeviceIO, get/observe): List of the audio inputs that the MaxDevice offers.
- prop audio_outputs (list of DeviceIO, get/observe): List of the audio outputs that the MaxDevice offers.
- prop midi_inputs (list of DeviceIO, get/observe) [since Live 11.0]: List of the midi inputs that the MaxDevice offers.
- prop midi_outputs (list of DeviceIO, get/observe) [since Live 11.0]: List of the midi outputs that the MaxDevice offers.

### Functions
- fn get_bank_count() -> [int] the number of parameter banks
- fn get_bank_name(bank_index: int) -> [list of symbols] The name of the parameter bank specified by bank_index
- fn get_bank_parameters(bank_index: int) -> [list of ints] The indices of the parameters contained in the bank specified by bank_index. Empty slots are marked as -1. Bank index -1 refers to the "Best of" bank

## MeldDevice
- URL: https://docs.cycling74.com/apiref/lom/melddevice/
- Inherits (per docs text): Device — "A MeldDevice has all the properties, functions and children of a Device."
- Description: This class represents an instance of a Meld device in Live. | A MeldDevice has all the properties, functions and children of a Device.
- Counts: 0 children, 4 properties, 0 functions

### Properties
- prop selected_engine (int, get/set/observe): Meld's oscillator engine selector. The modes are encoded as follows: | 0 = Engine A | 1 = Engine B
- prop unison_voices (int, get/set/observe): Selects the Unison voice count. The modes are encoded as follows: | 0 = off | 1 = two | 2 = three | 3 = four
- prop mono_poly (int, get/set/observe): Selects the polyphony mode. The modes are encoded as follows: | 0 = mono | 1 = poly
- prop poly_voices (int, get/set/observe): Selects the polyphony voice count. The modes are encoded as follows: | 0 = two | 1 = three | 2 = four | 3 = five | 4 = six | 5 = eight | 6 = twelve

## MixerDevice
- URL: https://docs.cycling74.com/apiref/lom/mixerdevice/
- Canonical path(s): `live_set tracks N mixer_device`
- Description: This class represents a mixer device in Live. It provides access to volume, panning and other DeviceParameter objects. See DeviceParameter to learn how to modify them.
- Counts: 9 children, 2 properties, 0 functions

### Children
- child sends (list of DeviceParameter, get/observe): One send per return track.
- child cue_volume (DeviceParameter, get): [in master track only]
- child crossfader (DeviceParameter, get): [in master track only]
- child left_split_stereo (DeviceParameter, get): The Track's Left Split Stereo Pan Parameter.
- child panning (DeviceParameter, get)
- child right_split_stereo (DeviceParameter, get): The Track's Right Split Stereo Pan Parameter.
- child song_tempo (DeviceParameter, get): [in master track only]
- child track_activator (DeviceParameter, get)
- child volume (DeviceParameter, get)

### Properties
- prop crossfade_assign (int, get/set/observe): 0 = A, 1 = none, 2 = B [not in master track]
- prop panning_mode (int, get/set/observe): Access to the Track mixer's pan mode: 0 = Stereo, 1 = Split Stereo.

## PluginDevice
- URL: https://docs.cycling74.com/apiref/lom/plugindevice/
- Inherits (per docs text): Device — "A PluginDevice is a type of Device, meaning that it has all the children, properties and functions that a Device has."
- Description: This class represents a plug-in device. | A PluginDevice is a type of Device, meaning that it has all the children, properties and functions that a Device has. Listed below are the members unique to PluginDevice.
- Counts: 0 children, 3 properties, 0 functions

### Properties
- prop is_editor_open (bool, get/set/observe): The opened state of the plug-in's editor window.
- prop presets (StringVector, get/observe): Get the list of the plug-in's presets.
- prop selected_preset_index (int, get/set/observe): Get/set the index of the currently selected preset.

## RackDevice
- URL: https://docs.cycling74.com/apiref/lom/rackdevice/
- Inherits (per docs text): Device — "A RackDevice is a type of Device, meaning that it has all the children, properties and functions that a Device has."
- Description: This class represents a Live Rack Device. | A RackDevice is a type of Device, meaning that it has all the children, properties and functions that a Device has. Listed below are members unique to RackDevice.
- Counts: 5 children, 7 properties, 9 functions

### Children
- child chain_selector (DeviceParameter, get): Convenience accessor for the Rack's chain selector.
- child chains (list of Chain, get/observe): The Rack's chains.
- child drum_pads (list of DrumPad, get/observe): All 128 Drum Pads for the topmost Drum Rack. Inner Drum Racks return a list of 0 entries.
- child return_chains (list of Chain, get/observe): The Rack's return chains.
- child visible_drum_pads (list of DrumPad, get/observe): All 16 visible DrumPads for the topmost Drum Rack. Inner Drum Racks return a list of 0 entries.

### Properties
- prop can_show_chains (bool, get): 1 = The Rack contains an instrument device that is capable of showing its chains in Session View.
- prop has_drum_pads (bool, get/observe): 1 = the device is a Drum Rack with pads. A nested Drum Rack is a Drum Rack without pads. | Only available for Drum Racks.
- prop has_macro_mappings (bool, get/observe): 1 = any of a Rack's Macros are mapped to a parameter.
- prop is_showing_chains (bool, get/set/observe): 1 = The Rack contains an instrument device that is showing its chains in Session View.
- prop variation_count (int, get/observe) [since Live 11.0]: The number of currently stored macro variations.
- prop selected_variation_index (int, get/set) [since Live 11.0]: Get/set the currently selected variation.
- prop visible_macro_count (int, get/observe): The number of currently visible macros.

### Functions
- fn copy_pad(source_index: int, destination_index: int): Copies all content of a Drum Rack pad from a source pad to a destination pad. The source_index and destination_index refer to pad indices inside a Drum Rack.
- fn add_macro() [since Live 11.0]: Increases the number of visible macro controls.
- fn insert_chain(index?: int) [since Live 12.3]: Attempts to insert a new chain at the given index, or at the end of the chain list if no index is provided. Throws an error if insertion is not possible.
- fn remove_macro() [since Live 11.0]: Decreases the number of visible macro controls.
- fn randomize_macros() [since Live 11.0]: Randomizes the values of eligible macro controls.
- fn store_variation() [since Live 11.0]: Stores a new variation of the values of all currently mapped macros.
- fn recall_selected_variation() [since Live 11.0]: Recalls the currently selected macro variation.
- fn recall_last_used_variation() [since Live 11.0]: Recalls the macro variation that was recalled most recently.
- fn delete_selected_variation() [since Live 11.0]: Deletes the currently selected macro variation. Does nothing if there is no selected variation.

## RackDevice.View
- URL: https://docs.cycling74.com/apiref/lom/rackdevice_view/
- Inherits (per docs text): Device.View — "A RackDevice.View is a type of Device.View, meaning that it has all the properties that a Device.View has."
- Description: Represents the view aspects of a Rack Device. | A RackDevice.View is a type of Device.View, meaning that it has all the properties that a Device.View has. Listed below are the members unique to RackDevice.View.
- Counts: 2 children, 2 properties, 0 functions

### Children
- child selected_drum_pad (DrumPad, get/set/observe): Currently selected Drum Rack pad. | Only available for Drum Racks.
- child selected_chain (Chain, get/set/observe): Currently selected chain.

### Properties
- prop drum_pads_scroll_position (int, get/set/observe): Lowest row of pads visible, range: 0 - 28. | Only available for Drum Racks.
- prop is_showing_chain_devices (bool, get/set/observe): 1 = the devices in the currently selected chain are visible.

## RoarDevice
- URL: https://docs.cycling74.com/apiref/lom/roardevice/
- Inherits (per docs text): Device — "A RoarDevice has all the properties, functions and children of a Roar Device."
- Description: This class represents an instance of a Roar device in Live. | A RoarDevice has all the properties, functions and children of a Roar Device.
- Counts: 0 children, 3 properties, 0 functions

### Properties
- prop routing_mode_index (int, get/set/observe): The index of the routing mode utilized by Roar.
- prop routing_mode_list (StringVector, get): The list of available routing modes.
- prop env_listen (bool, get/set/observe): Get, set and observe the Envelope Input Listen toogle.

## Sample
- URL: https://docs.cycling74.com/apiref/lom/sample/
- Canonical path(s): `live_set tracks N devices N sample`
- Description: This class represents a sample file loaded into Simpler.
- Counts: 0 children, 22 properties, 6 functions

### Properties
- prop beats_granulation_resolution (int, get/set/observe): Get/set which divisions to preserve in the sample in Beats Mode. | 0 = 1 Bar | 1 = 1/2 | 2 = 1/4 | 3 = 1/8 | 4 = 1/16 | 5 = 1/32 | 6 = Transients
- prop beats_transient_envelope (float, get/set/observe): Get/set the duration of a volume fade applied to each segment of audio in Beats Mode. | 0 = fastest decay | 100 = no fade
- prop beats_transient_loop_mode (int, get/set/observe): Get/set the Transient Loop Mode applied to each segment of audio in Beats Mode. | 0 = Off | 1 = Loop Forward | 2 = Loop Back-and-Forth
- prop complex_pro_envelope (float, get/set/observe): Get/set the Envelope parameter in Complex Pro Mode.
- prop complex_pro_formants (float, get/set/observe): Get/set the Formants parameter in Complex Pro Mode.
- prop end_marker (int, get/set/observe): Get/set the position of the sample's end marker.
- prop file_path (unicode, get/observe): Get the path of the sample file.
- prop gain (float, get/set/observe): Get/set the sample gain.
- prop length (int, get): Get the length of the sample file in sample frames.
- prop sample_rate (int, get) [since Live 11.0]: The sample rate of the loaded sample.
- prop slices (list of int, get/observe) [since Live 11.0]: The positions of all playable slices in the sample, in sample frames. Divide these values by the `sample_rate` to get the slice times in seconds.
- prop slicing_sensitivity (float, get/set/observe): Get/set the slicing sensitivity. Values are between 0.0 and 1.0.
- prop start_marker (int, get/set/observe): Get/set the position of the sample's start marker.
- prop texture_flux (float, get/set/observe): Get/set the Flux parameter in Texture Mode.
- prop texture_grain_size (float, get/set/observe): Get/set the Grain Size parameter in Texture Mode.
- prop tones_grain_size (float, get/set/observe): Get/set the Grain Size parameter in Tones Mode.
- prop warp_markers (dict/bang, get/observe) [since Live 11.0]: The Sample's Warp Markers as a dict. Observing this property bangs when the warp_markers change. | The last Warp Marker in the dict is not visible in the Live interface. This hidden, or "shadow" marker is used to calculate the BPM of the last segment.
- prop warp_mode (int, get/set/observe): Get/set the Warp Mode. | 0 = Beats Mode | 1 = Tones Mode | 2 = Texture Mode | 3 = Re-Pitch Mode | 4 = Complex Mode | 6 = Complex Pro Mode
- prop warping (bool, get/set/observe): 1 = warping is enabled.
- prop slicing_style (int, get/set/observe): Get/set the Slicing Mode. | 0 = Transient | 1 = Beat | 2 = Region | 3 = Manual
- prop slicing_beat_division (int, get/set/observe): Get/set the slice beat division in Beat Slicing Mode. | 0 = 1/16 | 1 = 1/16T | 2 = 1/8 | 3 = 1/8T | 4 = 1/4 | 5 = 1/4T | 6 = 1/2 | 7 = 1/2T | 8 = 1 Bar | 9 = 2 Bars | 10 = 4 Bars
- prop slicing_region_count (int, get/set/observe): Get/set the number of slice regions in Region Slicing Mode.

### Functions
- fn gain_display_string() -> [list of symbols] The sample's gain value as a string, e.g. "0.0 dB"
- fn insert_slice(slice_time: int): Insert a new slice at the specified time if there is none.
- fn move_slice(source_time: int, destination_time: int): Move an existing slice to a specified time.
- fn remove_slice(slice_time: int): Remove a slice at the specified time if it exists.
- fn clear_slices(): Clear all slices created in Manual Slicing Mode.
- fn reset_slices(): Reset all edited slices to their original positions.

## Scene
- URL: https://docs.cycling74.com/apiref/lom/scene/
- Canonical path(s): `live_set scenes N`
- Description: This class represents a series of clip slots in Live's Session View matrix.
- Counts: 1 children, 10 properties, 3 functions

### Children
- child clip_slots (list of ClipSlot, get/observe)

### Properties
- prop color (int, get/set/observe): The RGB value of the scene's color in the form `0x00rrggbb` or (2^16 * red) + (2^8) * green + blue, where red, green and blue are values from 0 (dark) to 255 (light). | When setting the RGB value, the nearest color from the Scene color chooser is taken.
- prop color_index (long, get/set/observe): The color index of the scene.
- prop is_empty (bool, get): 1 = none of the slots in the scene is filled.
- prop is_triggered (bool, get/observe): 1 = scene is blinking.
- prop name (symbol, get/set/observe): The name of the scene.
- prop tempo (float, get/set/observe): The scene's tempo. | Returns -1 if the scene tempo is disabled.
- prop tempo_enabled (bool, get/set/observe): The active state of the scene tempo. | When disabled, the scene will use the song's tempo, | and the tempo value returned will be -1.
- prop time_signature_numerator (int, get/set/observe): The scene's time signature numerator. | Returns -1 if the scene time signature is disabled.
- prop time_signature_denominator (int, get/set/observe): The scene's time signature denominator. | Returns -1 if the scene time signature is disabled.
- prop time_signature_enabled (bool, get/set/observe): The active state of the scene time signature. | When disabled, the scene will use the song's time signature, | and the time signature values returned will be -1.

### Functions
- fn fire(force_legato?: bool = 0, can_select_scene_on_launch?: bool = 1): Fire all clip slots contained within the scene and select this scene. | Starts recording of armed and empty tracks within a Group Track in this scene if Preferences->Launch->Start Recording on Scene Launch is ON. | Calling with force_legato = 1 (default = 0) will launch all clips immediately in Legato, independent of their launch mode. | When calling with can_select_scene_on_launch = 0 (default = 1) the scene is fired without selecting it.
- fn fire_as_selected(force_legato?: bool = 0): Fire the selected scene, then select the next scene. | It doesn't matter on which scene you are calling this function. | Calling with force_legato = 1 (default = 0) will launch all clips immediately in Legato, independent of their launch mode.
- fn set_fire_button_state(state: bool): If the state is set to 1, Live simulates pressing of scene button until the state is set to 0 or until the scene is stopped otherwise.

## ShifterDevice
- URL: https://docs.cycling74.com/apiref/lom/shifterdevice/
- Inherits (per docs text): Device — "A ShifterDevice is a type of device, meaning that it has all the children, properties and functions that a device has."
- Description: This class represents an instance of the Shifter audio effect. | A ShifterDevice is a type of device, meaning that it has all the children, properties and functions that a device has. Listed below are members unique to ShifterDevice.
- Counts: 0 children, 2 properties, 0 functions

### Properties
- prop pitch_bend_range (int, get/set/observe): The pitch bend range used in MIDI Pitch Mode.
- prop pitch_mode_index (int, get/set/observe): The current pitch mode index: 0 = Internal, 1 = MIDI

## SimplerDevice
- URL: https://docs.cycling74.com/apiref/lom/simplerdevice/
- Inherits (per docs text): Device — "A SimplerDevice is a type of device, meaning that it has all the children, properties and functions that a device has."
- Description: This class represents an instance of Simpler. | A SimplerDevice is a type of device, meaning that it has all the children, properties and functions that a device has. Listed below are members unique to SimplerDevice.
- Counts: 1 children, 11 properties, 7 functions

### Children
- child sample (Sample, get/observe): The sample currently loaded into Simpler.

### Properties
- prop can_warp_as (bool, get/observe): 1 = warp_as is available.
- prop can_warp_double (bool, get/observe): 1 = warp_double is available.
- prop can_warp_half (bool, get/observe): 1 = warp_half is available.
- prop multi_sample_mode (bool, get/observe): 1 = Simpler is in multisample mode.
- prop pad_slicing (bool, get/set/observe): 1 = slices can be added in Slicing Mode by playing notes which are not yet assigned to existing slices.
- prop playback_mode (int, get/set/observe): Get/set Simpler's playback mode. | 0 = Classic Mode | 1 = One-Shot Mode | 2 = Slicing Mode
- prop playing_position (float, get/observe): The current playing position in the sample, expressed as a value between 0. and 1.
- prop playing_position_enabled (bool, get/observe): 1 = Simpler is playing back the sample and showing the playing position.
- prop retrigger (bool, get/set/observe): 1 = Retrigger is enabled in Simpler.
- prop slicing_playback_mode (int, get/set/observe): Get/set Simpler's Slicing Playback Mode. | 0 = Mono | 1 = Poly | 2 = Thru
- prop voices (int, get/set/observe): Get/set the number of Voices.

### Functions
- fn crop(): Crop the loaded sample to the active region between the start and end markers.
- fn guess_playback_length() -> [float] An estimated beat time for the playback length between the start and end markers
- fn reverse(): Reverse the loaded sample.
- fn warp_as(beats: int): Warp the active region between the start and end markers as the specified number of beats.
- fn warp_double(): Double the playback tempo of the active region between the start and end markers.
- fn warp_half(): Halve the playback tempo for the active region between the start and end markers.
- fn replace_sample(file_path: symbol): Given an absolute path to a valid audio file in a supported format, replaces the loaded sample with the one specified.

## SimplerDevice.View
- URL: https://docs.cycling74.com/apiref/lom/simplerdevice_view/
- Inherits (per docs text): Device.View — "A SimplerDevice.View is a type of Device.View, meaning that it has all the properties that a Device.View has."
- Description: Represents the view aspects of a SimplerDevice. | A SimplerDevice.View is a type of Device.View, meaning that it has all the properties that a Device.View has. Listed below are the members unique to SimplerDevice.View.
- Counts: 0 children, 1 properties, 0 functions

### Properties
- prop selected_slice (int, get/set/observe): The currenctly selected slice, identified by its slice time.

## Song
- URL: https://docs.cycling74.com/apiref/lom/song/
- Canonical path(s): `live_set`
- Description: This class represents a Live Set. The current Live Set is reachable by the root path `live_set`.
- Counts: 9 children, 48 properties, 34 functions

### Children
- child cue_points (list of CuePoint, get/observe): Cue points are the markers in the Arrangement to which you can jump.
- child return_tracks (list of Track, get/observe)
- child scenes (list of Scene, get/observe)
- child tracks (list of Track, get/observe)
- child visible_tracks (list of Track, get/observe): A track is visible if it's not part of a folded group. If a track is scrolled out of view it's still considered visible.
- child master_track (Track, get)
- child view (Song.View, get)
- child groove_pool (GroovePool, get) [since Live 11.0]: Live's groove pool.
- child tuning_system (TuningSystem, get/observe): Live's currently active tuning system.

### Properties
- prop appointed_device (Device, get/observe): The appointed device is the one used by a control surface unless the control surface itself chooses which device to use. It is marked by a blue hand.
- prop arrangement_overdub (bool, get/set/observe): Get/set the state of the MIDI Arrangement Overdub button.
- prop back_to_arranger (bool, get/set/observe): Get/set/observe the current state of the Back to Arrangement button located in Live's transport bar (1 = highlighted). This button is used to indicate that the current state of the playback differs from what is stored in the Arrangement. | Setting this property to 0 will make Live go back to playing the content of the arrangement.
- prop can_capture_midi (bool, get/observe): 1 = Recently played MIDI material exists that can be captured into a Live Track. See *capture_midi*.
- prop can_jump_to_next_cue (bool, get/observe): 0 = there is no cue point to the right of the current one, or none at all.
- prop can_jump_to_prev_cue (bool, get/observe): 0 = there is no cue point to the left of the current one, or none at all.
- prop can_redo (bool, get): 1 = there is something in the history to redo.
- prop can_undo (bool, get): 1 = there is something in the history to undo.
- prop clip_trigger_quantization (int, get/set/observe): Reflects the quantization setting in the transport bar. | 0 = None | 1 = 8 Bars | 2 = 4 Bars | 3 = 2 Bars | 4 = 1 Bar | 5 = 1/2 | 6 = 1/2T | 7 = 1/4 | 8 = 1/4T | 9 = 1/8 | 10 = 1/8T | 11 = 1/16 | 12 = 1/16T | 13 = 1/32
- prop count_in_duration (int, get/observe): The duration of the Metronome's Count-In setting as an index, mapped as follows: | 0 = None | 1 = 1 Bar | 2 = 2 Bars | 3 = 4 Bars
- prop current_song_time (float, get/set/observe): The playing position in the Live Set, in beats.
- prop exclusive_arm (bool, get): Current status of the exclusive Arm option set in the Live preferences.
- prop exclusive_solo (bool, get): Current status of the exclusive Solo option set in the Live preferences.
- prop file_path (symbol, get): The path to the current Live Set, in OS-native format. If the Live Set hasn't been saved, the path is empty.
- prop groove_amount (float, get/set/observe): The groove amount from the current set's groove pool (0. - 1.0).
- prop is_ableton_link_enabled (bool, get/set/observe): Enable/disable Ableton Link. The Link toggle in the Live's transport bar must be visible to enable Link.
- prop is_ableton_link_start_stop_sync_enabled (bool, get/set/observe): Enable/disable Ableton Link Start Stop Sync.
- prop is_counting_in (bool, get/observe): 1 = the Metronome is currently counting in.
- prop is_playing (bool, get/set/observe): Get/set if Live's transport is running.
- prop last_event_time (float, get): The beat time of the last event (i.e. automation breakpoint, clip end, cue point, loop end) in the Arrangement.
- prop loop (bool, get/set/observe): Get/set the enabled state of the Arrangement loop.
- prop loop_length (float, get/set/observe): Arrangement loop length in beats.
- prop loop_start (float, get/set/observe): Arrangement loop start in beats.
- prop metronome (bool, get/set/observe): Get/set the enabled state of the metronome.
- prop midi_recording_quantization (int, get/set/observe): Get/set the current Record Quantization value. | 0 = None | 1 = 1/4 | 2 = 1/8 | 3 = 1/8T | 4 = 1/8 + 1/8T | 5 = 1/16 | 6 = 1/16T | 7 = 1/16 + 1/16T | 8 = 1/32
- prop name (symbol, get): The name of the current Live Set. If the Live Set hasn't been saved, the name is empty.
- prop nudge_down (bool, get/set/observe): 1 = the Tempo Nudge Down button in the transport bar is currently pressed.
- prop nudge_up (bool, get/set/observe): 1 = the Tempo Nudge Up button in the transport bar is currently pressed.
- prop tempo_follower_enabled (bool, get/set/observe): 1 = the Tempo Follower controls the tempo. The Tempo Follower Toggle must be made visible in the preferences for this property to be effective.
- prop overdub (bool, get/set/observe): 1 = MIDI Arrangement Overdub is enabled in the transport.
- prop punch_in (bool, get/set/observe): 1 = the Punch-In button is enabled in the transport.
- prop punch_out (bool, get/set/observe): 1 = the Punch-Out button is enabled in the transport.
- prop re_enable_automation_enabled (bool, get/observe): 1 = the Re-Enable Automation button is on.
- prop record_mode (bool, get/set/observe): 1 = the Arrangement Record button is on.
- prop root_note (int, get/set/observe): The root note of the scale currently selected in Live. The root note can be a number between 0 and 11, where 0 = C and 11 = B.
- prop scale_intervals (list, get/observe): A list of integers representing the intervals in Live's current scale (see *scale_name* and *scale_mode*). An interval is expressed as the difference between the scale degree at the list index and the first scale degree.
- prop scale_mode (bool, get/set/observe): Access to the Scale Mode setting in Live. | When on, key tracks that belong to the currently selected scale are highlighted in Live's MIDI Note Editor, and pitch-based parameters in MIDI Tools and Devices can be edited in scale degrees rather than semitones. | See also *root_note*, *scale_name*, and *scale_intervals*.
- prop scale_name (unicode, get/set/observe): The name of the scale selected in Live, as displayed in the Current Scale Name chooser.
- prop select_on_launch (bool, get): 1 = the "Select on Launch" option is set in Live's preferences.
- prop session_automation_record (bool, get/set/observe): The state of the Automation Arm button.
- prop session_record (bool, get/set/observe): The state of the Session Overdub button.
- prop session_record_status (int, get/observe): Reflects the state of the Session Record button.
- prop signature_denominator (int, get/set/observe)
- prop signature_numerator (int, get/set/observe)
- prop song_length (float, get/observe): A little more than `last_event_time`, in beats.
- prop start_time (float, get/set/observe): The position in the Live Set where playing will start, in beats.
- prop swing_amount (float, get/set/observe): Range: 0.0 - 1.0; affects MIDI Recording Quantization and all direct calls to `Clip.quantize`.
- prop tempo (float, get/set/observe): Current tempo of the Live Set in BPM, 20.0 ... 999.0. The tempo may be automated, so it can change depending on the current song time.

### Functions
- fn capture_and_insert_scene(): Capture the currently playing clips and insert them as a new scene below the selected scene.
- fn capture_midi(destination: int): Capture recently played MIDI material from audible tracks into a Live Clip. | If *destinaton* is not set or it is set to *auto*, the Clip is inserted into the view currently visible in the focused Live window. Otherwise, it is inserted into the specified view.
  - param destination: 0 = auto, 1 = session, 2 = arrangement
- fn continue_playing(): From the current playback position.
- fn create_audio_track(index): Index determines where the track is added, it is only valid between 0 and len(song.tracks). Using an index of -1 will add the new track at the end of the list.
- fn create_midi_track(index): Index determines where the track is added, it is only valid between 0 and len(song.tracks). Using an index of -1 will add the new track at the end of the list.
- fn create_return_track(): Adds a new return track at the end.
- fn create_scene(index) -> The new scene: Index determines where the scene is added. It is only valid between 0 and len(song.scenes). Using an index of -1 will add the new scene at the end of the list.
- fn delete_scene(index): Delete the scene at the given index.
- fn delete_track(index): Delete the track at the given index.
- fn delete_return_track(index): Delete the return track at the given index.
- fn duplicate_scene(index): Index determines which scene to duplicate.
- fn duplicate_track(index): Index determines which track to duplicate.
- fn find_device_position(device: live object, target: live object, target position: int) -> [int] The position in the target's chain where the device can be inserted that is the closest possible to the target position
- fn force_link_beat_time(): Force the Link timeline to jump to Live's current beat time.
- fn get_beats_loop_length() -> `bars.beats.sixteenths.ticks` [symbol]: The Arrangement loop length.
- fn get_beats_loop_start() -> `bars.beats.sixteenths.ticks` [symbol]: The Arrangement loop start.
- fn get_current_beats_song_time() -> `bars.beats.sixteenths.ticks` [symbol]: The current Arrangement playback position.
- fn get_current_smpte_song_time(format: int) -> *hours:min:sec* [symbol]: The current Arrangement playback position.
  - param format: is the time code type to be returned: 0 = the frame position shows the milliseconds, 1 = Smpte24, 2 = Smpte25, 3 = Smpte30, 4 = Smpte30Drop, 5 = Smpte29
- fn is_cue_point_selected() -> bool 1 = the current Arrangement playback position is at a cue point
- fn jump_by(beats: float)
  - param beats: is the amount to jump relatively to the current position
- fn jump_to_next_cue(): Jump to the right, if possible.
- fn jump_to_prev_cue(): Jump to the left, if possible.
- fn move_device(device: live object, target: live object, target position: int) -> [int] The position in the target's chain where the device was inserted: Move the device to the specified position in the target chain. If the device cannot be moved to the specified position, the nearest possible position is chosen.
- fn play_selection(): Do nothing if no selection is set in Arrangement, or play the current selection.
- fn re_enable_automation(): Trigger 'Re-Enable Automation', re-activating automation in all running Session clips.
- fn redo(): Causes the Live application to redo the last operation.
- fn scrub_by(beats: float): Same as `jump_by`, at the moment.
  - param beats: the amount to scrub relative to the current Arrangement playback position
- fn set_or_delete_cue(): Toggle cue point at current Arrangement playback position.
- fn start_playing(): Start playback from the insert marker.
- fn stop_all_clips(quantized? = 1): Calling the function with 0 will stop all clips immediately, independent of the launch quantization. The default is '1'.
- fn stop_playing(): Stop the playback.
- fn tap_tempo(): Same as pressing the Tap Tempo button in the transport bar. The new tempo is calculated based on the time between subsequent calls of this function.
- fn trigger_session_record(record_length?): Starts recording in either the selected slot or the next empty slot, if the track is armed. If *record_length* is provided, the slot will record for the given length in beats. | If triggered while recording, recording will stop and clip playback will start.
- fn undo(): Causes the Live application to undo the last operation.

## Song.View
- URL: https://docs.cycling74.com/apiref/lom/song_view/
- Canonical path(s): `live_set view`
- Description: This class represents the view aspects of a Live document: the Session and Arrangement Views.
- Counts: 8 children, 2 properties, 1 functions

### Children
- child detail_clip (Clip, get/set/observe): The clip currently displayed in the Live application's Detail View.
- child highlighted_clip_slot (ClipSlot, get/set): The slot highlighted in the Session View.
- child mod_mapping_device (Device, get/set/observe): When assigned a device id, modulation mapping mode is active. When assigned `id 0`, mapping mode is not active. Affects only Push 3 at this time. | The device value that is used to enable modulation mapping is also used for the following purposes: - When the device is removed, mapping mode is exited automatically without reporting a chosen parameter for mapping. | - When a parameter is chosen that belongs to the assigned device, this parameter will not be chosen for mapping.
- child mod_mapping_parameter (DeviceParameter, get/observe): The parameter selected for modulation mapping, or `id 0`. | Observing this property outputs the id of a parameter that is selected in the Live UI or that is chosen for mapping on Push. | Reports `id 0` when no parameter is chosen, for example when a parameter is deselected in the Live UI.
- child selected_chain (Chain, get/set/observe): The highlighted chain, or "id 0"
- child selected_parameter (DeviceParameter, get/observe): The selected parameter, or "id 0"
- child selected_scene (Scene, get/set/observe)
- child selected_track (Track, get/set/observe)

### Properties
- prop draw_mode (bool, get/set/observe): Reflects the state of the envelope/automation Draw Mode Switch in the transport bar, as toggled with Cmd/Ctrl-B. | 0 = breakpoint editing (shows arrow), 1 = drawing (shows pencil)
- prop follow_song (bool, get/set/observe): Reflects the state of the Follow switch in the transport bar as toggled with Cmd/Ctrl-F. | 0 = don't follow playback position, 1 = follow playback position

### Functions
- fn select_device(id NN): Selects the given device object in its track. | You may obtain the id using a live.path or by using `get devices` on a track, for example. | The track containing the device will not be shown automatically, and the device gets the appointed device (blue hand) only if its track is selected.

## SpectralResonatorDevice
- URL: https://docs.cycling74.com/apiref/lom/spectralresonatordevice/
- Inherits (per docs text): Device — "An SpectralResonatorDevice has all the properties, functions and children of a Device."
- Description: This class represents an instance of a Spectral Resonator device in Live. | An SpectralResonatorDevice has all the properties, functions and children of a Device. Listed below are members unique to SpectralResonatorDevice.
- Counts: 0 children, 7 properties, 0 functions

### Properties
- prop frequency_dial_mode (int, get/set/observe): Get, set and observe the Freq control's mode. | 0 = Hertz, 1 = MIDI note values.
- prop midi_gate (int, get/set/observe): Get, set and observe the MIDI gate switch's state. | 0 = Off, 1 = On.
- prop mod_mode (int, get/set/observe): Get, set and observe the Modulation Mode. | 0 = None, 1 = Chorus, 2 = Wander, 3 = Granular.
- prop mono_poly (int, get/set/observe): Get, set and observe the Mono/Poly switch's state. | 0 = Mono, 1 = Poly.
- prop pitch_mode (int, get/set/observe): Get, set and observe the Pitch Mode. | 0 = Internal, 1 = MIDI.
- prop pitch_bend_range (int, get/set/observe): Get, set and observe the Pitch Bend Range.
- prop polyphony (int, get/set/observe): Get, set and observe the Polyphony. | 0 = 2, 1 = 4, 2 = 8, 3 = 16 voices.

## TakeLane
- URL: https://docs.cycling74.com/apiref/lom/takelane/
- Canonical path(s): `live_set tracks N take_lanes M`
- Description: This class represents a take lane in Live. Tracks in Live can have take lanes in Arrangement View, which are used for comping. If take lanes exist for a track, they can be shown by right-clicking on a track and choosing Show Take Lanes.
- Counts: 1 children, 1 properties, 2 functions

### Children
- child arrangement_clips (list of Clip, get/observe): The list of this take lane's Arrangement View clip IDs

### Properties
- prop name (symbol, get/set/observe): The name as shown in the take lane header.

### Functions
- fn create_audio_clip(file_path: symbol, start_time: float): Given a valid audio file in a supported format, passing its absolute path (on Mac, starting with `/Volumes/(drive name)/`) creates an audio clip referencing the file in the arrangement view at the specified `start_time` in beats. | Prints an error if the track is not an audio track, if the track is frozen or if the track is being recorded into. `start_time` must be within the range `[0., 1576800]`.
- fn create_midi_clip(start_time: float, length: float): Creates an empty MIDI clip with the specified `length` in beats and inserts it into the arrangement at the specified `start_time` in beats. | Prints an error if the track is not a MIDI track, if the track is frozen or when the track is currently being recorded into. `start_time` must be within the range `[0., 1576800]`.

## this_device
- URL: https://docs.cycling74.com/apiref/lom/this_device/
- Canonical path(s): `live_set tracks N devices M`
- Description: This root path represents the device containing the live.path object to which the `goto this_device` message is sent. The class of this object is `Device`.
- Note: Root path alias: the docs say 'The class of this object is `Device`'; this page has no children/properties/functions of its own.
- Counts: 0 children, 0 properties, 0 functions

## Track
- URL: https://docs.cycling74.com/apiref/lom/track/
- Canonical path(s): `live_set tracks N`
- Description: This class represents a track in Live. It can either be an audio track, a MIDI track, a return track or the master track. The master track and at least one Audio or MIDI track will be always present. Return tracks are optional. | Not all properties are supported by all types of tracks. The properties are marked accordingly.
- Counts: 7 children, 40 properties, 10 functions

### Children
- child take_lanes (list of TakeLane, get/observe): The list of this track's take lanes
- child clip_slots (list of ClipSlot, get/observe)
- child arrangement_clips (list of Clip, get/observe) [since Live 11.0]: The list of this track's Arrangement View clip IDs
- child devices (list of Device, get/observe): Includes mixer device.
- child group_track (Track, get): The Group Track, if the Track is grouped. If it is not, *id 0* is returned.
- child mixer_device (MixerDevice, get)
- child view (Track.View, get)

### Properties
- prop arm (bool, get/set/observe): 1 = track is armed for recording. [not in return/master tracks]
- prop available_input_routing_channels (dictionary, get/observe): The list of available source channels for the track's input routing. It's represented as a *dictionary* with the following key: | `available_input_routing_channels` [list] | The list contains *dictionaries* as described in *input_routing_channel*. | Only available on MIDI and audio tracks.
- prop available_input_routing_types (dictionary, get/observe): The list of available source types for the track's input routing. It's represented as a *dictionary* with the following key: | `available_input_routing_types` [list] | The list contains *dictionaries* as described in *input_routing_type*. | Only available on MIDI and audio tracks.
- prop available_output_routing_channels (dictionary, get/observe): The list of available target channels for the track's output routing. It's represented as a *dictionary* with the following key: | `available_output_routing_channels` [list] | The list contains *dictionaries* as described in *output_routing_channel*. | Not available on the master track.
- prop available_output_routing_types (dictionary, get/observe): The list of available target types for the track's output routing. It's represented as a *dictionary* with the following key: | `available_output_routing_types` [list] | The list contains *dictionaries* as described in *output_routing_type*. | Not available on the master track.
- prop back_to_arranger (bool, get/set/observe): Get/set/observe the current state of the Single Track Back to Arrangement button (1 = highlighted). This button is used to indicate that the current state of the playback differs from what is stored in the Arrangement. | Setting this property to 0 will make Live go back to playing the track's arrangement content. For group tracks, this means that all of the tracks that belong to the group and any subgroups will go back to playing the arrangement.
- prop can_be_armed (bool, get): 0 for return and master tracks.
- prop can_be_frozen (bool, get): 1 = the track can be frozen, 0 = otherwise.
- prop can_show_chains (bool, get): 1 = the track contains an Instrument Rack device that can show chains in Session View.
- prop color (int, get/set/observe): The RGB value of the track's color in the form `0x00rrggbb` or (2^16 * red) + (2^8) * green + blue, where red, green and blue are values from 0 (dark) to 255 (light). | When setting the RGB value, the nearest color from the track color chooser is taken.
- prop color_index (long, get/set/observe): The color index of the track.
- prop fired_slot_index (int, get/observe): Reflects the blinking clip slot. | -1 = no slot fired, -2 = Clip Stop Button fired | First clip slot has index 0. | [not in return/master tracks]
- prop fold_state (int, get/set): 0 = tracks within the Group Track are visible, 1 = Group Track is folded and the tracks within the Group Track are hidden | [only available if `is_foldable` = 1]
- prop has_audio_input (bool, get): 1 for audio tracks.
- prop has_audio_output (bool, get): 1 for audio tracks and MIDI tracks with instruments.
- prop has_midi_input (bool, get): 1 for MIDI tracks.
- prop has_midi_output (bool, get): 1 for MIDI tracks with no instruments and no audio effects.
- prop implicit_arm (bool, get/set/observe): A second arm state, only used by Push so far.
- prop input_meter_left (float, get/observe): Smoothed momentary peak value of left channel input meter, 0.0 to 1.0. For tracks with audio output only. This value corresponds to the meters shown in Live. Please take into account that the left/right audio meters put a significant load onto the GUI part of Live.
- prop input_meter_level (float, get/observe): Hold peak value of input meters of audio and MIDI tracks, 0.0 ... 1.0. For audio tracks it is the maximum of the left and right channels. The hold time is 1 second.
- prop input_meter_right (float, get/observe): Smoothed momentary peak value of right channel input meter, 0.0 to 1.0. For tracks with audio output only. This value corresponds to the meters shown in Live.
- prop input_routing_channel (dictionary, get/set/observe): The currently selected source channel for the track's input routing. It's represented as a *dictionary* with the following keys: | `display_name` [symbol] | `identifier` [symbol] | Can be set to all values found in the track's *available_input_routing_channels*. | Only available on MIDI and audio tracks.
- prop input_routing_type (dictionary, get/set/observe): The currently selected source type for the track's input routing. It's represented as a *dictionary* with the following keys: | `display_name` [symbol] | `identifier` [symbol] | Can be set to all values found in the track's *available_input_routing_types*. | Only available on MIDI and audio tracks.
- prop is_foldable (bool, get): 1 = track can be (un)folded to hide or reveal the contained tracks. This is currently the case for Group Tracks. Instrument and Drum Racks return 0 although they can be opened/closed. This will be fixed in a later release.
- prop is_frozen (bool, get/observe): 1 = the track is currently frozen.
- prop is_grouped (bool, get): 1 = the track is contained within a Group Track.
- prop is_part_of_selection (bool, get)
- prop is_showing_chains (bool, get/set/observe): Get or set whether a track with an Instrument Rack device is currently showing its chains in Session View.
- prop is_visible (bool, get): 0 = track is hidden in a folded Group Track.
- prop mute (bool, get/set/observe): [not in master track]
- prop muted_via_solo (bool, get/observe): 1 = the track or chain is muted due to Solo being active on at least one other track.
- prop name (symbol, get/set/observe): As shown in track header.
- prop output_meter_left (float, get/observe): Smoothed momentary peak value of left channel output meter, 0.0 to 1.0. For tracks with audio output only. This value corresponds to the meters shown in Live. Please take into account that the left/right audio meters add a significant load to Live GUI resource usage.
- prop output_meter_level (float, get/observe): Hold peak value of output meters of audio and MIDI tracks, 0.0 to 1.0. For audio tracks, it is the maximum of the left and right channels. The hold time is 1 second.
- prop output_meter_right (float, get/observe): Smoothed momentary peak value of right channel output meter, 0.0 to 1.0. For tracks with audio output only. This value corresponds to the meters shown in Live.
- prop performance_impact (float, get/observe): Reports the performance impact of this track.
- prop output_routing_channel (dictionary, get/set/observe): The currently selected target channel for the track's output routing. It's represented as a *dictionary* with the following keys: | `display_name` [symbol] | `identifier` [symbol] | Can be set to all values found in the track's *available_output_routing_channels*. | Not available on the master track.
- prop output_routing_type (dictionary, get/set/observe): The currently selected target type for the track's output routing. It's represented as a *dictionary* with the following keys: | `display_name` [symbol] | `identifier` [symbol] | Can be set to all values found in the track's *available_output_routing_types*. | Not available on the master track.
- prop playing_slot_index (int, get/observe): First slot has index 0, -2 = Clip Stop slot fired in Session View, -1 = Arrangement recording with no Session clip playing. [not in return/master tracks]
- prop solo (bool, get/set/observe): Remark: when setting this property, the exclusive Solo logic is bypassed, so you have to unsolo the other tracks yourself. [not in master track]

### Functions
- fn create_audio_clip(file_path: symbol, position: float): Given an absolute path to a valid audio file in a supported format, creates an audio clip that references the file at the specified position in the arrangement view. Prints an error if the track is not an audio track, if the track is frozen, or if the track is being recorded into. The position must be within the range [0., 1576800]. | See the `ClipSlot.create_audio_clip` function if you need to create audio clips in session view instead.
- fn create_midi_clip(start_time: float, length: float): Creates an empty MIDI clip and inserts it into the arrangement at the specified time. Throws an error when called on a non-MIDI track or a frozen track, when the specified time is outside the [0., 1576800.] range, or when the track is currently being recorded into. | See the `ClipSlot.create_clip` function if you need to create audio clips in session view instead.
- fn create_take_lane(): Creates a take lane for this track.
- fn delete_clip(clip): Delete the given clip.
- fn delete_device(index): Delete the device at the given index.
- fn duplicate_clip_slot(index): Works like 'Duplicate' in a clip's context menu.
- fn duplicate_clip_to_arrangement(clip, destination_time: float): Duplicate the given clip to the Arrangement, placing it at the given *destination_time* in beats. The source clip can be a session or an arrangement clip.
- fn insert_device(device_name: symbol, target_index?: int) [since Live 12.3]: Attempts to insert the device specified by `device_name` at the given index in the track's device chain. If no index is provided, attempts to insert the device at the end of the chain. Throws an error if insertion is not possible. | `device_name` is the name as it appears in the UI of Live. | Not all indices are valid. As can be expected, indices outside of the range defined by the current length of the device chain are invalid, but there are other limitations: for example, a MIDI effect can't be inserted after an instrument. The rule of thumb is that if an index would be invalid when inserting using the mouse, it's invalid here. | At the moment, only native Live devices can be inserted. Max for Live devices and plug-in are not supported.
- fn jump_in_running_session_clip(beats: float): Modify playback position in running Session clip, if any.
  - param beats: is the amount to jump relatively to the current clip position.
- fn stop_all_clips(): Stops all playing and fired clips in this track.

## Track.View
- URL: https://docs.cycling74.com/apiref/lom/track_view/
- Canonical path(s): `live_set tracks N view`
- Description: Representing the view aspects of a track.
- Counts: 1 children, 2 properties, 1 functions

### Children
- child selected_device (Device, get/observe): The selected device or the first selected device (in case of multi/group selection).

### Properties
- prop device_insert_mode (int, get/set/observe): Determines where a device will be inserted when loaded from the browser. 0 = add device at the end, 1 = add device to the left of the selected device, 2 = add device to the right of the selected device.
- prop is_collapsed (bool, get/set/observe): In Arrangement View: 1 = track collapsed, 0 = track opened.

### Functions
- fn select_instrument() -> bool 0 = there are no devices to select: Selects track's instrument or first device, makes it visible and focuses on it.

## TuningSystem
- URL: https://docs.cycling74.com/apiref/lom/tuningsystem/
- Canonical path(s): `live_set tuning_system`
- Description: This class represents a tuning system in Live.
- Counts: 0 children, 6 properties, 0 functions

### Properties
- prop name (symbol, get/set/observe): The name of the currently active tuning system.
- prop pseudo_octave_in_cents (float, get): The pseudo octave in cents of the currently active tuning system.
- prop lowest_note (dictionary, get/set/observe): The note index within the pseudo octave and octave of the lowest note.
- prop highest_note (dictionary, get/set/observe): The note index within the pseudo octave and octave of the highest note.
- prop reference_pitch (dictionary, get/set/observe): The reference pitch of the current tuning system.
- prop note_tunings (dictionary, get/set/observe): The relative note tunings of the Tuning System in cents. Provided as a single-element dictionary holding an array.

## WavetableDevice
- URL: https://docs.cycling74.com/apiref/lom/wavetabledevice/
- Inherits (per docs text): Device — "A WavetableDevice shares all of the children, functions and properties that a Device has."
- Description: This class represents a Wavetable instrument. | A WavetableDevice shares all of the children, functions and properties that a Device has. Listed below are members unique to it.
- Note: Docs give no type for these properties: oscillator_1_wavetable_category, oscillator_2_wavetable_category, oscillator_1_wavetable_index, oscillator_2_wavetable_index.
- Counts: 0 children, 15 properties, 5 functions

### Properties
- prop filter_routing (int, get/set/observe): Access to the current filter routing. 0 = Serial, 1 = Parallel, 2 = Split.
- prop mono_poly (int, get/set/observe): Access to Wavetable's Poly/Mono switch. 0 = Mono, 1 = Poly.
- prop oscillator_1_effect_mode (int, get/set/observe): Access to oscillator 1's effect mode. 0 = None, 1 = Fm, 2 = Classic, 3 = Modern.
- prop oscillator_2_effect_mode (int, get/set/observe): Access to oscillator 2's effect mode.
- prop oscillator_1_wavetable_category (type not stated, get/set/observe): Access to oscillator 1's wavetable category selector.
- prop oscillator_2_wavetable_category (type not stated, get/set/observe): Access to oscillator 2's wavetable category selector.
- prop oscillator_1_wavetable_index (type not stated, get/set/observe): Access to oscillator 1's wavetable index selector.
- prop oscillator_2_wavetable_index (type not stated, get/set/observe): Access to oscillator 2's wavetable index selector.
- prop oscillator_1_wavetables (StringVector, get/observe): List of names of the wavetables currently available for oscillator 1. Depends on the current wavetable category selection (see *oscillator_1_wavetable_category*).
- prop oscillator_2_wavetables (StringVector, get/observe): List of names of the wavetables currently available for oscillator 2. Depends on the current wavetable category selection (see *oscillator_2_wavetable_category*).
- prop oscillator_wavetable_categories (StringVector, get): List of the names of the available wavetable categories.
- prop poly_voices (int, get/set/observe): The current number of polyphonic voices.
- prop unison_mode (int, get/set/observe): Access to Wavetable's unison mode parameter. | 0 = None | 1 = Classic | 2 = Shimmer | 3 = Noise | 4 = Phase Sync | 5 = Position Spread | 6 = Random Note
- prop unison_voice_count (int, get/set/observe): Access to the number of unison voices.
- prop visible_modulation_target_names (StringVector, get/observe): List of the names of modulation targets currently visible in the modulation matrix.

### Functions
- fn add_parameter_to_modulation_matrix(parameter_to_add: DeviceParameter): Add an instrument parameter to the modulation matrix. Only works for parameters that can be modulated (see *is_parameter_modulatable*).
- fn get_modulation_target_parameter_name(index: int) -> the modulation target parameter name at *index* in the modulation matrix as a [symbol]
- fn get_modulation_value(modulation_target_index: int, modulation_source_index: int) -> the amount of the modulation of the parameter at `modulation_target_index` by the modulation source at `modulation_source_index` in Wavetable's modulation matrix
- fn is_parameter_modulatable(parameter: DeviceParameter) -> 1 = `parameter` can be modulated: Call this before `add_parameter_to_modulation_matrix`.
- fn set_modulation_value(modulation_target_index: int, modulation_source_index: int): Set the amount of the modulation of the parameter at `modulation_target_index` by the modulation source at `modulation_source_index` in Wavetable's modulation matrix.
