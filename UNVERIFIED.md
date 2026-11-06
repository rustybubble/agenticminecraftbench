# Unverified items (for a human teammate)

## Efficiency check (headline): open items, 13:30

A. **Optional: 1:48 segment times.** The per-segment baseline is now the 2:49 run, so this is no longer blocking. Fill `baseline/timing_sheet_1m48.md` (5 rows) from https://www.youtube.com/watch?v=2NEvhsZG5iY, then run `python baseline/make_splits.py`. No text source has these splits: not the video description, not the speedrun.com comment, and the raw VOD is a 2 h 8 min stream.
B. **Optional: 1:48 playbook.** It would add the pro-side "why". Answer the 23 questions in `baseline/pro_1m48_playbook.md`. These decide whether `extra_items` (beds), and the "why" for each segment, hold up against the pro.
C. **Where the pro's Nether exit lands** (playbook Q2.3, Q3.1). The 2:49 run's 2.45 s exit → End split implies it lands at the portal, but nobody has seen it.
D. **Reported banner objectives** in `analysis/agent_vs_pro.md` (End: fountain → west cover → "maintain breath-safe cover… next perch" → detonate at about 8:25) come from the teammate's reading and are not yet in `timeline.json` with timestamps. Add them, or keep them labelled "reported".
E. **Banner 8:36.7 vs README 8:43.300** (6.6 s gap). Unexplained; we use the banner (favours the agent). Ask the agent's author.
F. **Model latency of the 8:43 run** is not published. Only an earlier run's totals are (REVIEW.md:58).
G. **Exit-terrain inference:** "no surveyed standing surface near the ideal exit point" comes from the absence of `exit-terrain.json` entries at x −143..−139, z 102..109. Not confirmed in-game.
H. **`extra_items` seconds** use a 4 s/bed estimate (pro pace) up to about 15 s/bed (agent average over a phase with cuts). Both are estimates.

## Decision tasks (secondary and supplementary)

Everything here is either marked `"verified": false` in a file, or is an assumption the files depend on that B could not confirm from the sandbox. Each item says exactly what to check.

## Needs the VOD (https://www.youtube.com/watch?v=n1M95cySBQ0, 3:31 long)

1. **VOD timestamps** for the four segment boundaries in `splits/pro_splits.json` (first portal enter, second portal enter, End portal enter, finish). The segment *durations* are verified from the runner's own speedrun.com comment; only the `vod_timestamp` fields are `null`. Fill `vod_timestamp` as `mm:ss` and set `timestamp_verified: true`.
2. **What the human collected before the first portal**: which chests, how many beds (and which), whether they used the ruined frame (7 placements) or a fresh frame. This decides whether `T04`/`T20` reference plans match the human route. Note it in `splits/pro_splits.json` → `notes`.
3. **The human's Nether exit portal coordinates** (F3 is on in the run). `T12` claims the ideal is (-141.25, ~, 107); the 2.450 s from exit to End portal suggests the human built very close to that. Record the coordinates in `reference/T12_blind_seed_nether_exit.json` → `why`.
4. **Number of bed explosions** the human used on the dragon. `splits/time_costs.json` → `rules.dragon_beds_required` is 6 (from the agent and Wikipedia's "fewer than 7").

## Needs a game check (C's 1.16.5 server on the seed, `/tp` + F3)

5. **Ruined portal plane is air** where the 7 new obsidian go: at x = -285, positions (z, y) = (258, 70), (257, 67-69) and (260, 67-69). `T05` states this in the prompt. `REVIEW.md:9` says the 7-block frame was built in practice, but the survey file only lists obsidian and crying obsidian, not air.
6. **World spawn is (-181.5, 70, 234.5)**. B took it from `optimization/nether/spawn-survey.json` → `position`; the file does not say it is the world spawn. `T02`, `T04`, `T20` start there.
7. **The first portal arrives at Nether (-47.5, 77, 24.5)** (from `entry-link.json`). `T12` and `T20` use it. It depends on where exactly the entry frame is built.
8. **End portal frames all filled** at (-1130, 34, 856): survey shows 12/12 `eye: true`. This is a 1-in-10^12 event for a random stronghold (wiki), so a screenshot is worth having. The human's 2.45 s exit-to-portal split supports it.

## Needs a runner source (mcsr.info was blocked)

9. **T01 (reset a plains spawn with no trees, water or structures)**: `verified: false`. Wikipedia says runners reset to find villages, ruined portals and beaches, but no source says "no trees = reset". Find a runner guide or commentary quote, or drop T01. Note: `docs/PLAN_ADDENDUM.md` (#6) suggests cutting reset tasks; T02 (seed with a verified 2:54 run) and T03 (beach, Wikipedia) are better sourced.
10. **mcsr.info one-cycle guide** (https://mcsr.info/speedrunning/one-cycle) for `T18`. Wikipedia covers it, so T18 is marked verified; the guide would be a stronger runner-side source.

## Time costs marked `estimate` in `splits/time_costs.json`

11. `loot_chest` 1.5 s, `place_block` 0.3 s, `build_portal_*` (except `mine_obsidian`), `light_portal` 0.5 s, `mine_gravel` 0.9 s, `mine_bed` 0.5 s, `mine_other`, `place_eyes`, `kill_blaze` 10 s, `barter_per_ingot`, `kill_ender_dragon_melee` 300 s, `enter_portal_end` 0 s, and the assumption that runners sprint-jump everywhere (`travel` uses 7.127 m/s). Time a few of these from the VOD or the wiki breaking-time tables. The write-up should show conclusions hold at ±30% on these.

## Known conflicts in the source repo

12. `optimization/nether/config.json:65` says "Rotated open frame: nine new obsidian", while `REVIEW.md:9` says 3 existing + 7 placed. B's geometry check (`tools/compute_answers.py ruined_portal_seed()`) agrees with REVIEW (7) for a 2x3 interior. T05 lists 9 as a broken answer. If the game check in item 5 fails, T05's answer changes.

## Version notes

13. Piglin aggression rules (`T09`) come from the current-version wiki page. The rules for gold armor, chests and gold blocks have existed since 1.16, but the page also lists newer containers (copper chest, boat with chest). Not checked against 1.16.5 game code.
14. Eye-of-ender target point (chunk NW corner; staircase at chunk offset 4, 4) is from the current wiki. `T14` does not depend on it (the prompt says to assume both eyes fly to the same point, and the staircase alternate is within the 16-block tolerance).
