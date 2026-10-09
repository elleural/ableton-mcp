# AbletonMCP

AbletonMCP lets an AI agent (Claude, or any MCP client) operate **Ableton Live 12** over the
[Model Context Protocol](https://modelcontextprotocol.io). It is built for an *agentic composer*. The
agent can go from an empty set to a finished song and render release-ready files without a human
touching Live:

1. Set tempo, key and scale.
2. Build instruments and effects.
3. Write MIDI parts and drum patterns.
4. Arrange sections.
5. Mix and automate.
6. Master and bounce the master and stems.
7. Measure loudness and spectrum.
8. Encode WAV, FLAC, MP3 and AAC with tags and artwork.

Version 2 is a ground-up redesign. The goals and design are in [docs/PRD.md](docs/PRD.md), and the
full tool reference is [docs/TOOLS.md](docs/TOOLS.md).

## How it works

```
AI agent ──MCP (stdio)──► AbletonMCP server ──TCP 127.0.0.1:9877──► AbletonMCP Remote Script ──► Ableton Live
                          (Python, this repo)                     (runs inside Live as a control surface)
```

- The **Remote Script** runs inside Live. It executes commands on Live's main thread, with one undo step per change.
- The **MCP server** exposes 78 workflow-shaped tools. It also does what Live's API cannot, using ffmpeg: rendering by resampling, loudness and spectral analysis, and encoding and tagging releases.

## Requirements

- Ableton Live 12.4 or later (verified on 12.4.6, Suite). macOS is the primary platform; Windows is best-effort.
- [uv](https://docs.astral.sh/uv/) and Python 3.10 or later.
- ffmpeg, for `analyze_audio` and `create_release`. On macOS: `brew install ffmpeg`.
- Optional: macOS Automation and Accessibility permission for the app running the MCP server. This enables `save_set`, `new_set` and `export_audio`, which drive Live's menus because Live has no API for them.

## Install

1. **Get the code**

   ```bash
   git clone https://github.com/elleural/ableton-mcp.git
   ```

   Then run `uv sync` from the cloned folder.

2. **Install the Remote Script into Live's User Library.** This links it to your checkout, so updates
   need no copying.

   ```bash
   uv run ableton-mcp install
   ```

3. **Restart Live.** It only discovers Remote Scripts at launch. Then open **Settings → Link, Tempo &
   MIDI** and set a **Control Surface** slot to **AbletonMCP**, with Input and Output set to **None**.

4. **Register the MCP server** with your client.

   - Claude Code:

     ```bash
     claude mcp add --scope user ableton -- uv run --directory /path/to/ableton-mcp ableton-mcp
     ```

   - Claude Desktop: in `claude_desktop_config.json`, add:

     ```json
     {"mcpServers": {"ableton": {"command": "uv", "args": ["run", "--directory", "/path/to/ableton-mcp", "ableton-mcp"]}}}
     ```

   Do not use `uvx ableton-mcp`. That installs an unrelated older package from PyPI.

5. **Check everything.**

   ```bash
   uv run ableton-mcp doctor
   ```

## Using it

Ask for music in plain language. For example: *"Make a 124 BPM house track in A minor: four-on-the-floor
drums, a rolling bassline, warm chords; arrange intro/verse/drop; mix it; bounce it with stems and give
me a -14 LUFS release."* The server's instructions teach the agent the workflow and conventions. Its
usual flow:

```
get_status → set_song → create_track / add_device / load_from_browser → create_clip (notes, pattern) →
write_automation → fire_scene → arrange_from_scenes → set_mixer / set_sidechain → bounce →
get_bounce_status → analyze_audio → create_release → save_set
```

Conventions every tool shares:

- **Tracks:** an index, a name, `"return:A"`, or `"master"`.
- **Devices:** an index, a name, or a rack path like `"Drum Rack/Kick/Simpler"`.
- **Time:** beats, or `"bar.beat.sixteenth"` such as `"17.1.1"`.
- **Pitch:** a MIDI number or a note name, where `C3` is 60.
- **Mixing units:** volume in dB, pan from −1 to +1.

Every change is one undo step (`undo`), and `lom_get` / `lom_set` / `lom_call` reach anything in Live's
object model that the curated tools do not.

### Rendering and release

Live's API has no export function, so `bounce` renders **in real time inside Live**:

1. It records the master, through Live's "Resampling" input, and any stems you ask for onto temporary audio tracks.
2. It restores your transport and arm settings.
3. It writes sample-accurate WAVs to `~/Music/AbletonMCP/Bounces/<name>/`.

`create_release` then:

1. Normalises to a loudness target, by default −14 LUFS with a −1 dBTP ceiling.
2. Encodes WAV 24-bit and 16-bit (dithered), FLAC, MP3 320 and AAC.
3. Writes tags and artwork.
4. Saves the files with a `release.json` manifest to `~/Music/AbletonMCP/Releases/<artist> - <title>/`.

### Listening loop

The agent cannot hear, so the listening loop ([docs/listening-loop-prd.md](docs/listening-loop-prd.md)) lets it
check its own work against a spec of the brief (key, progressions, loop lengths, layer tiers, loudness
targets; the bundled one is NOVA's, `ears/specs/nova.spec.json`):

| Tool | Does |
|---|---|
| `analyze_notes` | Checks the stem clips' notes: key, chord tones, semitone clashes between stems, loop lengths, grid, lead rests. Under a second, no audio |
| `capture` | Records every stem's track output, the returns and the main mix in real time inside Live (Session recording on temporary `cap:` tracks), cuts the folded second cycle into a *take* and analyses it. Leaves the set as found |
| `analyze_audio(take=...)` | Tier sums T1–T5 as the game layers them: −14 LUFS / −1 dBTP, key, mono sub, stems + returns cancel the mix, tempo consistency, tier ladder, masking, the game's analyser bands, phone survival; `strict` adds the delivery-file checks |
| `compare` | Deltas between two takes (or against the spec), loudness-matched, each improved, regressed or within the measured noise; `blind` gives an X/Y packet for a fresh judge |
| `takes` | The ledger of takes, `keep` the best one, `restore` an earlier take's notes and parameters |
| `ref`, `meter` | References: a Spotify track played in the desktop app and measured through the interface's loopback (a 4th Gen Scarlett's inputs 3-4, or a virtual device), once, as numbers only; or a file you own. `compare(take, "refs")` places a take's balance, dynamics and width against them; `meter` measures whatever plays now |

The analysis is the standalone `ears` package; its CLI runs without Live and doubles as the soundtrack's
acceptance script:

```bash
uv run ears acceptance path/to/public/music/masters
```

Takes live in `<set folder>/ears/` for a saved set, else `~/Music/AbletonMCP/Ears/<set name>/` (`EARS_HOME`
overrides). Verified capture behaviour and calibration are in [docs/spikes.md](docs/spikes.md) and
[docs/listening-loop-calibration.md](docs/listening-loop-calibration.md).

### Producing like a pro

Measurements are not ears. [docs/production/](docs/production/README.md) is a researched knowledge base for agents
that make music here: a playbook of rules and the change loop to follow with the human producer
([00-agent-playbook.md](docs/production/00-agent-playbook.md)), then digests on Live workflow, synthesis and
Live's instruments, sound design recipes, drums and low end, gain staging, mixing, mastering and loudness,
arrangement and harmony, the industrial/EBM/Nine Inch Nails palette, adaptive game music, judging audio without
ears, and every Live 12.4.6 device's exact parameter names. The `pro-production` skill points agents there.

## Limits of Live's API

| Not possible through Live's API | What AbletonMCP does instead |
|---|---|
| Offline export | Real-time `bounce`; optional `export_audio` drives Live's dialog through UI automation |
| Saving or creating sets | `save_set` / `new_set` through UI automation; `open_set` uses the OS |
| Group tracks | `create_bus` routes tracks into an audio bus track |
| Arrangement automation lanes | Automate Session clips with `write_automation`; envelopes travel into the arrangement |
| Freeze, flatten, consolidate, audio editing | Not available |

## Troubleshooting

- **Run `uv run ableton-mcp doctor` first.** It checks Live, the Remote Script link, the port, versions, ffmpeg and permissions, and prints a fix for each failure.
- **AbletonMCP is not in the Control Surface list:** restart Live after `ableton-mcp install`.
- **Errors after updating the code:** call the `reload_remote_script` tool, or run `uv run ableton-mcp-debug send reload_remote_script`, to hot-load new Remote Script code without restarting Live.
- **Live's log:** `~/Library/Preferences/Ableton/Live <version>/Log.txt` on macOS. Remote Script messages are prefixed `AbletonMCP`.

## Development

See [docs/DEVELOPING.md](docs/DEVELOPING.md) for the architecture, adding commands and tools, hot reload
and the test layers:

- **Offline unit and contract tests:** `uv run pytest tests/unit tests/contract`
- **Listening loop analysis (ears) on synthetic fixtures:** `uv run pytest tests/ears` and `uv run ears calibrate`
- **Live integration tests:** `uv run pytest tests/live`, against a running Live; they clean up after themselves.

## Credits

The original AbletonMCP is by [Siddharth Ahuja](https://github.com/ahujasid/ableton-mcp). This fork's v2
rewrite is by Frederic Laruelle. MIT licensed. This is a third-party project and is not made by Ableton.
