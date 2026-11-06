# Efficiency check: `demo-02`

Log: `runs/live/demo-02/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=71.226 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | 10.907 |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=71.226 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress before failure

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | 13.639 | 29.0-33.0 | -19.361 to -15.361 | 8 | village chest (iron_pickaxe 1, obsidian 6) |
| chest_2 | 35.9 | 54.0 | -18.1 | 14 | obsidian chest (iron_ingot 6, obsidian 11) |
| chest_3 | 40.441 | 49.0-51.0 | -10.559 to -8.559 | 20 | flint chest (flint 1, obsidian 4) |
| flint_and_steel | 40.441-51.206 | 60.0-61.0 | -9.794 to -8.794 | 30 | first seen in inventory at line 30 (no craft event in the log); crafted after the flint pickup at t=40.441 (line 20) |
| portal_build_attempted | 41.895 | 55.0 | -13.105 | 26 | build_portal skill started |
| portal_built | not reached | 63.0 | - | 27 | build_portal failed: frame incomplete, placed 0 |
| portal_lit | not reached | 63.0-64.0 | - | - | not reached |
| nether_entered | not reached | 66.7 | - | - | not reached |

run failed at: portal_built (line 27): build_portal failed: frame incomplete, placed 0

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (NOT_REACHED)

| Tag | Seconds | Evidence |
|---|---|---|
| failed_or_retried_action | 9.707 | RunEval failed_action at t=41.495 s (line 27): line 27: action 'build_portal' failed (FAILED: frame incomplete); 9.707 s lost |
| extra_items | 1.2 | RunEval excess_materials at t=51.206 s (line 30): stone: gathered 5 but 5 blocks were never consumed (slack 4); 1.2 s of gathering was surplus |

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

Total 71.226 s, attributed waste (overlaps merged) 10.907 s, efficiency 0.847, milestones 0/5, findings 7. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| inventory_loss_without_effect | high | 41.895 | 20, 25, 27, 30 | lines 25->30: obsidian 21 -> 19 (-2) across failed build_portal (line 27: placed 0, frame incomplete); items consumed, nothing built |
| self_report_contradiction | high | 71.226 | 6, 8, 12, 14, 18, 20, 24, 27, 32 | line 32: summary claims actions=0, but the log shows 8 (skill_result lines: lines 6, 8, 12, 14, 18, 20, 24, 27) |
| self_report_contradiction | high | 71.226 | 27, 32 | line 32: summary claims failures=0, but the log shows 1 (skill_result lines with ok:false: lines 27) |
| agent_server_mismatch | high | 51.202 | 27 (server 72) | agent line 27 reports pos (-285.5, 67.0, 260.5) (overworld); server line 72 (t=51.097) has (-279.0, 64.9, 262.5) (overworld), 7.14 blocks apart |

## Evidence coverage

Server log: `runs/live/demo-02/server.jsonl`, 71 samples, t=0.723-71.149 s (agent run t=0.0-71.226 s). Agent snapshots checked against a server sample within +-1.5 s: 11; without one: 0.
- server log covers the whole agent run

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind.
