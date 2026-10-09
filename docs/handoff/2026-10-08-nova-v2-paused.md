# Handoff: NOVA v2 recomposition, paused (2026-10-08)

Fred paused the industrial recomposition of the NOVA (tetris-nova) soundtrack: "it's not getting better", the
agent "does not have the skillset". Before resuming, read the production digests in `docs/production/`
(start with `00-agent-playbook.md`). This note records where things stand so nothing has to be rediscovered.

## The brief

- Recompose the game's NEON (and later MAINFRAME) music in the style of **Nine Inch Noize** (Nine Inch Nails
  reworked by Boys Noize). Fred's reference tracks: Vessel, She's Gone Away, Closer, As Alive As You Need Me To Be
  (album `spotify:album:7lcpCG4RBy3njzxHXlhOnp`; he plays them in the Spotify desktop app).
- The game contract still holds: A minor, one triad per bar, NEON progressions A = Am Am Dm Dm, B = Am F Dm E;
  loops kick 2 / perc 4 / pad 16 (shared by A and B) / bass, arp, lead 8 bars; tiers T1 pad+arp, T2 +bass, T3 +kick,
  T4 +perc, T5 +lead; tempos 100-180. Details: the soundtrack digest in the work folder (below) and
  `ears/specs/nova.spec.json`.

## What Fred said, in order (the useful signal)

1. Pass 1 (acid/EBM): "sounds horrible", "pace is way too fast", synths "like a circus, not a vast synthetic
   landscape". -> Half-time drums at 140, slower parts.
2. "Pick synth sounds closer to the songs; spend more time on pure synth pad design before composing."
3. Pass 3-5 (instruments chosen by timbre audition): "a lot of the sounds I am hearing right now sound awesome,
   you're on the right track". **Pass 5/6 is the last mix he liked.**
4. Pad: "too hollow, should be a bit meatier" -> "you still picked the wrong one; your first search result was the
   right one, raspy and heavy" -> picked "#2" (Dark Throne gritty) -> "wrong notes or pad tuning" -> "still not
   right" -> live reactions: too flangy (chorus), airy (noise / sub octave up), too distorted (saturator and a
   squashing limiter), wants "clean and big".
5. After listening to the references: wants the background synth "big and heavy and clean" like them. Liked
   "the first sound after you stopped listening to Spotify" -> saved as **base pad**; asked for bigger versions
   (echo, reverb, chorus) while keeping the base for comparison.
6. "You are applying effects to the wrong instruments or globally ... this sounds like garbage." Cause: the
   pass 7-8 metric-driven limiter/EQ/fader changes on every track. Fixed by restoring the pass-6 snapshot.
7. Paused composition; asked for deep research into pro production (this branch).

## State of the Live set (`~/Music/Ableton/NOVA v1 Project/NOVA v1.als`, unsaved changes at pause time)

- kick, perc, bassA/B, arpA/B, leadA/B: **restored exactly to pass 6** (take `neon-140-AB-0006`, every device
  parameter and fader, via `restore_mix.py`). The arps' filter cutoff moves with a clip envelope.
- History: passes 3-6 used the Dark Throne preset (Sub 39.4 % at -2 octaves, Noise 18.9 %, LPF 372 Hz, both main
  oscillators at 0 %) with its Sub lowered to 15 % and an EQ, tremolo and 8 s reverb chain: the pad Fred called
  hollow.
- `pad` (the track the game spec uses): **muted**. Holds Fred's earlier pick "#2": Dark Throne (Poli, Creative
  Extensions) Sub 50 % at -2 octaves, Noise 26 %, LPF 450 Hz, Res 12 %, Saturator Analog Clip 7 dB / -4 dB, other
  effects switched off, Utility Bass Mono 200 Hz, Limiter True Peak -6 dB; clips rewritten with sub-safe open
  voicings (`PAD_VOICINGS` in `nova_v2.py`).
- `base pad`: **Fred's base**, unmuted, fader -6 dB. Dark Throne with Saw 80 %, Pulse 0, Sub 35 % at -1 octave,
  Noise 0, LPF 1.4 kHz, Res 0, Chorus off, Random Pan 50 %; Hybrid Reverb Dark Hall 5 s, size 100 %, modulation 0,
  30 % wet; Utility Bass Mono 120 Hz; open voicings. Full record: `v2-work/base_pad.json`.
- `pad tuned`: muted clone of base pad tuned toward the As Alive intro synth by measurement (Chorus-Ensemble
  70 % at 0.4 Hz, Utility width 180 %, reverb 12 s, LPF 850 Hz, Sub 65 %, Pulse 25 %; distance 5.67 -> 2.81).
  **Fred has not judged it on its own**; he heard it while the damaged pass-8 mix was playing.
- Tempo restored to 120 (captures run at 140 and put it back). MID kicks are half-time (deviates from the
  original four-on-the-floor MID band, at Fred's request for a slower pace).

## Evidence and tools (outside the repo)

- Work folder: `~/Music/Ableton/NOVA v1 Project/v2-work/` - `nova_v2.py` (all note material), `timbre.py`,
  `compare_take.py`, `stem_diag.py`, `mix_sim.py` (offline stem mix with gain/EQ/limiter), `restore_mix.py`,
  `pad_choices.py`, `pad_match.py`, `tune_pad.py`, `synth_probe.py`, `soundtrack-digest.md`, `recompose-plan.md`.
- Takes: `NOVA v1 Project/ears/takes/neon-140-AB-0001 ... 0008` (stems, mix, report, and `snapshot.json` with
  every device parameter: the restore points).
- References: `~/Music/AbletonMCP/Ears/refs/` (Vessel, She's Gone Away profiles); `v2-work/ref_timbre.json`
  (10 sections), `v2-work/synth_probe.json` + `synth_target.json` (the sustained synth layer of all four tracks,
  0-116 s, per 4 s window: band balance, tonal peaks as notes, flatness, width). Audio was never stored.

## What was learned (also in `docs/production/00-agent-playbook.md`)

- **Choosing or mixing by numbers failed.** A full-mix reference spectrum is not a target for one instrument;
  per-stem limiting to hit true peak destroyed the sound. Measurements diagnose; Fred decides.
- **Live's octave naming:** C3 = 60, so MIDI 57 = A2 = 220 Hz and MIDI 45 = A1 = 110 Hz. The early bass and pad
  comments were an octave off.
- **Dark Throne is a sub-oscillator (-2 oct) plus noise** with both main oscillators at 0 %: hollow and airy by
  design. Its sub put chord thirds at 55-65 Hz and a D against the bass's E in variation B: "wrong notes".
- **Low-register intervals:** keep octaves and fifths below about 150 Hz; thirds there sound muddy or out of tune.
- **The references' background synth** (As Alive intro, Vessel intro): one low root (41-49 Hz) with a full
  saw-like harmonic stack to about 2 kHz, side/mid about 0.75-0.95 above 200 Hz, little noise, roll-off above 2 kHz.
- **Tooling:** `lom_get` lists show only the first 32 names (`count` has the total), so by-name checks past
  index 31 silently fail; use `get_mixer`/`get_track`/`delete_track(name)`. Equal-power 10 ms seam crossfades in
  the game overshoot by up to 3 dB on correlated audio (a linear crossfade would not).

## When resuming

1. Read `docs/production/00-agent-playbook.md`, then 03 (sound design), 06 (mixing), 11 (listening without ears).
2. Start from the pass-6 mix with `base pad`. Ask Fred to judge `pad tuned` against `base pad`, alone and in the
   mix. Change one thing at a time, keep the previous version on a muted twin track, loudness-match, label.
3. Only after Fred approves the pad: move it into the `pad` track, then revisit the mix gently (no per-stem
   limiters; let the delivery pipeline's shared gain curve handle seam peaks), then LOW/HIGH bands, MAINFRAME,
   and delivery to tetris-nova.
