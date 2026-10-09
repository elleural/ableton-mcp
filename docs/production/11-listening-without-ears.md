# Listening without ears: judging audio with measurements and a human in the loop

Research digest for AI agents that make music in Ableton Live 12.4.6 through AbletonMCP. Written 2026-10-08.
Companion files: [05-gain-staging-and-metering.md](05-gain-staging-and-metering.md) (meters, LUFS targets),
[06-mixing.md](06-mixing.md), [07-mastering-and-loudness.md](07-mastering-and-loudness.md),
[08-arrangement-and-composition.md](08-arrangement-and-composition.md) (voicing, low interval limits),
[03-sound-design-recipes.md](03-sound-design-recipes.md), [12-live-devices-reference.md](12-live-devices-reference.md),
[00-agent-playbook.md](00-agent-playbook.md).

Pitch names follow Live (C3 = MIDI 60), so 55 Hz is A0 (MIDI 33), 110 Hz is A1, 220 Hz is A2, 440 Hz is A3. Items marked
"computed" are my own calculations from published formulas or from this repo's stored numbers; they are reproducible
and are illustrations, not measurements of the producer's sets.

## If you remember five things

1. **Metrics find defects and tell you whether two versions differ. They do not tell you which one sounds better.** The
   human decides "better". Your job is to make that decision cheap, fair and reversible.
2. **Never choose a sound by its distance to a full-mix spectrum.** A mix is a sum of parts and no single part has the
   sum's shape. In a synthetic test (section 5.2, illustrative figures) a hollow "sub saw plus noise" patch landed 13.8 dB
   (RMS over third-octave bands) from a real reference's shape and a proper big saw pad 19.9 dB, so the ranking picked the
   wrong sound. Use a property checklist built from the producer's own words, then let him choose among the survivors.
3. **Loudness-match every comparison, yours and his** (within 0.2 LU, 0.3 LU at most), label what plays, keep clips near 10 s,
   change one variable, and never overwrite the sound he chose. The louder version wins, and gaps of 0.1 to 0.2 dB are
   reported to bias judgement (this repo's measurement noise on a part is 0.07-0.26 LU, which is why 0.2 LU is the working limit).
4. **Translate adjectives into hypotheses, then into one measurement and one small change.** "Hollow", "thin", "airy" and
   "bigger" each have several causes. When a measurement cannot decide, ask a specific question (section 7).
5. **Low-register physics produces the "out of tune / flangy / hollow" complaints.** Close thirds in the low register beat
   and roughen: a minor third at 55/65 Hz has fundamentals 10 Hz apart (a tenth of a critical band) and partials
   beating at 3 Hz, and 08 puts the floor for close major thirds near E2 (165 Hz). Saturating a chord sum creates notes that
   are not in the chord. Chorus on noise makes moving comb filters. Check voicing, mono-sum loss and off-grid power before
   the human hears it.

## 1. What your tools can and cannot tell you

Every measurement answers a narrow question about a rendered signal. The repo's own rule applies: passing every check does
not mean it sounds good, and the human listening check stays the release gate (`.claude/skills/listening-loop`, rules 7-8).

| Tool | Reads | Blind to |
| --- | --- | --- |
| `get_meters` | momentary post-fader peak of every track, return and master (dBFS, held 1 s, only while the transport plays) | loudness, tone, anything over time; a peak is not a level |
| `bounce` then `analyze_audio(path)` (`sections="locators"` splits by locator) | integrated, short-term max and momentary max LUFS; LRA; true peak; sample peak, RMS, crest; clipped samples; L/R correlation and width; energy share in five bands (below 60, 60-250, 250-2k, 2-6k, above 6k Hz); loudness curve | pitch, tuning, noise share, per-band stereo, comb filtering, roughness; LRA on clips under 60 s |
| `capture`, `analyze_audio(take=)`, `compare`, `takes` | the NOVA spec's checks on tier sums T1-T5: third-octave balance, mono-sub loss below 120 Hz, key estimate, sum null, tempo consistency, masking overlap, phone survival; loudness-matched deltas against the best take with measured noise floors | anything outside the spec; the "fuzzy" numbers are information only |
| `meter(source="live")`, `meter(source="external")` | what the Mac plays now through the interface loopback, 3 to 120 s: LUFS and true peak (live only) plus the level-independent profile (third-octave, bands, LRA, PLR, crest, width, correlation, mono-sub loss, onset rate, tempo, key) | needs playback; "external" has no absolute level |
| `ref`, `compare(take, "refs")` | each reference's profile stored as numbers; a take placed inside, above or below the range the references span | two of the four Nine Inch Noize tracks are stored at the time of writing; lossy stream; a direction, not a target |
| `analyze_notes` | exact MIDI checks: key, chord tones on beats, clashes within a sixteenth, grid, rests | what the sound does with the notes: register, beating, saturation, chorus |

`bounce` and `capture` play audibly in real time, so tell the human before you start.

**Not in the toolset: compute from a bounced WAV.** Spectral centroid, rolloff and flatness, per-band L/R correlation, the
mono-sum loss curve (comb detection), periodicity above 400 Hz (noise share), off-grid power share (intermodulation), cents
error and beat rate. Load a
file with `ears.audio.read(path)` (numpy, run with `uv run python`); librosa is not installed. Essentia defines related
descriptors: [inharmonicity](https://essentia.upf.edu/reference/std_Inharmonicity.html) (0 to 1, energy-weighted distance
of partials from multiples of f0), [odd-to-even harmonic energy ratio](https://essentia.upf.edu/reference/std_OddToEvenHarmonicEnergyRatio.html)
and [sensory dissonance](https://essentia.upf.edu/reference/std_Dissonance.html) (0 to 1). These six functions were
tested on synthetic signals; the rest of this file says what to read from them.

```python
import numpy as np
from scipy import signal

def band_correlation(L, R, fs, edges=(20, 120, 250, 500, 1000, 2000, 4000, 8000, 16000)):
    """Pearson correlation of L and R inside each band: 1 identical, 0 unrelated, below 0 out of phase."""
    out = {}
    for lo, hi in zip(edges[:-1], edges[1:]):
        sos = signal.butter(4, [lo, min(hi, 0.45 * fs)], "band", fs=fs, output="sos")
        l, r = signal.sosfiltfilt(sos, L), signal.sosfiltfilt(sos, R)
        out[f"{lo}-{hi}"] = float(l @ r / np.sqrt((l @ l) * (r @ r) + 1e-30))
    return out

def mono_sum_loss(L, R, fs, nfft=8192):
    """dB lost when L+R are summed, per frequency: 0 none, about 3 unrelated channels, spikes = comb notches."""
    f, pll = signal.welch(L, fs, nperseg=nfft)
    _, prr = signal.welch(R, fs, nperseg=nfft)
    _, plr = signal.csd(L, R, fs, nperseg=nfft)
    return f, 10 * np.log10((0.5 * (pll + prr) + 1e-30) / (0.25 * (pll + prr + 2 * plr.real) + 1e-30))

def off_grid_share(x, fs, f0s, lo=30, hi=1500, tol_cents=15, floor_db=-50):
    """% of the power in lo..hi Hz (lines within floor_db of the peak) NOT within tol_cents of a harmonic of any f0 in
    f0s: intermodulation products, aliasing, inharmonic partials. Compare the same chord before and after an effect.
    One f0's grid covers about 0.00116 x tol_cents x k of the axis near harmonic k, so keep hi near 10 x the lowest f0
    (the grid saturates above that) and use a long window."""
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / fs)
    on = np.zeros(len(f), bool)
    for f0 in f0s:
        for k in range(1, int(hi / f0) + 2):
            on |= np.abs(1200 * np.log2(np.maximum(f, 1e-9) / (f0 * k))) < tol_cents
    band = (f >= lo) & (f < hi) & (X > X.max() * 10 ** (floor_db / 10))
    return 100 * X[band & ~on].sum() / X[band].sum()

def hf_periodicity(x, fs, f0, hp_hz=400.0):
    """Normalised autocorrelation of the signal above hp_hz at the lag of f0 (searched +/-1.5 %): about the share of that
    band's power that is a harmonic series of f0. 1 = clean, 0.5 = as much noise as tone, 0 = noise. One note at a time."""
    y = signal.sosfiltfilt(signal.butter(4, hp_hz, "high", fs=fs, output="sos"), x)
    ac = np.fft.irfft(np.abs(np.fft.rfft(y, 2 * len(y))) ** 2)[:len(y)]
    lag = fs / f0
    return float(ac[int(lag * 0.985):int(lag * 1.015) + 1].max() / ac[0])

def harmonics_resolved(x, fs, f0, fmax=2000.0, within_db=40.0, above_floor_db=10.0):
    """(count, expected): harmonics k*f0 below fmax that stand within within_db of the strongest one and
    above_floor_db over the local median of the spectrum."""
    X = 20 * np.log10(np.abs(np.fft.rfft(x * np.hanning(len(x)))) + 1e-12)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    ks = np.arange(1, int(fmax / f0) + 1)
    peaks = np.array([X[(f >= k * f0 * 0.985) & (f <= k * f0 * 1.015)].max() for k in ks])
    n = sum(bool(p > peaks.max() - within_db and p > np.median(X[(f >= 0.5 * k * f0) & (f <= 1.5 * k * f0)]) + above_floor_db)
            for k, p in zip(ks, peaks))
    return n, len(ks)

def centroid(x, fs, power=False):
    """Spectral centroid in Hz. librosa weights by magnitude (power=False); power weighting reads several times lower."""
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    w = X ** 2 if power else X
    return float((f * w).sum() / w.sum())   # cents between two pitches: 1200 * np.log2(f / f_ref)
```

Frequency resolution is fs/N. Two partials 10 Hz apart (A0 and C1) need bins of 2.5 Hz or finer, so use windows of at
least 2^15 samples (0.74 s at 44.1 kHz) on sustained notes. Short windows smear exactly the register where trouble lives.

## 2. Vocabulary to measurement

Ranges are practitioner consensus and they disagree by up to a third of an octave (see the end of the file). Treat each as
a search region, not a rule. The thresholds are starting values taken from the stored references and from synthetic tests
(sections 3 and 5.2), not calibrated limits. A word is a hypothesis: confirm with the signature before changing anything,
and change one thing by a small step (EQ 1-3 dB, mix controls 10-20 points).

| Word | Where, what it is | Signature to measure | Usual causes | First small change (Live) |
| --- | --- | --- | --- | --- |
| muddy | 150-400 Hz; iZotope lists 200-500 Hz on kick, piano and strings, 300-500 Hz on bass, below 500 Hz on effect returns ([iZotope](https://www.izotope.com/en/learn/eq-cheat-sheet)) | third-octave 160-400 Hz more than 3 dB above the 125 Hz and 800 Hz bands and above the reference range; many stems active in the same bands (masking overlap); chords in the low register (4.3) | pad, bass and kick sharing 100-300 Hz; reverb without low cut; close thirds below E2; saturated chords | EQ Eight bell -2 dB at 200-300 Hz, Q about 1, on the part that owns less of that band; a reverb low cut near 250 Hz (Hybrid Reverb `EQ Lo Type` Cut with `EQ Lo Freq`, or an EQ Eight high-pass after the reverb); open the voicing |
| boomy | 60-200 Hz, one resonant bump that moves with pitch | one third-octave band 6 dB or more above both neighbours, long decay | sustained bass/kick fundamentals on one note; room | narrow cut -3 dB (Q 3-4) at that fundamental, or shorter amp release; retune the kick to the key |
| boxy | 250-800 Hz depending on source (kick 200-500, snare 300-500, brass 500-800 per iZotope; other guides say 400 or 600-700) | narrow bump (Q above 2) of 6 dB or more | resonance, comb filtering, unfiltered pad low-mids | find it by sweep with the human (7.3), cut -2 to -3 dB |
| honky, nasal | 500 Hz-1.5 kHz (vocal "nasal" 500-1.2k, brass "honk" 500-800 per iZotope); narrow pulse waves are described as thin and nasal ([Wikipedia](https://en.wikipedia.org/wiki/Pulse_wave)) | bump at 700 Hz-1.2 kHz; pulse width far below 50 % | PWM, filter resonance | bell -2 dB at the bump; widen pulse toward saw; less resonance |
| hollow | missing 150-600 Hz body, or a notch pattern | any of: 200-800 Hz band 6 dB or more below both the 100 Hz and 1-2 kHz bands; odd-to-even harmonic energy ratio far above 1 (square, 50 % pulse; [Essentia](https://essentia.upf.edu/reference/std_OddToEvenHarmonicEnergyRatio.html)); deep notches in the mono-sum loss curve; harmonics resolved below 2 kHz under 20 % of expected | scooped EQ, odd-harmonic waveform, stereo delay or chorus collapsing in mono, inverted flanger feedback (Live's [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#phaser-flanger) itself calls that sound hollow), sub-plus-noise patches | test Utility `Mono` first. Hollow only in mono: remove the delay/chorus on that layer. Otherwise low shelf +2 dB near 200 Hz or switch the waveform to saw |
| thin | weak 100-300 Hz and fundamental | low 100-300 Hz share against the reference; mono-sum loss above 3 dB below 300 Hz | high-passed source, polarity or phase cancelling between layers ([Sonnox](https://sonnox.com/articles/drum-phase-alignment-when-to-nudge-flip-or-leave-alone) notes phase problems pose as thin or hollow), narrow pulse | Utility polarity test (`Left Inv`, `Right Inv`); layer one octave down at -8 dB; shelf +2 dB at 150-250 Hz |
| harsh | 2-5 kHz, where hearing is most sensitive (Wikipedia: 2-5 kHz); iZotope: electric guitar 2-5k, hats 3-7k, cymbals near 4k | 2.5-4 kHz above the 1 kHz band by more than the reference; non-harmonic lines above 2 kHz (aliasing, intermodulation) | saturation, aliasing, resonance, over-bright layers | bell -2 dB at 3-4 kHz, Q about 1.5; 3 dB less Saturator `Drive` (and ask Fred to switch Hi-Quality on: it is a context-menu option, not a parameter); low-pass near 10 kHz |
| sibilant | 5-10 kHz bursts | 5-9 kHz exceeds the 2 kHz band by more than 10 dB in short bursts | noisy hats, bright saturation | Multiband Dynamics high band or a narrow dip; high shelf -2 dB |
| airy | 8-16 kHz; "air" is positive (iZotope: 8-12k on cymbals, 10k+ on vocals) but "breathy, raspy" is not | share above 6 kHz; `hf_periodicity` below 0.7 (0.5 means as much noise as tone); flatness 2-8 kHz above 0.2 | noise oscillators, noise-heavy presets, bright reverb | ask which meaning. Remove: noise layer -6 dB, Auto Filter low-pass 5-6 kHz. Add: high shelf +2 dB at 10-12 kHz on a tonal layer |
| dull, dark | lacking 3-8 kHz and above | lower high-band share and steeper slope than the reference (the stored Nine Inch Noize tracks already fall 2.4-3.2 dB/oct above 1 kHz in third-octave level, see 3.2) | low-pass, no upper harmonics, saturation placed after the filter | high shelf +2 dB at 6 kHz or open the cutoff 10-20 %; add harmonics before the filter |
| warm | 100-400 Hz fullness, soft top, even-order harmonics (folk wisdom, weak evidence); Live's Warmth knob adds slight distortion and filtering | +1 to +3 dB at 150-300 Hz, -2 to -4 dB above 8 kHz against neutral; rising 2nd and 3rd harmonic | tube/tape-style saturation | Saturator `Type` Soft Sine on a single-note part (not on a chord), `Dry/Wet` 20-30 %; low-mid shelf +1.5 dB |
| bright | 3-8 kHz and above | higher absolute spectral centroid: it tracks rated brightness better than centroid divided by f0 (r = 0.51 against 0.03, [Schubert and Wolfe 2006](https://newt.phys.unsw.edu.au/~jw/reprints/SchubertWolfe06.pdf)) | open filter, harmonics, noise | compare at the same pitch; shelf or cutoff |
| wide | width comes from content above about 200 Hz; below 80 Hz lateral localization is hard or impossible ([Wikipedia](https://en.wikipedia.org/wiki/Sound_localization)) | per-band L/R correlation below 0.5 above 200 Hz while 0.9 or more below 120 Hz; width (side/mid RMS) 0.27-0.51 on the stored references; mono-sum loss near 3 dB in the mids | decorrelated voices, stereo effects | Utility `Stereo Width` 120-150 % with `Bass Mono` On at `Bass Freq` 120-150 Hz |
| phasey, flangy | 100 Hz-8 kHz; notches spaced 1/delay (4.5) | regularly spaced deep notches in the mono-sum loss curve, moving if modulated; band correlation near 0 or negative; worst on noise | Chorus-Ensemble, Phaser-Flanger, Haas delays under 30 ms, offset duplicates, phase-synced unison | Dry/Wet down 20 points, Amount halved, Feedback 0, Delay Time fixed (not Auto), high-pass 150-300 Hz; keep chorus off noise layers |
| out of tune | pitch error of 10-25 cents or more between sustained notes ([Cent](https://en.wikipedia.org/wiki/Cent_(music)): about 5-6 cents noticeable in good conditions, 25 reliable); beating partials at 1-15 Hz; intermodulation lines not in the chord | cents of spectral peaks against 12-TET with A = 440 Hz (Live's A3); envelope modulation at the beat rate; off-grid share; `analyze_notes` | low-register thirds, unison detune above +/-10 cents, saturated chord sums, sub root different from the bass root | rewrite the voicing (4.3), cut detune, saturate per voice or per band |
| beating | amplitude pulsing at 0.5-15 Hz; roughness above about 20-30 Hz ([UNSW](https://www.animations.physics.unsw.edu.au/jw/beats.htm)) | sub-band envelope spectrum peak at the rate; a partial at f Hz detuned c cents beats at 0.000578 x c x f Hz | detune, near-unison notes, tuning | retune; or keep 0.3-2 Hz on purpose for slow motion |
| big, heavy, clean (the producer's words) | big: a long low root plus a full harmonic series and width above 200 Hz. heavy: weight at 40-120 Hz and low-mid mass. clean: no foreign pitches or noise | roots 41-49 Hz; harmonics resolved to about 2 kHz; `hf_periodicity` 0.85 or more; off-grid share near 0 %; correlation 0.9 or more below 120 Hz, low above 200 Hz; smooth roll-off above 2 kHz | | see 03-sound-design-recipes.md |

## 3. What the metrics mean, and normal ranges

### 3.1 Loudness family

| Metric | Definition | What it means to a listener | Notes and ranges |
| --- | --- | --- | --- |
| Momentary (M) | 0.4 s sliding window, not gated ([EBU Tech 3341](https://tech.ebu.ch/docs/tech/tech3341.pdf)) | the last beat | follows kick surges; use for peak density |
| Short-term (S) | 3 s sliding window, not gated | the last phrase | the sensible meter for a 2-8 bar loop |
| Integrated (I) | whole duration, gated: blocks of 400 ms, 75 % overlap, absolute gate -70 LUFS, then relative gate 10 LU below | "programme loudness", what streaming normalises | K-weighted (section 4.1). Silence and quiet sections drop out |
| Loudness range (LRA) | 95th minus 10th percentile of short-term values, after a -70 LUFS gate and a -20 LU relative gate ([Tech 3342](https://tech.ebu.ch/docs/tech/tech3342.pdf)) | macroscopic loudness variation | [EBU R 128](https://tech.ebu.ch/docs/r/r128.pdf) advises against it under 1 min; Tech 3341 flags it unstable for the first 60 s; leading or trailing silence inflates it. Stored references: 3.1-3.6 LU over full sections, 5.5-6.4 LU over whole tracks |
| True peak | peak of the oversampled waveform (4x from 48 kHz to 192 kHz, [BS.1770-5](https://www.itu.int/rec/R-REC-BS.1770-5-202311-I/en)) | whether decoding or conversion will clip | R 128 caps programmes at -1 dBTP; Spotify advises -1 dBTP for -14 LUFS masters and -2 dBTP if louder ([Spotify](https://support.spotify.com/us/artists/article/loudness-normalization/)). Loop crossfades add overs |
| PLR | true peak minus integrated loudness; EBU calls it a measure of micro-dynamics ([Tech 3343](https://tech.ebu.ch/docs/tech/tech3343.pdf)) | how much transient life is left | SOS reviewer Hugh Robjohns calls readings below 8 dB generally detrimental ([SOS](https://www.soundonsound.com/reviews/meterplugs-perception)); Ian Shepherd treats it as the LUFS-based successor of crest factor ([Production Advice](https://productionadvice.co.uk/plr/)); stored references: 6.5-13 dB |
| Crest factor | sample peak minus unweighted RMS; depends on the RMS window (SPAN uses 50 ms for its maximum, [Voxengo](https://www.voxengo.com/files/userguides/VoxengoSPAN_en.pdf/getbyname/Voxengo%20SPAN%20User%20Guide%20en.pdf)) | punch against density | stored references: 7.0-14.7 dB. Always state the window |

One LU equals one dB. A 1 kHz in-phase stereo sine peaking at -18 dBFS reads -18.0 LUFS. Streaming targets: Spotify -14
(Quiet -19, Loud -11), Apple Music -16, YouTube and Amazon -14, Tidal -14, Deezer -15
([iZotope](https://www.izotope.com/en/learn/mastering-for-streaming-platforms)); see 07 for what to do about them. Repeat
noise in this repo: 0.07 LU on a full mix, up to 0.26 LU on a synth part with free-running oscillators
(`docs/listening-loop-calibration.md` section 2), so smaller differences are not differences.

### 3.2 Spectral family

**Third-octave balance and tilt.** A pink-noise spectrum falls 3 dB per octave in power density and reads flat on
third-octave or octave bands ([Wikipedia](https://en.wikipedia.org/wiki/Pink_noise)). Spectrum analysers differ in
convention, so always say which. Voxengo draws its spectrum with a 4.5 dB/oct tilt because the power spectrum of
contemporary music follows that slope closely ([Voxengo guide](https://www.voxengo.com/files/userguides/VoxengoPrimaryUserGuide_en.pdf/getbyname/Voxengo%20Primary%20User%20Guide%20en.pdf)).

| Convention | Pink noise | Typical contemporary music | Stored Nine Inch Noize references (computed) |
| --- | --- | --- | --- |
| FFT power density, dB/oct | -3 | about -4.5 | 100 Hz-1 kHz: -3.8 to -4.1; 1-10 kHz: -5.4 to -6.2 |
| third-octave band level, dB/oct (add 3 to the line above) | 0 | about -1.5 | 100 Hz-1 kHz: -0.8 to -1.1; 1-10 kHz: -2.4 to -3.2 |

So the references follow the usual slope up to 1 kHz and are darker above it. They also hold most of their power in the
lowest bands: 63-65 % of the energy of the full sections (44-50 % of the sparse ones) sits in the third-octave bands up
to 80 Hz (computed from `~/Music/AbletonMCP/Ears/refs/*.json`; Vessel and She's Gone Away only, measured through
Spotify and the loopback).

**Genre tonal targets.** iZotope's Tonal Balance Control derives 12 genre curves by machine learning on thousands of
masters, shows a peak below 100 Hz with a gentle slope down, works on full mixes only, and says not to aim for ruler-flat
([iZotope](https://www.izotope.com/en/learn/what-is-tonal-balance-in-mixing-and-mastering)). Use targets as a band to sit
within, never as a curve to match.

**Centroid, rolloff, flatness.** librosa defines the centroid on the magnitude spectrogram with n_fft 2048 and hop 512,
rolloff at 85 % of the energy, and flatness as geometric over arithmetic mean of power from 0 (tonal) to 1 (noise)
([source](https://github.com/librosa/librosa/blob/main/librosa/feature/spectral.py)). Definitions change the answer by
large factors. For the stored references the power-weighted centroid is about 0.3-0.6 kHz, while the magnitude-weighted one
is about 2.7-3.5 kHz (computed from the third-octave bands, approximate). Brightness follows the absolute centroid, not
centroid divided by f0 ([Schubert and Wolfe](https://newt.phys.unsw.edu.au/~jw/reprints/SchubertWolfe06.pdf)), so compare
centroids only at the same pitch and with the same definition, and only on one source at a time.

### 3.3 Space and density

| Correlation | Width (side/mid RMS) | Mono-sum loss | Reading |
| --- | --- | --- | --- |
| 1.0 | 0.00 | 0 dB | mono |
| 0.9 | 0.23 | 0.2 dB | very narrow |
| 0.7 | 0.42 | 0.7 dB | typical full mix |
| 0.5 | 0.58 | 1.3 dB | wide |
| 0.0 | 1.00 | 3.0 dB | unrelated channels |
| -0.5 | 1.73 | 6.0 dB | phase trouble |

Computed for equal-power channels (the repo's `width` and `mono_sub` definitions). The stored references measure
correlation 0.58-0.86, width 0.27-0.51 and sub mono-sum loss 0.02-0.62 dB. Voxengo calls 0 to 1 the acceptable
correlation range, notes that uncorrelated material at equal peak level sounds about 1.25 dB louder, and averages over
500 ms. Mastering The Mix puts the line at 100-150 Hz for keeping bass centred
([guide](https://www.masteringthemix.com/pages/how-to-use-reference-tracks)); Live's Utility has Bass Mono from 50 to 500 Hz.
Whole-band correlation hides comb filtering (section 5.4), so also look at the per-band values and the loss curve. L/R
correlation is a signal-side proxy for the interaural correlation that governs apparent width (textbook psychoacoustics,
not re-verified here); speaker crosstalk makes the same file sound narrower than on headphones, so ask which one he used.

**Onset density.** The repo detects onsets by spectral flux, 30 ms minimum gap. The stored references give 1.8-3.4
onsets per second. One voice at n notes per beat gives about n x BPM / 60 per second (eighths at 93 BPM: 3.1), but near-
simultaneous hits merge.

> **For an agent: which measurement for which question**
>
> | Question | Use | Flag when (starting values) |
> | --- | --- | --- |
> | Did my change alter the level? | `bounce` both versions over the same bars, `analyze_audio`; or `meter(source="live")` | integrated LUFS differs by more than 0.2 LU. Match first, then listen |
> | Clipping or overs? | `get_meters` `over_0db`; `analyze_audio` notes | any clipped sample; true peak above -1 dBTP on a sum |
> | Is the low end solid and mono? | `band_correlation` 20-120 Hz on the stem; mono-sub loss from `capture` | correlation below 0.9; loss above 1 dB (the spec's limit) |
> | Wide but mono-safe? | `analyze_audio` width and correlation; `mono_sum_loss` curve | notch deeper than 10 dB between 200 Hz and 8 kHz |
> | Noisy, airy, raspy? | `hf_periodicity` on a held note, `analyze_audio` spectrum `high` | periodicity below 0.7 on a tonal source |
> | Foreign pitches after an effect on a chord? | `off_grid_share` before and after | a rise of more than about 1 % |
> | Are the notes safe? | `analyze_notes`, then the interval check in 4.3 | any fail; close major thirds below E2 or minor thirds below D#3 (derived floors in 08 section 2.5) |
> | In tune? | cents of FFT peaks against 12-TET | more than 10 cents between sustained notes without a reason |
> | Close to the references? | `compare("latest", "refs")`, `ref(action="list")` | outside the range they span; dynamics are information only |
> | Did the last change regress anything? | `compare("latest", "best")` | any regression beyond the noise floor |
> | Is it better? | the human, with a labelled loudness-matched A/B | never from metrics alone |

## 4. Psychoacoustic basics an agent must know

### 4.1 Equal loudness and K-weighting

Hearing is most sensitive at 2-5 kHz, and the equal-loudness contours flatten as level rises
([Wikipedia](https://en.wikipedia.org/wiki/Equal-loudness_contour), standard ISO 226:2003). Computed from the standard's
coefficients ([parameters](https://mosqito.readthedocs.io/en/stable/_modules/mosqito/sq_metrics/loudness/utils/equal_loudness_contours.html)),
the SPL needed to sound as loud as 1 kHz, in dB relative to the 1 kHz level:

| Loudness level | 50 Hz | 100 Hz | 200 Hz | 3.15 kHz | 10 kHz |
| --- | --- | --- | --- | --- | --- |
| 40 phon | +37.8 | +24.4 | +13.4 | -4.4 | +14.3 |
| 60 phon | +30.0 | +18.6 | +9.9 | -3.6 | +13.1 |
| 80 phon | +21.7 | +12.5 | +5.9 | -2.9 | +11.7 |
| 100 phon | +13.3 | +6.2 | +1.8 | -2.3 | +10.2 |

Turning a mix down from 80 to 40 phon makes 50 Hz sound about 16 dB weaker against the midrange. **A quieter version
sounds thinner and duller even when nothing else changed**, which is why level matching comes before any tonal judgement.

BS.1770's K-weighting is a head-related high shelf followed by a second-order high-pass (the RLB curve). From the published 48 kHz coefficients
([FFmpeg](https://ffmpeg.org/pipermail/ffmpeg-cvslog/2021-July/128249.html)) the response against 1 kHz is: 30 Hz -9.0 dB,
40 Hz -6.3, 50 Hz -4.6, 63 Hz -3.4, 100 Hz -1.8, 200 Hz -1.0, 2 kHz +2.4, 4 kHz and above +3.3 (computed). A 50 Hz tone reads
4.6 LU lower than a 1 kHz tone of equal RMS, so sub-heavy material measures quieter than it feels at club level. The
validation data behind the weighting are broadcast programme and speech material (mono correlation r = 0.982 with listeners,
[BS.1770-5](https://www.itu.int/rec/R-REC-BS.1770-5-202311-I/en)). LUFS is a good matcher for like against like and a poor
judge of a bass-heavy sound against a thin one.

### 4.2 Critical bands and masking

Components closer than a critical band interfere and mask each other. On the Bark scale the bands are about 100 Hz wide
below 500 Hz and then 15-25 % of the centre frequency (240 Hz wide at 1.6 kHz; [Bark scale](https://en.wikipedia.org/wiki/Bark_scale)).
The Zwicker-Terhardt formula is 25 + 75 (1 + 1.4 (f/kHz)^2)^0.69 Hz (textbook formula; the Traunmuller variant in
[Essentia](https://raw.githubusercontent.com/MTG/essentia/master/src/essentia/essentiamath.h) gives 79-91 Hz at 55-220 Hz). The ERB model gives much narrower low-frequency filters, 24.7 x (4.37 f/1000 + 1) Hz
([Glasberg and Moore, via Wikipedia](https://en.wikipedia.org/wiki/Critical_band)):

| Centre | 55 Hz | 110 Hz | 220 Hz | 440 Hz | 1 kHz |
| --- | --- | --- | --- | --- | --- |
| Critical band (Zwicker-Terhardt) | 100 Hz | 101 | 103 | 113 | 162 |
| ERB | 31 Hz | 37 | 48 | 72 | 133 |

(computed). Masking is asymmetric: low frequencies mask higher ones far more than the reverse, and the effect grows with
level ([Wikipedia](https://en.wikipedia.org/wiki/Auditory_masking), [HyperPhysics](https://hyperphysics.gsu.edu/hbase/Sound/mask.html)).
A loud kick and bass hide the 100 Hz-1 kHz region of a pad. Temporal masking lasts roughly 20-100 ms.

### 4.3 Beating, roughness and low-register intervals

Two partials closer than about a critical band beat, then rough up. The sensory-dissonance model of Plomp and Levelt
(JASA 38(4), 1965; see [Essentia](https://essentia.upf.edu/reference/std_Dissonance.html), which cites it) peaks near a
quarter of a critical band and vanishes beyond about 1.2 bands (read from the polynomial in
[Essentia's source](https://raw.githubusercontent.com/MTG/essentia/master/src/algorithms/tonal/dissonance.cpp)). Beats
slower than a few Hz sound like wobble or detuning. Above about 20-30 per second they stop being heard as beats and become
roughness ([UNSW](https://www.animations.physics.unsw.edu.au/jw/beats.htm)). In a harmonic tone every partial can beat,
so a note detuned c cents beats its k-th partial at 0.000578 x c x k x f0 Hz (computed).

Why low chords sound wrong rather than just thick: critical bandwidth stays near 100 Hz while pitch spacing shrinks in
hertz as you go down. Computed for equal-tempered intervals above the lower note shown:

| Lower note | Major third: spacing, critical bands | beat of 5th against 4th partial | Minor third: spacing, bands | beat of 6th against 5th | Fifth: beat of 3rd against 2nd |
| --- | --- | --- | --- | --- | --- |
| A0, 55 Hz | 14.3 Hz, 0.14 | 2.2 Hz | 10.4 Hz, 0.10 | 3.0 Hz | 0.19 Hz |
| A1, 110 Hz | 28.6 Hz, 0.28 | 4.4 Hz | 20.8 Hz, 0.21 | 5.9 Hz | 0.37 Hz |
| A2, 220 Hz | 57.2 Hz, 0.55 | 8.7 Hz | 41.6 Hz, 0.40 | 11.9 Hz | 0.74 Hz |
| A3, 440 Hz | 114 Hz, 1.01 | 17.5 Hz | 83.3 Hz, 0.73 | 23.7 Hz | 1.49 Hz |

This is the producer's "wrong notes or tuning": a pad voiced with its third at 65 Hz under a bass at 55 Hz sits in the
0.1-band zone with 3 Hz beating. A relative roughness index (Plomp-Levelt polynomial, sawtooth spectrum with 30 partials,
computed, no masking or level) drops by roughly 40 % for each octave a third or triad moves up:

| Dyad or chord, lower note | A0 | A1 | A2 | A3 |
| --- | --- | --- | --- | --- |
| major third | 3.2 | 1.8 | 1.0 | 0.6 |
| minor third | 3.2 | 1.9 | 1.3 | 0.8 |
| fifth | 3.0 | 1.3 | 0.5 | 0.5 |
| closed major triad | 7.7 | 4.5 | 2.4 | 1.5 |

Fifths clean up an octave or more before thirds do, which is why root plus fifth is the safe sub-register voicing. Chart
limits for voicing live in 08; Hoffmann stresses that such limits are guidelines, that mud depends on dynamics and
harmonic richness, and that you should add the root virtually when the lowest note is not the root
([Low Interval Limits](https://www.robin-hoffmann.com/dfsb/low-interval-limits/)). Strict "one critical band" criteria
(lowest lower note for a major third: A3 by Zwicker, E2 by ERB) are more conservative than those charts, and
low-register pitch discrimination of pure tones is coarse (about 3 Hz below 500 Hz, [Wikipedia](https://en.wikipedia.org/wiki/Just-noticeable_difference)),
so the cue listeners use there is beating, not pitch error.

### 4.4 The missing fundamental

The ear infers a pitch from the spacing of harmonics even when the fundamental is absent ([Wikipedia](https://en.wikipedia.org/wiki/Missing_fundamental)).
Consequences: a pad keeps its pitch through phone speakers that cannot reproduce 41 Hz, so pitch clarity does not need sub
energy, only weight does. A sound high-passed above its fundamental keeps its pitch but turns thin. The repo's `phone`
check (200 Hz high-pass) reports the share of energy that survives; it is information, not a gate.

### 4.5 Precedence, Haas, comb filtering and the phantom centre

When two copies arrive within roughly 30-40 ms the ear fuses them and localises toward the first; the delayed copy can be
about 10 dB louder without pulling the image, and beyond about 5 ms it adds spaciousness
([iZotope on the Haas effect](https://www.izotope.com/en/learn/what-is-the-haas-effect),
[Wikipedia](https://en.wikipedia.org/wiki/Precedence_effect)). In stereo this widens a sound, but in mono the same two
copies add into a comb filter ([Wikipedia](https://en.wikipedia.org/wiki/Comb_filter)):

| Delay | 0.5 ms | 1 ms | 2 ms | 5 ms | 10 ms | 20 ms |
| --- | --- | --- | --- | --- | --- | --- |
| First notch | 1000 Hz | 500 Hz | 250 Hz | 100 Hz | 50 Hz | 25 Hz |
| Notch spacing | 2000 Hz | 1000 Hz | 500 Hz | 200 Hz | 100 Hz | 50 Hz |

Notches sit at odd multiples of 1/(2 x delay). A null you can hear at f means an offset near 1000/(2f) ms
([Sonnox](https://sonnox.com/articles/drum-phase-alignment-when-to-nudge-flip-or-leave-alone), who also call mono the stress
test). Flanging is a swept delay under about 20 ms; phasing uses phase shifters instead of a delay
([Attack](https://www.attackmagazine.com/technique/tutorials/5-ways-to-add-flanging-to-techno-drums/)). Noise has energy
everywhere, so every notch is audible and the sweep is obvious; a harmonic tone shows it only where partials land. That is
why chorus on the noise layer sounded "flangy". Mono-safe widening options: put the Haas delay on the side channel so it
cancels instead of combing ([iZotope](https://www.izotope.com/en/learn/what-is-the-haas-effect)), or use different
voices or notes on each side and keep the low end mono ([Attack](https://www.attackmagazine.com/technique/tutorials/mono-safe-stereo-width/)).

A centred phantom image appears when both channels carry the same signal ([Wikipedia](https://en.wikipedia.org/wiki/Panning_(audio))).
Lateral cues come from time differences below about 800-1000 Hz and level differences above about 1.5 kHz
([Wikipedia](https://en.wikipedia.org/wiki/Sound_localization)), which is why width and mono-safety are decided above
200 Hz and the bass belongs in the centre.

### 4.6 Intermodulation: why saturated chords sound out of tune

A non-linearity adds sums and differences between all partials of all notes
([Wikipedia](https://en.wikipedia.org/wiki/Power_chord), citing Coulter, *Digital Audio Processing*). For a fifth (3:2) the
products land close to the harmonic series, which is why distorted power chords work; for thirds and richer chords they
land on unrelated pitches and sound messy, and equal temperament adds extra beating. Computed test: an A minor triad of
three saws (110, 130.8, 164.8 Hz) through tanh drive. Saturating the **sum** put 1.4 % of the power (30-1500 Hz) more than 15 cents off every chord-note
harmonic at +6 dB, 6.6 % at +12 dB and 15.2 % at +18 dB; the strongest foreign lines at +12 dB were near 241 Hz (about B),
275 Hz (C#) and 296 Hz (D), 15-16 dB below the strongest line: wrong notes for A minor. Saturating **each voice** before
summing gave 0.0 % foreign power. In Live: put drive inside the synth or per voice, or apply Saturator to a band
(a negative `Color Amt Low` lets the low notes skip the shaper, see [12-live-devices-reference.md](12-live-devices-reference.md)),
keep it light on chords, and ask Fred to switch Hi-Quality on (a context-menu option, not a settable parameter) to cut aliasing.

> **For an agent: pad check before the human hears it**
>
> 1. List simultaneous notes with Hz (`music_theory`, `get_notes`), including sub-octave layers and transposition. Apply the
>    practical rule and the derived floors in 08 (section 2.5, with the checker in 2.8): only roots, fifths and octaves below
>    about C2 (131 Hz), major thirds from E2 (165 Hz), minor thirds and seconds higher still (derived clean floor for a close
>    minor third: D#3, 311 Hz), or spread the third as a tenth; the lowest sounding note is the chord root. Any breach is a
>    flag; I treat a third whose lower note is below A1 (110 Hz) as a hard stop: its fundamentals are under 0.3 critical band
>    apart.
> 2. Bounce the pad alone. For one held note, `hf_periodicity`: 0.85 or more is clean, below 0.7 is noisy (a detuned
>    unison lowers it a little). For the chord, `off_grid_share` with every chord note as f0, before and after each effect: a
>    rise above about 1 % deserves an A/B. Compare with the chosen sound if the human picked one.
> 3. `mono_sum_loss`: no notch deeper than 10 dB between 200 Hz and 8 kHz; `band_correlation` at or above 0.9 below 120 Hz.
> 4. Only then offer it, labelled and loudness-matched (section 7).

## 5. The limits of metrics

### 5.1 Goodhart in mixing

"When a measure becomes a target, it ceases to be a good measure" is Strathern's phrasing of Goodhart's law
([Wikipedia](https://en.wikipedia.org/wiki/Goodhart%27s_law)). Manheim and Garrabrant distinguish several ways optimisation
on a proxy fails ([2018](https://arxiv.org/abs/1803.04585)); DeepMind's catalogue of specification gaming shows agents
satisfying the literal metric while missing the goal ([DeepMind](https://deepmind.google/discover/blog/specification-gaming-the-flip-side-of-ai-ingenuity/)).
The 2026-10-08 session fell into this three times:

| What was optimised | The proxy | What broke | Do instead |
| --- | --- | --- | --- |
| pad choice | spectral distance to full-mix references | circus synths, then a hollow sub-plus-noise pad | property checklist and human choice (5.2) |
| stem sum at -14 LUFS and -1 dBTP | loudness and peak numbers | True Peak limiters on every stem (+12 dB into -14 dB ceilings) crushed micro-dynamics (an SOS reviewer calls PLR under about 8 dB detrimental) | set level with the fader or Utility `Output` on the part that is off; limit once, on the sum, last (07) |
| band envelope of the mix | reference third-octave curve | broad EQ cuts and new faders on every track at once; "garbage" | one band, one track, 1-3 dB, A/B each step |

Remedies: use metrics as gates (necessary conditions) and diagnostics, never as the search objective; prefer ranges to
points; change one thing; keep a snapshot the human approved and compare against it; cap the number of automated
candidates before a human hears one.

### 5.2 One instrument against a full-mix reference

A full mix is a sum, and a stem cannot have its shape unless every stem does, which erases the separation between them.
The stored references put 44-65 % of their power in the bands up to 80 Hz; a pad matched to that shape is a bass. The
failure is easy to reproduce with synthetic stand-ins (computed, 44.1 kHz, six seconds each): A is a "big, heavy, clean"
saw stack (root 46 Hz, three voices at +/-8 cents, harmonics to 2 kHz, 12 dB/oct above); B imitates the failed patch
(55 Hz saw low-passed at 372 Hz plus noise); C is a "circus" 7-voice supersaw at 220 Hz.

| Measure | A big/heavy/clean | B hollow | C circus |
| --- | --- | --- | --- |
| RMS dB distance of third-octave shape to Vessel's full section (lower = "closer") | 19.9 | **13.8** | 27.0 |
| harmonics resolved below 2 kHz | 43 of 43 | 6 of 36 | 9 of 9 |
| level of 400-4000 Hz against total | -13.3 dB | -21.6 dB | -4.4 dB |
| periodicity above 400 Hz (`hf_periodicity`) | 0.86 | **0.07** | 0.91 |
| magnitude-weighted / power-weighted centroid | 787 / 111 Hz | 2980 / 96 Hz | 2598 / 619 Hz |

Distance here is the RMS difference over 31.5 Hz-16 kHz between `ears.measure.third_octave_levels(audio)["relative_db"]`
and the reference's stored `third_octave` values; the band level is 10 log10 of the 400-4000 Hz share of the 30 Hz-16 kHz
power. The distance ranking prefers B. (The absolute distances depend on how empty bands are floored; an independent rerun with simpler stand-ins and no floor gave larger values in the same order, B closest, then A, then C, which is the point.) The magnitude centroid calls B the brightest of A and B, because noise has many
high-frequency bins; the power centroid cannot tell A from B. The properties the producer named (harmonic series, noise
share, level of the mid band) separate them cleanly. Also, the third-octave bands of one sustained tonal note have holes
between harmonics (A's 63 Hz band is empty, -65 dB against the total), so third-octave shape is not a fingerprint of a
single held sound.

### 5.3 Loudness bias

Level differences bias judgement toward the louder version. A listening-test guide asks for A and B within 0.1 dB
([ProSoundWeb](https://www.prosoundweb.com/discerning-differences-how-to-conduct-proper-useful-listening-tests/)); a
Wikipedia summary cites 0.1 and 0.15 dB from older audio-magazine tests (Meyer 1991, Aczel 2003)
([Wikipedia](https://en.wikipedia.org/wiki/Audio_equipment_testing)); SOS's reviewer says the increase in loudness masks
degradation of micro-dynamics when comparing processed to original ([SOS](https://www.soundonsound.com/reviews/meterplugs-perception)).
For music with compression, Croghan, Arehart and Kates (JASA 2012, in [Croghan's thesis](https://www.colorado.edu/slhs/media/230)) found
that when loudness varied, listeners preferred mild limiting; when loudness was equalised, mild compression made no
difference and heavy compression was less preferred. A Maempel and Gawlik study found no link between loudness and which
songs listeners chose in mixed playlists ([summary](https://www.meterplugs.com/blog/2016/12/30/do-people-prefer-loud-music.html)). Equalising by a model is not
perfect either: even with Glasberg and Moore's loudness model within one phon, listeners judged the most compressed
versions less loud, and earlier work found compressed speech louder than uncompressed speech at equal RMS (Moore et al.
2003, cited in the [thesis](https://www.colorado.edu/slhs/media/230)). So: match with LUFS, report the residual, and let the human trim by
ear if he says one is louder. Commercial level-matched A/B tools use the BS.1770 measure for the same reason. This set's one rule
for A/B comparisons is within 0.2 LU, 0.3 LU at most: a tighter match is below this repo's noise floor on a part (0.07-0.26 LU, section 3.1).

### 5.4 Windows, gating and loops

- **Short clips:** momentary needs 0.4 s, short-term 3 s, and integrated needs at least one 400 ms block. A 4-bar loop at
  140 BPM is 6.9 s: two independent short-term windows, so an LRA from it is noise. The repo uses a gated 90th-minus-10th percentile
  "dynamics spread" for sections.
- **Gating** drops quiet material from the integrated figure. A loop with a half-bar of silence reads louder than the same
  loop measured over its whole length. Measure the exact bars you will play.
- **Loops and seams:** measure a whole number of bars; crossfades and tails add true-peak overs (the repo saw -0.6 dBTP at
  loop seams).
- **Stereo effects:** whole-band correlation averages notches away. In a test, a 1 ms offset left 500 Hz and 1.5 kHz down
  by about 38 dB while the 500-1000 Hz band correlation read only -0.05 (computed). Read the loss curve.
- **Psychoacoustic models** (ISO 532-1 loudness, DIN 45692 sharpness, Daniel-Weber roughness in
  [MoSQITo](https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.roughness.roughness_dw.roughness_dw.html),
  [loudness](https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.loudness.loudness_zwst.loudness_zwst.html),
  [sharpness](https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.sharpness.sharpness_din.sharpness_din_st.html))
  expect calibrated sound pressure in pascals. A bounce has no SPL, so any such number assumes a playback level. Use them
  for ranking versions at one assumed level, not for absolute claims.
- **Measurement chain:** the stored references went through Spotify's lossy stream and a 44.1 kHz loopback; their absolute
  level is the player's, so only shape metrics are kept.

## 6. How professionals use reference tracks

The consistent advice across [iZotope](https://www.izotope.com/en/learn/13-tips-for-using-references-while-mixing),
[Mike Senior in SOS](https://www.soundonsound.com/sound-advice/q-when-and-how-should-use-reference-tracks),
[Mastering The Mix](https://www.masteringthemix.com/pages/how-to-use-reference-tracks) and
[PureMix](https://www.puremix.com/blog/how-to-use-reference-tracks-when-mixing) (practitioner sources):

1. **Pick two or three references in the genre before you start**, plus your own rough mix as a baseline. One reference
   teaches its quirks.
2. **Loudness-match** (iZotope's example trims a reference by 4.1 dB to read -17 LU short-term, and monitors near 85 dB
   SPL). A reference mastered 6-10 dB louder will otherwise win every comparison.
3. **Compare like with like:** chorus against chorus, drop against drop, never your drop against their intro. Use the
   loudest, densest section because problems show there first.
4. **Compare for tonal balance, width, depth, density and the balance between parts,** one question at a time; keep the
   bass centred below 100-150 Hz.
5. **Look at the range several references span and decide where you sit in it.** Senior's point is that you cannot
   photocopy a reference, because it is never the same music; reference at the start and after breaks, not constantly.
6. **Short bursts of 2-5 seconds** after a break catch what long listening dulls (iZotope suggests a ten-minute break
   after one or two hours).

> **For an agent: references**
>
> - `compare("latest", "refs")` places the top tier's band balance, dynamics, width and onset density against the range of
>   all stored references; `refs:sparse` uses their sparse sections. Treat "above/below range" as a question for the
>   human, not as a target. Dynamics come back as information because a game stem sum at -14 LUFS is meant to be less dense
>   than a club master.
> - A stem or pad is not comparable with a full-mix profile. For parts, build the property card from the producer's words
>   and measure the references only for what they contain (e.g. low root 41-49 Hz, saw-like series to about 2 kHz, little
>   noise, wide above 200 Hz).
> - Check `ref(action="list")` for which references exist before quoting numbers.

## 7. Human-in-the-loop protocols

### 7.1 What listening-test standards say, applied to a studio

ITU-R BS.1116-3 builds its method on short-term memory because long and medium-term aural memory is unreliable: near-
instant switching (about 40 ms to fade down, change and fade up), sessions of 20-30 minutes with 10-15 trials, rest equal to
the session length, and 10-25 s sequences for training ([BS.1116-3](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1116-3-201502-I!!PDF-E.pdf)).
ITU-R BS.1534-3 (MUSHRA) keeps sequences near 10 s and preferably under 12 s, at most 12 signals per trial, loops of at
least 500 ms, 5 ms raised-cosine fades at loop points and switches with no crossfades between systems, and it uses a hidden
reference and anchors; skilled assessors set the excerpt loudness by ear before the test ([BS.1534-3](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1534-3-201510-I!!PDF-E.pdf)).
It also lists the attributes listeners rate: brightness, clarity, hardness, richness and equalization for colour;
stability, sharpness, realism and dynamics for homogeneity. An ABX test needs 9 of 10 or 12 of 16 correct for 95 %
confidence ([Wikipedia](https://en.wikipedia.org/wiki/ABX_test)). Targeted fixes do not need that rigour, but the habits
carry over: short, quick, level-matched, few trials, enough rest.

### 7.2 The A/B protocol

> **For an agent: announce, match, play, ask, decide**
>
> 1. **Fix the base.** The human's chosen sound is locked. `duplicate_track` or `duplicate_scene`, name `A: <what it is>` and
>    `B: <the one change>`. Never overwrite A; never swap in a different preset as the "improvement". If a replacement is
>    truly needed, offer it as C beside A.
> 2. **One variable.** One parameter group, one step (EQ 1-3 dB, mix 10-20 points, detune a few cents). Several changes go
>    in separate comparisons.
> 3. **Same material.** Same notes, bars, tempo and start; render two passes if oscillators or LFOs free-run.
> 4. **Match loudness.** Measure the exact bars of both (`bounce` plus `analyze_audio`, or `meter(source="live")`) and trim B
>    (never A) with Utility `Output` or `set_mixer` volume until integrated LUFS agree within 0.2 LU (0.3 LU at most).
>    Report the residual. Check that true peak did not change much.
> 5. **Announce and label.** Say in chat what plays, in what order and for how long, and put it in Live's status bar with
>    `show_message`. Example: "A = your pad, unchanged. B = same pad, chorus Dry/Wet 40 to 20 %. 4 bars each, A B A B, about
>    8 s each at 120 BPM, B trimmed 0.3 dB. Which has less swirl, or no difference?"
> 6. **Play short and in order.** `fire_scene` A, B, A, B at bar boundaries. No talking during playback, no changes during
>    the loop, same monitor volume throughout.
> 7. **Ask a specific question** (7.3), with "no difference" as a valid answer. Limit to about 10-15 comparisons per
>    session and offer a break.
> 8. **Decide.** Keep B only if he says so. Record the result (in a NOVA set: `capture(note=...)` and `takes(action="keep")`)
>    and measure the approved sound: his approved sounds, not global references, calibrate your thresholds for the rest of
>    the project.
> 9. **Unblinded is fine for fixing a stated complaint** (he knows what to listen for). Use blind X/Y with a key only for
>    close calls or when he asks.

### 7.3 Questions that work

- Attribute, not preference: "Which has more low end, A or B, or the same?" "Which has the steadier sub?" Preference
  questions ("which is better?") invite level, novelty and expectation effects.
- Category triage when you do not know the problem: "Is the issue pitch (wrong notes or tuning), tone (hollow, airy,
  boomy), or space (wide, phasey)?"
- Location: "At which bar does it first bother you?" then solo the parts present there.
- Sweep to find a resonance: automate one EQ Eight bell (+6 dB, Q 3-4) exponentially from 120 Hz to 1.2 kHz over 8 bars with
  `write_automation`, and ask him to say when it is ugliest; the bar number maps to frequency on a log scale. Cut there.
- Register test for tuning: play the sustained chord alone, then the same chord with everything below 100 Hz removed, and ask
  which one has the wrong note.
- Constrain choices: offer at most three candidates, each differing on one axis.

### 7.4 Interpreting terse feedback

Rule out defects and level mismatch before tone: clipping, polarity, mono collapse and wrong notes first, then a level
shift between versions, then tone, space, pitch and taste. Each row gives hypotheses in order of likelihood, the measurement
that tells them apart, the smallest change, and the question to ask if the measurement cannot decide.

| He says | Likely meanings, in order | Measure first | Smallest first change | Then ask |
| --- | --- | --- | --- | --- |
| "too flangy" | modulated or static comb from chorus/flanger/Haas, worst on noise; too much feedback | `mono_sum_loss` notches; noise share of the layer; which device is active | Dry/Wet 40 to 20 %, Amount halved, Feedback 0, FB Invert off. Chorus-Ensemble: Delay Time fixed instead of Auto (the [manual](https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/#chorus-ensemble) says this avoids unwanted phasing), HP on at 150-300 Hz. Move the effect off the noise layer | "Is the swirl in the highs only? Gone in mono?" |
| "airy" | noise or HF above the tone (negative); or nice "air" (positive) | `hf_periodicity`; share above 6 kHz; flatness 2-8 kHz | negative: noise layer -6 dB, Auto Filter low-pass 5-6 kHz, reverb high cut. positive: high shelf +2 dB at 10-12 kHz | "Airy as a compliment or a complaint?" |
| "hollow" | missing body 150-600 Hz; odd-harmonic wave; mono comb; sub-plus-noise | 200-800 Hz band against 100 Hz and 1-2 kHz; odd/even ratio; mono test; harmonics resolved | Utility `Mono` check first; then low shelf +2 dB at 200 Hz or an octave-down layer at -8 dB; switch square to saw | "Still hollow in mono?" |
| "meatier" | more 100-400 Hz weight with harmonic density | 125-400 Hz third-octave; crest factor | bell +1.5 to +3 dB at 150-300 Hz, Q 0.8; parallel Saturator on a single-note layer only (never a chord, 4.6), `Dry/Wet` 20-30 %, drive 6 dB, lows excluded with a negative `Color Amt Low` | "Meatier in the bass body or in the mids bite?" |
| "bigger" | wider; longer; lower; denser; or just louder | width and correlation above 200 Hz; tail length; low-mid level; loudness | build three one-axis variants: Utility `Stereo Width` +20 % with `Bass Mono` On; Reverb decay +1 s with 20-30 ms pre-delay; octave-down layer -10 dB | "Wider, longer, lower or louder?" (match loudness so "louder" is not confounded) |
| "thin" | weak 100-300 Hz; phase cancellation | band share; mono-sum loss; polarity | Utility polarity test (`Left Inv`, `Right Inv`); shelf +2 dB at 150-250 Hz; octave layer | "Thin in stereo or only in mono?" |
| "muddy" | 150-400 Hz buildup; low-register chord; reverb | third-octave 160-400 Hz; interval check (4.3); masking overlap | bell -2 dB at 250 Hz on the part with less need; reverb low cut; move chord notes up | "Which part: pad, bass or reverb?" |
| "harsh", "shrill" | 2-5 kHz resonance; aliasing; intermodulation | 2.5-4 kHz band; `hf_periodicity`; `off_grid_share` before and after the last effect | bell -2 dB at 3-4 kHz; Saturator `Drive` -3 dB (Hi-Quality is a context-menu switch: ask Fred) | "Constant or on certain notes?" |
| "boomy" | one note resonating at 60-200 Hz | per-note low-band peaks | narrow cut at that note's fundamental; shorter release | "On which notes?" |
| "dull", "dark" | HF loss; steep filter | slope against references; share above 6 kHz | high shelf +2 dB at 6 kHz or cutoff +10-20 % | "Dull compared with what?" The references are dark above 2 kHz |
| "wrong notes", "out of tune" | low thirds beating; detune; intermodulation; sub root mismatch | `analyze_notes`; 4.3 table; cents; off-grid share | open the voicing (root + fifth in the sub); detune to +/-5 cents; saturate per voice | "Solo the pad: still wrong? With the bass muted?" |
| "too wide", "narrow" | correlation above 200 Hz; mono-sum loss | `band_correlation`; loss curve | Utility `Stereo Width` +/-20 %; keep `Bass Mono` On | "In headphones or speakers?" |
| "garbage", "worse" | something regressed or a level shift misled | `compare("latest", "best")`; level difference | **restore the last approved state first** (`takes(action="restore")` or the saved duplicate), then bisect the changes one at a time | "Which moment or part?" |

### 7.5 When it goes badly

Stop changing things. Restore the last state he approved, say what you changed since, and re-introduce changes one at a time
with an A/B each. Do not argue with the ear using numbers; record the numbers of the version he likes and keep them as the
new local reference.

## 8. Before you claim "better"

> **For an agent: decision checklist**
>
> 1. One sentence: the complaint, the attribute, the direction.
> 2. One variable changed from a saved base that is untouched and restorable.
> 3. Same material, same bars, two passes if anything free-runs; difference is above the noise floor (0.07-0.26 LU).
> 4. Loudness matched within 0.2 LU (0.3 LU at most); residual reported; no clipping, true peak not worse.
> 5. Defect gates pass: `analyze_notes` clean; low end correlated and mono (loss 1 dB or less below 120 Hz); no mono-sum notch
>    deeper than 10 dB between 200 Hz and 8 kHz; off-grid share not up, periodicity not down; key confidence not down.
> 6. The target metric moved in the intended direction by more than noise and stayed inside the references' range (or you
>    can say why not).
> 7. `compare("latest", "best")` shows nothing regressed.
> 8. Wording: "measurably closer on X; not yet confirmed by ear" until the human says so. "Sounds better" is his sentence.
> 9. The revert path is stated in the message.
> 10. Result logged with the numbers of the approved sound.
>
> **Stop and ask when:** the word has several meanings; metrics disagree; the change would replace his sound; two of his
> answers conflict; any gate fails; you are about to change more than one thing.

## Sources

Standards and loudness
- EBU Tech 3341, Loudness metering: EBU Mode (2023): https://tech.ebu.ch/docs/tech/tech3341.pdf
- EBU Tech 3342, Loudness Range (2023): https://tech.ebu.ch/docs/tech/tech3342.pdf
- EBU R 128, Loudness normalisation and permitted maximum level (2023): https://tech.ebu.ch/docs/r/r128.pdf
- EBU Tech 3343, Guidelines for production in accordance with R 128 (2023): https://tech.ebu.ch/docs/tech/tech3343.pdf
- ITU-R BS.1770-5, Algorithms to measure audio programme loudness and true-peak audio level (2023): https://www.itu.int/rec/R-REC-BS.1770-5-202311-I/en
- FFmpeg commit showing the 48 kHz K-weighting coefficients: https://ffmpeg.org/pipermail/ffmpeg-cvslog/2021-July/128249.html
- Spotify for Artists, Loudness normalization: https://support.spotify.com/us/artists/article/loudness-normalization/
- iZotope, Mastering for streaming platforms: https://www.izotope.com/en/learn/mastering-for-streaming-platforms

Reference tracks, tonal balance, frequency descriptors
- iZotope, How to use reference tracks when mixing: https://www.izotope.com/en/learn/13-tips-for-using-references-while-mixing
- iZotope, What is tonal balance: https://www.izotope.com/en/learn/what-is-tonal-balance-in-mixing-and-mastering
- iZotope, EQ cheat sheet: https://www.izotope.com/en/learn/eq-cheat-sheet
- Mike Senior, Q. When and how should I use reference tracks? (SOS, Dec 2014): https://www.soundonsound.com/sound-advice/q-when-and-how-should-use-reference-tracks
- Mastering The Mix, How to use reference tracks (vendor guide): https://www.masteringthemix.com/pages/how-to-use-reference-tracks
- PureMix, How to A/B your mix against a reference (practitioner blog, weak): https://www.puremix.com/blog/how-to-use-reference-tracks-when-mixing
- Voxengo SPAN user guide and Primary user guide (slope, correlation, crest window): https://www.voxengo.com/files/userguides/VoxengoSPAN_en.pdf/getbyname/Voxengo%20SPAN%20User%20Guide%20en.pdf and https://www.voxengo.com/files/userguides/VoxengoPrimaryUserGuide_en.pdf/getbyname/Voxengo%20Primary%20User%20Guide%20en.pdf

Listening tests and loudness bias
- ITU-R BS.1116-3: https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1116-3-201502-I!!PDF-E.pdf
- ITU-R BS.1534-3 (MUSHRA): https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1534-3-201510-I!!PDF-E.pdf
- ProSoundWeb, Discerning differences: how to conduct proper, useful listening tests: https://www.prosoundweb.com/discerning-differences-how-to-conduct-proper-useful-listening-tests/
- Wikipedia, Audio equipment testing (level-matching tolerances, secondary): https://en.wikipedia.org/wiki/Audio_equipment_testing
- Hugh Robjohns, MeterPlugs Perception review (SOS, July 2014): https://www.soundonsound.com/reviews/meterplugs-perception
- N. Croghan, Perceived quality of recorded music processed through compression hearing aids (PhD thesis, Univ. of Colorado, 2013; contains Croghan, Arehart and Kates, JASA 132(2), 2012): https://www.colorado.edu/slhs/media/230
- MeterPlugs, Do people prefer loud music? (summary of Maempel and Gawlik 2009 and Croghan et al. 2012): https://www.meterplugs.com/blog/2016/12/30/do-people-prefer-loud-music.html
- Wikipedia, ABX test (secondary): https://en.wikipedia.org/wiki/ABX_test

Psychoacoustics
- ISO 226:2003 coefficients as implemented in MoSQITo: https://mosqito.readthedocs.io/en/stable/_modules/mosqito/sq_metrics/loudness/utils/equal_loudness_contours.html
- Wikipedia (secondary, used for definitions and numbers that its cited sources carry): https://en.wikipedia.org/wiki/Equal-loudness_contour, https://en.wikipedia.org/wiki/Critical_band, https://en.wikipedia.org/wiki/Bark_scale, https://en.wikipedia.org/wiki/Auditory_masking, https://en.wikipedia.org/wiki/Missing_fundamental, https://en.wikipedia.org/wiki/Precedence_effect, https://en.wikipedia.org/wiki/Sound_localization, https://en.wikipedia.org/wiki/Panning_(audio), https://en.wikipedia.org/wiki/Comb_filter, https://en.wikipedia.org/wiki/Pink_noise, https://en.wikipedia.org/wiki/Cent_(music), https://en.wikipedia.org/wiki/Just-noticeable_difference, https://en.wikipedia.org/wiki/Pulse_wave
- HyperPhysics, Masking: https://hyperphysics.gsu.edu/hbase/Sound/mask.html
- J. Wolfe, UNSW, Beats and roughness: https://www.animations.physics.unsw.edu.au/jw/beats.htm
- Plomp and Levelt, Tonal consonance and critical bandwidth, JASA 38(4), 1965 (cited via Essentia, not read directly): https://essentia.upf.edu/reference/std_Dissonance.html
- Essentia source: dissonance polynomial and Bark functions: https://raw.githubusercontent.com/MTG/essentia/master/src/algorithms/tonal/dissonance.cpp and https://raw.githubusercontent.com/MTG/essentia/master/src/essentia/essentiamath.h
- R. Hoffmann, Low interval limits: https://www.robin-hoffmann.com/dfsb/low-interval-limits/
- Wikipedia, Power chord (intermodulation): https://en.wikipedia.org/wiki/Power_chord

Audio descriptors and MIR
- librosa source, spectral features: https://github.com/librosa/librosa/blob/main/librosa/feature/spectral.py
- Essentia: Dissonance, Inharmonicity, OddToEvenHarmonicEnergyRatio: https://essentia.upf.edu/reference/std_Inharmonicity.html, https://essentia.upf.edu/reference/std_OddToEvenHarmonicEnergyRatio.html
- MoSQITo (loudness ISO 532-1, sharpness DIN 45692, Daniel-Weber roughness): https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.roughness.roughness_dw.roughness_dw.html, https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.sharpness.sharpness_din.sharpness_din_st.html, https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.loudness.loudness_zwst.loudness_zwst.html
- E. Schubert and J. Wolfe, Does timbral brightness scale with frequency and spectral centroid? Acta Acustica 92, 2006: https://newt.phys.unsw.edu.au/~jw/reprints/SchubertWolfe06.pdf

Stereo, phase, Haas
- iZotope, What is the Haas effect: https://www.izotope.com/en/learn/what-is-the-haas-effect
- Sonnox, Drum phase alignment: https://sonnox.com/articles/drum-phase-alignment-when-to-nudge-flip-or-leave-alone
- Attack Magazine, Mono-safe stereo width (Oct 2020): https://www.attackmagazine.com/technique/tutorials/mono-safe-stereo-width/
- Attack Magazine, 5 ways to add flanging to techno drums (Jun 2020): https://www.attackmagazine.com/technique/tutorials/5-ways-to-add-flanging-to-techno-drums/

Goodhart and specification gaming
- Wikipedia, Goodhart's law: https://en.wikipedia.org/wiki/Goodhart%27s_law
- D. Manheim and S. Garrabrant, Categorizing variants of Goodhart's law (2018): https://arxiv.org/abs/1803.04585
- DeepMind, Specification gaming: https://deepmind.google/discover/blog/specification-gaming-the-flip-side-of-ai-ingenuity/

Ableton and this repo
- Live 12 manual, Live audio effect reference (Chorus-Ensemble, Phaser-Flanger, Saturator, Utility, Spectrum): https://www.ableton.com/en/live-manual/12/live-audio-effect-reference/
- `ears/measure.py`, `ears/profile.py`, `ears/compare.py`, `MCP_Server/audio/analysis.py`, `docs/listening-loop-calibration.md`, `.claude/skills/listening-loop/SKILL.md`, and the stored reference numbers in `~/Music/AbletonMCP/Ears/refs/` (Vessel, She's Gone Away).
- Ian Shepherd, PLR (definition only): https://productionadvice.co.uk/plr/

## Open questions / where sources disagree

- **Frequency ranges.** Boxiness is quoted at 200-500 Hz (iZotope kick), 300-500 (snare), about 400, 500-800 (brass) and 600-700 Hz in other guides; mud at 150-500 Hz. These are instrument-specific resonances, so find them by sweep with the human.
- **Critical bandwidth at low frequency.** Bark/Zwicker gives about 100 Hz below 500 Hz, Glasberg and Moore's ERB gives 31-48 Hz at 55-220 Hz. Both put thirds at 55/65 Hz inside the roughness zone, but they disagree on where thirds become clean (A3 against E2 for a major third at one full band). Practical voicing charts sit lower still.
- **Level-match tolerance.** This set uses one rule for A/B comparisons: within 0.2 LU, 0.3 LU at most. The 0.5 LU that appears elsewhere is the NOVA delivery tolerance for the T5 sum, not an A/B tolerance, and it is large enough to bias a preference. Sources: 0.1 dB (ProSoundWeb), 0.1-0.15 dB (older magazine tests via Wikipedia), 0.2 LU measurement tolerance in EBU practice, and this repo's measured noise of 0.07-0.26 LU. Even model-based equalisation within one phon left perceived differences, so keep a human trim.
- **K-weighting for sub-heavy electronic music.** The validation material is broadcast speech and programmes; the high-pass takes 4.6 dB off 50 Hz against 1 kHz, while equal-loudness data say bass counts for more at high playback levels. No source here measures how well LUFS predicts perceived loudness of techno.
- **Minimum PLR.** Robjohns calls under 8 dB detrimental; the stored industrial references measure 6.5 dB in a dense section and 13 dB in another. No source gives a genre floor for industrial or techno.
- **Club loudness.** Typical integrated loudness of club masters was not sourced here (anecdotes say -6 to -9 LUFS); do not use it as a target.
- **"Warm" and even harmonics.** Common practitioner belief; I found no source that tests it.
- **Brightness and centroid.** The absolute centroid explains about a quarter of rated brightness variance in one study (r = 0.51); treat it as a hint.
- **Haas zone.** 30-40 ms (iZotope), up to 40 ms for complex sounds (Wallach via Wikipedia), 50-100 ms for some sounds; depends on signal type.
- **Reference data.** Two of four Nine Inch Noize tracks are stored, measured through a lossy stream; "typical" electronic ranges in this file come from them plus broadcast standards, not from a genre survey.
- **Not read** (paywalled or blocked at the time of research): AES papers (Clark 1982 on level-matched testing, Deruty and Tardieu 2014 on dynamics in mainstream music), Zacharakis et al. 2014 and the Stables et al. SAFE work on semantic timbre descriptors, Zwicker and Fastl's textbook values for the roughness and fluctuation-strength peaks. Nothing above relies on them. Two textbook statements are used without a fetched source and are marked as such: the Zwicker-Terhardt bandwidth formula (4.2) and the remark that L/R correlation proxies interaural correlation (3.3). The web search quota ran out during research, so later sources were fetched directly from known pages.
