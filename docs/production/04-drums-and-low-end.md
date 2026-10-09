# Drums and low end: kick, bass, drum processing and groove in Live 12

For AI agents making music in Live 12.4.x through AbletonMCP. You cannot hear: you act with tools, judge with measurements, and
Fred (the producer) judges by ear. Related digests: `03-sound-design-recipes.md` (bass sounds), `05-gain-staging-and-metering.md`,
`06-mixing.md`, `08-arrangement-and-composition.md` (voicing, MIDI tools), `09-industrial-ebm-techno-nin.md` (genre),
`10-game-audio-adaptive-music.md` (stems), `11-listening-without-ears.md`, `12-live-devices-reference.md`.

Evidence: web research (inline links, listed under "Sources"), Live's Reference Manual, and the factory presets installed with Live
12.4 on this Mac (I read the Drum Buss, EQ Eight, Glue Compressor, Roar, Utility, Saturator, Gate and Operator preset files, so
"factory preset" figures are Ableton's own sound-design choices). Tutorial numbers are starting points, not laws. Tags: **[D]**
derived by calculation here; **[weak]** vendor, blog or Wikipedia-level source; **[verify]** tool behaviour not confirmed in a
running Live. Note names follow Live and the MCP (**C3 = MIDI 60**), one octave below the scientific names most articles use. Parameter names in
`code` are the exact names `get_device` reports (dumped in `reference/live-12.4.6-device-parameters.md`); send display strings and read the echoed `display` back.

## If you remember five things

1. **Lock the low end first, with two voices.** One kick with one settled fundamental tuned to the song, one bass line with a
   different job, nothing else sustained below roughly 100 Hz. Faults down here are hard to fix once layers sit on top
   ([Sara Landry's workflow](https://www.ableton.com/en/blog/sara-landry-high-end-hard-techno/)).
2. **A kick is click + body + sub, mono, and finishes before the next hit.** Check layers for polarity and timing; a "rumble" is a
   separate low-passed, ducked, reverberant copy, not a longer kick.
3. **Make room in this order: pitch and arrangement, EQ slots, then sidechain.** Ducking depth is a style choice (1-3 dB
   transparent, 6-12 dB for the pumping sound). In stems that can play without the kick, composed gaps beat baked-in pumping.
4. **Drum bus: density without mush.** Drum Buss or Saturator for harmonics, Glue Compressor for 2-4 dB of gain reduction (attack
   10-30 ms keeps the punch), parallel paths for weight, distortion on the mids and highs with a clean low band. Level-match before
   judging. Never put a loudness limiter on every stem.
5. **Groove is small, deliberate and measurable.** Swing 54-60 % on hats and percussion (kick and clap stay on the grid), velocity
   contrast, ghost notes at 30-50 % of an accent, a few milliseconds of offset. Hits per second shape perceived pace more than BPM.
   Verify with grid deviation, velocity spread and onset rate, then let a human A/B.

---

## 1. The kick

### 1.1 Anatomy and range

An engineer quoted by Ableton splits a kick into the **transient** (click), the **envelope** (the fall from click to thud) and the
**decay** (boom). A kick that fails to cut through usually has one of these out of balance, and weight lives in the envelope and
decay: start the envelope from a lower point and reach the decay quickly, because a long subby tail without a thud is a warm blob
([Ableton: Drop It](https://www.ableton.com/en/blog/drop-it-kick-electronic-music/)). The same article calls the 909 kick tougher in
attack and body, good with distortion and better at cutting through, and the 808 kick booming. Physically, a struck drum head starts high in pitch and falls as it decays, with a brief burst of high partials as the click
([Sound On Sound, Reid](https://www.soundonsound.com/techniques/synthesizing-drums-bass-drum)); a 909 kick is that recipe in electronics: a near-sine
oscillator with a pitch envelope plus a separate click and noise path ([Reid](https://www.soundonsound.com/techniques/practical-bass-drum-synthesis)).

Techno kicks mostly settle between **45 and 65 Hz**: Ableton's `Kick EQ` presets boost 45-65 Hz, a techno-mixing guide puts the body
near 65 Hz ([MusicGuy Mixing, weak](https://www.musicguymixing.com/?p=1616)), a house kick sits at 50-60 Hz
([Gearnews](https://www.gearnews.com/kick-and-bass-workshop-studio/)), and Drum Buss's Boom frequency spans 30-90 Hz
([Cycling '74](https://docs.cycling74.com/reference/abl.device.drumbuss~)).

### 1.2 Choosing a sample

| Check | Why | If it fails |
| --- | --- | --- |
| Tail to -40 dB under ~85 % of the beat (1.5) | overlapping tails smear the low end | shorten (Drum Sampler Decay, Gate) or pick another |
| Energy above ~300 Hz | EQ cannot boost what is absent ([Attack](https://www.attackmagazine.com/technique/tutorials/layering-kick-drum-samples/)) | add a click layer |
| Settled fundamental known | must be in key (1.4) | measure it (Agent box 1) |
| Mono | stereo bass is a phase risk | Utility Mono or Width 0 % |
| Not already squashed | pack kicks are often limited | tiny crest factor: add no more compression |

Candidates on this install (names found on disk, not auditioned; `search_browser`, category `drums`): `Kick 909 1/2`, `Kick 909 Click Layer`, `Kick 808 Click Layer`,
`Kick 49 Hz`, `Kick Sub 909 Long`, `Kick Rumble`, `Kick Analog 1`, Drum Essentials `Kick Rumble Low`, `Kick Xtra Low`, `Kick Impact Industrial`; kits `909 Core Kit`, `64 Pads Dub Techno Kit`;
Operator presets `BD 1 Kick`, `Smack Kick`, `Zapp Kick`. Pitch names in sample titles (`Kick Sub 808 Long A1`) probably use scientific octaves: measure before trusting.
Landry makes a new kick for every track, partly so two same-key tracks in a DJ mix do not stack the phases of one shared kick.

### 1.3 Layering click, body and sub

Give each layer one job ([Attack](https://www.attackmagazine.com/technique/tutorials/layering-kick-drum-samples/)). A worked Drum
Rack example ([Attack, Slave to the Rhythm](https://www.attackmagazine.com/technique/tutorials/slave-to-the-rhythm-essential-drum-techniques/)):

- **Sub**: a subby kick in Simpler Classic mode, attack about 4 ms, release a few hundred ms to set the tail. If a bass sits above,
  low-pass the sub near 80 Hz ([Attack, rolling bass](https://www.attackmagazine.com/technique/tutorials/warehouse-rolling-techno-bass/)).
- **Body/transient**: high-pass about 270 Hz, attack 0, decay about 350 ms, sustain -inf, so it adds only snap.
- **Click**: a hat or rim high-passed near 2.5 kHz, decay about 66 ms (the Core Library `Kick 909 Click Layer` is ready-made).
- Levels: the click and transient layers a dB or two under the sub layer in that example. In a two-kick rumble set-up the punchy kick is high-passed near 50 Hz and the long kick owns the
  sub ([Attack, Dark Techno Rumble](https://www.attackmagazine.com/technique/beat-dissected/dark-techno-rumble/)).

**Polarity and time first.** Two fat kicks can sum to a thin one. Align transients so it reads as one hit, then flip the polarity of one
layer and keep the fuller version (Attack). Utility has a phase-invert per channel and a `Phase Invert` preset. A no-ears test: pull one
layer's fader down; if the low end grows, that layer was subtracting ([Sonnox](https://sonnox.com/articles/drum-phase-alignment-when-to-nudge-flip-or-leave-alone)).
For a 55 Hz sine **[D]**: a 2 ms offset costs 0.5 dB, 4 ms 2.3 dB, 6 ms 5.9 dB, about 9.1 ms nulls it, and an inverted copy nulls it at
any offset. The first comb null for an offset *d* sits at 1/(2d): 1 ms nulls 500 Hz, 2 ms 250 Hz, 5 ms 100 Hz. So the click layer is far
more sensitive to a few samples of misalignment than the sub.

### 1.4 Synthesising a kick, and tuning it to the key

**Principle.** A sine or triangle, a fast pitch envelope, a zero-attack short-decay amplitude envelope. More pitch modulation and
a shorter amp envelope gives a 909 thud; less modulation and a longer release gives a smooth 808; a click comes from a short noise
burst or a filtered second oscillator ([Attack, Thorn](https://www.attackmagazine.com/technique/synth-secrets/how-to-make-your-own-kick-drums-using-thorn/),
[Diva](https://www.attackmagazine.com/technique/synth-secrets/how-to-make-your-own-kick-drums-in-diva/)). Free-running oscillators start at a
different phase each hit, so the click varies; for club kicks, render one hit and use the audio.

- **Operator** ([manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)): `Osc-A Wave` Sine with oscillators B-D off; `A Fix On` with `A Fix Freq` at the
  target Hz, or track the note and use `Transpose`; `Pe On` and `Osc-A < Pe` On with `Pe Amt A` 100 %. Pitch-envelope levels are in semitones: set `Pe Init` and `Pe Peak` so the effective start is about +24 to +38 st (2-3 octaves) above the base,
  `Pe Attack` 0.1 ms, `Pe Decay` **16-100 ms** (Ableton's presets use 16-42 ms; `02-synthesis-and-live-instruments.md` suggests 20-120 ms and `01-live-workflow.md` 40-100 ms; shorter reads as a thud, longer as a zap), `Pe Sustain` 0 st. Amp envelope: `Ae Attack` 0.1 ms, `Ae Decay` 45-400 ms (longer for 808 character), `Ae Sustain` -inf dB, `Ae Release` 50-150 ms,
  `Ae Mode` Trigger (ignores note-off). Ableton's own presets, read from disk: `BD 1 Kick` has Pe Init +12 st and Peak +48 st at 56 % amount, Pe Decay about 42 ms, oscillator A decay about 44 ms and release
  146 ms, a 13 ms filter envelope for the click, Transpose -13 st; `Zapp Kick` Pe Decay 16 ms, Pe Sustain -48 st, sine decay 2.5 s; `Smack Kick` oscillator A in Fixed mode with the pitch gliding from
  +38 st to -3 st over about 105 ms, 410 ms decay, a short 20 ms component near 790 Hz.
- **DS Kick** (Max for Live, [manual](https://www.ableton.com/en/live-manual/12/max-for-live-devices/)): `Pitch` is in Hz, the easiest
  kick to tune exactly; `Env` pitch modulation, `Decay` length, `Drive`, `OT` harmonics, `Attack` smooths the onset, `Click` adds a transient (labels from the manual: neither DS Kick nor Drum Sampler is in the 12.4.6 parameter dump, so **[verify]** the exact names with `get_device`).
- **Drum Sampler**: playback effects `Pitch Env` (-100..100 %, decay), `Sub Osc` (30-120 Hz), `Punch`; AHD envelope, Trigger or Gate mode **[verify names]**.
- **Drift** can do it (Osc 1 sine, Env 2 or the cycling envelope into pitch, +-100 %) but its manual documents no fixed-frequency mode: better for a sub layer.
- **Note length can matter.** `write_drum_pattern` writes one-step notes, which cut a long tail at note-off when the envelope follows the gate. Simpler: set `Trigger Mode` to Trigger (not Gate) and
  `Ve Mode` as needed; Operator: `Ae Mode` Trigger; Drum Sampler: Trigger. Otherwise write longer notes. Simpler also has its own pitch envelope (`Pe On`, `Pe < Env` in semitones, `Pe Decay`) that adds a
  pitch-drop thump to any sample.

**Tune the settled fundamental.** Convention: sub on the tonic; in techno often the fifth or the (minor) seventh degree, per an Attack
author's reply to readers ([Attack](https://www.attackmagazine.com/technique/tutorials/how-to-tune-kick-snare-tom-drum-samples/)). The bass can
state the same note an octave up: in one analysed track the kick sat on C# near 70 Hz and the bass leaned on C# near 140 Hz
([Attack](https://www.attackmagazine.com/technique/tutorials/tuning-drums-to-improve-your-mix/)). iZotope suggests tuning the kick to the key or moving bass
notes around its fundamental ([iZotope](https://www.izotope.com/community/blog/how-to-mix-kick-and-bass)). The Ableton-quoted engineer calls tuning
subjective because humans struggle with pitch "below 60 Hz"; but a sustained bass near the kick's pitch produces measurable beating (3.2).

| Live note (MIDI) | Hz | Live note (MIDI) | Hz |
| --- | --- | --- | --- |
| E0 (28) | 41.2 | C#1 (37) | 69.3 |
| F0 (29) | 43.7 | D1 (38) | 73.4 |
| F#0 (30) | 46.2 | D#1 (39) | 77.8 |
| G0 (31) | 49.0 | E1 (40) | 82.4 |
| G#0 (32) | 51.9 | F1 (41) | 87.3 |
| A0 (33) | 55.0 | F#1 (42) | 92.5 |
| A#0 (34) | 58.3 | G1 (43) | 98.0 |
| B0 (35) | 61.7 | G#1 (44) | 103.8 |
| C1 (36) | 65.4 | A1 (45) | 110.0 |

Scientific names (used by most articles) are one octave higher: Live A0 = scientific A1 = 55 Hz. Ableton's `Boom in A/C/E/G` Drum Buss presets set Freq to
55.0, 65.4, 41.2 and 49.0 Hz **[D, from the preset files]**, which confirms the Live naming. For A minor (NOVA): root A0 55 Hz, fifth E0 41.2 Hz, minor seventh G0 49 Hz.

Procedure: (1) measure the settled fundamental f0 (Agent box 1) or read it from a Hz-named sample; (2) semitones = 12 x log2(f_target/f0);
(3) Transpose = the whole part, Detune = the remainder in cents; (4) re-measure. Limits **[D]**: at 50 Hz one hertz is 34 cents and a 120 ms
window resolves about +-2 Hz, so verify to the semitone, not the cent. Large transposes degrade a sample
([Toolroom](https://toolroomacademy.com/4-ways-to-fix-your-low-end)); to hear tuning, transpose up an octave or two, fine-tune, transpose back (Attack). Drum
Buss's manual lists a `Force To Note` option for Boom (it snaps the resonant filter to the nearest MIDI note) that is not in the 12.4.6 parameter dump, so the tools cannot set it: type the note's Hz into `Boom Freq` (30-90 Hz).

### 1.5 Length versus tempo, and transient control

| BPM | Beat (ms) | 8th | 16th | Kicks/s | Tail to -40 dB (four-on-the-floor) |
| --- | --- | --- | --- | --- | --- |
| 100 | 600 | 300 | 150 | 1.67 | under about 510 ms |
| 120 | 500 | 250 | 125 | 2.00 | under about 425 ms |
| 130 | 462 | 231 | 115 | 2.17 | under about 390 ms |
| 150 | 400 | 200 | 100 | 2.50 | under about 340 ms |
| 180 | 333 | 167 | 83 | 3.00 | under about 280 ms |

**[D]** beat = 60000/BPM; the 85 % rule is a heuristic. A longer tail is fine if the bass is silent in the gap. Too short and the sub lacks
pressure; too long and it clashes with the bass ([Gearnews](https://www.gearnews.com/?p=246014)). Ways to shorten: Drum Sampler `Decay`/`Hold`;
Simpler Classic envelope; **Gate** (Hold, Release; Ableton's `Gated Drums` preset holds about 263 ms, releases 31 ms; one macro-gate used -20 dB
threshold, 0.2 ms attack, 95 ms release, [Attack](https://www.attackmagazine.com/technique/tutorials/making-your-own-techno-kick-mix-chain-using-waves-studiorack/));
a transient shaper with sustain pulled down while a separate sub layer carries the weight
([Attack](https://www.attackmagazine.com/technique/tutorials/warehouse-rolling-techno-bass/)).

**NOVA.** Tempo bands (`ears/specs/nova.spec.json`): LOW 100-120 BPM with kicks on beats 1 and 3 (this repo's `notes.kick_pattern` calls that
"half-time"), MID 130-150 four-on-the-floor, HIGH 160-180 (the spec names no kick pattern for it, `"kick": null`; the `ears` fixture that mirrors the set plays four-on-the-floor plus a pickup there, and the kick plays in all three
bands, absent only in tiers T1-T2). Samples do not follow tempo: design the kick for the fastest tempo in its band
(400 ms beat at 150, 333 ms at 180) or render per-band kicks.

**Transient tools in Live.** Drum Buss `Transients` works above 100 Hz: positive adds attack and sustain (punch), negative adds attack but cuts
sustain (tighter, less room) ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)). Compressor attack of 10-50 ms
lets the peak through (very short takes the life out); Glue attack 10 ms is the usual punch setting; Drum Sampler `Punch` ducks after a fixed attack;
a longer Simpler attack removes snap from a rumble layer.

---

## 2. Processing the techno and industrial kick

### 2.1 A chain, in order

| Stage | Starting values | Source |
| --- | --- | --- |
| 1 Clean-up (EQ Eight) | low cut 48 dB/oct at 30 Hz; wide bell +6 to +10 dB at 45-65 Hz; cut -4 to -6 dB between 190 and 490 Hz; optional +3 dB at 2-4 kHz or +3 to +6 dB near 10 kHz; high cut 12 dB/oct at 17-19 kHz | Ableton `Kick EQ 1-4` presets |
| 1b Other cuts | 250-300 Hz to let the sub emerge; -3 dB at 500 Hz; 180 Hz (narrow) and 500 Hz in an electro kick; cuts near 120 Hz and 800 Hz with a low shelf lifted near 80 Hz on a layered group | [Industrial](https://www.attackmagazine.com/technique/beat-dissected/industrial-techno/), [Rumble](https://www.attackmagazine.com/technique/beat-dissected/dark-techno-rumble/), [Cybotron](https://www.attackmagazine.com/technique/beat-dissected/how-to-make-an-electro-beat-inspired-by-cybotrons-clear/), [reverb kick](https://www.attackmagazine.com/technique/tutorials/adding-reverb-techno-kick/) |
| 2 Compress | Glue on the layered group, about 5 dB of reduction (it also accentuates the click); or 4:1, attack 27 ms, release 177 ms with the sidechain filter excluding the lows | [Attack](https://www.attackmagazine.com/technique/tutorials/adding-reverb-techno-kick/), [Lifeline](https://www.attackmagazine.com/technique/tutorials/mixing-techno-drums-with-excite-audios-lifeline-console/) |
| 3 Saturate | Saturator 5-7 dB drive, output down by a little less than the drive; or Drum Buss; or Roar (2.2) | [Attack, organised chaos](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/) |
| 4 Clip or limit | Limiter or clipper shaving the very top (release Auto). Aggressive: Limiter ceiling -12 dB, lookahead 6 ms, then Utility +12 dB and Mono | [Attack](https://www.attackmagazine.com/technique/tutorials/adding-reverb-techno-kick/), [Phase Fatale](https://www.attackmagazine.com/technique/beat-dissected/hypnotic-techno-inspired-by-phase-fatales-love-is-destructive/) |
| 5 Tune the sub, mono | Drum Buss `Boom` at the key (2.2); Utility `Bass Mono` or Width 0 % | manual |

Distortion softens the transient while raising perceived loudness: the metered peak falls, the loudness rises (Attack). Stage 4's aggressive limiter pattern is a trick for one kick sample: the same +12 dB into a low ceiling on every stem is what flattened the NOVA mix on 2026-10-08, so use stage 4 on the kick sound only, never as a loudness or per-stem treatment (`00-agent-playbook.md`, rules 7 and 8). Ableton's presets
use a steep 30 Hz cut; Landry prefers a shelf because she dislikes the low cut's timbre; one tutorial cuts softly as low as 11 Hz to keep the
rumble. Compare by the effect on attack and sub share, not habit. Style anchor: the drum track of NIN's "Closer" is built around a heavily modified
sampled drum-machine kick plus a Roland R-70 ([Wikipedia, weak](https://en.wikipedia.org/wiki/Closer_(Nine_Inch_Nails_song))): sample plus processing, not synthesis.

### 2.2 Drum Buss, Saturator, Roar

**Drum Buss** ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)). Parameters: `Trim` first; `Compressor On`, a fixed fast-attack,
medium-release compressor; `Drive` into `Drive Type` Soft (waveshaping), Medium (limiting) or Hard (clipping with bass boost); `Crunch` sine-shaped distortion of
mids and highs; `Damping Freq`, a low-pass after the distortion; `Transients` (-1..1); the resonant low-end enhancer `Boom Amt`, `Boom Freq`, `Boom Decay`, `Boom Audition`; `Dry/Wet`; `Output`.
A fresh device starts with Drive 20 % (Soft), Damping 9.2 kHz, Boom Freq 50 Hz, Boom Amt 0 %, Boom Decay 100 %: set Drive to 0 for sub-only use.

| Purpose | Settings | Source |
| --- | --- | --- |
| Sub reinforcement only | Comp off, Drive 0, Boom 45 %, Freq at the key (55 Hz for A), Decay 100 %, Trim -3 dB | Ableton `Boom in A/C/E/G`; Attack rumble: Boom 45 % at 55 Hz |
| Kit glue and punch | Comp on, Crunch 20-50 %, Transients +0.2 to +0.75, Trim -6 dB, Output -5 dB | `Drum Pumper`; [Cybotron](https://www.attackmagazine.com/technique/beat-dissected/how-to-make-an-electro-beat-inspired-by-cybotrons-clear/): Drive 25 %, Crunch 20 %, Boom 13 %, Damp 15.8 kHz, Output -5 dB, Wet 96 % |
| Kick presence | Crunch 0 %, Boom 57 % at 49 Hz, Damp about 6.8 kHz, Transients about +0.75 to +0.8 on the kick; drum group at -14 dB | [Silent Servant](https://www.attackmagazine.com/technique/beat-dissected/create-raw-hypnotic-techno-like-silent-servant/) |
| Group drive | Drive 17 %, Boom 45 % at 55 Hz, Output -3 dB | [Dark Techno Rumble](https://www.attackmagazine.com/technique/beat-dissected/dark-techno-rumble/) |
| Heavy | Hard, Drive 40-75 % with Trim cut to -15 to -20 dB, Boom Decay 15-30 % | `Punchy Driven`, `Squeeze & Drive in G` |

Trim and Drive interact (heavy presets pair high Drive with 15-20 dB less Trim), so judge distortion at matched output level. Boom is a pitched
resonance: tune it to the key or it adds a competing note. `Transients` is -1..1 in the API and reads "0.00", not a percentage: the sources' "+75 %"
is 0.75. Send the number (`{"Transients": 0.75}`); a string such as "75 %" is out of range and clamps silently to 1.0.

**Saturator** (`Type`, `Drive`, `Color On`, `Color Amt Low`, `Post Clip Mode`, `Output`): the Bass Shaper curve is smoother on low, high-gain material (808s, basses). **Color** applies an EQ before the shaper and its inverse after,
so bass can be kept out of the shaper and only mids and highs saturate; Post Clip caps output at the Output level. Presets `808 Shaper`, `Beat Clipper`, `Hard Punch`.
**Roar** ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/), [blog](https://www.ableton.com/en/blog/roar-meet-live-12s-new-processing-powerhouse/)):
three stages, twelve shapers, seven routing modes (Single, Serial, Parallel, Multi Band, Mid Side, Feedback, Delay; the mode is a device property that `get_device` lists, not a parameter). **Multi Band** (`Low Mid X-Over` 200 Hz
and `Mid High X-Over` 2 kHz by default) lets mids and highs saturate while the low band stays clean; Ableton's `Basic Multi Band` uses small Soft Sine amounts and 25 %
compression. A negative **Tone** (`Tone Amt`) with **Color Compensation** (`Color On`) saturates drums without losing low-end impact (the manual's own tip). Its compressor has a
sidechain high-pass (`Comp Hp On`) so bass does not drive it (on in every Roar preset I read). Presets: `Kick Me`, `Made for 808s`, `Drums Deep Bassliner`,
`Mono Drums Squasher`. Avoid Feedback "Note" mode on a kick unless you want a tuned ring. **Pedal** and **Overdrive** also suit drums.

**Do not saturate sums of pitched material.** A nonlinearity creates sum and difference tones between simultaneous notes, which are not in the chord
**[D]**; saturating pad, bass and kick together can sound out of tune. Saturate single voices, or only the band above the chord and bass register.

### 2.3 Parallel distortion with a clean low band (Audio Effect Rack)

Two chains on the kick bus (after [Attack](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/)):
**Dry** (EQ Eight to tame the sub, Saturator Drive about 7 dB with Output about -5 dB, a transient control) and **Drive** (a filter *before* the
distortion choosing what gets driven, a strong distortion, an EQ *after* it removing the sub so the dry chain owns the weight, then a Compressor
sidechained to the dry kick so the driven copy ducks when the dry kick plays). Distortion is also compression, so the dry blend restores the transients it removes.

### 2.4 The rumble kick

A rumble is a **separate copy** of the kick, filtered to the lows, sustaining under and between hits. The sources agree on this skeleton:

1. **Source**: a short tight main kick (so four-on-the-floor does not overlap) plus a copy of it, or a second longer kick with a soft attack
   ([Bonedo](https://www.bonedo.de/artikel/bass-drum-rumble-rattle-for-techno), [Attack](https://www.attackmagazine.com/technique/beat-dissected/dark-techno-rumble/)).
2. **Chain**: Bonedo: Delay, then Reverb, then a low-pass starting near **250 Hz**. Menzel: Reverb 75-100 % wet, Overdrive, EQ low-pass below about 300 Hz
   ([Production Music Live, weak](https://productionmusiclive.com/blogs/news/6-steps-to-create-that-rumbling-techno-kick-you-love-with-johannes-menzel)).
   Attack: long decay, generous wet, low-pass with raised resonance and drive just under 4 dB. Another: Delay unsynced, 50 % feedback and wet; Reverb decay 3.8 s at 68 % wet;
   high cut; Saturator Medium Curve drive 5.7 dB ([Paula Temple style](https://www.attackmagazine.com/technique/beat-dissected/dark-cinematic-hypnotic-techno/)).
3. **Distortion position** (Bonedo): before the delay it washes out; after the delay the delay rhythm is clearer; after the reverb it makes the wash louder; after the filter it regenerates harmonics.
4. **Duck it**: a Compressor last in the rumble path, sidechained to the **dry kick tapped Pre FX**, so the rumble drops out on each kick and swells between
   (Pre FX is the clean kick, Post FX the processed one, [Ableton blog](https://www.ableton.com/en/blog/sidechain-compression-part-2-common-and-uncommon-uses/)).
5. **Parallel, never inserted**: a return track, a duplicate track or a Rack chain. Bonedo's effect path measured about **8 dB** below the dry kick; start with rumble peaks
   6-10 dB under the kick **[heuristic]**.
6. **Mono**; resample a good result so every hit is identical, since reverb tails vary ([The Producer School, weak](https://theproducerschool.com/blogs/featured-blogs/how-to-create-techno-rumble-kicks-for-2025)).
7. **Rhythm**: the delay time sets the rumble's rhythm; for control give it its own track and MIDI (16ths, very low velocity on the beats). Menzel adds a low-passed ghost kick between the main kicks.
8. **Restraint**: keep the reverb filtered and low, since overdoing it wrecks a club system ([Attack, Rolling Techno](https://www.attackmagazine.com/technique/beat-dissected/rolling-techno/)); resonate it at the key with Drum Buss Boom; automate the send by only 1-2 dB
   over 8 bars (Bonedo). A short bright **top kick** keeps the kick present on small speakers.

Build in Live: `create_track("return", "Rumble", device="Reverb")`, `set_mixer("Kick", sends={"A": -8})`, devices after the reverb, and a Compressor via `set_sidechain`.

### 2.5 How loud should the kick be?

No authoritative source gives an absolute figure. The kick "wins" each hit and the bass yields (iZotope); in Attack's Live examples the drum group sits at **-10 to -14 dB** on the fader with Main at **-6 dB**; raise the
bass from silence until you feel it rather than hear it ([Attack, Operator bass](https://www.attackmagazine.com/technique/synth-secrets/rumbling-techno-bass-ableton-operator/)). Take absolute levels from the user's
references with `compare`, and check the sub and low band shares (Agent box 3), not a fixed number.

> **For an agent, 1: build and measure a kick.**
> 1. Audition: `search_browser("kick", category="drums")`; `load_from_browser(track, uri=..., drum_pad="C1")`. Layers: one pad each, same pattern (name chains with `set_chain(name=...)`), or an Instrument Rack in a pad.
> 2. Pattern in the **arrangement**, because `bounce` renders the arrangement: `create_clip("Drums", at="1.1.1", length="2 bars", pattern={"Kick": "x---x---x---x---"})`; set the level with
>    `write_drum_pattern(track, pattern=..., arrangement_clip=<index from get_arrangement>, velocities={"x": 118})`. Keep four-on-the-floor kick velocity constant.
> 3. `bounce(stems=["Drums"], end="3.1.1", name="kick-test")`, `get_bounce_status(wait=50)` (returns the file paths), `analyze_audio(path)`. Read `levels.sample_peak_dbfs`, `crest_factor_db`,
>    `spectrum.sub/low/low_mid` (0-60, 60-250, 250-2000 Hz) and `stereo.width` (about 0 for a mono kick). Almost no `low_mid` and above means no click.
> 4. Pitch and tail (repo's `ears` package, run from the repo root; tested on a synthetic kick):
>    ```python
>    import numpy as np
>    from ears import audio, measure
>    def kick_report(path, bpm):
>        a = audio.read(path); x = a.mono(); sr = a.rate
>        s0 = int(float(measure.onsets(a)[0]) * sr)                                   # first hit
>        seg = x[s0 + int(.10*sr): s0 + int(.22*sr)] * np.hanning(int(.12*sr))          # after the pitch drop
>        spec = np.abs(np.fft.rfft(seg, n=4*sr)); f = np.fft.rfftfreq(4*sr, 1/sr); band = (f > 25) & (f < 130)
>        w = int(.005*sr); rms = np.sqrt(np.convolve(x**2, np.ones(w)/w, "same"))
>        hit = rms[s0: s0 + int(60/bpm*sr)]; below = np.where(hit < hit.max()*10**(-40/20))[0]
>        return {"fundamental_hz": round(float(f[band][np.argmax(spec[band])]), 1),
>                "tail_ms_to_minus40dB": round(1000*below[0]/sr) if len(below) else None, "beat_ms": round(60000/bpm)}
>    ```
>    A tail of `None` or over ~85 % of `beat_ms` runs into the next kick. The fundamental is good to about +-2 Hz.
> 5. Layer polarity: bounce twice with one layer's Utility phase invert (`Left Inv` and `Right Inv`) off and on, same gains (do not loudness-match this pair: the level difference is the signal); keep the version with the higher `levels.rms_dbfs` and `sample_peak_dbfs`. `spectrum.sub.db` is only the sub band's share of the file's total energy, so it moves less than the level does.
> 6. **Ask the human** about kick character, distortion and rumble amount: two bounces, loudness matched within 0.2 LU (0.3 LU at most), labelled "A baseline" and "B +rumble", with what changed in numbers. Never replace Fred's chosen kick: add on top and A/B.

---

## 3. Kick and bass together

### 3.1 Frequency slots

| Zone | Hz | Owner | Notes |
| --- | --- | --- | --- |
| Rumble, DC | below 25-30 | nobody | inaudible, eats headroom: low-cut kick and bass |
| Sub fundamental | 30-60 | kick's settled pitch (and its sub layer) | mono |
| Low body | 60-120 | kick body or bass fundamental: one at a time | mono below 120 |
| Boxy | 150-500 | cut in both (kick -4 to -6 dB) | before any sidechain |
| Click | 2-5 kHz | kick top layer | hats sit well above |

Kick and bass share roughly 20-160 Hz, so the kick takes the fundamental and the bass is EQed around it
([iZotope](https://www.izotope.com/community/blog/how-to-mix-kick-and-bass)). A warehouse-bass recipe: kick bell cut of 4.5 dB at 98 Hz (where the bass lives); sub layer low-passed at 80 Hz, 12 dB/oct; main bass high-passed at
65 Hz, low-passed at 350 Hz, small cut at 100 Hz; and **the first sixteenth of every beat left empty** so the bass avoids the kick
([Attack](https://www.attackmagazine.com/technique/tutorials/warehouse-rolling-techno-bass/)). Another bass keeps every note start off the kick positions
([Attack, Operator bass](https://www.attackmagazine.com/technique/synth-secrets/rumbling-techno-bass-ableton-operator/)). A techno-mixing guide also ducks the kick's ~150 Hz band when the bass plays (weak).

### 3.2 Pitch relationships: beating and the low interval limit

Two sines a few hertz apart beat at the difference frequency ([beat](https://en.wikipedia.org/wiki/Beat_(acoustics))). The ear's filters are wide at low frequency: the Glasberg-Moore approximation gives an equivalent
rectangular bandwidth of about **30-35 Hz** for 40-100 Hz ([ERB](https://en.wikipedia.org/wiki/Equivalent_rectangular_bandwidth); stated for 100 Hz and up, so this is an extrapolation). Tones closer than that are heard as roughness or beating, not as two pitches **[D]**:

| Above a root of A0 (55 Hz) | Hz | Difference | Difference / ERB (about 31 Hz) |
| --- | --- | --- | --- |
| minor 2nd | 58.3 | 3.3 | 0.11 |
| major 2nd | 61.7 | 6.7 | 0.22 |
| minor 3rd | 65.4 | 10.4 | 0.34 |
| major 3rd | 69.3 | 14.3 | 0.46 |
| 4th | 73.4 | 18.4 | 0.59 |
| 5th | 82.4 | 27.4 | 0.88 |
| octave | 110 | 55 | 1.8 |

By this derived argument, under about 110 Hz only the root, its octave and (carefully) the fifth read as clean intervals. **A third between sine-like notes at 55-65 Hz is a beating mess, not a chord**: it is why a pad whose thirds land at 55-65 Hz under the bass sounds like
"wrong notes or tuning". (Harmonic-rich notes also carry upper partials that name the chord, but their fundamentals still beat and muddy the sub.) The house rule keeps a margin on top of the derivation: below about 130 Hz (Live C2) only roots, fifths and octaves; major thirds from about 165 Hz (Live E2); minor thirds and seconds higher still; the lowest sounding note is the chord root (`08-arrangement-and-composition.md`). Rules:

- One sustained pitch below ~100 Hz at a time, doubled only at the octave. Pads and chords: voice above C2 (about 130 Hz) with only roots, fifths and octaves below it and major thirds from E2 (about 165 Hz), or high-pass them around 150 Hz; see `08-arrangement-and-composition.md`.
- Kick fundamental = bass root (or fifth), never a semitone or tone from a sustained bass note: 52 Hz against a sustained 55 Hz beats at 3 Hz.
- **Detune and unison belong above ~150 Hz.** 20 cents is 0.64 Hz at 55 Hz and 1.3 Hz at 110 Hz **[D]**, a slow wobble in the sub. Keep the sub a mono sine or triangle; put unison, chorus and saturation on the layer above.
- **Two bass layers**: same fundamental and start phase (retrigger/phase reset on), polarity checked as in 1.3. Two panned copies of the same patch cancel in mono; use comparable but different sounds
  ([Attack](https://www.attackmagazine.com/technique/tutorials/mono-safe-stereo-width/)).
- A lower key puts the bass on lower notes (an Attack loop moved from E to C for weight), but dropping an instrument a whole octave can degrade it
  ([Attack](https://www.attackmagazine.com/technique/passing-notes/choosing-keys-for-bass-weight/)).

### 3.3 Sidechain compression and ducking

Put a Compressor on the bass (or pad, or mix bus) and pick the kick track as the sidechain source. The Compressor can also band-limit its trigger (`S/C EQ On`, `S/C EQ Type` incl. Low pass and High pass, `S/C EQ Freq`) and has
`S/C Listen`; automatic makeup is off with an external sidechain ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)). A Compressor added with `add_device` starts (12.4.6 dump) at 4:1, attack 1 ms, release 30 ms, knee 6 dB, `Model` RMS,
`LookAhead` 0 ms, with `S/C EQ On` already On (`S/C EQ Type` High pass, `S/C EQ Freq` 80 Hz), so a kick key loses its sub until you switch that off or pick another type. To trigger from the kick inside a full drum mix, keep `S/C EQ On` and choose the Low pass type (the manual's tip is a low-pass on the key; the 150 Hz start is this digest's) and use `S/C Listen` to check what is triggering. The second chooser sets **Pre FX, Post FX or Post Mixer**, and for a Drum Rack source the whole rack or one chain
([Ableton blog](https://www.ableton.com/en/blog/sidechain-compression-part-2-common-and-uncommon-uses/)).

| Goal | Attack | Release | Ratio | Depth | Source |
| --- | --- | --- | --- | --- | --- |
| Transparent clearance | 2-5 ms | start ~20 ms, raise until the whole kick passes | 2-4:1 | 1-3 dB | [Toolroom](https://toolroomacademy.com/4-ways-to-fix-your-low-end), [Gearnews](https://www.gearnews.com/kick-and-bass-workshop-studio/) |
| Techno pump | 1-10 ms | 30-300 ms, open before the next kick (at most 60000/BPM; 200-350 ms at 128 BPM) | 4:1-10:1 | 6-12 dB | [Gearnews](https://www.gearnews.com/sidechain-compression-in-techno-workshop/) |
| Educator numbers | punchy 3-4 ms; natural about 30 ms | punchy 16-60 ms; natural about 250 ms | 4-5:1 (2:1 subtle, up to 12:1) | 2-3 dB subtle | EDMProd, as summarised in `01-live-workflow.md`; it also high-passes the trigger |
| Split bass | n/a | n/a | n/a | 8-12 dB on 20-200 Hz; 2-4 dB on 200 Hz-2 kHz | Gearnews |
| MCP default | 1 ms | 120 ms | 4:1 | threshold -24 dB | `set_sidechain` |
| Rumble or reverb return | under 1 ms | 0.6-0.9 x beat | 10:1 or limiter | full duck | heuristic; Bonedo and Menzel give no numbers |

Very fast attack with a high ratio clicks; try 2-5 ms attack, a low-passed bass, a softer ratio or the Compressor's lookahead (0, 1 or 10 ms). Sidechain complements frequency separation, it does not replace it (Gearnews). In heavy dark techno
it is common to duck pads and reverb clouds with the whole kit in Peak mode, not just the kick (Ableton blog).

**EQ Eight has no dynamic bands.** To duck only the sub, split the bass: a **Sub** track (mono sine or triangle, below ~100 Hz) and a **Mid** track (the rest), with the strong sidechain on Sub only. The MCP routes sidechains only for the
Compressor; `set_sidechain` accepts a `device` path (inside a rack chain too **[verify]**).

**Release from tempo [D]:** beat = 60000/BPM (462 ms at 130). Keep release at or under ~80 % of the beat; 150-300 ms covers 125-145 BPM.

**Stems that can play without the kick (NOVA).** The kick plays in every tempo band (LOW, MID and HIGH) but joins only at tier T3, so it is absent in tiers T1-T2, while the bass joins at T2. Kick-triggered ducking baked into the bass stem therefore pumps in tier T2, where the kick is not playing, and sounds like missing kicks (the same holds for a pad or arp stem in T1). Prefer composed spacing (empty first sixteenth,
shorter note ends, a volume envelope per note), with any baked ducking small (about 1-3 dB) unless the pulse is itself the rhythm. Whether a muted ghost-kick track still drives a Pre FX tap is **[verify]**.

### 3.4 Polarity, phase, alignment

Polarity is a binary fix, time offset a linear one, phase rotation a frequency-dependent one: check polarity first, then nudge in time. A hollow spot near 250 Hz implies about 2 ms of offset; summing to mono is the stress test
([Sonnox](https://sonnox.com/articles/drum-phase-alignment-when-to-nudge-flip-or-leave-alone)). Alignment can also be done by overlaying waveforms and shifting the bass in time or phase
([Armada University](https://www.armadamusic.com/university/music-production-articles/how-to-mix-your-kick-and-bass-5-must-know-methods)). Keep bass attacks and kick transients aligned in techno for PA impact; looser suits funk
([Gearnews](https://www.gearnews.com/kick-and-bass-workshop-studio/)). Re-check after changing chains (latency).

### 3.5 Mono low end

Utility's **Bass Mono** (`Bass Mono` On, `Bass Freq`, 120 Hz on a fresh device) sums everything below the chosen frequency (50-500 Hz) to mono, with an audition button; `Stereo Width` 0 % or `Mono` collapses the whole signal; `Left Inv`/`Right Inv` flip polarity
([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)), matching the advice to keep kick and bass mono below 120 Hz ([Armada](https://www.armadamusic.com/university/music-production-articles/how-to-mix-your-kick-and-bass-5-must-know-methods))
and this project's check (mono-sum loss below a 120 Hz crossover, tolerance 1 dB). Alternatives: EQ Eight in M/S mode with a steep low cut on Side at 120 Hz; Utility Width 0 % on the kick
([Toolroom](https://toolroomacademy.com/4-ways-to-fix-your-low-end)). Keep the kick fully mono; the bass can be wide above the crossover. Clubs and phones fold to mono or lose the sub, so the groove must also live in the click and in bass
harmonics above ~200 Hz (the project's phone check high-passes at 200 Hz). Counterexample: Gearnews cites a stereo sub in a Nine Inch Nails track ("Where Is Everybody?") made to work by careful writing and engineering.

> **For an agent, 2: slot kick and bass.**
> 1. Fundamentals: f = 440 x 2^((midi-69)/12). List simultaneous sustained pitches below ~165 Hz (Live E2); flag any pair that breaks the low-register rule (3.2: below ~130 Hz only roots, fifths and octaves; major thirds from ~165 Hz) or whose difference is under ~30 Hz.
> 2. `analyze_notes` after each note edit (kick pattern, density, clashes); leave the first sixteenth of each beat empty in the bass where the kick plays.
> 3. Duck: at 130 BPM, `set_sidechain("Bass", "Kick", channel="Pre FX", threshold_db=-28, ratio=4, attack_ms=3, release_ms=320)` (release about 0.7 x beat), then move the threshold until gain reduction is 3-6 dB (transparent) up to about 8 dB (obvious pump; `06-mixing.md` uses 4-8 dB for bass) on bass notes that
>    coincide with the kick. `set_sidechain` leaves the Compressor's `S/C EQ On`, `S/C EQ Type` and `S/C EQ Freq` as found, and a fresh one has an 80 Hz high-pass on the key (3.3). Isolate the trigger: the kick on its own track (or its Drum Rack chain, if the chooser lists it **[verify]**); a whole drum track also triggers on hats and claps. In the NOVA stems prefer composed gaps and keep any baked ducking small (3.3): tiers T1-T2 play without the kick.
> 4. Mono: Utility last in the bass chain: `set_device_parameters("Bass", "Utility", {"Bass Mono": "On", "Bass Freq": "120 Hz"})`. Check `analyze_audio(take="latest")`: `audio.mono_sub` loss under 1 dB, and kick-bass masking in the 40-125 Hz third-octaves.
> 5. Measure the duck: bounce the bass alone over a sustained note and call `analyze_audio(path, sections=[{"name": "after", "start": t, "end": t+0.08}, {"name": "before", "start": t+beat-0.08, "end": t+beat}])`, where `t` is a kick time in seconds.
>    The `rms_dbfs` difference is the effective duck depth; "before" should be back within ~0.5 dB of the un-ducked level (recovery).
> 6. Polarity probe: bounce kick+bass twice, same gains, with the bass polarity flipped (Utility `Left Inv` and `Right Inv`); keep the version with the higher `levels.rms_dbfs` and `loudness.integrated_lufs` (do not loudness-match this pair; `spectrum.sub.db` and `low.db` are shares of the total, so they move less).
> 7. One change per bounce. If the human hears "wrong notes", suspect 3.2 first (a sustained pitch pair, chords under ~165 Hz, saturation on a sum).

---

## 4. Drum bus and percussion

### 4.1 Bus structure, Glue and parallel

Kick and bass can be bussed together to glue the low end, or the kick can join the full drum bus; both work and the kick can feed both
([Attack Q&A](https://www.attackmagazine.com/technique/beat-dissected/grinding-analogue-techno/)). `create_bus(name, sources)` routes tracks into a new audio track; Drum Rack return chains (up to six) give per-pad sends inside one rack
([manual](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/)).

Glue is an SSL-style bus compressor with stepped controls. `Attack` steps 0-6 = 0.01, 0.1, 0.3, 1, 3, 10, 30 ms; `Release` 0-6 = 0.1, 0.2, 0.4, 0.6, 0.8, 1.2 s, Auto; `Ratio` 0-2 = 2, 4, 10 **[D: decoded from the presets; a fresh device sits on
Attack 1, Ratio 4, Release .6, the middle steps, which fits; the 12.4.6 dump lists no items for these three (raw 0-6, 0-2 and 0-6), so send the raw step as a number and read the display back]**. `Range` limits the compression (the API shows it as a positive 0-70 dB, 70.0 by default; a negative value clamps to 0 dB, which allows no compression at all); `Output` is the makeup gain (0 to +20 dB); `Peak Clip In` is the soft clipper, off unless you want its colour. Ableton warns that more than
about 6 dB of gain reduction significantly changes the sound (manual).

| Purpose | Ratio / attack / release | Depth and level | Source |
| --- | --- | --- | --- |
| Gentle two-bus | 2:1, 30 ms, Auto | 2-3 dB | Ableton `Drum - Gentle Two Buss`; [Spastik](https://www.attackmagazine.com/technique/beat-dissected/spastik-style-percussive-techno/) |
| Punch | attack 10 ms, release 0.2 s | about 4 dB, makeup 1.75 dB set by A/B | [Cybotron](https://www.attackmagazine.com/technique/beat-dissected/how-to-make-an-electro-beat-inspired-by-cybotrons-clear/) |
| Clamp and grit | 4:1, 0.3 ms, 0.4 s | threshold -16 to -20 dB, makeup +6 dB, wet 35-80 % | [Dave Clarke](https://www.attackmagazine.com/technique/beat-dissected/how-to-program-techno-like-dave-clarke/), [Paula Temple](https://www.attackmagazine.com/technique/beat-dissected/dark-cinematic-hypnotic-techno/) |
| Parallel | 2:1, 3 ms, 0.1 s | threshold about -17.5 dB, makeup about +8 dB, wet 50 % | Ableton `Drum - Full Parallel` |

General: fast attack, moderately fast or auto release, 2:1-4:1, nudge the peaks by a few dB, or squash a sparse part hard for effect
([Attack](https://www.attackmagazine.com/technique/tutorials/ten-tips-better-drums/)). Transparent parallel: very low threshold (near-continuous reduction), fastest attack, release about 300 ms, ratio about 2.5:1, Peak mode, then blend
([Attack](https://www.attackmagazine.com/technique/tutorials/parallel-compression/)). Always match compressed and bypassed levels before judging.

### 4.2 Hats, percussion, snare and clap

| Element | EQ | Level, pan, behaviour |
| --- | --- | --- |
| Closed hat | 12 dB/oct low cut at 244-321 Hz (Ableton `Hat EQ`; 317 Hz in Cybotron); up to ~1.6-1.8 kHz when layered or under rolls; tame a 2-6 kHz bell | -8 to -13 dB under the kick pad in Attack's examples; pan 7-17 % off centre; velocity at most ~70 % |
| Open hat | darker low-pass, high-pass near 300 Hz | -10 dB; choke with the closed hat; decay shorter on the first hit, longer on the second |
| Ride | high-pass near 1 kHz | 8ths, every second hit shorter and quieter; ducked by the kick; one example at -24 dB |
| Shaker | 24 dB/oct high-pass, medium resonance | offbeat or every second offbeat |
| Clap, snare | low cut 90-100 Hz (`Snare EQ`); body +3.6 to +6 dB at 180-230 Hz; presence 3.5-7 kHz | claps take 7-10 % reverb and delay without muddying |
| Toms (rolling) | low-pass each with resonance, three alternating pitches | under the kick; lower velocity where they coincide with kick or hat |

From Ableton's EQ Eight `Drums` presets, [Live Hi-Hats](https://www.attackmagazine.com/technique/beat-dissected/live-hi-hats/), [Spastik](https://www.attackmagazine.com/technique/beat-dissected/spastik-style-percussive-techno/),
[Industrial](https://www.attackmagazine.com/technique/beat-dissected/industrial-techno/), [Rolling Techno](https://www.attackmagazine.com/technique/beat-dissected/rolling-techno/) and [Silent Servant](https://www.attackmagazine.com/technique/beat-dissected/create-raw-hypnotic-techno-like-silent-servant/).
Pad dB figures depend on each sample's level: use them as relative hints and check meters. A real hi-hat cannot be open and closed at once, so give hats one **choke group** (`set_chain(..., choke_group=1)`); Live's 909 Core Kit already does.

### 4.3 Reverb, delay, gating, stereo

- Short and low: Hybrid Reverb on a clap, 200 ms decay, 7 % wet ([Attack](https://www.attackmagazine.com/technique/tutorials/in-the-red-mixer-distorted-90s-techno-drums/)); Drums Room, 710 ms decay, input low cut 3.76 kHz, ~8 % wet (Cybotron);
  reverb plus delay near 10 % wet on claps (Rolling Techno). Natural pre-delay is 1-25 ms (manual). Cut the reverb's lows.
- Dark techno: a clap only on the second kick of each bar, short dark chamber or spring reverb, a decay that eases into the next kick ([Attack](https://www.attackmagazine.com/technique/beat-dissected/dark-berlin-techno/)).
- Reverb without wash: sidechain-compress the return (threshold about -13 dB, extremely fast attack, moderate release, heavy ratio) ([Attack](https://www.attackmagazine.com/technique/tutorials/compressing-reverbs-for-clarity/)).
- Industrial snare: noise-based, on 2 and 4, driven, presence cut to soften the attack (Industrial). A gated tail is Reverb into Gate; start from `Gated Drums`.
- Stereo: kick, snare/clap and sub centred; hats and shakers a little off centre; high-frequency percussion to a convolution reverb with ping-pong delay for depth ([Rumble](https://www.attackmagazine.com/technique/beat-dissected/dark-techno-rumble/)).
  To widen a centred hit, pan two copies with up to ~20 ms between them and keep a mono copy, then check the mono sum ([Attack](https://www.attackmagazine.com/technique/tutorials/mono-safe-stereo-width/)).

> **For an agent, 3: drum bus and balance.**
> 1. `create_bus("Drum Bus", ["Kick", "Clap", "Hats", ...])`; `add_device` Drum Buss and Glue Compressor; then for example
>    `set_device_parameters("Drum Bus", "Drum Buss", {"Compressor On": "On", "Drive": "17 %", "Boom Amt": "45 %", "Boom Freq": "55 Hz", "Output": "-3 dB"})`; read the echoed `display` values back.
>    Or start from factory presets (`search_browser("Drum Pumper")`, `Boom in A`, `Drum - Gentle Two Buss`).
> 2. After every change, trim `Output` (Drum Buss, Glue Compressor and Compressor all have one; the Compressor's `Makeup` is only an automatic On/Off) until the bounce's integrated loudness is within 0.2 LU (0.3 LU at most) of the previous one, then judge.
> 3. Over-compression: bounce with the compressor on and off. If `levels.crest_factor_db` falls by more than ~3 dB, or gain reduction sits above ~6 dB, back off.
> 4. Low-end balance: `analyze_audio` on drums+bass: `spectrum.sub.db` minus `spectrum.low.db` (band values are shares of the file's total energy, so compare band to band, not absolute), `stereo.correlation` (clearly positive for a
>    mono-ish low end), `loudness.true_peak_dbtp`. Compare with a reference via `compare(take, "refs")`; differences under ~0.5 dB are noise here (`compare_noise_db`).
> 5. No loudness limiter per stem to hit a target; in a song (not the NOVA stems, which must work in every subset) one safety limiter on the drum bus catching under ~2-3 dB is enough.

---

## 5. Groove, patterns and pace

### 5.1 Swing

Swing delays every second step. Convention (MPC, Logic, Reason and Live's Swing grooves): **50 % straight, about 66.7 % triplet shuffle**; 4 % steps are just audible ([Attack](https://www.attackmagazine.com/technique/passing-notes/daw-drum-machine-swing/)).
Starting point for techno: 55-60 %, enough to loosen without sounding sloppy ([Attack, Belleville Techno](https://www.attackmagazine.com/technique/beat-dissected/belleville-techno/)); hats from straight to ~65 %, different swing per element, the kick straight
([Grinding Analogue Techno](https://www.attackmagazine.com/technique/beat-dissected/grinding-analogue-techno/)).

Live 12.4 groove files (read from disk) are named by percent with 50 straight: `Swing 16ths 52, 54, 57, 59, 61, 64, 66, 68, 71, 73` (also 8ths, 32nds), `Swing Logic 16ths 51-74`, `Swing MPC 3000 16ths 54-74`, `Swing SP 1200 16ths 54-71`,
accent grooves `Swing MPC Double Up/Down/Funker 16ths 55/60/70`, style grooves such as `House Subtle Swung 16ths`, and `Quantize 16`. Use 16th grooves on 16th patterns
([Attack](https://www.attackmagazine.com/technique/tutorials/jack-your-tracks-with-swing/)). Groove Pool ([manual](https://www.ableton.com/en/live-manual/12/using-grooves/)): `Base`, `Quantize`, `Timing` (how much of the groove applies; with
`Swing 16ths 64`, 100 % gives 64 % and 50 % gives ~57 %, [Attack](https://www.attackmagazine.com/technique/tutorials/going-off-grid-what-is-swing-and-how-to-add-it/)), `Random`, `Velocity` (-100..100 %), `Global Amount` (to 130 %, `set_song(groove_amount=...)`).
A groove applies to a whole clip: to groove one voice differently, extract its pad (`device_action(track, "Drum Rack", "to_midi_track", {"pad": "D1", "name": "Snare"})`).

**In the MCP.** `write_drum_pattern(swing=s)` and `transform_notes(operation="quantize", swing=s)` take `s` in 0..1 and delay every second step by `s` x half a step: **percent = 50 + 25 x s [D, from the code]**: s = 0.16 is 54 %, 0.32 is
58 %, 0.67 is the triplet shuffle (66.7 %) and 1 is 75 %. `get_grooves`, `set_groove` and `set_clip(groove=...)` work on the pool; the API cannot remove a clip's groove once set, and loading a groove file into the pool through the MCP is **[verify]**.

| Swing % | MCP `s` | Delay at 100 BPM | 130 BPM | 160 BPM |
| --- | --- | --- | --- | --- |
| 52 | 0.08 | 6.0 ms | 4.6 ms | 3.8 ms |
| 54 | 0.16 | 12.0 ms | 9.2 ms | 7.5 ms |
| 57 | 0.28 | 21.0 ms | 16.2 ms | 13.1 ms |
| 60 | 0.40 | 30.0 ms | 23.1 ms | 18.8 ms |
| 64 | 0.56 | 42.0 ms | 32.3 ms | 26.3 ms |
| 66.7 | 0.67 | 50.0 ms | 38.5 ms | 31.3 ms |

**Project constraint:** `analyze_notes` warns for notes more than 10 ms off the 16th grid. Baked swing of about BPM/30 points above 50 trips it (4.3 points, 54.3 %, at 130 BPM). A pool groove keeps note starts on the grid; otherwise accept the warning or stay within tolerance.

### 5.2 Velocity, ghost notes, chance, micro-timing

- **Kick**: constant and near full for four-on-the-floor; timing carries the groove ([Low End Theory](https://www.attackmagazine.com/technique/beat-dissected/low-end-theory/)). Vary only ghost kicks.
- **Closed hats**: offbeat closed hat at no more than ~70 % velocity ([Rumble](https://www.attackmagazine.com/technique/beat-dissected/dark-techno-rumble/)); in 16ths, accent the offbeat eighths, play the on-beats lower, ghost the rest. An open hat on the 2nd and 4th
  quarters with a few removed, the second-quarter hit pushed slightly late at about 50 % velocity ([Rolling Techno](https://www.attackmagazine.com/technique/beat-dissected/rolling-techno/)). Double a hit or mute one now and then ([Belleville](https://www.attackmagazine.com/technique/beat-dissected/belleville-techno/)); automate attack or
  decay slightly per hit ([Live Hi-Hats](https://www.attackmagazine.com/technique/beat-dissected/live-hi-hats/)).
- **Ghosts**: a ghost kick a sixteenth before beats 2 and 4 (the "pendulum"), low-velocity ghost claps around the main ones, two off-grid ghost kicks with slightly different offsets (Rolling, Grinding). Typical ghost velocity: 40-60 of 127 **[heuristic]**.
- **Chance and deviation**: notes carry `Chance` (0-100 %) and `Velocity Deviation` ([manual](https://www.ableton.com/en/live-manual/12/editing-midi/)); a Warp-style perc sets most 16ths to 10 % with a -50 velocity range
  ([Attack](https://www.attackmagazine.com/technique/beat-dissected/midi-probability-drums-inspired-by-warp-records-in-ableton-11/)). `write_notes` takes `probability` and `velocity_deviation`; `transform_notes(operation="humanize", timing="5ms", velocity=8, seed=1)` is repeatable.
- `write_drum_pattern` has three velocities per call (`x` 100, `X` 127, `o` 60 by default): one call per role, with `mode="add"`.
- **Offsets**: keep the main kicks rigid as the reference. Claps spread by Track Delay of about -9 and +5 ms ([Attack](https://www.attackmagazine.com/technique/tutorials/jack-your-tracks-with-swing/)); a tambourine a few ms before the snare. The MCP does not expose Track Delay, so offset
  note starts (beats = ms x BPM/60000; 10 ms = 0.022 beat at 130 BPM) or use the pool. Keep any single offset under ~25 ms.

**Research is mixed and not about electronic music.** Perfectly quantised drum patterns got the highest groove ratings in two studies (deviations of 15-25 ms rated worse) ([Davies and Fruhauf, as summarised by Senn et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5050221));
Senn et al. found quantised and expert-timed swing and funk equally groovy and exaggerated deviation worse; experts moved more to timing reduced by 60 % than to fully quantised ([Kilchenmann and Senn](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2015.01232/full)).
Medium syncopation gave the most urge to move and pleasure, an inverted U ([Witek et al. 2014](https://research.birmingham.ac.uk/en/publications/syncopation-body-movement-and-pleasure-in-groove-music/)). So exact quantisation is not by itself "lifeless": life comes from velocity, timbre variation
and moderate syncopation, and large offsets hurt.

### 5.3 Pattern library (16 steps, step 1 = beat 1; x hit, X accent, o ghost)

| Style | Lanes | Notes |
| --- | --- | --- |
| Four-on-the-floor | Kick `x---x---x---x---`; Clap `----x-------x---`; Open hat `--x---x---x---x-`; Closed hat `xoXoxoXoxoXoxoXo`; Ride `X-x-X-x-X-x-X-x-` | clap on 2 and 4; offbeat open hat; 16th hats accented on the offbeat eighths |
| Rolling techno | Kick `x--ox---x--ox---`; Clap `----x--o----x--o`; Open hat as above; Closed hat 16ths; filtered toms on 16ths | ghost kicks before beats 2 and 4; busy 16th low end |
| Industrial | Kick 4/4; Closed hat `--x---x---x---x-`; Shaker `------x-------x-`; Noise snare `----x-------x---`; driven toms | distortion, bitcrushing, toms ducked where they meet kick or hat |
| EBM backbeat | Kick `x---x---x---x---`; Snare `----x-------x---`; hats 8ths or 16ths; sequenced 16th bass pulse | 4/4 disco beat or backbeat, minor syncopation, repetitive sequenced bass ([Wikipedia, weak](https://en.wikipedia.org/wiki/Electronic_body_music)) |
| Half-time (NOVA LOW) | Kick `x-------x--o----`; Clap `----x-------x---`; Hat 8ths | `notes.kick_pattern` calls kicks on beats 1 and 3 "half-time" |
| Dark Berlin | Kick 4/4; Clap only on the 2nd kick of the bar; noise stab on the 3rd kick; compressed open hat on offbeats | sparse, loose |
| Break-flavoured | Snare `----x--x-x--x--x` over a 4/4 kick and a clap on every beat | ([Phase Fatale](https://www.attackmagazine.com/technique/beat-dissected/hypnotic-techno-inspired-by-phase-fatales-love-is-destructive/)) |

```
create_clip("Drums", slot=0, length="1 bar", pattern={"Kick": "x--ox---x--ox---", "Clap": "----x--o----x--o", "Open Hat": "--x---x---x---x-"})
write_drum_pattern("Drums", slot=0, mode="add", pattern={"Closed Hat": "xoXoxoXoxoXoxoXo"}, velocities={"X": 100, "x": 80, "o": 50}, swing=0.16)
```

Lane names must match the Drum Rack's pad names or General MIDI aliases (kick 36 = C1, snare 38 = D1, clap 39 = D#1, closed hat 42 = F#1, open hat 46 = A#1, crash 49 = C#2, ride 51 = D#2). Each lane loops on its own length, so a 12- or 15-step lane against a 16-step kick gives
a polymetric loop. The first Drum Rack pad is C1 = 36; `get_devices(track)` lists the non-empty pads. `set_chain(..., in_note=...)` moves a chain to another pad; `out_note` is the note sent into the chain's devices
(C3 = the sample's original pitch in Simpler), so it transposes a pad by semitones, a coarse way to tune a kick **[verify]**; use Detune for cents.

**Fills.** Make a roll feel faster at constant tempo by increasing the note value: quarters, then eighths, then sixteenths; ramp velocity or a Utility gain (not the fader), or stop short of the bar end
([Attack](https://www.attackmagazine.com/technique/tutorials/10-snare-rolls-for-the-drop/)). One-bar fill: snare `x---x-x-xxxxxxxx` with velocities rising from ~60 to 127 (`write_notes`/`edit_notes`). A kick high-pass near 82 Hz, switched off on the drop's downbeat, is a classic transition
([Spastik](https://www.attackmagazine.com/technique/beat-dissected/spastik-style-percussive-techno/)).

### 5.4 Density and perceived pace

**Hits per second = hits per bar x BPM / 240 [D].**

| Pattern | Hits/bar | Hits/s |
| --- | --- | --- |
| Kick + offbeat hat + clap, 130 BPM | 10 | 5.4 |
| 4/4 kick + 16th hats + ride + offbeat open hat + clap, 130 BPM | 34 | 18.4 |
| Rolling (ghosts, 16th toms, 16th hats), 130 BPM | 46 | 24.9 |
| Half-time with 8th hats, 100 BPM | 11 | 4.6 |

When beat rate and surface rhythm disagree, listeners' tempo judgement follows the **surface density** (subdivisions)
([London 2011](https://cdn.carleton.edu/uploads/sites/721/2021/12/London-2011-Tactus-vs-Tempo.pdf)). London's beat range is about 500-1500 ms; a techno quarter note (430-460 ms) sits just under it, so hats and sixteenths carry much of the pace **[inference]**. To make a section feel faster at
the same BPM, add subdivisions (16th hats, toms, rolling bass); to calm it, remove them and keep kick plus offbeat hat. For NOVA, perc (T4) is where density rises (`notes.density` reports onsets per bar per stem), and the HIGH band (160-180 BPM) already runs a quarter note every 333-375 ms, so its perceived pace depends even more on how many subdivisions perc adds **[inference]**.

> **For an agent, 4: groove.**
> 1. Write with `create_clip(..., pattern=...)` / `write_drum_pattern`. Swing only hats and percussion (separate call, `swing` 0.16-0.40), never kick or clap.
> 2. `get_notes`: hats should use at least four distinct velocities, ghosts 40-60, kick velocities constant. Check `analyze_notes` density and grid warnings; convert swing to ms with the table first.
> 3. Offsets: `transform_notes(operation="humanize", timing="4ms", velocity=6, seed=3)` on hats and percussion only; claps +-5-9 ms.
> 4. Audio check (NOVA set): `capture`, then `analyze_audio(take="latest")`. Tempo estimates of dense loops often come out at half tempo; look at the runner-up.
> 5. **Ask the human** about swing amount and ghost-note activity: bounce "A straight" and "B 57 % hats + ghosts", loudness matched, labelled.

---

## 6. Common mistakes and how to verify each

| Mistake | Measure | Fix |
| --- | --- | --- |
| Too much low end | `analyze_audio` `spectrum.sub` share vs a reference or earlier bounce; insert a 30 Hz low cut and re-bounce: a drop over ~0.5 LU means sub-30 Hz energy was eating headroom | low-cut kick and bass at 30 Hz; shorten tails; remove extra sub sources; filter the rumble return |
| Kick and bass fight | take-mode masking in 40-125 Hz; tail vs beat; pitch-pair table (3.2); polarity probe | tune, move notes off the kick step, EQ slots, sidechain 3-6 dB |
| Thin layered kick | `levels.rms_dbfs` with each polarity (`spectrum.sub.db` is only a share) | align transients, flip polarity |
| Over-compressed drums | crest factor of the drum bounce falls over ~3 dB; steady reduction above 6 dB | raise threshold, slower attack, use parallel |
| Distortion or limiter abuse | `levels.clipped_samples`, `loudness.true_peak_dbtp`, `notes` flags; limiter reduction over ~3 dB | lower drive, compensate output, at most one safety limiter on a song's bus (none on NOVA stems) |
| Everything quantised and flat | `get_notes`: fewer than 3 distinct hat velocities; no offsets; flat density | velocity pattern, ghosts, 54-60 % hat swing, chance |
| Over-humanised | kick or clap off grid by over ~10-15 ms (`analyze_notes` grid warnings) | tighten main hits, move variation to hats and ghosts |
| Pumping wrong | release over ~0.8 x beat; click at the kick | release at most ~0.8 x beat, attack 2-5 ms |
| Not mono-safe | `stereo.correlation`; take `audio.mono_sub` loss over 1 dB | Utility Bass Mono 120 Hz, mono kick and sub |
| Rumble swamps the mix | rumble return level vs kick (6-10 dB lower); duck depth | lower send, deeper duck, lower low-pass |
| Harsh hats | `spectrum.high_mid.db` and `high.db` vs a reference | higher high-pass, notch 2-6 kHz, Drum Buss Damp |
| "Wrong notes" in the low register | notes below ~130 Hz that are not root, octave or fifth, or major thirds below ~165 Hz | remove, move up an octave, high-pass pads |

---

## Sources

**Ableton:** Live 12 manual: [audio effect reference](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/), [instrument reference](https://www.ableton.com/en/live-manual/12/live-instrument-reference/),
[Max for Live devices](https://www.ableton.com/en/live-manual/12/max-for-live-devices/), [grooves](https://www.ableton.com/en/live-manual/12/using-grooves/), [racks](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/),
[editing MIDI](https://www.ableton.com/en/live-manual/12/editing-midi/); blog: [Drop It: the kick in electronic music](https://www.ableton.com/en/blog/drop-it-kick-electronic-music/),
[sidechain compression, part 2](https://www.ableton.com/en/blog/sidechain-compression-part-2-common-and-uncommon-uses/), [Sara Landry](https://www.ableton.com/en/blog/sara-landry-high-end-hard-techno/),
[Roar](https://www.ableton.com/en/blog/roar-meet-live-12s-new-processing-powerhouse/); [Cycling '74: Drum Buss parameters](https://docs.cycling74.com/reference/abl.device.drumbuss~); the Live 12.4 Core Library factory presets and groove folders read from disk.

**Attack Magazine:** [Adding reverb to a techno kick](https://www.attackmagazine.com/technique/tutorials/adding-reverb-techno-kick/), [Layering kick drum samples](https://www.attackmagazine.com/technique/tutorials/layering-kick-drum-samples/),
[Kick drums with Thorn](https://www.attackmagazine.com/technique/synth-secrets/how-to-make-your-own-kick-drums-using-thorn/) and [Diva](https://www.attackmagazine.com/technique/synth-secrets/how-to-make-your-own-kick-drums-in-diva/),
[Tune drum samples](https://www.attackmagazine.com/technique/tutorials/how-to-tune-kick-snare-tom-drum-samples/), [Tuning drums to improve your mix](https://www.attackmagazine.com/technique/tutorials/tuning-drums-to-improve-your-mix/),
[Choosing keys for bass weight](https://www.attackmagazine.com/technique/passing-notes/choosing-keys-for-bass-weight/), [Warehouse rolling techno bass](https://www.attackmagazine.com/technique/tutorials/warehouse-rolling-techno-bass/),
[Rumbling techno bass in Operator](https://www.attackmagazine.com/technique/synth-secrets/rumbling-techno-bass-ableton-operator/), [Mono-safe stereo width](https://www.attackmagazine.com/technique/tutorials/mono-safe-stereo-width/),
[Techno kick mix chain](https://www.attackmagazine.com/technique/tutorials/making-your-own-techno-kick-mix-chain-using-waves-studiorack/), [Organised chaos](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/),
[Mixer distortion](https://www.attackmagazine.com/technique/tutorials/in-the-red-mixer-distorted-90s-techno-drums/), [Lifeline Console drums](https://www.attackmagazine.com/technique/tutorials/mixing-techno-drums-with-excite-audios-lifeline-console/),
[Slave to the rhythm](https://www.attackmagazine.com/technique/tutorials/slave-to-the-rhythm-essential-drum-techniques/), [Ten tips for better drums](https://www.attackmagazine.com/technique/tutorials/ten-tips-better-drums/),
[Parallel compression](https://www.attackmagazine.com/technique/tutorials/parallel-compression/), [Compressing reverbs](https://www.attackmagazine.com/technique/tutorials/compressing-reverbs-for-clarity/),
[Swing in DAWs](https://www.attackmagazine.com/technique/passing-notes/daw-drum-machine-swing/), [Going off grid](https://www.attackmagazine.com/technique/tutorials/going-off-grid-what-is-swing-and-how-to-add-it/),
[Jack your tracks with swing](https://www.attackmagazine.com/technique/tutorials/jack-your-tracks-with-swing/), [10 snare rolls](https://www.attackmagazine.com/technique/tutorials/10-snare-rolls-for-the-drop/); Beat Dissected:
[Dark Techno Rumble](https://www.attackmagazine.com/technique/beat-dissected/dark-techno-rumble/), [Rolling Techno](https://www.attackmagazine.com/technique/beat-dissected/rolling-techno/), [Industrial Techno](https://www.attackmagazine.com/technique/beat-dissected/industrial-techno/),
[Grinding Analogue Techno](https://www.attackmagazine.com/technique/beat-dissected/grinding-analogue-techno/), [Belleville Techno](https://www.attackmagazine.com/technique/beat-dissected/belleville-techno/),
[Silent Servant](https://www.attackmagazine.com/technique/beat-dissected/create-raw-hypnotic-techno-like-silent-servant/), [Phase Fatale](https://www.attackmagazine.com/technique/beat-dissected/hypnotic-techno-inspired-by-phase-fatales-love-is-destructive/),
[Dave Clarke](https://www.attackmagazine.com/technique/beat-dissected/how-to-program-techno-like-dave-clarke/), [Spastik](https://www.attackmagazine.com/technique/beat-dissected/spastik-style-percussive-techno/),
[Cybotron](https://www.attackmagazine.com/technique/beat-dissected/how-to-make-an-electro-beat-inspired-by-cybotrons-clear/), [Paula Temple style](https://www.attackmagazine.com/technique/beat-dissected/dark-cinematic-hypnotic-techno/),
[Dark Berlin Techno](https://www.attackmagazine.com/technique/beat-dissected/dark-berlin-techno/), [Live Hi-Hats](https://www.attackmagazine.com/technique/beat-dissected/live-hi-hats/), [Low End Theory](https://www.attackmagazine.com/technique/beat-dissected/low-end-theory/),
[MIDI probability drums](https://www.attackmagazine.com/technique/beat-dissected/midi-probability-drums-inspired-by-warp-records-in-ableton-11/).

**Other editorial and education:** Sound On Sound (Gordon Reid), [The Bass Drum](https://www.soundonsound.com/techniques/synthesizing-drums-bass-drum) and [Practical Bass Drum Synthesis](https://www.soundonsound.com/techniques/practical-bass-drum-synthesis);
iZotope, [How to mix kick and bass](https://www.izotope.com/community/blog/how-to-mix-kick-and-bass); Sonnox, [Drum phase alignment](https://sonnox.com/articles/drum-phase-alignment-when-to-nudge-flip-or-leave-alone);
Gearnews, [sidechain in techno](https://www.gearnews.com/sidechain-compression-in-techno-workshop/), [kick and bass](https://www.gearnews.com/kick-and-bass-workshop-studio/), [the perfect techno kick](https://www.gearnews.com/?p=246014) (affiliate links in the articles);
Bonedo (German), [Bass drum rumble and rattle](https://www.bonedo.de/artikel/bass-drum-rumble-rattle-for-techno); Armada University, [kick and bass methods](https://www.armadamusic.com/university/music-production-articles/how-to-mix-your-kick-and-bass-5-must-know-methods);
Toolroom Academy, [4 ways to fix your low end](https://toolroomacademy.com/4-ways-to-fix-your-low-end).
**Weak evidence:** [Production Music Live (Menzel)](https://productionmusiclive.com/blogs/news/6-steps-to-create-that-rumbling-techno-kick-you-love-with-johannes-menzel),
[The Producer School](https://theproducerschool.com/blogs/featured-blogs/how-to-create-techno-rumble-kicks-for-2025), [MusicGuy Mixing: techno kick EQ](https://www.musicguymixing.com/?p=1616),
[Wikipedia: electronic body music](https://en.wikipedia.org/wiki/Electronic_body_music), [Wikipedia: Closer](https://en.wikipedia.org/wiki/Closer_(Nine_Inch_Nails_song)), [Equivalent rectangular bandwidth](https://en.wikipedia.org/wiki/Equivalent_rectangular_bandwidth), [Beat (acoustics)](https://en.wikipedia.org/wiki/Beat_(acoustics)).

**Research:** Justin London, [Tactus is not tempo (2011)](https://cdn.carleton.edu/uploads/sites/721/2021/12/London-2011-Tactus-vs-Tempo.pdf); Senn et al., [expert microtiming and groove (2016)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5050221);
Kilchenmann and Senn, [microtiming in swing and funk (2015)](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2015.01232/full); Witek et al.,
[syncopation, body movement and pleasure (2014)](https://research.birmingham.ac.uk/en/publications/syncopation-body-movement-and-pleasure-in-groove-music/).

**Repo:** `docs/TOOLS.md`, `MCP_Server/theory.py` (`drum_lanes`), `MCP_Server/tools/devices.py` (`set_sidechain`), `MCP_Server/audio/analysis.py` (`analyze_audio` fields), `ears/measure.py`, `ears/notes.py`, `ears/specs/nova.spec.json`.

## Open questions / where sources disagree

- **Ducking depth and release**: 1-3 dB (transparent kick-bass fit) vs 6-12 dB (pumping) vs 8-12 dB on a split low band; releases of 16-60 ms (punchy) to 150-350 ms (full recovery before the next kick). Start small and measure; no source covers baking ducking
  into stems that can play without the kick.
- **Tuning the kick**: Attack and iZotope say tune it; an engineer quoted by Ableton says pitch is hard to hear below 60 Hz. The beating argument (3.2) is mine, from standard psychoacoustics, and no electronic-music study tests it.
- **Low cut on the kick**: a 48 dB/oct cut at 30 Hz (Ableton presets), 20 Hz at 12-18 dB/oct, a soft 11 Hz cut, or a shelf (Landry). No source compares them objectively.
- **Mono**: strict "mono below 120 Hz" vs a stereo sub that works in one NIN track. Measure `mono_sub` before deciding.
- **Glue attack**: 0.3 ms (clamp), 10 ms (punch) and 30 ms (gentle) all appear in good sources; it depends on whether the transient should survive.
- **Quantisation**: the exactitude hypothesis vs mild expert microtiming; none of the studies tested electronic dance music.
- **Not verified in a running Live:** whether `set_sidechain` can name one Drum Rack chain as the source or work inside a rack chain; whether a groove file can enter the pool through the MCP; whether a muted trigger track drives a Pre FX
  sidechain; the exact DS Kick and Drum Sampler parameter names (the Compressor sidechain-EQ and Utility names are confirmed by the 12.4.6 dump); and the Glue attack and release display values (decoded from presets, consistent with the dump's defaults).
- **Gaps**: no authoritative source for an absolute kick level or per-instrument levels; no Boys Noize or Nine Inch Nails drum-production interview was retrieved (web-search quota ran out); `09-industrial-ebm-techno-nin.md` may cover it.
