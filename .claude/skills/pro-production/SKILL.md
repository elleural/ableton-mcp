---
name: pro-production
description: How to make music like a professional producer and sound engineer in Ableton Live 12 through the ableton MCP when you cannot hear - sound design, synthesis, drums and low end, gain staging, mixing, mastering and loudness, arrangement and harmony, the industrial/EBM/Nine Inch Nails palette, adaptive game stems - and how to work with the human producer (read the patch, one change at a time, keep the approved version, loudness-matched labelled A/B, the producer decides). Use before composing, designing or choosing sounds, mixing, mastering or delivering stems with the ableton tools.
---

# Producing like a pro without ears

The knowledge base is `docs/production/` (researched 2026-10-08, sources cited in every file). Read
`docs/production/00-agent-playbook.md` first: the rules, the change loop, the feedback-translation table and the
tool pitfalls. Then read the digest for the job in front of you:

| Job | Read |
| --- | --- |
| Choosing or designing a sound | 02 synthesis and Live's instruments, 03 sound design recipes, 11 listening without ears |
| Kick, bass, drums, groove | 04 drums and low end |
| Levels, meters, loudness numbers | 05 gain staging and metering |
| Mixing | 06 mixing (with 05 and 11) |
| Master, loudness targets, export, stem loudness | 07 mastering and loudness |
| Writing, voicing, arranging, pace | 08 arrangement and composition |
| Industrial, EBM, techno, Nine Inch Nails / Boys Noize | 09 genre deep dive |
| Game stems, loops, tiers, seams | 10 adaptive game music |
| Live workflow, routing, racks, what the tools cannot do | 01 Live workflow |
| Exact device parameter names and ranges | 12 devices reference and `docs/production/reference/live-12.4.6-device-parameters.md` |

Non-negotiables (each is explained in the playbook):

1. The producer's ear decides. Measurements diagnose; they never choose a sound or justify a mix move on their own.
2. Never match one instrument to a full-mix reference spectrum, never limit individual stems to hit a loudness number,
   never change tracks other than the one you were asked to work on without asking.
3. Read every parameter of a preset (`get_device`) before using it, and confirm the pitch it actually sounds.
4. Live names octaves with C3 = 60. Keep the low register to roots, fifths and octaves; the lowest note is the root.
5. One change at a time. Keep the approved version (muted twin track or a take snapshot), loudness-match within
   0.2 LU, announce what will play in which order, and let the producer choose.

For measuring what you made (notes checks, captures, comparisons against takes and references), follow the
`listening-loop` skill.
