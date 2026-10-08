# Listening loop — calibration report

PRD §13.4: which checks can be trusted, what they catch, their noise floors and the tuned value of every
† tolerance. Measured 2026-10-07 on Live 12.4.6 (44.1 kHz) with the NOVA set composed by the soundtrack
session, the shipped masters (`tetris-nova` worktree `public/music/masters/`, 48 kHz / 24-bit) and the
synthetic fixtures of `ears/fixtures/`. Re-run with `uv run ears calibrate` (fixtures, also in CI) and the
captures below.

## 1. Planted defects (PRD §13.2, fixture form)

`uv run ears calibrate` (neon, 140 BPM, 48 kHz, 24-bit). "Caught by" lists every check that failed or
warned; the extra entries are real consequences of the defect (a +6 dB arp boost also makes the mix louder,
a bass a semitone off also clashes with the arp).

| Defect | Must be caught by | Caught by | OK |
| --- | --- | --- | --- |
| none (clean fixture) | — | audio.key (bass heard alone, warn) | yes |
| +6 dB at 3 kHz on the arp | audio.balance, compare | audio.balance, compare, audio.loudness, audio.tempo_consistency | yes |
| sub out of phase between channels | audio.mono_sub | audio.mono_sub, audio.balance, audio.loudness | yes |
| one stem 3 dB louder at one tempo | audio.tempo_consistency | audio.tempo_consistency, audio.loudness | yes |
| reverb on the master only | audio.sum_null | audio.sum_null | yes |
| click at the loop seam | file.seam | file.seam, audio.loudness | yes |
| tail not folded | file.seam | file.seam, audio.balance, audio.loudness, audio.tempo_consistency | yes |
| file 5 ms short | file.duration | file.duration | yes |
| none (clean notes) | — | — | yes |
| bass a semitone off for one bar | notes.in_key, notes.chord_tones | notes.in_key, notes.chord_tones, notes.clash | yes |
| D major where Dm belongs | notes.in_key, notes.chord_tones | notes.in_key, notes.chord_tones | yes |
| two stems a semitone apart for a beat | notes.clash | notes.clash | yes |
| kick late by a thirty-second note | notes.grid | notes.grid (53.6 ms at 140 BPM) | yes |
| lead with no rests | notes.lead_rests | notes.lead_rests | yes |
| shared pad holding A over E (G#) | notes.shared_stem | notes.shared_stem, notes.clash | yes |

Planting each defect once in the real Live set (PRD §13.2, second form) is not done: it means editing
Frederic's set. The capture path itself is calibrated on a calibration file (§3).

## 2. Repeatability and noise floors (PRD §13.1)

Three tap captures of the unchanged NOVA state at 140 BPM (takes neon-140-AB-0001, -0003, -0004):

| Metric | Spread (max − min) | Used as noise floor |
| --- | --- | --- |
| T5 integrated loudness | 0.07 LU | 0.07 |
| T5 true peak | 0.24 dB | 0.24 |
| T5 loudness range | 0.07 LU | 0.07 |
| T1 / T2 / T3 / T4 loudness | 0.16 / 0.07 / 0.07 / 0.06 LU | — |
| Part loudness | 0.0 (kick, perc) to 0.26 LU (arpB) | 0.26 |
| stems + returns vs mix (sum null) | 60.6 / 60.6 / 73.1 dB | — |

Free-running oscillators and the lead's random pitch LFO make synth stems differ by about −3 dB
waveform null between passes while their loudness stays within 0.26 LU, so compare works on
measurements. `compare` reads these floors from `<ears home>/calibration/noise.json`; band metrics keep
the default 0.5 dB.

## 3. Capture (PRD §6.4, C2–C7)

| Requirement | Result |
| --- | --- |
| C2 no trace | Tempo, quantization, loop, metronome, record modes, start time, every track's mute/solo/arm and Back to Arrangement (per track) restored and verified on a later tick; the `cap:` tracks deleted. Live test `test_capture_is_sample_exact_and_leaves_no_trace` and every real capture |
| C3 bar alignment | 0 samples (impulses at known beats, tap and Resampling, 120 and 140 BPM, with and without a lookahead device); the cut lands within 0.5 sample of the bar (±5 ms allowed) |
| C4 unity gain | −18 dBFS tone recorded at −21.010 dBFS RMS on both routes (< 0.01 dB) |
| C5 format | Recorded at 44.1 kHz / 24-bit (Live's settings): every take warns |
| C6 provenance | `take.json`: set, tempo, variations, mode, bars, band, Live version, offsets, formats, warnings, pass labels, clips |
| C7 steady tempo | Tempo read at the start and end of each pass; a change fails the pass, and takes whose passes all completed are kept |
| Solo mode | Sidechain pumping keyed from the kick survives (soloed pad within 0.11 LU of its tap capture) |

## 4. Tuned tolerances (every † of the PRD)

| Tolerance | PRD start | Now | Basis |
| --- | --- | --- | --- |
| T5 loudness | −14 ± 0.5 LU | ± 0.5 | Kept. The shipped mixes sit at −14.5…−14.7 (the composer's deliberate −14.6) and fail by up to 0.2 LU |
| tempo consistency | ± 1 LU | ± 1 | Kept; noise is 0.26 LU per part |
| mono sub loss | 1 dB | 1 dB | Kept; the MAINFRAME pad loses 1.3–1.5 dB (a real finding) |
| sum null | 40 dB | 40 dB | Kept; real captures reach 60–73 dB, clean fixtures 149 dB, a master-only reverb 4.9 dB |
| bar alignment | ± 5 ms | ± 5 ms | Measured 0 samples |
| duration | ± 1 ms | ± 1 ms | Kept (brief) |
| seam: fold | (not in PRD) | head's first 3 ms ≥ 30 dB below the body's last 20 ms fails | Replaces the brief's "peak within 1 dB of the surrounding RMS", which fails every musical downbeat. Shipped masters: worst −25 dB (the 1-bar fill, which is not looped and is exempt), looped stems at worst −15.6 dB (the pad, which ducks on the downbeat); an unfolded pad fixture: −40.3 dB |
| seam: click | (detector†) | seam HF energy ≤ 6 dB above the body's loudest HF transient | Shipped masters: at most +3.2 dB (the equal-power crossfade's own bump on kick downbeats); a planted 0.5 ms burst: +40.4 dB |
| file.start | ± 5 ms | ± 5 ms | Needs the clip's notes (captures carry them; delivery folders do not) |
| notes.grid | (derived) | 10 ms | A 32nd note late is 54 ms at 140 BPM |
| lead rests | 40 % ± 10 points | ± 10 | Kept; the NOVA leads rest 55–59 % (warn) |
| chord tones on beats | 1 and 3 | 1 and 3 | Kept; notes up to 1/16 beat early count as on the beat |
| clash | a sixteenth | a sixteenth | Kept |
| compare noise | 0.5 dB | measured (§2) | `calibration/noise.json` |
| phone high-pass | 200 Hz | 200 Hz | Kept |

## 5. Checks on real material

**Real captures of the NOVA set** (tap, NEON 100 / 140 / 180 BPM, analysed together; 4–6.5 s per take):

| Check | Result |
| --- | --- |
| audio.sum_null | pass, 60–73 dB |
| audio.key (T5, both variations) | pass, A minor |
| audio.mono_sub | pass |
| audio.loudness | fail: T5 −14.1…−14.7 LUFS; true peak up to +0.4 dBTP at 180 BPM, on loop seams |
| audio.tempo_consistency | fail: pad +2.9 LU and arps +2.2/+2.4 LU at 100 BPM, perc −2.8 LU at 100 BPM (the LOW band's half-time pattern), bassA −1.8 LU at 180 BPM. The composer levelled the full mix per tempo in post, not each stem, so a player hears stems jump at level-ups |

**Shipped masters** (`uv run ears acceptance <masters>`, strict, 130 files, 13 tempo folders, 90 s): duration,
seam and format pass everywhere, and every tier mix reads A minor (MAINFRAME B, Am|Dm|G|E, is a near tie with
A major: margins 0.005–0.026, reported as an uncertain warn). audio.loudness fails at every tempo (−14.5…−14.7
LUFS, and −0.6 dBTP true peaks at several NEON tempos, on loop seams: the game's 10 ms equal-power crossfade
on folded material; the same stems looped natively peak at −1.45 dBTP). audio.tempo_consistency flags the
same per-stem jumps as the captures. The MAINFRAME pad fails audio.mono_sub (1.3–1.5 dB).

**Key estimation** (`measure.key_estimate`, three spectral views, the file's opening weighted): 130/130 tier
mixes of the masters read A minor in the measurement builder's run; per stem alone the pad 13/13 and arps
26/26 read A minor, the bass 9/26 and the leads 18/26, so per-stem key warnings are given for pad and arp only.

**Notes of the real set** (`analyze_notes`, 1.2 s): the shared pad fails notes.shared_stem (29 of 84 held
pitches: E over F in bar 2, A over E/G# in bar 4) and notes.clash in variation B (35 overlaps); bassA fails
notes.chord_tones once (C2 on beat 3 of bar 8, the turnaround); the leads warn on rests (55–59 %); the kick
patterns match the brief per band.

## 6. Listeners (PRD §10, §13.3)

None is built or enabled (phase 3). Agreement with Frederic's blind picks has not been measured. No fuzzy
score gates anything: masking, analyser bands and phone survival are report-level only.
