---
name: listening-loop
description: How a composing agent checks its own music in Ableton Live through the ableton MCP when it cannot hear - after note edits (analyze_notes), after sound or mix changes (capture, analyze_audio take), before keeping a change (compare against best, takes keep or restore), before calling stems done (tempo sweep, solo mode, blind A/B by a fresh subagent), and against the references the user named (ref, compare refs). Use whenever you compose, sound-design or mix with the ableton tools.
---

# Listening loop protocol

You cannot hear. These tools turn what you made into exact checks on the notes, measurements on the
audio and differences between takes (docs/listening-loop-prd.md section 12). The spec of the brief is
`ears/specs/nova.spec.json` unless the user names another (`spec=`).

1. **After every note edit:** `analyze_notes()`. Clear its fails before rendering anything. `where` is clip
   time ("3.1.1" = bar 3, beat 1); names are Live's convention (C3 = 60). Parts with MIDI effects are
   marked "before MIDI effects": their rhythm comes from audio onsets instead.
2. **After a batch of sound or mix changes:** `capture(note="what changed")` records at the set's middle
   tempo (140 BPM for NEON, about a minute, audible) and returns the audio checks. Clear the fails. If the
   result says it is still recording, call `capture()` again with no arguments.
3. **Before keeping a change:** `compare("latest", "best")`. If nothing regressed beyond noise,
   `takes(action="keep", take=<latest id>)`; otherwise `takes(action="restore", take=<best id>)` (check
   with `dry_run=True` first). The first take of a set and tempo has no best: keep it if its fails are clear.
4. **Tempos:** work at the middle tempo. Before calling a stem set done, capture the lowest and highest tempo
   (`capture(tempos=[100, 180])`; audio.tempo_consistency compares a part's loudness across tempos). Sweep
   every tempo (`tempos="all"`, about 8.5 min for NEON) only at milestones.
5. **At milestones:** `capture(mode="solo")` (each stem with its return effects and the master chain; about 4
   minutes per tempo), and `compare(..., blind=True)`: give only the packet to a fresh subagent that does not
   know which take is new, and read the key file after its verdict.
6. **Against the references** (outside music the user named, measured once and kept as numbers):
   `compare("latest", "refs")` places the top tier's band balance, dynamics (loudness range, peak to
   loudness, short-term spread), stereo width and onset density inside, above or below the range the
   references span; `audio.balance` warns outside it. It is a direction, not a target: a game stem sum at
   -14 LUFS is meant to be less dense than a club master, so dynamics come back as information.
   `compare("latest", "refs:sparse")` puts tier T2 against the references' sparse sections. `ref(action="list")` shows the references; a new
   one is `ref(action="measure", uri=<Spotify track>)`, which plays it in the Spotify app for as long as the
   track lasts (stop Live first; call `ref()` to keep waiting).
7. **Claim only what the evidence supports.** Passing every check does not mean it sounds good. A
   subjective claim needs a blind verdict or the user's ear.
8. **The human listening check stays the release gate** (soundtrack PRD section 10).

Reading the audio report:

- Tier sums T1..T5 are built the way the game layers stems (pad + arp, + bass, + kick, + perc, + lead),
  each stem looped with the game's 10 ms equal-power crossfade. T5 must be -14 LUFS (±0.5) and at most
  -1 dBTP; a lower tier louder than the next points to cancellation.
- audio.sum_null: the captured stems plus returns must cancel the main mix by 40 dB; if not, something
  reaches the master that was not captured (a master effect, or a track outside the spec).
- Fuzzy numbers (masking, analyser bands, phone survival) are information, never pass or fail.
- Captures run at Live's sample rate (44.1 kHz here); delivery files must be 48 kHz, 24-bit
  (`analyze_audio(take=..., strict=True)` or `uv run ears acceptance <masters>` checks exported files).

- Reference numbers are level-independent: a streamed track's level is the player's, so it carries no
  loudness figure; `meter(source="live")` measures Live's output through the same loopback.

Not available yet: audio-model listeners (`listen`, `ab_test`).
