# 13 Scanning presets by role: judge construction and defects, then let the producer choose

Written 2026-10-09 from the NOVA session in which Fred asked for "another scan of all pad candidates with improved
judging skill" after the 2026-10-08 failure, when presets were ranked by spectral distance to full-mix references
(00, rule 2). This digest is the method that replaced it, what it found in Live 12.4.6's library, and the traps met
on the way. It is a project measurement, not a published method: the thresholds were calibrated on one producer's
approved and rejected sounds.

## If you remember five things

1. **Gates first, then a score, then the ear.** Gates remove what the producer has rejected (noise and air,
   distortion on chords, a sub two octaves down, interval layers, unstable pitch, chord intermodulation, mono collapse)
   and what the role cannot have (a pad that does not sustain). A transparent score ranks the survivors for the job.
   The producer hears at most three, loudness-matched against his current sound (11, section 7.2).
2. **Calibrate on his sounds.** Measure the sound he approved and one he rejected with the same probe before setting
   any threshold. NOVA: the base pad read noise 46 dB under the partials, no wobble, no vibrato; Dark Throne (rejected
   as hollow, airy, flangy, "wrong notes") read noise level with the partials, a two-octave sub 12 dB over the played
   note and 26 cents of pitch jitter.
3. **Read the chain of every preset.** `get_devices` shows what the name hides: 76 of 282 pad presets carry a
   Saturator, Amp, Erosion, Pedal, Roar, Redux or Drum Buss somewhere inside a rack, and one drone rack hides a guitar
   **Amp** simulator, which is distortion on chords.
4. **Most stock pads are noisy, chorused or saturated by design.** Of 282 pads, 121 failed the noise gate, 76 the
   distortion gate and 43 do not sustain; 20 passed. The clean ones are mostly mono. Clean *and* wide is rare: build
   it (03, section 2.2), as Pad D was.
5. **Probe the role's real material in its register.** A pad plays a held A2 and the pad's own Am voicing; a bass a
   held A1 and its bar; an arp a held A3 and its quarter-note shape; a lead a held A4 and its first phrase; a kit each
   pad the parts use, one hit at a time. Live names: C3 = 60, so A2 = MIDI 57 = 220 Hz (08).

## 1. The probe and the measures

Each preset loads on a soloed scratch track (`[test:...] probe`, `load_from_browser` replaces the instrument), plays the
probe clips, and is recorded through the loopback into memory (our own audio only). One preset takes about 12 s.

| Measure | How | What it catches |
| --- | --- | --- |
| attack, sustain | 50 ms RMS envelope: time to within 3 dB of the peak; last 1.5 s against the peak | plucks and decays offered as pads; swells too slow for chords that change every bar |
| sounding pitch | strongest peak within 3 % of the written note, long FFT of the steady part | transposed presets, detuned layers |
| sub layers | energy at f0/2 and f0/4 against f0 | sub-octave layers that put chord thirds in the bass register ("wrong notes") |
| fifth layer | energy at 1.5 f0 when f0/2 is weak | presets that add a fifth to every note (they clash with the other progression) |
| partial staircase | partials 1-12 against the strongest; even/odd balance; partials above -40 dB below 2 kHz | hollow (odd only), thin (weak fundamental), full (saw-like 1/n) |
| noise | energy off the harmonic grid (f0, f0/2, f0/4 multiples) against on-grid energy, 80 Hz-8 kHz | airy, raspy, breathy layers |
| off-series peaks | strong peaks off the grid | FM, ring modulation, frequency shifters, extra pitch layers |
| wobble | energy-weighted standard deviation of third-octave band levels 250 Hz-4 kHz, 21 ms frames, trend removed | chorus, LFO sweeps, tremolo, beating unison (see section 4: it does not equal "flangy") |
| vibrato | frame-by-frame frequency of the strongest of partials 1-6 | pitch LFOs and drift that read as "out of tune" |
| chord off-series | the voicing's spectrum against the A and C partial grids | intermodulation from distortion on chords, detune smear |
| width, mono loss | side/mid energy per band; mono sum against the channel average; correlation | width above 200 Hz; comb filtering that collapses in mono |
| balance | 150-600 Hz against 600 Hz-5 kHz (body); 2-8 kHz against 200 Hz-2 kHz (top) | meat, darkness, brightness |

## 2. Pad gates and score as used

Gates (in order): silent; distortion device switched on anywhere in the chain; sustain under -12 dB or attack over
2.5 s; noise over -20 dB; two-octave sub over -15 dB; fifth layer; more than 6 off-series peaks; vibrato over 6 cents
or the pitch more than 15 cents off; chord off-series over -18 dB; mono loss worse than -4.5 dB; chord wobble over
4.5 dB. Score (0-100): clean 35 % (noise, chord off-series, wobble, vibrato), full 25 % (partials to 2 kHz,
fundamental, even/odd, body), dark top 15 % (2-8 kHz about 18 dB under 200 Hz-2 kHz), wide 25 % (side/mid
200 Hz-2 kHz up to 0.75, halved credit when mono loss is worse than -3.5 dB). Near misses fill the top 10 when fewer
than ten pass, labelled with the one gate they failed (a noise oscillator can be switched off).

## 3. What the NOVA pad scan found (2026-10-09)

- 282 presets from the pad, drone, ambient, strings, swell and choir categories of the installed packs. The ranked
  list with reasons is `~/Music/Ableton/NOVA v1 Project/v2-work/top10.md` (and `top10_pad.json`).
- Leaders: Analog Slow Sweep Pad (Operator: sine and user waves, `Spread` 70 %, open filter, envelope sweep), Strings
  Basis Pad (Operator: two saws plus a white-noise oscillator at -28 dB and an LFO on volume), Wave Pad (Drift).
  Operator's `Spread` produces side/mid near 1.
- Finalists played to Fred, labelled and matched within 0.05 LU: base pad, Analog Slow Sweep, Strings Basis with its
  noise oscillator off, and **Pad D**, built for the role in Wavetable (Basic Shapes saw at 66 %, the same saw an
  octave up at -6 dB, a sine sub an octave down at -10 dB, Classic unison 4 voices at 12 %, 24 dB clean low-pass at
  1.8 kHz, 60 Hz high-pass, attack 150 ms, release 2.5 s, 16 voices, on a twin of the base pad's reverb and Utility).
  Pad D measured noise -77 dB, chord off-series -72 dB, width 0.93, body +4 dB, in tune within 3 cents.
- Fred: "you pick for now, continue". Pad D became the `pad` track at the pass-6 pad stem loudness (-22 LUFS); the
  capture against pass 6 kept every tier's loudness, fixed a mono-sub fail and removed the pad from the masking report
  (the old pad's air had overlapped the arp at 6-10 kHz). Not yet confirmed by his ear in the mix.

## 4. Traps met while scanning and auditioning

- **Solo beats mute.** In Live 12.4.6 a soloed track plays even when its activator is off (`set_mixer(mute=True)`):
  an A/B that soloed every version and muted all but one played all four at once and matched them to each other's sum.
  Switch versions by solo (solo the next, then release the current) and keep the others unsoloed.
- **Polling a clip's `playing_position` can step over a narrow window.** Waiting for "position >= loop end - 60 ms"
  missed loop points and played some versions 16-32 s instead of 8 s. Also accept "the position wrapped".
- **The producer's sound may be far hotter than the mix.** The base pad (Poli, five voices, Volume -4.9 dB) peaked
  near 0 dBFS alone at a -6 dB fader, 14 dB over the pass-6 pad stem. Matching candidates up to it would have clipped:
  audition everything a fixed number of dB lower, and place the chosen sound at the approved mix's stem loudness.
- **The fader stops at +6 dB.** Put large trims on the chain's last Utility (`Output`, linear) instead.
- **Movement is not flange.** The Dark Throne Fred called flangy measured only 1-1.4 dB of wobble: the flange came from
  chorus acting on a noise layer. Do not gate clean ensemble or unison width on wobble alone; judge noise first.
- **Vibrato needs a strong partial.** Tracking a fixed partial on a sub-heavy bass read 272 cents of "vibrato"; track
  the strongest of partials 1-6 and report nothing when none stands out.
- **Old scanners carried the octave error.** A 2026-10-08 script analysed MIDI 57 as 110 Hz; every harmonic count it
  produced was an octave off. Check `f0` in any inherited analysis.
- **Wavetable's default table**, Basics > Basic Shapes, morphs sine (0 %) - triangle (25-33 %) - saw (about 66 %, all
  partials near 1/n) - square (100 %, odd partials). A fresh Wavetable may also open with `oscillator_1_effect_mode`
  warp-and-fold: set it to none for a clean saw.
- **`capture` returns images** with its result; scripts should read the take's `report.json` instead of serialising it.
- **Sub-only basses vanish on phones.** NOVA's bassA (Deep Bass) has its octave-below layer 21 dB over the played note
  and a 51 Hz spectral centroid; the capture's phone check gives it 0 %. A role scan should reward some 200 Hz-1 kHz
  harmonics for a game played on phones.

## 5. Tools (outside the repo, in the NOVA work folder)

`~/Music/Ableton/NOVA v1 Project/v2-work/`: `pad_scan.py` (pads; `track` mode measures an existing track on a copy),
`role_scan.py` (bass, arp, lead with role probes), `kit_scan.py` (kick and perc pads of drum kits), `scan_report.py`
(gates, score, top 10 into `top10.md`), `pad_finalists.py` (stages finalists on twins of the current sound),
`pad_design.py` (Pad D), `ab_pad.py` (solo-switched, loudness-matched, labelled A/B with a log). Candidate lists come
from browser searches (`search_browser`, `browse("drums")`).

## Open questions

- A metric that separates "flangy" (modulation on noise) from clean ensemble width; today's wobble does not.
- Kick and perc thresholds are engineering guesses, not yet calibrated on a sound the producer judged.
- Whether Fred hears Pad D's dark top (2-8 kHz about 33 dB under 200 Hz-2 kHz) as heavy or as dull.
