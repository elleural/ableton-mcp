# 00 Agent playbook: making music in Ableton Live when you cannot hear

You drive Ableton Live 12.4.6 Suite through this repo's MCP tools. You can read and set every parameter, write
every note, render and measure audio, but you cannot hear. A human producer (Fred, for the NOVA game soundtrack)
listens and decides. This playbook is the short version of the digests in this folder plus what went wrong on
2026-10-08, when a day of recomposition ended with "you do not have the skillset" and the work was paused
(`docs/handoff/2026-10-08-nova-v2-paused.md`). Read it before any music task; follow the links for depth.

## The rules

1. **The producer's ear decides; measurements diagnose.** Numbers tell you what changed and point at causes.
   They never choose a sound, and they never justify a mix move on their own. When the producer says "good",
   that version is the new baseline, whatever the numbers say. (11, 06)
2. **Never steer one instrument toward a full-mix spectrum.** A reference song's spectrum is drums, bass, vocals,
   synths and mastering together. Ranking pad presets by distance to it gave "circus" and "hollow" sounds. Use
   references for direction (register, width, cleanliness, loudness of the sum), measured on passages where the
   element is exposed, and build the sound for its role. (09, 11)
3. **Read the patch, not its name.** Before you use a preset, read every instrument parameter with
   `get_device(track, 0, detail=True)` and the whole chain with `get_devices`: oscillator levels, octave and
   transpose, sub level and octave, noise, filter type and cutoff, unison and voice mode, chorus. Then play one held
   note and find its spectral peaks: confirm the pitch it actually sounds. "Dark Throne" turned out to be a
   sub-oscillator two octaves down plus noise through a 372 Hz low-pass, with both main oscillators at 0 %:
   hollow and airy by construction. (02)
4. **Know where the notes sound.** Live names octaves with C3 = 60: MIDI 69 = A3 = 440 Hz, 57 = A2 = 220 Hz,
   45 = A1 = 110 Hz, 33 = A0 = 55 Hz. Below about 130 Hz (Live C2) write only roots, fifths and octaves; put major
   thirds above about 165 Hz and minor thirds and seconds higher still; the lowest sounding note of the mix is the
   chord root. Every layer counts: a sub-octave oscillator, a transposed preset or a MIDI effect moves notes into
   the bass register where they clash. Most "wrong notes or tuning" complaints are register, not pitch. (08, 02)
5. **One change at a time, and keep the approved version alive.** Duplicate the track (`duplicate_track`) and
   mute the copy, or note the take snapshot, before you touch anything the producer approved. Never replace a
   sound he picked with a different sound: iterate on his pick. Never change tracks you were not asked to change.
   (01, 06)
6. **Compare only at matched loudness.** The louder of two versions tends to win a short listen. Match integrated
   loudness within 0.2 LU before any A/B, alone and in context. (11, 05)
7. **Process in small doses, with a stated purpose.** Subtract before you add; about 1-3 dB of gain reduction on
   buses, more only on a drum that needs it; distortion on single-note parts (kick, mono bass, percussion), never
   on sustained chords (intermodulation sounds out of tune); width above about 200 Hz with a mono low end; chorus
   and detune sparingly (they are what "flangy" means); no limiter except one at the very end of one chain (on a
   stereo master about 1-3 dB of gain reduction, 4-6 dB only for dense electronic music after an A/B; never on
   stems). (06, 03, 07)
8. **Loudness is arithmetic on the sum.** LUFS = true peak - PLR. A mix whose peak-to-loudness ratio is 13 dB or
   less reaches -14 LUFS under -1 dBTP with no limiter. Set loudness with one shared gain on the sum; for adaptive
   game stems never limit or normalise stems one by one, check every subset the game can play, and leave margin
   for loop seams and codecs. (05, 07, 10)
9. **Fix problems where they live.** A hollow pad is a sound problem, clashing notes are a voicing problem, kick and
   bass fighting is an arrangement or EQ problem on those two tracks. None of them are fixed on the master or by
   processing other tracks. (07, 06)
10. **Tell the producer exactly what will play.** Before an audition, say the order, what each version changes and
    how long each plays; show the label in Live while it plays (`show_message("B: + chorus 30 %")`); give him a way
    to answer with a letter or number. He reacts in real time: keep a log of what played when so his messages map to
    the right version. (11)
11. **Translate his words into one hypothesis, then test it.** Use the table below. If three steps in the same
    direction do not get a "better", stop and ask a precise question instead of trying a fourth.
12. **Write down what he said.** His words and decisions go into the handoff notes (and memory), with the take or
    track that he judged. The next agent starts from his last "good", not from scratch.

## The change loop

1. **Goal**: the producer's words, and your hypothesis ("hollow" -> the pad has no harmonics between 300 Hz and
   1 kHz -> raise the saw oscillator).
2. **Restore point**: muted twin track or take snapshot; for mix work, note every value you will change.
3. **One change**: one parameter, one device, or one voicing.
4. **Measure** what the hypothesis predicts (table below), on the part alone and in context. If the numbers did not
   move the way you predicted, your hypothesis is wrong: revert before trying something else.
5. **Match loudness** of A and B within 0.2 LU.
6. **Announce and play** A then B (8 bars each is plenty), labelled in Live.
7. **He decides.** Keep B as the new base, or revert to A. Log it.

What to measure for each kind of change (tools: `bounce` + `analyze_audio`, `capture`, `compare`, `get_meters`,
`analyze_notes`; methods in 11):

| Change | Look at | A bad sign |
| --- | --- | --- |
| Oscillator, filter, voicing | spectral peaks of a held note and chord; harmonic series; noise share | missing harmonics, energy between harmonics (noise), unexpected sub-octave peaks |
| Width, chorus, unison, reverb | side/mid per band; mono-sum loss below 120 Hz; correlation | side energy below 120 Hz, correlation near 0 or negative, mono sum losing level |
| EQ, level | third-octave balance of the sum against the last approved take | big moves in bands the change was not meant to touch |
| Dynamics, limiting | true peak, PLR, crest factor, short-term loudness spread | PLR falling below about 8 dB on a game stem sum, flattened short-term loudness |
| Notes, arrangement | `analyze_notes` (key, chord tones, semitone clashes); intervals in the low register; onset rate | thirds below about 165 Hz, a non-root bass voice, semitone cross-relations |

## The producer's words, decoded

| He says | Likely cause (what you can measure) | First move to test (one at a time) |
| --- | --- | --- |
| hollow | no body between about 150 and 600 Hz; odd-only harmonics (50 % pulse, narrow band-pass); a patch that is only sub plus noise; open voicings with octave gaps; a mid cut | a fuller oscillator (saw), lower the high-pass, remove mid cuts, close the voicing in the middle register |
| meatier | as hollow, plus too little harmonic density | layer a saw an octave below or in unison; gentle saturation on that layer, not on the chord |
| airy | noise and high-frequency energy above the harmonics; reverb wash | less noise oscillator, a lower low-pass or a high shelf cut, drier reverb |
| raspy | noise plus saturation | if he likes it, keep it; otherwise less noise or drive |
| flangy, phasey | chorus or flanger (worst on noise), detuned unison beating, two copies of a sound slightly offset | chorus off or shallower, less detune, width from reverb or stereo voices instead |
| too distorted, dirty | saturator drive; a limiter or clipper squashing; distortion on whole chords | remove distortion from chords, check every limiter's gain reduction, move grit to a single-note layer |
| wrong notes, out of tune | semitone cross-relations; thirds or seconds in the low register; a non-root lowest note; sub-octave layers; detune or analogue drift; distortion on chords | list every sounding pitch per bar (with sub layers), apply the register rules, remove the sub layer, no chord saturation |
| circus | bright, staccato, high-register plucks; fast arps; major colour | lower register, longer notes, slower movement, darker filter, more space |
| pace too fast | onset rate; tempo; backbeat placement | half-time feel, fewer onsets per beat, longer notes |
| bigger | narrow image; thin harmonic stack; dry | octave layering, width above 200 Hz, a larger reverb on a send, keep the low end mono |
| heavy | weak 40-150 Hz; root too high | a low root in octaves and fifths, a sub layer in tune with the bass |
| clean | noise, distortion, intermodulation, squashing | remove noise and chord distortion, remove limiting, clean oscillators |
| garbage (whole mix) | many tracks changed at once | restore the last approved snapshot of every touched track, then one change at a time |

## Before you touch a sound

- Read the instrument parameters and the chain; write down what you see (oscillators, sub, noise, filter, voices).
- Confirm the sounding pitch on one held note; confirm the chord's lowest sounding note.
- Check clip envelopes (`get_automation`): they override manual values while the clip plays.
- For Max for Live devices and rack presets, expect non-obvious parameters (macros, hidden layers, internal
  effects); list the rack's chains.
- Use exact parameter names from `reference/live-12.4.6-device-parameters.md` and send display strings ("-6 dB",
  "800 Hz", "30 %") or item names, then read the echoed `display`.

## Tool pitfalls (as of 2026-10-08)

- Live has no native LUFS, true-peak or correlation meter. `get_meters` reports post-fader peak only, while the
  transport runs. Loudness, peaks, balance and width come from `bounce` + `analyze_audio` or `capture`. (05)
- `set_device_parameters` clamps out-of-range display values silently, reads "1/8" as 1 (send the raw integer step
  for synced rates and read the label back), and dry/wet is spelled differently per device ("Dry/Wet", "Dry Wet",
  "DryWet"). Always compare the echoed `display` with what you asked for. (12)
- `lom_get` lists show only the first 32 names (`count` is the true length): a by-name check past index 31
  silently fails. Use `get_mixer`, `get_track`, `delete_track(name)`.
- Delete structural objects (tracks, scenes, returns) one per call: batched deletions crashed Live 12.4.6. Save
  before risky operations; the producer is fine pressing Cmd+S (Save As through the tool once hung Live).
- `write_automation` creates Session clip envelopes (they travel with `arrange_from_scenes`); on Arrangement clips it
  can only edit envelopes they already carry, and it cannot write Arrangement lanes. `create_bus` makes an audio
  track, not a Group. Only the
  Compressor's sidechain source is routable (`set_sidechain`), and it leaves the Compressor's own settings as
  found: a fresh Compressor is in RMS mode with its sidechain EQ on (high-pass 80 Hz), which weakens a kick
  trigger; set `Model` and `S/C EQ On` deliberately. Never bake kick ducking into a stem that plays without the
  kick (in NOVA, bass in tier T2). The tools cannot freeze, flatten or bounce in place,
  map macros, edit rack zones, or set follow actions; Live 12's MIDI Tools and per-clip scales are not in the API.
  (01, 08)
- `music_theory` voice-led, drop-2, drop-3 and inverted voicings can put the third or fifth at the bottom: check
  the lowest note. Swing: delay = swing x half a step, so 0.67 is a triplet shuffle. (08)
- Firing a scene fires every clip in its row; in the NOVA set that plays variations A and B at once. For
  listening, fire the clips of one variation. Captures set the middle tempo and restore it afterwards.
- Recording auditions through the loopback means soloing and muting: restore every solo, mute and tempo you
  changed, and stop the transport.
- **A soloed track plays even when its activator is off** (Live 12.4.6, found 2026-10-09). Switch A/B versions by
  solo (solo the next, then release the current), never by muting soloed tracks. Session clips that were playing when
  the transport stopped resume when anything starts it: solo what you want to hear. (13)
- The fader stops at +6 dB: put big level trims on the chain's last Utility `Output`. Check the producer's sound's own
  level before matching to it: NOVA's base pad peaked near 0 dBFS alone, 14 dB over the mix's pad stem. (13, 05)

## Working with the producer

- Start every session from his last approved state. Ask what he wants to hear first.
- Offer a few labelled choices only when he asks for choices; otherwise iterate on what he picked.
- Keep choice tracks clearly named ("pad v2 - + echo") and loudness-matched; delete them only when he has chosen.
- When he is frustrated ("wtf", "garbage"), stop all audio changes, restore the last approved state, and say plainly
  what you changed that he did not ask for.
- Never claim something sounds better. Say what you changed, what the measurements show, and ask.

## Case study: NOVA, 2026-10-08

| What happened | Rule | Do instead |
| --- | --- | --- |
| Pad presets ranked by spectral distance to full-mix references: "circus", then "hollow" | 2, 3 | design for the role from construction (03, 09); read the patch |
| The chosen pad was a -2 octave sub plus noise; its chord thirds sat at 55-65 Hz under the bass | 3, 4 | check oscillators and sounding pitches; low-register rules |
| Saturating whole chords and chorus on noise: "out of tune", "flangy" | 7 | distortion on single notes only; chorus sparingly, never on noise |
| True Peak limiters on every stem, EQ and faders changed on every track: "garbage" | 5, 7, 8 | one track at a time; loudness with one shared gain on the sum |
| New rounds of different sounds after he had picked one | 5, 10 | iterate on his pick; keep it as the base |
| Auditions played without labels; he reacted to versions he could not name | 10 | announce the order; `show_message` labels; log what played when |
| Comments said A1 = 55 Hz for MIDI 45 (it is 110 Hz) | 4 | use the Live naming table |

## Reading map

| You are about to | Read |
| --- | --- |
| choose, read or design a sound | 02, 03, then 11 |
| scan a library of presets for a role | 13 |
| work on kick, bass, drums or groove | 04 |
| set levels or reason about loudness | 05, 07 |
| mix | 06 (with 05 and 11) |
| write, voice or arrange | 08, then 09 for the genre |
| deliver game stems | 10 and 07 section 5 |
| route, use racks, or check what the tools cannot do | 01, 12 and `reference/` |
