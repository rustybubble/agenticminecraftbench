# SplitCheck: checking AI against pro Minecraft speedrunners

**Pitch:** Finishing a game no longer tells you much. SplitCheck checks whether an AI makes the decisions a pro Minecraft speedrunner makes at each stage of a run, and names every shortcut it misses and what it cost.

## Exigence

- **Game characters are becoming agents.** NVIDIA ACE characters plan and act on their own, and Altera's Project Sid ran 1,000 agents in one Minecraft world (links in the team plan; not re-checked by B).
- **Agents can finish, but slowly.** Four Gemini 4 agents beat Minecraft in **27 h 14 min**, dying **605 times** on Easy ([Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/google-deepmind-claims-four-gemini-4-agents-beat-minecraft-in-27-hours-by-writing-2-783-programs-of-their-own-the-ai-team-died-605-times-on-easy-difficulty-and-ran-up-an-estimated-usd520-in-tokens)). The human random-seed record is **6:39.813** (Skycrab, [speedrun.com](https://www.speedrun.com/mc/runs/y44238ky)), so the agents were about 245× slower. That compares different categories, so treat it as context only.
- **The same-seed comparison is the fair one.** On seed `8398967436125155523` (Java 1.16.5), the [rmalde/minecraft-agent](https://github.com/rmalde/minecraft-agent) LLM agent's best run is **8:43.300** (`README.md:7`). A verified human run on the same seed takes **2:54.545** ([speedrun.com](https://www.speedrun.com/mc/runs/yoex3d0z)). The agent is **3.0× slower**, and it had help the human did not: Peaceful difficulty instead of Easy, a pre-surveyed route, the seed's coordinates, and a dragon-position sensor.
- **The agent's own notes list pro-avoidable mistakes:** "The agent collected extra food, wood, and tools on Peaceful difficulty" (`optimization/NOTES.md:13`). It "placed and recovered crafting tables after crafting was complete" (`NOTES.md:14`). It died walking back through a dragon-breath cloud (`optimization/nether/REVIEW.md:37`).
- **So "did it finish?" is the wrong question.** What matters is efficiency and judgment against human experts.

## What we built

- **21 decision tasks** (`tasks/`) covering 9 splits of an Any% run: reset (3), Nether entry (3), bastion (3), fortress (2), blind travel (2), triangulation (2), portal room (2), dragon (2), full route (2).
  - 7 tasks use the real surveyed seed and follow the human route (reset, Nether entry, the "do you need rods?" fortress check, Nether exit, full route). The other 14 are generic random-seed (RSG) situations for the splits this seed skips (bastion, fortress, triangulation, portal room) and for general Nether entry and dragon play. They are sourced from the wiki and game data, not from the human run.
  - Each prompt is self-contained: version, difficulty, state as JSON, question, and the exact JSON reply format.
- **Reference answers** (`reference/`) for every task. Each has the reason it is right, the trap, the pro techniques with sources, one miss tag, at least one alternate valid answer, and at least one broken answer with its expected verdict.
- **Pro split table** (`splits/pro_splits.json`), taken from the human runner's own segment times, and a **time-cost table** (`splits/time_costs.json`). Every cost is tagged `wiki`, `run`, `agent` or `estimate`.
- **Reproducible answer math** (`tools/compute_answers.py`): triangulation, Nether coordinates, barter expectations, rod counts, eye-break odds, and the ruined-portal frame search. `tools/validate_refs.py` checks that alternates pass and broken answers fail the stated tolerances.
- **The checker** (`code/`, Person A) and the AI runs (`attempts/`, `runs/`, Person C).

## How it checks

1. **Legality.** A state simulator runs a `plan` answer action by action, tracking inventory, dimension and position. It rejects steps that cannot happen: lighting a portal without flint and steel, mining obsidian without a diamond pickaxe, building a 10-block frame from 8 obsidian, or killing blazes on Peaceful. Verdict: `ILLEGAL`.
2. **Time against the pro route.** Each legal plan is priced from `splits/time_costs.json`. Travel uses wiki movement speeds, and the End fight uses the human run's own End segment. A plan more than the task's tolerance (15–20 s) slower than the priced reference is `SLOW`.
3. **Exact answers.** Number, coordinate and choice tasks are compared with the reference within a stated tolerance. Examples: ±2 Nether blocks (16 overworld blocks) for portal links, ±16 blocks for triangulation, exact counts for obsidian and rods. Outside tolerance is `WRONG`.
4. **Techniques missed.** Each reference lists the pro techniques that apply (for example `nether_travel_8to1`, `complete_ruined_portal`, `skip_fortress_active_portal`, `bed_one_cycle`). The report names the ones the AI missed and the seconds each cost, along with one of 8 miss tags: `no_reset_judgment`, `brute_force_over_trick`, `no_nether_shortcut`, `ignores_information`, `resource_miscount`, `mob_rule_unaware`, `detour_overprep`, `unnecessary_risk`.

## Ground truth and fairness

- **Every number has a source**: the seed survey files, game data (the 1.16.1 and 1.16.5 barter loot tables), minecraft.wiki pages read as raw wikitext with line numbers, Wikipedia's speedrunning article, or the speedrun.com run's own segment times. `SOURCES.md` maps each source to the tasks that use it. Anything not confirmed is marked `"verified": false` and listed in `UNVERIFIED.md`. Only T01 is unverified at the task level.
- **Seed-exact answers, not trivia.** Examples:
  - The ruined portal needs exactly **7** new obsidian, because the most intact frame is blocked by crying obsidian.
  - The route needs **17** obsidian, so the village chest is required even though the two portal chests hold 15.
  - The Nether exit belongs at **(−141.25, 107)**.
  - **0** blaze rods are needed: all 12 End frames are pre-filled, and on Peaceful blazes cannot spawn anyway.
- **Any legal route counts.** Plans are scored only by legality and time, never by string match. Each task's alternates must come back `OK`: a fresh 10-block frame instead of completing the ruined one, a different crafting order, rounded coordinates, or the staircase position instead of the chunk corner. T18 accepts both the one-cycle and the zero-cycle dragon kill, since both are documented strategies.
- **Checker tests are kept apart from AI results.** Reference, alternate and broken answers prove the checker works. They are never counted as AI results.
- **Version consistency.** All tasks use 1.16.5, the seed's version, except one deliberate pair: T07 (1.16.1) vs T08 (1.16.5). Pearls per gold ingot fell 4.3× between them (0.284 → 0.065).

## What we found

Model: TODO(C) · Date: TODO(C) · One fresh conversation per task, first answer kept, prompts exactly as in `tasks/*.json`. Raw attempts are in `attempts/`.

| Split | Tasks | OK | SLOW | ILLEGAL | WRONG | Seconds lost vs pro (plans) |
|---|---|---|---|---|---|---|
| reset | 3 | TODO(C) | – | – | TODO(C) | – |
| nether_entry | 3 | TODO(C) | TODO(C) | TODO(C) | TODO(C) | TODO(C) |
| bastion | 3 | TODO(C) | – | – | TODO(C) | – |
| fortress | 2 | TODO(C) | – | – | TODO(C) | – |
| blind_travel | 2 | TODO(C) | – | – | TODO(C) | – |
| triangulation | 2 | TODO(C) | – | – | TODO(C) | – |
| portal_room | 2 | TODO(C) | – | – | TODO(C) | – |
| dragon | 2 | TODO(C) | – | – | TODO(C) | – |
| full_route | 2 | TODO(C) | TODO(C) | TODO(C) | TODO(C) | TODO(C) |
| **Total** | **21** | TODO(C) | TODO(C) | TODO(C) | TODO(C) | TODO(C) |

**Top misses by tag:** TODO(C), from `runs/results.csv`. Count of failed tasks per `miss_category`, plus the techniques missed most often.

**Worked example: T12, Nether exit on the real seed.**
- **Task:** You are in the Nether at (−47.5, 77, 24.5). The End portal is active at overworld (−1130, 34, 856). Where in the Nether do you build your exit portal?
- **Pro answer:** (−1130 / 8, 856 / 8) = **(−141.25, 107)**. Y is not scaled.
  - With no existing portal nearby, the game places the overworld portal within 16 blocks of 8× the Nether position, so each Nether block of error costs 8 overworld blocks.
  - The human took 2.450 s from leaving this portal to entering the End portal.
  - The agent built at (−141, 40, 104), 3 Nether blocks off, and arrived about 24 overworld blocks away.
- **AI answer:** TODO(C)
- **What SplitCheck caught:** TODO(C), e.g. the distance in Nether and overworld blocks, the verdict, and the missed technique `precise_portal_link` / tag `no_nether_shortcut`.

## Limitations

- **One set seed.** The seed-based tasks come from one surveyed seed, and it is unusual: all 12 End frames are pre-filled, about a 1-in-10¹² event per portal (though over 8 million such seeds are known). Generic tasks cover the normal random-seed splits (bastion, fortress, triangulation), but they are not tied to a pro VOD.
- **Peaceful vs Easy.** The agent ran on Peaceful and the human on Easy. Seed tasks state their difficulty. The human time is an upper bound for Peaceful, since Peaceful is not harder.
- **Time costs.** Movement, portal delay, obsidian mining, barter time and the End segment are sourced. Chest, placement, crafting-overhead and gravel costs are estimates (tagged `estimate`). Conclusions should be checked at ±30% on those costs.
- **No VOD timestamps.** The sandbox could not play the VOD. The split durations come from the runner's own comment on the verified run, not from our timing. `UNVERIFIED.md` lists what a human must time: the boundaries, the human's beds and portal coordinates, and the bed count.
- **Unverified items.** T01's reset label lacks a runner-side source (mcsr.info was blocked). The ruined-portal air blocks and the spawn point should be confirmed in-game. See `UNVERIFIED.md`.
- **Chatbot, not live agent.** These tasks test decisions, not execution: mouse control, pathing and combat timing are out of scope. A model that answers every task correctly can still play slowly.
