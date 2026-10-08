# Handoff: listening loop, phases 0–2 and the agent protocol (2026-10-07)

The PRD is [../listening-loop-prd.md](../listening-loop-prd.md), the build plan
[../listening-loop-plan.md](../listening-loop-plan.md), verified Live behaviour in
[../spikes.md](../spikes.md) (section "Listening loop capture"), and the calibration report
[../listening-loop-calibration.md](../listening-loop-calibration.md).

## State

- **Capture (phase 0, 2).** `capture` records Session clips in real time: temporary `cap:` audio tracks tap
  each part's track output (Post Mixer), every return and the main mix (Resampling), fired in one main-thread
  tick with the source clips. It is sample-exact (0 samples offset on every route, with delay compensation),
  unity gain, leaves the set as found (tempo, quantization, mutes, solos, arms, transport, Back to
  Arrangement), and cuts the folded second cycle into a take. `tap` (default), `solo`, tempo sweeps
  (`tempos=[...]` or `"all"`), `bars` for quick checks.
- **ears (phase 1).** A standalone package and CLI (`uv run ears ...`): spec loading, the notes ear, the
  measurement ear with game-style tier sums (each stem looped with the game's 10 ms equal-power crossfade),
  strict delivery-file checks, compare with blind packets, takes, the ledger, images, synthetic fixtures with
  every planted defect of PRD 13.2, calibration. BS.1770 loudness is numpy/scipy and matches ffmpeg's ebur128
  to 0.05 LU on the shipped masters.
- **Tools.** 82 (budget raised to 90): new `capture`, `analyze_notes`, `compare`, `takes`; `analyze_audio`
  gained `take=` and `strict=`. The protocol (PRD 12) is in the server instructions (595 words) and in the
  skill `.claude/skills/listening-loop/SKILL.md`.
- **Tests.** Offline: 2,143 pass (unit, contract, `tests/ears` on synthetic fixtures; CI on GitHub
  Actions). Live: `tests/live/test_capture.py` (C2–C4 on a calibration file, a multi-pass mute regression,
  errors and cancel), `tests/live/test_listening.py` (snapshot/restore round trip and undo) and
  `tests/live/test_export.py` pass against the NOVA set.
- **Live crashed once (23:49:47, not reproduced).** In a run of the whole live suite, Live 12.4.6 raised
  `FatalError: Uncaught exception [std::out_of_range] vector` at the end of the v2 end-to-end release test
  (`tests/live/test_e2e_release.py`: its body passed, its scratch cleanup then timed out), with the large
  unsaved NOVA set open. That test uses none of the listening-loop commands. Before trusting the whole live
  suite on this set again, re-run `test_e2e_release.py` alone after Live restarts, and save the set first.
  `test_export.py` assumed an empty arrangement past bar 201 and now places its material past the set's
  last event.
- **Takes on this Mac.** The NOVA set is unsaved, so takes live in `~/Music/AbletonMCP/Ears/untitled/`
  (neon 140 ×4 incl. one solo, 100, 180). Saving the set moves future takes to `<set folder>/ears/`.

## Findings about the NOVA soundtrack (for Frederic and the composer)

Real results of the new checks; none of these were fixed here.

1. **Equal-power seam crossfade overshoots.** In the game's playback model (tier sums), T5 true peak reaches
   −0.6 dBTP at several NEON tempos, exactly on loop seams; the same stems looped natively peak at −1.45. A
   10 ms *equal-power* crossfade adds up to 3 dB when tail and head are the same material, which a folded loop
   is. Use an equal-gain (linear) crossfade for folded loops in `src/audio/composed.ts`, or leave 3 dB more
   headroom.
2. **The shared pad clashes with variation B.** The pad's "common-tone" voicing holds E through bar 2 (F in
   progression B) and A through bar 4 (E, with G#): 35 semitone overlaps with bassB/leadB, and 29 of its 84
   held pitches fail notes.shared_stem. Only D and B are safe over both chords in bar 4 (PRD 7).
3. **Bass turnaround.** bassA's walk-down puts C2 on beat 3 of bar 8 over Dm (notes.chord_tones fails for
   bass by rule; the composer may decide it is a passing tone and the rule should allow turnarounds).
4. **Leads are sparser than the brief:** 55–59% rests against 40% ± 10 (warn).
5. **Loudness.** The shipped tier sums sit at −14.5…−14.7 LUFS (the composer's deliberate −14.6, outside
   ±0.5 of −14), and the MAINFRAME pad loses 1.3–1.5 dB in mono below 120 Hz (fail at 1 dB).
6. **Stem levels jump between tempos.** In the Live set the pad is 2.9 LU and the arps 2.2–2.4 LU louder at
   100 BPM than at 140–180, the perc 2.8 LU quieter at 100 (the LOW band's half-time pattern), bassA 1.8 LU
   quieter at 180 (audio.tempo_consistency, ±1 LU). The composer levelled the full mix per tempo in post, not
   each stem, so stems jump at level-ups (soundtrack PRD 6: "stem levels must be consistent across tempos").
7. **Live renders at 44.1 kHz.** Every capture warns (C5). Set Live's sample rate to 48 kHz to capture and
   export at the delivery rate.

## Deviations from the PRD (deliberate)

- Capture tracks are temporary (no `capture_setup`); status and cancel are `capture()` / `capture(cancel=True)`;
  `ledger`/`keep`/`restore` are `takes(action=...)`. Python's `ClipSlot.fire()` has no record length, so the
  engine stops the transport after the planned beats and ears cuts on bar lines from the clip markers.
- Tracks outside a tap pass are muted for the pass (their arrangement clips would play into the mix).
- One tap pass captures every variation when each has its own tracks and no part uses a send (the real set).
- `file.seam` measures fold (the head carries the body's ringing over the seam; unfolded heads start from
  silence) and clicks (seam high-frequency energy against the body's own transients). Comparing head and tail
  directly flagged every shipped master, because the composer's renders continued into the FILL scene, so the
  50 ms tails are not the loops' own continuation (harmless at a 10 ms crossfade, but not what the brief says).
- `audio.balance` and `compare` against references wait for phase 4; the balance check runs in fixture form
  against a synthetic envelope.

## Next

- **Phase 3 (listeners)** needs Frederic's answers: Gemini key and permission (PRD 15 q3), embeddings policy
  (q4), local model licences (L6), and his 20 blind picks (13.3). Nothing is enabled.
- **Phase 4 (references)** needs the reference tracks (q5) and the Scarlett model (q2) for `meter`.
- **Requests for core** (from the snapshot/restore build): call `song.sync_parameter_changes()` before every
  mutating command's `end_undo_step` (parameter writes otherwise land in the next undo step); let
  `refs.device`/`refs.chain` address rack return chains (`return:N`).
- Open PRD 15 q7 answers are taken from the set as composed (MAINFRAME B plays C; no D in NEON; shared pad),
  marked "assumed" in the spec; the MAINFRAME band split (LOW 100–120, MID 130) is assumed too.

## Wiring

After this merges, Live's Remote Script link goes back to the main checkout
(`uv run ableton-mcp install --force` there, then `uv run python -m tests.live.reload --full`), and the main
checkout needs `uv sync` for scipy and matplotlib. Claude Code sessions see the new tools after the `ableton`
server restarts (a new session).
