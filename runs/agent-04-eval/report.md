# Efficiency check: `agent-04`

Log: `agent_runs/agent-04/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=49.357 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | 2.4 |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=49.357 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress before failure

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | 10.236 | 29.0-33.0 | -22.764 to -18.764 | 8 | village chest (iron_pickaxe 1, obsidian 6) |
| chest_2 | 33.032 | 54.0 | -20.968 | 14 | obsidian chest (iron_ingot 6, obsidian 11) |
| chest_3 | 37.534 | 49.0-51.0 | -13.466 to -11.466 | 20 | flint chest (flint 1, obsidian 4) |
| flint_and_steel | not reached | 60.0-61.0 | - | - | not reached |
| portal_build_attempted | not reached | 55.0 | - | - | not reached |
| portal_built | not reached | 63.0 | - | - | not reached |
| portal_lit | not reached | 63.0-64.0 | - | - | not reached |
| nether_entered | not reached | 66.7 | - | - | not reached |

run failed at: flint_and_steel (line 20): never attempted after chest_3

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (NOT_REACHED)

| Tag | Seconds | Evidence |
|---|---|---|
| extra_items | 2.4 | RunEval excess_materials at t=38.948 s (line 26): stone: gathered 6 but 6 blocks were never consumed (slack 4); 2.4 s of gathering was surplus |

### nether (NOT_REACHED)

No waste found.

### exit_to_end_portal (NOT_REACHED)

No waste found.

### end (NOT_REACHED)

No waste found.

## Timer basis (fairness.timer)

The agent clock is wall clock (portal loading and model latency included). Pro segment times are IGT (total 169.149 s); the pro's RTA is 174.545 s.
Agent total vs pro RTA: not scored (run unfinished).
The pro's RTA-IGT gap is 5.396 s, mostly portal loads that the agent's segments include. No FLAG verdict depends on it.

## RunEval summary

Total 49.357 s, attributed waste (overlaps merged) 2.4 s, efficiency 0.951, milestones 0/5, findings 4. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| self_report_contradiction | high | 49.357 | 6, 8, 12, 14, 18, 20, 24, 28 | line 28: summary claims actions=0, but the log shows 7 (skill_result lines: lines 6, 8, 12, 14, 18, 20, 24) |

## Evidence coverage

Server log: `agent_runs/agent-04/server_events.jsonl`, 5 samples, t=0.477-2.496 s (agent run t=0.0-49.357 s). Agent snapshots checked against a server sample within +-1.5 s: 1; without one: 9 (lines 6, 8, 12, 14, 18, 20, 24, 26, 28).
- server log ends at t=2.496 s, 46.861 s before the agent run ends (t=49.357 s)
- server log ends during the goto attempt (started t=0.558 s, line 5; result t=10.078 s, line 6)
- no server evidence for goto result at t=10.078 s (line 6)
- no server evidence for loot_chest result at t=10.236 s (line 8)
- no server evidence for goto result at t=32.019 s (line 12)
- no server evidence for loot_chest result at t=33.032 s (line 14)
- no server evidence for goto result at t=37.48 s (line 18)
- no server evidence for loot_chest result at t=37.534 s (line 20)
- no server evidence for goto result at t=38.542 s (line 24)
- no server evidence for the inventory snapshot at t=38.948 s (line 26)

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind.
