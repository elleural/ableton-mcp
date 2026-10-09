# Arrangement and composition for electronic music in Live 12

Digest 08 of the production set, for AI agents that compose in Ableton Live 12.4.6 Suite through AbletonMCP and cannot hear. Deeper treatments live elsewhere: Live workflow, scenes and racks in [01-live-workflow.md](01-live-workflow.md), sounds in [03-sound-design-recipes.md](03-sound-design-recipes.md), kick, bass and tuning in [04-drums-and-low-end.md](04-drums-and-low-end.md), EQ and saturation in [06-mixing.md](06-mixing.md), stems and loops in [10-game-audio-adaptive-music.md](10-game-audio-adaptive-music.md), A/B and measuring in [11-listening-without-ears.md](11-listening-without-ears.md), device parameters in [12-live-devices-reference.md](12-live-devices-reference.md), genre idioms (NIN, Boys Noize, EBM) in [09-industrial-ebm-techno-nin.md](09-industrial-ebm-techno-nin.md).

Evidence labels used below: **[manual]** Ableton documentation; **[article]** practitioner article or book chapter; **[paper]** peer-reviewed; **[derived]** my own arithmetic or simulation, reproducible with the snippets in this file; **[weak]** seen only in a search summary or forum, verify before relying on it.

## If you remember five things

1. **Arrange by subtraction, in 4/8/16-bar blocks, changing one thing at a time.** Sources agree on the phrase grid, on adding one layer every 4 to 8 bars, and on making contrast by removing things (bass, kick, a percussion layer) before any riser. Ableton's own advice is to fill the timeline first and then sculpt it down, which suits `arrange_from_scenes` well.
2. **The low register holds one note at a time.** Below about C2 (MIDI 48, 131 Hz in Live's naming) write only roots, fifths and octaves; put major thirds from about E2 (165 Hz) and minor thirds and seconds higher still, or spread thirds as tenths. The lowest sounding note of the whole mix must be the chord root (or the pedal note). Sections 2.5 and 2.8 give the derived tables and a checker you can run.
3. **"Wrong notes" are usually not wrong pitches.** They are semitone cross-relations (G against G#), thirds or seconds in the sub (beating and roughness), a bass voice that is not the root (voice-led pads, `drop2`, `drop3` and inversions from `music_theory` can all put a third or fifth at the bottom), hidden layers (instrument sub-octaves, MIDI effects, detune, a loaded tuning system), and distortion on full chords (intermodulation). Fix them with voicing and register, not EQ.
4. **Felt pace = tempo x onset rate x where the backbeat sits.** Half-time halves the felt pace at the same BPM, medium syncopation grooves best, and swing of about 54 to 66 percent moves the off-16th by 9 to 36 ms at 140 BPM. Change one pace lever per audition.
5. **Live 12's MIDI Tools, per-clip scale and Follow Actions are not in the Live API** (checked in this repo's 12.4.6 object-model dump). Recreate their logic with `music_theory` plus `write_notes`/`edit_notes`/`transform_notes`, or insert the MIDI-effect devices (Arpeggiator, Chord, Scale, Random). Present choices to Fred labelled, one variable at a time, loudness-matched, and never replace a sound he already approved (Section 6).

## 0. Cheat sheet

### Pitch, frequency, time

Live names notes with C3 = 60 and A3 = 440 Hz, one octave below scientific pitch notation (Live C3 is scientific C4); this is the convention of every pitch argument in `docs/TOOLS.md`. Frequency is 440 x 2^((midi - 69) / 12). `music_theory(operation="notes", notes=["A0", 33, "E1"])` returns MIDI number, name and Hz.

| Live name | E0 | G0 | A0 | C1 | E1 | A1 | C2 | E2 | A2 | C3 | A3 | C5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MIDI | 28 | 31 | 33 | 36 | 40 | 45 | 48 | 52 | 57 | 60 | 69 | 84 |
| Hz | 41.2 | 49.0 | 55.0 | 65.4 | 82.4 | 110 | 130.8 | 164.8 | 220 | 261.6 | 440 | 1046 |

Roots for the project's chords in the bass register: Am = A0 (33, 55 Hz), Dm = D1 (38, 73 Hz), G = G0 (31, 49 Hz) or G1 (43, 98 Hz), E = E1 (40, 82 Hz), F = F1 (41, 87 Hz), C = C1 (36, 65 Hz). The producer's references keep one low root at 41 to 49 Hz, which is E0 to G0.

Time: a 4/4 bar lasts 240 / BPM seconds, so 8 bars = 19.2 s at 100 BPM, 15.0 s at 128, 13.7 s at 140, 10.7 s at 180. Onsets per second = BPM / 60 x onsets per beat: 16th hats give 6.7 per second at 100 BPM, 9.3 at 140, 12 at 180.

### Which tool for what

| Job | Tool |
| --- | --- |
| Scales, chords, progressions, voicings | `music_theory` (operations `scale`, `chord`, `progression`, `notes`, `list`) |
| Write and edit notes | `write_notes` (modes `add`, `replace`, `replace_range`; `{"chord": "Am7"}` or `"pitches": [...]`), `create_clip(notes=...)`, `edit_notes` (by `note_id`), `delete_notes` |
| Bulk edits | `transform_notes`: `transpose` (semitones, or scale-degree `steps`), `quantize` (with `swing`), `humanize`, `velocity`, `legato`, `reverse`, `stretch`, `shift` |
| Drums | `write_drum_pattern` (step strings, `swing` 0..1), `create_clip(pattern=...)` |
| Check notes (no audio, under a second) | `analyze_notes`: in key, chord tones, semitone clashes between stems, shared stem, loop length, grid, lead rests; reports density, kick pattern, motif |
| Structure | `create_scene`/`set_scene` (per-scene tempo), `duplicate_scene`, `arrange_from_scenes`, `create_locator`, `write_automation` |
| Check audio | `bounce` then `analyze_audio(sections="locators")`; `capture`, `compare`, `takes`; `meter` |

## 1. Arrangement

### 1.1 The grid: 4, 8, 16, 32 bars

- Sections are built from blocks of 4, 8 or 16 bars ([Learning Music: song structure](https://learningmusic.ableton.com/song-structure/song-structure.html) [manual]). Treat 8 and 16 as starting points, not law ([Mixed In Key](https://mixedinkey.com/captain-plugins/wiki/how-to-arrange-a-dance-music-track/) [article]); elements usually change every 4 or 8 bars and bigger moves land on 16 or 32.
- Real tracks, as read by [Attack Magazine](https://www.attackmagazine.com/technique/deconstructed/joey-beltram-energy-flash/) [article]: Beltram's "Energy Flash" enters drums at bar 1, rim shot 5, clap 9, pitched clap 13, crash 17, bassline 25, tambourine 33, with at most 8 to 10 layers at its densest. [Jeff Mills' "The Bells"](https://www.attackmagazine.com/technique/deconstructed/jeff-mills-the-bells/) brings hats in at bar 8, rides and claps at 17, bassline at 65 and never has more than a few musical elements at once. [Âme's "Rej"](https://www.attackmagazine.com/technique/deconstructed/ame-rej/) uses 16-bar loops across 18 sections, a first synth at bar 49 and a stripped-down break at bar 81. [Drexciya's "Black Sea"](https://www.attackmagazine.com/technique/deconstructed/drexciya-black-sea/) enters its kick at bar 6, hats at 34, claps at 45 and chords at 49, and does not follow the 4/8-bar habit.
- Minimal and dub-leaning styles often skip a big climax and create tension from small texture changes ([Making Music: Dramatic Arc](https://makingmusic.ableton.com/dramatic-arc) [article]).

### 1.2 The energy curve

Ableton's model is a dramatic arc: exposition, rising action, climax (often a sudden jump in textural density), falling action, resolution ([Making Music](https://makingmusic.ableton.com/dramatic-arc)). For an agent, make the curve concrete as three measurable quantities per section: the number of active layers (`get_arrangement`), onsets per second (from `get_notes` or the `analyze_notes` density) and short-term loudness. `analyze_audio(path, sections="locators")` gives each section its integrated, short-term max and momentary max LUFS, sample peak and RMS, plus a loudness curve for the whole file (checked against `MCP_Server/audio/analysis.py`). It reports no onset rate, tempo or key per section (`meter(source="live")` and the take reports carry those), so count layers and onsets from the arrangement and the notes.

Illustrative plan for a fixed-length club track (my synthesis of Attack's "intro, breakdown, drop, breakdown, drop, cool-down, outro" template, the breakdown recipe and DJ-friendly intro advice; not a rule):

| Section | Bars | Layers | Move at the end |
| --- | --- | --- | --- |
| Intro | 16-32 | kick, hats/perc, one texture; no bass, no melody | add one layer every 8 bars; open a filter |
| Groove | 32 | + bass; pad or arp enters at the midpoint | variation at bar 16; 2-beat gap at the end |
| Breakdown | 24-32 (3 x 8) | strip kick, bass, hats; keep harmony as a filtered pad or low-cut bass; add atmosphere | riser and snare roll in the last 8; cut everything 2 beats early |
| Peak | 32 | everything, hook or lead | mutate one part every 8 bars; one unique event |
| Development | 16 | pad + arp + perc; shift mode or chord colour | rebuild |
| Peak 2 / cool-down | 32 | one new element, or the hook an octave up | strip to rhythm |
| Outro | 16-32 | kick, hats, one texture | end |

At 128 BPM that is about 192 bars = 6:00. For the adaptive game stems the same idea runs vertically (pad + arp, then + bass, + kick, + perc, + lead) instead of left to right; see [10-game-audio-adaptive-music.md](10-game-audio-adaptive-music.md).

### 1.3 How many things at once, and who owns which register

I found no study that gives a magic number, but the practitioner evidence points one way. Starting sparse leaves headroom to build ([Mike Senior, SOS Mix Rescue](https://www.soundonsound.com/node/4908260)); fewer simultaneous parts means each can sit louder in the same headroom ([Paul White, SOS](https://www.soundonsound.com/node/4904703)); twenty stacked pads work in the studio and fail on a dance floor ([Gearnews](https://www.gearnews.com/arrangement-techniques-for-electronic-music/)). Working rule [derived from those]: one hook idea at a time (lead and arp alternate rather than overlap), one sustained harmonic bed, one owner of the low end per beat, and no two parts with the same job in the same register.

Starting slots (note ranges are what you write, in Live names; fundamentals only, harmonics reach higher) [derived from the register tables in 2.5]:

| Role | Written range | Fundamentals | Rules |
| --- | --- | --- | --- |
| Kick (tuned) | one pitch, E0-A0 (28-33) | 41-55 Hz | tune to the root or fifth; see [04](04-drums-and-low-end.md) |
| Sub and bass | E0-C2 (28-48), one note at a time | 41-131 Hz | roots, fifths, octaves; owns everything below about 100 Hz |
| Pad, lowest voice | the chord root only (or the pedal note) | 41-82 Hz | single pitch; this is the "low root" of the producer's references |
| Pad, chord body | C2-C4 (48-72) | 131-523 Hz | major thirds from E2 up, minor thirds and seconds higher still (close pairs), or thirds as tenths; compact on top |
| Arp, stabs | C3-C5 (60-84) | 262-1047 Hz | above the pad's thirds, or in a different rhythmic slot |
| Lead | G3-G5 (67-91) | 392-1568 Hz | alternates with the arp; owns the 1-4 kHz presence region |

### 1.4 Tension and release devices

| Device | What it does | Live route | Source |
| --- | --- | --- | --- |
| Subtraction | mute the bass, drop a percussion layer or shorten the hook before adding any riser | delete or mute the part's clip in that section's scene; `clear_arrangement(tracks=[...], start, end)` | [Mixed In Key](https://mixedinkey.com/captain-plugins/wiki/how-to-arrange-a-dance-music-track/) |
| Silence gap | cut everything about 2 beats early so the return hits; a whole silent bar for major changes | `clear_arrangement(all_tracks=True, start="16.3.1", end="17.1.1")` empties the last 2 beats of bar 16 | [Attack: breakdown recipe](https://www.attackmagazine.com/technique/the-breakdown/what-is-the-recipe-for-an-effective-breakdown/), [Gearnews](https://www.gearnews.com/arrangement-techniques-for-electronic-music/) |
| Filter sweep | high-pass breakdown material, then sweep it away before the drop; low-pass automation to evolve a 4-bar loop | Auto Filter `Frequency` via `write_automation` (Live 12.2 added a DJ filter type, `Filter Type` DJ) | Attack, Gearnews, [release notes](https://www.ableton.com/en/release-notes/live-12/) |
| Riser and faller | layer a riser with the sweep; white-noise faller on the drop | Build and Drop pack racks ([pack](https://www.ableton.com/en/packs/build-and-drop/)): `search_browser`, `load_from_browser`, one long note | Attack |
| Fill, snare roll | denser and louder toward the end of the breakdown | `write_drum_pattern(steps_per_beat=8 or 12, mode="add")` on the last 1-2 bars; `transform_notes(operation="velocity", ...)` ramp | Attack |
| Layer-by-layer entry | add percussion one piece at a time every 4-8 bars; Mills and Beltram mute and unmute loops instead of writing fills | stagger clips across scenes | [Attack](https://www.attackmagazine.com/technique/deconstructed/joey-beltram-energy-flash/) |
| Harmonic suspension | hold the dominant (E with G# in A minor) or a sus chord over the last bar; tonic pedal under moving chords | `write_notes` | theory, see 2.2 |
| Gain, delay and reverb throws | Utility `Output` (gain) fades; echo or reverb on one hit | `write_automation` | [Production Music Live](https://www.productionmusiclive.com/blogs/news/how-to-arrange-a-track-10-arrangement-tips-for-electronic-music) |
| Unique event | a one-off sound, phrase variation or processing gesture; use sparingly or it becomes predictable | one clip, one place | [Making Music: Unique Events](https://makingmusic.ableton.com/unique-events) |

Breakdowns run 24 to 32 bars in roughly three 8-bar steps; the usual order is to strip kick, bass and hats first while keeping the rhythm alive with claps or snaps, keep the harmony in a filtered form, then bring in atmosphere that starts quiet ([Attack](https://www.attackmagazine.com/technique/the-breakdown/what-is-the-recipe-for-an-effective-breakdown/)).

### 1.5 Repetition with variation

- **Change one parameter every 4 or 8 bars.** Hypnotic genres run on small changes over time, not constant change ([Gearnews](https://www.gearnews.com/arrangement-techniques-for-electronic-music/), [Production Music Live](https://www.productionmusiclive.com/blogs/news/how-to-arrange-a-track-10-arrangement-tips-for-electronic-music)); Drexciya vary hat decay, filter cutoff and pitch by hand while the drum pattern stays put. Keep an ostinato fixed while bass and accompaniment move; that is what glues sections together ([Attack: ostinatos](https://www.attackmagazine.com/technique/passing-notes/ostinatos-and-acid-house-riffs/)).
- **Mutation over generations** ([Making Music](https://makingmusic.ableton.com/creating-variation-2-mutation-over-generations)): duplicate a loop, make one change, duplicate that, make another, 8 or more times; never undo an earlier change. The result is a family of related clips to sequence.
- **Asynchronous loops** ([Making Music](https://makingmusic.ableton.com/asynchronous-or-polyrhythmic-loops)): a 4-step and a 5-step loop realign every 20 sixteenths; add a 3-step loop and the cycle is 60.
- **Variation menu** an agent can apply through `transform_notes`/`edit_notes`: shift accents (`velocity`), drop 1 or 2 notes, displace one note by an octave, `shift` by one 16th, stretch a phrase, mute a layer for 1 to 2 bars, change only the last bar's chord (a turnaround such as Dm to E), swap the hat pattern.

### 1.6 From an 8-bar loop to a full track

1. Get the loop right first: every part clean in `analyze_notes()`, one scene row.
2. Mark the plan: `create_scene(name="Intro")`, `Groove`, `Breakdown`, `Peak`, `Outro`, or `duplicate_scene` the loop scene once per section.
3. Subtract in each scene: `delete_clip` the parts that should not play there (ask first if the clips are Fred's). Fill first, remove after, as in [Making Music: Arranging as a Subtractive Process](https://makingmusic.ableton.com/arranging-as-a-subtractive-process).
4. Write automation (filter opens, riser, gain) into the Session clips now; `arrange_from_scenes` copies clips, so later edits need a re-run with `clear=True`.
5. `arrange_from_scenes(sections=[{"scene": "Intro", "bars": 16}, {"scene": "Groove", "bars": 32}, ...], locators=True)`, then `get_arrangement`.
6. For any section longer than 16 bars, make a B version of one or two parts (mutation) and alternate every 8 bars.
7. Add transitions as separate FX clips (2 to 4 bars) at section ends, and the 2-beat silence gap before the biggest entry.

> **For an agent: arrangement**
> - After `bounce`, poll `get_bounce_status(wait=50)` until it is done, then run `analyze_audio(path, sections="locators")`. Check direction, not magnitude: the breakdown has fewer layers and a lower note-onset rate (`get_arrangement`, `get_notes`) than the groove before it; the peak after a breakdown is at least as loud (short-term max per section) as the previous peak; the outro ends below the groove. A breakdown less than a couple of LU quieter than its neighbours is probably not reading as a breakdown (heuristic [derived]; ask Fred).
> - Flag any part whose 8-bar blocks are note-for-note identical for more than 4 blocks in a row (compare `get_notes` output).
> - `bounce` and `capture` run in real time; a 192-bar track at 128 BPM takes about 6 minutes. In a set that follows a listening-loop spec (NOVA's track and scene names), `capture(bars=...)` is the quick check; elsewhere bounce a short range.
> - Do not delete or overwrite the producer's clips; add scenes and tracks, name them, and keep the old version muted.

## 2. Harmony and voicing for dark electronic music

### 2.1 Minor modes

Interval patterns from [Learning Music: Modes](https://learningmusic.ableton.com/advanced-topics/modes.html) [manual]; characterisation from [Ethan Hein](https://ethanhein.substack.com/p/why-are-there-so-many-minor-scales), [Composer Code](https://composercode.com/the-dorian-mode-darkness-with-a-hint-of-light/), [Flat](https://blog.flat.io/phrygian-mode-explained/) and [Fachords](https://www.fachords.com/phrygian-scale/) [article]; note names computed from Live's scale table.

| Live scale name | Degrees | In A | Character | Triads in A |
| --- | --- | --- | --- | --- |
| Minor (Aeolian) | 1 2 b3 4 5 b6 b7 | A B C D E F G | the default dark; no leading tone, so the V chord is minor unless borrowed | Am Bdim C Dm Em F G |
| Dorian | 1 2 b3 4 5 6 b7 | A B C D E F# G | dark with a hint of light; major IV chord (D) | Am Bm C D Em F#dim G |
| Phrygian | 1 b2 b3 4 5 b6 b7 | A Bb C D E F G | darkest usable minor; the b2 leans on the tonic (Am to Bb vamp); avoid the diminished v | Am Bb C Dm Edim F Gm |
| Harmonic Minor | 1 2 b3 4 5 b6 7 | A B C D E F G# | raised 7th gives a major V (E or E7) and a strong pull to Am; the F to G# step sounds ominous | Am Bdim C+ Dm E F G#dim |
| Phrygian Dominant | 1 b2 3 4 5 b6 b7 | A Bb C# D E F G | b2 plus a major third; tense and "Spanish" | - |

The project's own progressions mix Aeolian chords with a harmonic-minor V: A is Am Am Dm Dm, B is Am F Dm E, C is Am Dm G E, D is Am F C G (`ears/specs/nova.spec.json`). The G natural of the G chord and the G# of the E chord are a semitone apart, so never let both sound at once (Section 2.7).

### 2.2 Static harmony, pedals and drones

- **Pedal point.** A held bass note (usually tonic or dominant) under changing chords; dissonance against it is the tension and the return of a matching chord is the release ([Wikipedia: Pedal point](https://en.wikipedia.org/wiki/Pedal_point) [article]). With a tonic pedal the "lowest note is the root" test becomes "lowest note is the pedal".
- **Vamps and loops.** Two-chord moves (Am to Bb Phrygian, Am to G or F Aeolian) or the four-chord loops above, one chord per 1 to 2 bars.
- **Stabs can leave the key.** Parallel chord stabs shift one shape up and down regardless of scale ([Attack](https://www.attackmagazine.com/technique/tutorials/the-theory-of-techno-parallel-chord-stabs/) [article]). In this project that would trip `notes.in_key`, so keep parallel moves inside A minor (plus G# over E) unless Fred wants otherwise.
- **Colour without clash.** Adding the 4th/11th between chord tones (F between Eb and G in Cm7) gives a dark, blurred stab ([Attack](https://www.attackmagazine.com/technique/passing-notes/levelling-up-your-chord-stabs/)); it is a whole-step cluster, not a semitone one. 9ths add brightness.
- **Sus chords and root-fifth riffs** drop the third, so they fit major or minor surroundings. A two-note root-plus-fifth ostinato fits several chords because it never commits to a mode ([Attack](https://www.attackmagazine.com/technique/passing-notes/ostinatos-and-acid-house-riffs/)). One dub-techno stab recipe builds a minor triad from oscillators at +3 and +7 semitones over a sub-octave root ([Audiotent](https://www.audiotent.com/blogs/production-tips/dub-techno-chord-sound-design) [article]); the sub carries only the root.

### 2.3 Open fifths, power chords and distortion

A root-plus-fifth sits near a 3:2 ratio, so the sum and difference tones that distortion creates land close to the harmonics of the two notes; the difference tone is the root an octave down, which is why distorted guitars use power chords. Equal-tempered thirds produce a messier set of products ([Wikipedia: Power chord](https://en.wikipedia.org/wiki/Power_chord) [article]). Intermodulation is also audible at lower levels than harmonic distortion because the products are unrelated to the source ([Production Expert](https://www.production-expert.com/production-expert-1/intermodulation-distortion-the-audio-problem-you-may-be-overlooking) [article]).

Rule: distort or saturate one voice at a time, or distort only root + fifth (+ octave) and keep thirds and extensions in a clean layer. This is what made the saturated pad chords sound out of tune on 2026-10-08. Details of the devices are in [06-mixing.md](06-mixing.md) and [12-live-devices-reference.md](12-live-devices-reference.md).

### 2.4 Inversions, voice leading, close versus spread

- Keep common tones in the same voice, move other voices by the smallest step (no more than a third), let the bass leap by fourths and fifths while upper voices move by step ([Berklee Online](https://online.berklee.edu/takenote/voice-leading-paradigms-for-harmony-in-music-composition/), [Wikipedia: Voice leading](https://en.wikipedia.org/wiki/Voice_leading) [article]).
- Parallel motion is fine for stabs and power chords; classical rules against parallel fifths and octaves are about independent lines, not about fused riffs.
- Inversions keep the top note smooth and the chord compact, which also frees room for the bass ([Attack: Lessons from Disco](https://www.attackmagazine.com/technique/passing-notes/lessons-from-disco-chords/)).
- Contrary motion between bass and top line adds tension; Burial's "Archangel" has strings rising through the scale while the bass falls Ab-G-F ([Attack](https://www.attackmagazine.com/technique/passing-notes/contrary-motion/)).
- Wide at the bottom, close at the top. Close position low down sounds muddy and needs wider spacing ([Eerola and Lahdelma 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC9166839/) [paper]); an arranger's rule is that below the bass-clef middle line (Live D2, MIDI 50, 147 Hz) intervals should be consonant, ideally 10ths, 5ths or octaves ([Evan Rogers](https://www.evanrogersmusic.com/blog-contents/big-band-arranging/voicings-part2) [article]). Spreading a voicing across instruments, only the lowest two notes in octaves, is the orchestral trick ([Attack: Massive Chords](https://www.attackmagazine.com/technique/passing-notes/massive-chords-with-ensemble-voicings/)).

**What `music_theory` voicings do to the bottom note** (verified by running the repo's `MCP_Server/theory.py`; Live names, the `octave` argument is the octave of the root letter):

| Call | Pitches | Lowest note | Root at bottom? |
| --- | --- | --- | --- |
| `chord="Am", octave=2, voicing="close"` | A2 C3 E3 (57 60 64) | A2 | yes |
| `chord="Am", octave=2, voicing="open"` | A2 E3 C4 (57 64 72) | A2 | yes |
| `chord="Am", octave=3, voicing="spread"` | A2 C4 E4 (57 72 76) | A2 | yes, root dropped an octave |
| `chord="Am7", octave=3, voicing="drop2"` | E3 A3 C4 G4 (64 69 72 79) | E3 | no, the fifth |
| `chord="Am7", octave=3, voicing="drop3"` | C3 A3 E4 G4 (60 69 76 79) | C3 | no, the third |
| `chord="Am", octave=2, inversion=1` | C3 E3 A3 (60 64 69) | C3 | no, the third |
| `progression="i-iv-bVII-V", key="A minor", octave=2, voice_leading=True` | Am A2 C3 E3; Dm A2 D3 F3; G B2 D3 G3; E B2 E3 G#3 | A2, A2, B2, B2 | roots only in bar 1 |

So a voice-led or dropped pad is a mid-register tool. The root must come from a bass or a separate root-only layer (Section 2.8).

### 2.5 Low-interval limits

Why low intervals muddy: the ear resolves frequency coarsely at low pitch, so two close partials fall inside one auditory filter and beat or sound rough. In a study of four-note chords across seven registers (39 to 2637 Hz), roughness dominated at the low end and sharpness at the top, so the middle registers sounded most consonant ([Eerola and Lahdelma 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC9166839/) [paper]). Arrangers encode this as a "low interval limit" chart: the lowest place each interval can sit before it turns to mud ([Robin Hoffmann](https://www.robin-hoffmann.com/dfsb/low-interval-limits), [Sweetwater InSync](https://www.sweetwater.com/insync/low-interval-limit/)).

I could not open the Sweetwater chart (HTTP 403) or read the numbers on Hoffmann's page (an image). The right-hand column below is the classic chart as quoted in secondary summaries [weak]. The chart is printed in scientific pitch notation (m2 E3, M2 Eb3, m3 C3, M3 Bb2, P4 A2, tritone Bb2, P5 Bb1, sixths and sevenths F2); the column gives the same pitches in Live names, one octave lower (Live C3 = 60). The other two columns are mine [derived]: a dyad is rough when its two fundamentals are less than 0.5 ERB apart and clean from 1 ERB, with ERB(f) = 24.7 x (4.37 x f/1000 + 1) Hz at the lower note, f in Hz (Glasberg and Moore 1990, quoted on [Wikipedia](https://en.wikipedia.org/wiki/Equivalent_rectangular_bandwidth), which states the result's unit as kHz by mistake: its own 1983 polynomial gives 128 Hz at 1 kHz and this formula 133 Hz). Against the chart, the 1 ERB column is equal for the fourth (A1), two semitones higher for the fifth, six higher for the major third (E2 against A#1) and fifteen higher for the minor third (D#3 against C2), and lower for the tritone, sixths and sevenths; seconds reach 1 ERB only far above the bass (major second near 1.7 kHz, minor second never). The 0.5 ERB column is 6 to 15 semitones lower than the chart for thirds to fifths.

| Interval | Rough below (0.5 ERB), lower note | Clean from (1 ERB), lower note | Classic chart lower note [weak] |
| --- | --- | --- | --- |
| minor 2nd | D6 (98, 2.3 kHz) | never | E2 (52) |
| major 2nd | F#2 (54, 185 Hz) | never practical | D#2 (51) |
| minor 3rd | F#1 (42, 92 Hz) | D#3 (63, 311 Hz) | C2 (48) |
| major 3rd | B0 (35, 62 Hz) | E2 (52, 165 Hz) | A#1 (46) |
| perfect 4th | F#0 (30, 46 Hz) | A1 (45, 110 Hz) | A1 (45) |
| tritone | C#0 (25, 35 Hz) | E1 (40, 82 Hz) | A#1 (46) |
| perfect 5th | under 30 Hz | C1 (36, 65 Hz) | A#0 (34) |
| minor 6th | under 30 Hz | G#0 (32, 52 Hz) | F1 (41) |
| major 6th | under 30 Hz | F0 (29, 44 Hz) | F1 (41) |
| minor/major 7th | under 30 Hz | D0 / C0 (26 / 24) | F1 (41) |

**The practical rule used across this set** ([00-agent-playbook.md](00-agent-playbook.md) rule 4) is the simple, stricter form: below about 130 Hz (Live C2) only roots, fifths and octaves; major thirds from about 165 Hz (Live E2); minor thirds and seconds higher still; the lowest sounding note is the chord root. It is stricter than the classic chart for every third and second; the 1 ERB column and the three corrections below (saw-rich spectra, equal-tempered beating, wider Bark-style bandwidths) are the derived reasons. Where a table below allows more, the rule wins.

In practice (lower note of the pair):

| Zone | Lower note (MIDI, Hz) | What may sound together |
| --- | --- | --- |
| Sub | up to 39 (under 80 Hz) | root, fifth and octave only; the checker in 2.8 enforces this, and the same up to C2 |
| Bass | 40-47 (82-123 Hz) | the same, and by the practical rule nothing else sounds below C2. Derived headroom, not permission: a fourth from A1 (45); thirds and sixths only wide (a tenth or more) and only on dull timbres; no seconds or sevenths |
| Low-mid | 48-62 (131-294 Hz) | close major thirds clean from E2 (52), close minor thirds from D#3 (63); a close A minor triad at A2 (57) is acceptable (0.86 ERB); seconds only as colour from F#2 (54) |
| Upper | 63 and up (311 Hz and up) | all triads clean; seconds and sevenths are colour tones |

Three corrections to apply:

- **Timbre moves the floor.** Rich saw spectra interact on every partial. A Sethares/Plomp-Levelt roughness run [derived] with 8 harmonics shows a major third at C1 about three times as rough as at C3, and near-sine spectra about half to two-thirds as rough as saw-like ones at the same pitch. Use "clean from" for saw-rich pads and "rough below" for near-sine subs.
- **Equal temperament beats slowly in the bass, and wide spacing does not cure it.** Tempered thirds sit 14 to 16 cents from just (sixths likewise), so partial 5 against partial 4 (major third) beats at 2.2 Hz on a 55 Hz root and the minor third at 3.0 Hz, while a fifth beats at 0.19 Hz. A tenth beats at the same rate as a third because the same partial pair is involved. Slow pulsing like that reads as "out of tune" even when every note is right. Cures: fewer partials in the low layer (filter it, or use a sine or triangle), no thirds in low layers, or just tuning (5.2) [derived].
- **Models disagree on the bandwidth.** A Bark-style critical band is about 95 Hz wide at 100 Hz, far wider than the 35 Hz ERB used here ([Eerola and Lahdelma](https://pmc.ncbi.nlm.nih.gov/articles/PMC9166839/)). I used ERB because its 1 ERB column agrees with the practitioner chart for the fourth and nearly for the fifth (it is stricter for thirds); a half-critical-band criterion would forbid close minor triads below about C3, which is stricter than normal practice.

### 2.6 Sharing registers: pad, bass, arp

- The bass owns the lowest octave. The pad's lowest sounding note either doubles the bass root or sits above it; it never sounds a different pitch class below the bass unless you wrote a slash chord on purpose.
- Only the lowest octaves are doubled across instruments; do not stack the same full chord on three synths ([Attack: Massive Chords](https://www.attackmagazine.com/technique/passing-notes/massive-chords-with-ensemble-voicings/)).
- Arps live above the pad's thirds, leads above or alternating with the arp (Section 3), so each part has its own register and onset slot.
- High-passing is a mix tool, not a composition tool: in one Mix Rescue Mike Senior rolled most tracks off around 100 to 200 Hz ([SOS](https://www.soundonsound.com/node/4908260)), but a pad that is meant to carry a low root (the producer's references do) needs voicing discipline instead; see [06-mixing.md](06-mixing.md).
- In a stem ladder the lowest tier has no bass: in the NOVA tiers T1 = pad + arp, so the pad must carry each chord's root in T1 and must not clash when the bass joins at T2.
- Key choice sets how much weight the roots have. Moving the key down a few semitones gives deeper roots without an octave drop ([Attack: Choosing the Right Key for Bass Weight](https://www.attackmagazine.com/technique/passing-notes/choosing-keys-for-bass-weight/)); in A minor the tonic is A0 at 55 Hz, while E, F and G minor put it at 41, 44 and 49 Hz. The key belongs to the game spec and to Fred: raise it with him, do not change it yourself.

### 2.7 What "wrong notes" usually are

| What Fred hears | Usual cause | Numeric check | Fix |
| --- | --- | --- | --- |
| Low chord wobbles or sounds out of tune | thirds, sixths or sevenths below C2, or tempered thirds beating at 2 to 3 Hz | pair test in 2.8 on every part below C3 | spread to tenths, move up an octave, keep only roots and fifths below C2 |
| A sour note at a chord change | semitone cross-relation: G against G# of E, E against F in the F chord | `analyze_notes`: `notes.clash`, `notes.in_key`, `notes.shared_stem` | land on a chord tone, resolve by step, end the held note before the bar line |
| The bass seems to play the wrong note | lowest sounding pitch is the third or fifth (voice-led pad, `drop2`/`drop3`, inversion, or a sub layer that follows the pad's lowest note or folds notes into a window) | lowest pitch class per slice against the chord root | add a root-only low layer, re-voice, or write a slash chord deliberately |
| Notes you never wrote | instrument sub-oscillator or octave setting, Chord or Pitch MIDI effect, transpose on Drum Rack or Simpler, unison detune, a loaded tuning system | `get_devices`/`get_device`; `lom_get("live_set tuning_system")` | add the offsets to the sounding pitches, delete duplicate low layers |
| Mud, growl, "hollow" | close intervals under C2, too many partials, noise layers | pair test; third-octave balance 125-250 Hz in `analyze_audio` | open the voicing, fifths and octaves only low down |
| Saturated chord sounds out of tune | intermodulation between the chord's non-harmonic pairs | A/B one voice at a time | distort per voice or root + fifth only (2.3) |
| Detuned layers sound off at low notes | unison spread: +/-10 cents gives 0.64 Hz at a 55 Hz fundamental and 5 Hz on the 8th partial [derived] | read detune and unison parameters | no detune on low layers; widen by other means ([03](03-sound-design-recipes.md)) |
| A shared pad clashes with one progression | it holds a pitch a semitone from another progression's chord tone | `notes.shared_stem` | see 2.8 |

A reconstruction of the 2026-10-08 incident in numbers (the actual chords differed): a sub layer two octaves below an Am voiced A2 C3 E3 plays A0 C1 E1 (55, 65, 82 Hz). The A0 to C1 minor third is only 10.4 Hz apart, 0.34 ERB, under the 0.5 floor; the checker below flags it.

### 2.8 Worked example for this project, and the checker

Progression C in A minor, one chord per bar (`music_theory("progression", key="A minor", progression="i-iv-bVII-V", octave=2, voice_leading=True)`):

| Bar | Chord | Bass root | Voice-led pad | Pad bottom is the root? |
| --- | --- | --- | --- | --- |
| 1 | Am | A0 (33, 55 Hz) | A2 C3 E3 | yes |
| 2 | Dm | D1 (38, 73 Hz) | A2 D3 F3 | no (fifth) |
| 3 | G | G0 (31, 49 Hz) | B2 D3 G3 | no (third) |
| 4 | E | E1 (40, 82 Hz) | B2 E3 G#3 | no (fifth) |

The pad stays above 220 Hz, so there is no mud, but alone (tier T1) it plays chords in inversion. Fix: write the roots as a separate low line or give the pad stem a root-only layer, then keep the voice-led notes above A2.

The shared-pad problem [derived from `ears/specs/nova.spec.json`, consistent with the finding in `docs/handoff/2026-10-07-listening-loop.md`]: the chords across progressions A to D are Am, Dm, F, E, G, C. Among the twelve pitch classes only **D** has no semitone neighbour in any of their chord tones. A pad held on E clashes with the F chord (progressions B and D), and one held on A clashes with the G# of the E chord (B and C). Options for Fred: a D drone (the 4th, sus colour), per-progression pads, or a pad that only moves on common tones. Ask, do not decide.

Checker [derived; tested on the cases above]. It enforces the practical rule (only roots and fifths below C2, no third below E2, lowest note is the root) and flags close pairs under the derived 0.5 ERB floor. Feed it the sounding pitches of every part below C3: clip notes from `get_notes` plus the instrument's octave/transpose offsets and any MIDI-effect shifts.

```python
import itertools

def hz(m):   return 440.0 * 2 ** ((m - 69) / 12.0)        # Live: C3 = 60, A3 = 69 = 440 Hz
def erb(f):  return 24.7 * (4.37 * f / 1000.0 + 1.0)       # Glasberg & Moore 1990

def low_pairs(pitches, k=0.5, ceiling=60):
    """Simultaneous pairs, lower note below `ceiling`, whose fundamentals are < k ERB apart."""
    out = []
    for lo, hi in itertools.combinations(sorted(set(pitches)), 2):
        if lo >= ceiling or (hi - lo) % 12 == 0:
            continue
        d = hz(hi) - hz(lo)
        if d / erb(hz(lo)) < k:
            out.append((lo, hi, round(d, 1), round(d / erb(hz(lo)), 2)))
    return out

def slices(notes):                     # notes: [{"pitch","start","duration"}] in beats
    edges = sorted({n["start"] for n in notes} | {n["start"] + n["duration"] for n in notes})
    for a, b in zip(edges, edges[1:]):
        p = [n["pitch"] for n in notes if n["start"] < b and n["start"] + n["duration"] > a]
        if p:
            yield a, p

def check(notes, root_pc_at, k=0.5, low_top=47, third_floor=52):
    """root_pc_at(beat) -> pitch class (0-11) of the chord root, or of the pedal note.
    Practical rule: up to low_top (below C2) only root and fifth pitch classes sound (octaves included), and no
    third sounds below third_floor (E2). k is the derived ERB floor for close pairs."""
    seen = set()
    for a, p in slices(notes):
        root, msgs = root_pc_at(a), []
        if min(p) % 12 != root:
            msgs.append("lowest note %d is not the root" % min(p))
        for lo, hi, d, r in low_pairs(p, k):
            msgs.append("%d+%d only %s Hz apart (%s ERB)" % (lo, hi, d, r))
        for x in p:
            degree = (x - root) % 12
            if x <= low_top and degree not in (0, 7):
                msgs.append("%d is below C2 and not root or fifth" % x)
            elif x < third_floor and degree in (3, 4):
                msgs.append("%d is a third below E2" % x)
        for m in msgs:
            if m not in seen:
                seen.add(m)
                yield a, m
```

Test results: bass A0 + pad A2 C3 E3 + a 2-octave-down copy of the pad gives "33+36 only 10.4 Hz apart (0.34 ERB)" and "36 is below C2 and not root or fifth"; the same with a root-only sub gives no output; the voice-led Dm pad alone (A2 D3 F3) and `drop2` Am7 give "lowest note is not the root"; A1 C2 E2 over A gives "48 is a third below E2"; G1 B1 D2 over G flags B1.

> **For an agent: harmony and voicing**
> 1. Generate with `music_theory` (`progression` with numerals, `voice_leading=True` for the pad). Print the lowest note of every chord against its root before writing anything.
> 2. Write the bass roots as their own line (`write_notes`), single notes in MIDI 31-43, then the pad above A2.
> 3. Read the instrument with `get_device(parameters=True)`: octave, transpose, coarse, sub oscillator, unison/detune, any Chord, Pitch or Arpeggiator MIDI effect. Add those offsets to the pitches you feed `check()`. `analyze_notes` reads clip notes "before MIDI effects" and does not see instrument octave settings, sub layers or detune, and it has no low-interval or bass-is-root check.
> 4. Run `check()` and then `analyze_notes()`; clear both before any `capture`.
> 5. Stop and ask Fred when: you change mode or key; you want a deliberate semitone dissonance (say where and why); two valid voicings differ in mood (send an A/B, Section 6); anything needs a new low layer in a sound he approved.

## 3. Melody and motifs

- **Rhythm first, then pitches.** Write a one-bar rhythm of 3 to 6 onsets, then fill pitches from chord tones with one colour note. Ikonika's "Praxis" is a pair of near-identical two-bar phrases with a small change at the end, and its ascending five-note lines land in a different place in the bar each time, which creates forward motion ([Learning Music: Praxis](https://learningmusic.ableton.com/make-melodies/praxis.html) [manual]).
- **Call and response.** Kraftwerk's "Tour de France" melody uses a question phrase and an answer phrase that differ only in the last notes; later phrases repeat transposed up ([Learning Music](https://learningmusic.ableton.com/make-melodies/tour-de-france.html)). In clip terms: copy the 2-bar phrase, change the last 1 or 2 pitches for the answer (`edit_notes`), and move the third phrase up by scale degrees (`transform_notes(operation="transpose", steps=2)` after `set_song(key, scale)`).
- **Contrast steps and leaps.** Mostly stepwise motion with one or two leaps at phrase ends is more memorable than uniform motion ([Learning Music](https://learningmusic.ableton.com/make-melodies/love-will-tear-us-apart.html)). Shifting a pattern to start one beat later gives a different feel from the same pitches ([Learning Music: Ride variations](https://learningmusic.ableton.com/make-melodies/ride-variations.html)).
- **Space.** The NOVA spec asks leads to rest about 40 percent of the sixteenth steps (tolerance 10 points; `notes.lead_rests`). The first composition had 55 to 59 percent rests, sparser than briefed (`docs/handoff/2026-10-07-listening-loop.md`), so hold the target in both directions. Rests also leave the arp and pad room.
- **Lead over pad.** Chord tones on beats 1 and 3 (the `notes.chord_tones` rule), passing and neighbour tones on weak beats, no sustained non-chord tone against the bass. The 4th and 9th are safe colour over a minor chord. A held non-chord note is a legitimate tension device when you mean it ([Learning Music](https://learningmusic.ableton.com/make-melodies/love-will-tear-us-apart.html)).
- **Counter-melody.** Move against the bass (contrary motion, see 2.4), play in the gaps between stabs or in the lead's rests ([Attack: chord stabs](https://www.attackmagazine.com/technique/passing-notes/levelling-up-your-chord-stabs/)), use a different register or timbre, and stay on chord tones at the join points.
- **Simple recipes** from [Attack's melody techniques](https://www.attackmagazine.com/technique/passing-notes/dance-music-melody-composition-techniques-volume-1/): build from a note common to every chord in the loop, use a pentatonic scale that works over all of them, or hand-write arpeggios from chosen chord tones (root, third, seventh, ninth) instead of letting an arpeggiator cycle.

### Arpeggios

- Live's Arpeggiator has styles Up, Down (rising or falling), Converge, Diverge (inward or outward from the extreme notes), Play Order (the order you wrote), Chord Trigger and random variants, with Rate, Gate, Distance and Steps (octave or scale-degree transposition), Pattern Offset, Retrigger and Repeats ([Live manual: MIDI effects](https://www.ableton.com/en/live-manual/12/live-midi-effect-reference/) [manual]). Messy input makes interesting output: shorten some notes, move others an octave, then arpeggiate ([Attack: complex arps](https://www.attackmagazine.com/technique/tutorials/complex-arps-arpeggiator/)).
- Hand-written arps sound less mechanical; as MIDI they are also visible to `analyze_notes`, which cannot see a device's output. Prefer notes in the clip over a live Arpeggiator when checks matter.
- **Polyrhythm 3-over-4 and friends.** The classic 3-over-4 is a 3-sixteenth (dotted-eighth) step cycling over four-per-beat hats: it meets the beat grid every 3 beats and the bar line every 3 bars. In general a cycle of N sixteenths against a 16-step bar realigns after lcm(N, 16) steps:

| Arp length (16ths) | 3 | 5 | 6 | 7 | 9 | 12 |
| --- | --- | --- | --- | --- | --- | --- |
| Realigns after (bars) | 3 | 5 | 3 | 7 | 9 | 3 |

- **Polymetric arps.** Using twelve steps instead of sixteen turns an arp polymetric ([Attack](https://www.attackmagazine.com/technique/tutorials/when-is-an-arp-not-just-an-arp/)); 4/4 against 6/8 works on a 48th-note grid ([Attack: Polyrhythms](https://www.attackmagazine.com/technique/passing-notes/polyrhythms/)). In the NOVA spec the arp stem loops over 8 bars (128 sixteenths), so a 3-, 5- or 12-step cycle restarts at the loop point instead of completing. Write the pattern out for the full 8 bars and accept the restart, or use lengths whose cycle divides 8 bars (1, 2, 4, 8, 16 or 32 steps).
- **Euclidean patterns** spread k onsets as evenly as possible over n steps ([Toussaint 2005](http://cgm.cs.mcgill.ca/~godfried/publications/banff.pdf) [paper]): E(3,8) `x..x..x.` (tresillo), E(5,8) `x.xx.xx.`, E(5,16) `x..x..x..x..x...`, E(7,16) `x..x.x.x..x.x.x.`, E(9,16) `x.xx.x.x.xx.x.x.`, E(7,12) `x.xx.x.xx.x.`. Verified against the paper. Compact generator:

```python
def euclid(k, n):                       # Bjorklund; 'x' = onset, '.' = rest
    if not 0 < k < n:
        return "x" * k + "." * (n - k)
    a, b = [[1]] * k, [[0]] * (n - k)
    while len(b) > 1:
        m = min(len(a), len(b))
        a, b = [x + y for x, y in zip(a, b)], (a[m:] or b[m:])
    return "".join("x" if v else "." for g in a + b for v in g)
```

> **For an agent: melody**
> - Write the motif, run `analyze_notes()`, read `notes.motif` (how alike a stem's clips are across bands), the lead's rest share and `notes.chord_tones`. Make the variation, check again.
> - Use `set_song(key=..., scale=...)` before any `transpose` with `steps`; verify with `get_notes` that the pitches are what you meant, because `steps` use the song's scale.
> - Give the lead and the arp different onset slots: list their onset steps and keep shared steps under about a quarter of the lead's notes (heuristic [derived]).

## 4. Groove and pace

Pace is not tempo alone. The levers, with what they change:

| Lever | Effect | Numbers | Tool |
| --- | --- | --- | --- |
| Tempo | rate of everything | dub 60-90, hip-hop 60-100, house 115-130, techno/trance 120-140, dubstep 135-145, drum and bass 160-180 BPM ([Learning Music](https://learningmusic.ableton.com/make-beats/tempo-and-genre.html) [manual]) | `set_song(tempo)`, `set_scene(tempo)` |
| Backbeat level | half-time moves the snare to beat 3; the backbeat spacing of 140 BPM half-time equals that of a straight 70 BPM beat while hats still run at 140 | derived from the definition of backbeat on beats 2 and 4 ([Learning Music: Backbeats](https://learningmusic.ableton.com/make-beats/backbeats.html)) | `write_drum_pattern` |
| Onset rate | density drives energy; beat salience and event density correlate with how much music makes people want to move (Madison's work, cited in [Witek 2014](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0094446)) | 16ths: 6.7/s at 100 BPM, 9.3 at 140, 12 at 180 [derived] | `analyze_notes` density; onset rate from `meter(source="live")`; `audio.onsets` in `analyze_audio(take=...)` |
| Syncopation | medium syncopation gave the most desire to move and pleasure, an inverted U (50 drum patterns at 120 BPM) | [Witek et al. 2014](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0094446) [paper] | note placement; Euclidean patterns |
| Swing | bounce | see below | `transform_notes(quantize, swing)`, Groove Pool |
| Articulation | staccato feels tighter and faster, legato smoother | - | `transform_notes` `legato`, `stretch` |
| Harmonic rhythm | how often chords change; the spec uses 1 to 2 bars per chord | - | `write_notes` |

**Half-time in this project.** The kick plays in every NOVA tempo band and is absent only from tiers T1-T2: LOW (100-120 BPM) has a half-time kick on beats 1 and 3, MID (130-150) four-on-the-floor, HIGH (160-180) four-on-the-floor plus a pickup (the `ears` spec leaves HIGH's kick pattern open, `"kick": null`). Felt pace is carried by the hats, arp and perc as tempo rises. At 180 BPM 16th arps run at 12 onsets per second, near the point where notes blur into texture [heuristic, unverified]; check that tier with `analyze_notes` density and ask Fred.

**Swing.** Percent is the position of the off-16th inside its pair of 16ths: 50 straight, 66.7 triplet shuffle, 75 dotted ([Attack: swing](https://www.attackmagazine.com/technique/tutorials/going-off-grid-what-is-swing-and-how-to-add-it/) uses 52 to 73 percent examples and Live's "Swing 16th 64" groove; scales differ between systems, see [Attack: DAW and drum machine swing](https://www.attackmagazine.com/technique/passing-notes/daw-drum-machine-swing/)). Delay of the off-16th [derived]:

| Swing | 54% | 58% | 62% | 66.7% | 75% |
| --- | --- | --- | --- | --- | --- |
| 100 BPM | 12 ms | 24 ms | 36 ms | 50 ms | 75 ms |
| 140 BPM | 8.6 ms | 17 ms | 26 ms | 36 ms | 54 ms |
| 170 BPM | 7.1 ms | 14 ms | 21 ms | 29 ms | 44 ms |

Keep the kick as the fixed timing reference with static velocity, make ghost notes quieter, and let other parts play around it ([Attack: quantisation and velocity](https://www.attackmagazine.com/technique/tutorials/quantisation-velocity-editing-basics/)). Live's Groove Pool offers Base, Quantize, Timing, Random and Velocity (-100 to +100) per groove and a Global Amount up to 130 percent ([Live manual: Using Grooves](https://www.ableton.com/en/live-manual/12/using-grooves/)); in the tools: `get_grooves`, `set_groove`, `set_clip(groove=...)`, `set_song(groove_amount=...)`.

> **For an agent: groove and pace**
> - Swing in this repo's tools: off-step delay = swing x half a step (`MCP_Server/theory.py`, `AbletonMCP_Remote_Script/handlers/clips.py`), so MPC-style percent = 50 + 25 x swing: swing 0.16 = 54%, 0.32 = 58%, 0.48 = 62%, 0.67 = 66.7% (a triplet shuffle), 1.0 = 75%. The `drum_lanes` docstring in `MCP_Server/theory.py` gives the same table. Read back with `get_notes` and check the off-16th offsets in beats (62% is 0.06 beat late, 25.7 ms at 140 BPM).
> - `clip_action(quantize)` uses the song's swing amount; `transform_notes(quantize, swing=...)` uses the explicit value. Pick one, and say which.
> - Change one pace lever per audition. Tell Fred which: "same notes, half-time kick only".
> - A straight grid is a valid default for machine music: one study found the strongest groove for drum patterns without microtiming deviations (summarised in [Wikipedia: Groove](https://en.wikipedia.org/wiki/Groove_(music)) [weak]); Attack argues for feel around a steady kick. Let Fred's ear decide.

## 5. Writing in Live 12

### 5.1 The MIDI Tools

From the [Live 12 manual: MIDI Tools](https://www.ableton.com/en/live-manual/12/midi-tools/) [manual]. They work on a selected note range or the loop in Clip View, with Auto Apply or an Apply button; Seed, Shape, Stacks and Rhythm are generators (they replace overlapping notes), Velocity Shaper and Euclidean are Max for Live (included in Suite). With a clip scale on, pitch parameters switch to scale degrees. Practical walk-through: [Attack](https://www.attackmagazine.com/technique/tutorials/getting-started-with-ableton-lives-generative-midi-tools/).

**None of these has a Live API entry** (no generator or transformation member in `docs/reference/live_api_12.4.6.md`), so an agent cannot call them. The last column is the nearest route through the repo's tools.

| Tool | What it does (key parameters) | Dark-electronic use | Agent route |
| --- | --- | --- | --- |
| Rhythm (generator) | repeating pattern for one pitch or pad: Steps 1-16, Pattern, Density, Step Duration, Split, Shift, Accent | hats, shakers, ghost patterns; one voice at a time | `write_drum_pattern` step strings; `euclid()` |
| Seed | random notes within pitch, duration and velocity ranges; Voices, Density | glitchy textures, drone stabs | Python with a seeded RNG over `music_theory("scale")` pitches, then `write_notes` |
| Shape | notes along a drawn contour: Rate, Tie, Density, Jitter | pitch sweeps, rising or falling arps | compute a contour, `write_notes` |
| Stacks | chords and progressions in the clip scale (Tonnetz selector, Root, Inversion, Duration) | pads and progressions | `music_theory(chord/progression)`; check bottom notes (2.4) |
| Euclidean (M4L) | up to 4 voices: Steps, Density, Division, Rotation | polyrhythmic percussion, plucky arps | `euclid()` then `write_notes`/`write_drum_pattern` |
| Arpeggiate | break chords into 18 styles: Style, Distance, Steps, Rate, Gate | arps from stabs | write the sequence yourself, or add the Arpeggiator device |
| Connect | fill gaps with interpolated pitches: Spread, Density, Rate, Tie | passing tones between motif notes | compute passing tones, `write_notes` |
| Ornament | flams or grace notes: Position, Velocity, Chance, Amount | hat flams, lead grace notes | add short notes just before targets |
| Quantize | snap to a grid with Amount | tighten recorded or generated notes | `transform_notes(operation="quantize", grid, amount, swing)` |
| Recombine | shuffle, mirror or rotate position, pitch, duration or velocity | cheap variations: rotate the pitches one step, keep the rhythm | read `get_notes`, permute, `edit_notes` by `note_id` |
| Span | legato, tenuto or staccato with Offset, Variation | pads versus plucks from the same notes | `transform_notes(operation="legato")`, `stretch`, or edit durations |
| Strum | offset chord notes: Strum Low, Strum High, Tension | slow pad entries, dub stabs | `edit_notes` start offsets, or the Chord device's Strum |
| Time Warp | accelerando or ritardando by a speed curve with up to 3 breakpoints | accelerating snare rolls, drop fills | compute onsets on a curve, `write_notes` |
| Velocity Shaper (M4L) | velocity envelope: Min, Max, Loop, Rotate | accent contours, ghost notes | `transform_notes(operation="velocity", ...)` or write velocities |

### 5.2 Scale awareness

- Scale is stored per clip. The Control Bar chooser shows the selected clip's scale; without a clip selected it applies to new clips ([Live manual: Live Concepts](https://www.ableton.com/en/live-manual/12/live-concepts/), [Clip View](https://www.ableton.com/en/live-manual/12/clip-view/) [manual]).
- Scale Mode highlights scale rows, Fold to Scale hides the rest, Highlight Scale colours them purple. Changing a clip's scale never moves existing notes. **Fit to Scale** snaps pitches to the nearest scale degrees ([Editing MIDI](https://www.ableton.com/en/live-manual/12/editing-midi/)).
- Scale-aware devices: Arpeggiator, Chord, Pitch, Random and Scale (each with Use Current Scale), Auto Shift, Meld, Resonators/Spectral Resonator; Meld gained a scale-aware Chord oscillator type in 12.2 ([MIDI effects](https://www.ableton.com/en/live-manual/12/live-midi-effect-reference/), [release notes](https://www.ableton.com/en/release-notes/live-12/)). Max for Live devices did not follow scale or tuning at the Live 12.0 review ([Sound On Sound review](https://www.soundonsound.com/reviews/ableton-live-12) [article]); I did not re-check this for 12.4.
- The API exposes only Song-level `root_note`, `scale_name`, `scale_mode` (settable with `set_song(key, scale, scale_mode)`) and `scale_intervals` (read-only); there is no per-clip scale member. Treat scale as a display aid and a device input, never as validation of what you wrote.
- **Do not run Fit to Scale on a clip that holds the harmonic-minor G#.** With A Minor active it would snap G# to G or A and remove the leading tone from the E chord. Use scale "Harmonic Minor" for such clips or leave Fit to Scale alone.
- Tuning systems (Scala files, just intonation) apply to all built-in instruments; non-MPE third-party plug-ins and Max devices can play out of tune against them, and note names change ([Live manual](https://www.ableton.com/en/live-manual/12/using-tuning-systems/)). Drone Lab ships tunings such as Solfeggio, Pythagorean and Pelog and a Max drone synth that can run in just intonation ([pack](https://www.ableton.com/en/packs/drone-lab/)). Just thirds do not beat the way tempered ones do, but mixing them with equal-tempered parts causes the 14 to 16 cent offsets described in 2.5; treat this as Fred's decision.

### 5.3 MIDI-effect devices as generators

Arpeggiator (`Style`, `Synced Rate` or `Free Rate`, `Gate`, `Transp. Dist.`, `Transp. Steps`, `Retrigger Mode`), Chord (six added notes `Shift1` to `Shift6`, each plus or minus 36 semitones, with `Velocity1`.. and `Chance1`.. per note, and `Strum`), Scale (`Base`, `InternalScale`, `Transpose`, `Fold`), Random (`Chance`, `Choices`, `Interval`, `Mode`, `Sign`) and Pitch (`Pitch` plus or minus 128 semitones, `Pitch Scale Degrees` plus or minus 30) are all addable with `add_device` and settable with `set_device_parameters`; the names above are the API's (see `reference/live-12.4.6-device-parameters.md`), not always the labels on the device. A Random device followed by a Scale device keeps random notes in key ([Attack: Random MIDI](https://www.attackmagazine.com/technique/passing-notes/chords-and-melodies-with-random-midi/)). Caveats: their output is audio-only to your checks (`analyze_notes` reads clip notes before MIDI effects and only flags their presence as `notes.midi_effects`, information), and a Chord shift of -24 is exactly how a sub layer of thirds appears. List every MIDI effect with `get_devices` before trusting a clip's notes.

### 5.4 Follow Actions and clip variations

- Follow Actions (Stop, Play Again, Previous, Next, First, Last, Any, Other, Jump, No Action) run on a group of consecutive clips, with Chance A/B, Linked or Unlinked timing, a Follow Action Time and a loop Multiplier ([Live manual: Launching Clips](https://www.ableton.com/en/live-manual/12/launching-clips/) [manual]). **They are not exposed in the 12.4.6 API dump**, so the tools cannot set them; ask Fred to, or use scenes.
- The classic generative use ([Attack: Follow Actions](https://www.attackmagazine.com/technique/passing-notes/auto-generated-parts-with-follow-actions/)): single-note clips set to Any every 16th, empty clips set to Other for rests, record the result and loop the best bars. An agent gets the same, reproducibly, from a seeded RNG and `write_notes`.
- Note-level variation without extra clips: `write_notes` accepts `probability` and `velocity_deviation`; Live's Chance Editor groups notes as Play All or Play One. Takes then differ, which `analyze_notes` reports as `notes.probability`; for looping game stems keep notes deterministic.
- Variation recipe: `duplicate_clip` into the next scene, apply one change (`transform_notes`/`edit_notes`), name it "A", "B", "C", fire the scenes in order.

> **For an agent: Live 12 writing tools**
> - You cannot press the MIDI Tools, set a clip's scale or set Follow Actions. Generate notes in code (seeded RNG, `euclid()`, `music_theory`), write them with `write_notes`, and say in your report which Live tool the result imitates.
> - Seeds make variations reproducible: keep the seed in the clip name or the `capture` note so a take can be rebuilt.
> - If Fred wants the real tool (for example Stacks for chord ideas), ask him to apply it to a named clip, then read the result with `get_notes` and run the checks in 2.8 before anything else.
> - MIDI-effect devices change what sounds but not what `analyze_notes` reads: list them with `get_devices` and prefer notes in the clip when the checks matter.
> - Never run Fit to Scale or any transform over notes with intentional accidentals without reading back `get_notes` first.

## 6. Presenting musical options to Fred

Why: the 2026-10-08 failures were many simultaneous changes, unlabelled auditions, a replaced sound and no loudness-matched comparison. Fred's ear is the gate; metrics are guidance.

1. **One variable per audition.** Pick from the ladder, in this order: mode or key, progression, voicing and register, rhythm, tempo, sound. State which one.
2. **Two options, three at most, always including the current version as A.**
3. **Label everything in the set**: scenes or clips named "AUD2-A Aeolian", "AUD2-B Phrygian"; the old version stays on a muted twin until he picks.
4. **Announce the order before playing** (A, B, A again, 8 bars each) and ask one narrow question ("which one wants the loop to restart at bar 4?"), not "which is better".
5. **Match loudness first.** Harmony-only changes move level little, but voicings can. Check with `meter(seconds=10)` or `capture`/`compare` (spectral numbers there are loudness-matched) and trim with the Utility `Output` on that track, not the master, until the integrated loudness of A and B agrees within 0.2 LU (0.3 LU at most). See [11-listening-without-ears.md](11-listening-without-ears.md).
6. **Do not touch anything else** (levels, other tracks, his chosen sounds) until he answers; record what changed (`capture(note=...)`).
7. **Stop and ask** before key or mode changes, intentional dissonance, replacing a sound, deleting his clips, or any mix-wide move.

Template:

```
Audition 2 of 3 - harmony only. Same sounds, 140 BPM, levels matched within 0.2 LU.
  A (current)  Aeolian + borrowed V:  Am  Dm  G   E
  B            Phrygian colour:       Am  Bb  Am  E      (bars 2-3 changed)
Order: A, B, A, 8 bars each. Question: which one makes bar 4 pull harder back to Am?
I will not change anything else until you pick.
```

## 7. Pre-flight checklist before showing anything

- [ ] `analyze_notes()` has no fails (in key, chord tones, clash, shared stem, loop length).
- [ ] Sounding pitches include instrument octave and transpose settings, MIDI effects and any sub layer.
- [ ] `check()` is silent: lowest note is the root, nothing below C2 but roots and fifths, no third below E2, no pair under the 0.5 ERB floor.
- [ ] No two stems a semitone apart for a sixteenth or longer (G against G#).
- [ ] Each part sits in its register slot; the lead and the arp do not share onsets; lead rests are near 40 percent.
- [ ] Only one thing changed since the last approved version, and the previous version is kept muted.
- [ ] Loudness matched; options labelled; the question is narrow.
- [ ] Sections change on 4/8/16 bars; no 8-bar block repeated more than four times unchanged; one subtraction before every entrance.

Common mistakes: building the pad from `drop2` or voice-led chords and calling it the bass; letting an instrument's sub layer duplicate chord thirds; saturating a full chord; filling every beat of the lead; adding a riser before removing anything; presenting five options that differ in three ways; regenerating clips after `arrange_from_scenes` without re-running it.

## Sources

Ableton [manual] and Ableton education:
- [Live 12 manual: MIDI Tools](https://www.ableton.com/en/live-manual/12/midi-tools/); [Editing MIDI](https://www.ableton.com/en/live-manual/12/editing-midi/); [Live Concepts](https://www.ableton.com/en/live-manual/12/live-concepts/); [Clip View](https://www.ableton.com/en/live-manual/12/clip-view/); [Launching Clips](https://www.ableton.com/en/live-manual/12/launching-clips/); [Live MIDI Effect Reference](https://www.ableton.com/en/live-manual/12/live-midi-effect-reference/); [Using Grooves](https://www.ableton.com/en/live-manual/12/using-grooves/); [Using Tuning Systems](https://www.ableton.com/en/live-manual/12/using-tuning-systems/); [Live 12 release notes](https://www.ableton.com/en/release-notes/live-12/)
- Learning Music: [Song structure](https://learningmusic.ableton.com/song-structure/song-structure.html), [Modes](https://learningmusic.ableton.com/advanced-topics/modes.html), [Tempo and genre](https://learningmusic.ableton.com/make-beats/tempo-and-genre.html), [Backbeats](https://learningmusic.ableton.com/make-beats/backbeats.html), [Praxis](https://learningmusic.ableton.com/make-melodies/praxis.html), [Tour de France](https://learningmusic.ableton.com/make-melodies/tour-de-france.html), [Love Will Tear Us Apart](https://learningmusic.ableton.com/make-melodies/love-will-tear-us-apart.html), [Ride variations](https://learningmusic.ableton.com/make-melodies/ride-variations.html)
- Making Music (Dennis DeSantis): [Arranging as a Subtractive Process](https://makingmusic.ableton.com/arranging-as-a-subtractive-process), [Dramatic Arc](https://makingmusic.ableton.com/dramatic-arc), [Creating Variation 2](https://makingmusic.ableton.com/creating-variation-2-mutation-over-generations), [Asynchronous or Polyrhythmic Loops](https://makingmusic.ableton.com/asynchronous-or-polyrhythmic-loops), [Unique Events](https://makingmusic.ableton.com/unique-events)
- Packs: [Build and Drop](https://www.ableton.com/en/packs/build-and-drop/), [Drone Lab](https://www.ableton.com/en/packs/drone-lab/)

Attack Magazine [article]:
- Arrangement: [Recipe for an effective breakdown](https://www.attackmagazine.com/technique/the-breakdown/what-is-the-recipe-for-an-effective-breakdown/); [4 ways to break out of the loop](https://www.attackmagazine.com/technique/tutorials/4-ways-to-break-out-of-the-loop/) (template used in 1.2); deconstructions of [Âme "Rej"](https://www.attackmagazine.com/technique/deconstructed/ame-rej/), [Drexciya "Black Sea"](https://www.attackmagazine.com/technique/deconstructed/drexciya-black-sea/), [Beltram "Energy Flash"](https://www.attackmagazine.com/technique/deconstructed/joey-beltram-energy-flash/), [Jeff Mills "The Bells"](https://www.attackmagazine.com/technique/deconstructed/jeff-mills-the-bells/)
- Harmony and melody (Passing Notes): [Choosing the right key for bass weight](https://www.attackmagazine.com/technique/passing-notes/choosing-keys-for-bass-weight/), [Massive chords with ensemble voicings](https://www.attackmagazine.com/technique/passing-notes/massive-chords-with-ensemble-voicings/), [Lessons from disco](https://www.attackmagazine.com/technique/passing-notes/lessons-from-disco-chords/), [Contrary motion](https://www.attackmagazine.com/technique/passing-notes/contrary-motion/), [Levelling up your chord stabs](https://www.attackmagazine.com/technique/passing-notes/levelling-up-your-chord-stabs/), [Ostinatos and acid riffs](https://www.attackmagazine.com/technique/passing-notes/ostinatos-and-acid-house-riffs/), [Melody and composition techniques](https://www.attackmagazine.com/technique/passing-notes/dance-music-melody-composition-techniques-volume-1/), [Polyrhythms](https://www.attackmagazine.com/technique/passing-notes/polyrhythms/), [Follow Actions](https://www.attackmagazine.com/technique/passing-notes/auto-generated-parts-with-follow-actions/), [Random MIDI](https://www.attackmagazine.com/technique/passing-notes/chords-and-melodies-with-random-midi/), [DAW and drum machine swing](https://www.attackmagazine.com/technique/passing-notes/daw-drum-machine-swing/); tutorials: [Parallel chord stabs](https://www.attackmagazine.com/technique/tutorials/the-theory-of-techno-parallel-chord-stabs/), [Swing](https://www.attackmagazine.com/technique/tutorials/going-off-grid-what-is-swing-and-how-to-add-it/), [Complex arps](https://www.attackmagazine.com/technique/tutorials/complex-arps-arpeggiator/), [Arpeggiators](https://www.attackmagazine.com/technique/tutorials/when-is-an-arp-not-just-an-arp/), [Quantisation and velocity](https://www.attackmagazine.com/technique/tutorials/quantisation-velocity-editing-basics/), [Live generative MIDI tools](https://www.attackmagazine.com/technique/tutorials/getting-started-with-ableton-lives-generative-midi-tools/)

Other articles:
- [Mixed In Key: arranging a dance track](https://mixedinkey.com/captain-plugins/wiki/how-to-arrange-a-dance-music-track/); [Gearnews: arrangement techniques](https://www.gearnews.com/arrangement-techniques-for-electronic-music/); [Production Music Live: 10 arrangement tips](https://www.productionmusiclive.com/blogs/news/how-to-arrange-a-track-10-arrangement-tips-for-electronic-music)
- Sound On Sound: [Mix Rescue, Turn Back To Spring (Mike Senior)](https://www.soundonsound.com/node/4908260); [Crafting Loud Mixes That Sound Great (Paul White)](https://www.soundonsound.com/node/4904703); [Live 12 review](https://www.soundonsound.com/reviews/ableton-live-12)
- [Production Expert: intermodulation distortion](https://www.production-expert.com/production-expert-1/intermodulation-distortion-the-audio-problem-you-may-be-overlooking); [Berklee Online: voice leading](https://online.berklee.edu/takenote/voice-leading-paradigms-for-harmony-in-music-composition/); [Audiotent: dub techno chords](https://www.audiotent.com/blogs/production-tips/dub-techno-chord-sound-design); [Evan Rogers: voicings part 2](https://www.evanrogersmusic.com/blog-contents/big-band-arranging/voicings-part2); [Robin Hoffmann: low interval limits](https://www.robin-hoffmann.com/dfsb/low-interval-limits); [Sweetwater: low interval limit](https://www.sweetwater.com/insync/low-interval-limit/) (page not readable, values via search summary [weak])
- Modes: [Ethan Hein](https://ethanhein.substack.com/p/why-are-there-so-many-minor-scales), [Composer Code: Dorian](https://composercode.com/the-dorian-mode-darkness-with-a-hint-of-light/), [Flat: Phrygian](https://blog.flat.io/phrygian-mode-explained/), [Fachords: Phrygian chords](https://www.fachords.com/phrygian-scale/)
- Wikipedia (background): [Power chord](https://en.wikipedia.org/wiki/Power_chord), [Pedal point](https://en.wikipedia.org/wiki/Pedal_point), [Voice leading](https://en.wikipedia.org/wiki/Voice_leading), [Equivalent rectangular bandwidth](https://en.wikipedia.org/wiki/Equivalent_rectangular_bandwidth), [Groove (music)](https://en.wikipedia.org/wiki/Groove_(music))

Papers [paper]:
- Eerola and Lahdelma (2021), [Register impacts perceptual consonance through roughness and sharpness](https://pmc.ncbi.nlm.nih.gov/articles/PMC9166839/), Psychonomic Bulletin and Review 29(3)
- Witek, Clarke, Wallentin, Kringelbach and Vuust (2014), [Syncopation, body-movement and pleasure in groove music](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0094446), PLOS ONE
- Toussaint (2005), [The Euclidean algorithm generates traditional musical rhythms](http://cgm.cs.mcgill.ca/~godfried/publications/banff.pdf)
- Sethares, [dissonance curves and timbre](https://sethares.engr.wisc.edu/consemi.html) (summing roughness over all partial pairs)

Repo facts used: `docs/TOOLS.md` (tool signatures, Live pitch naming), `ears/specs/nova.spec.json` (key, progressions, rest share, tiers), `docs/reference/live_api_12.4.6.md` (no MIDI-tool, follow-action or per-clip scale members; `Song.tuning_system` exists), `MCP_Server/theory.py` and `AbletonMCP_Remote_Script/handlers/clips.py` (voicings, swing formula), `docs/handoff/2026-10-07-listening-loop.md` (shared-pad clash, sparse leads).

## Open questions / where sources disagree

- **Low-interval values.** I could not open the Sweetwater chart; its rows are from secondary summaries in scientific pitch notation, converted to Live names (one octave lower) [weak]. The 0.5 and 1.0 ERB floors are my own calibration: the 1 ERB column equals the chart for the fourth, runs 2 to 15 semitones above it for the fifth and thirds, and is lower for the tritone, sixths and sevenths. The practical rule (below C2 only roots, fifths and octaves; major thirds from E2; minor thirds and seconds higher still) is deliberately stricter than the chart for thirds and seconds. Bandwidth models (ERB versus Bark) disagree by a factor of nearly three at 100 Hz. Fred's ear should confirm the floors on this project's actual sounds.
- **Phrase lengths.** Sources call 8 and 16 bars a default, yet "Black Sea" enters its kick at bar 6 and "Energy Flash" is a 176-bar three-part form. Use the grid as a default and break it on purpose.
- **How many layers.** No empirical study found. Practitioner statements range from "never more than a few" (Mills) to 8 to 10 small layers (Beltram).
- **Mode and darkness.** All sources rank Phrygian darkest and Dorian lightest, but only qualitatively; the effect depends on voicing and sound design, so audition rather than assume.
- **Microtiming.** Attack advises feel around a steady kick; one study summarised on Wikipedia found the strongest groove with no microtiming deviation [weak]. Not resolved.
- **Perceived pace.** The statement that onset rate and event density raise perceived energy rests on Madison's work as cited by Witek et al.; I could not open the originals. The Witek stimuli were all at 120 BPM, so the inverted-U result is not tested at the 100 to 180 BPM range of this project.
- **Swing scale.** The tools' formula (delay = swing x half a step) gives 58 percent at 0.32 and 66.7 percent at 0.67. Other systems scale swing differently (Attack's article above), and `set_song(swing=...)` sets Live's own song swing amount, whose percent scale this digest did not check [verify].
- **Not reachable through the API.** MIDI Tools, Follow Actions and per-clip scale have no Live API members in the 12.4.6 dump; UI automation through `ui_automation.py` might reach them but I have not checked. A future `analyze_notes` could add the bass-is-root, low-interval and sounding-pitch checks from Section 2.8.
- **Not run against Live.** The brief forbade touching Live or the MCP tools, so no recipe here was executed in a session. Tool behaviour comes from `docs/TOOLS.md` and the repo code; the `music_theory` outputs come from running `MCP_Server/theory.py` directly, and the two code blocks were run and tested locally.
- **Search budget.** The web-search quota ran out partway through research. MusicRadar, Point Blank, Isotonik and the Ableton help article were unreadable (truncated or HTTP 403), so none of their claims are used.
