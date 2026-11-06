# Efficiency check: `demo-03`

Log: `runs/live/demo-03/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=79.853 s); end segment and total not scored); total not scored**

Run median ratio: **0.894**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | 59.641 | 66.683 | 0.894 | **OK** | 0.0 (raw 0.001) |
| nether | - | 40.783 | - | **NOT_REACHED** | 0.039 |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=79.853 s); end segment and total not scored; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress by step

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | 14.551 | 29.0-33.0 | -18.449 to -14.449 | 8 | village chest (iron_pickaxe 1, obsidian 6) |
| chest_2 | 36.705 | 54.0 | -17.295 | 14 | obsidian chest (iron_ingot 6, obsidian 11) |
| chest_3 | 41.213 | 49.0-51.0 | -9.787 to -7.787 | 20 | flint chest (flint 1, obsidian 4) |
| flint_and_steel | 41.213-59.681 | 60.0-61.0 | -1.319 to -0.319 | 39 | first seen in inventory at line 39 (no craft event in the log); crafted after the flint pickup at t=41.213 (line 20) |
| portal_build_attempted | 42.625 | 55.0 | -12.375 | 26 | build_portal skill started |
| portal_built | 59.64 | 63.0 | -3.36 | 27 | build_portal ok |
| portal_lit | 59.641 | 63.0-64.0 | -4.359 to -3.359 | 28 | implied by nether entry (no lit event) |
| nether_entered | 59.641 | 66.7 | -7.059 | 28 | nether_entered |

run reached every step in this table.

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (OK)

| Tag | Seconds | Evidence |
|---|---|---|
| failed_or_retried_action | 0.001 | RunEval failed_action at t=59.64 s (line 31): line 31: action 'travel_legs' failed (FAILED: not ok); 0.001 s lost |

### nether (NOT_REACHED)

| Tag | Seconds | Evidence |
|---|---|---|
| failed_or_retried_action | 0.039 | RunEval failed_action at t=59.641 s (line 36): line 36: action 'build_portal' failed (FAILED: no clear 4x5 site near the bot); 0.039 s lost |

### exit_to_end_portal (NOT_REACHED)

No waste found.

### end (NOT_REACHED)

No waste found.

## Timer basis (fairness.timer)

The agent clock is wall clock (portal loading and model latency included). Pro segment times are IGT (total 169.149 s); the pro's RTA is 174.545 s.
Agent total vs pro RTA: not scored (run unfinished).
The pro's RTA-IGT gap is 5.396 s, mostly portal loads that the agent's segments include. No FLAG verdict depends on it.

## RunEval summary

Total 79.853 s, attributed waste (overlaps merged) 0.04 s, efficiency 1.0, milestones 1/5, findings 8. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| self_report_contradiction | high | 79.853 | 6, 8, 12, 14, 18, 20, 24, 27, 31, 36, 41 | line 41: summary claims actions=0, but the log shows 10 (skill_result lines: lines 6, 8, 12, 14, 18, 20, 24, 27, 31, 36) |
| self_report_contradiction | high | 79.853 | 28, 41 | line 41: summary claims finalSplit=None, but the log shows 'nether_entered' (last milestone reached in the log: lines 28) |
| self_report_contradiction | high | 79.853 | 28, 41 | line 41: summary claims splits=0, but the log shows 1 (milestones reached in the log: lines 28) |
| self_report_contradiction | high | 79.853 | 31, 36, 41 | line 41: summary claims failures=0, but the log shows 2 (skill_result lines with ok:false: lines 31, 36) |
| agent_server_mismatch | high | 59.64 | 27 (server 82) | agent line 27 reports pos (-285.5, 67.0, 260.5) (overworld); server line 82 (t=59.201) has (-280.5, 66.0, 262.5) (overworld), 5.48 blocks apart |
| agent_server_mismatch | high | 59.641 | 31 (server 82) | agent line 31 reports pos (-285.5, 67.0, 260.5) (the_nether); server line 82 (t=59.201) has (-280.5, 66.0, 262.5) (overworld), 5.48 blocks apart |
| agent_server_mismatch | high | 59.68 | 36 (server 82) | agent line 36 reports pos (-285.5, 67.0, 260.5) (the_nether); server line 82 (t=59.201) has (-280.5, 66.0, 262.5) (overworld), 5.48 blocks apart |

## Evidence coverage

Server log: `runs/live/demo-03/server.jsonl`, 189 samples, t=0.705-217.55 s (agent run t=0.0-79.853 s). Agent snapshots checked against a server sample within +-1.5 s: 13; without one: 0.
- server log covers the whole agent run

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind.
