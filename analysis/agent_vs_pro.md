# Agent vs pro on seed 8398967436125155523: where, why, what it missed

- **Agent:** the published Astra + JEV run. Milestone brackets come from the montage banner (`agent_runs/published_montage/timeline.json`).
- **Pro (headline):** Rayoh, 1:48.421 IGT / 1:59.331 RTA ([speedrun.com](https://www.speedrun.com/mc/runs/zqe4g39z)). **Segment times: waiting on a human** (`baseline/timing_sheet_1m48.md`).
- **Pro (backup, used for the numbers below until the 1:48 sheet is filled):** dumbo0116, 2:49.149 IGT ([speedrun.com](https://www.speedrun.com/mc/runs/yoex3d0z), segments from the run comment).
- **Numbers:** `fixtures/published_montage.json` → `expected` (rules in `baseline/rules.json`).

**Labels.**
- **confirmed (frame):** seen in a montage banner read, recorded in `timeline.json` with its timestamp.
- **confirmed (docs/code):** stated in the agent repo or its route config.
- **reported:** a banner objective the teammate read off the montage that is not yet in `timeline.json`. Treat it like inferred until a timestamp is added.
- **inferred:** follows from the time gap only.

**Coverage caveat.** The montage shows about 39 s of a roughly 517 s run (about 7.5 %). The agent repo's notes (`NOTES.md`, `REVIEW.md`) describe **earlier** runs of the same harness, not the 8:43 run. Its README says "Historical review notes describe earlier versions" (`rmalde/minecraft-agent:README.md:23`). Those notes show what the harness tends to do, not what happened in this run.

## Summary (vs the 2:49 backup; re-run against 1:48 when timed)

| Segment | Agent s (low–high) | Pro s (2:49) | Ratio | Verdict | Pro s (1:48) | Ratio (1:48) |
|---|---|---|---|---|---|---|
| spawn → Nether | 184.7–189.45 | 66.683 | 2.77–2.84× | SLOW | TODO(human) | TODO |
| Nether | 108.7–118.1 | 40.783 | 2.67–2.90× | SLOW | TODO(human) | TODO |
| exit portal → End portal | 51.55–56.7 | 2.45 | **21.0–23.1×** | **FLAG** | TODO(human) | TODO |
| End | 161.35–162.35 | 59.233 | 2.72–2.74× | SLOW | TODO(human) | TODO |
| **Total** | 516.2–516.7 | 169.149 | **3.05×** | | 108.421 IGT / 119.331 RTA | **4.76–4.77× IGT**, 4.33× RTA |

The run's median segment ratio is 2.79. Only the exit → End portal segment exceeds 2 × median, so it is the only FLAG. The other three segments are all about 2.7–2.9×: a steady slowdown with no single detour. The total ratio against 1:48 is known now, since it needs only the final time; the per-segment 1:48 ratios need the timing sheet.

## 1. Spawn → Nether entry (agent 184.7–189.45 s; pro 66.683 s)

**Where:** 2.8× slower, about 118–123 s lost.

**Why (agent side):**
- confirmed (frame): first supply chest by 00:14.700, at (−224.5, 71, 240.7), objective "Loot the first supply chest for the iron pickaxe".
- confirmed (frame): collecting the **4th of 8 beds** at 01:08.000. Objective switches to "Finish the remaining kit at the two supply chests" by 02:15.250.
- confirmed (frame): portal repair at 02:56.950: "Place one cobblestone portal frame block at (−282,67,259)".
- confirmed (frame): lit with flint and steel at 03:03.4; in the Nether at 03:09.450.
- confirmed (docs/code): the route's kit is **8 beds**, 20 obsidian, an iron pickaxe and flint and steel (`config.json:58-64`). The dragon died to **6** bed explosions (`README.md:9`).
- So the agent spent roughly 120 s (00:14.7 → 02:15.25) mostly on beds, about 15 s per bed. That is an upper bound, because the frames in between are cut.
- confirmed (docs), earlier runs: beds were collected through house walls and a 5 s pickup timeout expired (`REVIEW.md:43`); long village approaches timed out (`REVIEW.md:33`); the agent "repeated a long entry-path search" (`REVIEW.md:47`). These are the harness's known slow spots in this segment.

**Why (pro side):** TODO(human), from playbook Q1.1–Q1.7: order, bed count, chests, frame type.

**What it missed:**
- `extra_items`: 2 beds collected but never used (8 vs 6). Cost: 2 × 4 s (pro-pace estimate, `rules.json`) to 2 × about 15 s (agent average per bed). **Inferred**, and pending the pro's bed count: if the pro also takes 8, this tag goes away.
- Everything else in this segment is execution speed (inferred), not a route difference that we can see.

## 2. Nether (agent 108.7–118.1 s; pro 40.783 s)

**Where:** 2.7–2.9× slower, about 68–77 s lost.

**Why (agent side):**
- confirmed (frame): arrives at (−36.1, 77, 32.5); building the exit portal at (−138.7, 41, 103.8) at 04:58.150.
- confirmed (code): the Nether action is "Follow a normal walking and digging path to the surveyed Nether exit approach" (`nether-agent.mjs:47`). The exit needs a placed approach ("Place one safe approach block toward the Nether exit", `nether-agent.mjs:50`) and "ten obsidian blocks and four ordinary corner supports" (`REVIEW.md:9`).
- confirmed (docs/code): the surveyed waypoint path (`config.json:108-149` plus `netherRoute`) is 139 blocks horizontally against 125 straight-line, so only 12 % longer. That is about 20–25 s of movement at sprint or sprint-jump speed.

**Why (pro side):** TODO(human), from playbook Q2.1–Q2.4: route, movement, exit build time.

**What it missed:**
- `longer_path`: **mostly rejected**. The route is only about 12 % longer than straight, worth about 2–3 s.
- The remaining roughly 65–75 s goes to digging, descending 36 blocks (y 77 → 41), bridging and the exit build. **Inferred** from the gap; no frames are visible.
- `idle_wait`: model latency also falls here and in every segment (see "Across the run").

## 3. Exit portal → End portal (agent 51.55–56.7 s; pro 2.45 s), the outlier

**Where:** 21–23× slower, about 49–54 s lost. This is the only FLAG.

**Why (agent side), confirmed (docs/code + frame):**
- The route's Nether exit is fixed at (−141, 40, 104) (`config.json:34-39`; used by `nether-agent.mjs:52`). In the montage it is being built at (−138.7, 41, 103.8) (04:58.150).
- ×8 gives (−1128, 832), 24 overworld blocks north of the active End portal (−1130, 34, 856) (`config.json:52-56`). The game made the arrival portal at x −1130..−1129, y 24–26, z 837 (`exit-link.json`). The agent came out at (−1129.5, 24, 837.5) (montage 05:02.800): **18.5 blocks horizontally and 10 blocks below the portal**, 21 blocks in 3D.
- Getting from there to the portal needs a dig/walk through the stronghold. The code action is "Walk and dig a normal path to the active End portal" (`nether-agent.mjs:58`), followed by the careful entry step (`nether-agent.mjs:57`). Earlier runs had "The pathfinder stopped above the End portal" (`REVIEW.md:35`).
- confirmed (frame): portal room at (−1129.6, 34.9, 856.5) at 05:54.350; in the End at 05:54.850.

**Why (pro side):**
- confirmed (run comment): "Second portal exit to end portal enter: 2s 450ms" (2:49 run). The pro's exit must therefore land almost on the portal.
- The ideal Nether position is (−1130/8, 856/8) = (−141.25, 107). The agent's exit is 3 Nether blocks off in Z.
- Where the 1:48 pro's exit lands: TODO(human), playbook Q2.3 and Q3.1.

**What it missed:**
- `missed_shortcut`: the exit-portal placement. Up to 49.1–54.3 s (the whole excess). This is an **upper bound**: if the agent had arrived next to the portal, some of its execution slowness would still remain.
- The placement part alone is confirmed. How the 49–54 s splits between placement and slow digging is **inferred**.
- **Fairness:** this coordinate was supplied by the route config written by the agent's authors ("The final route is fixed in `optimization/nether/config.json`", `README.md:104`). It is a miss of the agent *system* as published, not a decision the LLM made in the run.
- **Possible reason (inferred):** the Nether terrain survey `exit-terrain.json` has no standing surfaces at x −143..−139, z 102..109. That fits building over open space (lava) near the ideal point, which needs bridging. A pro bridges or builds there anyway.

## 4. End (agent 161.35–162.35 s; pro 59.233 s)

**Where:** 2.7× slower, about 102–103 s lost.

**Why (agent side):**
- confirmed (frame): arrives (100.5, 49, 0.5) at 05:54.850. "Detonate the already placed bed…" through 08:29.200. "Wait for the dragon death animation" at 08:33.700. COMPLETE at 08:36.700.
- reported: banner objectives move from fountain → west cover → "maintain breath-safe cover… next perch" → detonate at about 8:25.
- confirmed (docs): "killed the dragon with six bed explosions on the first landing" (`README.md:9`). "The End combat stage took 152 seconds" (`README.md:7`). So nearly all of the End time is **waiting for the first perch**, followed by one cycle.
- confirmed (docs), earlier runs: the harness waits east of the fountain, because "player distance affects strafe selection and player direction affects the landing approach" (`REVIEW.md:49`, from the 1.16.5 server classes). An earlier run died in breath clouds (`REVIEW.md:37`, `NOTES.md:54`). So the agent plays the End conservatively.

**Why (pro side):** TODO(human), from playbook Q4.1–Q4.6: time to first bed, perches, beds used.

**What it missed:**
- **Fairness:** perch timing is partly random ("Dragon flight and landing times can vary between runs", `README.md:7`). We cannot separate RNG from positioning without the pro's perch count and the agent's flight log.
- Possible `wrong_order` / waiting choice: inferred only.
- No death and no breath damage in this run (`README.md:9`: full health, no deaths).

## Across the run

- `idle_wait` (model latency): 131 JEV decisions and 35 Astra calls in this run (`README.md:11`). The total latency of this run is **not published**. A comparable earlier run (`nether-final-02`) logged 23.7 s of JEV and 26.3 s of Astra API time (`REVIEW.md:58`), but "Planner calls can overlap game actions, so API time is not the same as added run time" (`NOTES.md:7`). Reported as a separate line, not subtracted.
- **Clock:** the banner is wall-clock elapsed time (montage method). That is closer to the pro's RTA (119.331) than to IGT (108.421). Both ratios are reported.
- **Banner vs headline:** the banner shows COMPLETE at 8:36.7, but the README says 8:43.300. The 6.6 s gap is unexplained. We use the banner, which is better for the agent.

## Hypotheses from the brief

| Hypothesis | Status |
|---|---|
| Spawn → Nether: 8 beds collected, 6 used → 2 `extra_items` | confirmed for the agent (frame + docs); pro comparison pending the playbook |
| Nether: `longer_path` | mostly rejected (route 12 % longer than straight); the loss is execution, inferred |
| Exit → End: exit placed so the arrival is 21 blocks from the portal → `missed_shortcut` | **confirmed** (config, exit-link survey, montage XYZ, pro 2.45 s); size of the loss is an upper bound |
| End: waiting for perch, RNG vs decisions | confirmed that most time is the wait for the first perch (docs); RNG vs decision unresolved |
| Model latency as `idle_wait` | count confirmed, seconds unknown for this run |
