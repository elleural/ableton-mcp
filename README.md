# AbletonMCP - Ableton Live Model Context Protocol Integration
[![smithery badge](https://smithery.ai/badge/@ahujasid/ableton-mcp)](https://smithery.ai/server/@ahujasid/ableton-mcp)

AbletonMCP connects Ableton Live to Claude AI through the Model Context Protocol (MCP), allowing Claude to directly interact with and control Ableton Live. This integration enables prompt-assisted music production, track creation, and Live session manipulation.

### Join the Community

Give feedback, get inspired, and build on top of the MCP: [Discord](https://discord.gg/3ZrMyGKnaU). Made by [Siddharth](https://x.com/sidahuj)

## Features

- **Two-way communication**: Connect Claude AI to Ableton Live through a socket-based server
- **Track manipulation**: Create, modify, and manipulate MIDI and audio tracks
- **Instrument and effect selection**: Claude can access and load the right instruments, effects and sounds from Ableton's library
- **Clip creation**: Create and edit MIDI clips with notes
- **Session control**: Start and stop playback, fire clips, and control transport
- **Scene Management**: Create, list, fire, and rename scenes
- **Advanced Device Control**: Get and set device parameters by name, delete devices, and find devices by name.
- **Automation**: Write automation curves for device parameters.
- **Max for Live Integration**: Modify `.amxd` files by changing default parameter values.
- **Arrangement View Control**: List and create locators, and set the song position.
- **Mixer Control**: List return tracks and set send levels.
- **User Feedback**: Display messages in the Ableton Live status bar.

## Project History

This project was created by Siddharth Ahuja and has been improved with the help of the community. The latest updates include a host of new features that significantly expand the capabilities of AbletonMCP, including:

- Enhanced browser navigation with recursive exploration.
- Scene management.
- Advanced device control.
- Automation writing.
- Max for Live integration.
- Arrangement View control.
- Mixer control.
- Audio track creation.
- User feedback messages.

## Installation

### Prerequisites

- Ableton Live 10 or newer
- Python 3.8 or newer
- [uv package manager](https://astral.sh/uv)

If you're on Mac, please install uv as:
```
brew install uv
```

Otherwise, install from [uv's official website][https://docs.astral.sh/uv/getting-started/installation/]

⚠️ Do not proceed before installing UV

### Claude for Desktop Integration

[Follow along with the setup instructions video](https://youtu.be/iJWJqyVuPS8)

1. Go to Claude > Settings > Developer > Edit Config > claude_desktop_config.json to include the following:

```json
{
    "mcpServers": {
        "AbletonMCP": {
            "command": "uvx",
            "args": [
                "ableton-mcp"
            ]
        }
    }
}
```

### Cursor Integration

Run ableton-mcp without installing it permanently through uvx. Go to Cursor Settings > MCP and paste this as a command:

```
uvx ableton-mcp
```

⚠️ Only run one instance of the MCP server (either on Cursor or Claude Desktop), not both

### Installing the Ableton Remote Script

[Follow along with the setup instructions video](https://youtu.be/iJWJqyVuPS8)

1. Download the `AbletonMCP_Remote_Script/__init__.py` file from this repo

2. Copy the folder to Ableton's MIDI Remote Scripts directory. Different OS and versions have different locations. **One of these should work, you might have to look**:

   **For macOS:**
   - Method 1: Go to Applications > Right-click on Ableton Live app → Show Package Contents → Navigate to:
     `Contents/App-Resources/MIDI Remote Scripts/`
   - Method 2: If it's not there in the first method, use the direct path (replace XX with your version number):
     `/Users/[Username]/Library/Preferences/Ableton/Live XX/User Remote Scripts`
   
   **For Windows:**
   - Method 1:
     C:\Users\[Username]\AppData\Roaming\Ableton\Live x.x.x\Preferences\User Remote Scripts 
   - Method 2:
     `C:\ProgramData\Ableton\Live XX\Resources\MIDI Remote Scripts\`
   - Method 3:
     `C:\Program Files\Ableton\Live XX\Resources\MIDI Remote Scripts\`
   *Note: Replace XX with your Ableton version number (e.g., 10, 11, 12)*

4. Create a folder called 'AbletonMCP' in the Remote Scripts directory and paste the downloaded '\_\_init\_\_.py' file

3. Launch Ableton Live

4. Go to Settings/Preferences → Link, Tempo & MIDI

5. In the Control Surface dropdown, select "AbletonMCP"

6. Set Input and Output to "None"

## Usage

### Starting the Connection

1. Ensure the Ableton Remote Script is loaded in Ableton Live
2. Make sure the MCP server is configured in Claude Desktop or Cursor
3. The connection should be established automatically when you interact with Claude

### Using with Claude

Once the config file has been set on Claude, and the remote script is running in Ableton, you will see a hammer icon with tools for the Ableton MCP.

## Command List

### Session Control
- `get_session_info()`: Get detailed information about the current Ableton session.
  - **Example**: "Get the session info."
- `set_tempo(tempo: float)`: Set the tempo of the Ableton session.
  - **Example**: "Set the tempo to 120 BPM."
- `start_playback()`: Start playing the Ableton session.
  - **Example**: "Start playback."
- `stop_playback()`: Stop playing the Ableton session.
  - **Example**: "Stop playback."

### Track Control
- `get_track_info(track_index: int)`: Get detailed information about a specific track.
  - **Example**: "Get info for track 1."
- `create_midi_track(index: int = -1)`: Create a new MIDI track.
  - **Example**: "Create a new MIDI track."
- `create_audio_track(index: int = -1)`: Create a new audio track.
  - **Example**: "Create a new audio track."
- `set_track_name(track_index: int, name: str)`: Set the name of a track.
  - **Example**: "Rename track 1 to 'Drums'."

### Clip Control
- `create_clip(track_index: int, clip_index: int, length: float = 4.0)`: Create a new MIDI clip.
  - **Example**: "Create a 4-bar clip in track 1, slot 1."
- `add_notes_to_clip(track_index: int, clip_index: int, notes: List[Dict[str, Union[int, float, bool]]])`: Add MIDI notes to a clip.
  - **Example**: "Add a C4 note to the clip in track 1, slot 1."
- `set_clip_name(track_index: int, clip_index: int, name: str)`: Set the name of a clip.
  - **Example**: "Rename the clip in track 1, slot 1 to 'Intro'."
- `get_clip_info(track_index: int, clip_index: int)`: Get detailed information about a specific clip.
  - **Example**: "Get info for the clip in track 1, slot 1."
- `fire_clip(track_index: int, clip_index: int)`: Start playing a clip.
  - **Example**: "Play the clip in track 1, slot 1."
- `stop_clip(track_index: int, clip_index: int)`: Stop playing a clip.
  - **Example**: "Stop the clip in track 1, slot 1."

### Device Control
- `load_instrument_or_effect(track_index: int, uri: str)`: Load an instrument, effect, or audio file from the browser onto a track.
  - **Example**: "Load the 'Operator' synth on track 1."
- `get_device_parameters(track_index: int, device_index: int)`: Get a list of parameters for a specific device on a track.
  - **Example**: "Get the parameters for the first device on track 1."
- `get_device_details(track_index: int, device_index: int)`: Get detailed information about a specific device on a track.
  - **Example**: "Get details for the first device on track 1."
- `find_device_by_name(track_index: int, device_name: str)`: Find the index of a device on a track by its name.
  - **Example**: "Find the 'Operator' synth on track 1."
- `set_device_parameter(track_index: int, device_index: int, value: float, parameter_index: int = None, parameter_name: str = None)`: Set the value of a parameter for a specific device.
  - **Example**: "Set the 'Filter Freq' on the first device of track 1 to 800."
- `delete_device(track_index: int, device_index: int)`: Delete a device from a track.
  - **Example**: "Delete the first device from track 1."
- `write_automation(track_index: int, clip_index: int, device_index: int, points: List[Dict[str, float]], parameter_index: int = None, parameter_name: str = None)`: Write automation points for a device parameter within a clip.
  - **Example**: "Create a filter sweep automation on the first device of track 1."

### Scene Control
- `list_scenes()`: Get a list of all scenes in the Ableton session.
  - **Example**: "List all scenes."
- `fire_scene(scene_index: int)`: Fire a scene in the Ableton session.
  - **Example**: "Fire scene 1."
- `create_scene(scene_index: int = -1)`: Create a new scene in the Ableton session.
  - **Example**: "Create a new scene."
- `rename_scene(scene_index: int, name: str)`: Rename a scene in the Ableton session.
  - **Example**: "Rename scene 1 to 'Intro'."

### Browser Control
- `get_browser_tree(category_type: str = "all", max_depth: int = 2)`: Get a hierarchical tree of browser categories from Ableton.
  - **Example**: "Get the browser tree for instruments, up to 3 levels deep."
- `get_browser_items_at_path(path: str)`: Get browser items at a specific path in Ableton's browser.
  - **Example**: "Get the items in the 'Drums' category."
- `load_drum_kit(track_index: int, rack_uri: str, kit_path: str)`: Load a drum rack and then load a specific drum kit into it.
  - **Example**: "Load the '808 Core Kit' on track 1."

### Max for Live Control
- `modify_m4l_device_default(input_filepath: str, output_filepath: str, parameter_name: str, new_default_value: float)`: Creates a new Max for Live device file with a modified default value for a parameter.
  - **Example**: "Take the device 'MyReverb.amxd' and create a new version at 'MyReverb_Long.amxd' where the 'Decay' parameter defaults to 5.0"

### Arrangement View Control
- `list_locators()`: Get a list of all locators (cue points) in the Ableton session.
  - **Example**: "List all locators."
- `create_locator(time: float)`: Create a new locator (cue point) at a specific time in the arrangement.
  - **Example**: "Create a locator at beat 32."
- `set_song_position(time: float)`: Set the song's current playback time in the arrangement.
  - **Example**: "Set the song position to beat 16."

### MCP Consumer Reference

This section documents the MCP tools exposed by `MCP_Server/server.py` and the payloads you should send when invoking them from an MCP client.

#### duplicate_session_clip_to_arrangement

Duplicates a Session clip (from `Track.clip_slots[clip_index].clip`) into Arrangement at a specific beat position. After duplication, optionally configures length and looping for the new Arrangement clip.

- **Tool name**: `duplicate_session_clip_to_arrangement`
- **Parameters**:
  - `track_index` (int, required): Index of the track that contains the Session clip.
  - `clip_index` (int, required): Clip slot index in Session view to duplicate from.
  - `start_beats` (float, required): Arrangement beat where the clip should be placed.
  - `length_beats` (float, required): Desired length in beats for the resulting Arrangement clip.
  - `loop` (bool, optional): If `true`, enables looping and sets `loop_start = start_beats` and `loop_end = start_beats + length_beats`. If `false` or omitted, sets a non-looping `end_time = start_beats + length_beats`.

- **Example payloads**:

```json
{ "track_index": 5, "clip_index": 1, "start_beats": 32, "length_beats": 64, "loop": true }
```

```json
{ "track_index": 4, "clip_index": 1, "start_beats": 32, "length_beats": 4 }
```

- **Response (formatted)**:

```json
{
  "track_index": 5,
  "start_time": 32.0,
  "end_time": 96.0,
  "looping": true
}
```

- **Notes and limitations**:
  - The duplication is performed via `Track.duplicate_clip_to_arrangement` on the specified track. Some Live versions/devices may return a new clip object; others may require discovering the new clip by `start_time`.
  - On some Live versions, certain Arrangement `Clip` properties may be read-only (e.g., `loop_start`, `loop_end`, `end_time`). If setting these fails, the script falls back to setting only supported properties (e.g., disabling looping and setting `end_time`).
  - Make sure `length_beats` is provided; the tool requires it to compute loop/end boundaries.

If you encounter "property of 'Clip' object has no setter", try calling again without `loop` or use a smaller `length_beats`. If issues persist, record the clip into Arrangement as a temporary workaround.

### All MCP tools: schemas and example payloads

Below are all available MCP tools exposed by `MCP_Server/server.py`, with parameter schemas and minimal example payloads. Unless noted, send a JSON object with the listed fields.

#### Session
- `get_session_info`
```json
{}
```
- `set_tempo`
```json
{ "tempo": 120 }
```
- `start_playback`
```json
{}
```
- `stop_playback`
```json
{}
```

#### Tracks and clips
- `get_track_info`
```json
{ "track_index": 0 }
```
- `create_midi_track`
```json
{ "index": -1 }
```
- `create_audio_track`
```json
{ "index": -1 }
```
- `set_track_name`
```json
{ "track_index": 0, "name": "Drums" }
```
- `create_clip`
```json
{ "track_index": 0, "clip_index": 1, "length": 4 }
```
- `add_notes_to_clip`
```json
{ "track_index": 0, "clip_index": 1, "notes": [ { "pitch": 60, "start_time": 0, "duration": 1, "velocity": 100, "mute": false } ] }
```
- `set_clip_name`
```json
{ "track_index": 0, "clip_index": 1, "name": "Intro" }
```
- `get_clip_info`
```json
{ "track_index": 0, "clip_index": 1 }
```
- `fire_clip`
```json
{ "track_index": 0, "clip_index": 1 }
```
- `stop_clip`
```json
{ "track_index": 0, "clip_index": 1 }
```

#### Devices
- `load_instrument_or_effect`
```json
{ "track_index": 0, "uri": "Instruments/Operator" }
```
- `get_device_parameters`
```json
{ "track_index": 0, "device_index": 0 }
```
- `get_device_details`
```json
{ "track_index": 0, "device_index": 0 }
```
- `find_device_by_name`
```json
{ "track_index": 0, "device_name": "Operator" }
```
- `set_device_parameter` (provide either `parameter_index` or `parameter_name`)
```json
{ "track_index": 0, "device_index": 0, "value": 0.5, "parameter_name": "Filter Freq" }
```
- `delete_device`
```json
{ "track_index": 0, "device_index": 0 }
```
- `write_automation` (points = list of {time,value})
```json
{ "track_index": 0, "clip_index": 1, "device_index": 0, "points": [ { "time": 0.0, "value": 0.0 }, { "time": 4.0, "value": 1.0 } ], "parameter_name": "Filter Freq" }
```

#### Scenes
- `list_scenes`
```json
{}
```
- `fire_scene`
```json
{ "scene_index": 0 }
```
- `create_scene`
```json
{ "scene_index": -1 }
```
- `rename_scene`
```json
{ "scene_index": 0, "name": "Intro" }
```

#### Browser
- `get_browser_tree`
```json
{ "category_type": "all", "max_depth": 2 }
```
- `get_browser_items_at_path`
```json
{ "path": "instruments/analog" }
```
- `load_drum_kit`
```json
{ "track_index": 0, "rack_uri": "Drums/Drum Rack", "kit_path": "drums/808 core kit" }
```

#### Arrangement and transport
- `list_locators`
```json
{}
```
- `create_locator`
```json
{ "time": 32 }
```
- `set_song_position`
```json
{ "time": 16 }
```
- `set_current_song_time_beats`
```json
{ "beats": 16 }
```
- `get_current_song_time_beats`
```json
{}
```
- `set_record_mode`
```json
{ "on": true }
```
- `continue_playing`
```json
{}
```
- `jump_by`
```json
{ "beats": 4 }
```
- `set_back_to_arranger`
```json
{ "on": true }
```
- `set_start_time`
```json
{ "beats": 0 }
```
- `set_metronome`
```json
{ "on": true }
```
- `set_clip_trigger_quantization`
```json
{ "quant": 4 }
```
- `set_loop`
```json
{ "on": true }
```
- `set_loop_region`
```json
{ "start": 32, "length": 16 }
```
- `play_selection`
```json
{}
```
- `stop_all_clips`
```json
{ "quantized": 1 }
```
- `jump_to_next_cue`
```json
{}
```
- `jump_to_prev_cue`
```json
{}
```
- `jump_to_cue`
```json
{ "index": 0 }
```
- `toggle_cue_at_current`
```json
{}
```
- `re_enable_automation`
```json
{}
```
- `set_arrangement_overdub`
```json
{ "on": true }
```
- `set_session_automation_record`
```json
{ "on": true }
```
- `trigger_session_record` (optional `record_length`)
```json
{ "record_length": 8 }
```
- `rename_cue_point`
```json
{ "cue_index": 0, "name": "Verse" }
```
- `clear_arrangement` (optional `track_indices`)
```json
{ "track_indices": [0,1] }
```
- `duplicate_session_clip_to_arrangement` (see section above)

#### Misc
- `list_return_tracks`
```json
{}
```
- `set_send_level`
```json
{ "track_index": 0, "send_index": 0, "level": 0.5 }
```
- `modify_m4l_device_default`
```json
{ "input_filepath": "/path/in.amxd", "output_filepath": "/path/out.amxd", "parameter_name": "Decay", "new_default_value": 5.0 }
```
- `show_message`
```json
{ "message": "Hello from MCP" }
```

### Mixer Control
- `list_return_tracks()`: Get a list of all return tracks in the Ableton session.
  - **Example**: "List all return tracks."
- `set_send_level(track_index: int, send_index: int, level: float)`: Set the send level for a track.
  - **Example**: "Set the first send on track 1 to 0.5."

### User Feedback
- `show_message(message: str)`: Display a message in Ableton's status bar.
  - **Example**: "Show the message 'Hello from the AI!' in Ableton."

## Troubleshooting

- **Connection issues**: Make sure the Ableton Remote Script is loaded, and the MCP server is configured on Claude
- **Timeout errors**: Try simplifying your requests or breaking them into smaller steps
- **Have you tried turning it off and on again?**: If you're still having connection errors, try restarting both Claude and Ableton Live

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This is a third-party integration and not made by Ableton.
