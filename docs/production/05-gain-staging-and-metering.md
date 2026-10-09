# Gain staging and metering in Live 12

Digest 05 of `docs/production/`. Researched 2026-10-08 for Live 12.4.6 Suite driven through AbletonMCP, for agents that cannot hear.
Mixing technique is in [06-mixing.md](06-mixing.md); mastering and delivery targets are in
[07-mastering-and-loudness.md](07-mastering-and-loudness.md); judging audio without ears is in
[11-listening-without-ears.md](11-listening-without-ears.md); device parameters are in
[12-live-devices-reference.md](12-live-devices-reference.md).

## If you remember five things

1. **Live cannot clip internally, but devices still care about level.** The engine is 32-bit float with 64-bit
   summing at mix points, so a track "in the red" is not distorted inside Live. Clipping happens at the interface, in
   fixed-point exports and inside any plug-in that clips internally. What level changes is how *nonlinear* devices
   behave: Saturator, Drum Buss, Roar, Pedal, Amp, Compressor, Glue Compressor, Limiter and every analogue-modelled
   plug-in. Linear devices (Utility, EQ Eight, delays, reverbs) do not care.
2. **Choose one working-level convention and keep it.** Sustained material averaging about -18 dBFS RMS, tracks
   peaking about -18 to -10 dBFS, groups peaking at -8 or lower, Main peaking -6 to -3 dBFS with nothing on it that
   squashes. The exact figure matters less than consistency.
3. **Fix level at the source, balance with faders.** Use clip gain, the instrument's own volume or a Utility at the head
   of the chain. In Live the fader comes *after* the device chain, so pulling a fader down never un-overdrives a
   Saturator upstream.
4. **Loudness numbers describe a finished programme, not a stem.** LUFS, true peak, LRA and PLR belong to the Main or to
   a stem *sum*. Per-stem LUFS targets and per-stem limiters are exactly what failed on 2026-10-08. Remember
   `LUFS = true peak - PLR`: a sum whose PLR is 13 dB or less reaches -14 LUFS under -1 dBTP with no limiter at all.
5. **Live's meters are for eyes; the agent reads numbers through tools.** Live shows peak and RMS (post-fader). As far as
   the manual and release notes show, it has no native LUFS, true-peak or correlation meter through 12.4.x. `get_meters`
   returns peak only, held 1 s, only while the transport plays. Everything else comes from `bounce` + `analyze_audio` (or
   `meter`). Compare A and B only after matching loudness, because the louder one tends to win a short listen.

---

## 1. Why gain staging still matters in a floating-point DAW

### 1.1 What Live's engine does

Ableton states that Live processes at 32-bit internal precision and sums at 64-bit double precision at individual mix
points (clip inputs, return inputs, the Main track, Racks), and that tracks can be driven far past 0 dB (into the red)
without internal clipping; levels above 0 dB become a problem only when the signal reaches physical outputs, the Main
track feeding them, or an exported file
([Mixing](https://www.ableton.com/en/manual/mixing/), [Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/)).
Sound On Sound puts the theoretical dynamic range of 32/64-bit float at roughly 1,500 dB, so no resolution is lost at
low levels either ([SOS, Gain Staging In Your DAW Software](https://www.soundonsound.com/techniques/gain-staging-your-daw-software)).
For the same reason Ableton recommends rendering at 32-bit float without dither unless you are producing the final
lower-bit-depth file.

### 1.2 So why bother

Sources agree on the reasons and disagree on how much they matter:

- **Nonlinear devices change tone with input level.** SOS reports that well-known analogue-modelling plug-ins audibly
  suffer when overloaded, and that many presets quietly add a dB or two of output gain. iZotope warns that an analogue
  modeller pushed too hard still sounds distorted even if you turn a later fader down
  ([iZotope, gain staging](https://www.izotope.com/en/learn/gain-staging.html)). Slate Digital and Sonarworks describe
  modelled gear as calibrated around -18 dBFS (average level) because that is where analogue hardware sat, and say
  saturation grows above that ([Slate Digital](https://slatedigital.com/what-is-gain-staging-and-why-your-mix-sounds-muddy/),
  [Sonarworks](https://www.sonarworks.com/blog/learn/gain-staging-guide); both are vendor blogs: moderate evidence).
- **Meters stay readable and comparisons stay fair.** SOS's own answer to "-6 or -18?" says a float DAW does not
  *require* gain staging, but chaotic levels make meters useless as reference, and swapping or comparing processors is
  easier when each sees the same input
  ([SOS Q&A](https://www.soundonsound.com/sound-advice/q-should-gain-stage-6dbfs-or-18dbfs)).
- **The end of the chain is not float.** Converters, hybrid outboard gear and 16/24-bit exports clip. SOS notes that
  professional converters put 0 dBFS at about +24 dBu, so mixing hot (average levels around -6 dBFS) hands analogue gear
  signals roughly 18 dB hotter than it was designed for, which sounds hard, brittle and strained.
- **Dissent.** Pro Audio Files argues digital is linear, so level changes alter only noise floor and clipping risk, and
  that the red clip light in a DAW channel often does not mean real clipping
  ([Pro Audio Files](https://theproaudiofiles.com/gain-staging/), a transcript-style post: treat as practitioner
  opinion). That is true for *linear* processing. It is not true for the nonlinear devices listed next.

### 1.3 Which Live devices are level-dependent

| Level-dependent (audit input and output level) | Mostly level-independent |
| --- | --- |
| Compressor, Glue Compressor, Multiband Dynamics, Gate, Limiter (thresholds are absolute dBFS) | Utility, EQ Eight, EQ Three, Channel EQ (their Output or Gain controls are only trim) |
| Saturator, Drum Buss (Trim, Drive), Roar, Pedal, Overdrive, Amp, Dynamic Tube, Erosion, Redux, Vinyl Distortion | Reverb, Hybrid Reverb, Delay, Auto Pan-Tremolo |
| Auto Filter circuits with drive; instrument filter drive, unison and saturation stages (check each instrument) | Chorus-Ensemble and Echo, as long as Warmth, Input distortion, Noise and Wobble are off |
| Chorus-Ensemble Warmth, Echo Input distortion, any analogue-modelled VST/AU | Spectrum, Tuner |

Drum Buss has a **Trim** control that attenuates the input before its compressor and drive stages
([Ableton manual, Drum Buss](https://www.ableton.com/en/manual/live-audio-effect-reference/)): use it, not the fader, to
set how hard the drive stage is hit. Glue Compressor's soft clip (`Peak Clip In`) caps its output at about -0.5 dB and distorts whenever it
is active, and its Peak Clip LED goes red above 0 dB ([Glue Compressor, Live manual](https://www.ableton.com/en/live-manual/11/live-audio-effect-reference/)).

> **For an agent: level audit before touching dynamics or drive.**
> For each track with a nonlinear device, fire the loudest section, then read `get_meters(tracks=[...])` several times
> across 8-10 s and take the maximum of `peak_db`, or (better, exact) `bounce(stems=[track])` and read `peak_dbfs` from
> `get_bounce_status`. Check the *loudest chord or hit*, not a single test note: a pad with six stacked voices peaks well
> above one note and overloads a Saturator that looked fine on a probe. Then record the level *before* and *after* each
> nonlinear device (see section 3) and make them match unless the change is intended.

---

## 2. Typical working levels

There is no standard. These are the figures the sources give, then a synthesis.

| Source | Advice |
| --- | --- |
| [SOS, Gain Staging In Your DAW Software](https://www.soundonsound.com/techniques/gain-staging-your-daw-software) | Loudest track peaks -12 to -18 dBFS (sample peak); channel peaks generally no higher than -8 to -10 dBFS; leaves ~20 dB headroom, as analogue consoles do at 0 VU |
| [SOS, Mixing Essentials](https://www.soundonsound.com/techniques/mixing-essentials) | Set track levels so they peak around -10 dB to preserve headroom |
| [Attack Magazine, gain staging](https://www.attackmagazine.com/technique/tutorials/how-gain-staging-in-your-daw-can-help-keep-your-mix-clean-and-punchy/) | Track peaks -15 to -18 dBFS; master no hotter than -3 dB so the mastering engineer keeps 3-6 dB; keep programmed velocities below 127 to avoid stray peaks |
| [iZotope, gain staging](https://www.izotope.com/en/learn/gain-staging.html) | -18 dBFS average is the sweet spot for analogue-modelled plug-ins; -20 dBFS when stacking many processors |
| [Sonarworks](https://www.sonarworks.com/blog/learn/gain-staging-guide) | Nominal -18 to -12 dBFS; peaks near -10 or lower |
| [Pro Audio Files](https://theproaudiofiles.com/gain-staging/) | Average above -20 dBFS, peaks no hotter than -10 dBFS |
| [SOS Q&A](https://www.soundonsound.com/sound-advice/q-should-gain-stage-6dbfs-or-18dbfs) | 0 VU may be calibrated to -20, -18 or -16 dBFS; consistency matters more than the number; the author uses -18 average with a peak lamp at -6 |
| Ableton Forum threads ([example](https://forum.ableton.com/viewtopic.php?t=147067)) | Leave 6 dB on the Main, -12 to -6 peaks for mastering. Forum evidence: weak |

**Synthesis (use as defaults, not laws).**

| Point in the session | Sample peak | Average | Why |
| --- | --- | --- | --- |
| End of a *sustained* track's chain (pad, drone, arp, bass) | -18 to -10 dBFS | about -24 to -18 dBFS RMS | Analogue models are happiest near -18 RMS; peaks leave room for the sum |
| End of a *percussive* track's chain (kick, snare, perc) | -12 to -6 dBFS | far below peak (crest 12-20 dB) | Short transients: calibrate by peak, not RMS |
| Group / bus output | at most -8 dBFS | n/a | Sums add up (section 4) |
| Main (pre-mastering) | -6 to -3 dBFS sample peak | roughly -20 to -14 dBFS RMS depending on density | Leaves mastering headroom; no limiter whose job is loudness |
| Return tracks | follow their sources | n/a | A 100 % wet return can exceed its dry source; set it by send level |

Two practical points the sources imply but do not say outright:

- **RMS and peak calibrate different things.** An "-18 dBFS" convention is an *average* level into an analogue model.
  A kick whose RMS is -18 dBFS, with a crest factor of 12-20 dB, would peak between -6 and +2 dBFS. Calibrate sustained
  sources by average and cap their peaks; calibrate drums by peak.
- **Faders should live in a sane range.** SOS suggests setting channels with faders at or around -6 dB to keep fader
  resolution for balancing. A fader at -40 dB means the source is far too hot, and a nonlinear device before it
  probably sees too much level.

> **For an agent: a per-stem level report.**
> 1. `bounce(stems="all", include_returns=True, name="levels")`, poll `get_bounce_status(wait=50)` until `done`.
>    Each file gives `peak_dbfs`.
> 2. For each stem file, `analyze_audio(path=...)` and read `levels.sample_peak_dbfs`, `levels.rms_dbfs`,
>    `levels.crest_factor_db`, `levels.clipped_samples`, `stereo.correlation`.
> 3. Compare with the table above. Stems are recorded from each track's Post Mixer tap (the bounce code), i.e. *after* its fader and pan
>    law, so a stem peak includes the fader and the pan boost.
> 4. Red flags: any `clipped_samples` > 0; sample peak above -3 dBFS on a non-kick stem; crest below ~6 dB on a
>    sustained stem (it is being clipped, limited or heavily saturated); crest below ~10 dB on a kick (squashed);
>    `dc_offset` above 0.001; `silent: true`.
> 5. Fix with `set_device_parameters(track, "Utility", {"Output": "-4 dB"})` (Utility's gain is named `Output` in 12.4.6) at the head of the chain, the instrument's volume,
>    or `set_clip(..., gain_db=...)` for audio clips (range -inf to +24 dB). Re-bounce only the track you changed.
> 6. Do **not** normalise every stem to the same loudness or the same peak: a bass and a hat do not share a target.

---

## 3. Where level can be changed in Live, and in what order

Signal flow of an audio track, as documented by Ableton and the Live Object Model docs:

1. **Clip gain** (audio clips, Sample box; and the Clip Gain envelope in Clip Envelopes) acts *before* the device chain;
   the Track Volume modulation envelope acts on the post-effect signal
   ([Clip Envelopes](https://www.ableton.com/en/manual/clip-envelopes/)). `set_clip(gain_db=...)`, -inf to +24 dB.
2. **Device chain**, left to right. Instruments have their own output/volume controls. **Utility** is the clean trim:
   Gain (the parameter is `Output`) from -inf to +35 dB, Width (`Stereo Width`, 0-200 %), Mono, Bass Mono (`Bass Mono` and `Bass Freq`, 50-500 Hz, 120 Hz by default), Phase (`Left Inv`, `Right Inv`), `DC Filter`
   ([Utility, Live manual](https://www.ableton.com/en/manual/live-audio-effect-reference/); read from the official page
   through a search excerpt, as the reference page is too long to fetch whole).
3. **Mixer**: volume fader (up to +6 dB), then pan. Live's pan law is constant power with 0 dB at centre and a **+3 dB
   boost** for a signal panned fully left or right
   ([Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/)); Utility's Width control counters it.
4. **Sends** tap the post-mixer signal unless that return's Pre/Post switch is set to Pre.
5. **Track output meter.** The Live Object Model docs describe the output meter as taken behind the mixer device, so it is
   post-fader and post-pan ([Live API docs in this repo](../reference/live_api_12.4.6.md)).
6. **Group / Main tracks**: the same chain-then-fader structure. A Limiter on the Main sits *before* the Main fader, so
   lowering the Main fader does not reduce what the Limiter sees.

Consequences:

- **Gain-stage a nonlinear device with the gain stage *before* it** (clip gain, instrument volume, Utility, the device's
  own input/Trim), never with the fader after it.
- **Keep unity through each device.** iZotope's and Attack's working rule: roughly the same level out as in. After an EQ
  boost, trim the EQ's `Output`; after a Compressor, set `Output` (or switch on `Makeup`) so the average level matches
  ([iZotope](https://www.izotope.com/en/learn/gain-staging.html),
  [Attack](https://www.attackmagazine.com/technique/tutorials/how-gain-staging-in-your-daw-can-help-keep-your-mix-clean-and-punchy/)).
  Compressor's Makeup button compensates automatically when threshold and ratio change; that is a rough match, not
  a loudness match.
- **Pan law matters for metering.** A hard-panned mono source reads 3 dB higher in its channel; in a mono sum it falls
  about 3 dB below the same source panned centre ([SOS, Mike Senior on panning and mono](https://www.soundonsound.com/sound-advice/q-are-there-any-panning-rules-maintaining-mono-compatibility)).
- **Pre-fader level from a post-fader meter.** Because the meter is post-fader and post-pan, a track's level at the end of
  its device chain is about `peak_db - volume_db - pan_boost`. With Ableton's constant-power, sinusoidal law the louder
  channel gains roughly `20 log10(sqrt(2) cos(pi/4 (1 - |pan|)))` dB: 0 at the centre, about +2.3 dB at 50 % and +3 dB
  at the hard sides (derived from Ableton's description of the law; verify with a test tone). Use this to judge the
  *source* level; do not "fix" it with the fader.
- **Use Utility rather than a fader to move a whole chain's level without breaking automation.** iZotope lists
  a Utility trim as one of four ways to bring down a hot bus, with the benefit that it preserves fader automation.

> **For an agent: which tool for which gain stage.**
>
> | Job | Call |
> | --- | --- |
> | Trim a track's input to its device chain | `add_device(track, "Utility", position=0)`, then `set_device_parameters(track, "Utility", {"Output": "-6 dB"})` (on a MIDI track the Utility has to follow the instrument: read the returned position **[verify]**) |
> | Audio clip level | `set_clip(track, slot=..., gain_db=-3)` |
> | Balance | `set_mixer(track, volume_db=-2)` (aim for -12 to 0 dB) |
> | Send level | `set_mixer(track, sends={"A": -12})` |
> | Read post-fader peaks | `get_meters(tracks=[...])` |
> | Group sum | `create_bus(name, sources)`; mix it like a track |
>
> A Utility placed *after* a distortion trims its output only. If you want less drive, put the trim *before* the
> distortion. Add a Utility at the head of every track you will gain-stage, named so you can find it.

---

## 4. Headroom arithmetic

Use these to predict what a bus will do before you listen.

| Fact | Value | Source |
| --- | --- | --- |
| Peak minus RMS of a full-scale sine | 3.01 dB | [ITU-R BS.1770-5](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf) (a 0 dBFS 997 Hz sine in one channel reads -3.01 LKFS); [Wikipedia, crest factor](https://en.wikipedia.org/wiki/Crest_factor) |
| Crest factor of triangle and sawtooth | 4.77 dB | Wikipedia, crest factor |
| Crest factor of a square wave | 0 dB | Wikipedia, crest factor |
| N equal-level *uncorrelated* signals sum | +10 log10(N) dB (8 tracks: +9 dB) | arithmetic |
| N equal-level *identical* signals sum | +20 log10(N) dB (8 tracks: +18 dB) | arithmetic |
| Pan law in Live | +3 dB at the hard sides | Audio Fact Sheet |

An example: eight tracks, each peaking -18 dBFS. If they are unrelated and dense, the bus peaks at roughly -9 dBFS (less if
their transients never coincide); if they are all copies of the same kick, it peaks at 0 dBFS. Layers that share a waveform (octave-doubled saws, a bass layered on its own sub)
behave like the second case in the low end. This is why a stem "that was fine" overloads once layered, and why group
output should be checked, not assumed.

### 4.1 Loudness targets and per-stem limiters: the arithmetic of the 2026-10-08 failure

`LUFS_integrated = true_peak_dBTP - PLR`. Hitting a target means choosing where the *peaks* go, not stamping a limiter
on every part.

- Project requirement: sum at **-14 LUFS** and at most **-1 dBTP**. That allows a PLR of up to **13 dB** with no
  limiting. If the dense sum's natural PLR is 11 dB, -14 LUFS puts the true peak near -3 dBTP and no limiter is needed.
- If the natural PLR is 15 dB, -14 LUFS would peak at about +1 dBTP. The choices are: one shared gain of about -2 dB
  (sum sits at -16 LUFS), or *one* limiter on the sum removing about 2 dB of peak. Both are one decision at one point.
- What went wrong: True Peak limiters on **every** stem, each driven about +12 dB into a -14 dB ceiling. How much
  each limiter removed was set by that stem's crest factor and the drive, not by musical judgement, and with 12 dB of
  drive any stem whose peaks sit more than a few dB above its average is being flattened hard, on every stem at once.
  SOS suggests limiters only for catching brief peaks of 2-3 dB
  ([SOS, mix compression](https://www.soundonsound.com/techniques/how-when-use-mix-compression)).
  Attack Magazine describes limiters on tracks and master as a *safety net* while pushing distortion hard, not as the
  loudness tool ([Attack, Organised Chaos](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/)).
- Correct procedure: set stem balance for how it sounds (see 06), keep each stem's peaks in the table of section 2, sum
  them, *measure the sum*, then apply **one** shared gain (or one gentle limiter, <= 2 dB reduction) to the sum. A game
  pipeline that applies one periodic 2-bar gain curve per tempo to every stem, then one trim so the mean A/B sum lands at -14.6 LUFS
  (the game repo's `tools/music/cut_stems.py`), does this correctly (see [10-game-audio-adaptive-music.md](10-game-audio-adaptive-music.md)).

---

## 5. Monitoring level and equal-loudness effects

The ear is less sensitive to bass and treble at low playback levels, and the curves flatten as level rises (the
equal-loudness contours of Fletcher-Munson, Robinson-Dadson and ISO 226:2003;
[Wikipedia](https://en.wikipedia.org/wiki/Equal-loudness_contour)). Consequences:

- **Louder sounds better in short comparisons.** Bob Katz notes that of two identical programmes at slightly different
  loudness, the louder one often seems better ([Katz, K-System](https://www.digido.com/portfolio-item/level-practices-part-2/)).
  iZotope names the same trap in the "smiley-face" EQ: a bass and treble boost sounds more powerful and balanced at
  low volume but costs dynamic range and adds distortion ([iZotope, psychoacoustics](https://izotope.com/en/learn/psychoacoustics-how-perception-influences-music-production)).
- **Calibrate, and keep it constant.** Katz's K-System ties metering to monitor gain: pink noise at -20, -14 or -12 dBFS
  RMS (K-20, K-14, K-12) per channel should read **83 dB SPL**, C-weighted, slow; K-20 for wide-dynamics material, K-14
  for most pop and rock. Sonarworks cites 83 dB SPL, or 78-80 dB SPL in small rooms; Wikipedia's summary of the
  contours puts typical calibrated professional mixing around 85 dB SPL. Katz warns that a programme mixed loud will
  sound bass-shy when reproduced quieter, and recommends K-20 metering (20 dB of headroom over the average) while mixing to
  encourage clean mixes and discourage premature compression.
- **Check at more than one level.** SOS suggests listening at low monitor levels to judge balance and from outside the
  room, then checking on other systems. iZotope warns that long loud sessions make every instrument seem upfront, so the
  mix falls apart when the level drops, besides damaging hearing.

> **For an agent.** You cannot hear the monitor level, but you can avoid corrupting the human's comparison:
> - **Never change the Main fader, `cue_volume_db` or any shared gain between two auditions** unless you say so. If a
>   change needs a level compensation, put it on the *candidate* (a Utility on its track), not on the Main.
> - Give the human **loudness-matched** A and B (section 7.2), labelled, and say what changed and by how much.
> - If the human reports "too bass-heavy" or "thin", ask at what monitor level and on which system before reaching for
>   an EQ (the level, not the mix, may be the cause).

---

## 6. The meters

### 6.1 Summary table

| Meter | Measures | Window | Strength | Blind spot | In Live | Agent access |
| --- | --- | --- | --- | --- | --- | --- |
| **Sample peak** (dBFS) | highest sample | instant | clipping detection | misses inter-sample peaks | track meters (dark bar, peak number) | `get_meters` (`peak_db`); bounce `peak_dbfs`; `analyze_audio.levels.sample_peak_dbfs` |
| **True peak** (dBTP) | peak of the reconstructed waveform, 4x oversampled | instant | what a DAC or codec will do | not loudness | none (Limiter has a *True Peak* mode, 12.1) | `analyze_audio.loudness.true_peak_dbtp`; `meter(source="live")` |
| **RMS** (dBFS) | average power | file or short window | quick level, easy maths | not perception-weighted | track meters (bright bar) | `analyze_audio.levels.rms_dbfs` |
| **Loudness M / S / I** (LUFS) | K-weighted, gated power | 0.4 s / 3 s / whole programme | tracks perceived loudness | needs a programme-like signal | none | `analyze_audio.loudness`: `integrated_lufs`, `short_term_max_lufs`, `momentary_max_lufs`, `loudness_curve`; `meter` |
| **Loudness range** (LU) | spread of short-term loudness | whole programme, >= 1 min | macro dynamics | meaningless on short loops | none | `loudness.loudness_range_lu` |
| **PLR / PSR** (dB) | true peak minus integrated / short-term loudness | programme / 3 s | spots over-limiting | no absolute target | none | compute `true_peak_dbtp - integrated_lufs`; `profile.plr_db` in `compare` |
| **Crest factor** (dB) | sample peak minus RMS | whole file | per-stem dynamics | unweighted | none | `levels.crest_factor_db` |
| **Correlation, width** | L/R similarity; side / mid ratio | whole file | mono safety, image | one number per file | none | `stereo.correlation`, `stereo.width`; `mono_sub_loss_db` in the listening loop |
| **Spectrum** | energy by frequency | block of samples | balance, resonances | misleading if read as a target | Spectrum device, EQ Eight analyser | `analyze_audio.spectrum` (5 bands), third-octave in `compare` |

### 6.2 Peak, true peak, RMS

**Sample peak versus true peak.** ITU-R BS.1770 explains why a sample-peak meter can mislead: the real peak of a
sampled signal often falls *between* samples. A tone at a quarter of the sample rate can under-read by 3 dB; real
transients with high-frequency content can commonly under-read by several dB. A true-peak meter oversamples (4x at
48 kHz, i.e. 192 kHz) before taking the maximum, leaving a worst-case under-read of 0.69 dB at 4x
([BS.1770-5, Annex 2](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf)).
The consequence: a file with -0.1 dBFS sample peaks can reconstruct above 0 dB in a DAC or lossy codec. Spotify therefore
asks for -1 dBTP (and -2 dBTP if the master is louder than -14 LUFS)
([Spotify](https://support.spotify.com/us/artists/article/loudness-normalization/)); EBU R 128 also caps true peak at
-1 dBTP ([EBU R 128](https://tech.ebu.ch/docs/r/r128.pdf)). SOS argues sample-peak meters are of little use if you keep
headroom, which is right *during mixing*; true peak matters at the end.

**RMS** is average power; crest factor is peak minus RMS. A pure sine is 3.01 dB, a saw 4.77 dB, a square 0 dB, so a
sustained saw-based pad (the target character in this project) has a *low* crest factor. Stacked, detuned saws approach
noise-like statistics, so over a long file expect somewhere around 8-12 dB (rule of thumb, not sourced: measure your
own), and treat a value far below ~6 dB as a sign of clipping, limiting or heavy saturation. A kick or snare is the
opposite. Interpret crest only against the same kind of source, and best as a **before/after difference** around one
device.

### 6.3 LUFS, the EBU windows, and LRA

LUFS (= LKFS) comes from ITU-R BS.1770: a two-stage K-weighting filter (a shelf modelling the head, then a high-pass),
mean-square power per channel, channel-weighted summation, then gating on 400 ms blocks with 75 % overlap using an
absolute gate at -70 LKFS and a relative gate 10 LU below the ungated result
([BS.1770-5](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf)).
EBU Tech 3341 fixes the three time scales
([Tech 3341](https://tech.ebu.ch/docs/tech/tech3341.pdf)):

- **Momentary (M):** 0.4 s sliding window, no gating. Jumps with every kick.
- **Short-term (S):** 3 s sliding window, no gating. The most useful reading of a section's loudness for a mix move.
- **Integrated (I):** gated, over the programme.

1 LU equals 1 dB. EBU's broadcast target is -23.0 LUFS (R 128, tolerance +/-0.5 LU, true peak <= -1 dBTP); streaming
services use their own: Spotify's reference is -14 LUFS (Quiet -19, Loud -11)
([Spotify](https://support.spotify.com/us/artists/article/loudness-normalization/)). These are *delivery* numbers. Do not
mix to them stem by stem.

A calibration check from Tech 3341: a stereo 1 kHz sine with its peak at -18 dBFS in both channels should read -18.0
LUFS; the same tone in one channel reads 3 dB lower (BS.1770: 0 dBFS in one channel reads -3.01 LKFS). The repo's
meter test uses the equivalent -18 dBFS tone recorded at -21.01 dBFS RMS
([listening-loop calibration](../listening-loop-calibration.md)).

**Loudness range (LRA, Tech 3342)** is the 10th to 95th percentile spread of short-term loudness after a relative gate 20 LU
below the mean, so a short loud event or a fade-out does not dominate it
([Tech 3342](https://tech.ebu.ch/docs/tech/tech3342.pdf)). EBU does not recommend it for programmes shorter than one
minute (R 128 footnote). **Loops of 8-32 bars have a meaningless LRA; do not report or chase it for stems.**

LUFS is not RMS. K-weighting rolls off deep bass and lifts the highs, so two mixes with the same RMS can differ in
LUFS: sub-heavy material reads lower, bright material higher. Never swap one for the other.

### 6.4 PLR, PSR, crest factor and "dynamic health"

- **PLR** = true peak minus integrated loudness (`profile.plr_db` in the repo's `compare`). **PSR** compares the peak with
  *short-term* loudness, so it follows moment-to-moment dynamics. Meterplugs' Dynameter uses colour zones to show
  when material is over-compressed and offers platform-oriented presets; the vendor page gives no numeric thresholds
  ([Meterplugs Dynameter](https://www.meterplugs.com/dynameter)). I found no authoritative numeric PLR table. Treat any
  rule such as "keep PLR above X" as folklore; **take your target from the producer's own references**
  (`ref(action="list")` stores `plr_db`, `crest_db`, `lra`).
- Because streaming platforms normalise loudness, pushing PLR down no longer buys playback level on those platforms
  ([Production Advice, PLR](https://productionadvice.co.uk/plr/)); it only costs punch.
- Loudness-war background and the physical damage of over-compression (squashed transients, listener fatigue, clipping):
  [Wikipedia](https://en.wikipedia.org/wiki/Loudness_war), [Katz](https://www.digido.com/portfolio-item/level-practices-part-2/).

### 6.5 Correlation, width, mono safety

- **Correlation** runs from +1 (identical channels) through 0 (unrelated) to -1 (polarity-inverted). Healthy stereo mixes
  mostly sit between 0 and +1; a brief negative blip is harmless, a sustained negative reading means out-of-phase
  content and mono problems ([Craig Anderton](https://craiganderton.org/all-about-audio-phase-and-correlation-meters/)).
- **Width** in this repo is side RMS divided by mid RMS: 0 is mono, 1 means side and mid carry equal energy, and a
  polarity-inverted pair is capped at 1000 in the listening loop (`analyze_audio` on a file reports null for it). The producer's references measure about **0.75-0.95 above 200 Hz** for the
  background synth, which is wide but not out of phase.
- **Low-end mono safety.** iZotope advises collapsing everything below about 100-150 Hz to mono, because low frequencies
  are barely directional and out-of-phase low end cancels in mono and on club systems
  ([iZotope, mono vs stereo](https://www.izotope.com/en/learn/mono-vs-stereo.html)). The repo's `mono_sub_loss_db`
  measures what the mono sum loses below 120 Hz (identical channels lose 0 dB, decorrelated equal-level channels lose
  3 dB, an inverted pair loses everything); its tolerance is **1 dB**.
- **Live has no correlation meter or goniometer** in the stock mixer. Utility's Width, Mono and Bass Mono *act*, they do not *show*.

### 6.6 Spectrum analysers

Live gives you a Spectrum device and the EQ Eight **Analyze** display (a spectrum drawn behind the curve)
([EQ Eight, Live manual](https://www.ableton.com/en/manual/live-audio-effect-reference/)). Reading them:

- **FFT size trades low-frequency resolution against speed.** FabFilter's analyser offers 1,024 to 8,192 points; larger gives
  better bass detail but updates slower ([FabFilter Pro-Q](https://www.fabfilter.com/help/pro-q/using/analyzer)).
- **Tilt.** Music has more energy at low frequencies, so a raw spectrum slopes steeply. FabFilter's default 4.5 dB per
  octave tilt gives a natural-looking display that resembles how loudness is perceived, so a typical mix looks roughly
  flat. A flat display therefore means a *pink-ish* mix, not white noise.
- **Spectrum is a diagnostic, never a target.** The repo's own checks treat band balance and phone-survival numbers as
  information, not pass or fail. A full-mix reference spectrum says nothing about what one pad should look like; the
  2026-10-08 session ranked pads by distance to full-mix references and picked a hollow, airy preset.
- `analyze_audio.spectrum` reports five broad bands (sub below 60 Hz, low 60-250, low-mid 250-2,000, high-mid 2,000-6,000,
  high above 6,000), each as percent and dB. The listening loop adds third-octave levels.

### 6.7 What Live provides natively, and what it does not

| Provided | Not provided (as far as the manual and the 12.x release notes show) |
| --- | --- |
| Track meters showing peak and RMS together ([Mixing](https://www.ableton.com/en/manual/mixing/)); red above 0 dB; resettable peak readout and dB scale when the mixer is made taller | LUFS (M/S/I), LRA, true-peak meter |
| Spectrum device, EQ Eight analyser, Compressor/Glue/Limiter gain-reduction displays | Correlation meter, goniometer, spectrogram |
| Live 12 Limiter: updated metering, Soft Clip and True Peak modes, Mid/Side (12.1) | Oscilloscope, PLR/crest displays |
| Mixer now in Arrangement View (Live 12) | |

For the human, third-party meters fill the gap: Youlean Loudness Meter 2 (free: LUFS I/M/S, true peak, LRA, PLR, DR),
TBProAudio dPMeter5 and others ([Production Expert's list](https://www.production-expert.com/production-expert-1/free-metering-and-loudness-plugins-for-broadcast-and-streaming-2026)),
or Max for Live devices such as Flufs and Swiss Army Meter
([Flufs](https://lame.buanzo.org/max4live_blog/a-deep-dive-into-flufs-the-accessible-loudness-meter-for-all-musicians.html),
[Swiss Army Meter listing](https://maxforlive.com/library/device/9055/swiss-army-meter)). Put such a meter on the Main only if it is a
pure meter with no processing; the listening loop's sum-null check flags any unexplained processing there.

> **For an agent: which tool gives which number.**
>
> | Question | Tool |
> | --- | --- |
> | Is this track hot right now? | `get_meters(tracks=["Pad"])`: `peak_db` (max of L/R, post-fader, 1 s hold), `over_0db`. Raw 0..1 maps to dBFS as `76 * raw - 70`, accurate to 0.01 dB; moves only while playing |
> | Exact peak of a track over a section | `bounce(stems=[...], start, end)` then `get_bounce_status` -> `peak_dbfs` |
> | Loudness, true peak, crest, correlation, width, bands of a file | `analyze_audio(path=..., sections="locators")` |
> | What the Mac is playing right now, incl. integrated loudness and true peak | `meter(seconds=10, source="live")` (start playback first, e.g. `fire_scene`) |
> | A/B two states, loudness-matched | `capture(note=...)` then `compare("latest", "best")` (spectral metrics are loudness-matched) |
> | Against the producer's references | `compare("latest", "refs")`; `ref(action="list")` |
>
> `get_meters` is a *peak* meter: do not infer loudness or balance from it. Short LRA, crest and loudness numbers from a
> 4-bar bounce are noisy; use >= 8 s for short-term loudness, >= 1 min for anything involving LRA.

---

## 7. Protocols for agents

### 7.1 Gain-stage a set (start of a mixing session)

1. `get_mixer()` and `get_devices(track)` per track: list faders, pans, sends, and every nonlinear device (section 1.3).
   Note anything the producer approved: do not change those *sounds*, only the levels around them.
2. Add a Utility at the head of each track you may trim (named "Trim"), gain 0 dB.
3. Bounce a representative loud passage with stems; run the per-stem report (section 2).
4. Bring each stem into range using the Utility, instrument volume or clip gain; leave faders near unity.
5. Check group outputs (section 4) and the Main: aim at sample peak -6 to -3 dBFS, true peak <= -3 dBTP, no clipped
   samples. Keep the Main chain empty of loudness processors if the project measures stem sums.
6. Save a baseline: `capture(note="gain-staged baseline")` and `takes(action="keep", take=<id>)` so every later change has
   something to be compared with and restored to.

### 7.2 Loudness-matched A/B for the human

1. **Name the pair.** Duplicate the track or chain being changed (`duplicate_track`); call them "Pad A (approved)" and "Pad B
   (more reverb)". Change one thing.
2. **Measure both on the same bars**: bounce each soloed over the same range, then `analyze_audio(path, sections=[...])`
   and read `short_term_max_lufs` or `integrated_lufs` over a section of at least 8 s.
3. **Match.** Put the difference on a Utility gain (`Output`) on the louder one: `gain = LUFS_A - LUFS_B`. Re-measure; accept within
   0.2 LU (0.3 LU at most). The repo's repeat-capture noise floor for integrated loudness is 0.07 LU, so matching much tighter is pointless.
4. **Tell the human** which is which, what changed, and what offset was applied. Mute one and unmute the other (never
   both). Switch quickly: auditory memory is short.
5. **Keep A until the human chooses.** Delete the loser only after a clear answer.
6. For device settings, Live 12.3 added **Compare A/B** inside a device (toggle between two states with a shortcut);
   `set_device(compare_b=...)` exposes it. It does *not* match loudness: still match levels.

### 7.3 Mono and phase check

- After any width, chorus, delay or Haas change: `analyze_audio` the bounce and read `stereo.correlation` (watch for a
  sustained fall toward or below 0) and `stereo.width`. For the sub, the listening loop's `audio.mono_sub` check
  (`mono_sub_loss_db` <= 1 dB below 120 Hz) catches an out-of-phase bass; the calibration run shows it detects a
  planted sub out of phase between channels.
- The human can press **Mono** on a Utility on the Main and listen; the agent should offer that instead of leaving a
  Utility on the Main.

### 7.4 Troubleshooting

| Symptom | Likely cause | Check or fix |
| --- | --- | --- |
| Compressor "does nothing" at a sensible threshold | Input well below threshold | Raise level *before* the compressor (Utility, instrument volume); thresholds are absolute |
| Saturator is much harsher on chords than on a test note | Chord peaks hit the curve harder | Audit the loudest chord; lower Drive or trim before it |
| "Everything got bigger" after a processor | It added level; louder sounds better | Match loudness (7.2) before judging |
| Main meter red, "sounds fine" | Fine inside Live, but export and interface clip | Bounce, read `samples_over_full_scale` and `clipped_samples`; fix at the sum |
| A fader is far below -20 dB | Source too hot | Trim at the source; revisit what the preceding devices saw |
| A send effect louder than the dry sound | 100 % wet return plus a hot send | Lower the send (`set_mixer(sends=...)`), not the return fader, so the return's own ducking and EQ still see sensible level |
| Stem sum louder than the sum of expectations | Correlated layers add at 20 log N | Check group outputs; consider thinning or EQ-splitting layers |
| Dull after "level fixing" | A limiter or clipper was added to hit a number | Remove it; reduce level by one shared gain |

### 7.5 When to stop and ask the human

- Any move that changes the mix's *level relationship* by more than about 3 dB between two parts.
- Any addition on the Main, or any change that makes the Main a different loudness than before.
- When the numbers say "fine" and the producer said "garbage" (or the reverse): the producer wins; ask what is wrong
  and at what monitor level.
- When you cannot reach a loudness match within 0.3 LU or have no clean passage to measure.
- When a level fix requires replacing a sound the producer chose.

---

## Sources

**Primary and standards**

- Ableton, Live 12 manual: [Mixing](https://www.ableton.com/en/manual/mixing/), [Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/),
  [Clip Envelopes](https://www.ableton.com/en/manual/clip-envelopes/), [Live Audio Effect Reference](https://www.ableton.com/en/manual/live-audio-effect-reference/)
  (Compressor, Drum Buss, Echo, EQ Eight, Channel EQ; the page truncates before Utility, Limiter, Saturator and Spectrum), and the
  [Live 11 reference](https://www.ableton.com/en/live-manual/11/live-audio-effect-reference/) for Glue Compressor.
- Ableton, [Live 12 features](https://www.ableton.com/en/live/all-new-features/), [Live 12.1 announcement](https://www.ableton.com/en/blog/live-121-is-out-now/),
  [Live 12 release notes](https://www.ableton.com/en/release-notes/live-12/) (12.3 device A/B compare; 12.4.x lists no loudness metering).
- EBU, [R 128](https://tech.ebu.ch/docs/r/r128.pdf), [Tech 3341](https://tech.ebu.ch/docs/tech/tech3341.pdf), [Tech 3342](https://tech.ebu.ch/docs/tech/tech3342.pdf).
- ITU-R, [BS.1770-5](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf) (K-weighting, gating, true peak, sample-peak under-read).
- Bob Katz, [Level practices, part 2 (K-System)](https://www.digido.com/portfolio-item/level-practices-part-2/).
- [Spotify, loudness normalization](https://support.spotify.com/us/artists/article/loudness-normalization/).
- Repo: `docs/TOOLS.md`, `docs/spikes.md` (meter scaling), `docs/listening-loop-calibration.md`, `docs/reference/live_api_12.4.6.md`, `MCP_Server/audio/analysis.py`, `ears/profile.py`.

**Trade press and education**

- SOS: [Gain Staging In Your DAW Software](https://www.soundonsound.com/techniques/gain-staging-your-daw-software),
  [Should I gain-stage to -6 or -18?](https://www.soundonsound.com/sound-advice/q-should-gain-stage-6dbfs-or-18dbfs),
  [Mixing Essentials](https://www.soundonsound.com/techniques/mixing-essentials),
  [How & When To Use Mix Compression](https://www.soundonsound.com/techniques/how-when-use-mix-compression),
  [Panning rules and mono compatibility (Mike Senior)](https://www.soundonsound.com/sound-advice/q-are-there-any-panning-rules-maintaining-mono-compatibility).
- iZotope: [Gain staging](https://www.izotope.com/en/learn/gain-staging.html), [Mono vs stereo](https://www.izotope.com/en/learn/mono-vs-stereo.html),
  [Psychoacoustics](https://izotope.com/en/learn/psychoacoustics-how-perception-influences-music-production).
- Attack Magazine: [Gain staging](https://www.attackmagazine.com/technique/tutorials/how-gain-staging-in-your-daw-can-help-keep-your-mix-clean-and-punchy/),
  [Organised Chaos: distortion as a mix tool](https://www.attackmagazine.com/technique/tutorials/organised-chaos-distortion-as-a-mix-tool/).
- Craig Anderton, [Phase and correlation meters](https://craiganderton.org/all-about-audio-phase-and-correlation-meters/).
- FabFilter, [Pro-Q analyser](https://www.fabfilter.com/help/pro-q/using/analyzer).
- Wikipedia (definitions only): [Equal-loudness contour](https://en.wikipedia.org/wiki/Equal-loudness_contour),
  [Crest factor](https://en.wikipedia.org/wiki/Crest_factor), [Loudness war](https://en.wikipedia.org/wiki/Loudness_war).

**Weaker evidence (vendor blogs, forum, listings)**

- Slate Digital [gain staging](https://slatedigital.com/what-is-gain-staging-and-why-your-mix-sounds-muddy/); Sonarworks [gain staging guide](https://www.sonarworks.com/blog/learn/gain-staging-guide);
  Pro Audio Files [gain staging](https://theproaudiofiles.com/gain-staging/); Ableton Forum [levels and headroom](https://forum.ableton.com/viewtopic.php?t=147067);
  Ableton Forum [peak/RMS meters](https://forum.ableton.com/viewtopic.php?t=248931) (meters in Live show RMS and peak together);
  Meterplugs [Dynameter](https://www.meterplugs.com/dynameter); [productionadvice.co.uk PLR](https://productionadvice.co.uk/plr/);
  Production Expert [free meters](https://www.production-expert.com/production-expert-1/free-metering-and-loudness-plugins-for-broadcast-and-streaming-2026);
  [Flufs](https://lame.buanzo.org/max4live_blog/a-deep-dive-into-flufs-the-accessible-loudness-meter-for-all-musicians.html); [Swiss Army Meter](https://maxforlive.com/library/device/9055/swiss-army-meter).

---

## Open questions and where sources disagree

- **Peak versus average targets.** SOS wants the loudest track at -12 to -18 dBFS peak, Pro Audio Files accepts peaks to -10,
  Attack wants -15 to -18, others speak in average levels around -18 dBFS RMS. The defaults in section 2 span the range;
  none was tested against this project.
- **Does gain staging matter in float?** SOS and iZotope: yes for nonlinear plug-ins; Pro Audio Files: mostly no.
  Resolution used here: it matters for nonlinear devices and for fair comparisons, and not at all for linear ones.
- **Headroom for mastering.** 3-6 dB (Attack), -6 dBFS (forum), and "mix hot into a bus compressor" practice differ;
  see 07. For this project the delivery pipeline owns the final level.
- **PLR, crest and LRA thresholds.** No authoritative numeric table was found; use the producer's references.
- **Not verified here:** whether Live's Limiter *True Peak* mode guarantees a given dBTP under every setting; and the exact time
  constants of Live's RMS meter. Settled by the code and the 12.4.6 parameter dump: bounced stems are post-fader (the Post Mixer tap), Utility's
  `Stereo Width` runs 0-200 % and `Bass Freq` defaults to 120 Hz, and the dump lists no gain-reduction parameter for
  Compressor, Glue Compressor or Limiter (the displays are visual), so infer reduction by an A/B bounce.
