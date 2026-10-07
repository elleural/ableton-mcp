# Live 12.4.6 Python API (runtime introspection)

Generated with the `dump_live_api` command on Live 12.4.6. One line per member: `P name [rw|r] doc` for properties, `M signature : doc` for functions, `observable:` lists listenable properties. Licensing, MidiMap and plumbing modules omitted.

## module Application
- F combine_apcs() -> bool : Returns true if multiple APCs should be combined.
- F encrypt_challenge( (int)dongle1, (int)dongle2 [, (int)key_index=0]) -> tuple : Returns an encrypted challenge based on the TEA algortithm
- F encrypt_challenge2( (int)arg1) -> int : Returns the UMAC hash for the given challenge.
- F get_application() -> Application : Returns the application instance.
- F get_random_int( (int)arg1, (int)arg2) -> int : Returns a random integer from the given range.

### Application.Application (bases: LomObject)
- P average_process_usage [r] Reports Live's average CPU load.
- P browser [r] Returns an interface to the browser.
- P canonical_parent [r] Returns the canonical parent of the application.
- P control_surfaces [r] Const access to a list of the control surfaces selected in preferences, in the same order. The list contains None if no control surface is active at t
- P current_dialog_button_count [r] Number of buttons on the current dialog.
- P current_dialog_message [r] Text of the last dialog that appeared; Empty if all dialogs just disappeared.
- P number_of_push_apps_running [r] Returns the number of connected Push apps.
- P open_dialog_count [r] The number of open dialogs in Live. 0 if not dialog is open.
- P peak_process_usage [r] Reports Live's peak CPU load.
- P unavailable_features [r] List of features that are unavailable due to limitations of the current Live edition.
- P view [r] Returns the applications view component.
- M get_bugfix_version( (Application)arg1) -> int : Returns an integer representing the bugfix version of Live.
- M get_build_id( (Application)arg1) -> str : Returns a string identifying the build.
- M get_document( (Application)arg1) -> Song : Returns the current Live Set.
- M get_major_version( (Application)arg1) -> int : Returns an integer representing the major version of Live.
- M get_minor_version( (Application)arg1) -> int : Returns an integer representing the minor version of Live.
- M get_variant( (Application)arg1) -> str : Returns one of the strings in Live.Application.Variants.
- M get_version_string( (Application)arg1) -> str : Returns the full version string of Live.
- M has_option( (Application)arg1, (object)arg2) -> bool : Returns True if the given entry exists in Options.txt, False otherwise.
- M press_current_dialog_button( (Application)arg1, (int)arg2) -> None : Press a button, by index, on the current message box.
- M show_message( (Application)arg1, (Text)text [, (int)buttons=Application.MessageButtons.OK_BUTTON [, (bool)enable_markup=False [, (bool)show_success_icon=False]]]) -> int : Shows a message box, returning the position of the pressed button.
- M show_on_the_fly_message( (Application)arg1, (str)message [, (int)buttons=Application.MessageButtons.OK_BUTTON [, (bool)enable_markup=False [, (bool)show_success_icon=False [, (int)push_dialog_type=Application.PushDialogType.MESSAGE_BOX]]]]) -> int : Same as sh
- observable: average_process_usage, control_surfaces, open_dialog_count, peak_process_usage, unavailable_features

### Application.Application.View (bases: LomObject)
- P browse_mode [r] Return true if HotSwap mode is active for any target.
- P canonical_parent [r] Get the canonical parent of the application view.
- P focused_document_view [r] Return the name of the document view ('Session' or 'Arranger') shown in the currently selected window.
- M available_main_views( (View)arg1) -> StringVector : Return a list of strings with the available subcomponent views, which is to be specified, when using the rest of this classes functions. A 'subcomponent view' is a main view component of a document view, like
- M focus_view( (View)arg1, (object)arg2) -> None : Show and focus one through the identifier string specified view.
- M hide_view( (View)arg1, (object)arg2) -> None : Hide one through the identifier string specified view.
- M is_view_visible( (View)arg1, (object)identifier [, (bool)main_window_only=True]) -> bool : Return true if the through the identifier string specified view is currently visible. If main_window_only is set to False, this will also check in second window. Notific
- M scroll_view( (View)arg1, (int)arg2, (object)arg3, (bool)arg4) -> None : Scroll through the identifier string specified view into the given direction, if possible. Will silently return if the specified view can not perform the requested action.
- M show_view( (View)arg1, (object)arg2) -> None : Show one through the identifier string specified view. Will throw a runtime error if this is called in Live's initialization scope.
- M toggle_browse( (View)arg1) -> None : Reveals the device chain, the browser and starts hot swap for the selected device. Calling this function again stops hot swap.
- M zoom_view( (View)arg1, (int)arg2, (object)arg3, (bool)arg4) -> None : Zoom through the identifier string specified view into the given direction, if possible. Will silently return if the specified view can not perform the requested action.
- observable: browse_mode, focused_document_view, is_view_visible, view_focus_changed

### enum Application.Application.View.NavDirection: down=1, left=2, right=3, up=0

### Application.ControlDescription
- P id [r] 
- P name [r] 

### Application.ControlDescriptionVector
- M append( (ControlDescriptionVector)arg1, (object)arg2) -> None :
- M extend( (ControlDescriptionVector)arg1, (object)arg2) -> None :

### Application.ControlSurfaceProxy
- P control_descriptions [r] 
- P pad_layout [r] The layout of pads on Push.
- P type_name [r] 
- M enable_receive_midi( (ControlSurfaceProxy)arg1, (bool)arg2) -> None :
- M fetch_received_midi_messages( (ControlSurfaceProxy)arg1) -> tuple :
- M fetch_received_values( (ControlSurfaceProxy)arg1) -> tuple :
- M grab_control( (ControlSurfaceProxy)arg1, (int)arg2) -> None :
- M release_control( (ControlSurfaceProxy)arg1, (int)arg2) -> None :
- M send_midi( (ControlSurfaceProxy)arg1, (tuple)arg2) -> None :
- M send_value( (ControlSurfaceProxy)arg1, (tuple)arg2) -> None :
- M subscribe_to_control( (ControlSurfaceProxy)arg1, (int)arg2) -> None :
- M unsubscribe_from_control( (ControlSurfaceProxy)arg1, (int)arg2) -> None :
- observable: control_values_arrived, midi_received, pad_layout

### enum Application.MessageButtons: OK_ACCOUNT_BUTTON=4, OK_BUTTON=0, OK_NEW_SET_BUTTON=1, OK_PURCHASE_BUTTON=5, OK_RETRY_BUTTON=2, SAVE_DONT_SAVE_BUTTON=3

### enum Application.PushDialogType: MESSAGE_BOX=0, OUT_OF_UNLOCKS_DIALOG=5, RENT_TO_OWN_LICENSE_EXPIRED_DIALOG=7

### enum Application.UnavailableFeature: note_velocity_ranges_and_probabilities=0

### Application.UnavailableFeatureVector
- M append( (UnavailableFeatureVector)arg1, (object)arg2) -> None :
- M extend( (UnavailableFeatureVector)arg1, (object)arg2) -> None :

### Application.Variants
- P BETA [r] 
- P INTRO [r] 
- P LITE [r] 
- P STANDARD [r] 
- P SUITE [r] 
- P TRIAL [r] 

## module Browser

### Browser.Browser (bases: LomObject)
- P audio_effects [r] Returns a browser item with access to all the Audio Effects content.
- P clips [r] Returns a browser item with access to all the Clips content.
- P colors [r] Returns a list of browser items containing the configured colors.
- P current_project [r] Returns a browser item with access to all the Current Project content.
- P drums [r] Returns a browser item with access to all the Drums content.
- P filter_type [rw] Bang triggered when the hotswap target has changed.
- P hotswap_target [rw] Bang triggered when the hotswap target has changed.
- P instruments [r] Returns a browser item with access to all the Instruments content.
- P legacy_libraries [r] Returns a list of browser items containing the installed legacy libraries. The list is always empty as legacy library handling has been removed.
- P max_for_live [r] Returns a browser item with access to all the Max For Live content.
- P midi_effects [r] Returns a browser item with access to all the Midi Effects content.
- P packs [r] Returns a browser item with access to all the Packs content.
- P plugins [r] Returns a browser item with access to all the Plugins content.
- P samples [r] Returns a browser item with access to all the Samples content.
- P sounds [r] Returns a browser item with access to all the Sounds content.
- P user_folders [r] Returns a list of browser items containing all the user folders.
- P user_library [r] Returns a browser item with access to all the User Library content.
- M load_item( (Browser)arg1, (BrowserItem)arg2) -> None : Loads the provided browser item.
- M preview_item( (Browser)arg1, (BrowserItem)arg2) -> None : Previews the provided browser item.
- M relation_to_hotswap_target( (Browser)arg1, (BrowserItem)arg2) -> Relation : Returns the relation between the given browser item and the current hotswap target
- M stop_preview( (Browser)arg1) -> None : Stop the current preview.
- observable: filter_type, full_refresh, hotswap_target

### Browser.BrowserItem
- P children [r] Const access to the descendants of this browser item.
- P is_device [r] Indicates if the browser item represents a device.
- P is_folder [r] Indicates if the browser item represents folder.
- P is_loadable [r] True if item can be loaded via the Browser's 'load_item' method.
- P is_selected [r] True if the item is ancestor of or the actual selection.
- P iter_children [r] Const iterable access to the descendants of this browser item.
- P name [r] Const access to the canonical display name of this browser item.
- P source [r] Specifies where does item come from -- i.e. Live pack, user library...
- P uri [r] The uri describes a unique identifier for a browser item.

### Browser.BrowserItemIterator

### Browser.BrowserItemVector
- M append( (BrowserItemVector)arg1, (object)arg2) -> None :
- M extend( (BrowserItemVector)arg1, (object)arg2) -> None :

### enum Browser.FilterType: audio_effect_hotswap=2, count=7, disabled=-1, drum_pad_hotswap=4, hotswap_off=0, instrument_hotswap=1, midi_effect_hotswap=3, midi_track_devices=5, samples=6

### enum Browser.Relation: ancestor=0, descendant=2, equal=1, none=3

## module CcControlDevice

### CcControlDevice.CcControlDevice (bases: Device)
- P custom_bool_target [rw] Return the custom bool target
- P custom_bool_target_list [r] Return the custom bool target list
- P custom_float_target_0 [rw] Return the custom float target 0
- P custom_float_target_0_list [r] Return the custom float target 0 list
- P custom_float_target_1 [rw] Return the custom float target 1
- P custom_float_target_10 [rw] Return the custom float target 10
- P custom_float_target_10_list [r] Return the custom float target 10 list
- P custom_float_target_11 [rw] Return the custom float target 11
- P custom_float_target_11_list [r] Return the custom float target 11 list
- P custom_float_target_1_list [r] Return the custom float target 1 list
- P custom_float_target_2 [rw] Return the custom float target 2
- P custom_float_target_2_list [r] Return the custom float target 2 list
- P custom_float_target_3 [rw] Return the custom float target 3
- P custom_float_target_3_list [r] Return the custom float target 3 list
- P custom_float_target_4 [rw] Return the custom float target 4
- P custom_float_target_4_list [r] Return the custom float target 4 list
- P custom_float_target_5 [rw] Return the custom float target 5
- P custom_float_target_5_list [r] Return the custom float target 5 list
- P custom_float_target_6 [rw] Return the custom float target 6
- P custom_float_target_6_list [r] Return the custom float target 6 list
- P custom_float_target_7 [rw] Return the custom float target 7
- P custom_float_target_7_list [r] Return the custom float target 7 list
- P custom_float_target_8 [rw] Return the custom float target 8
- P custom_float_target_8_list [r] Return the custom float target 8 list
- P custom_float_target_9 [rw] Return the custom float target 9
- P custom_float_target_9_list [r] Return the custom float target 9 list
- M resend( (CcControlDevice)self) -> None : Resend all CC values.
- observable: custom_bool_target, custom_float_target_0, custom_float_target_1, custom_float_target_10, custom_float_target_11, custom_float_target_2, custom_float_target_3, custom_float_target_4, custom_float_target_5, custom_float_target_6, custom_float_target_7, custom_float_target_8, custom_float_target_9

## module Chain

### Chain.Chain (bases: DeviceContainer)
- P canonical_parent [r] Get the canonical parent of the chain.
- P color [rw] Access the color index of the Chain.
- P color_index [rw] Access the color index of the Chain.
- P devices [r] Return const access to all available Devices that are present in the chains
- P has_audio_input [r] return True, if this Chain can be feed with an Audio signal. This is true for all Audio Chains.
- P has_audio_output [r] return True, if this Chain sends out an Audio signal. This is true for all Audio Chains, and MIDI chains with an Instrument.
- P has_midi_input [r] return True, if this Chain can be feed with an Audio signal. This is true for all MIDI Chains.
- P has_midi_output [r] return True, if this Chain sends out MIDI events. This is true for all MIDI Chains with no Instruments.
- P is_auto_colored [rw] Get/set access to the auto color flag of the Chain. If True, the Chain will always have the same color as the containing Track or Chain.
- P mixer_device [r] Return access to the mixer device that holds the chain's mixer parameters: the Volume, Pan, and Sendamounts.
- P mute [rw] Mute/unmute the chain.
- P muted_via_solo [r] Return const access to whether this chain is muted due to some other chain being soloed.
- P name [rw] Read/write access to the name of the Chain, as visible in the track header.
- P solo [rw] Get/Set the solo status of the chain. Note that this will not disable the solo state of any other Chain in the same rack. If you want exclusive solo, 
- M delete_device( (Chain)arg1, (int)arg2) -> None : Remove a device identified by its index from the chain. Throws runtime error if bad index.
- M duplicate_device( (Chain)arg1, (int)arg2) -> None : Duplicate the device at the given index in the chain.
- M insert_device( (Chain)arg1, (str)DeviceName [, (int)DeviceIndex=-1]) -> LomObject : Add a device at a given index in the chain. At end if -1.
- observable: color, color_index, devices, is_auto_colored, mute, muted_via_solo, name, solo

## module ChainMixerDevice

### ChainMixerDevice.ChainMixerDevice (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the mixer device.
- P chain_activator [r] Const access to the Chain's Activator Device Parameter.
- P panning [r] Const access to the Chain's Panning Device Parameter.
- P sends [r] Const access to the Chain's list of Send Amount Device Parameters.
- P volume [r] Const access to the Chain's Volume Device Parameter.
- observable: sends

## module Clip

### Clip.Clip (bases: LomObject)
- P automation_envelopes [r] Const access to a list of all automation envelopes for this clip.
- P available_warp_modes [r] Available for AudioClips only. Get/Set the available warp modes, that can be used.
- P canonical_parent [r] Get the canonical parent of the Clip.
- P color [rw] Get/set access to the color of the Clip (RGB).
- P color_index [rw] Get/set access to the color index of the Clip.
- P end_marker [rw] Get/Set the Clips end marker pos in beats/seconds (unit depends on warping).
- P end_time [r] Get the clip's end time.
- P file_path [r] Get the path of the file represented by the Audio Clip.
- P gain [rw] Available for AudioClips only. Read/write access to the gain setting of the Audio Clip
- P gain_display_string [r] Return a string with the gain as dB value
- P groove [rw] Get the groove associated with this clip.
- P has_envelopes [r] Will notify if the clip gets his first envelope or the last envelope is removed.
- P has_groove [r] Returns true if a groove is associated with this clip.
- P is_arrangement_clip [r] return true if this Clip is an Arrangement Clip. A Clip can be either a Session or Arrangement Clip.
- P is_audio_clip [r] Return true if this Clip is an Audio Clip. A Clip can be either an Audioclip or a MIDI Clip.
- P is_midi_clip [r] return true if this Clip is a MIDI Clip. A Clip can be either an Audioclip or a MIDI Clip.
- P is_overdubbing [r] returns true if the Clip is recording overdubs
- P is_playing [rw] Get/Set if this Clip is currently playing. If the Clips trigger mode is set to a quantization value, the Clip will not start playing immediately. If y
- P is_recording [r] returns true if the Clip was triggered to record or is recording.
- P is_session_clip [r] return true if this Clip is a Session Clip. A Clip can be either a Session or Arrangement Clip.
- P is_take_lane_clip [r] return true if this Clip is a Take Lane Clip. A Take Lane Clip is also always an Arrangement Clip.
- P is_triggered [r] returns true if the Clip was triggered or is playing.
- P launch_mode [rw] Get/Set access to the launch mode setting of the Clip.
- P launch_quantization [rw] Get/Set access to the launch quantization setting of the Clip.
- P legato [rw] Get/Set access to the legato setting of the Clip
- P length [r] Get to the Clips length in beats/seconds (unit depends on warping).
- P loop_end [rw] Get/Set the loop end pos of this Clip in beats/seconds (unit depends on warping).
- P loop_start [rw] Get/Set the Clips loopstart pos in beats/seconds (unit depends on warping).
- P looping [rw] Get/Set the Clips 'loop is enabled' flag .Only Warped Audio Clips or MIDI Clip can be looped.
- P muted [rw] Read/write access to the mute state of the Clip.
- P name [rw] Read/write access to the name of the Clip.
- P pitch_coarse [rw] Available for AudioClips only. Read/write access to the pitch (in halftones) setting of the Audio Clip, ranging from -48 to 48
- P pitch_fine [rw] Available for AudioClips only. Read/write access to the pitch fine setting of the Audio Clip, ranging from -500 to 500
- P playing_position [r] Constant access to the current playing position of the clip. The returned value is the position in beats for midi and warped audio clips, or in second
- P position [rw] Get/Set the loop position of this Clip in beats/seconds (unit depends on warping).
- P ram_mode [rw] Available for AudioClips only. Read/write access to the Ram mode setting of the Audio Clip
- P sample_length [r] Available for AudioClips only. Get the sample length in sample time or -1 if there is no sample available.
- P sample_rate [r] Available for AudioClips only. Read-only access to the Clip's sampling rate.
- P signature_denominator [rw] Get/Set access to the global signature denominator of the Clip.
- P signature_numerator [rw] Get/Set access to the global signature numerator of the Clip.
- P start_marker [rw] Get/Set the Clips start marker pos in beats/seconds (unit depends on warping).
- P start_time [r] Get the clip's start time offset. For Session View clips, this is the time the clip was started. For Arrangement View clips, this is the offset within
- P velocity_amount [rw] Get/Set access to the velocity to volume amount of the Clip.
- P view [r] Get the view of the Clip.
- P warp_markers [r] Available for AudioClips only. Get the warp markers for this audio clip.
- P warp_mode [rw] Available for AudioClips only. Get/Set the warp mode for this audio clip.
- P warping [rw] Available for AudioClips only. Get/Set if this Clip is timestreched.
- P will_record_on_start [r] returns true if the Clip will record on being started.
- M add_new_notes( (Clip)arg1, (object)arg2) -> IntU64Vector : Expects a Python iterable holding a number of Live.Clip.MidiNoteSpecification objects. The objects will be used to construct new notes in the clip.
- M add_warp_marker( (Clip)self, (object)warp_marker) -> None : Available for AudioClips only. Adds the specified warp marker, if possible.
- M apply_note_modifications( (Clip)arg1, (MidiNoteVector)arg2) -> None : Expects a list of notes as returned from get_notes_extended. The content of the list will be used to modify existing notes in the clip, based on matching note IDs. This function should be us
- M automation_envelope( (Clip)arg1, (DeviceParameter)arg2) -> Envelope : Return the envelope for the given parameter.Returns None if the envelope doesn't exist.Returns None for Arrangement clips.Returns None for parameters from a different track.
- M beat_to_sample_time( (Clip)self, (float)beat_time) -> float : Available for AudioClips only. Converts the given beat time to sample time. Raises an error if the sample is not warped.
- M clear_all_envelopes( (Clip)arg1) -> None : Clears all envelopes for this clip.
- M clear_envelope( (Clip)arg1, (DeviceParameter)arg2) -> None : Clears the envelope of this clips given parameter.
- M create_automation_envelope( (Clip)arg1, (DeviceParameter)arg2) -> Envelope : Creates an envelope for a given parameter and returns it.This should only be used if the envelope doesn't exist.Raises an error if the envelope can't be created.
- M crop( (Clip)arg1) -> None : Crops the clip. The region that is cropped depends on whether the clip is looped or not. If looped, the region outside of the loop is removed. If not looped, the region outside the start and end markers is removed.
- M deselect_all_notes( (Clip)arg1) -> None : De-selects all notes present in the clip.
- M duplicate_loop( (Clip)arg1) -> None : Make the loop two times longer and duplicates notes and envelopes. Duplicates the clip start/end range if the clip is not looped.
- M duplicate_notes_by_id( (Clip)self, (object)note_ids [, (object)destination_time=None [, (int)transposition_amount=0]]) -> IntU64Vector : Duplicate all notes matching the given note IDs. If the optional destination_time is not provided, new notes will be insert
- M duplicate_region( (Clip)self, (float)region_start, (float)region_length, (float)destination_time [, (int)pitch=-1 [, (int)transposition_amount=0]]) -> None : Duplicate the notes in the specified region to the destination_time. Only notes of the specified pitch
- M fire( (Clip)arg1) -> None : (Re)Start playing this Clip.
- M get_all_notes_extended( (Clip)arg1) -> MidiNoteVector : Returns a list of all MIDI notes from the clip, regardless of their position relative to the start and end markers/loop start and loop end. Each note is represented by a Live.Clip.MidiNote object. The ret
- M get_notes( (Clip)self, (float)from_time, (int)from_pitch, (float)time_span, (int)pitch_span) -> tuple : Returns a tuple of tuples where each inner tuple represents a note starting in the given pitch- and time range. The inner tuple contains pitch, time, durati
- M get_notes_by_id( (Clip)arg1, (object)note_ids) -> MidiNoteVector : Return a list of MIDI notes matching the given note IDs.
- M get_notes_extended( (Clip)arg1, (int)from_pitch, (int)pitch_span, (float)from_time, (float)time_span) -> MidiNoteVector : Returns a list of MIDI notes from the given pitch and time range. Each note is represented by a Live.Clip.MidiNote object. The returned li
- M get_selected_notes( (Clip)arg1) -> tuple : Returns a tuple of tuples where each inner tuple represents a selected note. The inner tuple contains pitch, time, duration, velocity, and mute state.
- M get_selected_notes_extended( (Clip)arg1) -> MidiNoteVector : Returns a list of all MIDI notes from the clip that are currently selected. Each note is represented by a Live.Clip.MidiNote object. The returned list can be modified freely, but modifications will n
- M move_playing_pos( (Clip)arg1, (float)arg2) -> None : Jump forward or backward by the specified relative amount in beats. Will do nothing, if the Clip is not playing.
- M move_warp_marker( (Clip)self, (float)marker_beat_time, (float)beat_time_distance) -> None : Available for AudioClips only. Moves the specified warp marker by the specified beat time amount, if possible.
- M note_number_to_name( (Clip)self, (int)midi_pitch) -> str : Return a human-readable name for the given MIDI note number. Takes into account the scale and tonal spelling settings of the clip, as well as the current tuning system (if any)
- M quantize( (Clip)arg1, (int)arg2, (float)arg3) -> None : Quantize all notes in a clip or align warp markers.
- M quantize_pitch( (Clip)arg1, (int)arg2, (int)arg3, (float)arg4) -> None : Quantize all the notes of a given pitch. Raises an error on audio clips.
- M remove_notes( (Clip)arg1, (float)arg2, (int)arg3, (float)arg4, (int)arg5) -> None : Delete all notes starting in the given pitch- and time range.
- M remove_notes_by_id( (Clip)arg1, (object)arg2) -> None : Delete all notes matching the given note IDs. This function should NOT be used to implement modification of existing notes (i.e. in combination with add_new_notes), as that leads to loss of per-note event
- M remove_notes_extended( (Clip)arg1, (int)from_pitch, (int)pitch_span, (float)from_time, (float)time_span) -> None : Delete all notes starting in the given pitch and time range. This function should NOT be used to implement modification of existing notes (i.e. i
- M remove_warp_marker( (Clip)self, (float)beat_time) -> None : Available for AudioClips only. Removes the specified warp marker, if possible.
- M replace_selected_notes( (Clip)arg1, (tuple)arg2) -> None : Called with a tuple of tuples where each inner tuple represents a note in the same format as returned by get_selected_notes. The notes described that way will then be used to replace the old selection.
- M sample_to_beat_time( (Clip)self, (float)sample_time) -> float : Available for AudioClips only. Converts the given sample time to beat time. Raises an error if the sample is not warped.
- M scrub( (Clip)self, (float)scrub_position) -> None : Scrubs inside a clip. scrub_position defines the position in beats that the scrub will start from. The scrub will continue until stop_scrub is called. Global quantization applies to the scrub's position and l
- M seconds_to_sample_time( (Clip)self, (float)seconds) -> float : Available for AudioClips only. Converts the given seconds to sample time. Raises an error if the sample is warped.
- M select_all_notes( (Clip)arg1) -> None : Selects all notes present in the clip.
- M select_notes_by_id( (Clip)arg1, (object)arg2) -> None : Selects all notes matching the given note IDs.
- M set_fire_button_state( (Clip)arg1, (bool)arg2) -> None : Set the clip's fire button state directly. Supports all launch modes.
- M set_notes( (Clip)arg1, (tuple)arg2) -> None : Called with a tuple of tuples where each inner tuple represents a note in the same format as returned by get_notes. The notes described that way will then be added to the clip.
- M stop( (Clip)arg1) -> None : Stop playing this Clip.
- M stop_scrub( (Clip)arg1) -> None : Stops the current scrub.
- observable: color, color_index, end_marker, end_time, file_path, gain, groove, has_envelopes, is_overdubbing, is_recording, launch_mode, launch_quantization, legato, loop_end, loop_jump, loop_start, looping, muted, name, notes, pitch_coarse, pitch_fine, playing_position, playing_status, position, ram_mode, signature_denominator, signature_numerator, start_marker, start_time, velocity_amount, warp_markers, warp_mode, warping

### Clip.Clip.View (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the clip view.
- P grid_is_triplet [rw] Get/set wether the grid is showing in triplet mode.
- P grid_quantization [rw] Get/set clip grid quantization resolution.
- M hide_envelope( (View)arg1) -> None : Hide the envelope view.
- M select_envelope_parameter( (View)arg1, (DeviceParameter)arg2) -> None : Select the given device parameter in the envelope view.
- M show_envelope( (View)arg1) -> None : Show the envelope view.
- M show_loop( (View)arg1) -> None : Show the entire loop in the detail view.

### enum Clip.ClipLaunchQuantization: q_2_bars=4, q_4_bars=3, q_8_bars=2, q_bar=5, q_eighth=10, q_eighth_triplet=11, q_global=0, q_half=6, q_half_triplet=7, q_none=1, q_quarter=8, q_quarter_triplet=9, q_sixteenth=12, q_sixteenth_triplet=13, q_thirtysecond=14

### enum Clip.GridQuantization: count=10, g_2_bars=3, g_4_bars=2, g_8_bars=1, g_bar=4, g_eighth=7, g_half=5, g_quarter=6, g_sixteenth=8, g_thirtysecond=9, no_grid=0

### enum Clip.LaunchMode: gate=1, repeat=3, toggle=2, trigger=0

### Clip.MidiNote
- P duration [rw] 
- P mute [rw] 
- P note_id [r] A numerical ID that's unique within the originating clip of the note. Not to be used directly, but important for other API calls, namely apply_note_mo
- P pitch [rw] 
- P probability [rw] 
- P release_velocity [rw] 
- P start_time [rw] 
- P velocity [rw] 
- P velocity_deviation [rw] 

### Clip.MidiNoteSpecification

### Clip.MidiNoteVector
- M append( (MidiNoteVector)arg1, (object)arg2) -> None :
- M extend( (MidiNoteVector)arg1, (object)arg2) -> None :

### Clip.WarpMarker
- P beat_time [r] A WarpMarker's beat time.
- P sample_time [r] A WarpMarker's sample time.

### Clip.WarpMarkerVector
- M append( (WarpMarkerVector)arg1, (object)arg2) -> None :
- M extend( (WarpMarkerVector)arg1, (object)arg2) -> None :

### enum Clip.WarpMode: beats=0, complex=4, complex_pro=6, count=7, repitch=3, rex=5, texture=2, tones=1

## module ClipSlot

### ClipSlot.ClipSlot (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the ClipSlot.
- P clip [r] Returns the Clip which this clipslots currently owns. Might be None.
- P color [r] Returns the canonical color for the clip slot or None if it does not exist.
- P color_index [r] Returns the canonical color index for the clip slot or None if it does not exist.
- P controls_other_clips [r] Returns true if firing this slot will fire clips in other slots. Can only be true for slots in group tracks.
- P has_clip [r] Returns true if this Clipslot owns a Clip.
- P has_stop_button [rw] Get/Set if this Clip has a stop button, which will, if fired, stop any other Clip that is currently playing the Track we do belong to.
- P is_group_slot [r] Returns whether this clip slot is a group track slot (group slot).
- P is_playing [r] Returns whether the clip associated with the slot is playing.
- P is_recording [r] Returns whether the clip associated with the slot is recording.
- P is_triggered [r] Const access to the triggering state of the clip slot.
- P playing_status [r] Const access to the playing state of the clip slot. Can be either stopped, playing, or recording.
- P will_record_on_start [r] returns true if the clip slot will record on being fired.
- M create_audio_clip( (ClipSlot)arg1, (object)arg2) -> Clip : Creates an audio clip referencing the file at the given absolute path in the slot. Throws an error when called on non-empty slots or slots in non-audio or frozen tracks, or when the path doesn't point 
- M create_clip( (ClipSlot)arg1, (float)arg2) -> Clip : Creates an empty clip with the given length in the slot. Throws an error when called on non-empty slots or slots in non-MIDI tracks.
- M delete_clip( (ClipSlot)arg1) -> None : Removes the clip contained in the slot. Raises an exception if the slot was empty.
- M duplicate_clip_to( (ClipSlot)arg1, (ClipSlot)arg2) -> None : Duplicates the slot's clip to the passed in target slot. Overrides the target's clip if it's not empty. Raises an exception if the (source) slot itself is empty, or if source and target have differen
- M fire( (ClipSlot)arg1) -> None : Fire a Clip if this Clipslot owns one, else trigger the stop button, if we have one.
- M set_fire_button_state( (ClipSlot)arg1, (bool)arg2) -> None : Set the clipslot's fire button state directly. Supports all launch modes.
- M stop( (ClipSlot)arg1) -> None : Stop playing the contained Clip, if there is a Clip and its currently playing.
- observable: color, color_index, controls_other_clips, has_clip, has_stop_button, is_triggered, playing_status

### enum ClipSlot.ClipSlotPlayingState: recording=2, started=1, stopped=0

## module CompressorDevice

### CompressorDevice.CompressorDevice (bases: Device)
- P available_input_routing_channels [r] Return a list of source channels for input routing in the sidechain.
- P available_input_routing_types [r] Return a list of source types for input routing in the sidechain.
- P input_routing_channel [rw] Get and set the current source channel for input routing in the sidechain. Raises ValueError if the channel isn't one of the current values in availab
- P input_routing_type [rw] Get and set the current source type for input routing in the sidechain. Raises ValueError if the type isn't one of the current values in available_inp
- observable: available_input_routing_channels, available_input_routing_types, input_routing_channel, input_routing_type

## module Conversions
- F audio_to_midi_clip( (Song)song, (Clip)audio_clip, (int)audio_to_midi_type) -> None : Creates a MIDI clip in a new MIDI track with the notes extracted from the given audio_clip. The `audio_to_midi_type` decides which algorithm is used in the process. Raises err
- F create_drum_rack_from_audio_clip( (Song)song, (Clip)audio_clip) -> None : Creates a new track with a drum rack with a simpler on the first pad with the specified audio clip.
- F create_midi_track_from_drum_pad( (Song)song, (DrumPad)drum_pad) -> None : Creates a new Midi track containing the specified Drum Pad's device chain.
- F create_midi_track_with_simpler( (Song)song, (Clip)audio_clip) -> None : Creates a new Midi track with a simpler including the specified audio clip.
- F is_convertible_to_midi( (Song)song, (Clip)audio_clip) -> bool : Returns whether `audio_clip` can be converted to MIDI. Raises error when called with a MIDI clip
- F move_devices_on_track_to_new_drum_rack_pad( (Song)song, (int)track_index) -> LomObject : Moves the entire device chain of the track according to the track index onto the C1 (note 36) drum pad of a new drum rack in a new track.If the track associated with the t
- F sliced_simpler_to_drum_rack( (Song)song, (SimplerDevice)simpler) -> None : Converts the Simpler into a Drum Rack, assigning each slice to a drum pad. Calling it on a non-sliced simpler raises an error.

### enum Conversions.AudioToMidiType: drums_to_midi=2, harmony_to_midi=0, melody_to_midi=1

## module Device

### Device.ATimeableValueVector
- M append( (ATimeableValueVector)arg1, (object)arg2) -> None :
- M extend( (ATimeableValueVector)arg1, (object)arg2) -> None :

### Device.Device (bases: LomObject)
- P can_compare_ab [r] Returns true if the Device has the capability to AB compare.
- P can_have_chains [r] Returns true if the device is a rack.
- P can_have_drum_pads [r] Returns true if the device is a drum rack.
- P canonical_parent [r] Get the canonical parent of the Device.
- P class_display_name [r] Return const access to the name of the device's class name as displayed in Live's browser and device chain
- P class_name [r] Return const access to the name of the device's class.
- P is_active [r] Return const access to whether this device is active. This will be false bothwhen the device is off and when it's inside a rack device which is off.
- P is_using_compare_preset_b [rw] Returns whether the Device has loaded the preset in compare slot B. Only relevant if can_compare_ab, otherwise errors.
- P latency_in_ms [r] Returns the latency of the device in ms.
- P latency_in_samples [r] Returns the latency of the device in samples.
- P name [rw] Return access to the name of the device.
- P parameters [r] Const access to the list of available automatable parameters for this device.
- P type [r] Return the type of the device.
- P view [r] Representing the view aspects of a device.
- M save_preset_to_compare_ab_slot( (Device)arg1) -> None : Saves the current state of the device to the compare AB slot. Only relevant if can_compare_ab, otherwise throws.
- M store_chosen_bank( (Device)arg1, (int)arg2, (int)arg3) -> None : Set the selected bank in the device for persistency.
- observable: is_active, is_using_compare_preset_b, latency_in_ms, latency_in_samples, name, parameters

### Device.Device.View (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the View.
- P is_collapsed [rw] Get/Set/Listen if the device is shown collapsed in the device chain.
- observable: is_collapsed

### enum Device.DeviceType: audio_effect=2, instrument=1, midi_effect=4, undefined=0

## module DeviceIO

### DeviceIO.DeviceIO (bases: LomObject)
- P available_routing_channels [r] Return a list of channels for this IO endpoint.
- P available_routing_types [r] Return a list of available routing types for this IO endpoint.
- P canonical_parent [r] Get the canonical parent of the device IO.
- P default_external_routing_channel_is_none [rw] Get and set whether the default routing channel for External routing types is none.
- P routing_channel [rw] Get and set the current routing channel. Raises ValueError if the channel isn't one of the current values in available_routing_channels.
- P routing_type [rw] Get and set the current routing type. Raises ValueError if the type isn't one of the current values in available_routing_types.
- observable: available_routing_channels, available_routing_types, routing_channel, routing_type

## module DeviceParameter

### enum DeviceParameter.AutomationState: none=0, overridden=2, playing=1

### DeviceParameter.DeviceParameter (bases: LomObject)
- P automation_state [r] Returns state of type AutomationState.
- P canonical_parent [r] Get the canonical parent of the device parameter.
- P default_value [r] Return the default value for this parameter. A Default value is only available for non-quantized parameter types (see 'is_quantized').
- P display_value [rw] Get/Set the current value (as visible in the GUI) this parameter. The value must be inside the min/max properties of this device.
- P is_enabled [r] Returns false if the parameter has been macro mapped or disabled by Max.
- P is_quantized [r] Returns True, if this value is a boolean or integer like switch. Non quantized values are continues float values.
- P max [r] Returns const access to the upper value of the allowed range for this parameter
- P min [r] Returns const access to the lower value of the allowed range for this parameter
- P name [r] Returns const access the name of this parameter, as visible in Lives automation choosers.
- P original_name [r] Returns const access the original name of this parameter, unaffected of any renamings.
- P short_value_items [r] Return the list of possible values for this parameter. Like value_items, but prefers short value names if available. Raises an error if 'is_quantized'
- P state [r] Returns the state of the parameter: - enabled - the parameter's value can be changed, - irrelevant - the parameter is enabled, but value changes will 
- P value [rw] Get/Set the current internal value of this parameter. The value must be inside the min/max properties of this device.
- P value_items [r] Return the list of possible values for this parameter. Raises an error if 'is_quantized' is False.
- M begin_gesture( (DeviceParameter)arg1) -> None : Notify the begin of a modification of the parameter, when a sequence of modifications have to be consider a consistent group -- for Sexample, when recording automation.
- M end_gesture( (DeviceParameter)arg1) -> None : Notify the end of a modification of the parameter. See begin_gesture.
- M re_enable_automation( (DeviceParameter)arg1) -> None : Reenable automation for this parameter.
- M str_for_value( (DeviceParameter)arg1, (float)arg2) -> str : Return a string representation of the given value. To be used for display purposes only. This value can include characters like 'db' or 'hz', depending on the type of the parameter.
- observable: automation_state, display_value, name, state, value

### enum DeviceParameter.ParameterState: disabled=2, enabled=0, irrelevant=1

## module DriftDevice

### DriftDevice.DriftDevice (bases: Device)
- P mod_matrix_filter_source_1_index [rw] Return the filter mod source 1 index
- P mod_matrix_filter_source_1_list [r] Return the filter mod source 1 list
- P mod_matrix_filter_source_2_index [rw] Return the filter mod source 2 index
- P mod_matrix_filter_source_2_list [r] Return the filter mod source 2 list
- P mod_matrix_lfo_source_index [rw] Return the lfo mod source index
- P mod_matrix_lfo_source_list [r] Return the lfo mod source list
- P mod_matrix_pitch_source_1_index [rw] Return the pitch mod source 1 index
- P mod_matrix_pitch_source_1_list [r] Return the pitch mod source 1 list
- P mod_matrix_pitch_source_2_index [rw] Return the pitch mod source 2 index
- P mod_matrix_pitch_source_2_list [r] Return the pitch mod source 2 list
- P mod_matrix_shape_source_index [rw] Return the shape mod source index
- P mod_matrix_shape_source_list [r] Return the shape mod source list
- P mod_matrix_source_1_index [rw] Return the custom mod source 1 index
- P mod_matrix_source_1_list [r] Return the custom mod source 1 list
- P mod_matrix_source_2_index [rw] Return the custom mod source 2 index
- P mod_matrix_source_2_list [r] Return the custom mod source 2 list
- P mod_matrix_source_3_index [rw] Return the custom mod source 3 index
- P mod_matrix_source_3_list [r] Return the custom mod source 3 list
- P mod_matrix_target_1_index [rw] Return the custom mod target 1 index
- P mod_matrix_target_1_list [r] Return the custom mod target 1 list
- P mod_matrix_target_2_index [rw] Return the custom mod target 2 index
- P mod_matrix_target_2_list [r] Return the custom mod target 2 list
- P mod_matrix_target_3_index [rw] Return the custom mod target 3 index
- P mod_matrix_target_3_list [r] Return the custom mod target 3 list
- P pitch_bend_range [rw] Return the Pitch Bend Range
- P voice_count_index [rw] Return the voice count index
- P voice_count_list [r] Return the voice count list
- P voice_mode_index [rw] Return the voice mode index
- P voice_mode_list [r] Return the voice mode list
- observable: mod_matrix_filter_source_1_index, mod_matrix_filter_source_2_index, mod_matrix_lfo_source_index, mod_matrix_pitch_source_1_index, mod_matrix_pitch_source_2_index, mod_matrix_shape_source_index, mod_matrix_source_1_index, mod_matrix_source_2_index, mod_matrix_source_3_index, mod_matrix_target_1_index, mod_matrix_target_2_index, mod_matrix_target_3_index, pitch_bend_range, voice_count_index, voice_mode_index

## module DrumCellDevice

### DrumCellDevice.DrumCellDevice (bases: Device)
- P gain [rw] Return the Gain value
- observable: gain

## module DrumChain

### DrumChain.DrumChain (bases: Chain)
- P choke_group [rw] Access to the chain's choke group setting.
- P in_note [rw] Access to the incoming MIDI note that will trigger this chain.
- P out_note [rw] Access to the MIDI note sent to the devices in the chain.
- observable: choke_group, in_note, out_note

## module DrumPad

### DrumPad.DrumPad (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the drum pad.
- P chains [r] Return const access to the list of chains in this drum pad.
- P mute [rw] Mute/unmute the pad.
- P name [r] Return const access to the drum pad's name. It depends on the contained chains.
- P note [r] Get the MIDI note of the drum pad.
- P solo [rw] Solo/unsolo the pad.
- M delete_all_chains( (DrumPad)arg1) -> None : Deletes all chains associated with a drum pad. This is equivalent to deleting a drum rack pad in Live.
- observable: chains, mute, name, solo

## module Envelope

### Envelope.Envelope (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the envelope.
- P parameter [r] Read-only access to the parameter controlled by the envelope.
- M create_event( (Envelope)arg1, (EnvelopeEvent)arg2) -> None : Creates a new event at the specified time with the given value and, optionally, control coefficients.
- M delete_events_in_range( (Envelope)arg1, (float)arg2, (float)arg3) -> None : Deletes the events in the specified time range.
- M events_in_range( (Envelope)arg1, (float)arg2, (float)arg3) -> EnvelopeEventVector : Returns the events in the specified time range.
- M insert_step( (Envelope)arg1, (float)arg2, (float)arg3, (float)arg4) -> None : Given a start time, a step length and a value, creates a step in the envelope.
- M value_at_time( (Envelope)arg1, (float)arg2) -> float : Returns the parameter value at the specified time.

### Envelope.EnvelopeEvent
- P control_coefficients [rw] 
- P time [rw] 
- P value [rw] 

### Envelope.EnvelopeEventControlCoefficients
- P x1 [rw] 
- P x2 [rw] 
- P y1 [rw] 
- P y2 [rw] 

### Envelope.EnvelopeEventVector
- M append( (EnvelopeEventVector)arg1, (object)arg2) -> None :
- M extend( (EnvelopeEventVector)arg1, (object)arg2) -> None :

## module Eq8Device

### enum Eq8Device.EditMode: a=0, b=1

### Eq8Device.Eq8Device (bases: Device)
- P edit_mode [rw] Access to Eq8's edit mode.
- P global_mode [rw] Access to Eq8's global mode.
- P oversample [rw] Access to Eq8's oversample value.
- observable: edit_mode, global_mode, oversample

### Eq8Device.Eq8Device.View (bases: View)
- P selected_band [rw] Access to the selected filter band.
- observable: selected_band

### enum Eq8Device.GlobalMode: left_right=1, mid_side=2, stereo=0

## module Groove

### enum Groove.Base: count=6, gb_eight=1, gb_eight_triplet=2, gb_four=0, gb_sixteen=3, gb_sixteen_triplet=4, gb_thirtytwo=5

### Groove.Groove (bases: LomObject)
- P base [rw] Get/set the groove's base grid.
- P canonical_parent [r] Get the canonical parent of the groove.
- P name [rw] Read/write/listen access to the groove's name
- P quantization_amount [rw] Read/write/listen access to the groove's quantization amount.
- P random_amount [rw] Read/write/listen access to the groove's random amount.
- P timing_amount [rw] Read/write/listen access to the groove's timing amount.
- P velocity_amount [rw] Read/write/listen access to the groove's velocity amount.
- observable: name, quantization_amount, random_amount, timing_amount, velocity_amount

## module GroovePool

### GroovePool.GroovePool (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the groove pool.
- P grooves [r] Access to the list of grooves
- observable: grooves

## module HybridReverbDevice

### HybridReverbDevice.HybridReverbDevice (bases: Device)
- P ir_attack_time [rw] Return the current IrAttackTime
- P ir_category_index [rw] Return the current IR category index
- P ir_category_list [r] Return the current IR categories list
- P ir_decay_time [rw] Return the current IrDecayTime
- P ir_file_index [rw] Return the current IR file index
- P ir_file_list [r] Return the current IR file list
- P ir_size_factor [rw] Return the current IrSizeFactor
- P ir_time_shaping_on [rw] Return the current IrTimeShapingOn
- observable: ir_attack_time, ir_category_index, ir_decay_time, ir_file_index, ir_file_list, ir_size_factor, ir_time_shaping_on

## module LooperDevice

### LooperDevice.LooperDevice (bases: Device)
- P loop_length [r] The length of Looper's buffer.
- P overdub_after_record [rw] If true, Looper will switch to overdub after recording, when recording a fixed number of bars. Otherwise, the switch will be to playback without overd
- P record_length_index [rw] Access to the Record Length chooser entry index.
- P record_length_list [r] Read-only access to the list of Record Length chooser entry strings.
- P tempo [r] The tempo of Looper's buffer.
- M clear( (LooperDevice)arg1) -> None : Erase Looper's recorded content.
- M double_length( (LooperDevice)arg1) -> None : Double the length of Looper's buffer.
- M double_speed( (LooperDevice)arg1) -> None : Double the speed of Looper's playback.
- M export_to_clip_slot( (LooperDevice)arg1, (ClipSlot)arg2) -> None : Export Looper's content to a Session Clip Slot.
- M half_length( (LooperDevice)arg1) -> None : Halve the length of Looper's buffer.
- M half_speed( (LooperDevice)arg1) -> None : Halve the speed of Looper's playback.
- M overdub( (LooperDevice)arg1) -> None : Play back while adding additional layers of incoming audio.
- M play( (LooperDevice)arg1) -> None : Play back without overdubbing.
- M record( (LooperDevice)arg1) -> None : Record incoming audio.
- M stop( (LooperDevice)arg1) -> None : Stop Looper's playback.
- M undo( (LooperDevice)arg1) -> None : Erase everything that was recorded since the last time Overdub was enabled. Calling a second time will restore the material erased by the previous undooperation.
- observable: loop_length, overdub_after_record, record_length_index, tempo

## module MaxDevice

### MaxDevice.MaxDevice (bases: Device)
- P audio_inputs [r] Const access to a list of all audio inputs of the device.
- P audio_outputs [r] Const access to a list of all audio outputs of the device.
- P midi_inputs [r] Const access to a list of all midi outputs of the device.
- P midi_outputs [r] Const access to a list of all midi outputs of the device.
- M get_bank_count( (MaxDevice)arg1) -> int : Get the number of parameter banks. This is related to hardware control surfaces.
- M get_bank_name( (MaxDevice)arg1, (int)arg2) -> str : Get the name of a parameter bank given by index. This is related to hardware control surfaces.
- M get_bank_parameters( (MaxDevice)arg1, (int)arg2) -> list : Get the indices of parameters of the given bank index. Empty slots are marked as -1. Bank index -1 refers to the best-of bank. This function is related to hardware control surfaces.
- M get_value_item_icons( (MaxDevice)arg1, (DeviceParameter)arg2) -> list : Get a list of icon identifier strings for a list parameter's values.An empty string is given where no icon should be displayed.An empty list is given when no icons should be displayed.This
- observable: audio_inputs, audio_outputs, bank_parameters_changed, midi_inputs, midi_outputs

## module MeldDevice

### MeldDevice.MeldDevice (bases: Device)
- P mono_poly [rw] Returns the mode of Polyphony
- P poly_voices [rw] Return the Poly Voice count
- P selected_engine [rw] Return what Voice Engine is selected
- P unison_voices [rw] Return the Unison Voice count
- observable: mono_poly, poly_voices, selected_engine, unison_voices

## module MixerDevice

### MixerDevice.MixerDevice (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the mixer device.
- P crossfade_assign [rw] Player- and ReturnTracks only: Access to the Track's Crossfade Assign State.
- P crossfader [r] MainTrack only: Const access to the Crossfader.
- P cue_volume [r] MainTrack only: Const access to the Cue Volume Parameter.
- P left_split_stereo [r] Const access to the Track's Left Split Stereo Panning Device Parameter.
- P panning [r] Const access to the Tracks Panning Device Parameter.
- P panning_mode [rw] Access to the Track's Panning Mode.
- P right_split_stereo [r] Const access to the Track's Right Split Stereo Panning Device Parameter.
- P sends [r] Const access to the Tracks list of Send Amount Device Parameters.
- P song_tempo [r] MainTrack only: Const access to the Song's Tempo.
- P track_activator [r] Const access to the Tracks Activator Device Parameter.
- P volume [r] Const access to the Tracks Volume Device Parameter.
- observable: crossfade_assign, panning_mode, sends

### enum MixerDevice.MixerDevice.crossfade_assignments: A=0, B=2, NONE=1

### enum MixerDevice.MixerDevice.panning_modes: stereo=0, stereo_split=1

## module PluginDevice

### PluginDevice.PluginDevice (bases: Device)
- P is_editor_open [rw] Access to the opened state of the plugin's editor window.
- P presets [r] Get the list of presets the plugin offers.
- P selected_preset_index [rw] Access to the index of the currently selected preset.
- M get_parameter_names( (PluginDevice)arg1 [, (int)begin=0 [, (int)end=-1]]) -> StringVector : Get the range of plugin parameter names, bound by begin and end. If end is smaller than 0 it is interpreted as the parameter count.
- observable: is_editor_open, presets, selected_preset_index

## module RackDevice

### RackDevice.RackDevice (bases: Device)
- P can_show_chains [r] return True, if this Rack contains a rack instrument device that is capable of showing its chains in session view.
- P chain_selector [r] Const access to the chain selector parameter.
- P chains [r] Return const access to the list of chains in this device. Throws an exception if can_have_chains is false.
- P drum_pads [r] Return const access to the list of drum pads in this device. Throws an exception if can_have_drum_pads is false.
- P has_drum_pads [r] Returns true if the device is a drum rack which has drum pads. Throws an exception if can_have_drum_pads is false.
- P has_macro_mappings [r] Returns true if any of the rack's macros are mapped to a parameter.
- P is_showing_chains [rw] Returns True, if it is showing chains.
- P macros_mapped [r] A list of booleans, one for each macro parameter, which is True iffthat macro is mapped to something
- P return_chains [r] Return const access to the list of return chains in this device. Throws an exception if can_have_chains is false.
- P selected_variation_index [rw] Access to the index of the currently selected macro variation.Throws an exception if the index is out of range.
- P variation_count [r] Access to the number of macro variations currently stored.
- P visible_drum_pads [r] Return const access to the list of visible drum pads in this device. Throws an exception if can_have_drum_pads is false.
- P visible_macro_count [r] Access to the number of macros that are currently visible.
- M add_macro( (RackDevice)arg1) -> None : Increases the number of visible macro controls in the rack. Throws an exception if the maximum number of macro controls is reached.
- M copy_pad( (RackDevice)arg1, (int)arg2, (int)arg3) -> None : Copies all contents of a drum pad from a source pad into a destination pad. copy_pad(source_index, destination_index) where source_index and destination_index correspond to the note number/index of th
- M delete_selected_variation( (Device)arg1) -> None : Deletes the currently selected macro variation.Does nothing if there is no selected variation.
- M insert_chain( (RackDevice)arg1 [, (int)Index=-1]) -> LomObject : Inserts a new chain, either at the specified index or, if not index was specified, at the end of the chain sequence.
- M randomize_macros( (RackDevice)arg1) -> None : Randomizes the values for all macro controls not excluded from randomization.
- M recall_last_used_variation( (Device)arg1) -> None : Recalls the macro variation that was recalled most recently.Does nothing if no variation has been recalled yet.
- M recall_selected_variation( (Device)arg1) -> None : Recalls the currently selected macro variation.Does nothing if there are no variations.
- M remove_macro( (RackDevice)arg1) -> None : Decreases the number of visible macro controls in the rack. Throws an exception if the minimum number of macro controls is reached.
- M store_variation( (Device)arg1) -> None : Stores a new variation of the values of all currently mapped macros
- observable: chains, drum_pads, has_drum_pads, has_macro_mappings, is_showing_chains, macros_mapped, return_chains, variation_count, visible_drum_pads, visible_macro_count

### RackDevice.RackDevice.View (bases: View)
- P drum_pads_scroll_position [rw] Access to the index of the lowest visible row of pads. Throws an exception if can_have_drum_pads is false.
- P is_showing_chain_devices [rw] Return whether the devices in the currently selected chain are visible. Throws an exception if can_have_chains is false.
- P selected_chain [rw] Return access to the currently selected chain.
- P selected_drum_pad [rw] Return access to the currently selected drum pad. Throws an exception if can_have_drum_pads is false.
- observable: drum_pads_scroll_position, is_showing_chain_devices, selected_chain, selected_drum_pad

## module RoarDevice

### RoarDevice.RoarDevice (bases: Device)
- P env_listen [rw] Return the Envelope Input Listen toggle state
- P routing_mode_index [rw] Return the routing mode index
- P routing_mode_list [r] Return the routing mode list
- observable: env_listen, routing_mode_index

## module Sample

### Sample.Sample (bases: LomObject)
- P beats_granulation_resolution [rw] Access to the Granulation Resolution parameter in Beats Warp Mode.
- P beats_transient_envelope [rw] Access to the Transient Envelope parameter in Beats Warp Mode.
- P beats_transient_loop_mode [rw] Access to the Transient Loop Mode parameter in Beats Warp Mode.
- P canonical_parent [r] Access to the sample's canonical parent.
- P complex_pro_envelope [rw] Access to the Envelope parameter in Complex Pro Mode.
- P complex_pro_formants [rw] Access to the Formants parameter in Complex Pro Warp Mode.
- P end_marker [rw] Access to the position of the sample's end marker.
- P file_path [r] Get the path of the sample file.
- P gain [rw] Access to the sample gain.
- P length [r] Get the length of the sample file in sample frames.
- P sample_rate [r] Access to the audio sample rate of the sample.
- P slices [r] Access to the list of slice points in sample time in the sample.
- P slicing_beat_division [rw] Access to sample's slicing step size.
- P slicing_region_count [rw] Access to sample's slicing split count.
- P slicing_sensitivity [rw] Access to sample's slicing sensitivity whose sensitivity is in between 0.0 and 1.0. The higher the sensitivity, the more slices will be available.
- P slicing_style [rw] Access to sample's slicing style.
- P start_marker [rw] Access to the position of the sample's start marker.
- P texture_flux [rw] Access to the Flux parameter in Texture Warp Mode.
- P texture_grain_size [rw] Access to the Grain Size parameter in Texture Warp Mode.
- P tones_grain_size [rw] Access to the Grain Size parameter in Tones Warp Mode.
- P warp_markers [r] Get the warp markers for this sample.
- P warp_mode [rw] Access to the sample's warp mode.
- P warping [rw] Access to the sample's warping property.
- M beat_to_sample_time( (Sample)self, (float)beat_time) -> float : Converts the given beat time to sample time. Raises an error if the sample is not warped.
- M clear_slices( (Sample)self) -> None : Clears all slices created in Simpler's manual mode.
- M gain_display_string( (Sample)self) -> str : Get the gain's display value as a string.
- M insert_slice( (Sample)self, (int)slice_time) -> None : Add a slice point at the provided time if there is none.
- M move_slice( (Sample)self, (int)old_time, (int)new_time) -> int : Move the slice point at the provided time.
- M remove_slice( (Sample)self, (int)slice_time) -> None : Remove the slice point at the provided time if there is one.
- M reset_slices( (Sample)self) -> None : Resets all edited slices to their original positions.
- M sample_to_beat_time( (Sample)self, (float)sample_time) -> float : Converts the given sample time to beat time. Raises an error if the sample is not warped.
- observable: beats_granulation_resolution, beats_transient_envelope, beats_transient_loop_mode, complex_pro_envelope, complex_pro_formants, end_marker, file_path, gain, slices, slicing_beat_division, slicing_region_count, slicing_sensitivity, slicing_style, start_marker, texture_flux, texture_grain_size, tones_grain_size, warp_markers, warp_mode, warping

### enum Sample.SlicingBeatDivision: eighth=2, eighth_triplett=3, four_bars=10, half=6, half_triplett=7, one_bar=8, quarter=4, quarter_triplett=5, sixteenth=0, sixteenth_triplett=1, two_bars=9

### enum Sample.SlicingStyle: beat=1, manual=3, region=2, transient=0

### enum Sample.TransientLoopMode: alternate=2, forward=1, off=0

## module Scene

### Scene.Scene (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the scene.
- P clip_slots [r] return a list of clipslots (see class AClipSlot) that this scene covers.
- P color [rw] Get/set access to the color of the scene (RGB).
- P color_index [rw] Get/set access to the color index of the scene. Can be None for no color.
- P is_empty [r] Returns True if all clip slots of this scene are empty.
- P is_triggered [r] Const access to the scene's trigger state.
- P name [rw] Get/Set the name of the scene.
- P tempo [rw] Get/Set the tempo value of the scene. The song will use the scene's tempo as soon as the scene is fired. Returns -1 if the scene has no tempo property
- P tempo_enabled [rw] Get/Set the active state of the scene tempo. When disabled, the scene will use the song's tempo,and the tempo value returned will be -1Returns a bool 
- P time_signature_denominator [rw] Get/Set the scene's time signature denominator. The song will use the scene's time signature as soon as the scene is fired. Returns -1 if the scene ha
- P time_signature_enabled [rw] Get the active state of the scene time signature. When disabled, the scene will use the song's time signature,and the time signature values returned w
- P time_signature_numerator [rw] Get/Set the scene's time signature numerator. The song will use the scene's time signature as soon as the scene is fired. Returns -1 if the scene has 
- M fire( (Scene)arg1 [, (bool)force_legato=False [, (bool)can_select_scene_on_launch=True]]) -> None : Fire the scene directly. Will fire all clipslots that this scene owns and select the scene itself.
- M fire_as_selected( (Scene)arg1 [, (bool)force_legato=False]) -> None : Fire the selected scene. Will fire all clipslots that this scene owns and select the next scene if necessary.
- M set_fire_button_state( (Scene)arg1, (bool)arg2) -> None : Set the scene's fire button state directly. Supports all launch modes.
- observable: clip_slots, color, color_index, is_triggered, name, tempo, tempo_enabled, time_signature_denominator, time_signature_enabled, time_signature_numerator

## module ShifterDevice

### ShifterDevice.ShifterDevice (bases: Device)
- P pitch_bend_range [rw] Return the pitch bend range for MIDI pitch mode
- P pitch_mode_index [rw] Return the current pitch mode index
- P pitch_mode_list [r] Return the current pitch mode list
- observable: pitch_bend_range, pitch_mode_index

## module SimplerDevice
- F get_available_voice_numbers() -> IntVector : Get a vector of valid Simpler voice numbers.

### enum SimplerDevice.PlaybackMode: classic=0, one_shot=1, slicing=2

### SimplerDevice.SimplerDevice (bases: Device)
- P can_warp_as [r] Returns true if warp_as is available.
- P can_warp_double [r] Returns true if warp_double is available.
- P can_warp_half [r] Returns true if warp_half is available.
- P multi_sample_mode [r] Returns whether Simpler is in mulit-sample mode.
- P note_pitch_bend_range [rw] Access to the Note Pitch Bend Range in Simpler.
- P pad_slicing [rw] When set to true, slices can be added in slicing mode by playing notes .that are not assigned to slices, yet.
- P pitch_bend_range [rw] Access to the Pitch Bend Range in Simpler.
- P playback_mode [rw] Access to Simpler's playback mode.
- P playing_position [r] Constant access to the current playing position in the sample. The returned value is the normalized position between sample start and end.
- P playing_position_enabled [r] Returns whether Simpler is showing the playing position. The returned value is True while the sample is played back
- P retrigger [rw] Access to Simpler's retrigger mode.
- P sample [r] Get the loaded Sample.
- P slicing_playback_mode [rw] Access to Simpler's slicing playback mode.
- P voices [rw] Access to the number of voices in Simpler.
- M crop( (SimplerDevice)self) -> None : Crop the loaded sample to the active area between start- and end marker. Calling this method on an empty simpler raises an error.
- M guess_playback_length( (SimplerDevice)self) -> float : Return an estimated beat time for the playback length between start- and end-marker. Calling this method on an empty simpler raises an error.
- M replace_sample( (SimplerDevice)self, (object)file_path) -> None : Replaces the loaded samples with the one at the provided path.
- M reverse( (SimplerDevice)self) -> None : Reverse the loaded sample. Calling this method on an empty simpler raises an error.
- M warp_as( (SimplerDevice)self, (float)beat_time) -> None : Warp the playback region between start- and end-marker as the given length. Calling this method on an empty simpler raises an error.
- M warp_double( (SimplerDevice)self) -> None : Doubles the tempo for region between start- and end-marker.
- M warp_half( (SimplerDevice)self) -> None : Halves the tempo for region between start- and end-marker.
- observable: can_warp_as, can_warp_double, can_warp_half, multi_sample_mode, note_pitch_bend_range, pad_slicing, pitch_bend_range, playback_mode, playing_position, playing_position_enabled, retrigger, sample, slicing_playback_mode, voices

### SimplerDevice.SimplerDevice.View (bases: View)
- P sample_end [r] Access to the modulated samples end position in samples. Returns -1 in case there is no sample loaded.
- P sample_env_fade_in [r] Access to the envelope fade-in time in samples. Returned value is only in use when Simpler is in one-shot mode. Returns -1 in case there is no sample 
- P sample_env_fade_out [r] Access to the envelope fade-out time in samples. Returned value is only in use when Simpler is in one-shot mode. Returns -1 in case there is no sample
- P sample_loop_end [r] Access to the modulated samples loop end position in samples. Returns -1 in case there is no sample loaded.
- P sample_loop_fade [r] Access to the modulated samples loop fade position in samples. Returns -1 in case there is no sample loaded.
- P sample_loop_start [r] Access to the modulated samples loop start position in samples. Returns -1 in case there is no sample loaded.
- P sample_start [r] Access to the modulated samples start position in samples. Returns -1 in case there is no sample loaded.
- P selected_slice [rw] Access to the selected slice.
- observable: sample_end, sample_env_fade_in, sample_env_fade_out, sample_loop_end, sample_loop_fade, sample_loop_start, sample_start, selected_slice

### enum SimplerDevice.SlicingPlaybackMode: mono=0, poly=1, thru=2

## module Song
- F get_all_scales_ordered() -> tuple : Get an ordered tuple of tuples of all available scale names to intervals.

### Song.BeatTime
- P bars [rw] 
- P beats [rw] 
- P sub_division [rw] 
- P ticks [rw] 

### enum Song.CaptureDestination: arrangement=2, auto=0, session=1

### enum Song.CaptureMode: all=0, all_except_selected=1

### Song.CuePoint (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the cue point.
- P name [rw] Get/Set/Listen to the name of this CuePoint, as visible in the arranger.
- P time [r] Get/Listen to the CuePoint's time in beats.
- M jump( (CuePoint)arg1) -> None : When the Song is playing, set the playing-position quantized to this Cuepoint's time. When not playing, simply move the start playing position.
- observable: name, time

### enum Song.Quantization: q_2_bars=3, q_4_bars=2, q_8_bars=1, q_bar=4, q_eight=9, q_eight_triplet=10, q_half=5, q_half_triplet=6, q_no_q=0, q_quarter=7, q_quarter_triplet=8, q_sixtenth=11, q_sixtenth_triplet=12, q_thirtytwoth=13

### enum Song.RecordingQuantization: rec_q_eight=2, rec_q_eight_eight_triplet=4, rec_q_eight_triplet=3, rec_q_no_q=0, rec_q_quarter=1, rec_q_sixtenth=5, rec_q_sixtenth_sixtenth_triplet=7, rec_q_sixtenth_triplet=6, rec_q_thirtysecond=8

### enum Song.SessionRecordStatus: off=0, on=1, transition=2

### Song.SmptTime
- P frames [rw] 
- P hours [rw] 
- P minutes [rw] 
- P seconds [rw] 

### Song.Song (bases: LomObject)
- P appointed_device [rw] Read, write, and listen access to the appointed Device
- P arrangement_overdub [rw] Get/Set the global arrangement overdub state.
- P back_to_arranger [rw] Get/Set if triggering a Clip in the Session, disabled the playback of Clips in the Arranger.
- P can_capture_midi [r] Get whether there currently is material to be captured on any tracks.
- P can_jump_to_next_cue [r] Returns true when there is a cue marker right to the playing pos that we could jump to.
- P can_jump_to_prev_cue [r] Returns true when there is a cue marker left to the playing pos that we could jump to.
- P can_redo [r] Returns true if there is an undone action that we can redo.
- P can_undo [r] Returns true if there is an action that we can restore.
- P canonical_parent [r] Get the canonical parent of the song.
- P clip_trigger_quantization [rw] Get/Set access to the quantization settings that are used to fire Clips in the Session.
- P count_in_duration [r] Get the count in duration. Returns an index, mapped as follows: 0 - None, 1 - 1 Bar, 2 - 2 Bars, 3 - 4 Bars.
- P cue_points [r] Const access to a list of all cue points of the Live Song.
- P current_song_time [rw] Get/Set access to the songs current playing position in beats.
- P exclusive_arm [r] Get if Tracks should be armed exclusively by default.
- P exclusive_solo [r] Get if Tracks should be soloed exclusively by default.
- P file_path [r] Get the current Live Set's path on disk.
- P groove_amount [rw] Get/Set the global groove amount, that adjust all setup grooves in all clips.
- P groove_pool [r] Get the groove pool.
- P is_ableton_link_enabled [rw] Enable/disable Ableton Link.
- P is_ableton_link_start_stop_sync_enabled [rw] Enable/disable Ableton Link Start Stop Sync.
- P is_counting_in [r] Get whether currently counting in.
- P is_playing [rw] Returns true if the Song is currently playing.
- P last_event_time [r] Return the time of the last set event in the song. In contrary to song_length, this will not add some extra beats that are mostly needed for Display p
- P loop [rw] Get/Set the looping flag that en/disables the usage of the global loop markers in the song.
- P loop_length [rw] Get/Set the length of the global loop marker position in beats.
- P loop_start [rw] Get/Set the start of the global loop marker position in beats.
- P master_track [r] Access to the Main Track (always available)
- P metronome [rw] Get/Set if the metronom is audible.
- P midi_recording_quantization [rw] Get/Set access to the settings that are used to quantize MIDI recordings.
- P name [r] Get the current Live Set's name.
- P nudge_down [rw] Get/Set the status of the nudge down button.
- P nudge_up [rw] Get/Set the status of the nudge up button.
- P overdub [rw] Legacy hook for Live 8 overdub state. Now hooks to session record, but never starts playback.
- P punch_in [rw] Get/Set the flag that will enable recording as soon as the Song plays and hits the global loop start region.
- P punch_out [rw] Get/Set the flag that will disable recording as soon as the Song plays and hits the global loop end region.
- P re_enable_automation_enabled [r] Returns true if some automated parameter has been overriden
- P record_mode [rw] Get/Set the state of the global recording flag.
- P return_tracks [r] Const access to the list of available Return Tracks.
- P root_note [rw] Set and access the root (i.e. key) of the song. The root can be a number between 0 and 11, with 0 corresponding to C and 11 corresponding to B.
- P scale_intervals [r] Reports the current scale's intervals as a list of integers, starting with the root and representing the number of halfsteps (e.g. Major -> 0, 2, 4, 5
- P scale_mode [rw] Access to the Scale Mode setting in Live. When on, key tracks that belong to the currently selected scale are highlighted in Live's MIDI Note Editor, 
- P scale_name [rw] Set and access the currently selected scale by name. The default scale names that can be saved with a set and recalled are 'Major', 'Minor', 'Dorian',
- P scenes [r] Const access to a list of all Scenes in the Live Song.
- P select_on_launch [r] Get if Scenes and Clips should be selected when fired.
- P session_automation_record [rw] Returns true if automation recording is enabled.
- P session_record [rw] Get/Set the session record state.
- P session_record_status [r] Get the session slot-recording state.
- P signature_denominator [rw] Get/Set access to the global signature denominator of the Song.
- P signature_numerator [rw] Get/Set access to the global signature numerator of the Song.
- P song_length [r] Return the time of the last set event in the song, plus som extra beats that are usually added for better navigation in the arrangerview.
- P start_time [rw] Get/Set access to the songs current start time in beats. The set time may be overridden by the current loop/locator start time.
- P swing_amount [rw] Get/Set access to the amount of swing that is applied when adding or quantizing notes to MIDI clips
- P tempo [rw] Get/Set the global project tempo.
- P tempo_follower_enabled [rw] Get/Set whether the Tempo Follower is controlling the tempo. The Tempo Follower Toggle must be made visible in the preferences for this property to be
- P tracks [r] Const access to a list of all Player Tracks in the Live Song, excluding the return and Main Track (see also Song.send_tracks and Song.master_track). A
- P tuning_system [r] Access the currently active tuning system.
- P view [r] Representing the view aspects of a Live document: The Session and Arrangerview.
- P visible_tracks [r] Const access to a list of all visible Player Tracks in the Live Song, excluding the return and Main Track (see also Song.send_tracks and Song.master_t
- M begin_undo_step( (Song)arg1) -> None :
- M capture_and_insert_scene( (Song)arg1 [, (int)CaptureMode=Song.CaptureMode.all]) -> None : Capture currently playing clips and insert them as a new scene after the selected scene. Raises a runtime error if creating a new scene would exceed the limitations.
- M capture_midi( (Song)arg1 [, (int)Destination=Song.CaptureDestination.auto]) -> None : Capture recently played MIDI material from audible tracks. If no Destination is given or Destination is set to CaptureDestination.auto, the captured material is inserted into
- M continue_playing( (Song)arg1) -> None : Continue playing the song from the current position
- M create_audio_track( (Song)arg1 [, (object)Index=None]) -> Track : Create a new audio track at the optional given index and return it.If the index is -1, the new track is added at the end. It will create a default audio track if possible. If the index is invali
- M create_midi_track( (Song)arg1 [, (object)Index=None]) -> Track : Create a new midi track at the optional given index and return it.If the index is -1, the new track is added at the end.It will create a default midi track if possible. If the index is invalid or
- M create_return_track( (Song)arg1) -> Track : Create a new return track at the end and return it. If the new track would exceed the limitations, a limitation error is raised. If the maximum number of return tracks is exceeded, a RuntimeError is raised.
- M create_scene( (Song)arg1, (int)arg2) -> Scene : Create a new scene at the given index. If the index is -1, the new scene is added at the end. If the index is invalid or the new scene would exceed the limitations, a limitation error is raised.
- M delete_return_track( (Song)arg1, (int)arg2) -> None : Delete the return track with the given index. If no track with this index exists, an exception will be raised.
- M delete_scene( (Song)arg1, (int)arg2) -> None : Delete the scene with the given index. If no scene with this index exists, an exception will be raised.
- M delete_track( (Song)arg1, (int)arg2) -> None : Delete the track with the given index. If no track with this index exists, an exception will be raised.
- M duplicate_scene( (Song)arg1, (int)arg2) -> None : Duplicates a scene and selects the new one. Raises a limitation error if creating a new scene would exceed the limitations.
- M duplicate_track( (Song)arg1, (int)arg2) -> None : Duplicates a track and selects the new one. If the track is inside a folded group track, the group track is unfolded. Raises a limitation error if creating a new track would exceed the limitations.
- M end_undo_step( (Song)arg1) -> None :
- M find_device_position( (Song)arg1, (Device)device, (LomObject)target, (int)target_position) -> int : Returns the closest possible position to the given target, where the device can be inserted. If inserting is not possible at all (i.e. if the device type is wro
- M force_link_beat_time( (Song)arg1) -> None : Force the Link timeline to jump to Lives current beat time. Danger: This can cause beat time discontinuities in other connected apps.
- M get_beats_loop_length( (Song)arg1) -> BeatTime : Get const access to the songs loop length, using a BeatTime class with the current global set signature.
- M get_beats_loop_start( (Song)arg1) -> BeatTime : Get const access to the songs loop start, using a BeatTime class with the current global set signature.
- M get_current_beats_song_time( (Song)arg1) -> BeatTime : Get const access to the songs current playing position, using a BeatTime class with the current global set signature.
- M get_current_smpte_song_time( (Song)arg1, (int)arg2) -> SmptTime : Get const access to the songs current playing position, by specifying the SMPTE format in which you would like to receive the time.
- M get_data( (Song)arg1, (object)key, (object)default_value) -> object : Get data for the given key, that was previously stored using set_data.
- M is_cue_point_selected( (Song)arg1) -> bool : Return true if the global playing pos is currently on a cue point.
- M jump_by( (Song)arg1, (float)arg2) -> None : Set a new playing pos, relative to the current one.
- M jump_to_next_cue( (Song)arg1) -> None : Jump to the next cue (marker) if possible.
- M jump_to_prev_cue( (Song)arg1) -> None : Jump to the prior cue (marker) if possible.
- M move_device( (Song)arg1, (Device)device, (LomObject)target, (int)target_position) -> int : Move a device into the target at the given position, where 0 moves it before the first device and len(devices) moves it to the end of the device chain.If the device cann
- M play_selection( (Song)arg1) -> None : Start playing the current set selection, or do nothing if no selection is set.
- M re_enable_automation( (Song)arg1) -> None : Discards overrides of automated parameters.
- M redo( (Song)arg1) -> str : Redo the last action that was undone.
- M scrub_by( (Song)arg1, (float)arg2) -> None : Same as jump_by, but does not stop playback.
- M set_data( (Song)arg1, (object)key, (object)value) -> None : Store data for the given key in this object. The data is persistent and will be restored when loading the Live Set.
- M set_or_delete_cue( (Song)arg1) -> None : When a cue is selected, it gets deleted. If no cue is selected, a new cue is created at the current global songtime.
- M start_playing( (Song)arg1) -> None : Start playing from the startmarker
- M stop_all_clips( (Song)arg1 [, (bool)Quantized=True]) -> None : Stop all playing Clips (if any) but continue playing the Song.
- M stop_playing( (Song)arg1) -> None : Stop playing the Song.
- M sync_parameter_changes( (Song)arg1) -> None : Synchronize parameter changes with the UI thread. For performance reasons, parameter changes are not synchronized individually. This function is available in case synchronization of the parameter change into the do
- M tap_tempo( (Song)arg1) -> None : Trigger the tap tempo function.
- M trigger_session_record( (Song)self [, (float)record_length=1.7976931348623157e+308]) -> None : Triggers a new session recording.
- M undo( (Song)arg1) -> str : Undo the last action that was made.
- observable: appointed_device, arrangement_overdub, back_to_arranger, can_capture_midi, can_jump_to_next_cue, can_jump_to_prev_cue, clip_trigger_quantization, count_in_duration, cue_points, current_song_time, data, exclusive_arm, groove_amount, is_ableton_link_enabled, is_ableton_link_start_stop_sync_enabled, is_counting_in, is_playing, loop, loop_length, loop_start, metronome, midi_recording_quantization, nudge_down, nudge_up, overdub, punch_in, punch_out, re_enable_automation_enabled, record_mode, return_tracks, root_note, scale_information, scale_intervals, scale_mode, scale_name, scenes, session_automation_record, session_record, session_record_status, signature_denominator, signature_numerator, song_length, start_time, swing_amount, tempo, tempo_follower_enabled, tracks, tuning_system, visible_tracks

### Song.Song.View (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the song view.
- P detail_clip [rw] Get/Set the Clip that is currently visible in Lives Detailview.
- P draw_mode [rw] Get/Set if the Envelope/Note draw mode is enabled.
- P follow_song [rw] Get/Set if the Arrangerview should scroll to show the playmarker.
- P highlighted_clip_slot [rw] Get/Set the clip slot, defined via the selected track and scene in the Session.Will be None for Main- and Sendtracks.
- P mod_mapping_device [rw] The device that is waiting for a parameter (via mod_mapping_parameter) to modulate, or None if no device is waiting.
- P mod_mapping_parameter [r] Get the device parameter that's current selected to be mapped.
- P selected_chain [rw] Get the highlighted chain if available.
- P selected_parameter [r] Get the currently selected device parameter.
- P selected_scene [rw] Get/Set the current selected scene in Lives Sessionview.
- P selected_track [rw] Get/Set the current selected Track in Lives Session or Arrangerview.
- M select_device( (View)arg1, (Device)arg2 [, (bool)ShouldAppointDevice=True]) -> None : Select the given device.
- observable: detail_clip, draw_mode, follow_song, mod_mapping_device, mod_mapping_parameter, selected_chain, selected_parameter, selected_scene, selected_track

### enum Song.TimeFormat: ms_time=0, smpte_24=1, smpte_25=2, smpte_29=5, smpte_30=3, smpte_30_drop=4

## module SpectralResonatorDevice

### SpectralResonatorDevice.SpectralResonatorDevice (bases: Device)
- P frequency_dial_mode [rw] Return the current frequency dial mode index
- P frequency_dial_mode_list [r] Return the current frequency dial mode list
- P midi_gate [rw] Return the current midi gate index
- P midi_gate_list [r] Return the current midi gate list
- P mod_mode [rw] Return the current mod mode index
- P mod_mode_list [r] Return the current mod mode list
- P mono_poly [rw] Return the current mono poly mode index
- P mono_poly_list [r] Return the current mono poly mode list
- P pitch_bend_range [rw] Return the current pitch bend range
- P pitch_mode [rw] Return the current pitch mode index
- P pitch_mode_list [r] Return the current pitch mode list
- P polyphony [rw] Return the current polyphony
- observable: frequency_dial_mode, frequency_dial_mode_list, midi_gate, midi_gate_list, mod_mode, mod_mode_list, mono_poly, mono_poly_list, pitch_bend_range, pitch_mode, pitch_mode_list, polyphony

## module TakeLane

### TakeLane.TakeLane (bases: LomObject)
- P arrangement_clips [r] Read-only access to the arrangement clips in the take lane.
- P canonical_parent [r] Get the canonical parent of the take lane.
- P name [rw] Read/write access to the name of the TakeLane, as visible in the take lane header.
- M create_audio_clip( (TakeLane)arg1, (object)arg2, (float)arg3) -> Clip : Creates an audio clip referencing the file at the given path and inserts it into the arrangement at the specified time. Throws an error when called on a non-audio or a frozen track, when t
- M create_midi_clip( (TakeLane)arg1, (float)arg2, (float)arg3) -> Clip : Creates an empty MIDI clip and inserts it into the arrangement at the specified time. Throws an error when called on a non-MIDI track or a frozen track, when the specified time is outside th
- observable: arrangement_clips, name

## module Track

### Track.DeviceContainer (bases: LomObject)

### enum Track.DeviceInsertMode: count=3, default=0, selected_left=1, selected_right=2

### Track.RoutingChannel
- P display_name [r] Display name of routing channel.
- P layout [r] The routing channel's Layout, e.g., mono or stereo.

### enum Track.RoutingChannelLayout: midi=0, mono=1, stereo=2

### Track.RoutingChannelVector
- M append( (RoutingChannelVector)arg1, (object)arg2) -> None :
- M extend( (RoutingChannelVector)arg1, (object)arg2) -> None :

### Track.RoutingType
- P attached_object [r] Live object associated with the routing type.
- P category [r] Category of the routing type.
- P display_name [r] Display name of routing type.

### enum Track.RoutingTypeCategory: external=0, invalid=7, master=3, none=6, parent_group_track=5, resampling=2, rewire=1, track=4

### Track.RoutingTypeVector
- M append( (RoutingTypeVector)arg1, (object)arg2) -> None :
- M extend( (RoutingTypeVector)arg1, (object)arg2) -> None :

### Track.Track (bases: DeviceContainer)
- P arm [rw] Arm the track for recording. Not available for Main- and Send Tracks.
- P arrangement_clips [r] const access to the list of clips in arrangement viewThe list will be empty for the main, send and group tracks.
- P available_input_routing_channels [r] Return a list of source channels for input routing.
- P available_input_routing_types [r] Return a list of source types for input routing.
- P available_output_routing_channels [r] Return a list of destination channels for output routing.
- P available_output_routing_types [r] Return a list of destination types for output routing.
- P back_to_arranger [rw] Indicates if it's possible to go back to playing back the clips in the Arranger.Setting a value 0 will go back to the Arranger playback. Setting on gr
- P can_be_armed [r] return True, if this Track has a valid arm property. Not all tracks can be armed (for example return Tracks or the Main Tracks).
- P can_be_frozen [r] return True, if this Track can be frozen.
- P can_show_chains [r] return True, if this Track contains a rack instrument device that is capable of showing its chains in session view.
- P canonical_parent [r] Get the canonical parent of the track.
- P clip_slots [r] const access to the list of clipslots (see class AClipSlot) for this track. The list will be empty for the main and sendtracks.
- P color [rw] Get/set access to the color of the Track (RGB).
- P color_index [rw] Get/Set access to the color index of the track. Can be None for no color.
- P current_input_routing [rw] Get/Set the name of the current active input routing. When setting a new routing, the new routing must be one of the available ones.
- P current_input_sub_routing [rw] Get/Set the current active input sub routing. When setting a new routing, the new routing must be one of the available ones.
- P current_monitoring_state [rw] Get/Set the track's current monitoring state.
- P current_output_routing [rw] Get/Set the current active output routing. When setting a new routing, the new routing must be one of the available ones.
- P current_output_sub_routing [rw] Get/Set the current active output sub routing. When setting a new routing, the new routing must be one of the available ones.
- P devices [r] Return const access to all available Devices that are present in the Tracks Devicechain. This tuple will also include the 'mixer_device' that every Tr
- P fired_slot_index [r] const access to the index of the fired (and thus blinking) clipslot in this track. This index is -1 if no slot is fired and -2 if the track's stop but
- P fold_state [rw] Get/Set whether the track is folded or not. Only available if is_foldable is True.
- P group_track [r] return the group track if is_grouped.
- P has_audio_input [r] return True, if this Track can be feed with an Audio signal. This is true for all Audio Tracks.
- P has_audio_output [r] return True, if this Track sends out an Audio signal. This is true for all Audio Tracks, and MIDI tracks with an Instrument.
- P has_midi_input [r] return True, if this Track can be feed with an Audio signal. This is true for all MIDI Tracks.
- P has_midi_output [r] return True, if this Track sends out MIDI events. This is true for all MIDI Tracks with no Instruments.
- P implicit_arm [rw] Arm the track for recording. When The track is implicitly armed, it showsin a weaker color in the live GUI and is not saved in the set.
- P input_meter_left [r] Momentary value of left input channel meter, 0.0 to 1.0. For Audio Tracks only.
- P input_meter_level [r] Return the MIDI or Audio meter value of the Tracks input, depending on the type of the Track input. Meter values (MIDI or Audio) are always scaled fro
- P input_meter_right [r] Momentary value of right input channel meter, 0.0 to 1.0. For Audio Tracks only.
- P input_routing_channel [rw] Get and set the current source channel for input routing. Raises ValueError if the type isn't one of the current values in available_input_routing_cha
- P input_routing_type [rw] Get and set the current source type for input routing. Raises ValueError if the type isn't one of the current values in available_input_routing_types.
- P input_routings [r] Const access to the list of available input routings.
- P input_sub_routings [r] Return a list of all available input sub routings.
- P is_foldable [r] return True if the track can be (un)folded to hide/reveal contained tracks.
- P is_frozen [r] return True if this Track is currently frozen. No changes should be applied to the track's devices or clips while it is frozen.
- P is_grouped [r] return True if this Track is current part of a group track.
- P is_part_of_selection [r] return False if the track is not selected.
- P is_showing_chains [rw] Get/Set whether a track with a rack device is showing its chains in session view.
- P is_visible [r] return False if the track is hidden within a folded group track.
- P mixer_device [r] Return access to the special Device that every Track has: This Device contains the Volume, Pan, Sendamounts, and Crossfade assignment parameters.
- P mute [rw] Mute/unmute the track.
- P muted_via_solo [r] Returns true if the track is muted because another track is soloed.
- P name [rw] Read/write access to the name of the Track, as visible in the track header.
- P output_meter_left [r] Momentary value of left output channel meter, 0.0 to 1.0. For tracks with audio output only.
- P output_meter_level [r] Return the MIDI or Audio meter value of the Track output (behind the mixer_device), depending on the type of the Track input, this can be a MIDI or Au
- P output_meter_right [r] Momentary value of right output channel meter, 0.0 to 1.0. For tracks with audio output only.
- P output_routing_channel [rw] Get and set the current destination channel for output routing. Raises ValueError if the channel isn't one of the current values in available_output_r
- P output_routing_type [rw] Get and set the current destination type for output routing. Raises ValueError if the type isn't one of the current values in available_output_routing
- P output_routings [r] Const access to the list of all available output routings.
- P output_sub_routings [r] Return a list of all available output sub routings.
- P performance_impact [r] Reports the performance impact of this track.
- P playing_slot_index [r] const access to the index of the currently playing clip in the track. Will be -1 when no clip is playing.
- P solo [rw] Get/Set the solo status of the track. Note that this will not disable the solo state of any other track. If you want exclusive solo, you have to disab
- P take_lanes [r] returns the take lanes.
- P view [r] Representing the view aspects of a Track.
- M create_audio_clip( (Track)arg1, (object)arg2, (float)arg3) -> Clip : Creates an audio clip referencing the file at the given path and inserts it into the arrangement at the specified time. Throws an error when called on a non-audio or a frozen track, when the 
- M create_midi_clip( (Track)arg1, (float)arg2, (float)arg3) -> Clip : Creates an empty MIDI clip and inserts it into the arrangement at the specified time. Throws an error when called on a non-MIDI track or a frozen track, when the specified time is outside the [
- M create_take_lane( (Track)arg1) -> LomObject : Create a new TakeLane for this track.
- M delete_clip( (Track)arg1, (Clip)arg2) -> None : Delete the given clip. Raises a runtime error when the clip belongs to another track.
- M delete_device( (Track)arg1, (int)arg2) -> None : Delete a device identified by the index in the 'devices' list.
- M duplicate_clip_slot( (Track)arg1, (int)arg2) -> int : Duplicate a clip and put it into the next free slot and return the index of the destination slot. A new scene is created if no free slot is available. If creating the new scene would exceed the limitations,
- M duplicate_clip_to_arrangement( (Track)self, (Clip)clip, (float)destination_time) -> Clip : Duplicate the given clip into the arrangement of this track at the provided destination time and return it. When the type of the clip and the type of the track are incom
- M duplicate_device( (Track)arg1, (int)arg2) -> None : Duplicate a device at a given index in the 'devices' list.
- M get_data( (Track)arg1, (object)key, (object)default_value) -> object : Get data for the given key, that was previously stored using set_data.
- M insert_device( (Track)arg1, (str)DeviceName [, (int)DeviceIndex=-1]) -> LomObject : Add a device at a given index in the 'devices' list. At end if -1.
- M jump_in_running_session_clip( (Track)arg1, (float)arg2) -> None : Jump forward or backward in the currently running Sessionclip (if any) by the specified relative amount in beats. Does nothing if no Session Clip is currently running.
- M set_data( (Track)arg1, (object)key, (object)value) -> None : Store data for the given key in this object. The data is persistent and will be restored when loading the Live Set.
- M stop_all_clips( (Track)arg1 [, (bool)Quantized=True]) -> None : Stop running and triggered clip and slots on this track.
- observable: arm, arrangement_clips, available_input_routing_channels, available_input_routing_types, available_output_routing_channels, available_output_routing_types, back_to_arranger, clip_slots, color, color_index, current_input_routing, current_input_sub_routing, current_monitoring_state, current_output_routing, current_output_sub_routing, data, devices, fired_slot_index, has_audio_input, has_audio_output, has_midi_input, has_midi_output, implicit_arm, input_meter_left, input_meter_level, input_meter_right, input_routing_channel, input_routing_type, input_routings, input_sub_routings, is_frozen, is_showing_chains, mute, muted_via_solo, name, output_meter_left, output_meter_level, output_meter_right, output_routing_channel, output_routing_type, output_routings, output_sub_routings, performance_impact, playing_slot_index, solo, take_lanes

### Track.Track.View (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the track view.
- P device_insert_mode [rw] Get/Listen the device insertion mode of the track. By default, it will insert devices at the end, but it can be changed to make it relative to current
- P is_collapsed [rw] Get/Set/Listen if the track is shown collapsed in the arranger view.
- P selected_device [r] Get/Set/Listen the insertion mode of the device. While in insertion mode, loading new devices from the browser will place devices at the selected posi
- M select_instrument( (View)arg1) -> bool : Selects the track's instrument if it has one.
- observable: device_insert_mode, is_collapsed, selected_device

### enum Track.Track.monitoring_states: AUTO=1, IN=0, OFF=2

## module TuningSystem

### TuningSystem.PitchClassAndOctave
- P index_in_octave [r] A PitchClassAndOctave's index within the pseudo octave.
- P octave [r] A PitchClassAndOctave's octave.

### TuningSystem.ReferencePitch
- P frequency [r] A ReferencePitch's frequency in Hz.
- P index_in_octave [r] A ReferencePitch's index within the pseudo octave.
- P octave [r] A ReferencePitch's octave.

### TuningSystem.TuningSystem (bases: LomObject)
- P canonical_parent [r] Get the canonical parent of the TuningSystem.
- P highest_note [rw] Get/Set the highest note of the current tuning system, where the first entry is the index within the pseudo octave and the second entry is the octave.
- P lowest_note [rw] Get/Set the lowest note of the current tuning system, where the first entry is the index within the pseudo octave and the second entry is the octave.
- P name [rw] Get/Set the name of the currently active tuning system.
- P note_tunings [rw] Get/Set the currently active tuning system's note tunings, specified in Cents, where 100 Cents is one semi-tone in equal temperament.
- P number_of_notes_in_pseudo_octave [r] Get the number of notes in the pseudo octave.
- P pseudo_octave_in_cents [r] Get the pseudo octave in cents for the currently active tuning system.
- P reference_pitch [rw] Get/Set the reference pitch the currently active tuning system.
- observable: highest_note, lowest_note, name, note_tunings, reference_pitch

## module WavetableDevice

### enum WavetableDevice.EffectMode: frequency_modulation=1, none=0, sync_and_pulse_width=2, warp_and_fold=3

### enum WavetableDevice.FilterRouting: parallel=1, serial=0, split=2

### enum WavetableDevice.ModulationSource: amp_envelope=0, envelope_2=1, envelope_3=2, lfo_1=3, lfo_2=4, midi_channel_pressure=8, midi_mod_wheel=9, midi_note=6, midi_pitch_bend=7, midi_random=10, midi_velocity=5

### enum WavetableDevice.UnisonMode: classic=1, fast_shimmer=3, none=0, phase_sync=4, position_spread=5, random_note=6, slow_shimmer=2

### enum WavetableDevice.VoiceCount: eight=6, five=3, four=2, seven=5, six=4, sixteen=7, three=1, two=0

### enum WavetableDevice.Voicing: mono=0, poly=1

### WavetableDevice.WavetableDevice (bases: Device)
- P filter_routing [rw] Return the current filter routing.
- P mono_poly [rw] Return the current voicing mode.
- P oscillator_1_effect_mode [rw] Return the current effect mode of the oscillator 1.
- P oscillator_1_wavetable_category [rw] Return the current wavetable category of the oscillator 1.
- P oscillator_1_wavetable_index [rw] Return the current wavetable index of the oscillator 1.
- P oscillator_1_wavetables [r] Get a vector of oscillator 1's wavetable names.
- P oscillator_2_effect_mode [rw] Return the current effect mode of the oscillator 2.
- P oscillator_2_wavetable_category [rw] Return the current wavetable category of the oscillator 2.
- P oscillator_2_wavetable_index [rw] Return the current wavetable index of the oscillator 2.
- P oscillator_2_wavetables [r] Get a vector of oscillator 2's wavetable names.
- P oscillator_wavetable_categories [r] Get a vector of the available wavetable categories.
- P poly_voices [rw] Return the current number of polyphonic voices. Uses the VoiceCount enumeration.
- P unison_mode [rw] Return the current unison mode.
- P unison_voice_count [rw] Return the current number of unison voices.
- P visible_modulation_target_names [r] Get the names of all the visible modulation targets.
- M add_parameter_to_modulation_matrix( (WavetableDevice)self, (DeviceParameter)parameter) -> int : Add a non-pitch parameter to the modulation matrix.
- M get_modulation_target_parameter_name( (WavetableDevice)self, (int)target_index) -> str : Get the parameter name of the modulation target at the given index.
- M get_modulation_value( (WavetableDevice)self, (int)target_index, (int)source) -> float : Get the value of a modulation amount for the given target-source connection.
- M is_parameter_modulatable( (WavetableDevice)self, (DeviceParameter)parameter) -> bool : Indicate whether the parameter is modulatable. Note that pitch parameters only exist in python and must be handled there.
- M set_modulation_value( (WavetableDevice)self, (int)target_index, (int)source, (float)value) -> None : Set the value of a modulation amount for the given target-source connection.
- observable: filter_routing, modulation_matrix_changed, mono_poly, oscillator_1_effect_mode, oscillator_1_wavetable_category, oscillator_1_wavetable_index, oscillator_1_wavetables, oscillator_2_effect_mode, oscillator_2_wavetable_category, oscillator_2_wavetable_index, oscillator_2_wavetables, poly_voices, unison_mode, unison_voice_count, visible_modulation_target_names