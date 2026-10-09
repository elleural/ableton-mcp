# Mastering and loudness in Live 12 (music releases and game stems)

Digest 07 for agents that make music in Ableton Live 12.4.6 through AbletonMCP. Researched 2026-10-08. You cannot hear: every number here is something to measure with `bounce` + `analyze_audio`, and every judgement about sound belongs to Fred. Related: [05-gain-staging-and-metering.md](05-gain-staging-and-metering.md), [06-mixing.md](06-mixing.md), [04-drums-and-low-end.md](04-drums-and-low-end.md), [10-game-audio-adaptive-music.md](10-game-audio-adaptive-music.md), [11-listening-without-ears.md](11-listening-without-ears.md), [12-live-devices-reference.md](12-live-devices-reference.md).

Evidence labels: **[Spec]** standard or platform document. **[Manual]** Ableton documentation. **[Eng]** working engineer or educator. **[Vendor]** a plug-in maker's guide (opinion). **[Project]** measured in this repo. **[Rule]** common practice with no single source: a starting point, not a fact.

## If you remember five things

1. **Mastering is polish, not repair.** A few small tonal corrections, light dynamics control, a final level, delivery files. A hollow pad, clashing bass or "wrong notes" are not mastering problems: they go back to the sound or the notes. [Eng]
2. **Once normalised, louder is not louder.** Spotify, YouTube, Tidal and Amazon play to about -14 LUFS and Apple Music to -16; they turn loud masters down. A -8 LUFS master is simply played 6 dB quieter than it was made, with its transients already flattened. Master for the music, then test how it will play; do not aim at a number. [Spec, Eng]
3. **One limiter, last, lightly.** On a stereo master: Glue 1–2 dB, soft clip 0.5–2 dB, Limiter 1–3 dB (4–6 dB for dense electronic), True Peak mode, ceiling -1 dBTP. Never a limiter per track or stem. Reaching a target is arithmetic: gain = target - measured loudness; limiting needed = (true peak + gain) - ceiling. Above about 6 dB the material is too peaky for the target: fix peaks at the source, lower the target, or ask. [Rule]
4. **Adaptive stems are summed by the game.** Derive every stem from one mix, never normalise or limit stems individually, set loudness on the sum of all stems with one shared gain, keep at least 1 dB of true-peak margin for lossy encoding and loop seams, let the game's runtime limiter stage work at under about 2 dB (the -18 dB, 3:1 compressor ahead of it acts on the music by design), and check every subset the game can play (section 5).
5. **You measure, Fred listens.** After every change: bounce, analyse (integrated LUFS, true peak, LRA, PLR, crest, width, mono-sub loss), loudness-match any A/B to within 0.2 LU (0.3 LU at most), change one thing at a time, keep the previous version on a muted twin, and ask when the numbers say you are trading punch for level.

## 1. What mastering does, and does not

Mastering is the last pass over a finished stereo mix: small tonal corrections, light dynamics control, a final level, a check that the result survives where it will be played (mono, phones, lossy codecs, normalised services), and the delivery files. Sound On Sound calls it polish, not a remix, and advises changing only what serves the music ([SOS, Wright, 2025](https://www.soundonsound.com/techniques/what-mastering-can-cant-do)); iZotope says it works on the finished stereo product and does not rebalance what is inside it ([iZotope](https://www.izotope.com/community/blog/what-is-mastering)). Ableton's Multiband Dynamics page shows the failure from the other side: engineers are asked to put life back into crushed mixes, and a limiter placed after the repair can destroy it again ([manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)).

| What you hear or measure | Fix it in | Why not in the master |
| --- | --- | --- |
| Kick and bass mask each other; bass notes fight the chords | mix, sound design, notes (04, 06, 08) | one stereo file cannot separate them |
| A pad that is hollow, airy, "flangy" or "out of tune" | the instrument and its notes (02, 03) | master processing changes every other sound too |
| One broad tilt (slightly dark or bright, up to about 2 dB) | master EQ Eight | what mastering EQ is for |
| True peaks too high for the target | the transient at its source (drum bus, clip the kick), then the limiter | arithmetic in 3.5 |
| Sections too different in level | level automation in the mix | mastering compression only flattens them |
| Sounds quieter than a reference | check loudness-matched first (section 6) | it is probably just level |

This project has two "masters". A **stereo song** gets the Main-track chain of section 2 and `create_release`. **Adaptive game stems** get nothing that shapes sound on Main; one shared gain sets loudness (section 5).

> **For an agent: triage before you touch the master.** (1) `get_devices("master")` to see what is there. (2) Bounce and `analyze_audio` the current state as a baseline. (3) If the problem is a sound, a note or a balance, report it instead of compensating on the master. (4) Never "fix" a sound Fred chose with master processing; iterate on the sound.

## 2. A Live-native mastering chain

### 2.1 Where it lives

The Main track (the tools call it `"master"`) is the last stage. Live computes in 32-bit float with 64-bit summing at every mix point, so tracks do not clip internally; clipping can only happen at the output stage ([Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/)). A red track meter is not distortion by itself; what matters is the first device that clips (Saturator, Glue soft clip, Limiter) and the converter or export. Export renders the Main track post-fader, so what you measure after the chain is what ships. The manual's rule: anything after Limiter can add gain, so Limiter goes last and the Main fader stays at or below 0 dB.

### 2.2 The chain, in order

| # | Device | Job | Starting point | Limit | Basis |
| --- | --- | --- | --- | --- | --- |
| 1 | Utility (optional) | Trim level into the chain | `Output` (its gain) so Glue's threshold has work to do | - | Rule |
| 2 | EQ Eight | Corrective tone (corrective before "sweetening", linear before non-linear) | Stereo: 12 dB/oct low cut at 20–25 Hz only for rumble; one or two broad shelves or bells of 0.5–1.5 dB. M/S: 12 dB/oct low cut at 100–150 Hz on the Side curve (bass mono) | about 3 dB total in any region | Manual, Eng, Rule |
| 3 | Glue Compressor | Bus glue | `Ratio` 2:1 (raw step 0), `Attack` 10–30 ms (steps 5–6), `Release` Auto (step 6; or 0.2–0.4 s, steps 1–2), `Threshold` for 1–2 dB at the peaks, `Peak Clip In` Off (the soft clip), `Dry/Wet` 100%, `Output` to restore level | 3 dB | Manual, Rule |
| 4 | Multiband Dynamics (only for a measured band problem) | Tame one band: bass swell, harsh highs | `Low-Mid Crossover` about 150–200 Hz and `Mid-High Crossover` 3–5 kHz, ratio about 2:1, `Amount` 20–50% | 3–4 dB per band | Manual, Eng |
| 5 | Saturator as soft clipper | Shave the highest, shortest peaks before the limiter | `Type` Analog Clip; raise `Drive` from 0 in 0.5 dB steps until, at matched loudness, crest falls by 0.5–2 dB; `Output` compensates; `Post Clip Mode` Soft Clip, `Dry/Wet` 100%, Hi-Quality on (a title-bar menu option, not a parameter) | 0.5–2 dB of shaving | Manual, Rule |
| 6 | Utility (bass mono, width) | Only if EQ Eight M/S did not do it | `Bass Mono` On, `Bass Freq` 100–150 Hz, `Stereo Width` 100% | no widening without a measured reason | Manual, Rule |
| 7 | Limiter (last) | Final level and ceiling | `Mode` True Peak, `Lookahead` 3–6 ms, `Auto` On (release Auto), `Link` 100%, `Routing` L/R, `Maximize On` On with `Output` -1.0 dB, lower `Threshold` until peaks show 1–3 dB of reduction | see 2.4 | Manual, Rule |

Main fader 0 dB or lower. Nothing after the Limiter.

### 2.3 Device notes (Live 12.4.6)

**EQ Eight**: Stereo, L/R and M/S modes (an Edit switch picks the Mid or Side curve), cuts at 12 or 48 dB/oct (`n Filter Type A`: High Pass 12dB or 48dB), `Adaptive Q`, a global gain (`Output`, ±12 dB), a `Scale` that moves every gain-capable band together, and 2x Oversampling in the title-bar menu for smoother highs. Prefer 12 dB/oct for a bass-mono cut: steeper filters add phase shift. Mastering moves are tiny: SOS presents a 0.5 dB cut at 7.4 kHz as meaningful.

**Glue Compressor**: Cytomic's model of an 1980s console bus compressor, made for Main or groups. Controls are stepped (`Ratio` 2, 4 or 10; `Attack` 0.01–30 ms; `Release` 0.1–1.2 s or Auto; the 12.4.6 dump lists no items for them, so send the raw step as a number (0–2, 0–6, 0–6) and read the display back). Auto release mixes a slow base time with a fast transient time. `Range` caps compression (about -60 to -70 dB in the manual's notation reproduces the hardware); the API shows it as a positive 0–70 dB, 70.0 by default, so never send a negative value (it clamps to 0 dB, which allows no compression at all). Its soft clip switch (`Peak Clip In`) holds output near -0.5 dB and the manual calls it not transparent: leave it off unless you want that colour. `Output` (0 to +20 dB) is the makeup gain.

**Multiband Dynamics**: Ableton says it is designed primarily for mastering: three bands, each with Above and Below thresholds (`Above Threshold (Low)`, `Below Threshold (Mid)` and so on), adjustable crossovers (`Low-Mid Crossover`, `Mid-High Crossover`), a global `Time Scaling` and `Amount`. SOS's multiband tips: ratio 2:1, attack 20 ms, at most 3–4 dB per band, crossovers at 200 Hz (two bands) or 200 Hz and 5 kHz (three), and band splitting adds phase shift that can become audible when repeated ([SOS, Walden, 2021](https://www.soundonsound.com/techniques/cubase-pro-mix-mastering-multiband-tools)).

**Saturator** (redesigned in 12.1): eight curves (Analog Clip, Soft Sine, Bass Shaper, Medium Curve, Hard Curve, Sinoid Fold, Digital Clip, Waveshaper). Digital and Analog Clip stay linear below the clip point, so only peaks are touched (Digital hard, Analog rounded); the Soft Sine, Medium and Hard curves colour at every level. `Post Clip Mode` (No Clip, Soft Clip or Hard Clip) stops output exceeding the `Output` control. Hi-Quality (less aliasing) is in the title-bar menu. The curve is the parameter `Type`.

**Utility**: `Stereo Width` (0% mono, above 100% wider, up to 200%), `Bass Mono` On plus `Bass Freq` 50–500 Hz, gain -inf to +35 dB (the parameter is `Output`), `DC Filter`.

**Limiter** (overhauled in 12.1: smoother release curve, new metering, M/S routing, Soft Clip and True Peak modes, Maximize; [release notes](https://www.ableton.com/en/release-notes/live-12/)):

- *API names (12.4.6 dump).* `Input Gain`, `Ceiling`, `Release`, `Auto`, `Link`, `M/S Link`, `Lookahead` (1.5 ms, 3 ms, 6 ms), `Routing` (L/R, M/S), `Mode` (Standard, Soft Clip, True Peak), `Maximize On`, `Threshold`, `Output`. A fresh Limiter has `Ceiling` -0.3 dB, `Release` 100 ms and `Mode` Standard.
- *Ceiling modes* (`Mode`). Standard limits sample peaks. Soft Clip adds gentle clipping near the ceiling; its LED flashes when it clips, so a lit LED means you are pushing. True Peak also prevents inter-sample peaks.
- *Maximize* (`Maximize On`). Ceiling becomes Threshold and Input Gain becomes Output. Lowering Threshold by X dB raises output by X dB, and Output sets where peaks land. Loudness becomes one control: set `Output` to -1.0 dB, then lower `Threshold`. Good for agents: each step is one number.
- *Release.* Fast is louder and punchier; slow is smoother but lowers dynamic range. `Auto` On disables the knob. The 12.1 envelope makes long times cleaner than before.
- *Lookahead* 1.5, 3 or 6 ms. Shorter allows more reduction but distorts, especially bass; longer catches fast peaks and adds latency.
- *Link and Routing.* At 100% both channels get the same reduction (stable image); at 0% they act independently (a stereo "wobble"). M/S routing limits mono and stereo parts separately, which can stop a mono kick ducking wide pads, at the cost of latency and a changed image.
- Ranges (Ableton DSP package for Max): Gain -24 to +24 dB, Ceiling -24 to 0 dB, Release up to 3 s ([Cycling '74](https://docs.cycling74.com/reference/abl.device.limiter~)).

**Third-party equivalents.** The usual pro limiters (FabFilter Pro-L 2, iZotope Ozone Maximizer, DMG Limitless) are not needed: Live's Limiter in True Peak mode does the job and every setting is reachable from the tools. [Rule]

### 2.4 How much gain reduction is normal

| Stage | Normal at the loudest moments | Look closer at | Basis |
| --- | --- | --- | --- |
| Glue Compressor | 1–2 dB | above 3 dB | Rule |
| One multiband band | 1–2 dB | above 3–4 dB | Eng (Walden) |
| Soft clip | 0.5–2 dB, LED only on the loudest hits | LED lit constantly | Manual, Rule |
| Limiter | 1–3 dB open; 3–6 dB dense, loud electronic | above 6 dB, or a meter that never returns to 0 | Rule; `create_release` warns above 6 dB [Project] |
| Whole chain, PLR lost | 4–6 dB at most | more than 6 dB | Rule |

Limiter's gain-reduction meter is not among the 12.4.6 dump's parameters, so the tools probably cannot read it (check `get_device` for a read-only value). Otherwise estimate it: bounce with the Limiter bypassed and use the formula `create_release` uses, reduction at the peaks = true peak + gain - ceiling.

> **For an agent: build and verify a master chain (stereo songs only).**
> 1. `get_devices("master")`. For adaptive stems stop here (section 5).
> 2. `add_device("master", "EQ Eight")`, then `"Glue Compressor"`, `"Saturator"`, `"Utility"`, `"Limiter"` (`position=-1` appends, so call order is chain order). Multiband Dynamics goes between Glue and Saturator only for a measured band problem.
> 3. After each add, `get_device("master", "<name>")` and copy the exact parameter names, ranges and items. Set one device per call with display strings, e.g. `set_device_parameters("master", "Limiter", {"Mode": "True Peak", "Maximize On": "On", "Output": "-1 dB"})`; `Maximize On` swaps the active pair: `Threshold` and `Output` with it on, `Input Gain` and `Ceiling` with it off. `set_mixer("master", volume_db=0)`.
> 4. Baseline vs chain: bounce with every chain device disabled (`set_device(..., enabled=False)`), then enabled: `bounce(start=..., end=..., name="master-check")`, poll `get_bounce_status(wait=50)` until `done`, `analyze_audio(path=...)` on each master file.
> 5. Read integrated LUFS (target within 0.2 LU; 0.5 LU is only the game spec's T5 tolerance), true peak (at or below the ceiling; allow 0.1–0.2 dB), loudness range, crest and PLR, width and correlation, mono-sub loss (at most 1 dB below 120 Hz), band changes (no more than intended).
> 6. Loudness-match before comparing (within 0.2 LU, 0.3 LU at most): put the difference in a Utility `Output` on the louder version, or use `compare`, whose spectral metrics are already loudness-matched. Use neutral labels.
> 7. Ask Fred when the reduction estimate is above 3 dB, when the chain moves a broad band by more than about 1.5 dB, or before leaving a soft clipper on: no meter measures distortion.

## 3. Loudness targets by destination

### 3.1 How normalisation works

Services measure integrated loudness (BS.1770: K-weighting, 400 ms blocks overlapping 75%, gated at -70 LUFS and then 10 LU below the result; [ITU-R BS.1770-5](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf)) and apply one gain offset to the track or album. Most only turn down; Spotify and Apple Music also turn quiet masters up, only as far as peak headroom allows. What each does to a master (derived arithmetic):

| Master, integrated | Spotify (-14) | Apple Music (-16) | YouTube (-14, down only) | YouTube Music (about -7, down only) | SoundCloud, Beatport, Bandcamp |
| --- | --- | --- | --- | --- | --- |
| -6 LUFS | -8 dB | -10 dB | -8 dB | -1 dB | unchanged |
| -8 LUFS | -6 dB | -8 dB | -6 dB | unchanged | unchanged |
| -10 LUFS | -4 dB | -6 dB | -4 dB | unchanged | unchanged |
| -12 LUFS | -2 dB | -4 dB | -2 dB | unchanged | unchanged |
| -14 LUFS | 0 | -2 dB | 0 | unchanged | unchanged |

A -8 and a -14 LUFS master both reach a Spotify listener at -14 LUFS, but the first had 6 dB taken off peaks that were already squashed. In Ian Shepherd's case study a master at -7.9 LUFS was turned down about 6 dB while a remaster at -10.7 LUFS lost about 3.5 dB and kept its dynamics ([Meterplugs](https://www.meterplugs.com/blog/2022/06/14/mastering-with-perception-ab.html)). He adds that most aggressive music rarely benefits from sitting more than 3 dB above the point where it is turned down, roughly louder than -11 LUFS ([Production Advice](https://productionadvice.co.uk/no-lufs-targets/)).

### 3.2 Streaming platforms

| Service | Reference | Worth knowing |
| --- | --- | --- |
| Spotify | -14 LUFS default; Loud -11, Quiet -19 | Turns down with no added distortion; turns up keeping 1 dB true-peak headroom; the Loud setting adds a limiter at -1 dB (5 ms attack, 100 ms decay). Web player and third-party devices do not normalise. Artist advice: -14 LUFS integrated, true peak at or below -1 dBTP, at or below -2 dBTP if louder than -14. [Spec: [Spotify](https://support.spotify.com/artists/article/loudness-normalization/)] |
| Apple Music | -16 LUFS | Sound Check on by default on new devices; track or album mode; never limits. Apple asks for 24-bit masters and at least 1 dB headroom. [Spec, Eng: [Apple brief](https://www.apple.com/apple-music/apple-digital-masters/docs/apple-digital-masters.pdf), [iZotope 2025](https://www.izotope.com/en/learn/mastering-for-streaming-platforms.html)] |
| YouTube | -14 LUFS | Track only, always on, turns down only. |
| YouTube Music | about -7 LUFS | Reported October 2023: reduces only above -7 LUFS. One source; could change. [Eng: [Production Advice](https://productionadvice.co.uk/youtube-music/)] |
| Tidal, Amazon Music | -14 LUFS | Tidal normalises by album even in playlists; Amazon by track. |
| Deezer, Pandora | -15 LUFS; about -14 (not true LUFS) | Deezer always on; Pandora can boost. |
| SoundCloud, Beatport, Bandcamp | none | Masters play as delivered ([SOS, April 2023](https://www.soundonsound.com/techniques/ian-shepherd-loudness-dynamics); iZotope 2025 for SoundCloud). |

iZotope (July 2025): about -12 LUFS integrated, peaks at or below -1 dBTP and short-term no higher than -10 or -9 LUFS will still be turned down a little on every major service; its advice is the highest level at which the track keeps its impact, not a number. For albums the AES recommendation (TD1008, now AES77) is album normalisation with the loudest track at -14 LUFS, or music normalised to -16 LUFS per track; speech -18. It rests on Eelco Grimm's 2017 research for Tidal (4.2 million albums analysed, plus a listening test in which about 80% preferred album normalisation) ([Production Advice](https://productionadvice.co.uk/td1008/), [Radio World](https://www.radioworld.com/?p=115138)).

### 3.3 Broadcast, club and games

- **Broadcast.** EBU R 128 (2023): -23.0 LUFS; 1.0 LU tolerance for live programmes, 0.2 LU for measurement error in QC; true peak at most -1 dBTP ([EBU R 128](https://tech.ebu.ch/docs/r/r128.pdf)). R 128 s2 (2023, streaming): produce at -23 LUFS, or an interim distribution level of -20 to -16 LUFS if the broadcaster controls the dynamic treatment; true-peak limiting in the device when it raises the level ([s2](https://tech.ebu.ch/docs/r/r128s2.pdf)). Tech 3343 notes heavily compressed music tends to be played 2–3 LU louder, and still discourages a higher music target ([Tech 3343](https://tech.ebu.ch/docs/tech/tech3343.pdf)). US TV (ATSC A/85) is -24 LKFS with a 2 dB tolerance (not re-verified here).
- **Club and DJ.** No standard; playout is not normalised and DJs ride trim, so extra loudness buys little. Practitioners disagree: Shepherd uses a -10 LUFS short-term ceiling for EDM and thrash alike (integrated -10 to -11); iZotope's Stewart calls about -12 integrated already loud enough to be turned down everywhere; Mastering The Mix calls -6 short-term the "loud lane" but warns that with a -2 dBTP ceiling it forces limiting equal to a -4 LUFS master [Vendor: [MTM](https://www.masteringthemix.com/pages/how-loud-should-you-master)]. A defensible club master sits around -10 to -8 LUFS integrated with PLR of 8 dB or more; this is taste, so ask Fred. [Rule]
- **Games, console.** G.A.N.G. IESD v03.02 (2015) for Sony, Microsoft and Nintendo titles: -24 LUFS plus or minus 2 LU, true peak at most -1 dBTP, BS.1770 measurement, stereo downmix as loud as surround. Sony's earlier figures: -23 LUFS (PS3), -18 (Vita), plus or minus 2 LU, measured over at least 30 minutes of representative play; PS4: -24 LKFS over at least 30 minutes ([G.A.N.G.](https://www.audiogang.org/wp-content/uploads/2015/04/IESD-Mix-Ref-Levels-v03.02.pdf), [Taylor interview](https://designingsound.org/2012/07/30/video-games-and-loudness-standards-interview-with-sonys-garry-taylor/), [Sulpha](https://designingsound.org/2015/06/04/sulpha-the-new-ps4-mastering-suit/)).
- **Games, mobile and handheld.** G.A.N.G.: -16 LUFS plus or minus 2 LU with a loudness range of 10–15 LU. Rob Bridgett proposes adapting: about -24 on headphones in quiet, -18 to -16 in noise, -16.2 on a phone speaker ([Audio Media International](https://audiomediainternational.com/mobile-loudness-an-adaptive-approach/)). These cover music, effects and voice together.

### 3.4 True-peak ceilings and codec overshoot

Lossy encoders reconstruct a waveform that can overshoot the original peaks. Apple's brief says levels with no overs on the PCM master can still clip once encoded, asks for at least 1 dB of headroom, and ships `afclip` (it checks 4x-upsampled peaks) to test the encoded file. EBU Tech 3344 limits production to -1 dBTP, puts an end-stage peak limiter at -2 dBTP in front of an encoder, and says to go lower at low bit rates ([Tech 3344](https://tech.ebu.ch/docs/tech/tech3344.pdf)). Spotify says the same in its own terms (-1 dBTP, -2 when louder than -14 LUFS). iZotope: at least 1 dB, more for loud material or low bit rates, -0.3 dBTP is fine for lossless-only; Production Expert: 1–3 dB. The repo's `create_release` measures its encoded MP3 (320 kbps) and AAC (256 kbps) true peaks and re-encodes from a lower-ceiling premaster when they overshoot [Project]. Spotify names Ogg Vorbis and AAC; no source here measured Opus (used by some video platforms), so treat it like AAC and test an encode if it matters. Mastering The Mix's vendor guide advises switching true-peak limiting off for loud masters; this contradicts every standards source here, so treat it as opinion.

**Practical ceilings:** -1.0 dBTP by default; -2.0 dBTP when louder than -14 LUFS or the codec is unknown. macOS check, per Apple: `afconvert` to 256 kbps AAC, decode back, run `afclip` (both are in `/usr/bin`; confirm flags with `-h`).

### 3.5 PLR, crest factor, and the arithmetic of a target

- **PLR** = true peak - integrated LUFS (EBU's definition). **Crest factor** = peak - average, here sample peak minus RMS. **LRA** is the spread of short-term loudness over a whole programme, and EBU does not recommend it for programmes under a minute ([EBU R 128](https://tech.ebu.ch/docs/r/r128.pdf)). They differ by roughly 0.5–2 dB on the same file (0.6 and 1.6 dB in the reference profiles below), so compare like with like.
- **Ranges** (context, never targets):

| Material | Typical figure | Source |
| --- | --- | --- |
| Unprocessed drums | crest 16–18 dB | [iZotope, 2020](https://www.izotope.com/en/learn/what-is-crest-factor.html) |
| Legato strings, unprocessed | crest 6–8 dB | iZotope |
| Punchy mix, little limiting | crest 12–15 dB sparse, 9–12 dB dense | iZotope |
| Masters that translate well | crest 8–12 dB; under 9–10 suggests over-processing | iZotope |
| Loud pop and EDM | crest 3–5 dB reported | iZotope |
| Katz's K-20 (film, classical), K-14 (pop, rock, folk), K-12 (broadcast) | 20, 14 and 12 dB of headroom over the average | [Katz](https://www.digido.com/portfolio-item/level-practices-part-2/) |
| Nine Inch Noize references, whole tracks | PLR 8.5 and 13.1, crest 9.1 and 14.7, LRA 6.4 and 5.5 | [Project] (n = 2) |
| Metal vs classical | LRA 3–4 vs 20 or more | iZotope 2025 |

- **Why loudness competes with itself.** Katz puts the onset of dynamic inversion (a soft section sounding louder) around a -14 dBFS average; iZotope shows the -10 LU gate can make a dynamic song measure louder than it sounds. Judge dynamics by short-term loudness and PLR, not integrated LUFS alone.
- **The arithmetic.** Gain needed = target - measured LUFS. Peak after gain = measured true peak + gain. Limiting needed = that peak - ceiling. Example: an unlimited sum at -20 LUFS and -2 dBTP (PLR 18) needs +6 dB to reach -14, putting peaks at +4 dBTP, so a -1 dBTP ceiling needs 5 dB of peak reduction. In general -14 LUFS with a -1 dBTP ceiling allows PLR 13 with no limiting: source PLR 12 needs none, 16 needs 3 dB, 20 needs 7 dB.

> **For an agent: choose a target, measure, decide.**
> 1. Ask which destination: streaming single, album, club or game. Do not guess.
> 2. Bounce the unlimited master (limiter bypassed). `analyze_audio`: integrated LUFS, true peak, PLR (true peak - integrated), crest, LRA.
> 3. Compute the limiting needed. Up to 3 dB: proceed. 3–6 dB: keep it only after Fred has heard a matched-loudness A/B (06 also stops and asks above 3 dB). Above 6 dB: do not push the limiter; tell Fred the material is too peaky for the target and offer three options (fix the loudest transients at source, lower the target, accept the dynamics).
> 4. After limiting confirm integrated within 0.2 LU of the target (`create_release` itself converges to 0.2 LU) and true peak at or below the ceiling. Repo noise floors are 0.07 LU for integrated and 0.24 dB for true peak [Project]; smaller differences are not real.
> 5. For a streaming release `create_release(target_lufs=-14, true_peak=-1)` applies linear gain when peaks allow and otherwise a 4x-oversampled limiter; read the method and `gain_reduction_db` in `release.json`.

## 4. Limiting, clipping, inter-sample peaks, dither, export, stems

### 4.1 Limiting versus clipping

A limiter is a compressor with a near-infinite ratio plus lookahead: it lowers gain around a peak and recovers on its release, so sustained material under the peak ducks (pumping) but waveforms stay smooth. A clipper chops the peak instantly: no time constants, no pumping, but harmonics (and aliasing if not oversampled). iZotope's primer says a limiter's real home is mastering, because its compression is too extreme for channels ([iZotope, 2025](https://www.izotope.com/en/learn/audio-dynamics-101-compressors-limiters-expanders-and-gates.html)).

Live's clippers: Saturator (Digital or Analog Clip, Post Clip Mode), Glue's Soft clip switch, and Limiter's Soft Clip mode. Common electronic practice is to shave the highest, shortest transients (kick, snare, clap) by 0.5–2 dB with a soft clipper first, so the limiter works less and pumps less [Rule]. The price is distortion no meter measures: if the kick sounds flat or buzzy it has gone too far. That is Fred's call, with a labelled A/B.

### 4.2 Release and lookahead

At 140 BPM a beat is 429 ms and a sixteenth 107 ms (60000 / BPM). If release is longer than the gap between loud hits, gain reduction never recovers and the master pumps. Start on Auto. Manual starting points: 50–150 ms for a drum-driven groove, 200–400 ms for pads and ambient [Rule]. For bass-heavy material use Lookahead 3–6 ms (short lookahead distorts bass, per the manual). GR should fall toward 0 between kicks.

### 4.3 Inter-sample peaks

A sampled waveform's true peaks often fall between samples. BS.1770-5 Annex 2 notes sample-peak meters can under-read, by 3 dB for a tone at a quarter of the sample rate in unlucky phase; a true-peak meter oversamples (at least 192 kHz from a 48 kHz base, so 4x). EBU Tech 3344 adds that the remaining difference to the analogue level is under 1 dB, typically a few tenths. So use True Peak mode for the final stage, verify with the true-peak figure from `analyze_audio` (not `get_meters`, a momentary meter), and keep the codec margin of 3.4. A commercial master was measured at -5.3 LUFS with a true peak of +3.48 dBTP ([Production Advice](https://productionadvice.co.uk/youtube-music/)): this happens.

### 4.4 Dither and export in Live 12.4

| Setting | Use | Why |
| --- | --- | --- |
| File type | WAV (AIFF equivalent; FLAC for archive) | Live offers WAV, AIFF, FLAC |
| Bit depth | 32-bit float for anything processed again (stems, premasters, input to `create_release`); 24-bit for final delivery; 16-bit only on request | Live is 32-bit float inside; Ableton says render at 32-bit and dither only the final file |
| Dither | none at 32-bit; Triangular (default) at 24 or 16; POW-r only on the very last render, never before another mastering stage | dither once only; Apple's encoders need none from a 24-bit source |
| Normalize | **off** | it lifts the highest peak to full scale (breaks the ceiling) and on separate stem files would rescale each independently |
| Sample rate | set Live's sample rate (Settings, Audio; it is the interface's, not stored in the set) to the delivery rate before starting (48 kHz for this project's game files); export at that rate | lower export rates are downsampled by SoX in a second step; Ableton advises choosing the rate first |
| Render as Loop | on for loops and looping stems | folds the effect tail into the start |
| Convert to Mono | off | |
| Include Return and Main Effects | careful, see 4.5 | each stem then also passes the Main chain |
| Encode MP3 | CBR 320 adds a little silence at the start | misaligns stems; use `create_release` for MP3 |

Sources: [manual, Exporting Audio and Video](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/), [Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/), [iZotope on bit depth](https://www.izotope.com/en/learn/digital-audio-basics-sample-rate-and-bit-depth.html), Apple brief. Tools: `bounce` records in real time by resampling inside Live at Live's rate and recording bit depth (the calibration notes record captures at 44.1 kHz and 24-bit); `create_release` does the final normalise, 24/16-bit and dither; `export_audio` (UI automation, experimental) uses Live's own offline export.

### 4.5 Stem mastering, and why game stems are different

In stem mastering an engineer receives a few stereo submixes (drums, bass, music, vocals) rendered without master-bus effects, with identical start points and no bus limiter, and adjusts them before the final stereo limiter ([iZotope, 2023](https://www.izotope.com/en/learn/stem-mastering.html)). A vendor guide asks for -6 to -3 dB peaks on the loudest bars ([MTM](https://www.masteringthemix.com/pages/how-to-stem-master-a-song)). iZotope: use it when you cannot go back to the mixer; if you can, fix the mix. The stems sum back to the original mix by design.

Game stems are not that. The player's engine sums a subset at runtime, nobody mixes the result, and the "master" is whatever the sum is. Exporting with "Include Return and Main Effects" would also run each stem through the Main chain, so a Main limiter would act on every stem alone (the failure in 5.3). The repo's `audio.sum_null` check (stems plus returns must cancel the Main mix by 40 dB) fails when something on Main changes the signal, so keep Main neutral (no effects, fader at 0 dB) while preparing stems.

> **For an agent: export checks.** Final files: 24-bit WAV, Normalize off, no dither at 32-bit, triangular only for a 16-bit deliverable. Intermediates: 32-bit float. `bounce(stems=[...], include_returns=True)` for stems, with Main empty. Never run `create_release` on each stem as if it were a song; pass them as `stems` so they are copied unprocessed.

## 5. Loudness for adaptive game stems that the game sums at runtime

### 5.1 The situation

The soundtrack is five tiers that join by level: T1 pad + arp, T2 + bass, T3 + kick, T4 + perc, T5 + lead, looping at 100–180 BPM, delivered at 48 kHz and 24-bit. The game sums the active stems, applies its master chain (a compressor, a limiter and the master volume: rule 5 in 5.3) and sums SFX and stingers on top of the music. The spec asks T5 (all on) for -14 LUFS plus or minus 0.5 LU and at most -1 dBTP; lower tiers are reported, not targeted [Project: docs/listening-loop-prd.md]. That -14 LUFS music-only target is louder than the whole-game guidance in 3.3: see Open questions.

### 5.2 What happens to level when stems add

For N stems of equal peak that all peak together, the sum is 20 log10(N) dB higher; for uncorrelated stems, average level grows 10 log10(N) dB:

| N stems | Worst-case peak sum | Average-level growth (uncorrelated) |
| --- | --- | --- |
| 2 | +6.0 dB | +3.0 dB |
| 3 | +9.5 dB | +4.8 dB |
| 5 | +14.0 dB | +7.0 dB |

Real stems differ in level and spectrum, so reality lands between (kick and bass are the pair that routinely aligns). Five stems each peaking at -1 dBFS could sum to +13 dBFS in the worst case, so peaks cannot be budgeted per stem: measure the real sum. For uncorrelated material, a stem sitting r dB below the existing sum adds 10 log10(1 + 10^(-r/10)) to its loudness: 0 dB gives +3.0 LU, 6 dB +1.0, 10 dB +0.4, 12 dB +0.3. That is the step size to expect on the tier ladder; a tier quieter than the one below it points to cancellation.

### 5.3 The rules

1. **Derive every stem from one mix.** Stems are post-fader outputs of the same session at the same gain staging, so the full sum is the mix, and any subset peaks at or below the full sum unless cancellation intervenes (the ladder check catches that).
2. **No limiter, normalisation or loudness matching per stem.** The failed attempt put True Peak limiters on every stem, +12 dB into -14 dB ceilings, and Fred called it garbage [Project: docs/handoff/2026-10-08-nova-v2-paused.md]. Why: each limiter reacts to its own stem's peaks, so a kick stem alone is flattened to reach a loudness it never needs; all stems end up near the same loudness, which erases the tier ladder and the balance; five squashed stems still sum above the ceiling, so a second limiter follows, and double limiting is the worst kind. iZotope notes limiters are mastering tools, not channel tools. Stem crest factors also differ wildly (unprocessed drums 16–18 dB, sustained strings 6–8, by iZotope's figures), so one loudness target for all stems is meaningless.
3. **Set loudness once, on the full sum, with one gain shared by every stem.** Never level stems one by one, so they keep their relative levels. For this game the delivery pipeline does it (tetris-nova `tools/music/cut_stems.py`): one periodic 2-bar gain curve per tempo, applied to every stem so every subset sees the same reduction at the loop seams, then one trim so the mean A/B sum is -14.6 LUFS. In Live keep the stems unlimited; if you trim there, change every stem track by the same dB (the same `volume_db`, or the same Utility `Output`). Use the arithmetic of 3.5 on the unlimited T5 sum.
4. **If the sum is too peaky for -14 / -1, fix the peaks at their source**, not with limiters on stems: the loudest transients (usually kick and bass, or an over-hot perc) via Drum Buss, a clipper on that one stem, or a lower fader; then re-measure.
5. **Know the game's master chain: the compressor acts by design, the limiter is the safety net.** The runtime chain (tetris-nova `src/audio/context.ts`, relayed to this digest, not re-read) is a DynamicsCompressor at threshold -18 dB, ratio 3:1, attack 5 ms, release 150 ms, then a limiter at -1 dB with 20:1, then the master volume; SFX and stingers sum on top of the music. A -14 LUFS music sum peaks near -1 dBTP, about 17 dB above that threshold, so the compressor works on the music most of the time and probably narrows the tier ladder (reasoned, not measured: `10-game-audio-adaptive-music.md`, 6.3). A Web Audio DynamicsCompressorNode also adds automatic makeup gain (in WebKit's code, the inverse of its full-scale gain raised to the power 0.6, which lifts material below the threshold) and puts its knee above the threshold, so the net level change cannot be read off threshold and ratio; the game's knee is not recorded here **[verify]**. Your offline numbers are therefore not what the player hears: measure the game's own output and log each node's `reduction` while T5 plays. Expect the limiter stage to act rarely: above about 2 dB means the stems are too hot or the SFX pile up. [Rule]
6. **Leave margin for the file path.** The shipped masters peaked at -0.6 dBTP at loop seams (measured offline, before the game's master chain) because the game's 10 ms equal-power crossfade adds up to 3 dB on correlated audio, while the same stems looped natively peaked at -1.45 dBTP [Project: docs/listening-loop-calibration.md, handoff]. Aim for -2 dBTP or lower at the file level, or ask for a linear crossfade; lossy encoding adds more (3.4).
7. **Check every subset the game can play.** The ladder covers five. If variations can mix (A bass with B arp) or the lead can leave while the kick stays, build those sums too.

### 5.4 Consistency across tempos and sections

Tempo changes density: a half-time pattern at 100 BPM has more silence than at 180, and fixed-millisecond envelopes behave differently against the beat. In the project's calibration (2026-10-07) a part's loudness differed by up to 2.9 LU between tempos (pad +2.9 and arps +2.2 and +2.4 at 100 BPM, perc -2.8 at 100, bass A -1.8 at 180), because the composer levelled the full mix per tempo instead of each stem, so a player heard stems jump at level-ups [Project]. The spec allows 1 LU per stem across a set's tempos. Fix it at the stem: trim each stem per tempo until its loop loudness agrees, then apply the shared gain of rule 3. Read integrated and short-term loudness on the tiled loop; EBU does not recommend LRA for short material.

### 5.5 Checks, with numbers

| Check | Passes when | Tool |
| --- | --- | --- |
| T5 loudness and peak | -14 LUFS plus or minus 0.5 LU and at most -1 dBTP (noise floor 0.07 LU and 0.24 dB) | `capture`, `analyze_audio(take=...)` |
| Tier ladder | each tier louder than the one below; steps match the 5.2 formula | `audio.tier_ladder` |
| Stem consistency | each stem within 1 LU across tempos | `capture(tempos=[low, high])`, `audio.tempo_consistency` |
| Sum null | stems plus returns cancel Main by at least 40 dB (no Main effects) | `audio.sum_null` |
| Mono sub | loses at most 1 dB below 120 Hz | `audio.mono_sub` |
| Seams | fold and click checks pass; true peak with the game's crossfade still at or below -1 dBTP | `file.seam`, strict mode, tier sums |
| Runtime | the limiter stage (-1 dB, 20:1) reduces by under about 2 dB with T5 and typical SFX playing; the -18 dB, 3:1 compressor acts by design | log each node's `reduction` in the game |

> **For an agent: stems and the sum.** (1) Keep Main empty; confirm with `get_devices("master")`. (2) `capture()` at the middle tempo, then the lowest and highest. (3) Read T5 integrated and true peak and compute the limiting needed (3.5). (4) If it exceeds about 3 dB, find which stem brings the peaks (`analyze_audio` on each stem file: peak and crest) and ask Fred about treating that stem. (5) Apply one shared gain (the same `volume_db` change on every stem track, or the same Utility `Output`; the pipeline then adds its own curve and trim), re-capture, `compare("latest", "best")`. (6) Never add a limiter to a stem track to hit loudness. (7) Report the ladder and numbers, not "sounds good"; the human listening check stays the gate.

## 6. Reference mastering

1. **Match loudness first.** Louder sounds better, so an unmatched A/B tells you about level, not quality ([Meterplugs](https://www.meterplugs.com/blog/2022/06/14/mastering-with-perception-ab.html)). Match short-term loudness of comparable sections (loudest to loudest) within 0.2 LU (0.3 LU at most), not integrated loudness of arrangements that differ. Pros also say to pick a reference of similar structural intensity and, for electronic music, a similar key ([iZotope pros](https://www.izotope.com/community/blog/pro-reference-tracks)). `compare("latest", "refs")` already loudness-matches its spectral metrics; PLR, crest and LRA are not matched and are information only.
2. **Balance, don't match.** That is the title of Shepherd's SOS lesson on EQ. iZotope: references teach tonal balance, loudness, crest factor, width and low-end punch; resist leaning on them so far that you lose what is unique ([iZotope](https://www.izotope.com/community/blog/how-to-use-mastering-references)).
3. **Copy:** broad tonal tilt in four to six bands; where the energy sits in the lows; width above 200 Hz and mono below; density and dynamics direction (PLR and short-term spread inside the range the references span).
4. **Do not copy:** absolute loudness; the reference's limiter distortion; one song's EQ curve; a full-mix spectrum as the target for a single instrument (the earlier failure: ranking pads by distance to full-mix spectra); peaks that come from its key or bass line.
5. **Tonal-balance targets.** iZotope's Tonal Balance Control 3 ships 30+ genre targets built from hundreds of professional masters, a Target Blender and a low-end crest meter ([iZotope](https://www.izotope.com/en/products/tonal-balance-control.html)). Live has no equivalent; use the stored reference profiles (`ref(action="list")`), which keep numbers, never audio. `compare(..., "refs")` reports band balance, dynamics, width and onset density against the range all references span: inside is fine, outside means look.
6. **Reading a band difference.** Within about 1 dB (the compare noise floor is 0.5 dB): ignore. 1–3 dB: note it. Over 3 dB in a broad band: decide with Fred whether it is intended (a sub-heavy club master against a streaming reference, say).
7. **Project data point.** The two Nine Inch Noize profiles in `~/Music/AbletonMCP/Ears/refs` (She's Gone Away, Vessel) read PLR 8.5 and 13.1 over the whole track, but 6.5 and 12.5 in dense sections and 9.5 and 10.9 in sparse ones; correlation 0.83 and 0.76; width (side/mid RMS) 0.31 and 0.37. Two tracks through a lossy stream are a direction, not a target [Project].

> **For an agent: references.** `ref(action="list")` first; never chase a reference's loudness; report where the take sits against the range; if it is outside, say which band and by how much, and ask before correcting. For a new reference: `ref(action="measure", uri=...)` (stop Live first), then compare.

## 7. Over-limiting numbers, and when to ask the human

| Measure | Fine | Look closer | Over-limited | Basis |
| --- | --- | --- | --- | --- |
| Estimated limiter reduction at peaks | up to 3 dB | 3–6 dB | above 6 dB, or a meter stuck above 0 | Rule; `create_release` warns above 6 dB |
| PLR (true peak - integrated) | 8 dB or more | 6–8 dB | below 6 dB | Rule from the 3.5 crest ranges |
| Crest (sample peak - RMS) | 9–14 dB | 6–9 dB | below 6 dB | iZotope |
| Short-term maximum below true peak | at least 6 LU | 4–6 LU | under 4 LU | iZotope |
| Integrated loudness | -14 to -10 LUFS | -10 to -8 | louder than -8: turned down 6 dB or more on most services | 3.1 |
| Dynamics spread (90th minus 10th percentile of short-term loudness) | 3 LU or more | 2–3 | under 2 for a track with sections | Project refs 3.0–6.2 |
| Loudness range, full track | 3 LU or more | 2–3 | under 2 | iZotope, Project |
| True peak after encoding vs the WAV | within 0.3 dB | 0.3–1 dB | above the ceiling | 3.4 |
| Limiter on individual stems or tracks | none | - | any, to reach a loudness | section 5 |

Dense industrial and EDM can sit at the edge of these ranges on purpose: that is Fred's decision with a labelled A/B, not yours.

**Ask Fred when:**
- the destination is unspecified, or the target conflicts with the style (more than 3 dB of limiting, or PLR under 8);
- you are about to process the Main track of a set Fred likes, or a sound he chose;
- you add soft clipping or saturation, or want to leave it on after an A/B (distortion cannot be measured);
- band balance differs from references by more than 3 dB;
- lossy-encode overshoot persists after lowering the ceiling;
- a loudness choice would change the tier ladder or stem balance.

Present a labelled, loudness-matched A/B: neutral names, same section, loudness matched within 0.2 LU (0.3 LU at most), one line on what changed, and the measurements. One change at a time; keep the previous version on a muted twin.

**Common mistakes**
1. A limiter on every stem or track to reach -14 LUFS (the NOVA failure), when linear gain plus a peak fix would do.
2. Normalize on at export, especially for stems; dithering twice or POW-r before a mastering stage.
3. Judging a change that is also louder (unmatched A/B).
4. Stem export with a limiter on Main and "Include Return and Main Effects" on.
5. Processing after the Limiter, or a Main fader above 0 dB.
6. A 0 or -0.1 dB ceiling for lossy delivery, or trusting a sample-peak meter.
7. Many changes in one pass; unlabelled auditions.
8. Ranking or EQing one instrument against a full-mix reference.

## Sources

Ableton and Cycling '74
- [Live 12 manual: Audio Effect Reference](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/) (Limiter 29.24, Multiband Dynamics 29.26, EQ Eight 29.15, Glue Compressor 29.21, Saturator 29.34, Utility 29.40)
- [Live 12 manual: Managing Files and Sets](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/) (5.1.3 Exporting Audio and Video)
- [Live 12 manual: Audio Fact Sheet](https://www.ableton.com/en/live-manual/12/audio-fact-sheet/)
- [Live 12 release notes](https://www.ableton.com/en/release-notes/live-12/) (12.1: Limiter, Saturator)
- [Cycling '74: abl.device.limiter~](https://docs.cycling74.com/reference/abl.device.limiter~)

Standards and platform documents
- [EBU R 128 (2023)](https://tech.ebu.ch/docs/r/r128.pdf); [R 128 s2, Loudness in Streaming (2023)](https://tech.ebu.ch/docs/r/r128s2.pdf); [Tech 3343 (2023)](https://tech.ebu.ch/docs/tech/tech3343.pdf); [Tech 3344 v2.1 (2016)](https://tech.ebu.ch/docs/tech/tech3344.pdf)
- [ITU-R BS.1770-5 (2023)](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf)
- [Spotify: loudness normalization](https://support.spotify.com/artists/article/loudness-normalization/)
- [Apple Digital Masters technology brief](https://www.apple.com/apple-music/apple-digital-masters/docs/apple-digital-masters.pdf)
- AES TD1008 / AES77 (paywalled; read through secondary sources): [Production Advice](https://productionadvice.co.uk/td1008/), [Radio World](https://www.radioworld.com/?p=115138), [iZotope 2025](https://www.izotope.com/en/learn/mastering-for-streaming-platforms.html)
- [G.A.N.G. IESD mix recommendations v03.02 (2015)](https://www.audiogang.org/wp-content/uploads/2015/04/IESD-Mix-Ref-Levels-v03.02.pdf)
- [Web Audio API spec: DynamicsCompressorNode](https://webaudio.github.io/web-audio-api/) (parameters; the knee is a range above the threshold per [MDN](https://developer.mozilla.org/en-US/docs/Web/API/DynamicsCompressorNode)); automatic makeup gain and the knee placement as coded in [WebKit's DynamicsCompressorKernel.cpp](https://github.com/WebKit/WebKit/blob/main/Source/WebCore/platform/audio/DynamicsCompressorKernel.cpp)

Engineers and educators
- [Sound On Sound: Ian Shepherd on Loudness & Dynamics (April 2023)](https://www.soundonsound.com/techniques/ian-shepherd-loudness-dynamics)
- [Sound On Sound: What Mastering Can & Can't Do (Wright, September 2025)](https://www.soundonsound.com/techniques/what-mastering-can-cant-do)
- [Sound On Sound: Cubase Pro mix mastering with multiband tools (Walden, November 2021)](https://www.soundonsound.com/techniques/cubase-pro-mix-mastering-multiband-tools)
- iZotope: [How to master for streaming platforms (Stewart, July 2025)](https://www.izotope.com/en/learn/mastering-for-streaming-platforms.html); [What is crest factor (Stewart, July 2020)](https://www.izotope.com/en/learn/what-is-crest-factor.html); [Audio dynamics 101 (Brown, 2025)](https://www.izotope.com/en/learn/audio-dynamics-101-compressors-limiters-expanders-and-gates.html); [Sample rate and bit depth](https://www.izotope.com/en/learn/digital-audio-basics-sample-rate-and-bit-depth.html); [Stem mastering (2023)](https://www.izotope.com/en/learn/stem-mastering.html); [What is audio mastering?](https://www.izotope.com/community/blog/what-is-mastering); [Using reference tracks in mastering](https://www.izotope.com/community/blog/how-to-use-mastering-references); [How pros use reference tracks](https://www.izotope.com/community/blog/pro-reference-tracks); [Tonal Balance Control 3](https://www.izotope.com/en/products/tonal-balance-control.html)
- Production Advice (Shepherd): [do not aim at LUFS targets](https://productionadvice.co.uk/no-lufs-targets/); [YouTube Music is different (October 2023)](https://productionadvice.co.uk/youtube-music/); [TD1008 summary](https://productionadvice.co.uk/td1008/)
- [Meterplugs: mastering with loudness-matched A/B](https://www.meterplugs.com/blog/2022/06/14/mastering-with-perception-ab.html)
- [Bob Katz: the K-System](https://www.digido.com/portfolio-item/level-practices-part-2/)
- Production Expert: [Apple chooses -16 LUFS (October 2022)](https://www.production-expert.com/production-expert-1/apple-choose-16lufs-loudness-level-for-apple-music-heres-why); [EBU loudness standard updated (October 2020)](https://www.production-expert.com/home-page/ebu-loudness-standard-updated)
- Designing Sound: [Sony's Garry Taylor (2012)](https://designingsound.org/2012/07/30/video-games-and-loudness-standards-interview-with-sonys-garry-taylor/); [Loudness in game audio (2013)](https://designingsound.org/2013/02/28/loudness-in-game-audio/); [Sulpha PS4 mastering suite (2015)](https://designingsound.org/2015/06/04/sulpha-the-new-ps4-mastering-suit/); [Audio Media International: mobile loudness, an adaptive approach](https://audiomediainternational.com/mobile-loudness-an-adaptive-approach/)

Weak or vendor sources (opinion, used sparingly)
- Mastering The Mix (a plug-in maker; its guides also promote its products): [how loud should you master](https://www.masteringthemix.com/pages/how-loud-should-you-master), [stem mastering](https://www.masteringthemix.com/pages/how-to-stem-master-a-song)

This repo (read for tool behaviour and measurements): `docs/TOOLS.md`, `docs/listening-loop-prd.md`, `docs/listening-loop-calibration.md`, `docs/handoff/2026-10-08-nova-v2-paused.md`, `ears/loudness.py`, `ears/measure.py`, `ears/profile.py`, `MCP_Server/audio/release.py`, and the reference profiles in `~/Music/AbletonMCP/Ears/refs`. Game repo (values relayed, not re-read here): tetris-nova `src/audio/context.ts` (master chain) and `tools/music/cut_stems.py` (delivery gain curve and trim).

## Open questions / where sources disagree

- **Is -14 LUFS the right target for music-only game stems?** The project spec says -14 LUFS and -1 dBTP at T5, but G.A.N.G.'s whole-game figures are -24 (console) and -16 plus or minus 2 (mobile). A web game is closest to mobile or desktop; music at -14 sits above the mobile band. It depends on how loud the game's effects and bus are. Ask Fred and the game side.
- **What the runtime chain does to the stems.** The compressor (-18 dB, 3:1, attack 5 ms, release 150 ms) and the limiter (-1 dB, 20:1) are relayed from the game's source, not measured on its output. The knee, any other node settings, and the effect on the tier ladder and the loop-seam peaks stay unknown until the game's own output is captured; automatic makeup gain in a Web Audio compressor means the level change is not just gain reduction.
- **Apple Music at -16 or -14.** iZotope and Production Expert say -16; older Apple documents describe Sound Check without LUFS, and older OS versions may still use it.
- **EBU R 128 s2 values changed.** A 2020 report described an interim -18 LUFS general and -16 LUFS for music with a PLR limit of 15 dB; the 2023 document gives -20 to -16 LUFS. Neither is a mastering target.
- **Console -23 or -24.** Sony's early figure was -23 (PS3); G.A.N.G. v03.02 and the PS4 notes say -24.
- **True-peak ceiling.** -1 dBTP (EBU, Spotify), -2 for loud or low-bit-rate material (Spotify, EBU encoder input), -0.3 for lossless (iZotope), versus a vendor guide recommending no true-peak limiting. The standards sources agree; the vendor is the outlier.
- **Club loudness.** Short-term -10 (Shepherd), integrated about -12 (iZotope), short-term -6 "loud lane" (vendor). No standard exists.
- **YouTube Music at about -7 LUFS** comes from one engineer's October 2023 test and may have changed.
- **Mix headroom.** A vendor guide asks for -6 to -3 dB peaks, Shepherd for -16 to -18 LUFS short-term at the loudest, while Ableton's fact sheet notes that Live's 32-bit float tracks cannot clip internally. Treat headroom as a gain-staging habit, not a technical need, except at fixed-point or external stages.
- **Soft clip before the limiter.** Widely used in electronic music, but no authoritative source was found; its audibility is a human judgement.
- **Parameter names.** The names in this digest follow the 12.4.6 parameter dump (`reference/live-12.4.6-device-parameters.md`). Older tables and tutorials say `Gain` for Utility, `Makeup` for Glue and `Maximize` for Limiter; 12.4.6 uses `Output`, `Output` and `Maximize On`. Still `get_device` before `set_device_parameters`. Also unverified: whether True Peak mode ever lets 0.1–0.3 dB through, so measure.
- **Not read in the original:** AES TD1008 / AES77 (paywalled) and ATSC A/85 (not found); their numbers come from secondary sources.
