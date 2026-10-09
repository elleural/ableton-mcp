# Ableton Live 12 like a pro: workflow, routing and organisation

Digest 01 of `docs/production/`. Written 2026-10-08 for agents that drive **Live 12.4.6 Suite** through AbletonMCP and cannot hear. Facts come from the Live 12 manual, Ableton's Help Center and release notes (through 12.4.6, 15 Sep 2026), a few educator articles, and this repo's own tool docs (`docs/TOOLS.md`, `docs/spikes.md`). Shortcuts are for macOS. Deeper material lives in the sibling digests: synthesis in `02-synthesis-and-live-instruments.md`, sound design in `03-sound-design-recipes.md`, drums and low end in `04-drums-and-low-end.md`, gain staging in `05-gain-staging-and-metering.md`, mixing in `06-mixing.md`, mastering and export in `07-mastering-and-loudness.md`, arrangement and MIDI in `08-arrangement-and-composition.md`, the genre in `09-industrial-ebm-techno-nin.md`, adaptive game audio in `10-game-audio-adaptive-music.md`, judging audio in `11-listening-without-ears.md`, device reference in `12-live-devices-reference.md` (with the exact parameter names in `reference/live-12.4.6-device-parameters.md`).

## If you remember five things

1. **Change one thing, keep the old one alive, let the human choose.** Pros audition against what they already have. Keep the approved version on a muted twin track, make one change, label the A and B, level-match them, and let Fred's ear decide. Never replace a sound he picked. (Section 11.)
2. **Write in Session, shape and commit in Arrangement.** A track plays a Session clip or an Arrangement clip, never both, and Session wins until you press Back to Arrangement. In this project the Session scenes are the authoring surface; the Arrangement is for linear renders. (Section 1.)
3. **Route on purpose.** Groups and buses for submixes, returns for shared time effects, and three tap points (Pre FX, Post FX, Post Mixer) that decide what a sidechain or a recording hears. `create_bus` makes an audio track, not a Live Group Track, and a bus changes what a "stem" is. (Section 3.)
4. **Racks and modulation make one sound move, but the tools cannot map macros or edit zones.** Inspect existing Racks, store a Macro Variation before touching one, and ask the human for the mapping step. `write_automation` creates Session clip envelopes only (it can edit an Arrangement clip's envelope only if the clip already carries one). (Sections 4 and 6.)
5. **Commit deliberately, then protect the work.** Freeze is reversible, Bounce to New Track keeps the source, Bounce Track in Place replaces it. Live keeps ten backups, crash recovery replays undo history (and re-arms tracks), and real-time captures need CPU headroom. Save into a real Project first, and delete structural objects one per call. (Sections 5, 8, 9.)

---

## 1. Session View and Arrangement View: who does what

### 1.1 The rule behind every surprise

A track plays one clip at a time, and it plays either a Session clip or an Arrangement clip, never both. Session clips take precedence. Launching one lights **Back to Arrangement** (in the Session Main track and the Arrangement scrub area, and per track in Arrangement), and pressing it hands the track back to the timeline ([Live Concepts](https://www.ableton.com/en/live-manual/12/live-concepts/)). If "the arrangement does not play", a Session clip is still running on that track. Tool: `transport("back_to_arrangement")`.

### 1.2 Division of labour

| Job | Session View | Arrangement View |
|---|---|---|
| Sketch, jam, A/B variants | Scenes are rows; launch quantization; Legato; follow actions; per-scene tempo and time signature | Poor fit |
| Catch an idea after the fact | **Capture MIDI** records what was just played on armed or monitored tracks. In a new, empty Set with the transport stopped it also detects tempo (80 to 160 BPM only) ([Recording](https://www.ableton.com/en/live-manual/12/recording-new-clips/)) | Same button |
| Build drum patterns | Session record plus overdub plus Record Quantization: the pattern grows each loop ([Recording](https://www.ableton.com/en/live-manual/12/recording-new-clips/)) | Possible, slower |
| Order sections | Scene order is only a list. **Capture and Insert Scene** snapshots what is playing into a new scene ([Session View](https://www.ableton.com/en/live-manual/12/session-view/)) | Locators, time-signature markers, loop brace, Copy Time (Cmd+Shift+C, since 12.4) |
| Time-based shaping | Clip envelopes only | Automation lanes, fades (4 ms declick option), crossfades, Split (Cmd+E), Consolidate (Cmd+J), take lanes, linked tracks ([Arrangement](https://www.ableton.com/en/live-manual/12/arrangement-view/)) |
| Mixing | Mixer under the clip grid, group slots | Mixer in Arrangement (View menu, Cmd+Opt+M); some controls (Performance Impact, Track Delay, crossfader) exist only in the mixer |

### 1.3 Workflows pros actually use

- **Loop first, then print the jam.** Ableton's own recommended path: improvise with Session clips, record the improvisation into the Arrangement with Arrangement Record (it logs launches, parameter moves, automation and scene tempo changes), then refine ([Live Concepts](https://www.ableton.com/en/live-manual/12/live-concepts/), [Session View](https://www.ableton.com/en/live-manual/12/session-view/)). The way back is **Consolidate Time to New Scene** (one clip per track into a new scene).
- **Generate, then curate.** One Ableton interview describes dumping raw generative material seven or eight times, then listening to small loops and shaping them into an arc ([Lynyn](https://www.ableton.com/en/blog/lynyn-trace-elements/)). Live 12's MIDI Generators suit this (Section 7).
- **Zero-friction start.** A pre-built template with Drum Racks, Simpler tracks and effects ready, so a 15-minute window becomes recording, not setup ([DATSUNN](https://www.ableton.com/en/blog/DATSUNN-Habits-That-Make-Better-Beats/)).
- **Arrangement for edits, Session for variants.** Take lanes and comping, fades, automation and tempo/time-signature changes belong to the timeline ([Comping](https://www.ableton.com/en/live-manual/12/comping/)); alternatives live in scenes.

### 1.4 Scenes in Live 12

Scenes can carry their own tempo (20 to 999 BPM) and time signature (numerator 1 to 99, denominator 1, 2, 4, 8 or 16); a coloured launch button shows it, and old Sets that stored tempo in scene names migrate automatically ([Session View](https://www.ableton.com/en/live-manual/12/session-view/), [Scene Tempo](https://help.ableton.com/hc/en-us/articles/5595081962524)). Scene follow actions can be Linked to the longest clip in the scene or Unlinked (12.2) ([release notes](https://www.ableton.com/en/release-notes/live-12/)). Firing a scene selects the next scene unless "Select Next Scene on Launch" is off.

### 1.5 Layout changes in Live 12 worth using

**Stacked detail views** (triangle toggles beside the Clip and Device View selectors, bottom right) show the clip editor and the device chain together; **Mixer in Arrangement**; Tab switches views; Cmd+Opt+3 / 4 toggle Clip / Device View ([Live Concepts](https://www.ableton.com/en/live-manual/12/live-concepts/)). 12.1 added Undo History (View menu, Cmd+Opt+Z) and a full-height browser ([release notes](https://www.ableton.com/en/release-notes/live-12/)).

> **For an agent**
> - Author in Session: one scene per section (`create_scene(name=..., tempo=...)`), one clip per stem per scene. Use `select(view="Session")` so Fred sees what you touch.
> - After any Session launch, a track may be off the timeline. Check `get_status` transport `back_to_arranger`; call `transport("back_to_arrangement")` before judging an arrangement.
> - `arrange_from_scenes` copies Session clips into the timeline. Finish notes and envelopes in Session first; re-run with `clear=True` after later edits. `clear_arrangement` is destructive: ask before clearing tracks Fred may have edited by hand. Verify with `get_arrangement`.
> - This project (`ears/specs/nova.spec.json`): stems are tracks named `{stem}{variation}`, tempo bands are scenes (`NEON-LOW`, `NEON-MID`, ...). Keep that structure; do not reorganise it without asking.

---

## 2. Templates, default sets, names, colours, order

### 2.1 Default Set and templates

- The factory Default Set has two audio, two MIDI and two return tracks. **File > Save Live Set as Default Set** replaces it; **Save Live Set As Template** adds a named template under User Library/Templates; right-click a template and Set Default Live Set to reset ([Default Set and Template Sets](https://help.ableton.com/hc/en-us/articles/209067189)).
- Hold Shift at launch to bypass a custom Default Set; a corrupt audio file or plug-in inside a template can crash Live at start ([Troubleshooting a crash](https://help.ableton.com/hc/en-us/articles/209773265)).
- Educators converge on content: groups per family with a bus device or two, three returns (EQ'd reverb, tempo-synced delay, parallel compression), master-chain devices present but off (Utility, EQ Eight, Glue Compressor, Limiter), role colours, and **no clips** ([Audeobox](https://www.audeobox.com/learn/ableton/ableton-templates-guide/), [EDMProd](https://www.edmprod.com/daw-templates/)). They also warn that a heavy template stifles invention and slows loading; keep several small purpose-built templates rather than one big one.

### 2.2 Names, colours, order

- Rename with Cmd+R; Tab jumps to the next title bar. A `#` prefix numbers tracks automatically (`##` pads zeros) ([Mixing](https://www.ableton.com/en/live-manual/12/mixing/)). **Name audio tracks before recording**: clips and files take the track's name ([Recording Audio](https://help.ableton.com/hc/en-us/articles/7938193554460)). Bounces append "(Bounce)".
- Colour by role (a typical scheme: drums red, bass blue, melodics green, FX purple) and use "Assign Track Color to Grouped Tracks and Clips" on a Group header ([Audeobox](https://www.audeobox.com/learn/ableton/ableton-templates-guide/), [Mixing](https://www.ableton.com/en/live-manual/12/mixing/)).
- Track order is convention, not rule: sources by family (drums, bass, harmony, leads, FX), returns after, Main last. For this project the readable choice is the order stems join in the game (pad+arp, bass, kick, perc, lead). That is a suggestion; check with Fred.
- **One Live Project per song.** Several songs in one Project folder bloat it and slow Live; several versions of the same song in one Project are fine and share collected samples ([Unique Projects](https://help.ableton.com/hc/en-us/articles/360002864179), [Managing Files](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/)).

> **For an agent**
> - Name every track at creation (`create_track(kind, name, color=...)`). Names must be unique, and Live renumbers default names such as "3-Audio" when tracks move (`docs/spikes.md`). Return tracks carry a letter prefix ("A-Reverb"); bare names also resolve.
> - Do not rename, recolour or reorder Fred's tracks unasked. Tools: `set_track(name=, color=)`.

---

## 3. Groups, buses, returns and routing

### 3.1 Group, return, bus

| | Group Track | Return Track | "Bus" made by `create_bus` |
|---|---|---|---|
| What | Submixer that holds tracks; no clips of its own; Cmd+G | Effects-only track fed by sends | Ordinary audio track (monitoring In, input "No Input") that sources are routed into |
| Use | Glue and shared EQ on a family; one fader, mute, solo; fold; Bounce Group | Shared reverb/delay; parallel processing; saves CPU | Same job when you cannot create a Group |
| Folding, colour inheritance, Bounce Group | Yes | n/a | **No** (it is not a Group) |
| Tool | none (UI) | `create_track(kind="return")` | `create_bus(name, sources)` |

Groups do not cost CPU by themselves: the tracks inside run in parallel. What forces serial work is any routing of one track into another and every send/return pair, because the receiving track must wait ([Multi-core FAQ](https://help.ableton.com/hc/en-us/articles/209067649)).

### 3.2 Sends versus inserts

An **insert** (device on the track) shapes that track: EQ, dynamics, saturation, anything that changes tone. A **send effect** (return track at 100% wet) is shared by many tracks: reverb, delay, parallel crush. One reverb instance on a return instead of one per track also saves CPU. Per-track parallel processing can live inside an Audio Effect Rack instead (Section 4).

- **Pre/Post** toggle on the return: Post (default) follows the track fader; Pre ignores the fader and the track Activator, so the send level does not change when you fade the dry. A track's **Sends Only** output sends nothing to Main ([Mixing](https://www.ableton.com/en/live-manual/12/mixing/), [Routing](https://www.ableton.com/en/live-manual/12/routing-and-i-o/)).
- A return's own sends to other returns are off by default (feedback risk). Soloing a clip track leaves returns audible when **Solo in Place** is on.
- Live's engine is 32-bit float: levels above 0 dB do not clip between devices, only at the physical output or a bounce/export ([Mixing](https://www.ableton.com/en/live-manual/12/mixing/), [Working with Instruments](https://www.ableton.com/en/live-manual/12/working-with-instruments-and-effects/)). A stereo-to-mono output is summed at -6 dB, and Live's pan can raise a channel up to +3 dB at hard pan ([Routing](https://www.ableton.com/en/live-manual/12/routing-and-i-o/), [Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/)).

### 3.3 Tap points: Pre FX, Post FX, Post Mixer

When a track takes its input from another track (or a sidechain listens to one), choose where to tap ([Routing](https://www.ableton.com/en/live-manual/12/routing-and-i-o/)):

| Tap | Signal | Source fader, pan, mute | Soloing the destination still lets you hear the source |
|---|---|---|---|
| Pre FX | before the source's devices | no effect | yes |
| Post FX | after devices, before the mixer | no effect (device changes do) | yes |
| Post Mixer | after devices and mixer | fader, pan, mute change it | **no** |

Rack chains offer their own taps (`Rack | Chain | Post FX`). Practical consequences: a muted "ghost" track can still key a sidechain through Pre FX or Post FX (not Post Mixer); a recording of Post Mixer includes the fader move you made.

### 3.4 Sidechain

Compressor, Glue Compressor, Gate, Auto Filter, Multiband Dynamics, Corpus and Shifter have an external sidechain (12.2 gave them a dedicated header) ([release notes](https://www.ableton.com/en/release-notes/live-12/)). Roar can take an external envelope follower and a MIDI sidechain, and the Max for Live Envelope Follower got a sidechain in 12.1. The controls follow one pattern ([Audio Effect Reference](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)):

- **Sidechain/External** toggle; **Audio From** (the source track) plus the **tap** (Pre FX, Post FX, Post Mixer).
- **Gain** (trigger level only; it never makes the track louder), **Mix / Dry-Wet** (at 100% the device reacts only to the external signal).
- A **sidechain EQ or filter** and a **Listen** button (headphone) that auditions the trigger instead of the output.
- Third-party plug-ins: only those with their own sidechain input respond; set Audio From in the plug-in's sidechain section ([Help](https://help.ableton.com/hc/en-us/articles/209775325)).

Numbers educators use for kick ducking ([EDMProd](https://www.edmprod.com/sidechain-compression/)): ratio 4:1 to 5:1 (2:1 with 2 to 3 dB of reduction for subtle ducking, up to 12:1 for effect); punchy pump: attack 3 to 4 ms, release 16 to 60 ms; natural duck: attack about 30 ms, release about 250 ms; high-pass the trigger so sub rumble does not drive it; a **ghost kick** (a trigger that plays in builds but is silent in the drop) gives pumping without the kick. Rule of thumb (mine): the release should let the level recover before the next trigger; at 128 BPM a beat is 469 ms, so 150 to 250 ms for quarter-note triggers. EDMProd's own caution: use it to solve a problem or for an obvious effect, not by reflex. See `04-drums-and-low-end.md`.

### 3.5 Resampling and recording one track from another

- **Resampling** is an Audio From choice on an audio track: it records the Main output. Set Monitor to Off, arm the track, record into an empty slot. The track's own output is excluded. Files go to the Project's `Samples/Recorded`, or to a temporary folder until the Set is saved ([Routing](https://www.ableton.com/en/live-manual/12/routing-and-i-o/), [Real-time rendering](https://help.ableton.com/hc/en-us/articles/209067709)).
- To record **one** track (not the whole mix), set Audio From to that track and a tap. Pre FX/Post FX taps ignore its fader; use Post Mixer if the fader and pan are part of the sound. Watch the source's meter first: a recording is as loud as its tap.
- Recording from internal routes is sample-aligned: this repo measured 0 samples of offset for Post Mixer and Resampling taps (`docs/spikes.md`).
- Monitoring: Auto (monitor when armed), In (always), Off. "Keep Monitoring Latency in Recorded Audio" is on by default; turn it off for acoustic sources ([Monitoring FAQ](https://help.ableton.com/hc/en-us/articles/360006569179)).

### 3.6 Multi-output instruments and Drum Racks

- Another track can tap a single Drum Rack or Instrument Rack **chain** through Audio From (Pre FX, Post FX, Post Mixer for that chain). Tapping removes it from the instrument's internal mix, as with Impulse's 8 slot outputs ([Routing](https://www.ableton.com/en/live-manual/12/routing-and-i-o/)).
- **Session View chain strips**: a track holding a multi-chain Rack has a fold button that shows each chain as a mixer strip; drag a chain out to its own track (a drum chain keeps its note) ([Racks](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/)).
- Drum Racks have up to six **return chains** (send sliders per pad, Audio To the Rack's main output or the Set's returns), and up to 16 **choke groups** (hat open/closed).
- **External Instrument / External Audio Effect** devices add the interface latency plus a Hardware Latency slider; freezing them forces a real-time pass. This project has no hardware synths.

> **For an agent**
> - Group: `create_bus("Drum Bus", ["Kick","Hats"])` makes an audio track at the end, routes the sources' outputs into it, sets its input to "No Input" and monitoring to In. It takes **two undo steps** to revert and needs unique names. Routing lists fill a tick after a track is created, so routing can answer "busy"; retry (`docs/spikes.md`). Verify with `get_routing_options` and `get_meters` that audio arrives.
> - **Do not bus stems that the listening loop captures separately** unless the bus is a captured part: stems are tapped at each part's own output, so bus processing is missing from them and the sum-null check (`audio.sum_null`) will point at "a track outside the spec" (`.claude/skills/listening-loop/SKILL.md`).
> - Returns: `create_track(kind="return", name="Plate", device="Reverb")`, then `set_mixer(track, sends={"A": -12})`. The **Pre/Post toggle is not exposed** by any tool or the Live API: ask Fred if it matters.
> - Sidechain: `set_sidechain("Bass", "Drums", threshold_db=-30, ratio=4, attack_ms=1, release_ms=150)` works on Live's **Compressor only**, the one device whose sidechain input the Live API can route (default tap Post FX; `docs/TOOLS.md`, `docs/reference/live_api_12.4.6.md`). For Glue Compressor, Gate, Auto Filter and the rest, ask Fred to pick the source in Live. A `source` that is a whole Drum Rack track keys on every drum, hats included.
> - After any routing change: `get_meters` with the transport playing, then a `capture`. A sidechain that "works" in meters can still duck the wrong thing.

---

## 4. Racks in depth

### 4.1 Four kinds, one idea

A Rack is parallel **chains**, each a serial device chain, with a mixer per chain, summed at the Rack output ([Racks](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/)).

| Rack | Holds | Placed on |
|---|---|---|
| MIDI Effect Rack | MIDI effects | MIDI tracks |
| Instrument Rack | MIDI effects, one or more instruments, audio effects | MIDI tracks |
| Audio Effect Rack | audio effects | any audio-carrying track |
| Drum Rack | one chain per pad (note), return chains, choke groups | MIDI tracks |

Select devices and press Cmd+G to wrap them; Cmd+G on a Rack nests it; "Group to Drum Rack" for samples. Chain list rows have activator, solo, hot-swap, volume, pan and send controls.

### 4.2 Zones and the chain selector

Before MIDI enters a chain it must pass three filters: **Key Zone** (note range), **Velocity Zone** (1 to 127) and **Chain Select Zone** (0 to 127). Fade ranges at zone edges make crossfades (velocity for MIDI, volume for audio). The **Chain Selector** is one parameter that picks the chains whose select zone covers its value: set each chain a unique zone with small overlaps and it becomes a morphable preset bank, automatable and mappable ([Racks](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/)).

### 4.3 Macros and Macro Variations

- **8 Macro Controls by default, up to 16** (the +/- buttons). Map mode: click a parameter, press Map under a macro; set per-parameter **Min/Max** in the mapping list; Min above Max gives an inverted mapping. A mapped parameter greys out because the macro owns it. Mapping several parameters resets the macro to a generic "Macro n" name, so rename it.
- **Rand** randomises mapped macros (a macro can be excluded in its context menu).
- **Macro Variations** (since Live 11) store, launch, overwrite and rename snapshots of all mapped macros; a macro can be excluded from variations.

### 4.4 How pros build layered instruments and one-knob controls

Illustrative starting points (mine; adapt to the sound):

- **Layered pad:** an Instrument Rack with three chains (body: saw-based synth; air: noise or FM, high-passed; sub: sine, mono, low-passed). Macros: Body/Air balance (chain volumes mapped in opposite directions), Width (Utility on the Rack output), Space (return send or Reverb Dry/Wet). Per-chain EQ keeps layers out of each other's band.
- **One-knob "Intensity":** one macro to Auto Filter Frequency (for example 300 Hz to 6 kHz), Saturator Drive (0 to 6 dB), a "Dirt" chain volume (-inf to -12 dB) and Utility Width (100% to 130%); set tapers with Min/Max so the knob stays musical across its whole travel.
- **Parallel dirt:** Audio Effect Rack with chains Dry, Crush and Space. Distortion on the parallel chain, not on the full chord, keeps the clean harmonic series intact (saturating dense chords creates intermodulation that reads as "out of tune"; see `03-sound-design-recipes.md`).
- **Velocity layers for drums:** three chains with velocity zones about 1 to 64, 65 to 100, 101 to 127, overlapped by 10 to 20 so hits crossfade.
- **Chain Selector bank:** four sound variants on one track; automate the selector per section.
- **MIDI Effect Rack:** Scale (with `Use Current Scale`) into Chord into Arpeggiator, macros on the Arpeggiator's `Synced Rate`, `Gate` and `Style`.
- Drum Racks: choke group for open/closed hats, a drum-only reverb on a return chain, and Drum Sampler (new in 12.1), which you can make the default pad (right-click a pad, "Save as Default Pad").

### 4.5 Rack hygiene

- **Store an "approved" Macro Variation first**; never press Rand on a sound Fred approved.
- A preset's name tells you nothing: open the chains and see which devices and macros it holds. One audition produced a "hollow" pad because the only pitched voice was a sub saw and noise.
- Hot-Swap (Q) and A/B Compare (P) work inside Racks. Save a finished Rack from its title bar (Save Preset); presets and Racks live in the User Library, Live Clips (.alc) also save the track's devices ([Managing Files](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/)).

> **For an agent**
> - **Can:** `get_devices` (chains, visible macros, variation count), `get_device` (chain mixers, macro values, chain selector), `set_device_parameters(track, rack, {"Macro 3": 64})` (macros run 0 to 127), `set_chain` (name, colour, mute, solo, volume_db, pan; Drum chains: in_note, out_note, choke_group), `device_action` (`insert_chain`, `add_macro`, `remove_macro`, `store_variation`, `recall_variation`, `randomize_macros`), `add_device(track, "Audio Effect Rack")` and then `add_device(track, "Saturator", chain="Audio Effect Rack/new")` (one call per chain), `load_from_browser` for finished Rack presets.
> - **Cannot** (no tool, and the Live API does not expose it): map a macro to a parameter, edit key/velocity/chain-select zones or fade ranges, set Pre/Post sends. **Stop and ask** Fred to do that step in Live, or load an existing mapped Rack from the browser.
> - `device_action` is flagged destructive; `randomize_macros` overwrites. Call `store_variation` first and keep its index.
> - Load candidates onto a **new** track. `load_from_browser` of an instrument or kit replaces the track's instrument (`docs/TOOLS.md`).
> - Verify: re-read with `get_device`, then `get_meters` with the transport playing. A macro that is not mapped to anything does nothing, so a changed macro value proves nothing by itself.

---

## 5. Committing: Freeze, Bounce, Consolidate, Resample

### 5.1 What each command does

| Command (Mac) | Renders | Mixer settings | Source afterwards | Reversible | Files |
|---|---|---|---|---|---|
| **Freeze Track** (Cmd+Opt+Shift+F) | Devices and clip settings for Session and Arrangement clips, 32-bit | kept live (volume, pan, sends still adjustable) | track stays; edits locked until Unfreeze | Yes: Unfreeze | `Samples/Processed/Freeze` |
| **Bounce Track in Place** (12.2) | Whole track, post-FX, pre-mixer, as one audio track | copied to the new track | **replaced** by the audio track (treat the MIDI and instrument as gone) | Undo only | `Samples/Processed/Bounce` |
| **Bounce to New Track** (Cmd+B, 12.2) | Selected clips or time range, post-FX, pre-mixer | track settings duplicated | kept, **deactivated** so playback is not doubled | Yes: reactivate | same |
| **Bounce Group in Place / to New Track** (12.3) | The Group with its own effects, sends and returns, taken at the Main track before Main's devices | n/a | replaced / kept | Undo / reactivate | same |
| **Paste Bounced Audio** (Cmd+Opt+V, 12.3) | Copied material, in its current state | n/a | untouched | n/a | same |
| **Consolidate** (Cmd+J) | Clip-level only: gain, warp, pitch, clip envelopes. No track effects. Normalises with clip gain compensated | n/a | new clip replaces selection | Undo | `Samples/Processed/Consolidate` |
| **Resample** (Audio From = Resampling or a track) | Anything routed, in real time, including returns and Main chain | what you record is post whatever tap you chose | untouched | n/a | `Samples/Recorded` |

Sources: [Bounce to Audio](https://www.ableton.com/en/live-manual/12/bounce-to-audio/), [Bounce FAQ](https://help.ableton.com/hc/en-us/articles/22999165562396), [Committing Audio](https://help.ableton.com/hc/en-us/articles/22998838817820), [CPU chapter](https://www.ableton.com/en/live-manual/12/computer-audio-resources-and-strategies/), [Arrangement](https://www.ableton.com/en/live-manual/12/arrangement-view/), [12.2 and 12.3 release notes](https://www.ableton.com/en/release-notes/live-12/). Plain Freeze/Unfreeze still exists; 12.2 renamed the old "Freeze and Flatten Track" and "Flatten" commands to Bounce Track in Place. Freeze cannot be applied to Group, Return or Main tracks, and a frozen Session clip stores only two loop cycles.

### 5.2 Why pros commit

Committing frees CPU, forces decisions, and turns a patch into audio you can reverse, chop, pitch and re-process. **Generational resampling** is the sound-design version: process, resample, reverse or stretch, process again; each pass adds character no single chain gives ([EDMProd](https://www.edmprod.com/resampling/), [Lost Stories Academy](https://loststoriesacademy.com/blogs-and-tutorials/why-professional-producers-love-resampling)). Other Bounce to New Track tricks ([Attack](https://www.attackmagazine.com/technique/tutorials/six-bounce-to-new-track-tricks-to-try-in-live-12-2/)): bounce an effect tail separately (fully wet delay or reverb, then bounce again with the following bars) so it can be shaped per element; reverse-reverb swells (bounce a bar, reverse, add a wet 15-second plate, bounce, reverse back); do destructive loop edits on the bounce so the reverb on the source does not smear the cuts.

### 5.3 Cautions

- **Where the bounce is taken.** A track bounce is post-FX but pre-mixer, so its fader, pan and sends are *not* in the audio (they are copied to the new track). A group bounce is taken at the Main track before Main's own devices: it includes the group's effects, sends and returns, leaves out tracks routed outside the group, and counts a return only if that return reaches Main.
- Release notes list bugs worth re-checking after a commit: before 12.4, freezing or bouncing a track with real-time devices could disable devices on tracks used for sidechaining or Max-for-Live modulation (fixed in 12.4); 12.4.6 fixed a hang when rendering, bouncing or consolidating Sets with many Beats-mode audio tracks at Transients resolution. After a commit, confirm the sidechained and modulated tracks still behave.
- Do not use a commit to fix level. Bounce what Fred approved; do not bake in a limiter chasing a number.
- Check warping on bounced clips: stems in this project must be unwarped, and the same file has come up warped one time and unwarped the next (`docs/spikes.md`).
- **Name clash:** the MCP tool `bounce` renders the Arrangement to WAV in real time for analysis (resampling inside Live). It is not Live's Bounce to New Track.

> **For an agent**
> - Freeze, Bounce Track in Place, Bounce to New Track and Consolidate are UI commands: **no tool performs them** (the Live API has `is_frozen` and `can_be_frozen` but no freeze, bounce or consolidate call; the `bounce` tool is a different thing, a real-time render to WAV files that changes no track). `get_track` reports `frozen`. Ask Fred to select the clips and press **Cmd+B** (non-destructive: the source stays, deactivated); do not ask for Bounce Track in Place on anything he has not signed off.
> - To get rendered audio into the Set without UI: `bounce(...)` or `capture(...)` write WAV files; `create_clip(track, slot=, file_path=)` places a file on an audio track. Looper has an `export_to_clip_slot` action (`device_action(track, "Looper", "export_to_clip_slot", args={"track": ..., "slot": ...})`): record into a Looper on an audio track fed from another track, then export to an empty slot. Untested for this purpose; try it on a scratch track in a saved Set.
> - `fire_clip` refuses empty slots, so you cannot start a resampling take that way; `capture` does it internally.

---

## 6. Modulation, automation, follow actions, groove

### 6.1 Automation versus modulation

Automation (red) sets a control's value over time; modulation (blue) offsets it and can only work inside what automation allows, so both can run on one parameter ([Automation and Modulation](https://help.ableton.com/hc/en-us/articles/209070629), [Clip Envelopes](https://www.ableton.com/en/live-manual/12/clip-envelopes/)). Where each lives:

- Session clip: the Envelope box has **Aut** and **Mod** tabs; an LED shows red, blue or both.
- Arrangement: automation in lanes (press A); a clip only shows modulation in Clip View. Copying Session automation into the Arrangement turns it into track automation ([Automation](https://www.ableton.com/en/live-manual/12/automation/)).
- Overriding an automated control by hand lights **Re-Enable Automation** until you press it or relaunch the clip.

### 6.2 Editing automation (Live 12)

Draw mode is B. Click a segment to add a breakpoint, a point to delete it, right-click for "Edit Value"; Opt-drag curves a segment. Right-click a time selection for shapes (sine, triangle, sawtooth, inverse sawtooth, square, ramps, ADSR). **Simplify Envelope** cleans recorded automation; **Lock Envelopes** keeps automation on the timeline when clips move; since 12.2 the keyboard can walk breakpoints. Song tempo is an automation lane on Main (Mixer > Song Tempo) ([Automation](https://www.ableton.com/en/live-manual/12/automation/), [release notes](https://www.ableton.com/en/release-notes/live-12/)).

### 6.3 Clip envelopes: linked and unlinked

By default an envelope follows the clip's loop. **Unlinked** gives it its own loop length: an eight-bar fade from a one-bar clip, a four-bar filter sweep over a one-bar loop, a three-against-four polyrhythm, odd lengths such as 3.2.1 bars. Audio clips also have Clip Gain, Transposition and (Beats mode) Sample Offset envelopes. Modulation cannot open a send past the Send knob ([Clip Envelopes](https://www.ableton.com/en/live-manual/12/clip-envelopes/)).

### 6.4 Max for Live modulators

LFO, Envelope Follower, Shaper (audio effects) and Envelope MIDI, Expression Control, Shaper MIDI (MIDI effects) map to up to eight parameters each ([Max for Live Devices](https://www.ableton.com/en/live-manual/12/max-for-live-devices/)). Press **Map**, click a target; **Modulation** mode adds to the knob (it stays adjustable, new in Live 12), **Remote Control** takes it over. LFO: shapes from Sine, Triangle and Square to Random, Stray and Glider; Rate in Hz or beat divisions; Jitter, Smooth, Phase, Offset, Depth, Polarity, Hold/Retrigger. Envelope Follower: Gain, Rise, Fall, Delay, sidechain with a Pre/Post FX source (a ducking tool since 12.1). Shaper: drawn breakpoint envelope, Loop/1-Shot/Manual. Native modulation also lives in the instruments: Wavetable's mod matrix ([Attack: ten routings](https://www.attackmagazine.com/technique/tutorials/10-common-modulation-routings-using-abletons-wavetable/)), Drift, Meld, the redesigned Auto Filter (12.2) and Auto Pan-Tremolo (12.3). Max devices need their `.amxd` files collected, and an open editor window adds latency ([Delay Compensation FAQ](https://help.ableton.com/hc/en-us/articles/209072409)).

### 6.5 Follow actions

Ten actions (No Action, Stop, Play Again, Previous, Next, First, Last, Any, Other, Jump); two actions per clip with chances; **Linked** (clip end or N loops) or **Unlinked** (a time you set); scene follow actions; a global enable button; "Create Follow Action Chain" ([Launching Clips](https://www.ableton.com/en/live-manual/12/launching-clips/), [Follow Actions in Live 11](https://help.ableton.com/hc/en-us/articles/360019101360)). Chances below 100% are random, so captures stop being repeatable. Keep them deterministic while measuring.

### 6.6 Groove pool and swing

A groove has Base (grid), Quantize, Timing, Random (0 to 100%), Velocity (-100 to +100), and a Global Amount up to 130%. **Commit** writes it into notes or audio Warp Markers ([Using Grooves](https://www.ableton.com/en/live-manual/12/using-grooves/)). Grooves are non-neutral on audio because they move warp markers ([Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/)). Since 12.1 a groove is loaded in the default Set and auto-applied to new MIDI clips; Global Groove Amount defaults to 0%, so raising it moves every such clip at playback while note data stays unchanged ([release notes](https://www.ableton.com/en/release-notes/live-12/)). The song **swing** amount (0 to 1) affects only recording quantization and direct quantize calls. In this repo's note tools (`transform_notes` quantize, `write_drum_pattern`) `swing` delays every second step by swing x half a step, i.e. MPC-style percent = 50 + 25 x swing, so 0.67 is a triplet shuffle. Keep swing small in techno and EBM and verify by reading note starts back.

> **For an agent**
> - `write_automation(track, "volume", slot=0, shape={"type": "sine", "from": -12, "to": -6, "period": "1 bar"})` writes a **Session clip envelope** (automation) that loops with the clip and travels with `arrange_from_scenes`. It is the tool-side substitute for an LFO. Arrangement clips only edit envelopes they already carry. The Live API exposes no modulation (blue) envelopes, no unlinked loop length, and no Max-device mapping.
> - When Fred copies a Session clip into the Arrangement by hand, Live turns its automation into track automation lanes; the tool's copy keeps it as a clip envelope that loops with the clip (`docs/spikes.md`). After `arrange_from_scenes`, tell him where the movement lives.
> - Read back with `get_automation`; clear with `clear_automation`. If Fred has moved an automated control by hand, Live ignores that automation until re-enabled: `capture` and `bounce` warn about it, and `lom_call("live_set", "re_enable_automation")` clears it.
> - Follow actions are not in the Live API; tell Fred what to set. `set_clip` covers launch mode, launch quantization, legato, groove; `get_grooves`/`set_groove`/`set_song(swing=, groove_amount=)` cover the pool. A clip's groove cannot be set back to None (`docs/spikes.md`).

---

## 7. Live 12 features that change the workflow

### 7.1 Version map

| Version (date) | Highlights relevant here |
|---|---|
| 12.0 (5 Mar 2024) | MIDI Transformations and Generators; Keys and Scales; Tuning Systems; Roar, Meld, Granulator III; Mixer in Arrangement; stacked detail views; tag-based browser and sound-similarity search |
| 12.1 (8 Oct 2024) | Auto Shift; Drum Sampler; rebuilt Limiter (True Peak, Soft Clip, Mid/Side) and Saturator (Bass Shaper curve); Find and Select Notes; Chop tool; MPE tools; scale for audio clips; groove auto-load; Undo History; auto-tagging of user samples |
| 12.2 (11 Jun 2025) | Bounce Track in Place / to New Track; Auto Filter redesign; Meld Chord oscillator; Roar sidechains and Delay mode; scale/tuning in Resonators and Spectral Resonator; Operator to 32 voices; Quick Tags |
| 12.3 (25 Nov 2025) | Stem Separation (Suite); Splice; Auto Pan-Tremolo; Bounce Group; Paste Bounced Audio; device A/B Compare (P); browser overhaul |
| 12.4 (5 May 2026) | Link Audio; Erosion, Chorus-Ensemble, Delay updates; Learn View; Copy Time; S toggles solo on selected chains; Wavetable max 16 voices |
| 12.4.3 to 12.4.6 (Jul to Sep 2026) | Re-Pitch warp respects groove; Max for Live 9.1.5; hang fix for rendering/bouncing many Beats-mode tracks |

Sources: [release notes](https://www.ableton.com/en/release-notes/live-12/), [Live 12 features](https://www.ableton.com/en/live/all-new-features/), [Live 12.4 post](https://www.ableton.com/en/blog/live-12-4-is-out-now/), [Wikipedia for the 12.0 date](https://en.wikipedia.org/wiki/Ableton_Live).

### 7.2 MIDI Transformations and Generators

Both live in the Clip View tool panels and work in scale degrees when the clip has a scale ([MIDI Tools](https://www.ableton.com/en/live-manual/12/midi-tools/)). **Transformations:** Arpeggiate, Chop (up to 64 parts), Connect, Glissando (MPE), LFO (MPE), Ornament, Quantize, Recombine, Span, Strum, Time Warp, Velocity Shaper (Max). **Generators:** Rhythm (up to 16 steps, density, split, accents), Seed (random notes inside pitch, length and velocity ranges), Shape, Stacks (chords in the scale; custom JSON chord banks since 12.1), Euclidean (Max, up to four voices). They fill the loop brace or time selection, and **Auto** applies changes live while you tweak; the output is ordinary MIDI notes. 12.1 added chaining and Key/MIDI mapping. Practical advice ([Attack](https://www.attackmagazine.com/technique/tutorials/getting-started-with-ableton-lives-generative-midi-tools/)): one voice at a time for Rhythm; Seed with Voices 1, a narrow duration range, Density near 50%; set the loop brace to the length you want first. See `08-arrangement-and-composition.md`.

### 7.3 Keys and Scales, Tuning Systems

- A **clip scale** (Root and Scale Name in Clip properties; since 12.1 also audio clips and Drum Rack tracks) is forwarded to devices with **Use Current Scale**: Scale, Chord, Pitch, Random, Arpeggiator, Meld's chord and scale-aware oscillators, Resonators, Spectral Resonator, Auto Pitch ([Editing MIDI](https://www.ableton.com/en/live-manual/12/editing-midi/), [MIDI Effects](https://www.ableton.com/en/live-manual/12/live-midi-effect-reference/)). In the piano roll, K highlights scale keys and G folds to the scale.
- **Tuning Systems** (.scl / .ascl, browser Tunings label) apply per Set. All native instruments follow; MPE plug-ins need a 48-semitone bend range or play out of tune; Drum Racks bypass; Scale Mode switches off while a tuning is loaded ([Tuning](https://www.ableton.com/en/live-manual/12/using-tuning-systems/)).
- **Drift's Drift control** deliberately detunes voices; high values sound out of tune by design ([Instrument Reference](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)).

### 7.4 Instruments and effects you will meet

**Meld** (bi-timbral, 25 oscillator types per engine in 12.4.6 including the 12.2 Chord oscillator, MPE), **Roar** (three-stage saturation, feedback generator, envelope follower with external and MIDI sidechain), **Granulator III** (Max for Live, Suite; Classic, Loop and Cloud modes; can record live audio from Live; resample its output; [pack page](https://www.ableton.com/en/packs/granulator-iii/)), **Drift** (two-oscillator subtractive, Poly/Mono/Stereo/Unison, light on CPU). Details in `02-synthesis-and-live-instruments.md` and `12-live-devices-reference.md`.

### 7.5 Finding sounds

The Live 12 browser has tags, filters, Quick Tags (12.2), Collections (colours 1 to 7) and **Similarity Search** (right-click a file, Cmd+Shift+F) that finds sounds similar to a chosen one in the Core and User libraries; Drum Racks can swap a sample for a similar one. Samples under 60 s are analysed in the background and auto-tagged; progress shows in the Status Bar ([Browser](https://www.ableton.com/en/live-manual/12/working-with-the-browser/), [Live Concepts](https://www.ableton.com/en/live-manual/12/live-concepts/)). Hot-Swap is Q. Use similarity to **shortlist from a sound Fred already likes**, not to rank presets against a reference mix; it compares sounds, not mixes, and says nothing about whether one is good.

### 7.6 Comping, linked tracks

Take lanes exist in the Arrangement only: recording over material or loop-recording adds lanes automatically, the last take is copied to the main lane, Audition Mode is T, and source highlights show where each comp section came from ([Comping](https://www.ableton.com/en/live-manual/12/comping/)). **Link Tracks** makes edits (move, split, consolidate, fades, takes) apply to several tracks at once: a natural fit for editing several stems with identical cuts ([Arrangement](https://www.ableton.com/en/live-manual/12/arrangement-view/)).

### 7.7 A/B Compare

Since 12.3 every device has two states, A and B (P switches). Edit one, flip to hear the other, or copy A to B to bank a change. Automation is state-specific: after switching, re-enable automation on affected parameters ([Working with Instruments](https://www.ableton.com/en/live-manual/12/working-with-instruments-and-effects/)).

> **For an agent**
> - `set_song(key="A minor", scale="Minor", scale_mode=True)` sets the Set scale; `transform_notes(operation="transpose", steps=...)` transposes in scale degrees; `analyze_notes` checks key and chord tones; `music_theory` builds scales, chords, progressions.
> - Loading a tuning file is not in the API. `live_set tuning_system` can be read with `lom_get`; the Live API dump lists its `name`, `reference_pitch`, `lowest_note`, `highest_note` and `note_tunings` as read-write, so `lom_set` could change them (untested here, and a change would retune every instrument: ask Fred first). If Fred hears "wrong notes", first read `lom_get("live_set tuning_system")` (nothing loaded is the normal case), then device Detune and Drift's Drift amount, then voice stacking.
> - You cannot run Similarity Search. `search_browser` matches names only; shortlist with names and tags, then ask Fred which to audition.
> - Device A/B in the tools: `device_action(track, device, "save_ab_slot")` stores the current state in the compare slot, `set_device(track, device, compare_b=True)` switches the device to the B state so you can edit B while A stays as approved, and `get_device` shows which is active. Fred presses P to compare. Check the `compare_b` flag after every call; this path is untested.

---

## 8. CPU, latency, sample rate

### 8.1 Latency arithmetic

Interface latency is buffer size divided by sample rate: 256 samples at 44.1 kHz is 5.8 ms, and round-trip is roughly double ([How Latency Works](https://help.ableton.com/hc/en-us/articles/360010545559)).

| Buffer (samples) | 44.1 kHz | 48 kHz |
|---|---|---|
| 64 | 1.5 ms | 1.3 ms |
| 128 | 2.9 ms | 2.7 ms |
| 256 | 5.8 ms | 5.3 ms |
| 512 | 11.6 ms | 10.7 ms |
| 1024 | 23.2 ms | 21.3 ms |

Convention (practitioner, not an Ableton number): 128 to 256 while playing live, 512 to 1024 while mixing, rendering or running real-time captures. Ableton's advice for dropouts: raise the buffer until crackles stop; use 44.1 kHz to cut load ([Crackles and dropouts](https://help.ableton.com/hc/en-us/articles/209070329)). Latency is irrelevant to what the agent hears, but a dropout during a real-time capture corrupts the take.

### 8.2 Delay compensation

Automatic compensation delays every path to match the slowest. Lookahead devices (Limiter, Compressor lookahead) add latency even when bypassed; negative Track Delays cascade onto other tracks. **Reduced Latency When Monitoring** bypasses compensation on monitored tracks, so they drift out of sync with returns and can misplace recorded automation: turn it off for mixing, rendering and export ([Reduced Latency FAQ](https://help.ableton.com/hc/en-us/articles/209072249), [Delay Compensation FAQ](https://help.ableton.com/hc/en-us/articles/209072409)).

### 8.3 CPU

- The CPU meter shows how close each audio buffer comes to its deadline, not total CPU. 100% means dropouts. Live 11+ shows **Current** (peak) by default; **Average** is smoother. Use **Performance Impact** (six-segment indicator per track in the mixer) to find the heaviest track ([CPU Meter](https://help.ableton.com/hc/en-us/articles/360019151379), [Mixing](https://www.ableton.com/en/live-manual/12/mixing/)).
- One serial chain is the limit: effects on a track run in sequence on one core. Spread load across tracks, use returns instead of duplicate heavy plug-ins, and freeze or bounce the heaviest track ([Multi-core FAQ](https://help.ableton.com/hc/en-us/articles/209067649)).
- Cheapest wins: switch devices **off** (off costs nothing); cut voices (Wavetable unison multiplies: 8 notes x 3 oscillators x 8 unison voices is 192 voices); turn off Spread on Operator, Sampler and Corpus; use the Clean filter instead of Cytomic circuits; avoid Complex and Complex Pro warping and Hi-Q when transposing ([Wavetable CPU](https://help.ableton.com/hc/en-us/articles/360000036930), [CPU-intensive devices](https://help.ableton.com/hc/en-us/articles/12911009486108)). Close Max editor windows.
- macOS: Live uses Performance cores only on Apple silicon (since 11.3); close browsers, switch off Wi-Fi and Bluetooth, keep at least 10% disk free, prevent thermal throttling ([macOS CPU](https://help.ableton.com/hc/en-us/articles/5266527910812)).

### 8.4 Sample rate

Decide before starting; do not mix rates inside a Set; convert files offline; Live resamples on import and export with the SoX library ([Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/)). This Set runs at 44.1 kHz while the delivery spec is 48 kHz, 24-bit (`ears/specs/nova.spec.json`). Whether to switch the Set is a decision for Fred (Open questions).

> **For an agent**
> - CPU: `get_status` returns `live.cpu` (average load); `get_track(track, detail=True)` adds `performance_impact`. `capture` and `bounce` warn above 75% that a real-time capture (or bounce) "may drop out". Aim lower (say under 60%) before long captures, and reduce load by asking Fred to freeze or bounce, not by deleting devices.
> - Buffer size and sample rate are Live preferences and not in the Live API: ask Fred. Do not claim them.

---

## 9. Saving, versioning, crash recovery

- **Project hygiene.** A Set lives in a Project folder. "Save Live Set As" starts a new Project unless you save into an existing one; "Save a Copy" branches without switching. Keep versions of one song in its Project; never several songs ([Managing Files](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/), [Unique Projects](https://help.ableton.com/hc/en-us/articles/360002864179)).
- **Backups.** After the second save Live writes a `Backup` folder in the Project and keeps the ten most recent saves, named with a timestamp in brackets; the browser filter Content > Backup Set finds them ([Backup Sets](https://help.ableton.com/hc/en-us/articles/360000377870), [release notes](https://www.ableton.com/en/release-notes/live-12/)).
- **Collect All and Save** copies audio, video and Max for Live devices into the Project (not plug-ins). Run it before moving, sharing or archiving ([Collect All and Save](https://help.ableton.com/hc/en-us/articles/209775645)). Preset and Pack content from Factory Packs can be included deliberately.
- **Undo History** (Cmd+Opt+Z) lists all steps since the Set opened and lets you jump; it is not saved with the Set ([Managing Files](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/)).
- **Crash recovery.** On relaunch Live offers to restore from an undo file in its preferences folder. If you decline, the files go to `~/Library/Preferences/Ableton/Live x.x.x/Crash/`; to recover manually, quit Live, strip the date from the three items (BaseFiles, CrashRecoveryInfo.cfg, Undo), move them into the parent folder, replace, relaunch; the same Live version must do it. Recordings may survive in temporary Projects ([Recovering a Set](https://help.ableton.com/hc/en-us/articles/115001878844)). Hold Option at launch to skip plug-in scanning when hunting a crash ([Troubleshooting](https://help.ableton.com/hc/en-us/articles/209773265)).
- **Habits.** Save when you finish a section, before bulk edits, before heavy routing changes, and before running anything that deletes. Save As to a numbered name at milestones. Move recordings out of the temporary folder by saving early.

> **For an agent**
> - The first thing to establish is whether the Set is saved: `get_status` shows `set.saved`. The NOVA Set was still unsaved earlier on 2026-10-08, so its takes sat in `~/Music/AbletonMCP/Ears/untitled/` until the first save; by the pause it was `NOVA v1.als` with unsaved changes and takes under `NOVA v1 Project/ears/takes/` (`docs/handoff/2026-10-08-nova-v2-paused.md`). `save_set(path)` needs macOS UI automation (see `get_status` capabilities); otherwise ask Fred for Cmd+S.
> - **Delete structural objects (tracks, returns, scenes) one per call.** A batch that deleted three tracks, a return and two scenes in one tick crashed Live 12.4.6 (`std::out_of_range` in the scene bookkeeping, 2026-10-07; `docs/DEVELOPING.md`). Live's own release notes show a history of crashes around scenes and track deletion.
> - **Recovery re-arms tracks:** crash recovery replays the undo history, which does not record arm changes, so tracks created by `create_track` came back armed. After recovery, `get_song_overview`, diff against a take snapshot, and disarm.
> - `undo(steps)` shares Live's history with Fred's own edits. Do not undo blindly after he has worked; revert your own change explicitly.
> - Crash forensics: `uv run ableton-mcp journal --crash` finds the last command without an end.

---

## 10. Shortcuts to hand to Fred

| Action | Mac |
|---|---|
| Save, Save As | Cmd+S, Cmd+Shift+S |
| Bounce to New Track | Cmd+B |
| Paste Bounced Audio | Cmd+Opt+V |
| Freeze / Unfreeze | Cmd+Opt+Shift+F |
| Consolidate | Cmd+J |
| Group tracks / devices | Cmd+G (Ungroup Cmd+Shift+G) |
| Rename | Cmd+R |
| Device A/B Compare, Hot-Swap, Deactivate | P, Q, 0 |
| Similarity Search | Cmd+Shift+F |
| Undo History | Cmd+Opt+Z |
| Session / Arrangement | Tab |
| Mixer, Clip View, Device View | Cmd+Opt+M, Cmd+Opt+3, Cmd+Opt+4 |
| Automation mode, Draw mode | A, B |
| Fold to Scale, Highlight Scale | G, K |
| Show/Hide take lanes | Cmd+Opt+U |
| Copy Time (12.4) | Cmd+Shift+C |
| Export Audio/Video | Cmd+Shift+R |

Sources: [Live shortcuts](https://www.ableton.com/en/live-manual/12/live-keyboard-shortcuts/), [new Live 12 shortcuts](https://help.ableton.com/hc/en-us/articles/12840878679452), [Editing MIDI](https://www.ableton.com/en/live-manual/12/editing-midi/), [Comping](https://www.ableton.com/en/live-manual/12/comping/).

---

## 11. For an agent: workflows mapped to tools

### 11.1 Capability matrix

| Workflow step | Tool(s) | Gap, so ask Fred |
|---|---|---|
| Tracks, scenes, clips, notes, drum patterns | `create_track`, `create_scene`, `create_clip`, `write_notes`, `write_drum_pattern`, `duplicate_track`, `duplicate_scene` | none |
| Submix | `create_bus` | real Group Track, folding, Bounce Group |
| Returns and sends | `create_track(kind="return")`, `set_mixer(sends=)` | Pre/Post toggle |
| Routing, monitoring | `set_track(input, input_channel, output, monitoring)`, `get_routing_options` | none (mind tick timing) |
| Sidechain | `set_sidechain` (Compressor only) | source routing on Glue Compressor, Gate, Auto Filter, Roar and the rest |
| Rack chains, macros, variations | `set_chain`, `device_action`, `set_device_parameters`, `get_devices` | macro mapping, zones, fade ranges |
| Presets and kits | `search_browser`, `load_from_browser` | Similarity Search, tag editing |
| Automation | `write_automation`, `get_automation` (Session clip envelopes; Arrangement clips only if they already carry the envelope) | Arrangement lanes, new envelopes on Arrangement clips, modulation envelopes, unlinked envelopes, Max mapping |
| Launch and follow actions | `set_clip(launch_mode, launch_quantization, legato)` | follow actions |
| Groove, swing | `get_grooves`, `set_groove`, `set_song(swing, groove_amount)`, `set_clip(groove)` | removing a clip's groove |
| Scale, tuning | `set_song(key, scale, scale_mode)`; `lom_get("live_set tuning_system")` | per-clip scale (the API has the song scale only), loading a tuning file |
| MIDI Tools (Transformations, Generators) | `transform_notes`, `write_notes`, `write_drum_pattern`, `music_theory` do the same jobs by hand | the Live 12 tool panels themselves (no API members) |
| Freeze, Bounce Track in Place / to New Track, Consolidate (Live's UI commands; the `bounce` tool is a WAV render, not one of them) | none | Fred runs them (Section 5) |
| Section the timeline | `arrange_from_scenes`, `create_locator`, `clear_arrangement`, `get_arrangement` | tempo/time-signature markers |
| Save, Collect All and Save | `save_set` (UI automation) | Collect All and Save, buffer, sample rate |
| Anything else | `lom_describe`, `lom_get`, `lom_set`, `lom_call` | risk: no guard rails |

### 11.2 The change protocol (one change, A/B, human decides)

1. **Snapshot.** `get_track` and `get_devices`/`get_device` for the track; for stems, remember `takes` holds snapshots (`takes(action="restore", dry_run=True)` previews a rollback).
2. **Twin.** `duplicate_track("pad", name="pad (approved)")`, then `set_mixer("pad (approved)", mute=True)`. The copy lands right after the original and is selected; indices shift, so address by name. A twin of a sidechain *source* does not take over the key; keep the original as the source.
3. **One change** on the working track: one device, one chain, one macro. Load candidate sounds onto a **new track**, not onto the approved one (`load_from_browser` replaces the instrument).
4. **Label.** `show_message("A = approved pad, B = wider pad")` and say the same in chat; say what to listen for and in what order.
5. **Level-match.** The louder option wins A/B. Measure both (`capture` or `meter`) and trim the candidate with `set_mixer(volume_db=)` until they agree within 0.2 LU (0.3 LU at most; synth stems differ by up to about 0.26 LU between identical captures, so measure each side more than once).
6. **Let him judge.** Exactly one of the pair unmuted at a time (`get_mixer` to confirm); toggle on request, or use device A/B (P).
7. **Keep or revert.** If kept, delete the twin later, one deletion per call. If not, restore the parameters you changed (not a blind `undo`).

### 11.3 Recipes

```
# Sketch to arrangement
create_scene(name="Intro"); create_clip("padA", slot=0, length="8 bars", notes=...)
write_automation("padA", "volume", slot=0, shape={"type": "ramp", "from": -24, "to": -6})
fire_scene("Intro")                  # audition, then get_meters
arrange_from_scenes([{"scene": "Intro", "bars": 8}, {"scene": "Verse", "bars": 16}], locators=True)
get_arrangement()                    # verify clips, extents, envelopes

# Return + sidechain
create_track("return", name="Plate", device="Reverb")
set_mixer("padA", sends={"A": -14})
set_sidechain("bassA", "kick", threshold_db=-30, ratio=4, release_ms=150)

# Facts through the escape hatch (read first)
lom_get("live_set", ["tempo", "swing_amount", "groove_amount", "scale_mode", "root_note", "scale_name"])
lom_get("live_set tuning_system")
lom_get("live_app", ["average_process_usage", "peak_process_usage"])
lom_get("live_set tracks 3", ["is_frozen", "can_be_frozen", "performance_impact"])
```

`lom_set` and `lom_call` can do anything, including crash Live. Use curated tools first, try escape-hatch writes on a scratch track in a **saved** Set, and make one structural change per call.

### 11.4 What to measure

| Change | Check | A bad result looks like |
|---|---|---|
| New route or bus | `get_routing_options`, `get_meters` while playing, then `capture` | Bus meter silent; source still reaching Main (doubled level, up to +6 dB); `audio.sum_null` below the 40 dB the spec requires |
| Sidechain | Ducked part's loudness dips at the trigger's onsets in `capture(mode="solo")` | Dips at every hat as well as the kick; no dip; level not recovered before the next hit; more than about 6 dB of reduction unless a pump is the point |
| Rack change | `get_device` read-back (chains, macro values, variation count), `get_meters` | Macro moved but nothing audible changes (unmapped); a level step above 0.2 LU the human did not ask for when a chain switches |
| Commit by Fred | `get_track` (frozen flag, devices on), sidechain and modulated tracks still working, `get_clip` warping off, `compare("latest", "best")` | Loudness off the live track by more than the repo's noise floor (about 0.3 LU per part); warping on; a device disabled after a freeze |
| Automation | `get_automation` samples; no re-enable warning | Samples flat across the clip; overridden control so the move never plays |
| CPU | `get_status.live.cpu` before and during a capture | Above 75% (the engines warn), or a dropout reported by `analyze_audio` |

### 11.5 Stop and ask Fred when

- You would replace, delete or re-route anything he approved (instruments, presets, buses, sends).
- A choice is about taste: which preset, how wide, how dirty. Offer a short, labelled, level-matched A/B.
- The step is UI-only: macro mapping, zones, Pre/Post, follow actions, tuning, any bounce, freeze or consolidate, buffer size, sample rate.
- A change touches every stem at once (master chain, global groove, tempo, key, tuning, sample rate).
- The Set is unsaved and you are about to restructure it.

---

## Sources

Ableton Live 12 manual: [Live Concepts](https://www.ableton.com/en/live-manual/12/live-concepts/) · [Managing Files and Sets](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/) · [Arrangement View](https://www.ableton.com/en/live-manual/12/arrangement-view/) · [Session View](https://www.ableton.com/en/live-manual/12/session-view/) · [Editing MIDI](https://www.ableton.com/en/live-manual/12/editing-midi/) · [MIDI Tools](https://www.ableton.com/en/live-manual/12/midi-tools/) · [Using Grooves](https://www.ableton.com/en/live-manual/12/using-grooves/) · [Using Tuning Systems](https://www.ableton.com/en/live-manual/12/using-tuning-systems/) · [Launching Clips](https://www.ableton.com/en/live-manual/12/launching-clips/) · [Routing and I/O](https://www.ableton.com/en/live-manual/12/routing-and-i-o/) · [Mixing](https://www.ableton.com/en/live-manual/12/mixing/) · [Recording New Clips](https://www.ableton.com/en/live-manual/12/recording-new-clips/) · [Bounce to Audio](https://www.ableton.com/en/live-manual/12/bounce-to-audio/) · [Comping](https://www.ableton.com/en/live-manual/12/comping/) · [Instrument, Drum and Effect Racks](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/) · [Automation](https://www.ableton.com/en/live-manual/12/automation/) · [Clip Envelopes](https://www.ableton.com/en/live-manual/12/clip-envelopes/) · [Max for Live Devices](https://www.ableton.com/en/live-manual/12/max-for-live-devices/) · [Live Audio Effect Reference](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/) · [Live MIDI Effect Reference](https://www.ableton.com/en/live-manual/12/live-midi-effect-reference/) · [Live Instrument Reference](https://www.ableton.com/en/live-manual/12/live-instrument-reference/) · [Working with Instruments and Effects](https://www.ableton.com/en/live-manual/12/working-with-instruments-and-effects/) · [Working with the Browser](https://www.ableton.com/en/live-manual/12/working-with-the-browser/) · [Computer Audio Resources and Strategies](https://www.ableton.com/en/live-manual/12/computer-audio-resources-and-strategies/) · [Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/) · [Live Keyboard Shortcuts](https://www.ableton.com/en/live-manual/12/live-keyboard-shortcuts/)

Ableton release notes and pages: [Live 12 release notes](https://www.ableton.com/en/release-notes/live-12/) (read in full locally) · [Live 12 features](https://www.ableton.com/en/live/all-new-features/) · [Live 12.4 post](https://www.ableton.com/en/blog/live-12-4-is-out-now/) · [Granulator III pack](https://www.ableton.com/en/packs/granulator-iii/) · interviews [DATSUNN](https://www.ableton.com/en/blog/DATSUNN-Habits-That-Make-Better-Beats/), [Lynyn](https://www.ableton.com/en/blog/lynyn-trace-elements/)

Ableton Help Center (fetched through its public article API): [Committing Audio in Live](https://help.ableton.com/hc/en-us/articles/22998838817820) · [Bounce Tracks to Audio FAQ](https://help.ableton.com/hc/en-us/articles/22999165562396) · [How Latency Works](https://help.ableton.com/hc/en-us/articles/360010545559) · [Delay Compensation FAQ](https://help.ableton.com/hc/en-us/articles/209072409) · [Reduced Latency When Monitoring](https://help.ableton.com/hc/en-us/articles/209072249) · [Live's CPU Meter](https://help.ableton.com/hc/en-us/articles/360019151379) · [Multi-core performance](https://help.ableton.com/hc/en-us/articles/209067649) · [Wavetable CPU](https://help.ableton.com/hc/en-us/articles/360000036930) · [CPU-intensive devices](https://help.ableton.com/hc/en-us/articles/12911009486108) · [Reducing CPU on macOS](https://help.ableton.com/hc/en-us/articles/5266527910812) · [Crackles and dropouts](https://help.ableton.com/hc/en-us/articles/209070329) · [Recovering a Set](https://help.ableton.com/hc/en-us/articles/115001878844) · [Troubleshooting a crash](https://help.ableton.com/hc/en-us/articles/209773265) · [Default Set and Templates](https://help.ableton.com/hc/en-us/articles/209067189) · [Backup Sets](https://help.ableton.com/hc/en-us/articles/360000377870) · [Collect All and Save](https://help.ableton.com/hc/en-us/articles/209775645) · [Unique Projects](https://help.ableton.com/hc/en-us/articles/360002864179) · [Automation and Modulation](https://help.ableton.com/hc/en-us/articles/209070629) · [Follow Actions in Live 11](https://help.ableton.com/hc/en-us/articles/360019101360) · [Scene Tempo](https://help.ableton.com/hc/en-us/articles/5595081962524) · [Monitoring FAQ](https://help.ableton.com/hc/en-us/articles/360006569179) · [Sidechaining a plug-in](https://help.ableton.com/hc/en-us/articles/209775325) · [Real-time rendering](https://help.ableton.com/hc/en-us/articles/209067709) · [Recording Audio](https://help.ableton.com/hc/en-us/articles/7938193554460) · [New shortcuts in Live 12](https://help.ableton.com/hc/en-us/articles/12840878679452)

Educators and press: [Attack, six Bounce to New Track tricks](https://www.attackmagazine.com/technique/tutorials/six-bounce-to-new-track-tricks-to-try-in-live-12-2/) · [Attack, generative MIDI tools](https://www.attackmagazine.com/technique/tutorials/getting-started-with-ableton-lives-generative-midi-tools/) · [Attack, Wavetable modulation routings](https://www.attackmagazine.com/technique/tutorials/10-common-modulation-routings-using-abletons-wavetable/) · [EDMProd, resampling](https://www.edmprod.com/resampling/) · [EDMProd, sidechain](https://www.edmprod.com/sidechain-compression/) · [EDMProd, DAW templates](https://www.edmprod.com/daw-templates/) · [Audeobox, Ableton templates](https://www.audeobox.com/learn/ableton/ableton-templates-guide/) · [Lost Stories Academy, resampling](https://loststoriesacademy.com/blogs-and-tutorials/why-professional-producers-love-resampling) · [Wikipedia, Ableton Live](https://en.wikipedia.org/wiki/Ableton_Live) (12.0 date only)

This repo: `docs/TOOLS.md`, `docs/spikes.md`, `docs/DEVELOPING.md`, `docs/reference/live_api_12.4.6.md`, `.claude/skills/listening-loop/SKILL.md`, `ears/specs/nova.spec.json`, and the Remote Script handlers for `create_bus`, `fire_clip`, `get_status`, `get_track`.

Weak evidence: educator articles are marked as such where used. The buffer-size ranges, the template colour scheme, the Rack recipes, the ghost-kick release rule of thumb, the 6 dB ducking ceiling and the "stay under 60% CPU" figure are practitioner convention or my own, not Ableton numbers.

---

## Open questions / where sources disagree

1. **Freeze versus Bounce.** The Bounce to Audio chapter says Bounce supersedes "Freeze and Flatten Track", while the CPU chapter, the shortcut list and the Help Center still document plain Freeze/Unfreeze. The 12.2 release notes resolve it: only the combined Freeze-and-Flatten and Flatten commands were renamed. Treat Freeze as present.
2. **What Bounce to New Track does to the source.** The manual and release notes say the source clips or selection are muted; the Help Center says the original track and clips are deactivated. Either way they stop sounding. After a bounce, check `get_clip(...).muted` before assuming.
3. **Does bounce render faster than real time?** Not stated for bounce; the Help Center says export normally renders faster than real time and some external gear or plug-ins need real time. The MCP `bounce` tool is real time by design.
4. **Undo History persistence.** The managing-files chapter says it is not saved with the Set; crash recovery nevertheless restores from an undo file in preferences. Both are true: different mechanisms.
5. **Sample rate.** The Set runs at 44.1 kHz; delivery needs 48 kHz / 24-bit. Ableton advises choosing the rate before starting and not mixing rates; whether to switch now or resample on export is Fred's call and belongs in `07-mastering-and-loudness.md` and `10-game-audio-adaptive-music.md`.
6. **Adaptive stems and sidechain.** Ducking keyed from the kick and baked into the pad stem will still pump when the kick stem is not playing (lower tiers), and a bus compressor over several stems cannot be reproduced when stems join one by one. Not settled here; see `10-game-audio-adaptive-music.md`.
7. **Buffer sizes and CPU thresholds.** Ableton gives a method (raise the buffer until dropouts stop), not numbers; the 128 to 256 / 512 to 1024 split and the 60% target are convention.
8. **Similarity Search.** Ableton does not publish what it compares. Treat it as a shortlist generator only.
9. **Not verifiable from sources:** whether Looper's `export_to_clip_slot` is a practical in-Set resampling path from another track; whether chain-level taps show up in `get_routing_options` for Drum Racks; whether the Live API ever exposes the clip's modulation envelopes. Test on a scratch track in a saved Set before relying on any of them.
10. **Evidence gaps.** Ableton's blog and tutorial pages are mostly video teasers; several educator pages were unreachable (Isotonik, Gear4Music) or truncated (MusicRadar). Pro-interview coverage is thin: DATSUNN and Lynyn only. The mix and arrangement digests have the deeper practitioner evidence.
