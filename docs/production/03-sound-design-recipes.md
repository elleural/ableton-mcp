# Sound design recipes by role, in Live 12

Digest 03 of `docs/production/`, written for AI agents that build and judge sounds in Ableton Live 12.4.6 Suite
through the AbletonMCP tools. You cannot hear. The producer (Fred) decides what sounds right; the measurements
in this file find defects, they do not rank taste. This file is the by-role recipe book. Background and deeper
treatments live next door: [02-synthesis-and-live-instruments.md](02-synthesis-and-live-instruments.md) (detune zones,
section 1.3), [04-drums-and-low-end.md](04-drums-and-low-end.md) (kick, bass, beating in the bass register, 3.2),
[06-mixing.md](06-mixing.md), [08-arrangement-and-composition.md](08-arrangement-and-composition.md) (low-interval
limits, 2.5), [09-industrial-ebm-techno-nin.md](09-industrial-ebm-techno-nin.md) (genre, pad and riser starting values, 6.1 and 6.6),
[11-listening-without-ears.md](11-listening-without-ears.md) and [12-live-devices-reference.md](12-live-devices-reference.md)
(exact parameter names and per-device cards, recipes in section 8).

**Conventions.** Note names are Live's (C3 = MIDI 60, so every name is one octave lower than scientific pitch
notation; MIDI 33 = A0 = 55 Hz). Where it matters I give MIDI numbers and Hz. Parameter names in backticks are the
12.4.6 strings in `reference/live-12.4.6-device-parameters.md` and digest 12; the others follow the Live 12 manual, so call `get_device` first and let it decide.
`set_device_parameters` takes display strings such as "2.2 kHz", "-3 dB", "30 %". A number with a link comes from that
source. A number marked *(start)* is a starting point I derived from sources and acoustics: tune it, never treat it as
truth. Sources, and the places where they disagree, are at the end.

## If you remember five things

1. **"Big, heavy, clean" is a saw-like harmonic series on a low root, with width only above about 200 Hz and nothing
   noisy, saturated or modulated underneath.** Build it as a mono root layer plus a wide chord body (section 2). The
   producer's references measure as one low root at 41-49 Hz, a full saw-like stack to about 2 kHz, side/mid about
   0.75-0.95 above 200 Hz, little noise and a roll-off above 2 kHz
   ([handoff note](../handoff/2026-10-08-nova-v2-paused.md)).
2. **Weight comes from octave layers and a mono low end, not from more detune.** Detune beats scale with pitch: a
   10-cent spread is a slow 0.3 Hz swell on a 55 Hz root but a 6-13 Hz flutter at the 10th-20th partial of a 110 Hz
   note. Octave-related saws share partials exactly, so they add size without beating. Keep unison small, keep one
   oscillator on pitch, filter the top.
3. **Respect the low interval limits.** Below about 130 Hz (Live C2) use only roots, fifths and octaves; major thirds
   from about 165 Hz (E2); minor thirds and seconds higher still; the lowest sounding note is the chord root (rule and
   table in section 8.3). A voice built on a sub-oscillator put chord thirds at 55-65 Hz, and the ear heard "wrong notes".
4. **Never saturate, chorus or "warm" a summed chord when you can do it per voice or per layer.** Distortion makes sum
   and difference tones between all partials; with equal-tempered thirds they land between the chord's own partials and
   sound out of tune. Use the synth's per-voice filter drive, or saturate single-note layers.
5. **Change one thing at a time, on a copy, loudness-matched, labelled.** Keep the producer's chosen sound as a muted
   twin, A/B against it, and ask before touching anything he approved. Numbers diagnose (hollow, noisy, phasey,
   clashing); the human picks.

Contents: 1 Facts - 2 Pads - 3 Drones and textures - 4 Basses - 5 Leads, plucks, arps, delay throws - 6 FX - 7 Width
and size - 8 Layering - 9 Matching a reference, and the A/B protocol - 10 Agent checklist - Appendix (measurement
script) - Sources - Open questions.

## 1. Five facts that explain most failures

**Partials.** A sawtooth contains every harmonic ([Wikipedia](https://en.wikipedia.org/wiki/Sawtooth_wave)) at
1/n amplitude: relative to the fundamental the 2nd partial is -6 dB, the 3rd -9.5, the 4th -12, the 5th -14. A
square (50 % pulse) has odd partials only ([Live manual, Analog](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)).
Gordon Reid finds that a pulse-width-modulated wave alone sounds slightly hollow and that mixing it with a saw fills
the sound in ([SOS](https://www.soundonsound.com/techniques/synthesizing-strings-string-machines)). A "full" pad
shows a smooth staircase of partials; a "hollow" one shows missing even partials, a weak fundamental or comb notches.

**Beating scales with pitch.** Two voices c cents apart beat at f x (2^(c/1200) - 1) Hz
([beats](https://en.wikipedia.org/wiki/Beat_%28acoustics%29)); partial n beats n times faster.

| Fundamental | 5 cents | 10 cents | 20 cents | 30 cents |
| --- | --- | --- | --- | --- |
| 41 Hz (E0) | 0.12 Hz | 0.24 | 0.48 | 0.72 |
| 55 Hz (A0) | 0.16 | 0.32 | 0.64 | 0.96 |
| 110 Hz (A1) | 0.32 | 0.64 | 1.3 | 1.9 |
| 220 Hz (A2) | 0.64 | 1.3 | 2.6 | 3.9 |
| 20th partial of 110 Hz (2.2 kHz) | 6.4 | 12.7 | 25.6 | 38 |

Under about 1 Hz reads as breathing, above roughly 15 Hz as roughness (zones in `02-synthesis-and-live-instruments.md`, section 1.3). So a unison that is
lovely on the root is raspy two octaves up unless the top is filtered or the spread is smaller. Reid found that beyond
a minimal detune two saws take on an off-colour timbre
([SOS](https://www.soundonsound.com/techniques/synthesizing-strings-string-machines)); Ableton advises detuning only a
little, never so much that the pitch loses clarity, and leaving the first oscillator on pitch
([Ableton blog](https://www.ableton.com/en/blog/pad-it-out-10-ways-make-distinctive-pad-sounds/)).

**Critical bands and the low interval limit.** Two partials of similar level closer than a critical bandwidth
produce roughness ([roughness](https://en.wikipedia.org/wiki/Roughness_%28psychophysics%29)). The ERB approximation
24.7 x (4.37 f[kHz] + 1) Hz ([ERB](https://en.wikipedia.org/wiki/Equivalent_rectangular_bandwidth), valid from 100 Hz)
gives 35 Hz at 100 Hz, 41 Hz at 150 Hz and 79 Hz at 500 Hz. A third at 55 and 65 Hz is 10 Hz apart, deep inside one
band. Orchestration texts publish "low interval limits" for this reason (section 8.3).

**Short delays are comb filters.** A copy delayed by t has its first notch at 1/(2t) and further notches every 1/t
([comb filter](https://en.wikipedia.org/wiki/Comb_filter)): 1 ms notches 500 Hz, 5 ms 100 Hz, 10 ms 50/150/250 Hz,
20 ms 25/75/125/175 Hz. Haas widening (1-40 ms), a chorus or flanger delay line and feedback all carve such notches
into a pad's body where the channels meet (mono playback, speakers close together); inverted feedback sounds hollow
([Live manual, Chorus-Ensemble](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)).

**Distortion multiplies partials together.** Besides harmonics, every pair of partials makes sum and difference tones.
For simple chords the difference tones are subharmonics of the chord tones; more complex chords make lower ones, heard
as beating, and minor chords make much lower ones than major chords, so minor-key material needs cleaner treatment
([Production Expert](https://www.production-expert.com/production-expert-1/intermodulation-distortion-the-audio-problem-you-may-be-overlooking)).
Equal-tempered minor thirds are narrower and major thirds wider than just ones (15.6 cents flat of 6:5, 13.7 cents
sharp of 5:4) while a fifth is only 2 cents flat, which is why distorted fifths cohere and distorted thirds turn "messy
and indistinct" ([Wikipedia, Power chord](https://en.wikipedia.org/wiki/Power_chord)). The project is in A minor.

## 2. Pads

### 2.1 Pick the instrument by the job

| Job | Start with | Notes |
| --- | --- | --- |
| Big, clean saw pad | **Wavetable** (Basic Shapes saw, Classic unison, two filters) | Unmodulated oscillators are band-limited, so no aliasing; non-Clean filter circuits have a per-voice `Flt n Drive`; Filter 2 can be the high-pass ([manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)) |
| Warm analog, Juno-like | **Analog** (4th-order low-pass, `Unison` with 2 or 4 voices) or **Drift** (voice modes Poly/Mono/Stereo/Unison, `Drift` slider) | Drift randomises pitch and cutoff per voice: set `Drift` to 0 on any layer that must stay in tune |
| Cinematic, evolving | **Wavetable** with the Matrix tab (two LFOs, three envelopes) or **Meld** (Swarm, Chord, Sub oscillators) | Slow modulation does the work |
| Drone | **Operator** (drawn harmonics), **Meld** (`A Keytracking` off), Drone Lab racks | Section 3 |
| Texture | **Granulator III**, Spectral Resonator, Spectral Time | Section 3 |
| Starting from a preset | Synth Essentials (200+ racks), Mood Reel, Drone Lab, Glitch and Wash, Build and Drop | Screen the architecture first (2.8) |

### 2.2 Recipe A: the "big, heavy, clean" background pad, built from scratch

*Why it works:* the weight lives in a single mono saw note that never gets unison or chorus; the chord above it carries
the width, so mono compatibility and tuning stay clean. If a producer-approved pad already exists, iterate on
it instead (digest 12 section 8.3 and digest 09 section 6.1 give that route) and use this recipe to understand and
verify the parts. Reference targets: root 41-49 Hz, partials to about 2 kHz, roll-off above, side/mid 0.75-0.95 above
200 Hz, little noise.

**Layer 1, "Pad Root" (MIDI track, one note per bar, the chord root at MIDI 28-40 = 41-82 Hz), Wavetable**
- `Osc 1` on a Basic Shapes table positioned on the saw, `Osc 1 Gain` 0 dB, `Osc 1 Transp` 0. Osc 2 off, Sub off,
  `unison_mode` None.
- `Flt 1 Type` low-pass, `Flt 1 Slope` 24 dB, circuit Clean, `Flt 1 Freq` 2.0-2.4 kHz *(start)*, `Flt 1 Res` 0-5 %, no key
  tracking (the cutoff must stay put so the root keeps its harmonics up to 2 kHz).
- Amp: `Amp Attack` 1-2 s, `Amp Sustain` 0 dB, `Amp Release` 2-3 s *(start)*. No chorus and a smaller reverb send than the body
  (below). A Saturator (Soft Sine, `Drive` 2-4 dB) is acceptable here because it is one note.
- Level: root layer about 3 dB below the body *(start)*; raise it 2 dB when the producer says "heavier".

**Layer 2, "Pad Body" (the chord above the root; lowest note MIDI 52 = E2 = 165 Hz or higher), Wavetable**
- Osc 1 saw, `Osc 1 Transp` 0. Osc 2 (`Osc 2 On` On: it is Off by default) the same saw at `Osc 2 Transp` +12, `Osc 2 Gain` -6 dB: an octave layer whose partials
  coincide with the even partials of Osc 1, so it thickens the sound with no beating (detuned copies would beat).
- Unison: `unison_mode` Classic, `unison_voice_count` 3-4, `Unison Amount` about 10-15 % *(start)*, then **calibrate**
  (7.1): aim for outer voices about +-4-10 cents. Fewer voices sound clearer, more sound thicker
  ([manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)).
- Filters: `Flt 1` low-pass 24 dB Clean at 2.2 kHz, `Flt 1 Res` 0-8 %; `Flt 2` (`filter_routing` Serial) high-pass 24 dB at
  130 Hz so the root layer owns everything below.
- Slow opening: Env 2 to `Flt 1 Freq` +10-15 %, A 2.5 s, D 8 s, S 40 %; LFO 1 triangle 0.07 Hz (retrigger off) to `Flt 1
  Freq` +-4 % *(start; AULART's pad uses 0.07 Hz and a 5.8 s envelope,
  [AULART](https://www.aulart.com/blog/create-an-ever-evolving-pad-from-scratch-with-abletons-wavetable/))*.
- Amp: attack 0.8-1.2 s, sustain 0 dB, release 2.5-3.5 s.
- Voicing: open; major thirds from MIDI 52 (E2) up and minor thirds higher still (`08-arrangement-and-composition.md` section 2.5 tolerates a close Am triad from A2); e.g. Am as E2-A2-C3-E3 (MIDI 52, 57, 60, 64). Check with `voicing_problems` (appendix; its table is the more permissive printed chart, so also apply the rule of 8.3 by hand).
- Optional width, added only after the dry pad passes the checks and only with the producer's yes on an approved sound:
  **Chorus-Ensemble**, `Mode` Ensemble, `Rate` 0.4-0.6 Hz, `Amount` 20-30 %, `Width` 100-140 %, `HP On` at `HP Freq` 220 Hz,
  `Feedback` 0, `Warmth` 0, `Dry/Wet` 30-40 %. Chorus is the likeliest source of "flangy" (2.7).
- Then **EQ Eight** in M/S mode (property `global_mode` `mid_side`): Side low cut (`High Pass 48dB`: EQ Eight has no 24 dB cut) at 200 Hz; high shelf -3 dB at 3 kHz on both channels;
  a Mid bell -2 dB at 300 Hz only if mud shows. Then **Utility**: `Stereo Width` 100-115 %, `Bass Mono` On, `Bass Freq` 150 Hz,
  last in the chain.
- Return A, **Hybrid Reverb**: `Routing` Algorithm (the default Parallel also runs the convolution engine), Dark Hall, `Decay` 5 s, size 100 %, `Predelay` 10-40 ms, `Modulation` 0 %, EQ tab low cut 250 Hz and
  high cut 5 kHz (`EQ Hi Type` Cut; it is Shelf by default), Bass Mono on, `Vintage` Off, `Dry/Wet` 100 %. Body send about -14 dB; root send about 4 dB lower (the reverb's low cut keeps the root's
  fundamental out of the tail). (The producer's saved
  base pad used Dark Hall, 5 s, size 100 %, modulation 0, 30 % wet, Bass Mono 120 Hz.)

**Acceptance on a held-note render** (appendix script): lowest peak within 2 cents of the root; partials 2-16 within about
3-4 dB of the saw staircase (-6, -9.5, -12, -14 dB ...) up to the filter corner; even-minus-odd between -3 and 0 dB; side/mid
above 200 Hz 0.75-0.95 and below 120 Hz under 0.1; mono-sum loss below 120 Hz under 0.5 dB; peak at least 6 dB under full
scale with no limiter on the stem.

> **For an agent.** `create_track("midi", "Pad Root", device="Wavetable")` and the same for "Pad Body"; read each with
> `get_device`; write values with `set_device_parameters`; unison mode and voice count are properties
> (`set_device(track, "Wavetable", properties={"unison_mode": "Classic", "unison_voice_count": 4})`); Wavetable modulation
> amounts go through `device_action(track, "Wavetable", "set_modulation", {...})`; the reverb lives on a return
> (`create_track("return", ...)`, `set_mixer(track, sends={"A": -14})`). If the project needs a single `pad` track, use one
> Instrument Rack with two chains and a MIDI **Pitch** effect (`Mode` Block, `Lowest`/`Range`) at the head of each chain to
> split root from chord, because rack key zones are not scriptable (only Drum Rack `in_note`/`out_note` are), or put both
> tracks in `create_bus("Pad", [...])`; check how the project's spec names the pad part before splitting tracks. Render a clip
> with the root held 8 bars and then the chord held 8 bars; `bounce(stems=[...])`; run the appendix script on each file. Ask
> the human only after the numbers pass, with the base on a muted twin.

### 2.3 Vocabulary to parameter moves (the producer's words)

Apply one move, re-render, level-match, then ask.

| The human says | Likely cause | First move (one at a time) | What should change |
| --- | --- | --- | --- |
| bigger | low weight, width, space | root layer +2 dB; or Ensemble `Width` +20 %; or return send +3 dB / `Decay` +1.5 s | band 40-160 Hz, width above 200 Hz |
| heavier, meatier | too little 40-200 Hz or thin harmonics | root +2 dB; raise the root layer's low-pass 300 Hz; or add the fifth above the root to the root layer (fifths are allowed down to about MIDI 34) | partial table, third-octave 40-160 Hz |
| cleaner | noise, modulation artefacts, distortion | remove the noise source; `Unison Amount` -5 points; chorus `Dry/Wet` -10 points; reverb `Modulation` 0 and `Vintage` Off; `Warmth` 0; no Saturator on the chord | valley depth up, between-partials share down (appendix) |
| less airy | noise or too much top | low-pass -400 Hz; drop the noise oscillator or the Noise/Shimmer unison; reverb damping up | energy above 6 kHz down |
| less flangy | short modulated delays, Phase Sync unison, chorus on noise | chorus `Feedback` 0, `Rate` at or under 0.5 Hz, `Amount` -10 points, `HP Freq` up; remove Haas or phaser | frame-to-frame spectral wobble 500-4k |
| less hollow | missing even partials or fundamental, inverted feedback | add a saw or an octave layer; `FB Invert` off; lower any high-pass | even-minus-odd, fundamental level |
| wrong notes, out of tune | thirds too low, intermodulation, Drift, wide detune | move the third up an octave; saturate per layer; `Drift` 0; `Unison Amount` down | `analyze_notes`, pitch of the lowest peak |
| thin | phase cancellation, high-pass too high | check polarity and mono loss; octave layer; lower the high-pass | mono-sum loss, 100-400 Hz |
| muddy | 150-400 Hz build-up, close low intervals | high-pass 130-200 Hz on the chord; bell -2 to -3 dB at 250-350 Hz; wider voicing | third-octave 160-315 Hz |

### 2.4 Recipe B: dark, cinematic pad

Same architecture as A with these changes: low-pass 12 dB at 600-900 Hz instead of 2 kHz (the roll-off is the darkness;
AULART's pad uses 550 Hz with 20 % resonance), root layer 2 dB louder, filter envelope opening over 5-6 s, Hybrid Reverb
Dark Hall 7-10 s with damping up, and an Echo before the reverb (`Channel Mode` Ping Pong, 5/16, `Filter On` with a low cut,
`Feedback` about 35 %, Wobble on; AULART does the same with an EQ dip near 1.5 kHz for smoothness). For a colder variant Attack
builds a pad in Analog from a sine (no harmonics, filter off), a slowly building vibrato (vibrato delay and attack), Unison for
harmonics, Chorus after the synth, and Filter Delay with low-cut filters for ambience instead of reverb, because a filtered delay
keeps the sound cleaner ([Attack, Cold Pads](https://www.attackmagazine.com/technique/tutorials/cold-dark-pads/)). Add dark
saturation only on the root layer. Dark is not muddy: keep the chord high-pass at 130 Hz.

### 2.5 Recipe C: warm analog pads; Juno chorus versus supersaw

**Warm analog (Analog or Drift).** Osc 1 saw, Osc 2 a square (pulse width set by ear or slowly modulated) detuned about 6
cents, 24 dB low-pass with a dropped cutoff (0.9-1.4 kHz *(start)*), filter envelope A 280 ms / D 2.5 s / S 50 %, amp A 300 ms /
S full / R 730 ms ([MusicRadar](https://www.musicradar.com/how-to/how-to-build-a-classic-80s-pad-sound)); width from a
Chorus-Ensemble in Chorus mode (7.2), not from unison. In Drift use `voice_mode` Poly or Stereo (two voices per note, `Spread`),
`Drift` 15-35 % for analog wander, `LP Type` I (12 dB, drives warmly) or II (24 dB)
([manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)). PWM can make the tuning of low notes feel
nebulous ([SOS](https://www.soundonsound.com/techniques/creating-analogue-sounds-digital-synths-part-2)), so keep PWM off the
root layer.

| | Supersaw (JP-8000 style) | Juno style |
| --- | --- | --- |
| Source | Seven saws, one centre and six sides, free-running random phase per note, a high-pass tracking the fundamental ([Szabo thesis](https://web.archive.org/web/2018id_/https://www.nada.kth.se/utbildning/grukth/exjobb/rapportlistor/2010/rapporter10/szabo_adam_10131.pdf), archived copy) | One oscillator (saw, pulse, sub) |
| Width from | Detune and pan inside the oscillator | A slow stereo BBD chorus, modes at about 0.4 and 0.6 Hz and a stronger two-button mode ([Wikipedia](https://en.wikipedia.org/wiki/Roland_Juno-60)) |
| Detune facts | Outer saws sit at about +-9 cents at 24 % of the knob, +-18 at 50 %, +-45 at 75 %, -202/+177 at maximum (converted from the thesis tables); the mix control lowers the centre saw from 1.0 to 0.45 while the sides rise to 0.6 | None in the oscillator |
| Character | Dense, bright, rough upper partials | Smooth shimmer, slight pitch wobble, some noise |
| In Live | Wavetable Classic unison 5-7 voices, small amount, `Flt 1` high-pass key-tracked (MIDI Note to `Flt 1 Freq` 100 %; cutoff at C3 then tracks the note) | Analog or Drift plus Chorus-Ensemble, Chorus mode, `Rate` 0.4-0.6 Hz, `Amount` 40-60 %, `Dry/Wet` about 50 %, `Warmth` 0 |
| Risk | Roughness above partial 10; keep the centre voice strong | The mono sum thins (comb); do not chorus the root layer |

### 2.6 Recipe D: evolving, textural pad (Wavetable)

AULART's walkthrough as a parameter list: Osc 1 JUP SawPulse (Vintage) at position 50 %, Semi -12, FM 3 % with Tune 50 %; Sub on at
-14 dB, Tone 30 %, -1 octave; Osc 2 "Transformations" (Complex) at 50 %, Semi 0; Filter 1 low-pass 12 dB, OSR circuit, 550 Hz,
Res 20 %, Drive 2 dB; amp A 800 ms, D 6.6 s, S -3.1 dB, R 1.7 s; Unison Shimmer, 4 voices, 25 %; LFO 1 triangle 0.07 Hz (retrigger
off) to Osc 1 position +50 and Osc 2 position -50 (opposite directions keep the balance), also to LFO 2 rate (7.8) and Env 3 decay
(20); LFO 2 triangle 0.7 Hz to the filter (1.6); Env 2 (A 5.8 s, D 11.7 s, S 0) to the filter (19); Env 3 looping (A 67 ms, D 141 ms)
to FM amount (48); then EQ Eight, Echo ping-pong 5/16 with wobble, Hybrid Reverb Quartz. Use Shimmer unison only when movement
matters more than a clean tone; Ableton's blog also lists Wavetable's Noise unison (about 40 %, many voices) as a deliberate
degrade for grit.

### 2.7 Diagnosing a bad pad

| Symptom | Usual causes | Measure | Fix in Live |
| --- | --- | --- | --- |
| **Hollow** | only a sub or band-pass energy; weak fundamental; square/PWM only; inverted feedback; comb from a short delay; layers out of polarity | even-minus-odd below -10 dB; fundamental more than 12 dB under the 2nd partial; mono loss above 3 dB | add a saw layer or an octave layer; `FB Invert` off; lower the high-pass; flip a layer's polarity (Utility `Left Inv` and `Right Inv`) |
| **Thin** | high-pass too high; two identical detuned waves cancelling; sides cancelling in mono | mono loss; little energy 100-400 Hz | octave layer; different waveforms or free-running oscillators; narrow below 300 Hz |
| **Airy, raspy** | noise oscillator, Noise or Shimmer unison, bright shelf, resonant filter | valley depth under about 30 dB and between-partials share over about 2 % (appendix); energy above 6 kHz | remove noise; unison Classic; low-pass 12-24 dB at 2-3 kHz; reverb damping up |
| **Flangy** | chorus or flanger with feedback; Phase Sync unison; chorus on noise; Haas on a sustained note | spectrum wobbles frame to frame; notch comb at multiples of 1/(2t) | `Feedback` 0, `Rate` and `Amount` down, `HP On`, no chorus on noise |
| **Muddy** | 150-400 Hz excess; thirds below the limit; reverb low end; chorus acting in the lows | third-octave 160-315 Hz above reference | high-pass 130-200 Hz; open voicing; reverb low cut 250 Hz |
| **Circus, harsh** | detune too wide for the upper partials; aliasing; resonance | roughness above partial 10; level above 4 kHz | smaller spread; low-pass 3-6 kHz; Hi-Quality on (Wavetable, Saturator, Pedal; a menu option, ask) |
| **Out of tune** | intermodulation; thirds too low; Drift; PWM on low notes | lowest peak vs MIDI pitch; `analyze_notes` clashes; `off_series_peaks` | saturate per layer; `Drift` 0; unison off on low notes |

### 2.8 Screening presets before auditioning

> **For an agent.** (1) `get_devices` and `get_device` on the candidate: which oscillators are on and at what octave, is there a
> full-spectrum oscillator at the root pitch or only a sub, noise level, filter type and cutoff, unison mode and amount,
> chorus/phaser/flanger feedback, distortion, limiters. Reject "only a sub plus noise" voices (that is what made the earlier hollow,
> raspy pick), cutoffs under 600 Hz on noisy sounds, and any saturation or limiter on a chord stem. (2) Render the held root and one
> chord, run the appendix script, compare with the base. (3) Offer the human at most three labelled candidates. Do not rank presets
> by spectral distance to a full-mix reference: a reference mix is not a target for one instrument.

## 3. Drones, background synths and textures

A drone is a pad reduced to its foundation: one low root (optionally with its fifth), a chosen harmonic stack, slow
movement, width above the bass, space. The references' background synth measures as exactly that (root 41-49 Hz,
saw-like stack to about 2 kHz, little noise). Keep the root's pitch static (no vibrato on it), emphasise harmonics with filters or EQ rather
than distortion, move things at 0.03-0.1 Hz (AULART's pad uses 0.07 Hz), and put the width above 200 Hz only. What is documented about
the Reznor and Ross scores' palette (saw stacks, a fixed 1-2 kHz cutoff, octaves and fifths low) is in digest 09, sections 2.4-2.5.

### 3.1 Four ways to build the root-plus-stack drone

1. **Subtractive (fastest).** Recipe A's root layer held for 16 bars or more, filter envelope attack 6-8 s, LFO 0.05 Hz
   on the cutoff at a few percent. Add a second note a fifth above the root if a power-chord weight is wanted (a root-fifth dyad is
   safe in the low register).
2. **Additive in Operator.** Choose the waveform "User" for an oscillator and draw the amplitude of each harmonic;
   the context menu can edit only even or only odd harmonics, and Normalize keeps the level stable
   ([manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)). Draw a saw (1/n) to 2 kHz, or
   lift partials 2, 3, 4, 6, 8 for an organ or choir colour. Pick an algorithm in which all oscillators output directly,
   filter low-pass 24 dB near 2 kHz, Spread 0 on the root, amp attack 3-6 s.
3. **Meld for a fixed-pitch drone.** With `A Keytracking` (or `B Keytracking`) off an engine always plays C3 (the scale root with Use
   Current Scale), so it ignores the chords: set `A Octave` -3 and `A Transpose` +4 st for 41.2 Hz (C3 = 261.6 Hz, three octaves down is C0 = 32.7 Hz, four semitones up is E0). Basic Shapes at the saw plus
   a Sub oscillator (Aux adds a lower sine) on the other engine. Use this only for a drone that must not follow
   the progression.
4. **Drone Lab.** Racks with evocative macro names, 600+ drawn-out samples and the Harmonic Drone Generator, an
   eight-voice Max for Live synth that can be tuned to just intonation
   ([Ableton](https://www.ableton.com/en/packs/drone-lab/)). Read the macros with `get_device`; a just-tuned drone
   avoids the 13.7-cent-wide equal-tempered third, but it will beat against equal-tempered instruments, so use it alone
   or retune everything.

**Carve the stack with EQ.** Attack's LCD Soundsystem-style drone is a single saw playing a dyad on D2, D3, D4 and G3;
cutting notches at 150, 300, 600 and 1200 Hz (the D partials) makes the G stand out, then envelope pumping and tape
saturation after the pumping add life
([Attack](https://www.attackmagazine.com/technique/synth-secrets/making-lcd-soundsystem-style-drones/)). With a saw you
steer which note the ear hears by notching partials of the others, not by adding notes.

### 3.2 Granular textures with Granulator III

Facts from the designer's page ([Henke](https://roberthenke.com/technology/granulator3.html)): three grain modes. Classic
plays two overlapping grains per stereo channel with a flexible grain envelope; Loop behaves like a crossfading sampler;
Cloud layers up to 20 unsynchronised grains, suits thick monophonic textures and has a Density control; Ableton
describes Cloud as the mode for drones and experimental textures
([Ableton](https://www.ableton.com/en/packs/granulator-iii/); it needs Max for Live and Live 12 Suite). Grains run from 2 ms
to 2 s; very small grains make noisy or pitched timbres. Position is a percentage of the sample, Scan ramps it, Variation randomises position, size, pitch and volume per grain, Spread detunes left and right
playback and desynchronises their grains (even a little makes it very stereophonic), and two series state-variable
filters follow the key by default. Capture records any source straight in (1-8 s, remember to save). MusicRadar finds
the most musical results with longer samples and larger grains
([MusicRadar](https://www.musicradar.com/how-to/granulator-iii-ableton-live-12)).

*Clean cloud pad (start):* source a clean sustained note (a bounced root layer or a Drone Lab sample, 8 s) - Cloud mode -
Density 8-14 - Grain Size 150-400 ms - Position on a steady region, Scan off - Variation 5-15 % - `Spread` a few hundredths of a semitone to start (its display is in semitones, 0-12 st, not a percent; widen by measurement) - LFO free (`LFO Sync` Hz),
0.03-0.1 Hz, small amount on Position - Filter low-pass about 3 kHz (key follow 100 %) - volume envelope A 2 s, R 4 s -
then Recipe A's ensemble, side-only low cut and reverb. Grains under about 20 ms or large Variation turn a pad into
noise; bounce the result to audio once it is stable.

### 3.3 Resampled atmospheres

- **Loop and slice a resample in Simpler.** Attack resamples a strings chord through Simpler: Beats mode slices the
  sample (Complex Pro is smoother), loop length is typed as a percentage of a one-bar sample so it stays in time, loop
  mode Off gates the chops, a Beat Repeat with Pitch Decay adds pitch fills
  ([Attack](https://www.attackmagazine.com/technique/synth-secrets/resampled-pads-with-spitfire-audio-tundra-ableton-simpler/)).
- **Transpose, bounce, transpose back.** Raise the MIDI chord 7 semitones, bounce, lower the audio 7 semitones with a
  warp mode, and keep the artefacts as character; or remove the attack from a piano note, smear it with a long
  release and reverb, low-pass it and tuck it under the synth pad
  ([Ableton blog](https://www.ableton.com/en/blog/pad-it-out-10-ways-make-distinctive-pad-sounds/)).
- **Pitch a one-shot down 24 semitones to lengthen it,** layer an octave-up copy, glue both with saturation on a bus
  and lift a resonance near 300 Hz ([Attack](https://www.attackmagazine.com/technique/tutorials/drones-from-drums/)).
- **Freeze.** Hybrid Reverb Freeze and Freeze In, Delay Freeze, Spectral Time's Freezer sustain any sound
  ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)); Spectral Resonator with Stretch at
  100 % keeps odd harmonics only, a square-like colour tuned to a note.
- After any resample re-measure the pitch (warping can leave the key a few cents off), high-pass below the root, and
  fade the loop edges (a reverb tail masks a loop click, as in Attack's Shepard tone tutorial).

> **For an agent.** Render 16 s of the held drone; `analyze_audio(path)` gives the loudness curve (flat within about
> 1 LU for a static drone) and spectrum; run the appendix script for the partial staircase, valley depth and width by
> band. For "evolving, not wandering", compare third-octave spectra of the first and last 4 s: 2-6 dB of change in
> 500-2000 Hz is movement, 0 is static, over 10 dB is too much for a background *(start thresholds)*. Check the loop
> seam by comparing the first and last 10 ms. A grain size below 20 ms, Noise or Shimmer unison, or a noise-heavy
> source will show up as low valley depth.

## 4. Basses

Rules for every bass: one pitched source per frequency region; the low end mono (Utility Bass Mono, 50-500 Hz range,
Audition switch to check it, [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/));
tuned to the key and to the kick (`04-drums-and-low-end.md` has the full method); saturate the mono line or the upper layer,
never a chord; layer by frequency.

### 4.1 Clean sub

Operator (Osc A sine, the rest off), Wavetable (sine, or the Sub oscillator with Tone 0 % which is a pure sine) or Analog.
Mono or one voice. Amp: A 3-8 ms, D 0, S 0 dB, R 40-120 ms *(start; a hard start of a sine clicks)*. If you use Drift set
`Drift` to 0 and Retrigger on so every note starts at the same phase. To make it audible on small speakers add the 2nd
and 3rd harmonics with Saturator, `Type` **Bass Shaper** (designed for 808s and synth basslines, smoother harmonics at
high Drive; a low `Threshold` gives soft clipping), `Threshold` -30 to -40 dB, then raise `Drive` from 3 dB in 1 dB steps (6-12 dB
is typical, digest 12 section 4.1) and compensate with `Output`
([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)); Pedal's "Sub Warmer" tip (Overdrive,
Sub on, Bass up, Gain raised slowly) does the same. Stop when the harmonics read right: 2nd partial about -20 to -30 dB and
3rd about -25 to -35 dB under the fundamental, nothing above about 400 Hz *(start)*. EQ Eight `High Pass 12dB` at 25-30 Hz
(below E0 = 41 Hz; use `High Pass 48dB` for real rumble: EQ Eight has no 24 dB cut).

### 4.2 Saturated mid-bass over a sine sub

- **Sub chain:** the sine from 4.1.
- **Mid chain:** saw or square, mono. **High-pass 24 dB at 90-110 Hz before the saturator** so no low partials
  intermodulate, then Saturator Analog Clip or Soft Sine Drive 8-14 dB, then low-pass 4-5 kHz, then 2-4 dB of
  compression. Mode Audio's recipe for adding weight to a weak bass is the same idea: high-pass the original around 75 Hz,
  add a sine copy of the part, balance them, bus-compress 3-6 dB
  ([Mode Audio](https://modeaudio.com/magazine/quick-tips-009-sub-bass-layering)).
- Symmetric curves (Soft Sine, Analog Clip, Hard Curve) add odd harmonics, a hollow squarish colour; asymmetric shaping
  (Roar Shaper Bias, Half Wave Rectifier, Pedal Fuzz) adds even ones too. Measure with even-minus-odd.
- Combine both (two chains of one Instrument Rack, or two tracks in a bus), Utility `Bass Mono` On at 120-150 Hz after them, then run the
  polarity test (section 8.2).

### 4.3 Reese

Two detuned saws (or sines) into a low-pass, played mono. Attack's Analog version: both oscillators sine, Osc 1 up and
Osc 2 down 0.27 semitone (27 cents), Voices Mono, amp S 1.00, R 24 ms; the PWM variant uses a pulse with width 100 %, LFO 1 on
width at 0.73 and 3.2 Hz, filter about 800 Hz with Key 1.00 and Env 0 ([Attack](https://www.attackmagazine.com/technique/tutorials/reese-bass-redux/)).
Native Instruments' version: two saws +-0.30 semitone, low-pass about 650 Hz with 14 % resonance, mono; +-0.15 gives slower
beating and a mellower sound; overdrive it, then sweep a notch for movement
([NI](https://blog.native-instruments.com/reese-bass/)). The pair beats at f x (2^(2c/1200) - 1): +-30 cents is 1.5 Hz on
E0, 1.9 Hz on A0, 3.9 Hz on A1, 7.8 Hz on A2, so the wobble speeds up as the line climbs. To lock the root's wobble to
tempo (2 Hz = quarter notes at 120 BPM) use about +-30 cents on 49-55 Hz notes *(derived)*. **Keep the low end stable:** the
beating makes the fundamental's level swell, so high-pass the Reese at 100-150 Hz and add a sine sub under it.

### 4.4 Acid, 303-style, in Live

A 303 line is one oscillator, saw or square, through a resonant low-pass
([Attack](https://www.attackmagazine.com/technique/tutorials/how-to-make-an-acid-house-bassline/)); the acid character comes
from moving cutoff, resonance and envelope amount, plus accents (louder, brighter notes) and slides (glide between
overlapping notes). Live has 12 and 24 dB filters, so use the 24 dB ladder with moderate resonance.
- **Wavetable:** Osc 1 saw, `mono_poly` Mono, `Glide` 50-80 ms *(start; Glide acts in Mono mode and slides overlapping notes)*;
  `Flt 1` low-pass 24 dB, circuit (`Flt 1 LP/HP`) PRD (ladder, no resonance limiting) or MS2, `Flt 1 Drive` 3-6 dB, `Flt 1 Freq`
  300-700 Hz, `Flt 1 Res` 55-75 %; Env 2 to `Flt 1 Freq` +50-80 % with A 0, D 150-300 ms, S 0; MIDI Velocity to `Flt 1 Freq`
  +15-30 % and to volume so accents are velocity 120+ and normal notes 70-90; amp A 1 ms, S 100 %, R 20-40 ms. Write overlapping
  notes where the line should slide.
- **Process:** drive (Pedal Distortion or Saturator on the mono line is fine), EQ low cut about 85 Hz with the mids carved and
  highs lifted, dotted-eighth delay with a high-pass in the delay, reverb with its low cut rolled up to about 400 Hz so a closed
  filter stays tight and an open sweep opens into space (all from Attack's walkthrough).
- **Movement is cutoff and resonance automation,** recorded or drawn: `write_automation("Acid", "Flt 1 Freq", slot=0,
  device="Wavetable", shape={"type": "sine", "from": "350 Hz", "to": "1.8 kHz", "period": "4 bars"})`; read the curve back
  with `get_automation` (frequency parameters are not linear in raw units, so check the sampled Hz values).

### 4.5 EBM and industrial sequenced bass

EBM's bass is a repeating sequenced line under a rigid pulse (`09-industrial-ebm-techno-nin.md`). Front 242's palette was
analog (Roland System 100/100m, Yamaha CS-40M and CS-15, the Moog Source "Operating Tracks" bass) plus FM (DX7, later TG-77),
and a single bass note played at varying dynamics was new at the time
([Bonedo](https://www.bonedo.de/artikel/die-praegenden-synthesizer-von-front-242), German). No source gives parameter values;
these are starting points.
- **Analog EBM bass:** Osc 1 saw, Osc 2 square at Semi -12, -6 dB; mono; low-pass 24 dB (MS2 or PRD) 250-500 Hz, Res 15-30 %;
  Env 2 to Freq +40-60 %, D 100-150 ms, S 0; amp A 0-2 ms, D 150-250 ms, S 60-80 %, R 50-80 ms; velocity to filter for
  dynamics; Pedal Distortion Gain 30-50 % or Roar Serial (Tube Preamp into Diode Clipper) around 30-40 %; EQ Eight low cut 35 Hz;
  duck it to the kick with `set_sidechain` (threshold -30 dB, ratio 4-6, release 120-150 ms).
- **FM EBM bass:** Operator, two operators in series (B modulates A), A sine, B ratio 1 or 2 with level 40-60 % and a decay of
  80-150 ms so the first 100 ms is bright, then it settles to a near-sine; Feedback 0-20 %; keep ratios integer for a stable pitch.
- Patterns: sixteenth notes on one or two pitches with octave jumps, locked to the kick (`08-arrangement-and-composition.md`, `09-industrial-ebm-techno-nin.md`).

### 4.6 Distorted techno bass and rumble

- **Rumble from the kick.** Delay, then Reverb, then distortion, then a low-pass near 250 Hz (start there); more delay and less
  reverb is rhythmic, more reverb and less delay is dark; distortion after the reverb makes the washy tail more audible
  ([Bonedo](https://www.bonedo.de/artikel/bass-drum-rumble-rattle-for-techno), German). Menzel's version: reverb 75-100 % wet,
  then overdrive, then an EQ low-pass under 300 Hz, the rumble sidechained so it ducks fully, and Utility at the end of the
  chain to mono the lows
  ([Production Music Live](https://productionmusiclive.com/blogs/news/6-steps-to-create-that-rumbling-techno-kick-you-love-with-johannes-menzel)).
  Put it on a duplicate of the kick or an Audio Effect Rack chain, never on the kick itself.
- **Distorted saw bass.** Mono saw, low-pass 24 dB at 200-500 Hz, Pedal Distortion (Gain 30-60 %, Treble down) or Roar with
  Note-mode feedback set to the bass pitch, EQ low cut 35 Hz, Bass Mono 120 Hz. Keep it a single line or fifths and octaves.

### 4.7 Mono and in tune with the kick

Bass Mono at 120-150 Hz on every bass track. Tune by measurement: take the kick's tail (the last 100-300 ms of its bounce),
find the FFT peak between 35 and 90 Hz, convert to cents against the bass root. A 52 Hz kick tail against a 55 Hz bass note
beats at 3 Hz, an audible wobble. Retune the kick (transpose in Simpler or the drum instrument) to the tonic, or write the
bass around it (`04-drums-and-low-end.md`).

> **For an agent.** Bounce the bass alone (`bounce(stems=["Bass"])`) and run the appendix script with the root frequency:
> partial staircase for a clean sub, even-minus-odd for saturation colour, `mono_sum_loss_below_120_db` under 0.5 dB, width
> in the low bands near 0. Run the polarity test when two layers share 60-150 Hz. Ask the human before changing a bass he has
> approved; offer "sub only", "sub + mid" and "sub + mid + saturation" as three labelled, loudness-matched takes.

## 5. Leads, plucks, arps and delay throws

### 5.1 Plucks

A pluck is an amplitude envelope, a filter envelope and a transient, in that order of importance.
- **Attack's Drift lead (sourced values):** Osc 1 mix +6 dB; Osc 2 triangle, Oct 0, Detune -0.11 (about -11 cents), mix +2.5 dB;
  Noise -10 dB; filter 2 kHz, Res 0.38; Env 1 (amp) Decay 2.37 s, Sustain 24 %; Env 2 to pitch 8 % with Attack 0, Decay about
  79 ms, Sustain 0, Release 10 ms (the quick pitch blip is the transient); LP Frequency modulated by Env 1 by 10 %; `Drift`
  100 %; then Glue Compressor (threshold -21, makeup 11 dB, attack 10 ms), Delay with 3 and 4 sixteenths on L and R,
  Feedback 40 %, Dry/Wet 30 %, Reverb 3.6 s, Chorus-Ensemble 20 %, EQ Eight low cut near 60 Hz
  ([Attack](https://www.attackmagazine.com/technique/synth-secrets/detuned-festival-leads-with-ableton-drift/)).
- **General pluck (start):** Wavetable saw plus a +12 square at -8 dB; amp A 2-5 ms, D 250-600 ms, S 0-25 %, R 80-200 ms; filter
  600-1200 Hz with Env 2 +40-70 %, D 150-300 ms, S 0; MIDI Velocity to filter +15 %. A 4-5 ms attack softens a transient that
  turns harsh in reverb, and a low-pass near 18 kHz on a bright layer stops top-band harshness
  ([Attack, layered pluck](https://www.attackmagazine.com/technique/synth-secrets/mall-grab-switchblade-lead/)).

### 5.2 Arps that cut without harshness

Space first: at 1/16 notes and 120 BPM the notes are 125 ms apart, so Release <= 100 ms and Decay <= 250 ms keep notes from
smearing. Then: high-pass 150-250 Hz; low-pass 3-6 kHz at 12 dB with Res <= 15 %; amp attack 2-5 ms; a narrow velocity range
(80-110) so transients are consistent; Echo on the part with its filter set high-pass 300 Hz, low-pass 5 kHz and Ducking on
(wet drops while the dry plays); reverb send high-passed at 300 Hz with 20-40 ms predelay at 15-25 %. Cut-through comes from
separation: roll the pad off above 2-3 kHz so the arp owns 2-6 kHz (a pad can lose its top above 3-4 kHz to make room for
drums and cymbals, [Copland](https://johnnycopland.com/how-to-eq-pad-sounds)). Make width with ping-pong delay or the
Side-only chorus (7.4), not a Haas copy.

### 5.3 Leads above the mix

Mono or near-mono saw plus small-detune partner (Attack's lead detunes 11 cents), glide 20-60 ms, saturation on the mono lead
is fine, presence +2 dB around 2-4 kHz, a -2 dB bell on the pad near 2.5 kHz, reverb with 40-80 ms predelay and a 300 Hz low cut so
the lead stays in front of its own tail, delay throws for tails *(start; general practice)*.

### 5.4 Delay throws

Put the delay on a return at 100 % wet and automate the send up just before a phrase ends, so the tail carries the last note
into the gap ([Attack](https://www.attackmagazine.com/technique/tutorials/automated-delay-effects/)). Use filtering in the
feedback path so repeats get darker; in Live, Echo's HP/LP filter does this, its Ducking keeps repeats under the live part, and
Reverb Location chooses pre, post or inside the feedback loop. Example: Echo return (`Dry Wet` 100 %, `Feedback` 40-50 %, `Filter On` with `HP Freq` 300 Hz and `LP Freq` 5 kHz, `Duck On`); then open the send for one
beat at the end of bar 1 of a lead clip (two points at one time make a jump): `write_automation("Lead", "send:A", slot=0,
points=[{"time": "1.1.1", "value": -60}, {"time": "1.4.1", "value": -60}, {"time": "1.4.1", "value": -6}, {"time": "2.1.1", "value": -6},
{"time": "2.1.1", "value": -60}])` (the string "-inf dB" is accepted in display units and maps to the bottom of the send range; out-of-range display values are rejected here, not clamped as `set_device_parameters` does).

> **For an agent.** Bounce the part; a harsh pluck shows a high crest factor and strong energy above 5 kHz in
> `analyze_audio`; fix with the 4-5 ms attack or a lower low-pass and compare crest and band energy at matched loudness.
> Use `analyze_audio` onset results to confirm the rhythm survived the envelope changes. Taste (bright, sweet, biting) is the
> human's: give two labelled versions that differ in one parameter.

## 6. FX: risers, impacts, downlifters, sweeps, reverse reverb

A riser makes four ramps at once (filter opening, pitch or noise colour rising, level rising, width and reverb growing) and
ends on the downbeat. Keep every riser and sweep out of the sub (high-pass 150-300 Hz) so the drop's low end keeps its
impact. The pack Build and Drop ships risers, sirens and effects as Instrument Racks with eight macros
([Ableton](https://www.ableton.com/en/packs/build-and-drop/)); start there when a sound is needed fast and judge it by ear.

- **Noise riser (start):** Operator Osc A noise (or Analog noise) on one long note spanning 4-8 bars; Auto Filter high-pass 24 dB
  sweeping 150 Hz to 1.5 kHz and a low-pass 24 dB sweeping 600 Hz to 12 kHz with `Resonance` 15-30 %; Utility `Output` from -24 to -4 dB;
  `Stereo Width` from 80 % to 160 %; reverb send rising (digest 09 section 6.6 gives a variant: high-pass only, 300 Hz to 9 kHz over 4 or 8 bars). Attack's Pigments riser sweeps a noise's tune from -36 to +36
  semitones, high-passes it (70 %) against low rumble and low-passes it at 5-6 kHz with resonance about 0.7 against harshness,
  adds a pitch-shifting delay at maximum feedback, a tape echo at 1/2 notes, and raises the channel 6 dB as the note lifts
  ([Attack](https://www.attackmagazine.com/technique/synth-secrets/modulating-risers-with-additive-synthesis/)).
  Automate each ramp with `write_automation(..., shape={"type": "ramp", "from": ..., "to": ...})` and read it back with
  `get_automation`; frequency ramps may not be linear in Hz, so check the sampled values.
- **Endless (Shepard) riser:** four sine tracks one octave apart (A4, A3, A2, A1) in Operator, each gliding up 12 semitones over
  eight bars, Utility Gain fading the top track out (0 dB to -inf) and the bottom one in, a full-wet reverb on the group to hide
  the loop click ([Attack](https://www.attackmagazine.com/technique/tutorials/how-to-make-an-endless-riser/)).
- **Impact (start):** (1) sub boom: Operator sine tuned to the key (36-55 Hz) with a pitch envelope dropping about 24 semitones in
  120-300 ms, amp decay 1.5-3 s; (2) a short thud 80-200 Hz; (3) a noise or cymbal burst, low-passed, decay 0.5-1.5 s; (4) a
  100 % wet reverb tail on a bus (decay 4-8 s, high-pass 150 Hz, low-pass 3-6 kHz). Leave a 1/16-1/8 note of near silence
  before it. Saturating the summed hit is fine; it is one event, not a chord.
- **Downlifter:** the riser mirrored: low-pass 10 kHz down to 300 Hz over 1-2 bars, pitch falling 12-24 semitones, noise fading
  out; or reverse the riser audio.
- **Reverse reverb:** (1) bounce the sound (a chord or a snare); (2) put a Reverb or Hybrid Reverb at 100 % wet with decay 2-4 s
  and a low cut near 200 Hz on a copy, and render a bar longer than the sound; (3) reverse the render (Reverse button in Clip
  View, which creates a new sample; in Arrangement select the range and press R,
  [manual](https://www.ableton.com/en/live-manual/12/clip-view/)); (4) place it so the swell ends on the original's onset,
  nudged earlier by 0-30 ms; (5) mute the dry reverb copy.

> **For an agent.** After bouncing, check: energy under 120 Hz in third-octave bands at least 40 dB under the peak band; the
> loudness curve rising monotonically through the riser; the last transient or peak within 20 ms of the target bar line;
> no click at the cut. Ask the human to judge length and intensity: give "4 bars" and "8 bars" as labelled options.

## 7. Width and size

### 7.1 Unison and detune: how much, and how to measure it

| Instrument | Controls | Start for a clean pad body | Notes |
| --- | --- | --- | --- |
| Wavetable | properties `unison_mode`, `unison_voice_count`; parameter `Unison Amount` | Classic, 3-4 voices, Amount 10-15 %, then calibrate to outer voices about +-4-10 cents | Classic = equal spacing, alternate pan. Shimmer and Noise jitter the pitch (noisy by design), Phase Sync locks phases and sweeps like a phaser, Position Spread and Random Note change timbre ([manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)) |
| Drift | property `voice_mode` Stereo (2 voices per note, `Spread`) or Unison (4 voices, `Strength`); `Drift` | Stereo `Spread` 30-60 % or Unison `Strength` 10-25 %; `Drift` 10-35 % on chords, 0 on subs | Voices per note divide the 32-voice pool |
| Analog | `Unison On/Off`, `Unison Voices` (2 or 4), `Unison Detune`, Delay | 2 voices, small detune | the oscillators are modelled, so there is no aliasing |
| Operator | `Spread` | small | two voices per note, detuned and panned, set at note-on, CPU heavy |
| Meld | property `unison_voices` (the UI's Stacked Voices), parameter `Voice Spread` | off, or 2 | Spread does nothing until it is routed to a target in the matrix (the manual lists Spread as a modulation source) [verify by measurement]; stacked voices duplicate both engines |

The unison amounts of Wavetable and Drift are not in cents (digest 02 section 1.3). **Calibrate once per patch:** render a held A1
(110 Hz), run `unison_spread_cents` (appendix) on the 8th partial (a single voice reads about 3 cents; subtract it), and move the
amount until the outer voices sit at +-4-10 cents for a pad body (+-20-45 cents is the supersaw regime; Szabo's measurements put
the JP-8000's outer saws at +-9 cents with the knob at 24 % and +-18 at 50 %). To keep low notes steady, key-scale the amount:
Wavetable's `Unison Amount` is a multiplicative modulation destination and the MIDI tab offers Note as a source (centred on C3), so
a positive Note amount gives notes below C3 less unison and notes above it more; verify at three pitches before trusting it. Prefer the separate root layer
of Recipe A when the low root must be rock steady.

### 7.2 Chorus-Ensemble settings

Chorus mode adds two time-modulated delays; Ensemble uses three delay lines with evenly split modulation phase offsets, which
is richer and smoother; Vibrato modulates pitch only. `Width` (0-200 %) balances the wet signal between mid and side, `HP On` and
`HP Freq` (20 Hz-2 kHz) reduce the modulation below that frequency, `Warmth` adds distortion, `FB Invert` makes high-feedback
settings hollow. Per the manual, `Delay Time` (items Auto, 7, 10, 20, 35 and 50 ms; Auto scales with the modulation, a fixed value keeps the pitch steady) and `Delay Taps` (1 or 2)
are the two extra controls of Chorus mode only, and digest 12 section 5.1 agrees; they are inactive in Ensemble and Vibrato, so read `get_device` after switching modes
([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)). Reid's account of the classic ensemble: three delay lines
modulated 120 degrees apart; slow sweeps (a fraction of a hertz) give a gentle chorus, 5-7 Hz a typical synth ensemble; the minimum
modulation depth is what you want; the stereo version feeds different delay lines to left and right
([SOS](https://www.soundonsound.com/techniques/more-creative-synthesis-delays)).

| Purpose | `Mode` | `Rate` | `Amount` | `Width` | `HP Freq` | `Feedback` | `Dry/Wet` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Clean, slow pad width | Ensemble | 0.3-0.6 Hz | 20-30 % | 100-140 % | 200-250 Hz | 0 | 30-40 % |
| Juno-like shimmer | Chorus, 2 taps | 0.4-0.6 Hz | 40-60 % | 100-140 % | off or 150 Hz | 0 | about 50 % |
| String-ensemble motion | Ensemble | 0.8-1.5 Hz | 40-60 % | 100-140 % | 200 Hz | 0 | 40-50 % |
| Width for plucks and arps (on a return) | Chorus | 0.8-1.5 Hz | 30 % | 150 % | 300 Hz | 0 | 100 % |
| Steady pitch on a low part | Chorus, fixed `Delay Time` 20 ms | 0.3 Hz | 10-20 % | 100 % | 200 Hz | 0 | 20-30 % |

All rows *(start)*. `Warmth` 0 on chords. Avoid `Feedback` above 0, `FB Invert` on, and `Rate` above 1.5 Hz with `Amount` above 40 %: that is
the flanger regime. Never on noise, never on the root layer.

### 7.3 Haas delays and their mono risk

The Haas zone is delays below about 30-40 ms; below roughly 5 ms the direction follows the first arrival, above it the sound
grows in spaciousness, and a delayed copy can be up to 10 dB louder without moving the image
([iZotope](https://www.izotope.com/en/learn/what-is-the-haas-effect)). The price is comb filtering when the channels sum:

| Delay | First notch | Then every |
| --- | --- | --- |
| 1 ms | 500 Hz | 1000 Hz |
| 5 ms | 100 Hz | 200 Hz |
| 10 ms | 50 Hz | 100 Hz |
| 20 ms | 25 Hz | 50 Hz |
| 30 ms | 17 Hz | 33 Hz |

(derived from the comb filter relation, section 1.) Rules: never on a sustained pad, bass or lead; acceptable on short, high-passed
parts (plucks, arps) at 8-15 ms, the delayed copy 3-6 dB down and high-passed at 300 Hz or more; always check the mono sum. In Live the
`Delay` device accepts 1 ms to 5 s per channel; `Echo` has a Stereo/Ping Pong/Mid/Side `Channel Mode`. iZotope's safer variant applies the
delay to the Side channel only, so the delayed copy cancels itself in mono instead of combing; the rack in 7.4 does this.

### 7.4 Mid/side EQ, Utility and the side-only rack

- **EQ Eight, M/S mode** (property `global_mode` `mid_side`, `edit_mode` `a`/`b` switches between M and S): a low cut on the Side channel at 150-200 Hz,
  12 or 48 dB per octave (EQ Eight has no 24 dB cut), forces the lows to the centre and removes stereo from the region where it hurts; the cut belongs on the Side curve only
  ([Aulart](https://www.aulart.com/blog/mid-side-equalization-what-is-it-and-when-to-use-it/) on high-passing the stereo content of the lows,
  [MusicRadar](https://www.musicradar.com/how-to/mid-side-eq-ableton) on EQ Eight's M/S mode). A gentle high shelf on the Side for air is common practice *(start)*. Johnny Copland high-passes a drone pad up to 200 Hz and rolls its top
  off above 3-4 kHz as well ([Copland](https://johnnycopland.com/how-to-eq-pad-sounds)).
- **Utility** (`StereoGain`): `Stereo Width` 0-200 % (0 mono; in the manual's Mid/Side mode the control runs from 100M mono to 100S sides only);
  `Mono`; `Bass Mono` with `Bass Freq` 50-500 Hz and an Audition switch; `Left Inv`/`Right Inv`. Width above 100 % lifts the side level: start at
  100-115 % on a pad and measure ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)). Bass Mono is a crossover, so
  put it last in the chain and set it no higher than needed.
- **Side-only rack.** An Audio Effect Rack with two chains, each starting with Utility in Mid/Side mode: chain "Mid" at 100M, chain "Side" at
  100S. Put chorus, delay or reverb (100 % wet) and an EQ Eight low cut at 200 Hz in the "Side" chain only. MusicRadar shows the same split in Live
  and processes the sides separately (compressing the mids, adding reverb to the sides). For strict mono safety use effects that treat left and
  right identically (EQ, linked delay), so the added content stays out of phase and cancels in mono. If `Stereo Width` does not expose the Mid/Side
  switch through the API, use EQ Eight in M/S mode and chorus with `HP On` instead.

### 7.5 Reverb as width, and "washy" versus "big"

Narrow the dry and widen with the tail: in Attack's atmosphere tutorial the chords go to 50 % width in Utility and a send reverb spreads them again (a Glue
Compressor sidechained to the loop makes the wash pump), while the arp gets its own chorus-only send at full width
([Attack](https://www.attackmagazine.com/technique/tutorials/adding-atmosphere-with-delay-and-reverb/)); iZotope suggests narrowing a pad partially (full mono can cause phasing)
and panning its reverb to the other side ([iZotope](https://www.izotope.com/en/learn/5-tips-for-mixing-pads)). In Live: Reverb `Stereo Image` goes to 120 degrees
for independent left and right tails and has input low and high cuts; Hybrid Reverb has `Width`, an EQ tab (Pre Algo switch) and `Bass Mono` at 180 Hz; its Prism
algorithm is a "ghost" reverb that adds depth without crowding the source, while Tides ripples the spectrum and Shimmer climbs in pitch (neither is clean)
([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)).

| Problem | Cause | Fix |
| --- | --- | --- |
| **Washy** | long, dense tail with no predelay; low end in the tail; reverb filling the gaps | predelay 30-60 ms; `Decay` shorter than the chord (about one bar at the tempo); low cut 250-400 Hz and high cut 5 kHz in the wet signal; send -18 to -12 dB; duck the return from the source or the kick (`set_sidechain` if the return accepts it); `Modulation` 0 |
| **Flangy** | see 2.7 | `Feedback` 0, high-pass in the chorus, nothing modulated on noise |
| **Big and clean** | octave layers, a mono root, small unison, slow Ensemble in the sides, a filtered tail, 3-6 dB of reverb behind a clear dry | build in this order, one step at a time |

> **For an agent (width).** Bounce the stem, run the appendix script: `width_by_band` (below 120 Hz at most 0.1; above 200 Hz about 0.75-0.95 for the "very wide"
> target; a mono-sum loss under 0.5 dB below 120 Hz), and `analyze_audio` for overall correlation and mono-sum loss. Ableton notes that a correlation
> meter dropping below zero signals phase trouble ([blog](https://www.ableton.com/en/blog/pad-it-out-10-ways-make-distinctive-pad-sounds/)); `06-mixing.md` treats sustained negative
> values as a fail. After each width move re-measure; if the mono loss rose, undo the widener first. Do not widen in several places at once (unison, chorus, Utility, reverb):
> change one, measure, ask.

## 8. Layering

### 8.1 Split a sound into sub, body and top

| Layer | Range | Source | Processing |
| --- | --- | --- | --- |
| Sub | 20-120 Hz | a sine, or a saw low-passed at 100-130 Hz; one voice, `Drift` 0, retrigger on | low cut 24 dB at 25-30 Hz; low-pass 24-48 dB at 100-130 Hz if it has harmonics; mono; no chorus, no unison |
| Body | 100-1500 Hz | saw-like, the real timbre | high-pass 24-48 dB at 100-130 Hz; low-pass 2-3 kHz for pads; unison and saturation (per voice) live here |
| Top | 1.5-8 kHz | the body an octave up, or noise-free shimmer | high-pass 800 Hz-1 kHz, low-pass 4-6 kHz, level -10 to -14 dB, widest |

Build it as chains of one Instrument Rack when the layers share notes (a bass): `add_device(track, "Instrument Rack")`, a chain per layer
(`add_device(track, "Wavetable", chain="Instrument Rack/new")` makes the chain and puts the device in it; later `Instrument Rack/0`, `/1` address existing chains), EQ Eight inside each chain for the crossover (EQ Eight low and high cuts run at 12 or 48 dB per
octave), `set_chain(track, rack, chain, name=..., volume_db=...)` for names and balance. Rack key zones cannot be set through the tools, so when layers
need different notes (a pad's root versus its chord) use a MIDI **Pitch** effect with `Mode` Block and `Lowest`/`Range` at the head of each chain, or separate
clips on separate tracks. Octave layering works as in Mode Audio's recipe: duplicate the MIDI, transpose -12 for weight with the low layer low-passed near
550 Hz, +12 for shine with its low-pass set so it does not jump out, then compress the bus, add a touch of chorus and reverb
([Mode Audio](https://modeaudio.com/magazine/quick-tips-015-unison-layering)); apply it to single notes or the upper chord notes, never so that a chord's
thirds drop below the limits in 8.3.

### 8.2 Phase and tuning between layers

- **Tuning:** layers share the same MIDI notes and differ only by whole octaves; no detune on the sub; `Drift` 0 and retrigger on where the instrument has them.
  Verify by rendering each layer alone and reading the lowest peak with the appendix FFT: within 2 cents of each other.
- **Timing first, then polarity.** Layered sounds can cancel where their waveforms oppose, which leaves a thin, weak result even from two fat sounds. Align the
  transients, then flip the polarity of one layer (Utility `Left Inv` and `Right Inv` together) and keep whichever is fuller; inverting both equals inverting
  neither ([Attack](https://attackmagazine.com/technique/tutorials/layering-kick-drum-samples/2)). **Measurable version:** bounce the two layers solo and the sum
  twice (polarity normal and inverted); keep the setting whose 60-150 Hz band level is higher; a difference over 1.5 dB means the first setting was costing weight.
- Two panned copies of the same patch cancel in mono; give layers comparable but different sounds or keep both centred (digest 04, sections 3.4 and 3.5).
- Crossovers: matching 24 dB slopes at the same frequency, minimal overlap, and no resonance at the corner.

### 8.3 Low interval limits (what may sound together, and how low)

Roughness comes from partials closer than a critical band, so each interval has a lowest register in which it stays clear. The classic chart in
orchestration texts ([Robin Hoffmann](https://www.robin-hoffmann.com/dfsb/low-interval-limits), which holds it as an image; Sweetwater's text gives
the same idea, [Sweetwater](https://www.sweetwater.com/insync/make-orchestrations-sound-more-balanced/)) is a guideline: soft low voicings on strings are more
forgiving than loud ones on brass, rich saw timbres behave like brass, and when the lowest note is not the root, imagine the root present. I read the
printed chart's note heads directly; the values below can be off by a semitone (Sweetwater puts the major third at B1-D#2 in Live names, MIDI 47 and 51).
This is the permissive chart, not the rule this set follows: the rule under the table is stricter for thirds and seconds.

| Interval (semitones) | Lowest lower note (MIDI, Live name, Hz) |
| --- | --- |
| Octave (12) | no limit |
| Major 10th (16), perfect 5th (7) | 34, A#0, 58 Hz |
| Minor 10th (15) | 36, C1, 65 Hz |
| Major 9th (14), minor 9th (13) | 39 D#1 78 Hz, 40 E1 82 Hz |
| Major 6th (9), minor and major 7th (10, 11) | 41, F1, 87 Hz |
| Minor 6th (8) | 43, G1, 98 Hz |
| Perfect 4th (5), tritone (6), major 3rd (4) | 46, A#1, 117 Hz |
| Minor 3rd (3) | 48, C2, 131 Hz |
| Major 2nd (2) | 51, D#2, 156 Hz |
| Minor 2nd (1) | 52, E2, 165 Hz |

**Practical rule** (the one used across this set: `00-agent-playbook.md` rule 4 and `08-arrangement-and-composition.md` section 2.5, stricter than the chart for every third and
second): below about 130 Hz (Live C2) only roots, fifths and octaves; major thirds from about 165 Hz (E2); minor thirds and seconds higher still (the derived ERB bound for a
minor third is a root near 304 Hz, D#3); the lowest sounding note is the chord root. Sixths and sevenths from about 87-98 Hz in open spacing (chart); an open voicing (root, fifth,
tenth) puts a third into a low chord. A third whose lower note is at 55-65 Hz sits 10-15 semitones (about an octave) below the chart's limit, which is why a sub-octave voice sounded
wrong. Digest 08 section 2.5 treats this at length, with the same chart pitches and derived ERB columns next to them. `voicing_problems` (appendix) checks adjacent pairs against the
chart table only, so also apply the rule above by hand. The same limits apply across tracks: a pad note a semitone or a whole tone from a
sustained bass note (variation B's D against the bass's E in the NOVA set) is a low second between two stems. `analyze_notes` flags stems a semitone apart
(`notes.clash`) but not whole tones, so check seconds across stems yourself against the table.

### 8.4 Harmonic saturation per layer, not per chord

Why: section 1, fact 5. How:
1. **Per voice, inside the synth.** Voice filters act before voices sum, so notes do not intermodulate: Wavetable `Flt n Drive` on non-Clean circuits, Analog's
   filter Drive, Meld's `Drive` (it sits in the mixer, before the per-voice limiter), Drift's two saturation points in the filter. Keep oscillator gains at or under the default in Drift.
2. **Per layer.** Saturate single-note layers (root, bass, lead, arp) on their own track or chain; it is one note, so no intermodulation.
3. **If a chord must be coloured:** keep the lows out of the shaper (Saturator `Color On` with negative `Color Amt Low` [verify the sign range, digest 12 section 4.1], or high-pass before it and mix in parallel;
   Roar in Multi Band with only the mid or high band driven); symmetric curves, 1-3 dB of drive, `Dry/Wet` 30-50 %; fifths and octaves tolerate more than thirds.
4. **Off by default on chords:** chorus/phaser `Warmth`, Echo's input distortion, Hybrid Reverb `Vintage`, Pedal, Roar, any limiter.
5. **Verify:** render the same chord with and without the effect and run `off_series_peaks`: a clean chord shows none below 1 kHz; a saturated sum showed dozens of
   new peaks in my synthetic test (about -24 dB for a minor triad), while per-voice saturation showed none. A saturated fifth gives fewer, and some land on the
   common sub-harmonic series (coherent): read counts and levels together.

> **For an agent (layering).** Before touching a layered patch, store the state (device A/B via `set_device(compare_b=True)`, a muted twin, or a take snapshot).
> Check tuning and polarity of each layer by measurement (8.2), voicing by `voicing_problems` (8.3) and `analyze_notes`, saturation by `off_series_peaks` (8.4).
> If the sum feels "out of tune", the order of suspects is: thirds below the limit, saturation on the sum, `Drift`/unison on low notes, then layer detune.

## 9. Matching a reference (listen, describe, identify, build, compare, iterate)

You cannot hear the reference, so work from the producer's words and from numbers measured on exposed passages. The method, in order:

1. **Freeze the base.** Duplicate the producer's chosen sound to a muted twin (`duplicate_track(track, name="Pad BASE (keep)")`, `set_mixer(..., mute=True)`;
   for a device, A/B via `set_device(compare_b=True)`; a `capture` take stores every device parameter and can be restored with `takes`). Never edit it.
2. **Listen (the human).** Ask for three to five adjectives (big, heavy, clean) and the reference moment. Measure the reference's exposed section with `ref`/`analyze_audio`
   (sections) for facts, never as a target for the whole mix.
3. **Describe as a sound card**, then identify what produces each line:

   ```
   register:  lowest fundamental 41-49 Hz (MIDI 28-31); chord body from MIDI 52
   partials:  saw-like, about 1/n up to ~2 kHz, roll-off above
   noise:     low (valley depth at least the base's)
   movement:  slow, 0.05-0.1 Hz; attack 1+ s; release 3 s
   stereo:    side/mid 0.75-0.95 above 200 Hz, mono below 120 Hz
   effects:   reverb Dark Hall ~5 s, 30 % wet; no chorus on noise; no saturation
   words:     big, heavy, clean; not hollow, airy, flangy, distorted
   ```

   | Descriptor | Likely source | Device and parameter |
   | --- | --- | --- |
   | thick, buzzy | saw stack | oscillator shape, unison |
   | dark, round | low-pass 12-24 dB at 0.5-1.5 kHz | `Flt 1 Freq`, slope |
   | evolving | slow envelope or LFO on cutoff or table position | Env 2, LFO 1 at 0.03-0.1 Hz |
   | wide | unison or Ensemble in the sides, reverb | 7.1-7.5 |
   | weight | root layer, octave layer | 2.2, 8.1 |
4. **Build the minimum**, in this order: oscillator and register, filter, amp envelope, movement, width, space. After each stage render the held-note clip and compare
   the card line it addresses (one stage, one measurement).
5. **Compare** on matched loudness (integrated LUFS of the same passage within 0.2 LU, 0.3 LU at most, set with a Utility `Output` trim, never with a limiter or compressor): the
   level-independent numbers (third-octave `relative_db` from `ears.measure.third_octave_levels`, partial staircase, `width_by_band`, mono loss) against the base and the card; flag differences above about 3 dB.
6. **Iterate one parameter at a time**, logging parameter, old and new value, measured effect, the human's verdict. Revert on regression.
7. **Hand over** labelled: "A = base (unchanged), B = base plus one change (what), same 8 bars, level matched within 0.2 LU, order A B A B." Announce the order before playing.
   The producer reacts live; keep his pick untouched and change only what he names.

**Ask the human** before: replacing or adding to a sound he approved; switching oscillator types, unison or voice modes; adding saturation, chorus, a limiter or any bus
or mix-wide processing; changing a track he did not name; keeping a preset whose numbers and ears disagree; more than three auditions at once.

## 10. Agent checklist

| Measure | How | Healthy for the "big, heavy, clean" target | Red flag |
| --- | --- | --- | --- |
| Lowest peak vs MIDI pitch | appendix script | within 2 cents | over 10 cents: `Drift`, detune, pitch envelope |
| Partial staircase | `partials_db` | about -6, -9.5, -12, -14 dB to the filter corner, within 3-4 dB | holes at even partials (hollow); early steep roll-off (dull) |
| Even minus odd | `even_minus_odd_db` | -3 to 0 dB (saw-like) | below -10 dB |
| Valley depth | `valley_depth_db` | at least the base take's | far below the base, or under about 30 dB: noise or smear |
| Noise share | `between_partials_share_pct` | at most the base's; under about 1 % *(guideline)* | over 2 %: airy, raspy |
| Width by band | `width_by_band` | below 120 Hz at most 0.1; above 200 Hz 0.75-0.95 | above 0.2 in the lows; under 0.5 or over 1.2 above 200 Hz |
| Mono-sum loss below 120 Hz | `mono_sum_loss_below_120_db` | 0.5 dB or less | over 1 dB |
| Whole-band mono loss | `analyze_audio` | 1-3 dB for a wide pad *(guideline)* | over 4-6 dB or deep notches |
| Off-series peaks | `off_series_peaks` | none before and after a saturator | dozens after |
| Loudness for A/B | `analyze_audio` LUFS | within 0.2 LU (0.3 LU at most) | mismatched: louder sounds better |
| Headroom | `analyze_audio` peak | 6 dB or more on stems, no limiter | clipping or pumping |
| Third-octave 160-315 Hz | `analyze_audio` | not above the base | mud |

Mistakes that cost a day (2026-10-08): ranking presets by spectral distance to a full-mix reference; choosing a sub-oscillator-plus-noise voice; saturating whole chords;
chorus on noise; True Peak limiters and broad EQ on every stem at once; replacing the producer's pick; many changes in one pass; unlabelled auditions; no loudness match.

## Appendix: measurement script

Tested on synthetic signals only (saw, square, saw plus noise, a 7-voice unison, clean and saturated chords); not yet validated on bounces from Live. Save as
`pad_tools.py` in the repo root; it uses numpy, scipy and the repo's `ears` package (`audio.read`, `measure.stereo`, `measure.mono_sub`). Run:
`uv run python pad_tools.py "<bounce>.wav" 55 --start 1 --seconds 4`.

```python
"""Held-note measurements for sound design."""
import numpy as np
from scipy import signal as sg
from ears import audio, measure


def _db(x):
    return 10 * np.log10(np.asarray(x) + 1e-30)


def _band_energy_db(power, freqs, centre, cents):
    """Energy within +-cents of a partial: a detuned unison spreads one partial over several peaks, so sum, not max."""
    sel = (freqs >= centre * 2 ** (-cents / 1200)) & (freqs <= centre * 2 ** (cents / 1200))
    return float(_db(power[sel].sum())) if sel.any() else -300.0


def held_note_report(path, f0, start_s=1.0, seconds=4.0, harmonics=24, cents=35):
    """Partial staircase, even-minus-odd, valley depth, width per band and mono-sum loss of a held note at f0 Hz."""
    a = audio.read(path).slice(start_s, start_s + seconds)
    rate, n = a.rate, a.frames
    power = np.mean([np.abs(np.fft.rfft(a.samples[:, c] * np.hanning(n))) ** 2 for c in range(a.channels)], axis=0)
    freqs = np.fft.rfftfreq(n, 1 / rate)                       # power averaged over channels: no mono cancellation
    ks = [k for k in range(1, harmonics + 1) if k * f0 < 0.45 * rate]
    peak = np.array([_band_energy_db(power, freqs, k * f0, cents) for k in ks])
    valley = np.array([_db(np.median(power[(freqs >= (k + .3) * f0) & (freqs <= (k + .7) * f0)])) for k in ks[:-1]])
    rel = peak - peak.max()                                    # dB re the strongest partial
    gaps = sum(power[(freqs >= (k + .3) * f0) & (freqs <= (k + .7) * f0)].sum() for k in ks[:-1])
    total = power[(freqs >= .5 * f0) & (freqs <= (ks[-1] + .5) * f0)].sum()
    out = {"partials_db": {k: round(float(v), 1) for k, v in zip(ks, rel)},
           "even_minus_odd_db": round(float(rel[1::2].mean() - rel[0::2].mean()), 1),   # saw about -1, square very low
           "valley_depth_db": round(float(np.mean(peak[:-1] - valley)), 1),            # compare with the base take
           "between_partials_share_pct": round(float(100 * gaps / total), 2)}          # noise share: energy off the partials
    if a.channels == 2:
        width = {}
        for name, (lo, hi) in {"<120": (None, 120), "120-500": (120, 500), "500-2k": (500, 2000), ">2k": (2000, None)}.items():
            sos = (sg.butter(4, hi, "low", fs=rate, output="sos") if lo is None else
                   sg.butter(4, lo, "high", fs=rate, output="sos") if hi is None else
                   sg.butter(4, [lo, hi], "band", fs=rate, output="sos"))
            width[name] = round(measure.stereo(audio.Audio(sg.sosfiltfilt(sos, a.samples, axis=0), rate))["width"], 2)
        out["width_by_band"] = width                           # side RMS / mid RMS: 0 mono, about 1 very wide
        out["mono_sum_loss_below_120_db"] = round(measure.mono_sub(a, cutoff=120.0)["loss_db"], 2)
    return out


def unison_spread_cents(path, f0, partial=8, start_s=1.0, seconds=4.0, drop_db=20.0):
    """Width in cents of the spectral cluster around one partial: about the outer-voice spread of a unison stack.
    A single voice reads about 3 cents (window width); subtract that."""
    a = audio.read(path).slice(start_s, start_s + seconds)
    x = a.mono()
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)), n=4 * len(x))) ** 2
    freqs = np.fft.rfftfreq(4 * len(x), 1 / a.rate)
    c = partial * f0
    sel = (freqs > c * 2 ** (-100 / 1200)) & (freqs < c * 2 ** (100 / 1200))
    p, f = spec[sel], freqs[sel]
    keep = f[p > p.max() * 10 ** (-drop_db / 10)]
    return float(1200 * np.log2(keep.max() / keep.min()))


def off_series_peaks(path, midi_notes, start_s=1.0, seconds=4.0, within_db=40, tol_cents=20, harmonics=40, f_max=1000.0):
    """Spectral peaks (20 Hz to f_max, within `within_db` of the strongest) that sit on no partial of any chord note.
    Compare a chord render before and after a saturator: dozens of new off-series peaks means intermodulation.
    Products of a fifth can still land on the common sub-harmonic series: read counts and levels, not one number."""
    a = audio.read(path).slice(start_s, start_s + seconds)
    x, n = a.mono(), len(a.mono())
    spec = _db(np.abs(np.fft.rfft(x * np.hanning(n), n=2 * n)) ** 2)
    freqs = np.fft.rfftfreq(2 * n, 1 / a.rate)
    peaks, _ = sg.find_peaks(spec, height=spec.max() - within_db, distance=max(1, int(2 * n / a.rate * 0.5)))
    grid = np.array([440 * 2 ** ((m - 69) / 12) * k for m in midi_notes for k in range(1, harmonics + 1)])
    hits = [(round(float(freqs[p]), 1), round(float(spec[p] - spec.max()), 1)) for p in peaks
            if 20 <= freqs[p] <= f_max and np.min(np.abs(1200 * np.log2(freqs[p] / grid))) > tol_cents]
    return {"off_series_count": len(hits), "strongest": sorted(hits, key=lambda h: -h[1])[:6]}   # (Hz, dB re max)


# Lowest MIDI note of the lower voice for each interval in semitones, read off the printed low-interval-limit chart
# (+-1 semitone); octaves and intervals above a major tenth have no limit. Live naming: MIDI 60 = C3.
# This is the permissive chart: the project rule (section 8.3) is stricter for thirds and seconds, so apply it by hand too.
LOW_LIMIT = {1: 52, 2: 51, 3: 48, 4: 46, 5: 46, 6: 46, 7: 34, 8: 43, 9: 41, 10: 41, 11: 41, 13: 40, 14: 39, 15: 36, 16: 34}


def voicing_problems(midi_notes):
    """(lower, upper, semitones, lowest_allowed) for every adjacent pair below the limit. Assume the root is present."""
    notes = sorted(midi_notes)
    return [(lo, hi, hi - lo, LOW_LIMIT[hi - lo]) for lo, hi in zip(notes, notes[1:]) if lo < LOW_LIMIT.get(hi - lo, 0)]


if __name__ == "__main__":
    import argparse
    import json
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("f0", type=float)
    p.add_argument("--start", type=float, default=1.0)
    p.add_argument("--seconds", type=float, default=4.0)
    args = p.parse_args()
    print(json.dumps(held_note_report(args.path, args.f0, args.start, args.seconds), indent=1))
```

Test results on the synthetic files, for orientation: a 55 Hz saw gave -6.0, -9.5, -12.0 dB for partials 2-4 and even-minus-odd -1.3 dB; a square gave a hole of
more than 150 dB at even partials; saw plus noise at -24 dB cut the valley depth from 180 dB (noise-free) to 54 dB; a 7-voice unison spread of +-12 cents read
26.8 cents (a single voice reads 3.0); `voicing_problems([33, 36, 40])` flags both thirds, `voicing_problems([33, 52, 57, 60, 64])` returns nothing. Noise calibration (a saw at 55 Hz plus noise low-passed at 1 kHz, at -30, -20, -12 and -6 dB relative to the tone): valley depth 48, 38, 31 and 27 dB, between-partials
share 0.04, 0.35, 2.1 and 7.1 %. So a pad reading under about 30 dB and over 2 % has noise within roughly 12 dB of the tone and will sound airy. Real bounces have noise floors and
reverb tails (render the dry pad for this test), so compare against the base take rather than against these numbers.

## Sources

Ableton and the packs
- [Live 12 manual: Audio Effect Reference](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/) (Chorus-Ensemble, Utility, Saturator, Roar, Pedal, EQ Eight, Echo, Delay, Reverb, Hybrid Reverb, Shifter, Spectral Resonator and Time)
- [Live 12 manual: Instrument Reference](https://www.ableton.com/en/live-manual/12/live-instrument-reference/) (Wavetable, Drift, Analog, Operator, Meld)
- [Live 12 manual: MIDI Effect Reference](https://www.ableton.com/en/live-manual/12/live-midi-effect-reference/) (Pitch with Block mode, Velocity) and [Clip View](https://www.ableton.com/en/live-manual/12/clip-view/) (Reverse)
- [Ableton blog: Pad it out, 10 ways to make distinctive pad sounds](https://www.ableton.com/en/blog/pad-it-out-10-ways-make-distinctive-pad-sounds/)
- Packs: [Drone Lab](https://www.ableton.com/en/packs/drone-lab/), [Granulator III](https://www.ableton.com/en/packs/granulator-iii/), [Build and Drop](https://www.ableton.com/en/packs/build-and-drop/), [Mood Reel](https://www.ableton.com/en/packs/mood-reel/), [Synth Essentials](https://www.ableton.com/en/packs/synth-essentials/), [Glitch and Wash](https://www.ableton.com/en/packs/glitch-and-wash/)
- [Robert Henke: Granulator III](https://roberthenke.com/technology/granulator3.html)

Magazines and tutorials
- Attack Magazine: [Detuned Pad](https://www.attackmagazine.com/technique/synth-secrets/detuned-pad/), [Cold Pads](https://www.attackmagazine.com/technique/tutorials/cold-dark-pads/), [Ambient pad (Hive 2)](https://www.attackmagazine.com/technique/synth-secrets/the-ambient-pad-that-holds-it-all-together/), [Drift detuned lead](https://www.attackmagazine.com/technique/synth-secrets/detuned-festival-leads-with-ableton-drift/), [Reese Bass Redux](https://www.attackmagazine.com/technique/tutorials/reese-bass-redux/), [Acid house bassline](https://www.attackmagazine.com/technique/tutorials/how-to-make-an-acid-house-bassline/), [LCD-style drones](https://www.attackmagazine.com/technique/synth-secrets/making-lcd-soundsystem-style-drones/), [Drones from drums](https://www.attackmagazine.com/technique/tutorials/drones-from-drums/), [Resampled pads](https://www.attackmagazine.com/technique/synth-secrets/resampled-pads-with-spitfire-audio-tundra-ableton-simpler/), [Layered pluck lead](https://www.attackmagazine.com/technique/synth-secrets/mall-grab-switchblade-lead/), [Endless riser](https://www.attackmagazine.com/technique/tutorials/how-to-make-an-endless-riser/), [Modulating risers](https://www.attackmagazine.com/technique/synth-secrets/modulating-risers-with-additive-synthesis/), [Automated delay effects](https://www.attackmagazine.com/technique/tutorials/automated-delay-effects/), [Adding atmosphere with delay and reverb](https://www.attackmagazine.com/technique/tutorials/adding-atmosphere-with-delay-and-reverb/), [Layering kick drum samples (phase)](https://attackmagazine.com/technique/tutorials/layering-kick-drum-samples/2)
- Sound On Sound: [Synthesizing strings, string machines](https://www.soundonsound.com/techniques/synthesizing-strings-string-machines), [Creating analogue sounds on digital synths, part 2](https://www.soundonsound.com/techniques/creating-analogue-sounds-digital-synths-part-2), [More creative synthesis with delays](https://www.soundonsound.com/techniques/more-creative-synthesis-delays)
- [AULART: ever-evolving Wavetable pad](https://www.aulart.com/blog/create-an-ever-evolving-pad-from-scratch-with-abletons-wavetable/); [MusicRadar: classic 80s pad](https://www.musicradar.com/how-to/how-to-build-a-classic-80s-pad-sound); [MusicRadar: mid/side EQ in Ableton](https://www.musicradar.com/how-to/mid-side-eq-ableton); [MusicRadar: Granulator III](https://www.musicradar.com/how-to/granulator-iii-ableton-live-12)
- [iZotope: 5 tips for mixing pads](https://www.izotope.com/en/learn/5-tips-for-mixing-pads); [iZotope: the Haas effect](https://www.izotope.com/en/learn/what-is-the-haas-effect)
- [Mode Audio: sub bass layering](https://modeaudio.com/magazine/quick-tips-009-sub-bass-layering); [Mode Audio: unison layering](https://modeaudio.com/magazine/quick-tips-015-unison-layering); [Native Instruments: Reese bass](https://blog.native-instruments.com/reese-bass/)
- [Bonedo: kick rumble and rattle](https://www.bonedo.de/artikel/bass-drum-rumble-rattle-for-techno) (German); [Production Music Live: rumbling techno kick](https://productionmusiclive.com/blogs/news/6-steps-to-create-that-rumbling-techno-kick-you-love-with-johannes-menzel); [Bonedo: Front 242 synthesizers](https://www.bonedo.de/artikel/die-praegenden-synthesizer-von-front-242) (German)
- [Johnny Copland: EQ for pad sounds](https://johnnycopland.com/how-to-eq-pad-sounds); [Aulart: mid/side EQ](https://www.aulart.com/blog/mid-side-equalization-what-is-it-and-when-to-use-it/)
- [Production Expert: intermodulation distortion](https://www.production-expert.com/production-expert-1/intermodulation-distortion-the-audio-problem-you-may-be-overlooking)
- [Sweetwater inSync: low interval limits](https://www.sweetwater.com/insync/make-orchestrations-sound-more-balanced/); [Robin Hoffmann: low interval limits](https://www.robin-hoffmann.com/dfsb/low-interval-limits)

Reference and measurement
- [Szabo, How to Emulate the Super Saw, KTH 2010](https://web.archive.org/web/2018id_/https://www.nada.kth.se/utbildning/grukth/exjobb/rapportlistor/2010/rapporter10/szabo_adam_10131.pdf) (archived copy; the original host now shows a dismissal notice)
- Wikipedia: [Sawtooth wave](https://en.wikipedia.org/wiki/Sawtooth_wave), [Comb filter](https://en.wikipedia.org/wiki/Comb_filter), [Beat (acoustics)](https://en.wikipedia.org/wiki/Beat_%28acoustics%29), [Roughness](https://en.wikipedia.org/wiki/Roughness_%28psychophysics%29), [ERB](https://en.wikipedia.org/wiki/Equivalent_rectangular_bandwidth), [Power chord](https://en.wikipedia.org/wiki/Power_chord), [Roland Juno-60](https://en.wikipedia.org/wiki/Roland_Juno-60) (weak where noted)
- Weak evidence: [unison.audio on recreating sounds](https://unison.audio/how-to-recreate-your-favorite-sounds/) (generic method, some questionable numbers, not used for values)
- In this repo: `docs/TOOLS.md`, `.claude/skills/listening-loop/SKILL.md`, `ears/measure.py`, `docs/reference/live_api_12.4.6.md`, `docs/handoff/2026-10-08-nova-v2-paused.md`, and digests 02, 04, 06, 08, 09, 12 in this folder.

## Open questions / where sources disagree

- **Low-interval numbers.** I read the printed Hoffmann chart directly; Sweetwater's text puts the major third one semitone higher; digest 08's "classic chart" column (from secondary summaries, converted to Live names) now gives the same pitches as the table in 8.3. The chart is the permissive end: the rule used across this set (below about 130 Hz only roots, fifths and octaves; major thirds from about 165 Hz; minor thirds and seconds higher still) is stricter for thirds and seconds, and where they differ the rule wins.
- **Detune amounts.** Ableton says 1-10 % (cents) between oscillators, Attack's Sylenth pad 3-4 cents per voice, digest 09 a total spread of 3-8 cents, the supersaw regime +-9 to +-45 cents; Reese basses use +-15-30 cents on purpose. All are consistent with "small for pads, larger for deliberate roughness", but none gives a Live unison-amount to cents map: calibrate by measurement.
- **Chorus-Ensemble `Delay Time`.** The manual puts Delay Time and Taps in Chorus mode only, and digest 12 now says the same (the parameters stay in the list in every mode). Read `get_device` after switching modes.
- **High-pass for pads.** 430 Hz in iZotope's demo, 80-150 Hz as a general start, 200 Hz plus a 3-4 kHz roll-off for a drone pad (Copland), 130 Hz here: it depends on the role, so measure and ask.
- **Juno chorus rates.** Wikipedia gives about 0.4 and 0.6 Hz; I found no service-manual figure.
- **Impacts, downlifters and the EBM bass** have no source with parameter values; those recipes are mine and marked *(start)*.
- **Thresholds in the checklist** (valley depth, width, mono loss, evolution) come from synthetic tests and from the references' measurements, not from a standard. Treat them as comparisons against the base take.
- **Not verified in Live:** every recipe here was built from documentation and sources, not run in Live (the brief did not allow touching Live). Names were checked on 2026-10-08 against the reference dump `reference/live-12.4.6-device-parameters.json` and digest 12; values need the safe edit loop (`get_device`, set, read the echo, measure, ask).
