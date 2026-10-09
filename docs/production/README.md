# Production knowledge base

How to make music like a professional producer and sound engineer in **Ableton Live 12** when you are an agent
that cannot hear and works through this repo's MCP tools. Written on 2026-10-08 after a day of recomposing the
NOVA game soundtrack ended with the producer pausing the work: the agent chose sounds and mixed by numbers, changed
many things at once and lost the sounds he had approved (`docs/handoff/2026-10-08-nova-v2-paused.md`). Each digest
was researched from the Live 12 manual, engineering literature, artist and engineer interviews and tutorials, and
cites its sources; claims are tagged where the evidence is weak or derived.

Start with **[00-agent-playbook.md](00-agent-playbook.md)**: the rules, the change loop, the table that turns the
producer's words into causes and first moves, and the tool pitfalls. The `pro-production` skill
(`.claude/skills/pro-production/SKILL.md`) points agents here automatically.

| # | Digest | Read it when you |
| --- | --- | --- |
| 00 | [Agent playbook](00-agent-playbook.md) | start any music task |
| 01 | [Live 12 workflow, routing and organisation](01-live-workflow.md) | set up a session, route, use racks, commit audio, or need to know what the tools cannot do |
| 02 | [Synthesis fundamentals and Live's instruments](02-synthesis-and-live-instruments.md) | choose an instrument, read a preset, reason about timbre, pitch and detune |
| 03 | [Sound design recipes by role](03-sound-design-recipes.md) | build a pad, drone, bass, lead, pluck, arp or FX; make something bigger or cleaner |
| 04 | [Drums and low end](04-drums-and-low-end.md) | design or process kicks, basses and drums; set groove and swing |
| 05 | [Gain staging and metering](05-gain-staging-and-metering.md) | set levels, read meters, reason about LUFS, true peak and PLR |
| 06 | [Mixing](06-mixing.md) | balance, EQ, compress, add space and width |
| 07 | [Mastering and loudness](07-mastering-and-loudness.md) | finish a release, hit a loudness target, export, or set stem loudness |
| 08 | [Arrangement and composition](08-arrangement-and-composition.md) | write parts, voice chords, avoid "wrong notes", shape pace and energy |
| 09 | [Industrial, EBM, techno, Nine Inch Nails and Boys Noize](09-industrial-ebm-techno-nin.md) | work in that palette |
| 10 | [Adaptive game music](10-game-audio-adaptive-music.md) | make stems, tiers and loops a game plays |
| 11 | [Listening without ears](11-listening-without-ears.md) | judge audio from measurements, compare takes, run auditions with a human |
| 12 | [Live 12 devices reference](12-live-devices-reference.md) | set device parameters (purpose, key parameters, pro settings, pitfalls) |
| 13 | [Scanning presets by role](13-preset-scanning.md) | shortlist presets for a role from the whole library (gates, measures, calibration, what Live's pads contain) |
| - | [Live 12.4.6 device parameters](reference/live-12.4.6-device-parameters.md) ([JSON](reference/live-12.4.6-device-parameters.json)) | need the exact parameter names, ranges and items, dumped from the running Live |

Regenerate the parameter reference after a Live update with `scripts/dump_device_parameters.py` (it only touches
its own scratch tracks). The digests reflect what was readable on 2026-10-08; each ends with open questions and
places where sources disagree. When you learn something new in a session, add it to the relevant digest with its
source, and record what the producer said in the handoff notes.
