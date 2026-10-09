# Synthesis fundamentals and Live 12's instruments

For AI agents that compose in Ableton Live 12.4.6 Suite through AbletonMCP and cannot hear. Written 2026-10-08.
Companions: `03-sound-design-recipes.md` (recipes by role), `04-drums-and-low-end.md` (kick and bass design),
`11-listening-without-ears.md` (measurement and human judgement), `12-live-devices-reference.md` (effects and
utilities). This file explains what sounds are made of and how Live's instruments make them.

Evidence tags used below: **[manual]** Ableton Live 12 manual; **[API]** parameter and property names as the
tools report them (the reference dump `reference/live-12.4.6-device-parameters.json`, dumps of `get_device` captured
in earlier sessions on 12.4.6, and the Live Object Model docs in `docs/reference/lom_docs_12.4.5.md`); **[calc]** computed for this digest from stated formulas (reproducible);
**[practice]** practitioner convention with no single authoritative source (treat as a starting point and A/B it).

Contents: 1 fundamentals (waveforms, vocabulary, detune, sync/FM/noise); 2 shaping (filters, envelopes, LFOs, voices);
3 the instruments (Wavetable, Drift, Operator, Analog, Meld, Simpler/Sampler, drums, Creative Extensions and packs);
4 which instrument for which job, with starting settings; 5 pitch facts; 6 for an agent (inspection, one-change A/B,
measurement code, questions for Fred); Sources; Open questions.

## If you remember five things

1. **Read the patch, not its name.** A preset name says nothing about its oscillators. Before using any preset, read
   the whole chain (`get_devices`) and every instrument parameter (`get_device(..., detail=True)`): oscillator levels,
   octave and transpose settings, sub level and octave, noise level, filter type and cutoff, voice and unison modes.
   The pad that failed was "Dark Throne", a Max for Live Poli preset (Creative Extensions). The preset loads with Saw 0 %,
   Pulse 0 %, Sub 39.4 % at -2 octaves, Noise 18.9 %, LPF 372 Hz, Res 2 %, Chorus C; in the NOVA set the agent had
   lowered Sub to 15 %. Its only pitched voice is the sub. Those numbers predicted "hollow, airy, raspy" before anyone
   listened (section 6.1).
2. **Live names octaves with C3 = 60.** MIDI 57 = A2 = 220 Hz, MIDI 45 = A1 = 110 Hz, MIDI 33 = A0 = 55 Hz, and the
   references' 41-49 Hz root is E0-G0. Sub octaves, transposes, FM ratios, MIDI effects, Meld's scale mode and tuning
   systems can make the sounding pitch differ from the written note: verify on a dry held note with an FFT (section 5).
3. **Timbre words have spectral causes.** Saw = every harmonic at 1/n; square = odd harmonics only (the 50 % pulse is
   the only odd-only pulse); narrow pulse = thin and nasal; "hollow" = odd-harmonic or missing low-mid body; "airy" =
   energy between the harmonics (noise); "flangy" = comb filtering, loudest on noise. "Big, heavy, clean" (Fred's
   words, measured on the references) = a low root, a full saw-like series up to about 2 kHz, almost no noise, width
   made by detune or stereo voices above 200 Hz (section 1.2).
4. **Detune is arithmetic.** Beat rate = f x (2^(cents/1200) - 1), and the k-th harmonic beats k times faster. Roughly
   4-12 cents is chorus, 15-25 cents is wide and thick, beyond about 30 cents it sounds out of tune. Thirds in the sub region are rough whatever the
   tuning, because the ear cannot resolve partials closer than about one ERB (31-37 Hz at 55-110 Hz): keep low voicings
   to roots and fifths (sections 1.3 and 5.3).
5. **One change, original kept, measured, labelled, loudness-matched, then Fred decides.** Never choose a sound by its
   spectral distance to a full-mix reference. Design for the role first, then measure what you built (section 6).

---

## 1. Fundamentals an agent must reason with

### 1.1 Waveforms and their harmonic content

A periodic wave with fundamental f0 is a sum of harmonics at k x f0. The waveform decides which harmonics exist and
how strong they are; filters, modulation and effects then reshape that. The table is [calc] from the standard Fourier
series ([saw](https://en.wikipedia.org/wiki/Sawtooth_wave), [triangle](https://en.wikipedia.org/wiki/Triangle_wave),
[pulse](https://en.wikipedia.org/wiki/Pulse_wave); [SOS Synth Secrets part 1](https://www.soundonsound.com/techniques/whats-sound)
for the saw's 1/n law). Levels are dB relative to the fundamental of the same wave.

| Wave | Harmonics present | 2nd / 3rd / 4th / 5th | Power in the fundamental | Character |
| --- | --- | --- | --- | --- |
| Sine | 1 only | - | 100 % | pure, round; sub bass, FM carrier |
| Triangle | odd, amplitude 1/n^2 | - / -19 / - / -28 dB | 98.6 % | soft, flute-like, close to a sine |
| Square (50 % pulse) | odd, amplitude 1/n | - / -9.5 / - / -14 dB | 81 % | hollow, woody, clarinet-like |
| Pulse 25 % | all except 4, 8, 12... | -3 / -9.5 / absent / -14 dB | 54 % | reedy, a little nasal |
| Pulse 10 % | all except 10, 20... | -0.4 / -1.2 / -2.3 / -3.8 dB | 22 % | thin, pinched, nasal |
| Sawtooth | all, amplitude 1/n | -6 / -9.5 / -12 / -14 dB | 61 % (even harmonics hold 25 % of the power) | bright, buzzy, full; strings, brass, pads |

- A pulse of width d has harmonic n at amplitude proportional to |sin(n x pi x d)| / n, so harmonics vanish where n x d
  is a whole number: 25 % loses every 4th, 33 % every 3rd, 10 % every 10th. Only d = 50 % is odd-only. (Some tutorials
  say "pulse waves have only odd harmonics"; that is true of the square only.) The same arithmetic describes plucking a
  string at 1/3 or 1/4 of its length, which deletes every 3rd or 4th harmonic ([SOS, plucked strings](https://www.soundonsound.com/techniques/synthesizing-plucked-strings)).
  Sweeping the width with an LFO moves those holes and gives the PWM sweep.
- Narrowing the pulse moves power out of the fundamental into the upper harmonics, so the sound loses body and gets
  "thin, nasal" ([Wikipedia, pulse wave](https://en.wikipedia.org/wiki/Pulse_wave)); [Yamaha](https://yamahasynth.com/learn/synth-programming/synthesizer-basics-with-mx-part-ii/)
  calls a 10 % pulse pinched and nasal, and Live's Analog manual says low Width values sound tinny or pinched
  and that 100 % Width is a perfect square [manual 31.1.2]. Check the scale by measurement: the even harmonics should vanish at the square setting.
- Why square reads "hollow": the 2nd harmonic (the octave that reinforces a saw) is missing, and it sounds less bright and more open
  than a saw ([Splice](https://splice.com/blog/whats-in-a-wave/)). A clarinet is a closed
  pipe and also lacks even harmonics, which is why a square is the textbook clarinet starting point
  ([SOS, wind instruments](https://www.soundonsound.com/techniques/synthesizing-wind-instruments)). A narrow band-pass
  filter also reads hollow or nasal: it keeps a few partials around its centre and removes both the body below and the
  top above, like a fixed formant ([SOS, formant synthesis](https://www.soundonsound.com/techniques/formant-synthesis)).
- Live's oscillator sets: Analog shapes are sine, saw, rectangle (with pulse width) and white noise; Drift Osc 1 offers
  Sine, Triangle, Shark Tooth, Saturated, Saw, Pulse, Rectangle and Osc 2 offers Sine, Triangle, Saturated, Saw, Rectangle
  [manual 31.3]; Operator waves are Sine, Saw, Square, Triangle (the number in "Square 6" is the count of resynthesised
  harmonics; fewer is mellower and aliases less) plus 4-bit/8-bit and digital variants, noise, and a drawable User
  wave [manual 31.9]; Wavetable plays any table and its Classic effect applies pulse width to every table [manual 31.13];
  Poli mixes Saw, Pulse (with width), a Sub and Noise [API].

### 1.2 Vocabulary: what the words mean in the spectrum

There is no standard. The only descriptor with an accepted acoustic measure is brightness (the amount of
high-frequency content, measured as spectral centroid: [Wikipedia, timbre](https://en.wikipedia.org/wiki/Timbre),
[spectral centroid](https://en.wikipedia.org/wiki/Spectral_centroid)). The rest of this table is working vocabulary
[practice] built on the waveform facts above. When Fred uses a word, treat the row as a hypothesis and test it with
an A/B (section 6.4).

| Word | Usually means | What to measure | Typical fix |
| --- | --- | --- | --- |
| Bright / dark | more / less energy above about 2 kHz | spectral centroid, third-octave balance | filter cutoff, filter envelope amount, wavetable position, drive |
| Thin | weak fundamental and low-mid body: narrow pulse, high-pass, few harmonics | power below 300 Hz, fundamental share | widen the pulse, add a saw layer, add a sine or triangle at the root, lower the high-pass |
| Hollow | (a) odd-harmonic dominance (square, or FM with the modulator at twice the carrier); (b) missing low-mid body, the 150-600 Hz range scooped while a sub and highs remain; (c) static comb notches from phase-locked copies or a very short fixed delay | even-vs-odd harmonic ratio, 150-600 Hz energy against 600-5000 Hz | add a saw (even harmonics), raise the cutoff, add a real oscillator at the written pitch, free-run the oscillator phases |
| Nasal | a narrow resonance around 700-1500 Hz: narrow pulse, band-pass, high Q, formant filter | a narrow peak in that band | wider pulse, lower resonance, open the filter |
| Meaty / beefy | solid 150-600 Hz body made of real harmonics at the written pitch, not only a sub | 150-600 Hz energy, harmonics within 40 dB | saw or pulse layer through a 24 dB low-pass at 1-2 kHz |
| Warm | strong 100-500 Hz body, gentle roll-off above 2-4 kHz, mild even-harmonic colour | centroid under about 1.5 kHz, smooth slope | 12 dB low-pass, saw plus triangle, no resonance peak |
| Full / fat / thick | many harmonics plus several slightly different voices, sub support, width | harmonics within 40 dB, peak splitting around each harmonic, side/mid | unison or two detuned oscillators, sub for the root only |
| Airy | energy between the harmonics: noise, noise-like unison modes, breath | between-harmonics level (section 6.3), spectral flatness | noise to 0, avoid Wavetable's Noise and Shimmer unison, lower the high shelf |
| Raspy / gritty | noise plus distortion or aliasing at high frequencies | off-harmonic energy above 2 kHz | remove noise, lower Operator's Tone, lower FM index, lower drive |
| Muddy | build-up around 150-400 Hz from stacked layers or low thirds | 150-400 Hz level against neighbours | open voicings, high-pass the non-bass layers |
| Flangy | time-varying comb notches: a chorus or ensemble on a noise-rich or detuned source | notch pattern moving with the chorus rate | no chorus on noisy layers, slower rate, lower amount |
| Out of tune / "circus" | detune beyond about 30 cents, inharmonic FM or ring modulation, intermodulation from saturating chords, thirds in the sub region | peak positions in cents (section 5.4), roughness | smaller detune, integer FM ratios, saturate per voice or the root only, open voicings |

Fred's reference measurement of the background synth ("big, heavy, clean"): one low root at 41-49 Hz (E0-G0)
with a full saw-like series up to about 2 kHz, wide above 200 Hz, little noise, a smooth roll-off above 2 kHz. A root
at 41.2 Hz has 48 harmonics below 2 kHz [calc], so the target is "a saw through a 24 dB low-pass near 2 kHz, written
low, with width from detuned or stereo voices", not a sub plus noise. "Circus" was Fred's word for the first-round
synths; its cause is not established (bright narrow-pulse or PWM tones, fast vibrato or arps in a high register are
candidates), so ask rather than assume.

### 1.3 Detune, beating, unison and chorus

Two oscillators c cents apart beat at |f1 - f2| = f x (2^(c/1200) - 1), about 0.0578 % of f per cent ([beating](https://en.wikipedia.org/wiki/Beat_(acoustics))).
Beat rate of the **fundamental** in Hz [calc]:

| Detune | 55 Hz (A0) | 110 Hz (A1) | 220 Hz (A2) | 440 Hz (A3) |
| --- | --- | --- | --- | --- |
| 3 cents | 0.10 | 0.19 | 0.38 | 0.76 |
| 7 cents | 0.22 | 0.45 | 0.89 | 1.78 |
| 12 cents | 0.38 | 0.77 | 1.53 | 3.06 |
| 25 cents | 0.80 | 1.60 | 3.20 | 6.40 |
| 50 cents | 1.61 | 3.22 | 6.45 | 12.9 |

- **The k-th harmonic beats k times faster.** A 12-cent detune on A2 makes the fundamental swell at 1.5 Hz and the 8th
  harmonic at 12 Hz. Chorus-like shimmer lives in the upper partials; the low end stays stable. That is why detuned
  saws sound wide on top and solid underneath.
- **Zones** [practice]: up to 3 cents is analog drift (alive, steady); 4-12 cents is chorus and ensemble thickness; 15-25 cents is
  wide and thick (fine as a background unison, starts to read as two instruments on an exposed line); 30-50 cents sounds out of tune;
  near 100 cents it is a different note. The zones come from the arithmetic above and from three sources: SOS's string-synth patch
  detunes its two saws by about 4 cents ([SOS 47](https://www.soundonsound.com/techniques/synthesizing-strings-pwm-string-sounds)) and notes that two
  slightly mistuned saws sound thicker than either alone ([SOS, string machines](https://www.soundonsound.com/techniques/synthesizing-strings-string-machines));
  Ableton's pad tutorial says small detune amounts are enough and the first oscillator should stay at zero
  ([Ableton](https://www.ableton.com/en/blog/pad-it-out-10-ways-make-distinctive-pad-sounds/)); the supersaw measurements below.
- **What the beat rates sound like** [practice; the sequence slow tremolo, roughness, separate pitches is described in
  [Wikipedia, beat](https://en.wikipedia.org/wiki/Beat_(acoustics))]: under about 1 Hz a gentle swell that barely reads as beating; 1-6 Hz pulsing, chorus-like
  shimmer; 6-15 Hz flutter; 15-40 Hz roughness and growl; far above that the two components are heard as separate pitches (out of tune unless the interval was intended).
- **Real supersaw numbers.** Roland's JP-8000 supersaw is seven free-running saws with a pitch-tracked high-pass; at full
  detune the outer saws sit at about -202 and +177 cents, but the knob is strongly non-linear: half way is about +-18
  cents, a quarter about +-9 cents ([Szabo, KTH thesis](https://www.adamszabo.com/internet/adam_szabo_how_to_emulate_the_super_saw.pdf),
  figures converted to cents here). So the musically useful range (single digits to about 20 cents) occupies the lower half of that knob.
- **Free-running versus retriggered phase.** If every voice restarts in phase, the same comb relationship repeats each
  note and the timbre depends on the note; free-running phases (Drift's `Osc Retrig On` off) make each note slightly
  different. Wavetable's *Phase Sync* unison deliberately locks phases and produces a sweeping phaser effect [manual 31.13.8].
- **Unison in Live**: Wavetable Classic (equal detune spacing, alternate pan), Shimmer (random pitch jitter plus a
  little table offset, reverb-like), Noise (the same jitter, much faster: breathy noise), Phase Sync, Position Spread
  (spreads wavetable positions, little detune), Random Note (random positions and detune per note), each with a voice
  count and an Amount [manual]; Drift's Unison (4 independently detuned voices, `Strength`) and Stereo (2 voices
  panned L/R, `Spread`) modes [manual 31.3.7]; Analog's `Unison` (2 or 4 voices, `Detune`, `Delay`); Operator, Simpler
  and Sampler `Spread` (2 detuned voices panned L/R; Operator warns it is CPU-heavy); Meld's `Stacked Voices` (property
  `unison_voices`, off/2/3/4, duplicates both engines) with `Voice Spread`; Poli's `Voicemode` and `Unison Spread` [API].
  Wavetable's and Drift's amounts are not in cents: calibrate by measurement (section 6.3).
- **Chorus versus flanger.** Both mix the signal with a delayed, modulated copy. A delay of t ms puts the first notch at
  1/(2t) and repeats it every 1/t ([comb filter](https://en.wikipedia.org/wiki/Comb_filter)): 1 ms notches every
  1000 Hz, 5 ms every 200 Hz, 20 ms every 50 Hz [calc]. Short delays (flanger) give a few wide sweeping notches; chorus
  uses longer delays, so the notches are dense and mostly masked by a tonal source. **Noise has a flat, continuous
  spectrum, so the moving notches are plainly audible: a chorus on a noisy layer sounds flangy.** The fix is not a
  different chorus preset but removing the noise (or chorusing only the tonal layer).
- **Intermodulation.** A nonlinearity applied to a sum of notes creates sum and difference products (2f1 - f2 and so on)
  that are not harmonics of either note ([intermodulation](https://en.wikipedia.org/wiki/Intermodulation)). Saturating
  a whole chord therefore adds partials that sound like wrong notes. In a polyphonic synth the voice filters (and their `Drive`)
  normally act on each voice before the voices are summed (Sampler's manual calls its filter polyphonic); drive a single low root, or
  one voice at a time, instead of the summed chord.

### 1.4 Oscillator sync, ring modulation, FM and noise

- **Hard sync.** A "follower" oscillator is reset every time the "leader" completes a cycle. The pitch is the leader's;
  the follower's frequency sets the harmonic content, and sweeping it gives the classic tearing sweep
  ([oscillator sync](https://en.wikipedia.org/wiki/Oscillator_sync)). Live: Analog `O1 Sub/Sync` with `OSC1 Mode` set to
  Sync (the ratio is the slider; 0 % = no effect) [manual 31.1.2], Wavetable's Classic effect (*Sync*).
  Use: lead and bass "rip" by sweeping the ratio with an envelope. How the spectrum evolves under sync, PWM and detune is analysed in
  [Electric Druid](https://electricdruid.net/?p=1287).
- **Ring modulation.** Output holds the sum and difference frequencies only; with unrelated frequencies the result is
  inharmonic and clangorous; with a simple ratio the difference tone can stay musical ([SOS, amplitude modulation](https://www.soundonsound.com/techniques/amplitude-modulation)).
  Live: Poli `Ring`, `RM Source`, `Freq`; Drum Sampler's Ring Mod playback effect; Sampler's modulation oscillator in AM mode.
- **FM.** A modulator at fm around a carrier at fc makes sidebands at fc +- n x fm; the modulation index (set by the
  modulator's level) controls how many matter, and bandwidth is roughly 2 x fm x (1 + index) ([SOS, introduction to FM](https://www.soundonsound.com/techniques/introduction-frequency-modulation)).
  Integer ratios give harmonic spectra, non-integer ratios give bell and metal spectra ([FM synthesis](https://en.wikipedia.org/wiki/Frequency_modulation_synthesis)).
  Verified numerically here with the modulator at ratio r to the carrier [calc]: 1:1 gives every harmonic (saw-like);
  2:1 gives odd harmonics only (square-like, hollow); 3:1 skips every third harmonic; ratios such as 1.41 or 3.5 put
  most of the energy off the harmonic grid; a ratio such as 1.5 makes the true repetition rate half the carrier's
  frequency, so the **perceived pitch can drop an octave**. Rule: the sounding fundamental is the greatest common divisor
  of the carrier and modulator frequencies. Keep every Operator ratio an integer (`A Coarse` 1, 2, 3 with `A Fine`
  0) if the note must sound at its written pitch. Higher modulator level means brighter and noisier ([manual, Operator
  parameter list](https://www.ableton.com/en/live-manual/12/live-instrument-reference/)).
- **Noise.** White noise is flat; pink falls 3 dB per octave; both are the main source of "air". A noise layer is right
  for transients, breath and texture (around -30 to -20 dB below the tone, [practice]) and wrong in a pad that must be
  clean. Where it lives: Analog noise generator (white, with a 6 dB/oct low-pass `Noise Color`), Drift `Noise`, Wavetable's
  *Noise* and *Shimmer* unison modes (pitch-jitter noise), Operator's noise waves and LFO noise, Poli `Noise` with
  `Noise Color`, Meld's Noise Loop, Filtered Noise, Crackle, Rain and Bubble oscillators, DS HH (white or pink).
  Noise through a low-pass (as in a 372 Hz filter) becomes a low rumble that reads as raspy air in the 100-400 Hz region.

---

## 2. Shaping and moving the sound

### 2.1 Filters

- **Cutoff** is the point where the filter has already cut 3 dB, not where it starts to act ([SOS, further with filters](https://www.soundonsound.com/techniques/further-filters)).
  **Slope** is 6 dB per octave per pole: 12 dB = 2-pole, 24 dB = 4-pole. 24 dB is the safer choice for "clean" because
  it removes the harmonics above the cutoff more completely; 12 dB is softer and warmer.
- **Resonance** boosts a band around the cutoff and slightly attenuates the low end; at maximum a filter self-oscillates
  and can act as an extra oscillator ([SOS, responses and resonance](https://www.soundonsound.com/techniques/responses-resonance)).
  For clean pads keep it at 0-15 %; high values add the nasal, whistling peak.
- **Types** in Live: low-pass, high-pass, band-pass, notch and a Morph filter that sweeps LP-BP-HP-notch (Wavetable,
  Operator, Simpler, Sampler, Meld's SVF); circuits *Clean* (the EQ Eight filter), *OSR* (resonance limited by a hard-clipping
  diode), *MS2* (Sallen-Key, soft clipping), *SMP*, *PRD* (ladder, no resonance limiting); `Drive` exists on every
  circuit except Clean [manual]. Drift has a low-pass with Type I (12 dB, DFM-1 style) or Type II (24 dB, Cytomic MS2)
  plus a separate high-pass. Analog has 2nd- and 4th-order LP, BP, notch, HP and formant filters (with a formant type
  selected, the resonance knob, `F1 Resonance`, cycles through vowels). Meld has 17 filter types including combs, resonators, a vowel filter and a phaser.
  **Clean circuit with Drive off is the clean choice; MS2/OSR with Drive adds grit.**
- **Key tracking** makes the cutoff follow pitch; 100 % means it doubles every octave and the harmonic balance stays
  constant across the keyboard. In Operator and Wavetable the centre point is C3, so at C3 the cutoff is where you set it
  [manual]; Drift's `Key > LPF` runs 0 to 1.00. With no tracking, high notes get duller and low notes brighter.
  Operator's "Play by Key" context-menu command sets `Filt < Key` to 100 % and the cutoff to 466 Hz.
- **Envelope amount** sweeps the cutoff over time. In Operator, 100 % can sweep about 9 octaves [manual]; musical
  values are small for pads (5-20 %) and larger for plucks (30-70 %) [practice].
- **Low-pass and high-pass as a design tool.** Low-pass near 1.2-2 kHz makes a heavy, dark, clean pad; a high-pass at
  25-40 Hz removes inaudible rumble; layered synths work best when each layer owns a range (an Attack Magazine layering
  example uses a sine sub at 40-60 Hz rolled off above 190 Hz, a warm layer at 130 Hz-3 kHz, and a third layer high-passed
  at 250 Hz: [Attack, layering synths](https://www.attackmagazine.com/technique/synth-secrets/layering-synths/)).

### 2.2 Envelopes

ADSR: attack (time to peak), decay (time to the sustain level), sustain (a level, not a time), release (time to silence
after the note ends). Your brain identifies an instrument from the first few milliseconds, and an attack of exactly zero
creates a percussive spike ([SOS, envelopes](https://www.soundonsound.com/techniques/envelopes-gates-triggers)). Starting
values by role [practice; the rationale is in the last column]:

| Role | Attack | Decay | Sustain | Release | Why |
| --- | --- | --- | --- | --- | --- |
| Background pad | 150-800 ms (ambient: 1-5 s) | 2-6 s | 70-100 % | 1.5-4 s | no audible onset; tails overlap chords; Ableton's pad tutorial recommends medium-to-long attack and release |
| Drone | 2-10 s, or 0 with slow modulation | long | 100 % | 3-8 s | continuous; movement comes from LFOs |
| Pluck / arp | 0-2 ms | 150-500 ms | 0-10 % | 50-200 ms | brightness and loudness both decay; filter envelope decays faster than the amp |
| Sustained bass | 1-5 ms (3 ms or more at sub frequencies) | 100-400 ms | 70-100 % | 30-120 ms | zero attack clicks on low notes |
| Lead | 0-10 ms | 100-300 ms | 60-90 % | 80-300 ms | articulate but not clicky |
| Stab | 0-5 ms | 100-300 ms | 0-30 % | 100-300 ms | short, percussive chord |
| Synth kick | 0-1 ms (amp), pitch envelope 20-120 ms | 200-500 ms | 0 | - | see `04-drums-and-low-end.md` |

Live specifics: Operator envelopes have three times and three levels (Initial, Peak, Sustain) and modes Loop, Beat, Sync and
Trigger (Trigger ignores note-off: ideal for percussion); the Time knob scales all envelope rates. Wavetable has Amp, Env 2
and Env 3 with Time and Slope per segment and loop modes None, Trigger, Loop. Drift has Env 1 (amplitude) and Env 2, which can be
switched to a Cycling Envelope (`Cyc Env Tilt`, `Cyc Env Hold`, and `Cyc Env Time Mode` Freq/Time/Ratio/Sync) that acts like a note-retriggered LFO. Analog's
`AEG1 Free` / `FEG1 Free` switch makes an envelope ignore the held key (trigger behaviour) and its `Loop` items are Off, AD-R, ADR-R and ADS-AR.
Velocity can shorten the attack or scale the envelope (`AEG1 A < Vel`, `FEG1 < Vel`, Operator `Ae R < Vel`).

### 2.3 LFOs, velocity and modulation routing

| Purpose | Rate | Depth | Retrigger |
| --- | --- | --- | --- |
| Pad movement, slow filter swell | 0.05-0.3 Hz (about 0.1 Hz is a slow sweep per [SOS](https://www.soundonsound.com/techniques/modulation)) | filter 5-15 % | free-run, so voices differ |
| Wah-like | 1-2 Hz | filter | either |
| Vibrato | 5-7 Hz (singers 5-8 Hz: [Wikipedia, vibrato](https://en.wikipedia.org/wiki/Vibrato)) | pitch under 50 cents for wind and bowed instruments, under 10 cents for choirs; Ableton's pad tip: LFO amount about 10 %, sine or triangle | on, with an LFO delay or fade-in of 200-600 ms [practice] |
| PWM / wavetable position | 0.3-2 Hz | 10-40 % | free-run for pads, retrigger for bass |
| Tempo-synced wobble or pump | 1/8-1/4 | filter | on |
| "Growl" | 10-20 Hz (SOS) | filter | on |
| Audio-rate FM or AM | above 20 Hz | pitch or amplitude | n/a |

**Velocity.** Written velocities move level and, where routed, brightness and attack: map velocity to level and a little cutoff on playable parts; on pads and drones
set the sensitivity to zero (Drift `Vel > Vol` 0 %; Analog `AEG1 < Vel` and `FEG1 < Vel`; Operator `Osc-X Lev < Vel`, `Filt < Vel`) so a clip's velocity values do not change loudness or tone unexpectedly [practice].

Audio-rate modulation changes the sound from movement into new partials (sidebands): Drift's LFO in Ratio time mode used on
pitch makes FM tones, Operator's LFO reaches 12 kHz [manual], Sampler's modulation oscillator does FM or AM.
**Retrigger** restarts the LFO at the same phase on every note, which is predictable (good for bass and plucks); free-running
gives each voice a different phase (organic, good for pads). A retriggered LFO on a polyphonic chord moves all voices in lock-step.

Routing in Live: Drift has a three-slot mod matrix (sources Env 1, Env 2/Cyc, LFO, Key, Velocity, Modwheel, Pressure, Slide;
destinations Osc 1 Gain, Osc 1 Shape, Osc 2 Gain, Osc 2 Detune, Noise Gain, LP Frequency, LP Resonance, HP Frequency, LFO Rate,
Cyc Env Rate, Main Volume) plus dedicated slots for pitch, shape, LP cutoff and LFO amount; the source choosers are device
*properties* (`mod_matrix_source_1`, `mod_matrix_filter_source_1`, ...), the amounts are parameters (`Mod Matrix Amt 1`,
`LP Mod Amt 1`) [manual, API]. Wavetable's matrix has sources along the top and targets down the side; some targets are additive
(centred on 0, can go negative), others multiplicative (neutral 1, minimum 0, the sources multiply), and a global Amount
and Time (negative = faster) scale everything [manual]; read and write cells with `device_action(..., "get_modulation" |
"set_modulation" | "add_parameter_to_modulation_matrix")`. Operator's MIDI map sends Velocity, Key, Aftertouch, Pitch Bend and
Mod Wheel to two destinations each; Meld has a matrix per engine.

### 2.4 Glide, voices, stealing, mono, poly and unison

- **Glide** slides pitch between notes. It only works when notes overlap in mono or legato use, and it can be constant time
  or proportional to the interval. Live names: Drift `Glide Time` (Mono mode with `Legato On` for overlapping notes);
  Wavetable `Glide` (Mono only); Analog `Glide On/Off`, `Glide Time`, `Glide Mode` Const or Prop, `Glide Legato`; Operator
  polyphonic glide (`Glide On`, `Glide Time`); Simpler and Sampler *Glide* (monophonic) versus *Portamento* (polyphonic);
  Meld `A Glide Mode` / `A Glide Time` (and `B`): Portamento (continuous) or Glissando (steps in scale degrees), active in Mono and Poly; Poli `Glide`. A Minimoog-style
  solo used about 80 ms ([Attack, legato synths](https://www.attackmagazine.com/technique/passing-notes/legato-synths-glide-slide-portamento/)).
- **Voices and stealing.** A voice is one note with its own envelope and filter. When more notes sound than the voice count,
  the oldest are cut (Operator, Simpler [manual]) or `Key Priority` decides (Analog and Tension: High, Low or Last).
  A polyphonic synth needs a separate envelope and filter per voice, which is also why unison multiplies voices
  ([SOS, polyphony](https://www.soundonsound.com/techniques/introducing-polyphony)).

| Instrument | Voice facts [manual unless noted] |
| --- | --- |
| Drift | up to 32 voices; Poly = 1 voice per note; Stereo = 2 per note (16 notes at 32 voices); Unison = 4 per note (8 notes); Mono = one note rendered with 4 voices via `Thickness` (0 = one voice) |
| Wavetable | Mono (legato envelopes) or Poly with a voice count (properties `mono_poly`, `poly_voices`; 16 voices since 12.4); unison multiplies oscillators per voice |
| Operator | up to 32 voices (since 12.2), oldest cut off; `Voices` = 1 gives legato mono; 6-12 is realistic for CPU. The voice count is a UI control: it is not in the parameter list or the Live API |
| Analog | `Voices` chooser (Mono, 2, 4, 8 ... 32), `Key Priority`; Unison 2 or 4 |
| Meld | Mono (+Legato) or Poly 2-12 voices (properties `mono_poly`, `poly_voices`); Stacked Voices (property `unison_voices`) duplicate both engines (heavy CPU) |
| Simpler / Sampler | `Voices` (Simpler: property `voices`; Sampler up to 32, a UI control); `Retrig` (Simpler property `retrigger`) cuts a sounding repeat of the same note; Simpler One-Shot is strictly mono |
| Poli | `Voicemode` (Poly, Mono, Unison), `Unison Spread` [API] |

---

## 3. Live 12's instruments in depth

Parameter names below are what `get_device` reports ([API]; the full lists, with raw ranges and items, are in
`reference/live-12.4.6-device-parameters.md`); units in brackets are the display units. Strings you pass to
`set_device_parameters` are display values ("-6 dB", "7 ct", "Saw"), numbers are raw. Settings that the Live Object Model
exposes as *properties* rather than parameters go through `set_device(properties={...})` (option properties accept a name
or an index; `"voice_mode"` works for `voice_mode_index`). The manual chapter is
[31. Live Instrument Reference](https://www.ableton.com/en/live-manual/12/live-instrument-reference/); section numbers are cited in brackets.

### 3.1 Wavetable (class `InstrumentVector`) [31.13]

- **Architecture.** Two wavetable oscillators, a Sub, two filters, three envelopes (Amp, Env 2, Env 3), two LFOs, a
  modulation matrix and a MIDI tab. Oscillator output is perfectly band-limited (no aliasing) until it is modulated.
  Moving *Position* scans the table without changing pitch, so it behaves like playing a sample at a chosen place; the table
  choosers are a category and a table within it; any WAV or AIFF can be dropped on the display as a table (Raw mode skips
  Live's clean-up) ([manual](https://www.ableton.com/en/live-manual/12/live-instrument-reference/),
  [Ableton, Wavetable design notes](https://www.ableton.com/en/blog/new-wave-depth-look-wavetable/)).
- **Oscillator effects** (per oscillator, two sliders, the parameters `Osc N Effect 1` and `Osc N Effect 2`, whose values persist when the type changes): *FM* (`Amt`, `Tune`; tune
  50 % = modulator one octave up or down, 100 % = two octaves, values between are inharmonic and noisy), *Classic* (*PW*, pulse width
  for any table; *Sync*), *Modern* (*Warp* like pulse width, *Fold* wavefolding).
- **Sub.** `Sub On`, `Sub Gain`, `Sub Tone` (0 % = sine, more = more harmonics), `Sub Transpose` (0, -1 or -2 octaves).
- **Filters.** Lowpass, Highpass, Bandpass, Notch, Morph; 12 or 24 dB (`Flt n Slope` items `12`, `24`); circuits Clean/OSR/MS2/SMP/PRD in `Flt n LP/HP`
  (Bandpass, Notch and Morph have only Clean and OSR, in `Flt n BP/NO/MO`); `Drive` on
  non-Clean circuits. Routing (property `filter_routing`): Serial (all into Filter 1 then Filter 2), Parallel, or Split
  (Osc 1 to Filter 1, Osc 2 to Filter 2, Sub split) for layered sounds.
- **Names.** `Osc 1 On / Transp [st] / Detune [ct] / Pos [%] / Effect 1 / Effect 2 / Pan / Gain [dB]` (same for Osc 2);
  `Sub On / Tone / Gain / Transpose`; `Flt 1 On / Type / LP/HP / BP/NO/MO / Slope / Freq / Res / Drive / Morph` (and `Flt 2`);
  `Amp Attack / Decay / Sustain / Release / A Slope / D Slope / R Slope / Loop Mode` (`Env 2` and `Env 3` add `Initial`,
  `Peak`, `Final`); `LFO 1 Retrigger / Shape / Amount / Shaping / Phase Offset / Sync / Rate / S. Rate / Attack Time` (and `LFO 2`);
  `Time`, `Global Mod Amount`, `Unison Amount`, `Transpose`, `Glide`, `Volume`.
  **Properties (not parameters):** `unison_mode` (UI names None, Classic, Shimmer, Noise, Phase Sync, Position Spread, Random Note; the
  strings the tool takes are the API enum names, where Shimmer is `slow_shimmer` and Noise is `fast_shimmer`, and a plain "Shimmer" is ambiguous),
  `unison_voice_count`, `mono_poly`, `poly_voices`, `filter_routing`, `oscillator_1_effect_mode` (UI names None, FM, Classic, Modern; API
  strings `none`, `frequency_modulation`, `sync_and_pulse_width`, `warp_and_fold`),
  `oscillator_N_wavetable_category`, `oscillator_N_wavetable_index` with the lists `oscillator_wavetable_categories` and
  `oscillator_N_wavetables`. Read the lists instead of guessing table names.
- **Strengths.** Evolving pads, leads and basses from position scans and a deep matrix; precise filters; wide
  palette. Ableton's own pad advice, demonstrated in Wavetable: saw blended with saw or square for strings, small detune with oscillator 1
  left at zero, a sine or triangle LFO at about 10 % for vibrato, medium-to-long amp attack and release, unison with a
  correlation meter on the output, and Noise unison near 40 % only when grit is wanted
  ([Ableton, pad it out](https://www.ableton.com/en/blog/pad-it-out-10-ways-make-distinctive-pad-sounds/)).
- **Traps.** *Shimmer* and *Noise* unison add random pitch jitter and breath (airy, "flangy" under a chorus); *Phase Sync*
  is a phaser sweep; `Unison Amount` is not in cents; unison multiplies oscillators (CPU and polyphony); `Glide` only acts
  in Mono; `Osc N Transp` and `Sub Transpose` move the sounding pitch; Hi-Quality mode (context menu) is off by default
  since Live 11.1 and changes modulation resolution slightly.

### 3.2 Drift (class `Drift`) [31.3]

- **Architecture.** A fast subtractive synth: two oscillators with analog-style per-voice instability, a noise generator, a
  low-pass (Type I 12 dB or Type II 24 dB) plus a high-pass, Env 1 (amplitude), Env 2 (ADSR or Cycling Envelope), an LFO
  with nine waveforms (Sine, Triangle, Saw Up, Saw Down, Square, Sample & Hold, Wander and two one-shot decays), and the
  mod matrix of section 2.3. Ableton's design idea: two oscillators drifting in and out of sync make the instrument feel
  like "a living, breathing machine" ([Ableton](https://www.ableton.com/en/blog/drift-exploring-the-new-synth-in-live-113/)).
- **Voice modes** (property `voice_mode`): Poly, Mono, Stereo (`Spread`), Unison (`Strength`) with `Thickness` for Mono; the
  `Drift` knob randomises each voice's pitch and filter cutoff (large amounts sound out of tune) [manual].
- **Names.** `Osc 1 On / Wave / Shape / Oct / Gain / Shape Mod Amt`; `Osc 2 On / Wave / Oct / Detune / Gain`; `Noise On / Gain / Flt On`;
  `Osc 1 Flt On`, `Osc 2 Flt On`; `LP Freq / Res / Type [I, II] / LP Mod Amt 1 / LP Mod Amt 2`, `HP Freq`, `Key > LPF` (0-1);
  `Env 1 Attack / Decay / Sustain / Release`, same for `Env 2`, `Env 2 Cyc On` (Env or Cyc), `Cyc Env Rate / Ratio / Time /
  Synced / Tilt / Hold / Time Mode`; `LFO Wave / Time Mode / Rate / Ratio / Time / Synced / Amt / Mod Amt / Retrig On`;
  `Pitch Mod Amt 1/2`, `Mod Matrix Amt 1/2/3`; `Spread`, `Strength`, `Thickness`, `Drift`; `Legato On`, `Glide Time`,
  `Vel > Vol`, `Osc Retrig On`, `Transpose` (+-48 st), `Volume`.
- **Details that matter.** Oscillator gains above the default -6 dB start to saturate the filter input (a second
  saturation point above 0 dB), which is an easy way to add grit and an easy way to lose clean. `Osc 2 Detune` is documented
  in semitones (an Attack Magazine lead uses -0.11, about -11 cents:
  [Attack, detuned Drift leads](https://www.attackmagazine.com/technique/synth-secrets/detuned-festival-leads-with-ableton-drift/));
  the display has no unit, so confirm by measurement. At 32 voices (property `voice_count`), Unison gives 8-note polyphony, so a 5-note chord is
  safe but a layered arp may steal voices.
- **Strengths.** Clean saw/pulse pads, mono basses (the *Saturated* wave is Ableton's suggestion for bass), leads with
  glide, plucks with Env 2 on the filter. Public recipes use Unison with a high `Drift`, Type II filter at 144 Hz with Env 1
  at 85 % for stabs ([Attack, Drift chord stabs](https://www.attackmagazine.com/technique/synth-secrets/pitch-bending-chord-stabs-with-ableton-drift/)),
  and an LFO at about 40 % on `LP Freq` for modulated basses ([Attack, Drift bass](https://www.attackmagazine.com/technique/synth-secrets/use-drift-to-modulate-bass-like-overmono-modeselektor/)).

### 3.3 Operator (class `Operator`) [31.9]

- **Architecture.** Four oscillators (A-D), eleven algorithms (`Algorithm` = Alg. 1...11, signal flows top to bottom), a
  filter (LP/HP/BP/Notch/Morph, 12/24 dB, Clean/OSR/MS2/SMP/PRD, Drive, waveshaper), an audio-rate LFO (it works as a
  fifth oscillator), a pitch envelope, per-oscillator envelopes, `Spread` (two detuned voices), glide, and global `Tone` (high-frequency
  content; 100 % is brightest and most likely to alias) and `Time` (scales every envelope rate). The manual suggests exploring FM without the filter first. The algorithm icons show which operators are carriers (heard) and which only modulate;
  Alg. 1 is, as far as we know, the fully serial stack (most FM) and the last algorithm four parallel carriers (additive, organ-like) [practice, not verified here]: after
  choosing one, confirm by silencing an operator (`Osc-X Level` -inf) and measuring.
- **Names.** `Osc-A On`, `A Coarse` (whole-number ratios), `A Fine`, `A Fix On ` (the real name ends in a space; matching ignores it), `A Fix Freq`, `A Fix Freq Mul`, `Osc-A
  Level`, `Osc-A Wave` (23 waves), `Osc-A Feedb`, `Osc-A Phase`, `Osc-A Retrig`, `Osc-A < Pe`, `Osc-A < LFO`, `Osc-A Lev < Vel`;
  envelope `Ae Attack / Init / Decay / Peak / Sustain / Release / Mode / Loop` (B-D likewise as `Be`, `Ce`, `De`); pitch envelope `Pe On /
  Init / Peak / Decay / End / Amount / Amt A` (levels in semitones, +-48); `LFO On / Type / Range / Rate / Amt / Amt A / Dst B`;
  `Filter On / Type / Circuit - LP/HP / Slope / Freq / Res / Drive`, `Filt < Key`, `Fe Amount`; `Shaper Type / Mix / Drive`;
  `Spread`, `Tone`, `Time`, `Transpose`, `Glide On`, `Glide Time`, `Volume`.
- **How it makes sound.** The level of a modulating oscillator is the FM depth, its Coarse/Fine ratio sets the spectrum
  (section 1.4), and an oscillator that is not modulated can modulate itself through `Feedb` (saw-like, brighter with more feedback).
  Fixed mode (`A Fix On`) makes an oscillator ignore the note and play `Fix Freq` x `Mul` Hz (down to 0.1 Hz), which is useful for drums
  whose pitch must not follow the key. Envelopes can loop (Loop, Beat, Sync), and Trigger ignores note-off for percussion.
  A sustained note with `Voices` = 1 plays legato (envelopes are not retriggered); `Voices` is a UI control, not a parameter.
- **A working kick found in an earlier set** [API]: Osc A sine (Coarse 1), pitch envelope Init and Peak +16 st falling to End 0 in
  80 ms, amp decay 900 ms, sustain -inf, filter off. The shape to remember: a sine that starts a few semitones to a few
  octaves above its target and falls in tens of milliseconds, with the target at the kick's tuned note; see
  `04-drums-and-low-end.md` for tuning kick and bass together.
- **Strengths.** Digital and FM basses, kicks and percussion, bells and metal, evolving drones with looping envelopes.
  Public example: one oscillator modulated at a 17:1 ratio, then dropped 38 semitones with a Pitch MIDI effect, for an aggressive
  Noisia-style synth ([Attack, Operator synths](https://www.attackmagazine.com/technique/synth-secrets/learn-how-to-make-noisia-inspired-synths-with-abletons-operator/)).
- **Traps.** Non-integer ratios, fixed mode and pitch envelopes change the perceived pitch; `Spread` is CPU-heavy; aliasing at
  high notes (lower `Tone`); a modulator at a high level turns bright and noisy.

### 3.4 Analog (class `UltraAnalog`) [31.1]

- **Architecture.** Physical-model virtual analog (no sampling, no aliasing) made with Applied Acoustics Systems: two
  oscillators (sine, saw, rectangle with pulse width, white noise) each with a Sub (a square one octave down for saw or rectangle, a sine for sine) or Sync mode, a noise
  generator, two multimode filters (2nd and 4th order LP, BP, notch, HP, formant; routable serial or parallel; Filter 2 can follow
  Filter 1's cutoff), two amplifiers, four ADSR envelopes with loop modes, two LFOs, vibrato, `Unison` (2 or 4 voices), glide,
  `Key Priority`, `Key Stretch` and `Key Error` (tuning deviations).
- **Names.** `OSC1 On/Off / Shape / Octave / Semi / Detune / PW / Mode / Level / Balance`, `O1 Sub/Sync`, `O1 Keytrack`, `PEG1 Amount / Time`;
  `Noise On/Off / Color / Level / Balance`; `F1 On/Off / Type / Drive / Freq / Resonance / Freq < Key / Freq < Env / To F2`, `F2 Slave`;
  `FEG1 Attack / Decay / Sustain / Rel / S Time`, `AEG1 ...`; `LFO1 Shape / Speed / SncRate / Sync / Retrig / Delay / Fade In`; `Unison On/Off / Voices /
  Detune / Delay`; `Voices`, `Key Priority`, `Key Stretch`, `Key Error`, `Glide On/Off / Time / Mode / Legato`, `Vib ...`, `Octave`, `Semitone`, `Detune`, `Volume`.
- **Strengths.** Warm per-voice filtered pads, sync leads, formant (vowel) filter textures, detuned dual-saw leads; Ableton's
  Analog tutorials build a lead from two detuned saws and a pad from two detuned saws an octave down plus noise
  ([Attack, Analog leads and pads](https://www.attackmagazine.com/technique/synth-secrets/trippy-leads-analogue-pads-ableton-analog-sonnox-voxdoubler/)).
- **Traps.** `Key Stretch` and `Key Error` deliberately detune; `Unison Delay` shifts the stacked voices in time; the Quick Routing
  buttons change which oscillator feeds which filter without touching levels; Sub mode adds a square one octave down.

### 3.5 Meld [31.8]

- **Architecture.** Two independent "macro oscillator" engines (A and B), each with its own filter, amplitude and modulation
  envelopes, two LFOs and a modulation matrix. 25 oscillator types in 12.4.6 (seven scale-aware, marked ♭♯ in the type list; the manual
  still counts 24 and six, before the 12.2 Chord oscillator), each with two macro knobs (`A Osc Shape`, `A Osc Tone`) whose
  meaning changes with the type (for example *Basic Shapes*: Shape and Tone; *Swarm Saw*: Motion and Spacing; *Harmonic FM*:
  Amount and Ratio; *Chord*: four detuned saws, Shape and Inversion; *Sub*; *Noise Loop*; *Rain*; *Bubble*; *Crackle*;
  *Shepard's Pi*). 17 filter types, including SVF 12/24, MS2, OSR, comb, vowel, plate and membrane resonators, phaser and
  redux. Mix section: per-engine Volume, Pan and a bipolar Tone filter (`A Volume`, `A Pan`, `A Tone Filter`), a per-voice limiter (`Limiter On`), global `Drive`.
- **Pitch-relevant settings.** `A Keytracking` / `B Keytracking` off makes that engine's oscillator play a constant C3 (or the scale's root) for every
  note, good for drones and percussion and a trap for tonal parts; **Use Current Scale** and the `Scale Aware` switches (global `Scale Aware`, per engine
  `A Osc Scale Aware`, `A Transp Scale`) make
  transpositions move in scale degrees (a note you wrote can sound as another scale degree); Portamento slides, Glissando steps (`A Glide Mode`).
  Properties: `selected_engine`, `unison_voices` (off, 2, 3, 4), `mono_poly`, `poly_voices` (2-12) [API]. The 129 parameter names are in the reference
  dump (per engine with an `A ` or `B ` prefix; the shared section has `Drive`, `Limiter On`, `Voice Spread`, `Volume`); the digest 12 card for Meld lists them.
- **Strengths.** Evolving textures, drones, unusual sources, cross-engine modulation. A review praises its richness and the
  versatility of the macros ([SOS, Live 12 review](https://www.soundonsound.com/reviews/ableton-live-12)); Ableton frames it as
  a tool for exploration guided by musical intention ([Ableton](https://www.ableton.com/en/blog/meld-a-look-at-live-12s-new-bi-timbral-synth/)).
- **Traps.** Stacked voices duplicate both engines (heavy CPU); macros are type-specific; it is the easiest Live instrument in
  which the sounding pitch differs from the written note.

### 3.6 Simpler and Sampler [31.11, 31.10]

- **Simpler** plays a region of one sample at its original pitch when the note is C3, with `Transpose` +-48 st, `Detune` +-50
  ct, pitch bend +-5 st, `Spread`, glide (Glide = mono, Portamento = poly), a filter, three ADSR envelopes (amp, filter, pitch), an
  LFO and optional warping, so warped samples follow the set tempo whatever the note. Modes (property `playback_mode`):
  **Classic** (polyphonic, ADSR, loop; for pitched instruments), **One-Shot** (strictly mono; `Trigger` plays on after
  note-off, `Gate` fades out on release; for drum hits), **Slicing** (slice by Transient, Beat, Region or Manual, up to 64
  slices, played chromatically; `Slice to Drum Rack` splits them out). Voice stealing drops the oldest voices; `Retrig`
  (property `retrigger`) cuts a repeated note. Names: `S Start`, `S Length`, `S Loop On / Length / Fade`, `Snap`, `Spread`, `Glide Mode / Time`,
  `Transpose`, `Detune`, `Ve Attack / Decay / Sustain / Release / Mode`, `Fade In`, `Fade Out`, `Trigger Mode`, `F On`, `L On`,
  `Volume`, `Vol < Vel`, `Pan`. Sample details go through `set_device(properties={"sample.warping": true, "sample.warp_mode":
  "complex"})` and `device_action(crop | reverse | warp_as | to_drum_rack | insert_slice ...)`.
- **Sampler** (class `MultiSampler`) is the multisampling version: key, velocity and sample-select zones, round robin,
  sustain and release loops with crossfade, a modulation oscillator (21 waves, FM or AM, its output is never heard directly), a
  pitch envelope, a polyphonic filter with a waveshaper (Soft, Hard, Sine, 4bit), an auxiliary envelope, three LFOs, 32 voices.
  Its zone editor spans C-2 to G8 (MIDI 0-127), which is the clearest statement of Live's octave naming in the manual.
  `Key Zone Shift` transposes which sample plays without changing the played pitch.
- **Installed content built on them.** Orchestral Strings (violin, viola, cello, double bass, solo and ensemble, with articulation
  racks; multisampled and played through Simpler), Mood Reel (about 295 instrument racks of sampled acoustic gear, electronic sounds
  and textures, 20 drum racks), Glitch and Wash and Build and Drop (instrument and drum racks with eight macros each)
  ([Orchestral Strings](https://www.ableton.com/en/packs/orchestral-strings/), [Mood Reel](https://www.ableton.com/en/packs/mood-reel/),
  [Glitch and Wash](https://www.ableton.com/en/packs/glitch-and-wash/), [Build and Drop](https://www.ableton.com/en/packs/build-and-drop/)).
  Sampled instruments have a root note and may not sit at A = 440 Hz: check by measurement before building chords on them.

### 3.7 Drum Rack, Drum Sampler and the DS drum synths

- **Drum Rack** [manual 25.6]: 128 pads, one per MIDI note. Each chain has `Receive` (the incoming note, `in_note`), `Play` (the note sent to
  the chain's devices, `out_note`: a pitch shift for a pitched instrument) and `Choke` (one of 16 groups, so a closed hat can cut an open
  one), a mixer and send levels to up to six return chains. Dropping a sample on an empty pad creates a chain with Simpler (or Drum
  Sampler if saved as the default pad). Drum Racks bypass tuning systems [manual]. Tools: `get_devices` lists the non-empty pads,
  `set_chain(in_note, out_note, choke_group)` edits them, `write_drum_pattern` writes the clip.
- **Drum Sampler** [31.4] (new in Live 12.1; [manual] names, not in the reference dump: read the real ones with `get_device`): one-shot player for Drum Racks. Start, Length, `Sample Gain` (-70 to +24 dB), an AHD envelope (Trigger or Gate mode), `Transpose` +-48
  and `Detune` +-50 ct, a filter (12 or 24 dB low-pass, 24 dB high-pass, peak) and nine playback effects: Stretch, Loop, Pitch Env, Punch, 8-Bit, FM,
  Ring Mod, Sub Osc (30-120 Hz) and Noise. Velocity or MPE slide can modulate the filter, the envelope stages and the effect parameters.
- **DS synths** (Max for Live, [Max for Live Devices 33.1](https://www.ableton.com/en/live-manual/12/max-for-live-devices/); [manual] labels, not in the reference dump): *DS Kick* is a modulated sine
  with `Pitch` (Hz), `Drive`, `OT` (harmonics), `Attack`, a `Click` switch, `Decay`, `Env` (pitch modulation) and `Volume`. *DS Snare*:
  `Color` (pitched part), `Tone` (noise), LP/HP/BP noise filter, `Decay`, `Tune`. *DS HH*: white or pink noise plus a sine, `Tone`, a resonant 12 or 24 dB
  high-pass, `Attack`, `Pitch`, `Decay`. *DS Clap*: `Sloppy`, `Tail`, `Spread`, `Tone`, `Tune`, `Decay`. *DS Tom*: `Pitch` (Hz), `Color`, `Tone`, `Bend`, `Decay`. *DS Cymbal*, *DS FM* (`Feedb.`, `Amnt`, `Mod`)
  and *DS Clang* (two cowbell tones plus a clave mode) complete the set. They load through the browser, and their kick pitch is a frequency in Hz you
  can set directly to the tuned note.
- **Impulse** is the older eight-slot sampler (C3 triggers the leftmost slot); prefer Drum Rack.

### 3.8 Creative Extensions, Granulator III and other installed sources

- **Poli** and **Bass** (Creative Extensions, Max for Live): Poli is a virtual analog synth for polyphonic chords with detunable
  oscillators, a modulation section and built-in chorus; Bass is a monophonic virtual analog bass synth for deep to distorted
  tones ([Ableton](https://www.ableton.com/en/packs/creative-extensions/)). Poli has no manual chapter; the names the tool reports
  are `Saw`, `Saw  Tune` (two spaces), `Saw Fine Tune`, `Xmod`, `Pulse`, `Pulse Tune`, `Pulse Fine Tune`, `Pulse Width`, `Sub`, `Sub Octave` (items -2, -1, 0),
  `Sub Wave` (Saw, Sine), `Noise`, `Noise Color`, `Ring`, `Freq`, `RM Source`, `LFO Shape`, `Rate`, `Fade-In`, `Sub -> Filter`, `HPF`, `LPF`, `Res`, `Attack`,
  `Decay`, `Sustain`, `Release`, `Filter Env`, `Amp Env`, `Key`, `Velocity`, `Aftertouch`, `Chorus`, `Random Pan`, `Glide`, `Glide Time`, `Voicemode`,
  `Unison Spread`, `Volume`, `PB Range` [API]. Items: `RM Source` Saw or Sine, `Sub -> Filter` Bypass or Thru, `Chorus` -, A, B or C, `Voicemode` Poly, Mono or
  Unison. Several names repeat (`Rate`, `Attack`, `Decay`, `Sustain`, `Release`, `Filter Env`, `Amp Env`, `Key`, `Velocity`, `Aftertouch`, `LFO`), and a repeated name is an error, so address
  those, and `Saw  Tune`, by the index from `get_device`. Each source has its own level, so a preset can set `Saw` and `Pulse` to 0 % and
  leave only `Sub` and `Noise` (the failure case; a freshly added Poli has `Saw` 100 % and `Pulse`, `Sub` and `Noise` at 0 %). With `Sub -> Filter` on Bypass (the default) the sub is not filtered by `LPF`: toggle it and measure rather than assuming.
  Live's tuning-system rule for Max for Live instruments and plug-ins is a pitch-bend range of 48 semitones; Poli's `PB Range` only goes to 12 st in the dump, so with a non-12-TET tuning system loaded it would likely play out of tune (the default 12-TET changes nothing) [manual, API].
- **Granulator III** (Robert Henke; included with Suite): granular instrument with Classic, Loop and Cloud modes, live audio capture,
  MPE and tuning-system support ([Ableton](https://www.ableton.com/en/packs/granulator-iii/)); the reviewer notes it dropped Granulator II's FM and
  dual filters ([SOS](https://www.soundonsound.com/reviews/ableton-live-12)). Its 117 parameter names are in the reference dump (for example `Mode`, `Grain Size`, `Density`,
  `Position`, `Scan`, `Variation`, `Spread` in semitones, `Transpose`, `Flt Freq`). Use it for texture layers and drones, not as the pad's main voice: grain
  position, size and spray decide the pitch stability, so measure a held note before trusting it.
- **Drone Lab** (Max for Live Harmonic Drone Generator by Expert Math, eight voices, equal or just intonation; 70+ racks): just intonation puts
  intervals off the 12-tone grid on purpose, so a Drone Lab sound can sound "out of tune" against equal-tempered notes
  ([Ableton](https://www.ableton.com/en/packs/drone-lab/)). **Synth Essentials**: over 250 Wavetable, Operator, Analog, Tension and Collision presets plus
  200 instrument racks, designed around a few macros ([Ableton](https://www.ableton.com/en/packs/synth-essentials/)): open the underlying
  instrument and read it as in 6.1. **PitchLoop89** is a pitch-shifting delay effect, not a sound source ([Ableton](https://www.ableton.com/en/packs/pitchloop89/)).

### 3.9 Collision, Tension, Electric

Physical-model instruments (Applied Acoustics Systems). **Collision** (mallet, noise, two resonators: beam, marimba, string, membrane,
plate, pipe, tube; `Res 1 Inharmonics` and `Res 2 Inharmonics` stretch partials) gives metallic and mallet percussion and decaying bell tones; **Tension** (bow, hammer or
plectrum on a modelled string, body, filter, unison) gives bowed and plucked strings and, with the bow exciter, slow evolving drones; **Electric** is a
tine electric piano. Each has tuning controls that can move pitch: Collision `Res n Tune`, `Res n Fine Tune` and `Res n Tune < Key`; Tension `Stretch`, `Error` and `Uni Detune`; Electric `Detune` and `KB Stretch`. Tension's and Analog's `Key Priority` decides stealing.
They are rarely the first choice for industrial pads; Collision and Tension are useful for metallic hits and bowed textures.

---

## 4. Which instrument for which job

| Job | First choice | Why | Also good | Avoid |
| --- | --- | --- | --- | --- |
| Background pad ("big, heavy, clean") | Drift (Stereo or Unison) or Wavetable (Classic unison, saw-like table) | a saw stack through a 24 dB low-pass is exactly the reference's anatomy; per-voice width without noise; light CPU | Analog (warm, per-voice filters), Poli with real `Saw`/`Pulse` levels, Meld for evolving beds | patches whose only voice is a sub plus noise; Noise or Shimmer unison; chorus on noisy layers; saturating the summed chord |
| Drone or texture bed | Meld, Wavetable with slow position LFOs | long evolving timbres from cheap modulation; Meld has noise, swarm and rain sources | Granulator III (Cloud), Drone Lab racks, Operator with looping envelopes, Tension with the bow | Poly instruments with random pitch jitter if the drone must stay tuned |
| Bass (sub and mid) | Drift in Mono, or Operator | a mono saw/saturated voice with a sub-sine and a low-pass is the classic structure; Operator gives punchy digital and FM tone | Analog (sync, sub), Wavetable (Mono + Sub), Creative Extensions *Bass* | sub octaves below the lowest note you need (a root at 41-55 Hz needs no extra -1 octave) |
| Lead | Drift (Mono, Legato, Glide) or Analog | glide, vibrato, detuned dual oscillators | Wavetable, Meld | unison so wide it reads out of tune |
| Pluck or arp | Operator, or Drift/Analog with a decaying filter envelope | fast decays of both loudness and brightness | Wavetable (Env 2 on position), Collision | slow filter envelopes |
| Kick | DS Kick, Operator, or a sample in a Drum Rack (Drum Sampler or Simpler) | a sine with a pitch sweep tuned to the key | Simpler one-shot | long reverb tails before the transient is set |
| Hats and percussion | DS HH, DS Clang, DS Clap, Drum Sampler effects, Operator with LFO noise | noise plus filter envelopes | Impulse (legacy) | - |
| Risers, noise, FX | Meld noise oscillators, Wavetable Noise unison (on purpose), Operator noise | noise is the point here | Granulator III | - |
| Organic or orchestral layer | Simpler or Sampler racks (Orchestral Strings, Mood Reel) | recorded acoustic partials | - | assuming A = 440 Hz tuning of the samples |

Full recipes by role, layering and width are in `03-sound-design-recipes.md`; the layered-pad rack pattern (body, air, sub) is in `01-live-workflow.md`.

**Third-party equivalents.** Pros commonly reach for Serum, Vital or Massive X (wavetable and hybrid), Sylenth1, Diva or Hive (virtual analog, supersaws, pads),
FM8 or Dexed (FM) and Kontakt or Omnisphere (sample libraries). The Live equivalents are Wavetable, Drift and Analog, Operator, and Sampler or Simpler with the installed packs; Attack Magazine's
synth tutorials use those plug-ins, and the principles here (anatomy, detune, filter, envelope) transfer directly [practice].

**Starting settings** (all [practice]; none has been auditioned by Fred; use them to get a measurable first draft, then A/B and iterate, see 6.2).
Write chords at their real pitch and keep the lowest voicing open (section 5.3); the reference pad's root is E0-G0 (41-49 Hz).

*A. Big, heavy, clean pad, Drift.* `Osc 1 Wave` Saw, `Osc 1 Shape` 0, `Osc 1 Gain` -6 dB; `Osc 2 Wave` Saw, `Osc 2 Oct` 0 (the default is -1), `Osc 2 Detune` +0.07 (about +7 cents), `Osc 2 Gain` -9 dB;
`Noise On` Off; `Osc Retrig On` Off. `LP Type` II, `LP Freq` 1.6 kHz, `LP Res` 0.05-0.15, `Key > LPF` 0.7, `HP Freq` 30 Hz. `Env 1`: Attack 400 ms, Decay 4 s,
Sustain 85 %, Release 2.5 s. `voice_mode` Stereo with `Spread` about 35 % (or Unison with `Strength` about 25 %), `Drift` 10-20 %. Movement: Env 2 (Attack 1.5 s,
Sustain 60 %) to `LP Freq` by +10-15 %; the LFO (Sine, about 0.12 Hz, `LFO Retrig On` Off) to `LP Freq` by about 5 %. Source choosers are the `mod_matrix_*` properties.

*B. Same pad, Wavetable.* Pick a table whose position 0 is a saw (read `oscillator_1_wavetables` for the category). `Osc 1 Pos` 0 %, `Osc 1 Detune` -5 ct, `Osc 1 Pan` 20 % left,
`Osc 1 Gain` -6 dB; Osc 2 the same table (`Osc 2 On` On: it is Off by default), `Osc 2 Detune` +5 ct, 20 % right. `Sub On` Off for chords. `Flt 1` Lowpass, circuit Clean (MS2 for a touch of grit), `Slope` 24,
`Freq` 1.6 kHz, `Res` 8 %, `Drive` 0 dB. `unison_mode` Classic, `unison_voice_count` 3, `Unison Amount` 15-25 % (calibrate in cents, 6.3). `Amp`: Attack 400 ms, Decay 2 s, Sustain
-3 dB, Release 2 s. Env 2 to `Flt 1 Freq` +10 %; LFO 1 (Sine, 0.1 Hz, `Retrigger` Off) to `Osc 1 Pos` about 10 %. Put a sub on its own mono instrument playing the root only.

*C. Dark drone.* Wavetable: two rich tables (`Osc 2 On` On), `Detune` +-4 ct, unison Classic with 3-5 voices at Amount 15 %, `Flt 1` 24 dB low-pass at 0.9-1.2 kHz, `Amp Attack` 3 s, Sustain 0 dB, Release 6 s; LFO 1 Sine
0.03-0.08 Hz (`LFO 1 Sync` Free) on position by +-20 %, LFO 2 at 0.05 Hz on filter frequency by +-8 %. Or Meld: engine A *Swarm Saw* (Motion 20-30 %: the macro knob `A Osc Shape` or `A Osc Tone`, read the display), engine B a sine from *Sub* or *Basic Shapes* an octave down, `A Keytracking` and
`B Keytracking` on, property `unison_voices` 2 (Stacked Voices), LFOs at 0.05-0.2 Hz on the filters. Keep tuned drones on equal temperament (no just-intonation Drone Lab racks) unless asked.

*D. Mono bass, Drift.* `voice_mode` Mono, `Thickness` 0-15 %, `Legato On`, `Glide Time` 0-60 ms. `Osc 1 Wave` Saturated or Saw, `Osc 1 Gain` -6 dB; `Osc 2 Wave` Sine with `Osc 2 Oct` -1 at -8 dB *only if* the lowest note is above about 50 Hz. `LP Type` II,
`LP Freq` 180-350 Hz, `LP Res` 0.10-0.25, `Key > LPF` 0.6-1.0. `Env 1`: Attack 2 ms, Decay 300 ms, Sustain 80 %, Release 80 ms; Env 2 (Decay 250 ms, Sustain 0) to `LP Freq` by +20-40 %. See `04-drums-and-low-end.md` for the kick relationship.

*E. Mono lead, Analog or Drift.* Two saws detuned in opposite directions by 6-10 cents, mono and legato, glide 20-80 ms; 24 dB low-pass at 2-3 kHz, resonance 10-20 %, filter envelope 20-40 %; vibrato 5-6 Hz, at most 20 cents, with a 300-500 ms
delay; amp Attack 5 ms, Decay 200 ms, Sustain 75 %, Release 150 ms.

*F. Pluck or arp.* Amp Attack 0-2 ms, Decay 200-350 ms, Sustain 0-5 %, Release 80-150 ms; Env 2 (Decay 150-250 ms, Sustain 0) to `LP Freq` by +60-80 % starting from 500-800 Hz with resonance 0.15-0.3; polyphonic. Operator version: carrier A sine,
modulator B at ratio 2-3 with a moderate `Osc-B Level` and a shorter envelope than A, so the brightness decays before the loudness.

*G. Kick.* DS Kick: `Pitch` 45-55 Hz (the key's root), low `Drive`, `Click` on, `Decay` 300-450 ms, medium `Env`. Operator: a sine, pitch envelope from +12 to +36 semitones to 0 in 40-100 ms, amp decay 250-450 ms, sustain -inf, filter off. Details: `04-drums-and-low-end.md`.

---

## 5. Pitch facts agents get wrong

### 5.1 MIDI numbers versus Live's octave names

Live names notes with **C3 = MIDI 60**, one octave lower than scientific pitch notation (where C4 = 60: [Middle C](https://en.wikipedia.org/wiki/Middle_C),
[scientific pitch notation](https://en.wikipedia.org/wiki/Scientific_pitch_notation)). Evidence in Live's own manual: Sampler's zone editor spans
C-2 to G8 (MIDI 0-127), Simpler plays a sample at its original pitch on C3, Operator's and Wavetable's key-tracking centre is C3, and Meld without key
tracking plays a constant C3 [manual 31.10, 31.11, 31.9, 31.13, 31.8]. The tools take either a number or a Live name. Frequency = 440 x 2^((n - 69)/12) Hz [calc]:

| MIDI | Live name | Hz | | MIDI | Live name | Hz |
| --- | --- | --- | --- | --- | --- | --- |
| 24 | C0 | 32.70 | | 52 | E2 | 164.81 |
| 28 | E0 | 41.20 | | 57 | A2 | 220.00 |
| 29 | F0 | 43.65 | | 60 | C3 | 261.63 |
| 30 | F#0 | 46.25 | | 64 | E3 | 329.63 |
| 31 | G0 | 49.00 | | 69 | A3 | 440.00 |
| 33 | A0 | 55.00 | | 72 | C4 | 523.25 |
| 36 | C1 | 65.41 | | 81 | A4 | 880.00 |
| 40 | E1 | 82.41 | | 84 | C5 | 1046.5 |
| 45 | A1 | 110.00 | | | | |
| 48 | C2 | 130.81 | | | | |

Many MIDI libraries and most frequency tables use C4 = 60, so a name copied from them is an octave off in Live: write numbers when in doubt. The earlier bass and pad comments in this project were an octave off (handoff note).

### 5.2 What makes the sounding pitch differ from the written note

| Cause | Where to look | Notes |
| --- | --- | --- |
| Sub octave | Wavetable `Sub Transpose`; Poli `Sub Octave` (-2, -1, 0; -1 by default); Analog `OSC1 Mode` = Sub; Meld *Sub* oscillator, Aux macro | a sub two octaves down turns written A2 (220 Hz) into 55 Hz |
| Transpose, octave, semitone | `Transpose` (Wavetable, Drift +-48, Operator, Simpler, Sampler), `Osc N Transp`, `Osc N Oct`, Analog `Octave` and `Semitone`, Poli `Saw  Tune` (two spaces) and `Pulse Tune`, Meld `A Octave`, `A Transpose` and `A Transp Scale` (and `B`) | combine: the offsets add |
| FM and ring ratios | Operator `X Coarse`, `X Fine`; Wavetable FM *Tune*; Poli `Ring` | non-integer ratios shift or smear the pitch; fundamental = gcd (1.4) |
| Fixed or non-tracking oscillators | Operator `X Fix On`; Meld `A Keytracking` / `B Keytracking` off | every note plays the same pitch |
| MIDI effects before the instrument | `get_devices` (Pitch, Scale, Chord, Arpeggiator, Random, Note Length) | Pitch moves notes up to +-128 semitones; Chord adds up to six extra pitches; Scale remaps | 
| Rack structure | Instrument Rack key, velocity and chain-select zones; Drum Rack chain `Play` note | a chain can play a different sample or note than written |
| Tuning system or scale | Live 12 tuning systems (default 12-TET; saved with the set; Drum Racks bypass them; Max for Live instruments need a 48 st bend range); Meld *Use Current Scale* | read `live_set tuning_system` (`name`, `reference_pitch`) with `lom_get` ([Using Tuning Systems](https://www.ableton.com/en/live-manual/12/using-tuning-systems/)) |
| Sample root and tuning | Simpler and Sampler root key and `Detune`; sample's own pitch | a kick or string sample is rarely exactly at A = 440 |
| Built-in tuning wobble | Analog `Key Stretch`, `Key Error`; Tension `Stretch`, `Error`; Drift `Drift` | small by design, large if set high |
| Missing fundamental | spectrum with partials at 2:3:4 and no 1 | the ear hears the implied pitch below the lowest partial ([SOS, bells](https://www.soundonsound.com/techniques/synthesizing-bells)); "pitch" and "lowest peak" can disagree |

### 5.3 Low-register intervals

Partials closer than about one critical band (the ear's filter width) cannot be resolved and are heard as beating or roughness
([critical band](https://en.wikipedia.org/wiki/Critical_band); [consonance and dissonance](https://en.wikipedia.org/wiki/Consonance_and_dissonance)).
The Glasberg-Moore width is ERB = 24.7 x (4.37 x f_kHz + 1) Hz ([ERB](https://en.wikipedia.org/wiki/Equivalent_rectangular_bandwidth);
stated valid from 100 Hz, so numbers below it are extrapolated): 31 Hz at 55 Hz, 37 Hz at 110 Hz, 48 Hz at 220 Hz [calc]. A minor third above A0 is 10.4 Hz
apart, a major third 14.3 Hz, a fifth 27 Hz: all inside one ERB. The root above which the two **fundamentals** of an interval are at least one ERB apart [calc]:

| Interval | Lowest root | Rule of thumb |
| --- | --- | --- |
| Octave | any | always safe |
| Perfect fifth | about 63 Hz (C1) | safe above C1; the harmonics also coincide |
| Perfect fourth | about 109 Hz (A1) | |
| Major third | about 163 Hz (E2) | avoid below E2 |
| Minor third | about 304 Hz (D#3) | avoid below D#3; this is a minimum, upper partials can beat too |

This is the arithmetic behind Fred's "wrong notes or tuning": a pad with a sub two octaves down turned the chord A2-C3-E3 into A0-C1-E1 (55, 65.4, 82.4 Hz), whose
neighbours are 10 and 17 Hz apart, far inside one ERB, so the chord could not be heard as a chord. The practical rule used across this set
(`00-agent-playbook.md` rule 4, `08-arrangement-and-composition.md` section 2.5): below about 130 Hz (Live C2) only roots, fifths and octaves; major thirds from about 165 Hz (E2);
minor thirds and seconds higher still; the lowest sounding note is the chord root. Rough but not "wrong" is the right diagnosis; the fix is the voicing, not the tuning.
The table above is the derived, stricter fundamentals-only bound behind that rule, and the minor third is the interval that needs the most room.

### 5.4 Verifying what pitch a patch really sounds

Do not trust a note name, a preset name or `analyze_audio`'s key estimate (it works on full mixes). Render **one held note, dry** (reverb, delay, chorus and
saturation off; the track soloed), read the spectral peaks and compare them with the expected frequency. In Live naming, the peak list should start at the written note
or at an octave you intended. A saw also shows its natural harmonics: the 3rd partial sits 2 cents off equal-tempered E, the 5th about 14 cents flat of C#, the 7th
about 31 cents flat of G, which is correct and not a tuning error. Use the function in 6.3; it returns the strongest peaks as (Hz, note, cents off, dB) and flags energy
below the written pitch (`sub_octave_db`, `sub_2oct_db` above 0 dB means the patch sounds lower than written). Two examples from synthetic tones [calc]:
five saws detuned by up to +-12 cents at A2 show peaks at 218.5 and 221.5 Hz (A2 -12 and +12 cents); a saw sub two octaves below A2 shows its strongest peak at 55.0 Hz (A0) with
`sub_2oct_db` = +12.0.

---

## 6. For an agent

### 6.1 Inspect before trusting a preset

1. `get_devices(track)`: the whole chain, including MIDI effects *before* the instrument, racks with chains and zones, macros and Drum Rack pads. Anything that is not the instrument can change pitch or timbre.
2. `get_device(track, device, detail=True)` for the instrument and every device inside racks: read the parameters in the table, then the *properties* (`unison_mode`, `voice_mode`, `playback_mode`, ...). Racks hide values behind macros: read the mapped parameters, not only the macro names.
3. Predict the sound from the numbers first (what is loud, what is off, what is an octave away), then measure (6.3), and only then listen or ask.

| Device | Read | Red flags |
| --- | --- | --- |
| Wavetable | `Osc 1/2 On, Gain, Transp, Detune, Pos`; `Sub On, Gain, Transpose`; `Flt 1 Type, Freq, Res, Drive`; `unison_mode`, `unison_voice_count`, `Unison Amount`; `Amp` envelope; `Transpose` | both oscillators off or at -inf; Sub louder than the oscillators or at -2; `Transp` of 12 or more; Noise or Shimmer unison; cutoff under 500 Hz on a pad |
| Drift | `Osc 1/2 Wave, Oct, Gain, Detune`; `Noise On`; `LP Type, Freq, Res`; `Env 1`; `voice_mode`, `Strength`/`Spread`/`Thickness`; `Drift` | `Noise On`; `Osc 2 Oct` of -3; oscillator gain at or above 0 dB (saturates the filter); `Drift` above 50 %; Mono for chords |
| Operator | `Algorithm`; each `Osc-X Level, Wave, Coarse, Fine, Fix On`; `Pe On, Amount`; `Transpose`; `Spread`; filter | non-integer ratios; fixed oscillators; an active pitch envelope on a pad; a loud modulator; `Tone` 100 % on high notes |
| Analog | `OSC1/2 On, Level, Shape, Octave, Semi, Detune, Mode`; `Noise On, Level`; `F1/F2 Type, Freq, Resonance`; `Unison`; `Key Stretch`, `Key Error` | Sub mode on; noise level; large unison detune; `Key Error` above 0 |
| Poli | `Saw`, `Pulse`, `Sub`, `Sub Octave`, `Noise`, `LPF`, `Res`, `Chorus`, `Voicemode`, `Unison Spread`, `Sub -> Filter` | `Saw` and `Pulse` at 0 %; `Sub Octave` -2; `Noise` above about 5 %; chorus on with noise |
| Simpler, Sampler | `Transpose`, `Detune`, warp mode, root and loop; `Voices`, `Spread` | unexpected `Transpose`; complex warp modes smearing pitch; sample not at A = 440 |
| Racks | chain zones and selector, macros, `Receive`/`Play` | key or velocity zones playing another sample; a `Play` offset |

**Worked example, "Dark Throne" (a Max for Live Poli preset from Creative Extensions).** The preset loads with `Saw` 0 %, `Pulse` 0 %, `Sub` 39.4 % at `Sub Octave` -2 (saw sub), `Noise` 18.9 %,
`LPF` 372 Hz, `Res` 2 %, `Chorus` C; in the NOVA set the agent had lowered `Sub` to 15 %, and `Sub -> Filter` read Bypass.
Reading it: no main oscillator carries 150-2000 Hz at the written pitch; the only pitched source is the sub, two octaves below the note; if `Sub -> Filter` = Bypass really skips the filter,
the only filtered element is the noise (a 372 Hz low-pass on noise is a low rasp). Predicted sound: hollow (no body), airy (noise between harmonics), chord thirds at 55-82 Hz (rough, "wrong notes").
Fred's complaints matched each prediction, and `get_device` would have shown all of it before any audition. A cleaner variant used `Saw` 80 %, `Pulse` 0, `Sub` 35 % at -1 octave, `Noise` 0, `LPF` 1.4 kHz, `Res` 0
(Fred's later "base pad").

### 6.2 Change one thing at a time and keep the original

1. **Keep a way back.** Either `duplicate_track` into a muted twin named "<name> (keep)", or use the device's A/B slots: `device_action(track, device, "save_ab_slot")` stores the current state in the other slot and
   `set_device(track, device, compare_b=True/False)` swaps between them (native devices that report `compare_b` in `get_device`; Live's manual notes the original stays in B once you edit A;
   Max for Live devices may not support it, so use the twin track). Racks also have `store_variation` and `recall_variation`.
2. **Record the baseline**: `get_device` output plus the probe from 6.3 (peaks, harmonics, between-harmonics level).
3. **Change one parameter** (or one named pair that must move together) with `set_device_parameters`; re-read the device to confirm the display strings (units differ: Wavetable `Detune` is cents, Drift `Osc 2 Detune` shows no unit).
4. **Render the same material again** (the same dry note and the same chord), re-run the probe, write down before/after.
5. **Label and loudness-match** the audition: clips named "A: base" and "B: LPF 372 Hz -> 1.4 kHz", the faders set so A and B agree within 0.2 LU of integrated loudness (0.3 LU at most; `analyze_audio`), the same scene, the same effects. A louder version always wins an A/B.
6. **Do not stack mix moves on a sound edit.** The failed pass changed limiters, EQs and faders on every stem at once; nobody could tell which move caused "garbage". Sound design and mixing are separate passes with separate A/Bs; see `06-mixing.md` and `11-listening-without-ears.md`.
7. **Iterate on Fred's chosen sound**; do not replace it with a different preset. Rank candidates by role and anatomy (6.1), never by spectral distance to a full-mix reference: a mix spectrum contains drums, bass and vocals that one synth cannot be.

### 6.3 Measuring harmonic content

Render a scratch track named like `[test:probe] pad` with one 4-bar clip holding one note (for a pad's root, the lowest note it will really play), solo it, bypass
reverb, delay, chorus and saturation, arrange it, `bounce(stems=[track], name="probe-A1")` (real-time and audible: warn Fred; files land in `~/Music/AbletonMCP/Bounces/probe-A1/` as `probe-A1 - <track>.wav`) and read the WAV with `ears.audio.read` (or any loader). The function below
is tested on synthetic tones (numpy and scipy only; run with the repo's environment). Delete the scratch track afterwards.

```python
import numpy as np
from scipy.signal import find_peaks
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
live_name = lambda m: "%s%d" % (NAMES[int(round(m)) % 12], int(round(m)) // 12 - 2)   # Live: C3 = 60
hz = lambda midi: 440.0 * 2 ** ((midi - 69) / 12.0)

def probe_note(x, sr, midi, skip=0.5, kmax=16):
    """x: mono samples of ONE held note, dry; midi: the note that was written (Live numbers)."""
    f0 = hz(midi)
    x = np.asarray(x, float)[int(skip * sr):]
    n = 1 << int(np.ceil(np.log2(len(x))))
    spec = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(len(x)), n)) ** 2
    fr = np.fft.rfftfreq(n, 1 / sr)
    db = 10 * np.log10(spec / spec.max() + 1e-20)
    band = lambda lo, hi: spec[(fr >= lo) & (fr < hi)].sum() + 1e-30
    idx, _ = find_peaks(db, height=-50, prominence=15, distance=max(1, int(0.5 / (fr[1] - fr[0]))))
    peaks = []
    for i in sorted(sorted(idx, key=lambda i: -db[i])[:8]):                   # strongest peaks as notes
        a, b, c = db[i - 1], db[i], db[i + 1]
        f = fr[i] + (0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c else 0.0) * (fr[1] - fr[0])
        m = 69 + 12 * np.log2(f / 440.0)
        peaks.append((round(f, 1), live_name(m), int(round((m - round(m)) * 100)), round(float(db[i]), 1)))
    h = np.array([band(f0 * k * 0.98, f0 * k * 1.02) for k in range(1, kmax + 1)])   # harmonics 1..16 of the written note
    rel = lambda v: round(float(10 * np.log10(v / h.max())), 1)
    gaps = sum(band(f0 * (k + .25), f0 * (k + .75)) for k in range(1, kmax))        # energy between the harmonics
    return {"written": "%s = %.2f Hz" % (live_name(midi), f0), "peaks": peaks,
            "harmonics_db": [rel(v) for v in h],
            "sub_octave_db": rel(band(f0 * .49, f0 * .51)), "sub_2oct_db": rel(band(f0 * .245, f0 * .255)),
            "even_vs_odd_db": round(float(10 * np.log10(h[1::2].sum() / max(h[2::2].sum(), 1e-30))), 1),
            "between_harmonics_db": round(float(10 * np.log10(gaps / h.sum())), 1),
            "harmonics_within_40db": int((10 * np.log10(h / h.max()) > -40).sum())}
# a = ears.audio.read(path); print(probe_note(a.mono(), a.rate, midi=33))     # A0 = 55 Hz
```

Calibration on ideal tones at A2 (220 Hz) [calc]; real patches add filter roll-off, detune smear and noise, so compare *before and after* on the same note rather than against these absolutes:

| Test tone | `even_vs_odd_db` | `sub_2oct_db` | `between_harmonics_db` |
| --- | --- | --- | --- |
| ideal saw | +2.8 | below -100 | below -100 |
| ideal square | below -100 (no even harmonics) | below -100 | below -100 |
| saw + white noise 20 dB below | +2.8 | about -57 | -31 |
| saw + white noise 10 dB below | +2.7 | about -48 | -21 |
| saw sub two octaves down (the "Dark Throne" anatomy) | +2.5 | **+12** (sub louder than anything at the written pitch) | not meaningful while the sub flags are above 0 |
| five saws within +-12 cents | +2.8 | below -100 | peaks split into clusters 3 Hz apart |

How to read it:
- **Pitch.** The first peak should be the written note's frequency (or an intended octave). `sub_octave_db` or `sub_2oct_db` above 0 dB: the patch sounds lower than written (a sub, a transpose, an FM subharmonic). Peaks that are not at multiples of the written pitch: inharmonic FM, ring modulation, sync or intermodulation.
- **Hollow** is likely when `even_vs_odd_db` is strongly negative (square, or FM with the modulator at twice the carrier), when `harmonics_db` dips at the 2nd harmonic, or when the 150-600 Hz band is scooped while a sub and highs remain
  (`ears.measure.third_octave_levels` gives the bands). **Thin**: few `harmonics_within_40db`, weak 150-600 Hz. **Airy or raspy**: `between_harmonics_db` above about -30 dB.
  **Wide or thick** (unison, detune): each harmonic splits into a cluster; the spacing in cents is the detune, and the spacing of the k-th harmonic in Hz is k times that of the fundamental.
- **Repeatability.** Free-running oscillator phases, Drift, random pan, sample-and-hold LFOs and Random Note unison make two renders of the same patch differ a little. Render the
  baseline twice to learn your measurement noise, and treat differences smaller than that (levels within about 1 dB, peaks within about 5 cents) as no change.
- **Calibrate unknown scales** (Wavetable `Unison Amount`, Drift `Strength`, Analog `Unison Detune`): render the same held note at 0, 25, 50 and 100 % and read the spread of the fundamental's peak in cents.
- Descriptors of brightness and noisiness over a longer phrase: spectral centroid and spectral flatness ([centroid](https://en.wikipedia.org/wiki/Spectral_centroid), [flatness](https://en.wikipedia.org/wiki/Spectral_flatness))
  are reasonable summaries, but they describe a sound; they do not tell you whether Fred will like it.

### 6.4 What to ask Fred, and when to stop

Stop and ask (with a labelled, loudness-matched A/B, never a bare question) when: you are about to replace a sound he chose; a change moves a measurement more than you predicted (the written pitch is no longer the strongest peak, loudness changes by more than
1 dB, the spectral centroid shifts by a third of an octave or more); the preset has hidden modification (MIDI effects, rack zones, macros); a word he used maps to several spectral causes; or the tools cannot verify what you did.
Useful questions, each with a rendered A and B:
- "When you say hollow, which is closer: (1) not enough low-mid body, (2) like a clarinet, only odd partials, (3) phasey and comb-like? A has a saw added at the written pitch, B has the cutoff raised."
- "Pad A keeps the sub at -1 octave, pad B has no sub and a saw an octave lower: which has the right weight? Which is cleaner?"
- "Is the chord low enough to want thirds (it will be rough below E2), or should the lowest voices be root and fifth only?"
- "Reference root is E0 (41 Hz): do you want the pad's lowest note there, or A0 (55 Hz)?"
- "Is this width right (detune about 7 cents plus stereo voices), or does it start to sound out of tune?"
Say what changed, in one line, and which one thing differs between A and B.

### 6.5 Common mistakes

- Choosing a preset by name or by spectral distance to a reference mix; trusting that a "pad" preset has a pad's anatomy.
- Believing a note name: Live's C3 = 60, so a 220 Hz root is A2 (MIDI 57), not A3; copying note names from C4 = 60 tables.
- Adding a sub octave or a -2 transpose to a patch whose root is already 41-55 Hz (energy at 20-27 Hz that only eats headroom), or leaving a sub on a chord instrument.
- Putting a chorus or ensemble on a noisy layer, or using Noise and Shimmer unison in a pad meant to be clean.
- Saturating or distorting the summed chord (intermodulation) instead of one voice or the root.
- Thirds below about E2 (major) or D#3 (minor), or a third in the sub region from a sub octave.
- Treating `Unison Amount`, `Strength` or `Detune` as cents; non-integer FM or ring ratios on notes that must be tuned; fixed oscillators in tuned parts.
- Setting parameters by raw number when the display string says otherwise (read back the display after every set).
- Several changes in one audition; auditions without labels; an A/B that is louder on one side; overwriting the sound Fred chose.

---

## Sources

Ableton (primary)
- [Live 12 manual, 31. Live Instrument Reference](https://www.ableton.com/en/live-manual/12/live-instrument-reference/) (Analog, Collision, Drift, Drum Sampler, Electric, Impulse, Meld, Operator, Sampler, Simpler, Tension, Wavetable)
- [Live 12 manual, 33. Max for Live Devices](https://www.ableton.com/en/live-manual/12/max-for-live-devices/) (DS drum synths); [25. Instrument, Drum and Effect Racks](https://www.ableton.com/en/live-manual/12/instrument-drum-and-effect-racks/); [Working with Instruments and Effects](https://www.ableton.com/en/live-manual/12/working-with-instruments-and-effects/) (A/B compare, presets); [Live MIDI Effect Reference](https://www.ableton.com/en/live-manual/12/live-midi-effect-reference/); [Using Tuning Systems](https://www.ableton.com/en/live-manual/12/using-tuning-systems/)
- Packs: [Creative Extensions](https://www.ableton.com/en/packs/creative-extensions/), [Granulator III](https://www.ableton.com/en/packs/granulator-iii/), [Synth Essentials](https://www.ableton.com/en/packs/synth-essentials/), [Drone Lab](https://www.ableton.com/en/packs/drone-lab/), [Mood Reel](https://www.ableton.com/en/packs/mood-reel/), [Glitch and Wash](https://www.ableton.com/en/packs/glitch-and-wash/), [Build and Drop](https://www.ableton.com/en/packs/build-and-drop/), [PitchLoop89](https://www.ableton.com/en/packs/pitchloop89/), [Orchestral Strings](https://www.ableton.com/en/packs/orchestral-strings/)
- Blog: [Pad it out: 10 ways to make distinctive pad sounds](https://www.ableton.com/en/blog/pad-it-out-10-ways-make-distinctive-pad-sounds/), [Wavetable design notes](https://www.ableton.com/en/blog/new-wave-depth-look-wavetable/), [Meld](https://www.ableton.com/en/blog/meld-a-look-at-live-12s-new-bi-timbral-synth/), [Drift in Live 11.3](https://www.ableton.com/en/blog/drift-exploring-the-new-synth-in-live-113/), [Learning Synths](https://www.ableton.com/en/blog/learn-synthesis-in-your-browser/) (the lesson pages at [learningsynths.ableton.com](https://learningsynths.ableton.com/en/) need a browser and could not be read by the fetch tool)
- This repo: `docs/TOOLS.md` (tool signatures), `docs/reference/lom_docs_12.4.5.md` (Live Object Model: WavetableDevice, DriftDevice, MeldDevice, TuningSystem), `.claude/skills/listening-loop/SKILL.md`, `docs/handoff/2026-10-08-nova-v2-paused.md` (what Fred said, the measured references)

Sound On Sound, Gordon Reid, "Synth Secrets"
- [What's In A Sound?](https://www.soundonsound.com/techniques/whats-sound), [An Introduction To Additive Synthesis](https://www.soundonsound.com/techniques/introduction-additive-synthesis), [Further With Filters](https://www.soundonsound.com/techniques/further-filters), [Of Responses And Resonance](https://www.soundonsound.com/techniques/responses-resonance), [Envelopes, Gates and Triggers](https://www.soundonsound.com/techniques/envelopes-gates-triggers), [Modulation](https://www.soundonsound.com/techniques/modulation), [Amplitude Modulation](https://www.soundonsound.com/techniques/amplitude-modulation), [An Introduction To Frequency Modulation](https://www.soundonsound.com/techniques/introduction-frequency-modulation), [Introducing Polyphony](https://www.soundonsound.com/techniques/introducing-polyphony), [Formant Synthesis](https://www.soundonsound.com/techniques/formant-synthesis), [Synthesizing Wind Instruments](https://www.soundonsound.com/techniques/synthesizing-wind-instruments), [Synthesizing Plucked Strings](https://www.soundonsound.com/techniques/synthesizing-plucked-strings), [Synthesizing Bells](https://www.soundonsound.com/techniques/synthesizing-bells), [Strings: String Machines](https://www.soundonsound.com/techniques/synthesizing-strings-string-machines), [Strings: PWM and String Sounds](https://www.soundonsound.com/techniques/synthesizing-strings-pwm-string-sounds)
- [SOS review: Ableton Live 12](https://www.soundonsound.com/reviews/ableton-live-12)

Other
- Attack Magazine, Synth Secrets: [Detuned festival leads with Ableton Drift](https://www.attackmagazine.com/technique/synth-secrets/detuned-festival-leads-with-ableton-drift/), [Pitch-bending chord stabs with Drift](https://www.attackmagazine.com/technique/synth-secrets/pitch-bending-chord-stabs-with-ableton-drift/), [Drift bass](https://www.attackmagazine.com/technique/synth-secrets/use-drift-to-modulate-bass-like-overmono-modeselektor/), [Noisia-style synths with Operator](https://www.attackmagazine.com/technique/synth-secrets/learn-how-to-make-noisia-inspired-synths-with-abletons-operator/), [Analog leads and pads](https://www.attackmagazine.com/technique/synth-secrets/trippy-leads-analogue-pads-ableton-analog-sonnox-voxdoubler/), [Layering synths](https://www.attackmagazine.com/technique/synth-secrets/layering-synths/), [Legato synths: glide, slide, portamento](https://www.attackmagazine.com/technique/passing-notes/legato-synths-glide-slide-portamento/)
- Szabo, [How to Emulate the Super Saw](https://www.adamszabo.com/internet/adam_szabo_how_to_emulate_the_super_saw.pdf) (KTH bachelor thesis, 2010); Splice, [What's in a waveform?](https://splice.com/blog/whats-in-a-wave/); Yamaha, [Synthesizer basics with the MX, part II](https://yamahasynth.com/learn/synth-programming/synthesizer-basics-with-mx-part-ii/); Electric Druid, [Timbral evolution](https://electricdruid.net/?p=1287)
- Wikipedia (maths and definitions only): [pulse wave](https://en.wikipedia.org/wiki/Pulse_wave), [sawtooth wave](https://en.wikipedia.org/wiki/Sawtooth_wave), [triangle wave](https://en.wikipedia.org/wiki/Triangle_wave), [oscillator sync](https://en.wikipedia.org/wiki/Oscillator_sync), [frequency modulation synthesis](https://en.wikipedia.org/wiki/Frequency_modulation_synthesis), [beat (acoustics)](https://en.wikipedia.org/wiki/Beat_(acoustics)), [critical band](https://en.wikipedia.org/wiki/Critical_band), [equivalent rectangular bandwidth](https://en.wikipedia.org/wiki/Equivalent_rectangular_bandwidth), [consonance and dissonance](https://en.wikipedia.org/wiki/Consonance_and_dissonance), [comb filter](https://en.wikipedia.org/wiki/Comb_filter), [intermodulation](https://en.wikipedia.org/wiki/Intermodulation), [timbre](https://en.wikipedia.org/wiki/Timbre), [vibrato](https://en.wikipedia.org/wiki/Vibrato), [spectral centroid](https://en.wikipedia.org/wiki/Spectral_centroid), [spectral flatness](https://en.wikipedia.org/wiki/Spectral_flatness), [middle C](https://en.wikipedia.org/wiki/Middle_C), [scientific pitch notation](https://en.wikipedia.org/wiki/Scientific_pitch_notation)

## Open questions / where sources disagree

- **"Pulse waves have only odd harmonics."** Yamaha's tutorial says it of pulse waves in general; the pulse-wave maths (and Wikipedia) show only the 50 % pulse is odd-only. This digest follows the maths.
- **What "hollow" means.** No source ties it to one spectral property; Wikipedia's timbre article only grounds "bright". Clarinet and square-wave odd harmonics, scooped low-mids and comb notches are all used. Ask Fred, with an A/B, which he means.
- **Detune zones** (3, 12, 25, 50 cents) are conventions built from beat-rate arithmetic, one measured supersaw, one string-synth patch and one Ableton tutorial; there is no standard that says "out of tune starts at N cents". Ableton's tutorial states its detune advice as a percentage ("1% to 10%") while Wavetable's own display is in cents.
- **Envelope and LFO starting values** are practitioner conventions; no authoritative source gives pad, bass or pluck times. They are meant to be measured and A/B'd.
- **Drift `Osc 2 Detune` units**: the manual says semitones, the API display has no unit, an Attack Magazine patch uses -0.11 (consistent with semitones); confirm by measurement.
- **Poli** has no manual: its parameter meanings (`Xmod`, what `Sub -> Filter` Bypass and Thru do) are inferred from names and the pack page. The option lists are now known from the reference dump (`Voicemode` Poly, Mono, Unison; `Sub -> Filter` Bypass, Thru; `Chorus` -, A, B, C), as are the Meld and Granulator III parameter names.
- **ERB below 100 Hz.** The Glasberg-Moore fit is stated for 100 Hz-10 kHz; the 31-37 Hz widths at 55-110 Hz are extrapolations, and the low-interval limits in 5.3 are one-ERB arithmetic on the fundamentals, not a measured roughness model (complex tones help intervals whose harmonics coincide, such as fifths). The Wikipedia ERB page labels the formula's output unit as kHz; the formula only gives sensible values in Hz.
- **Beat-rate perception boundaries** (slow swell, chorus-like pulsing, roughness, two pitches) are described qualitatively by [Wikipedia](https://en.wikipedia.org/wiki/Beat_(acoustics)); the Hz boundaries used here are convention. Psychoacoustic literature gives peaks (about 4 Hz fluctuation, about 70 Hz roughness) that could not be re-checked in this session.
- **Learning Synths** lessons could not be read (JavaScript only); Ableton's blog posts for Drift, Meld and Granulator III are promotional and carry little numeric detail, so their parameter-level facts come from the manual and the tool dumps.
