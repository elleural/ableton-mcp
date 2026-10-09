# Adaptive game music: stems, loops, transitions and loudness

*Digest 10 of the production set. Written 2026-10-08 for AI agents that compose in Ableton Live 12.4.6 through AbletonMCP and cannot hear. Companions: [04-drums-and-low-end.md](04-drums-and-low-end.md) (kick, bass, sidechain), [05-gain-staging-and-metering.md](05-gain-staging-and-metering.md), [06-mixing.md](06-mixing.md), [07-mastering-and-loudness.md](07-mastering-and-loudness.md), [08-arrangement-and-composition.md](08-arrangement-and-composition.md), [09-industrial-ebm-techno-nin.md](09-industrial-ebm-techno-nin.md), [11-listening-without-ears.md](11-listening-without-ears.md), [12-live-devices-reference.md](12-live-devices-reference.md).*

*Labels: **[measured]** = the researcher's own measurement on this project's shipped NEON masters (method in 6.7); **[practice]** = common practice or inference, not tied to one source; unlabelled claims carry a link. Audiokinetic's Wwise manual returned HTTP 403, so Wwise statements are secondary.*

## If you remember five things

1. **Every state the engine can produce is a finished piece.** Split layers by function (bed, motion, weight, energy, melody), put the whole chord story in the lowest tier, and bake only linear processing (EQ, reverb, delay, chorus, width). Sidechain pumping, bus compression, limiting and anything keyed by another stem belongs at runtime or nowhere. [measured] The shipped NOVA pad has a 9-12 dB beat-periodic pump at 130-180 BPM (4.7 dB at 100), so in tiers T1-T2, which have no kick, it pumps to a kick that is not playing yet.
2. **A loop is a steady-state render of an exact number of bars.** Render two or more cycles, keep the second, so tails are folded into the start. Check duration (within 1 ms), start (transient at sample 0), fold and click. Zero-crossing edits repair bad cuts; they are not the recipe.
3. **The crossfade law must match what is crossfaded.** A loop's tail crossfaded into its own head is identical audio: a linear (equal-gain) fade sums to unity, an equal-power fade swells up to +3 dB. [measured] The game's equal-power seam raised the kick's true peak 2.2 dB at every tempo and the T5 sum's by 0.2-0.8 dB at 3 of 9 tempos.
4. **Set loudness on the sum with one shared gain, never per stem.** Uncorrelated stems add in power, so tiers can be predicted; dense, flat-topped stems (what per-stem limiting at the ceiling produces) overshoot more after encoding; each stem should stay within about 1 LU across tempos. [measured] After Opus a dynamic sum moved within about +/-0.5 dB of true peak; a loud, clipped sum rose 0.5-2.1 dB.
5. **Test the states players get, not the full mix.** Subset matrix, a 3-iteration seam render, a mono pass, a 200 Hz high-pass pass, loudness per tier. Passing checks does not mean it sounds good: Fred judges, with labelled, loudness-matched files.

---

## 1. The running example: how this project's engine plays stems

These facts come from the repo (`ears/tiers.py`, `ears/strict.py`, `ears/specs/nova.spec.json`, `docs/handoff/2026-10-08-nova-v2-paused.md`) and the NOVA soundtrack digest in the producer's work folder. They are this game's contract (tetris-nova, a browser game on Web Audio), not generic rules.

- **Stems:** kick (2 bars), perc (4), pad (16, shared by variations A and B), bass, arp, lead (8 each, A and B). Cumulative tiers: T1 pad+arp, T2 +bass, T3 +kick, T4 +perc, T5 +lead.
- **Tempo:** one render per tempo (NEON 100-180 BPM in steps of 10; MAINFRAME 100-130), no time-stretching. A tempo step restarts every stem at bar 1 on a bar line.
- **Playback:** no native loop. A new iteration of each stem starts on a global bar clock; the file is loop body plus a 50 ms tail; the old iteration fades out over 10 ms with an equal-power curve and stops 60 ms after the seam. Stems join mid-loop at their own phase with a one-beat gain ramp.
- **Delivery:** 48 kHz, 24-bit WAV masters shipped as Ogg Opus (48-64 kbps per stem, kick and bass mono). T5 at -14 LUFS (+/-0.5) and at most -1 dBTP; stems plus returns cancel the main mix by 40 dB; each stem within 1 LU of its median across tempos; sub (<120 Hz) mono within 1 dB.
- **Runtime:** music bus (-6 dB, noted as an unverified guess), compressor (-18 dB threshold, 3:1), limiter (-1 dB), master volume. SFX and stingers add on top; some SFX are pitched from the current chord.

---

## 2. Vertical, horizontal, stingers

| Technique | What changes | Strengths | Risks | Examples |
| --- | --- | --- | --- | --- |
| **Vertical layering** (additive or interchangeable synced stems) | gains of parallel stems | immediate; progress or variety without fragmenting the piece ([Phillips](https://www.gamedeveloper.com/game-platforms/pure-vertical-layering-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-)) | one tempo, key and chord sequence for all; you do not control the sum | Destiny's Rift (additive), Final Fantasy XV (acoustic and electric swap) ([Evans](https://etheses.whiterose.ac.uk/27365/)); Dead Space 2 (four layers, one per level of fear) ([Wikipedia](https://en.wikipedia.org/wiki/Adaptive_music)) |
| **Horizontal re-sequencing** (segments, branches, bridges) | which segment plays next | form, key and tempo changes; shorter segments adapt faster ([Evans](https://etheses.whiterose.ac.uk/27365/)) | needs exits, entries, tails; more composing | Spyder (30+ segments in random order), Sackboy boss (three chunks, hidden joins) ([Phillips](https://www.gamedeveloper.com/audio/horizontal-resequencing-and-dynamic-transitions-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-)); iMUSE (markers and branch points) ([Wikipedia](https://en.wikipedia.org/wiki/IMUSE)) |
| **Stingers** | a short cue over or between music | marks events; can be rhythm- and harmony-aware | clashes with the current chord; wrong place in the bar | Sekiro (percussive stingers on strong beats) ([Evans](https://etheses.whiterose.ac.uk/27365/)) |
| **Hybrid** | both | progress from segments, variety from layers, reward from layered cues | most composing and testing | Sackboy "Waltz of the Bubbles": seven segments, a choir layer, a success-melody layer that fits whatever plays ([Phillips](https://www.gamedeveloper.com/game-platforms/hybrid-horizontal-vertical-structure-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-)) |

**Choosing.** [practice] Vertical for intensity inside a stable harmonic bed (this game's tiers); horizontal when form, key or tempo must change; stingers for discrete events on the grid. Real games mix all three.

**Constraints of vertical layering** ([Game Developer](https://www.gamedeveloper.com/audio/adaptive-music-in-competitive-games)): shared tempo, time signature and harmony; a neutral "zero layer" as the bed; each added layer brings something distinct (rhythm, timbre or melody); keep every layer in one DAW project, in folders and buses. The rules can be bent (harmony changes on bar boundaries, an ambient bed tolerates other tempos).

**Engine vocabulary**

| Concept | Wwise (secondary) | FMOD Studio | Godot 4.3+ | This game |
| --- | --- | --- | --- | --- |
| Synced layers | layered tracks, volume by parameter | parallel instruments on one timeline, volume automated | [`AudioStreamSynchronized`](https://docs.godotengine.org/en/stable/classes/class_audiostreamsynchronized.html): up to 32 streams, per-stream volume | one source per stem, gate gain |
| Sequencing | Music Playlist and Switch containers, transition matrix | transition markers and regions to destination markers or loop regions ([docs](https://www.fmod.com/docs/2.02/studio/authoring-events.html)) | [`AudioStreamInteractive`](https://docs.godotengine.org/en/latest/classes/class_audiostreaminteractive.html) clip table | scheduler decides per bar |
| Quantised exit | next bar, beat, grid or cue | regions quantised to 1-2 bars or a beat value from tempo markers (120 BPM, 4/4 if none) | immediate, next beat, next bar, end | bar-line arithmetic |
| Tails across a join | pre-entry and post-exit ([Audiokinetic Q&A](https://www.audiokinetic.com/qa/1367/issue-with-pre-entry-when-using-states-to-change-the-music)) | transition timelines, fade curves | fade mode with length in beats | 50 ms tail, 10 ms crossfade |
| Tempo change | segment grid | tempo markers; "relative" offset keeps the beat position across regions of different BPM | not documented | new render, restart at bar 1 |
| Stingers | triggered at a grid position | instrument with quantisation (1-2 bars, minim, crotchet, dotted crotchet, quaver) | separate scheduled player | scheduled one-shots |

---

## 3. Designing layers so every subset is complete, in tune and clean

### 3.1 Split by function, not by instrument

| Role | Job | Must carry | Must not do |
| --- | --- | --- | --- |
| Bed (pad, drone) | key, chords, space | all chord tones in the mid register (about 165 Hz-2 kHz, Live E2 and up; below that only a root, fifth or octave), width | rely on the bass for its root; put thirds near 55-65 Hz; pump |
| Motion (arp) | pulse, pitch movement | chord tones of the bar's chord | restate the bed's harmony with a clashing voicing |
| Weight (bass, kick) | low end | work alone (bass without kick) and together | carry EQ carves or sidechain that only make sense with the other |
| Energy (perc, hats) | density | rhythm, air | carry sub or pitched content |
| Focus (lead) | melody | rests, a register above the bed | assume a particular bar |
| Events (risers, stingers) | emphasis | grid-aligned starts | commit to a harmony the engine cannot guarantee |

Evidence: Hades' calm states are sometimes just the bass, or bass plus guitar ([Laced Records](https://www.lacedrecords.com/blogs/blog/how-rock-band-influenced-hades-soundtrack)), so one self-sufficient part can be a complete lowest tier. CRI builds stems to "sound good at various states of intensity" and orders them ambience, strings, drums ([CRI ADX2](https://blog.criware.com/?p=2855)). Phillips wants each layer to work as a piece of its own while supporting the whole ([Mix](https://www.mixonline.com/recording/game-composer-winifred-phillips-429243)); Sweet warns against relying on fades alone for emotional shape ([Evans](https://etheses.whiterose.ac.uk/27365/)).

### 3.2 Rules that keep every subset in tune and complete

1. **One source of truth for harmony:** all stems from the same chord track, key and tuning (A = 440 Hz, Live's A3); chords change on bar lines; `analyze_notes` after every edit (in key, chord tones, semitone clashes). Voicings: [08-arrangement-and-composition.md](08-arrangement-and-composition.md).
2. **The lowest tier carries the harmony,** in a register small speakers reproduce. A key estimate on T1 should read the key. A bass that is the only root, or thirds at 55-65 Hz (this project's failure), makes T1 or T2 sound wrong.
3. **Register slots** [practice]: bed chord tones above about 165 Hz (Live E2) in open voicings, with at most a root and fifth below; bass below about 200 Hz with harmonics to 1 kHz; arp 300 Hz-3 kHz; lead 500 Hz-4 kHz; perc above 200 Hz. The game high-passes the pad at 300 Hz in "danger", so the pad needs content above it.
4. **Each layer adds one thing** (rhythm, timbre or range). Two layers with the same job make a louder step, not a richer one.
5. **No stem depends on another for its sound:** no EQ carved against another stem, no sidechain keyed from another, no distortion tuned to mask something.
6. **Phase-entry safe:** a stem can join at any bar, so avoid notes tied across bar lines in stems gated on bar lines (use `get_notes` to flag notes that start before a bar line and end after it).
7. **Low end mono** below about 120 Hz; **distort single notes, not chords** (intermodulation sounds out of tune). Mick Gordon fed one sine wave into four parallel hardware chains ([Thumbsticks](https://www.thumbsticks.com/mick-gordon-crafted-doom-soundtrack/)).
8. **One space:** the same reverb family and similar pre-delay on every stem, so a tier change adds parts and not a new room.

### 3.3 The linearity rule: what may be baked into a stem

Separately processed stems sum to the processed sum only for linear, signal-independent processing. [practice] Reverb, delay, EQ, chorus and width qualify: bake them, with delays and LFOs synced to tempo and LFO periods that divide the loop. Compressors, limiters, gates and saturators do not: use them only on a stem's own signal as part of its sound, never keyed from another stem, never as bus or master processing during the stem render. Mike Cave makes the same point for a bus limiter: it reacts differently on a stem than on the full mix, so bypass it or key it from the full mix ([Cave](https://mikecave.co.uk/?p=994)). `audio.sum_null` (stems plus returns cancel the main mix by 40 dB) catches violations.

### 3.4 Baked sidechain: why it fails when the kick layer is absent

T1 and T2 have no kick, so a pad ducked by a kick still breathes on every beat: a ghost kick. [measured] Beat-folded envelope depth of the shipped NEON pad (the PRD says sidechain is baked in): 4.7 dB at 100 BPM, 11.6 at 130, 10.3 at 160, 9.3 at 180. Synthetic calibration: a steady chord reads 0.3 dB; 3, 6 and 10 dB ducks read 2.8, 5.4 and 8.5 dB.

Ways out, best first:

1. **Compose the gap:** off-beat bass, a rhythmically phrased pad with rests, an arp that avoids the beat. Works in every tier, no engine cost. [practice]
2. **Duck at runtime,** keyed from the kick layer only while it plays. FMOD's Compressor can be keyed by a Sidechain effect ([FMOD](https://www.fmod.com/docs/2.02/studio/effect-reference.html)); in Web Audio it is a gain envelope on the beat clock. Costs engineering; the duck leaves the files.
3. **Render two versions** (clean for tiers without kick, pumped for tiers with) and switch at the kick entry. Doubles files.
4. **A shallow pump (2-3 dB, long release)** only if Fred likes it as groove. Ask first. See [04-drums-and-low-end.md](04-drums-and-low-end.md).

### 3.5 The level ladder

[measured] NEON 130 BPM A set, tiled with the game's seams:

| Tier | Stems | LUFS | True peak | Step |
| --- | --- | --- | --- | --- |
| T1 | pad+arp | -19.5 | -5.5 dBTP | |
| T2 | +bass | -17.2 | -2.5 | +2.3 LU |
| T3 | +kick | -15.3 | -1.7 | +1.9 |
| T4 | +perc | -14.9 | -1.5 | +0.4 |
| T5 | +lead | -14.7 | -1.5 | +0.2 |

- **Loudness cannot see texture layers.** Perc and lead add 0.4 and 0.2 LU yet change the music; judge them by onset rate, spectral change and Fred's ear.
- **Power-sum rule** [measured]: stems add in power, `10*log10(sum 10^(L_i/10))`. The six stems' LUFS (pad -21.4, arp -23.6, bass -20.9, kick -19.7, perc -25.2, lead -26.2) predict T5 at -14.45 against -14.7. Over nine tempos it ran high by 0.1-0.3 LU at 130-180 BPM and 0.6-0.9 at 100-120. Plan with it, then measure.
- **Leave-one-out** at 130: kick 1.6 LU, bass 1.1, pad 1.0, arp 0.6, perc 0.4, lead 0.2.
- The ladder shape (rising loudness, or matched tiers) is a design choice; the spec fixes only T5. Ask before levelling lower tiers. A lower tier louder than the next points to cancellation (low-end phase between kick and bass).

> **For an agent: subset matrix**
> - **Do:** ask which subsets the engine can produce (cumulative tiers here; Hades picks stems at random, so test every singleton, pair and leave-one-out there). After `capture`, mix subsets offline with the game's seams:
> ```python
> from ears import audio, loudness, tiers        # repo root: PYTHONPATH=. python3 x.py
> DIR, BPM = "<folder of stem WAVs>", 130
> BARS = {"pad": 16, "arpA": 8, "bassA": 8, "kick": 2, "perc": 4, "leadA": 8}
> bar = 240.0 / BPM
> stems = {n: tiers.tile(audio.read(f"{DIR}/{n}.wav"), b * bar, 32 * bar).samples for n, b in BARS.items()}
> n = min(len(x) for x in stems.values())
> def report(names):
>     x = sum(stems[k][:n] for k in names)
>     return loudness.integrated(x, 48000), loudness.true_peak(x, 48000)
> ```
> - **Measure per subset:** LUFS, true peak, mono-sum loss, loudness after a 200 Hz high-pass, key estimate, onset rate, third-octave holes. `capture(mode="tap")` gives T1-T5; `capture(mode="solo")` single stems; `bounce(stems=[...])` plus `analyze_audio(path)` for the loudness, peaks, stereo and five spectrum bands of any other subset (the key estimate and onset rate come from the take reports and `meter`).
> - **Bad looks like:** a tier quieter than the one below; a step above about 4 LU; a key estimate that flips at T1; pump depth above 1.5 dB in a tier without kick; a bass that vanishes above 200 Hz.
> - **Ask the human:** "Is T1 alone enough music to stay in for two minutes?" "Quieter lower tiers, or loudness-matched?" Offer labelled files.

> **For an agent: pump depth** (sustained stems only; a rhythmic arp always shows depth)
> ```python
> import numpy as np
> from ears import audio
> def pump_depth_db(path, bpm, bars, win_ms=20, bins=48):
>     a = audio.read(path); x = a.samples.mean(axis=1)[: int(bars * 240 / bpm * a.rate)]
>     w = int(win_ms / 1000 * a.rate); env = np.sqrt(np.convolve(x * x, np.ones(w) / w, "same") + 1e-12)
>     beat = 60.0 / bpm
>     idx = np.minimum((((np.arange(len(x)) / a.rate) % beat) / beat * bins).astype(int), bins - 1)
>     folded = np.array([env[idx == i].mean() for i in range(bins)])
>     return 20 * np.log10(folded.max() / folded.min())
> ```
> Under about 1.5 dB is clean; 3 dB or more is a baked duck. Never remove an existing duck without asking.

---

## 4. Loop craft

### 4.1 Bar-exact lengths

Length is `bars * beats_per_bar * 60 / BPM` seconds. 8 bars at 130 BPM is 14.769231 s, 708,923.08 samples at 48 kHz: not an integer. [measured] The shipped file with its 50 ms tail is 711,323 samples. Schedule iteration k at `k * length` from one clock and never add rounded lengths. A native loop must round to a whole sample (an error of at most half a sample, about 10 microseconds). The spec's tolerance is +/-1 ms on `bars*240/BPM + 0.050 s` (`file.duration`); a larger error means padding from plugin latency, a start offset or a codec (4.5).

### 4.2 Fold the tails into the start

A loop cut while its reverb or delay still rings restarts from silence under a dying tail: a dead-air hiccup even without a click. Folding puts what the previous cycle was ringing into the first milliseconds of the file. Four ways, Live first:

1. **Second-cycle render:** loop the clips two or more cycles and keep the second. `capture` does this; the delivery pipeline records bars 1-34 and cuts from bar 17 for a 16-bar stem.
2. **Live's Export "Render as Loop":** two passes, the tail of the first wrapped into the start, length unchanged ([Live manual](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/)). Add "Include Return and Main Effects".
3. **Manual overlap-add:** render past the end, add the overhang onto the start, trim.
4. **Continuation tail for per-iteration engines:** this game also wants 50 ms after the body, which must be the loop's own continuation (the first 50 ms of the next cycle), not silence and not the next scene.

Preconditions: clip envelopes as long as the loop; LFOs and random modulators synced to the loop length (a random or granular source can never fold exactly; give it a crossfade). [practice]

### 4.3 The seam: zero crossings, DC, fades

- A folded, bar-exact loop is continuous across the seam by construction, because the head is the end's continuation. Moving the cut to a zero crossing would break bar-exactness. [practice]
- Zero-crossing cuts and 1-5 ms fades repair material that is not self-continuous (one-shots, samples, a render that ran into another scene). This project's one-shots end with a 12 ms fade-out; Godot's importer fades trimmed silence for the same reason ([Godot](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_audio_samples.html)).
- DC offset clicks at any hard edge; keep a DC filter or a 20 Hz high-pass on synths that carry it. [practice]

### 4.4 Crossfade laws: why equal power overshoots on identical audio

With weights `w` and `wi` and correlation `r`, mixed power is proportional to `w^2 + 2*w*wi*r + wi^2` ([Fink, Holters and Zölzer, DAFx-16](https://www.hsu-hh.de/ant/wp-content/uploads/sites/699/2017/10/Fink-Holters-Z%C3%B6lzer-2016-Signal-matched-power-complementary-cross-fading-and-dry-wet-mixing.pdf); one author is at Ableton). At the midpoint:

| Law | Weight (each) | Identical (r=1) | r=0.5 | Unrelated (r=0) |
| --- | --- | --- | --- | --- |
| Linear (equal gain), or sin²/cos² | 0.5 (-6 dB) | 0 dB (unity) | -1.3 dB | -3.0 dB dip |
| Equal power (sin/cos) | 0.707 (-3 dB) | **+3.0 dB swell** | +1.8 dB | 0 dB |
| "-4.5 dB" compromise (geometric mean) | 0.596 | +1.5 dB | +0.3 dB | -1.5 dB |

For identical audio an equal-power fade has gain `cos x + sin x`: 0 dB at the ends, +2.3 dB at the quarter points, +3.0 dB in the middle. The paper calls the "equal power for unrelated, linear for related" rule practical but inexact. Cubase and Audacity document the same two modes ([Steinberg](https://archive.steinberg.help/nuendo/v12/en/cubase_nuendo/topics/fades_crossfades_and_envelopes/fades_crossfades_editor_r.html), [Audacity](https://www.audacityteam.org/manual/effects/fading/crossfade-tracks)); equal-power fades can exceed full scale ([Wikipedia](https://en.wikipedia.org/wiki/Fade_(audio_engineering))).

A loop's 50 ms tail crossfaded into its own head is the r near 1 case, so **the game's equal-power fade adds up to +3 dB to any stem with a strong event at the seam.** [measured] Repo `tile()` (game seams) against a linear copy, NEON A set:

| Item | Result |
| --- | --- |
| 110 Hz sine, identical head and tail | sample peak +2.7 dB vs 0 dB |
| Kick true peak, every tempo 100-180 | +2.2 dB |
| Lead true peak | +1.0 dB at 100 BPM, +1.3 at 160, +2.4 at 170, +1.0 at 180 |
| Loudest 2 ms inside the fade, vs linear | +2.5 to +3.0 dB on pad, kick, perc, lead; +0.7 to +2.0 on bass, arp |
| T5 (six-stem) true peak, equal power vs linear | -0.60 vs -1.41 dBTP at 150 BPM; -0.73 vs -1.25 at 180; -1.49 vs -1.72 at 110; identical at the other six |

The sum is hurt only when the loudest transient sits on a seam and several stems' seams coincide (they all coincide every 16 bars). When the engine is not yours:

1. Measure T5 true peak with the game's seams (`tile()`), not just the stems; keep it at or below -1 dBTP after seams and codec.
2. Leave 2-3 dB of peak headroom on stems with a strong beat-1 transient (kick, bass, lead); do not use a limiter for it.
3. Use one shared gain curve (6.2).
4. Ask the developer for a linear or correlation-aware fade for same-variation seams; variation changes (A to B) are partly correlated and can keep equal power. [practice]

Where an engine offers a choice (FMOD fade curves, Godot fade mode and length in beats), use equal gain for same-material seams (a raised-cosine sin²/cos² curve is equal gain with zero slope at its ends, so it adds less edge than linear [practice]) and equal power for different material.

### 4.5 How engines play loops

| Style | Used by | Deliver | Watch for |
| --- | --- | --- | --- |
| **Native loop** | Web Audio `loop`, `loopStart`, `loopEnd` ("at a sample-frame level", [spec](https://webaudio.github.io/web-audio-api/)); Godot Ogg and MP3 loop forward from a loop-begin point ([docs](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_audio_samples.html)); FMOD loop regions | body only, tails folded, no padding | any codec delay shifts the loop; no tail to crossfade |
| **Per-iteration scheduling** | this game; Unity `PlayScheduled` ([docs](https://docs.unity3d.com/ScriptReference/AudioSource.PlayScheduled.html)); look-ahead schedulers ([web.dev](https://web.dev/articles/audio-scheduling)) | body plus continuation tail | seams, overlapping voices, the crossfade law; decisions taken one look-ahead early (100 ms with a 25 ms timer is the article's start; Unity suggests 100-200 ms) |
| **Cue-based segments** | Wwise entry and exit cues with pre-entry and post-exit; FMOD loop and transition regions | file with cues, tails past the exit cue | an FMOD asynchronous instrument plays its whole file after it is untriggered unless Cut is on ([docs](https://www.fmod.com/docs/2.02/studio/working-with-instruments.html)) |

A game schedules per iteration to pick a variation each time, to re-enter in phase after drift (this engine re-syncs a node drifting over 15 ms) and to restart at a tempo step. The price is the seam.

**Codecs and gapless loops.** MP3 adds decoder delay (528 samples) and encoder delay (528 to 1,160 depending on the encoder) ([LAME FAQ](https://lame.sourceforge.io/tech-FAQ.txt)): avoid it for tight loops. Ogg Opus stores a pre-skip and an end granule position, so trimming is sample-accurate ([RFC 7845](https://datatracker.ietf.org/doc/html/rfc7845)). Vorbis is the other safe choice (Wikipedia does not describe its gapless handling; verify decoded length). Opus runs at 48 kHz internally ([Wikipedia](https://en.wikipedia.org/wiki/Opus_(audio_format))): render at 48 kHz.

### 4.6 Seam testing, in order

1. **Length:** decoded samples vs `bars*240/BPM + tail`, within 1 ms (`file.duration`).
2. **Start:** first transient within 5 ms of sample 0 where beat 1 has a note (`file.start`); 20-60 ms means padding.
3. **Fold:** head's first 3 ms vs the body's last 20 ms, within 30 dB (`file.seam`); an unfolded loop reads 40-60 dB down.
4. **Click:** energy above 4 kHz at the seam as the game plays it, at most 6 dB above the material's loudest transient (`file.seam`); equal power alone adds up to 3 dB on a downbeat.
5. **Seam peak:** true peak at the seam vs the interior (4.4), then on the tier sums.
6. **Human:** loop three times and listen to the second join.

> **For an agent: seam checks**
> - **Do:** `analyze_audio(take="latest", strict=True)` returns `file.duration`, `file.start`, `file.seam`, `file.format`; `images=True` adds a seam zoom. To compare laws, run `tiers.tile(...)` with the game's curve and a linear one and compare `loudness.true_peak` of the T5 sum.
> - **Measure:** fold and click in dB, tail length, true peak with and without seams, decoded length after Opus.
> - **Bad looks like:** fold below -30 dB; click above 6 dB; T5 true peak rising more than 0.3 dB when seams are added; decoded length off by more than 1 ms.
> - **Ask the human:** write a 3-iteration render of each suspect stem and of the T5 sum (`tiers.tile`, then `audio.write`), give Fred the paths and name the seam you worry about. Never call a seam "clean" from numbers alone ([11-listening-without-ears.md](11-listening-without-ears.md) for the A/B protocol).

---

## 5. Entries, exits, tempo changes, stingers, pitched SFX

### 5.1 Layer entries and exits mid-loop

- **Enter on a grid line.** FMOD quantises instruments to 1-2 bars or beat values and does not quantise untriggering ([FMOD](https://www.fmod.com/docs/2.02/studio/working-with-instruments.html)); Godot's clips take next beat or next bar ([Godot](https://docs.godotengine.org/en/latest/classes/class_audiostreaminteractive.html)).
- **Ramps** [practice]: bed 1 bar to 1 beat; arp and lead 1 beat; bass an eighth of a beat to one beat, on a downbeat; kick and hats a hard entry on the downbeat. This game uses one beat for all stems.
- **Fade in fast, out slow** (or reverse): an asymmetric parameter seek speed ([FMOD](https://www.fmod.com/docs/2.02/studio/parameters-reference.html)); CRI suggests linear curves with attack and release against abrupt steps ([CRI](https://blog.criware.com/?p=2855)).
- **A stem entering at its own phase must work from any bar** (3.2, rule 6): no held note without an attack.
- **Exits:** fading a stem while its reverb rings cuts the tail. Fade only the dry source and let tails play out, or fade over a bar. [practice]

### 5.2 Tempo changes

- **One render per tempo** (this project: synced delays and LFOs, no tempo automation). Stretching baked stems is a different trade: Live's Complex and Complex Pro suit mixed material, Beats suits drums, Tones suits single lines ([Live manual](https://www.ableton.com/en/live-manual/12/audio-clips-tempo-and-warping/)); the Berklee text warns that tempo changes on compressed audio create artifacts and suit MIDI better ([Berklee](https://online.berklee.edu/takenote/?p=14985)).
- **Restart on a bar line with a strong bar 1;** the game hides the join with a 10 ms crossfade.
- **In FMOD** a "relative" offset leaves a bar at any beat and arrives at the same beat of a bar in a region with another BPM, if the time signatures match ([FMOD](https://www.fmod.com/docs/2.02/studio/authoring-events.html)).
- **Precedents:** Lumines locks its sweep line to each track's tempo, 4/4 with 16 eighth-notes per two bars ([Wikipedia](https://en.wikipedia.org/wiki/Lumines)); Tetris Effect changes tempo with visual switches at line-clear thresholds and found 4/4 at about 135 BPM exciting and 6/4 at 100-120 calming ([Splice](https://splice.com/blog/?p=5870)).
- **Tempo-aware sound design** [practice]: milliseconds do not scale (a 200 ms decay is 1/3 beat at 100 BPM, 0.6 beat at 180), so fast tempos get denser and louder with the same patch. Sync delays and LFOs; shorten reverb decays and compressor releases at fast tempos; expect arps to gain level.

**Consistency across tempos and bands.** [measured] Stem loudness across the nine NEON tempos: perc spans 5.2 LU (-28.1 to -22.9), pad 4.1 (-19.0 to -23.1), bass 2.8, kick 2.4, arp 2.1, lead 1.2, while the sum stays -14.7 to -14.6 LUFS. The pipeline pins the sum with one trim per tempo, so as kick and perc get louder the pad falls 4 LU between 100 and 180 BPM, breaking the within-1-LU rule; T1 alone moves from -17.2 to -20.5 LUFS. The sum and every stem cannot both be pinned unless the sound design is tempo-invariant. Recipe:

1. `capture(tempos="all")` at a milestone; tabulate per-stem LUFS (`audio.tempo_consistency`).
2. Take per-stem targets (the median, or the middle tempo's value).
3. Fix drift at the source with the stem's own gain (per-tempo `set_mixer(volume_db)` then `capture(tempo=N)`, or velocity), never per-stem limiters. Repeat per band (LOW, MID, HIGH) where kick and perc patterns change.
4. Check stems within about 1 LU and the sum within 0.5 LU of -14; if only the sum is off, move the shared delivery trim.

### 5.3 Stingers that fit any bar

- **Quantise, and know the wait.** A beat is 600 ms at 100 BPM and 333 ms at 180; an eighth 300 and 167; a sixteenth 150 and 83. ITU-R BT.1359-1 puts audio-video detectability at about 45 ms early and 125 ms late ([Wikipedia](https://en.wikipedia.org/wiki/Audio-to-video_synchronization)): a 16th grid is near the edge, a beat grid is not transparent. Rez quantises player sounds so imprecise play lands on the beat ([Wikipedia](https://en.wikipedia.org/wiki/Rez_(video_game))).
- **Harmony-safe by construction** [practice]: unpitched impacts, risers, noise; or root and fifth only; or a pedal tone that is a chord tone of every bar it can land on; or one stinger per chord chosen by the engine from the current bar. Phillips' Sackboy success melody fits any segment because it was composed to ([Phillips](https://www.gamedeveloper.com/game-platforms/hybrid-horizontal-vertical-structure-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-)).
- **Length and tail:** keep the pitched part to one beat or less; only an unpitched tail may cross a chord change. This project's one-shots keep a natural tail with a 12 ms fade-out.
- **Loudness:** EBU R 128 s1 treats stingers and bumpers as short-form content (programme -23 LUFS, maximum short-term -18 LUFS, -1 dBTP, loudness range "not applicable") ([EBU](https://tech.ebu.ch/docs/r/r128s1.pdf)). A 1-2 s stinger cannot be judged by integrated LUFS; compare its short-term or peak level with the music under it.

### 5.4 SFX pitched to the music

Rez has player sounds in time and key with the music, and its composers wrote modular sections the game could loop and layer ([PlayStation Blog](https://blog.playstation.com/archive/2017/10/20/classic-levels-deconstructed-tetsuya-mizuguchi-musician-adam-freeland-dissect-rez-infinites-area-5)); Mizuguchi builds the music first and syncs cut sounds to each action ([WCCFTech](https://wccftech.com/interview-tetsuya-mizuguchi-synesthesia-tetris-effect-rez-lumines/)). Here the SFX take the chord of the bar the arp plays, so harmony cannot go atonal without code changes. [practice] Use chord tones so an SFX never makes a semitone with any stem; keep pitch shifts to a few semitones (large shifts change the timbre); avoid reverb tails across a chord change; keep tones above the bass (this game's glyph tones are A-based, 110-1760 Hz); retune the bank if the key moves.

> **For an agent: entries, tempo, stingers**
> - **Do:** flag notes crossing bar lines (from `get_notes`) in stems gated on bar lines; render each stem at three tempos and compare per-stem LUFS; for a stinger, list the chords it can land on and check its pitches against all of them.
> - **Measure:** crossing notes, per-stem LU drift, semitone clashes, quantisation wait in ms at the lowest and highest tempo.
> - **Bad looks like:** a stem that starts a held note without an attack at some bar; drift above 1 LU across tempos; a stinger pitch a semitone from a chord tone in any progression.
> - **Ask the human:** whether a mid-note entry is acceptable, the longest acceptable stinger wait, whether faster tempos should be louder.

---

## 6. Mixing and loudness for stems the engine sums at runtime

### 6.1 Headroom

[measured] The shipped NEON stems peak at about -9 to -11 dBFS each (130 BPM: kick -9.4, perc -9.5, pad -10.2, bass -9.3, arp -10.4, lead -11.1) and sum to -14.7 LUFS and -1.4 dBTP: a peak-to-loudness ratio near 13 dB, roomy next to a club master (the listening-loop skill: a game stem sum is meant to be less dense). Mix the **sum** and leave stems unlimited. Reserve headroom for seams (4.4), codec overshoot (6.6) and SFX on top. Do not mix into the runtime limiter: if it acts, your offline tier levels no longer hold. Units and metering: [05-gain-staging-and-metering.md](05-gain-staging-and-metering.md); limiting and export: [07-mastering-and-loudness.md](07-mastering-and-loudness.md).

### 6.2 One shared gain, not per-stem limiters

Last time the agent put True Peak limiters (about 12 dB of gain into low ceilings), broad EQ cuts and new faders on every stem at once to hit the sum targets; Fred called the result "garbage", and restoring the earlier mix fixed it. Limiting is the part this digest can explain: a limiter on one stem changes its dynamics and its balance against the others, and its gain reduction differs on a stem and on the sum ([Cave](https://mikecave.co.uk/?p=994)). Instead:

1. Render stems unlimited; main chain empty or linear (EQ, Utility).
2. Build the T5 sum with the game's seams and compute one gain curve that holds its true peak at the ceiling (a true-peak limiter model, or a periodic curve over the loop).
3. Apply the same curve to every stem: every subset sees the same reduction and the stems still sum to the limited mix. The game repo's `tools/music/cut_stems.py` does this per tempo with one periodic 2-bar curve on every stem (so any subset stays under -1.2 dBTP), then one trim so the mean A/B sum is -14.6 LUFS (at most tempos the -1 dBTP ceiling sets it); [measured] at 130 BPM its report shows a dip of at most 0.71 dB (mean -0.03 dB) plus a -0.2 dB trim. [07-mastering-and-loudness.md](07-mastering-and-loudness.md) section 5 covers the same ground from the mastering side.
4. Keep the curve small. More than 1-2 dB means a stem is peaky; fix the stem.

In Live the offline route is simplest. A live alternative is Compressors at ratio infinity with an external sidechain from a parallel sum track (Audio From Pre FX, Post FX or Post Mixer; lookahead 0, 1 or 10 ms; no automatic makeup with an external sidechain) ([Live manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/)); it is fiddly and prone to feedback routing. True-peak limiters such as FabFilter Pro-L 2 do not link gain reduction across separate stems; if one accepts an external key, feed it the full mix while bouncing each stem. [practice]

### 6.3 The runtime chain

The engine's own chain reshapes the sum. [practice] A compressor at -18 dB threshold and 3:1 acts on peaks of a -14 LUFS music sum and compresses loud tiers more than quiet ones, narrowing your ladder (T1 peaks near -5.5 dBTP, T5 near -1.5 offline). Measure the engine's real output, not only the stems, and ask for the exact chain. FMOD offers Compressor, Limiter and Sidechain on any bus ([FMOD](https://www.fmod.com/docs/2.02/studio/effect-reference.html)). SFX and stingers add on top of the music.

### 6.4 Targets and which apply

| Source | Figures | Use here |
| --- | --- | --- |
| Sony ASWG (2012, PS3 and Vita) | -23 LUFS +/-2 LU for consoles, -18 LUFS +/-2 handheld; 30+ minutes of representative play, measured as a whole, music and speech not separated; true peak not above -1 dBFS ([interview](https://designingsound.org/2012/07/30/video-games-and-loudness-standards-interview-with-sonys-garry-taylor/), [Designing Sound](https://designingsound.org/2013/02/loudness-in-game-audio/)) | whole-game loudness; the platform numbers have moved, so check the current document |
| ASWG's 120-title study | games -17.8 LUFS, film -23.1, TV -22.5 ([Fast and Wide](https://fast-and-wide.com/blog/46-blog/3716-sound-design-level-up)) | context: games ran about 5 LU louder |
| EBU R 128 s1 | short-form: -23 LUFS, -18 LUFS short-term max, -1 dBTP ([EBU](https://tech.ebu.ch/docs/r/r128s1.pdf)) | stingers, one-shots |
| Spotify | -14 LUFS; -1 dBTP, or -2 dBTP for louder masters because lossy conversion adds distortion ([Spotify](https://support.spotify.com/us/artists/article/loudness-normalization/)) | headroom logic for Ogg |

This project's -14 LUFS covers the music sum only; Sony's figures cover everything the player hears, so music at -14 plus SFX is louder than a console target. The spec is the developer's call; do not change it, but ask how SFX sit on top.

### 6.5 Mono, small speakers, fatigue

- **Mono.** Check each tier with Utility's Mono or the mono-sum loss in `analyze_audio` ([06-mixing.md](06-mixing.md)). [measured] NOVA tiers lose 0.1-0.6 LU in mono, the wide lead 1.9-2.1 LU. Keep everything under about 120 Hz mono.
- **Phones and laptops reproduce little below about 150-300 Hz.** The ear infers a missing fundamental from harmonics ([Wikipedia](https://en.wikipedia.org/wiki/Missing_fundamental)), so give the bass harmonic content at 150-1000 Hz (light saturation on the bass stem alone), not extra sub; no noise on the pad (this producer disliked it). Mick Gordon layered white noise under DOOM's sub-bass for ordinary speakers ([Wikipedia](https://en.wikipedia.org/wiki/Doom_(2016_video_game))), a choice that suited that score. Quiet listening thins bass further ([Wikipedia](https://en.wikipedia.org/wiki/Equal-loudness_contour)); do not compensate with sub.
- **200 Hz high-pass test** (the spec's `phone_highpass_hz`) [measured] at 130 BPM: NEON bass alone loses 0.7 LU, pad 0.9, kick 9.3 (mostly sub); T3 as a whole loses 2.2 LU (2.9 at 180 BPM). Expected for a kick; a bass losing more than about 3 LU has no mid-range identity.
- **TV speakers** sit close together, so wide stereo collapses; check mono and a mid-focused pass. [practice] ASWG chose a 79 dB living-room reference over theatrical 85 ([Designing Sound](https://designingsound.org/2013/02/loudness-in-game-audio/)).
- **Fatigue.** Hades has about 2.5 hours of music for hundreds of hours of play ([Wikipedia, quoting Korb](https://en.wikipedia.org/wiki/Hades_(video_game))); stems are chosen semi-randomly per chamber and the mix thins after combat ([Laced Records](https://www.lacedrecords.com/blogs/blog/how-rock-band-influenced-hades-soundtrack)). Celeste's Raine uses few instruments and simple motifs so loops stay listenable ([VGMonline](https://vgmonline.net/lena-raine-interview-mountain-climbing/)); Spyder's 30+ segments settle into silence now and then ([Phillips](https://www.gamedeveloper.com/audio/horizontal-resequencing-and-dynamic-transitions-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-)). A 2-bar kick at 140 BPM repeats every 3.4 s, a 16-bar pad every 27 s; mixed loop lengths and A/B variations spread repeats. [practice] Hearing peaks at 2-5 kHz ([Wikipedia](https://en.wikipedia.org/wiki/Equal-loudness_contour)), so keep that band restrained on pads and arps and leave room to thin out; verify with a 10-15 minute loop of the tier Fred hears most, not T5.

### 6.6 Codecs and overshoot

Lossy codecs can raise the true peak above the source; Spotify advises 2 dB of headroom for loud masters because Ogg Vorbis and AAC add distortion ([Spotify](https://support.spotify.com/us/artists/article/loudness-normalization/)). Xiph's Opus guidance for music: 64-96 kbps for streaming, 96-128 for storage, 128 kbps VBR "pretty much transparent" ([Xiph](https://wiki.xiph.org/Opus_Recommended_Settings)); Opus is reported better than Vorbis and MP3 at 96 kbps ([Wikipedia](https://en.wikipedia.org/wiki/Opus_(audio_format))); Vorbis q4-q6 is roughly 128-192 kbps ([Wikipedia](https://en.wikipedia.org/wiki/Vorbis)).

[measured] Change in true peak after encode and decode of the NEON A-set sum (ffmpeg libopus VBR, libmp3lame):

| Source | Opus 48k | 64k | 96k | 128k | 192k | MP3 128k | MP3 192k |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 130 BPM dynamic sum at -1.0 dBTP (PLR 12.7 dB) | -0.46 | +0.03 | -0.16 | +0.23 | -0.06 | -0.51 | -0.32 |
| 180 BPM dynamic sum at -1.0 dBTP | +0.53 | +0.14 | -0.16 | -0.07 | +0.34 | -0.26 | -0.17 |
| 130 BPM loud sum (+6 dB, clipped at -1 dBFS, PLR 7.5) | +2.12 | +1.24 | +1.46 | +0.95 | +0.51 | +0.30 | +0.16 |
| 180 BPM loud sum | +1.91 | +1.30 | +1.27 | +1.06 | +0.88 | +0.53 | 0.00 |

The shipped per-stem Opus files (48-64 kbps) moved single stems' true peak by -1.0 to +1.1 dB (pad +0.6 to +1.1) and the A-set sum by -0.43 to +0.58 dB, with loudness changing 0.02 LU or less. Vorbis was not measured (no libvorbis encoder installed). Reading: dense, flat-topped signals overshoot far more than dynamic ones, and low bitrates make it worse. Do not limit stems to the ceiling; leave about 1 dB of true-peak headroom for dynamic material and 2 dB or more for dense material; decode the shipped file and measure again (`analyze_audio(path)` on the decoded file, or `uv run ears acceptance <masters>`). [practice] Mastering engineers use a true-peak meter on the decoded file for the same job (Youlean Loudness Meter, iZotope Insight, Nugen MasterCheck are common choices).

> **For an agent: loudness per tier**
> - **Do:** `analyze_audio(take="latest")` for T1-T5 loudness, true peak, sum null, tempo consistency; predict the ladder first with the power-sum rule. After encoding, decode the Opus files and re-measure.
> - **Measure:** per-tier LUFS and step; T5 -14 +/-0.5 LUFS and at most -1 dBTP with seams; each stem within 1 LU across tempos; sum null at least 40 dB; true-peak change after the codec within 0.6 dB.
> - **Bad looks like:** per-stem limiters or a hot master limiter; a tier quieter than the one below; a stem moving more than 1 LU with tempo; a decoded true peak above the ceiling.
> - **Ask the human:** before touching dynamics on any existing stem. Send a labelled pair loudness-matched within 0.2 LU, 0.3 LU at most (the tolerance in [11-listening-without-ears.md](11-listening-without-ears.md)), one change per pair, and keep the previous version on a muted twin track.

### 6.7 How the [measured] numbers were made

Researcher's runs on 2026-10-08 and 09 on the NEON masters (`tetris-nova/.../public/music/masters/neon/<bpm>/`, A set: kick, perc, pad, bassA, arpA, leadA, 48 kHz 24-bit) with this repo's `ears` package: BS.1770-4 loudness and 4x-oversampled true peak (`ears/loudness.py`); the game's seams from `ears.tiers.tile` and a linear copy; loops tiled 32-48 bars; ffmpeg round trips; pump depth from a 20 ms RMS envelope folded over one beat in 48 bins. One machine, one content type (synthwave): treat figures as orders of magnitude. Scripts stayed in the session scratchpad.

---

## 7. Workflow in Live for game stems

### 7.1 Prototype in Session View

- **One scene per tier or band, one track per stem;** name tracks as the spec does (`kick`, `perc`, `pad`, `bassA`, `arpB`, `leadA`); names must be unique and `analyze_notes` checks `set.names`. Loop lengths in bars match the stems (2, 4, 8, 16); global launch quantisation 1 bar ([Live manual](https://www.ableton.com/en/live-manual/12/launching-clips/)).
- **Audition what the engine does.** The game keeps every stem running on one clock and only gates gain. Fire the T5 scene so all stems run, then build tiers by muting and unmuting tracks (`set_mixer(mute=...)`): phase-locked mid-loop entries. Legato mode lets a clip take the play position of the previous clip in its track, which auditions an A/B variation swap in phase, and Follow Actions (two actions with independent probabilities, including Random) can imitate the engine's random variation pick ([Live manual](https://www.ableton.com/en/live-manual/12/launching-clips/)). `set_clip(legato=True)` sets Legato; the tools cannot set Follow Actions (ask Fred, see [08-arrangement-and-composition.md](08-arrangement-and-composition.md) section 5.4).
- **`capture` is the real check:** it fires each part's clip, records stems and main mix in real time, keeps the second cycle, builds T1-T5 with the game's seams and runs the checks.

### 7.2 Render stems consistently

1. **Same chain, same state:** no device changes between renders; `takes` snapshots device parameters for `restore`.
2. **Same start:** render from 1.1.1 with every clip looping from bar 1; verify the first transient (`file.start`).
3. **Same length:** Live's "All Individual Tracks" yields equal-length files ([Live manual](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/)); `bounce(stems="all")` trims each file sample-exactly. Identical length and start for every stem is also the standard stem-delivery rule ([Cave](https://mikecave.co.uk/?p=994)).
4. **Tails:** Render as Loop, or two cycles and cut the second; use `tail="2 s"` on `bounce` when you need a continuation for the overlap.
5. **Returns and main chain:** switch on "Include Return and Main Effects" (Live 12 calls the master track "Main") so each stem carries its share of reverb and delay; keep the Main chain empty or linear (3.3).
6. **No Normalize** (it lifts each file's highest peak to full scale and destroys relative levels); dither only when reducing bit depth, once, at the end.
7. **48 kHz:** set the Live set to 48 kHz so no conversion is needed (the pipeline otherwise resamples 44.1 to 48 offline). **Convert to Mono** only for stems the engine plays as dual mono (kick, bass here), after the mono check.

Pipeline used for this game: per tempo `set_song(tempo=N)`, `arrange_from_scenes`, `bounce(stems="all", ...)` for bars 1-34 plus 0.5 s, `get_bounce_status(wait=50)`, then the game repo's `tools/music/` scripts: `cut_stems.py` (resample, cut from bar 17, length `bars*240/bpm + 0.050` s, one shared gain curve), `cut_oneshots.py`, `build_manifest.py`, `acceptance.py --strict`. Save the set before any long run. Routing and export detail: [01-live-workflow.md](01-live-workflow.md), [07-mastering-and-loudness.md](07-mastering-and-loudness.md).

### 7.3 Naming

[practice] Names are identical across tempos so the engine swaps folders, not names: `<set>/<bpm>/<stem><variation>.wav` (`neon/130/bassA.wav`). Tempo is a folder; the take id (`neon-140-AB-0006`) carries the version; no "final", "new" or "v2" in file names; lowercase ASCII, no spaces; a sidecar `report.json` records tempo, range, levels and the checks passed. Consistent names are what let Korb's FMOD templates work across pieces ([Game Developer](https://www.gamedeveloper.com/game-platforms/composer-darren-korb-talks-audio-middleware-and-its-importance-to-game-developers)).

### 7.4 Delivery checklist

| Level | Check | Pass |
| --- | --- | --- |
| File | length, start | `bars*240/BPM + tail` within 1 ms; first transient within 5 ms of sample 0 |
| File | seam | fold within 30 dB; click at most 6 dB; true peak with seams |
| File | format, DC | 48 kHz, 24-bit, stereo (mono where the spec says); no DC offset; no mid-file digital silence |
| Tier | ladder, T5 | monotonic, steps 1.5-3 LU early, texture tiers small; T5 -14 +/-0.5 LUFS and at most -1 dBTP with seams |
| Tier | sum null, mono, phone | at least 40 dB; sub mono within 1 dB; bass keeps mid-range identity |
| Set | consistency, notes | each stem within about 1 LU across tempos; `analyze_notes` clean; A and B variations both checked |
| After encode | decode and re-measure | true-peak change within 0.6 dB; decoded length within 1 ms |
| Human | listening | phone, laptop, headphones; seams three times; ten minutes in T1 |

All of this is necessary and not sufficient: the release gate is Fred's ear.

---

## 8. Case studies

| Game | What it does | What to take |
| --- | --- | --- |
| **Tetris Effect** (Hydelic, Enhance) | Music evolves as the player progresses, gameplay tied to the beat; tempo and mood switch with visual changes at line-clear thresholds; 4/4 at about 135 BPM for excitement, 6/4 at 100-120 for calm; the Deep Sea stage took more than 10 compositions; reverb spread on claps to balance what players see and hear ([Splice](https://splice.com/blog/?p=5870), [PlayStation Blog](https://blog.playstation.com/2020/05/28/inside-the-creation-of-tetris-effects-original-soundtrack-out-today/), [Wikipedia](https://en.wikipedia.org/wiki/Tetris_Effect), [VGC](https://www.videogameschronicle.com/features/4-years-of-tetris-effect/)). Mizuguchi: music first, then sounds cut and synced to each action ([WCCFTech](https://wccftech.com/interview-tetsuya-mizuguchi-synesthesia-tetris-effect-rez-lumines/)) | SFX as part of the music; changes tied to events at bar boundaries; one reverb space |
| **Rez, Lumines** (Mizuguchi) | Rez quantises player actions to the beat; levels advance by "layers" that change music, layout and enemies ([Wikipedia](https://en.wikipedia.org/wiki/Rez_(video_game))); composers wrote modular sections ([PlayStation Blog](https://blog.playstation.com/archive/2017/10/20/classic-levels-deconstructed-tetsuya-mizuguchi-musician-adam-freeland-dissect-rez-infinites-area-5)). Lumines ties its sweep to track tempo in 4/4 ([Wikipedia](https://en.wikipedia.org/wiki/Lumines)) | quantise short feedback sounds to a 16th grid; compose in loopable modules |
| **DOOM (2016)** (Mick Gordon) | Brief said no guitars; six to nine months of synths first, then a nine-string guitar merged with a chainsaw sample ([Wikipedia](https://en.wikipedia.org/wiki/Doom_(2016_video_game)), [Thumbsticks](https://www.thumbsticks.com/mick-gordon-crafted-doom-soundtrack/)). A "DOOM instrument": one sine into four parallel chains of pedals, tape echo, spring reverb, mini amp and compressors, mixed and EQ'd into the DAW ([Thumbsticks](https://www.thumbsticks.com/mick-gordon-crafted-doom-soundtrack/)); guitar riffs recorded at double speed on tape and played back at half speed through distortion ([All The Alt Things](https://allthealtthings.com/2022/01/31/mick-gordon-sound-design-as-music/)); white noise under sub-bass for small speakers. Songs are fragments the engine reassembles by activity (exploring, many demons, bosses, low health); the album versions extend them into full songs ([Bethesda](https://bethesda.net/zh-CN/news/inside-the-doom-score-mick-gordon-interview)). GDC 2017 talk exists ([GDC Vault](https://www.gdcvault.com/play/1024068/-DOOM-Behind-the)); only its description was readable | industrial weight comes from processing chains on simple sources, not distorted finished chords; author fragments, deliver the album cut separately |
| **Hades** (Darren Korb, FMOD) | Stems chosen semi-randomly at the start of each chamber; combat adds percussion-heavy parts; afterwards the mix thins to nothing, bass, or bass plus guitar ([Laced Records](https://www.lacedrecords.com/blogs/blog/how-rock-band-influenced-hades-soundtrack)). Pieces move through a synth-pad section, an acoustic section and a hard-rock boss section, with parallel stems reacting to enemies; Pyre used five to eight tracks in almost any combination ([Everything Is Noise](https://everythingisnoise.net/?p=50582)). Korb uses FMOD markers, section transitions and stems, with templates and consistent parameter names ([Game Developer](https://www.gamedeveloper.com/game-platforms/composer-darren-korb-talks-audio-middleware-and-its-importance-to-game-developers)) | a thin state can be one part; random subsets must all work; templates make a system reusable |
| **Celeste** (Lena Raine, FMOD) | Tracks build or strip parts over a chapter; few instruments, simple motifs ([VGMonline](https://vgmonline.net/lena-raine-interview-mountain-climbing/)). Raine planned cues, the sound designer built them in FMOD, designers placed triggers; she calls a game soundtrack and a game album "two wildly different things" ([Destructoid](https://www.destructoid.com/celeste-composer-lena-raine-talks-video-game-music-philosophy-and-upcoming-projects/)). FMOD publishes the Celeste project with its designer's notes ([FMOD](https://www.fmod.com/docs/2.02/studio/appendix-a-celeste.html)) | write the loop for the game and the track for the album separately; open the Celeste project to see a shipped system |
| **Others** | Dead Space 2: four layers for four levels of fear ([Wikipedia](https://en.wikipedia.org/wiki/Adaptive_music)); iMUSE: markers and branching, "a pit orchestra" waiting for events ([Wikipedia](https://en.wikipedia.org/wiki/IMUSE)); Skyrim, Destiny, FFXV, Sekiro ([Evans](https://etheses.whiterose.ac.uk/27365/)); Sackboy and Spyder ([Phillips](https://www.gamedeveloper.com/game-platforms/hybrid-horizontal-vertical-structure-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-)) | layers, branching and stingers combine; the hard part is testing |

---

## 9. Common mistakes, and when to stop and ask

1. Baking sidechain, bus compression or master limiting into stems that can play without the trigger.
2. Per-stem limiters to hit a loudness target; Normalize on stems; levelling every tier to the same LUFS without asking.
3. Equal-power seam on identical audio (+3 dB), or a hard cut with an unfolded tail; leading silence, latency offsets, MP3 padding.
4. EQ carved against another stem (each sounds hollow alone); the chord's root or third only in the bass.
5. Judging a tier by loudness alone; testing only the full mix; per-stem drift above 1 LU across tempos.
6. Stems peaking at the ceiling with no seam or codec margin.
7. Many changes at once, unlabelled auditions, replacing the producer's chosen sound instead of iterating on it.

**Stop and ask Fred** before removing a pump, changing a lower tier's level, touching dynamics on an existing stem, replacing a sound, accepting a seam or changing a tempo's balance. Send a labelled, loudness-matched A/B (within 0.2 LU, 0.3 LU at most), one change per pair, with what you measured and what you cannot judge.

---

## Sources

**Engine and Live documentation**
- FMOD Studio: [Authoring Events](https://www.fmod.com/docs/2.02/studio/authoring-events.html), [Working with Instruments](https://www.fmod.com/docs/2.02/studio/working-with-instruments.html), [Parameters Reference](https://www.fmod.com/docs/2.02/studio/parameters-reference.html), [Effect Reference](https://www.fmod.com/docs/2.02/studio/effect-reference.html), [Celeste appendix](https://www.fmod.com/docs/2.02/studio/appendix-a-celeste.html). Read through the docs site's content CDN; the public URLs are canonical.
- Godot: [AudioStreamInteractive](https://docs.godotengine.org/en/latest/classes/class_audiostreaminteractive.html), [AudioStreamSynchronized](https://docs.godotengine.org/en/stable/classes/class_audiostreamsynchronized.html), [importing audio samples](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_audio_samples.html).
- [Web Audio API spec](https://webaudio.github.io/web-audio-api/); Chris Wilson, [A tale of two clocks](https://web.dev/articles/audio-scheduling); Unity [AudioSource.PlayScheduled](https://docs.unity3d.com/ScriptReference/AudioSource.PlayScheduled.html).
- Ableton Live 12 manual: [managing files and sets (export)](https://www.ableton.com/en/live-manual/12/managing-files-and-sets/), [launching clips](https://www.ableton.com/en/live-manual/12/launching-clips/), [audio clips, tempo and warping](https://www.ableton.com/en/live-manual/12/audio-clips-tempo-and-warping/), [audio effect reference](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/).
- Audiokinetic Q&A, search snippet only (the site returned 403 when opened): [pre-entry and post-exit](https://www.audiokinetic.com/qa/1367/issue-with-pre-entry-when-using-states-to-change-the-music).

**Crossfade, loops, codecs, loudness**
- Fink, Holters, Zölzer, [Signal-matched power-complementary cross-fading and dry-wet mixing (DAFx-16)](https://www.hsu-hh.de/ant/wp-content/uploads/sites/699/2017/10/Fink-Holters-Z%C3%B6lzer-2016-Signal-matched-power-complementary-cross-fading-and-dry-wet-mixing.pdf); [Steinberg crossfade editor](https://archive.steinberg.help/nuendo/v12/en/cubase_nuendo/topics/fades_crossfades_and_envelopes/fades_crossfades_editor_r.html); [Audacity crossfade tracks](https://www.audacityteam.org/manual/effects/fading/crossfade-tracks); [Wikipedia: Fade](https://en.wikipedia.org/wiki/Fade_(audio_engineering)).
- [RFC 7845](https://datatracker.ietf.org/doc/html/rfc7845); [Xiph: Opus recommended settings](https://wiki.xiph.org/Opus_Recommended_Settings); Wikipedia: [Opus](https://en.wikipedia.org/wiki/Opus_(audio_format)), [Vorbis](https://en.wikipedia.org/wiki/Vorbis); [LAME tech FAQ](https://lame.sourceforge.io/tech-FAQ.txt).
- [EBU R 128 s1](https://tech.ebu.ch/docs/r/r128s1.pdf); [Spotify loudness normalization](https://support.spotify.com/us/artists/article/loudness-normalization/); Designing Sound: [Sony's Garry Taylor on loudness](https://designingsound.org/2012/07/30/video-games-and-loudness-standards-interview-with-sonys-garry-taylor/), [Loudness in game audio](https://designingsound.org/2013/02/loudness-in-game-audio/); [Fast and Wide](https://fast-and-wide.com/blog/46-blog/3716-sound-design-level-up).
- [Mike Cave: what is stem mastering](https://mikecave.co.uk/?p=994) (practitioner blog); Wikipedia: [audio-to-video synchronization](https://en.wikipedia.org/wiki/Audio-to-video_synchronization), [equal-loudness contour](https://en.wikipedia.org/wiki/Equal-loudness_contour), [missing fundamental](https://en.wikipedia.org/wiki/Missing_fundamental).

**Adaptive music craft**
- Winifred Phillips (Game Developer): [pure vertical layering](https://www.gamedeveloper.com/game-platforms/pure-vertical-layering-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-), [horizontal resequencing](https://www.gamedeveloper.com/audio/horizontal-resequencing-and-dynamic-transitions-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-), [hybrid](https://www.gamedeveloper.com/game-platforms/hybrid-horizontal-vertical-structure-for-game-music-composers-from-spyder-to-sackboy-gdc-2021-); [Mix interview](https://www.mixonline.com/recording/game-composer-winifred-phillips-429243).
- [Adaptive music in competitive games](https://www.gamedeveloper.com/audio/adaptive-music-in-competitive-games); [Darren Korb on middleware](https://www.gamedeveloper.com/game-platforms/composer-darren-korb-talks-audio-middleware-and-its-importance-to-game-developers); Richard Evans, [Analyzing and Designing Dynamic Music Systems for Games](https://etheses.whiterose.ac.uk/27365/) (York, 2019; chapter 3); [CRI ADX2: vertical layering](https://blog.criware.com/?p=2855); [Berklee Online](https://online.berklee.edu/takenote/?p=14985); Michael Sweet's book, [table of contents](https://www.informit.com/store/writing-interactive-music-for-video-games-a-composers-9780321961587); Wikipedia: [Adaptive music](https://en.wikipedia.org/wiki/Adaptive_music), [iMUSE](https://en.wikipedia.org/wiki/IMUSE).

**Case studies**
- DOOM: [Bethesda](https://bethesda.net/zh-CN/news/inside-the-doom-score-mick-gordon-interview), [Thumbsticks](https://www.thumbsticks.com/mick-gordon-crafted-doom-soundtrack/), [All The Alt Things](https://allthealtthings.com/2022/01/31/mick-gordon-sound-design-as-music/), [Wikipedia](https://en.wikipedia.org/wiki/Doom_(2016_video_game)), [GDC Vault entry](https://www.gdcvault.com/play/1024068/-DOOM-Behind-the).
- Hades: [Laced Records](https://www.lacedrecords.com/blogs/blog/how-rock-band-influenced-hades-soundtrack), [Everything Is Noise](https://everythingisnoise.net/?p=50582), [Wikipedia](https://en.wikipedia.org/wiki/Hades_(video_game)). Celeste: [VGMonline](https://vgmonline.net/lena-raine-interview-mountain-climbing/), [Destructoid](https://www.destructoid.com/celeste-composer-lena-raine-talks-video-game-music-philosophy-and-upcoming-projects/).
- Tetris Effect, Rez, Lumines: [Splice](https://splice.com/blog/?p=5870), [PlayStation Blog (soundtrack)](https://blog.playstation.com/2020/05/28/inside-the-creation-of-tetris-effects-original-soundtrack-out-today/), [WCCFTech](https://wccftech.com/interview-tetsuya-mizuguchi-synesthesia-tetris-effect-rez-lumines/), [VGC](https://www.videogameschronicle.com/features/4-years-of-tetris-effect/), [PlayStation Blog (Rez Infinite)](https://blog.playstation.com/archive/2017/10/20/classic-levels-deconstructed-tetsuya-mizuguchi-musician-adam-freeland-dissect-rez-infinites-area-5), Wikipedia: [Tetris Effect](https://en.wikipedia.org/wiki/Tetris_Effect), [Rez](https://en.wikipedia.org/wiki/Rez_(video_game)), [Lumines](https://en.wikipedia.org/wiki/Lumines).

**Project documents:** `docs/handoff/2026-10-08-nova-v2-paused.md`, `ears/tiers.py`, `ears/strict.py`, `ears/loudness.py`, `ears/specs/nova.spec.json`, `docs/TOOLS.md`, `.claude/skills/listening-loop/SKILL.md`, and the NOVA soundtrack digest (`~/Music/Ableton/NOVA v1 Project/v2-work/soundtrack-digest.md`).

---

## Open questions / where sources disagree

1. **Which crossfade law for loop seams.** Textbooks say equal power for unrelated audio and equal gain for related audio; the DAFx paper calls both rules of thumb and proposes correlation-matched curves. The game's seams mix partly correlated audio (variation changes), so no single law is settled. Linear for same-variation seams and equal power for A/B changes is a proposal, untested in the game.
2. **Bake or not (reverb, sidechain).** CRI says reverb can be baked into seamless stems; others use buses at runtime. This digest bakes linear effects and keeps dynamics out; runtime ducking needs engine support that nobody has confirmed for this game.
3. **How self-sufficient a layer must be.** Phillips wants each layer to stand alone; Hades' random stems imply any subset works; texture stems (perc, lead here) are not complete alone. This digest requires only the lowest tier to be complete; Fred should judge T1.
4. **Loudness targets.** Sony's whole-game figures date from 2012; browser games have none; this project's -14 LUFS is music only. Whether SFX and the runtime compressor make the real level too loud is unknown without measuring the game's output.
5. **Opus bitrates.** Xiph recommends 64-96 kbps for streaming; the game ships 48-64 per stem. No listening test was run; the data show peak behaviour only, and Vorbis was not measured.
6. **The runtime compressor.** Its effect on the tier ladder and seam peaks was reasoned, not measured.
7. **Not reached:** Wwise's own manual (403), A Sound Effect and Designing Music NOW (no result or no resolvable site), and the contents of the DOOM and Hades GDC talks (video only).
8. **What the masters represent.** The NEON masters come from the earlier synthwave pass; the industrial recomposition is paused. The measurements describe seam, codec and level behaviour, not the sound Fred wants.
