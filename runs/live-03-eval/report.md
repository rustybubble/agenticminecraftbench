# Efficiency check: `live-03`

Log: `runs/live/live-03/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=231.565 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | 266.75 |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=231.565 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress by step

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | not reached | no pro time for this step | - | - | not derivable from this log |
| chest_2 | not reached | no pro time for this step | - | - | not derivable from this log |
| chest_3 | not reached | no pro time for this step | - | - | not derivable from this log |
| flint_and_steel | not reached | 60.0-61.0 | - | - | not derivable from this log |
| portal_build_attempted | not reached | 55.0 | - | - | not derivable from this log |
| portal_built | not reached | 63.0 | - | - | not derivable from this log |
| portal_lit | not reached | 63.0-64.0 | - | - | not derivable from this log |
| nether_entered | not reached | 66.7 | - | - | not derivable from this log |

run reached every step in this table.

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (NOT_REACHED)

| Tag | Seconds | Evidence |
|---|---|---|
| failed_or_retried_action | 35.565 | RunEval lost_drop at t=3.72 s (lines 4-7): line 7: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 35.565 s wasted |
| failed_or_retried_action | 35.565 | RunEval no_progress at t=3.72 s (lines 4-7): lines 4-7: 'collect_wood' succeeded but position and inventory are unchanged; 35.565 s lost |
| failed_or_retried_action | 0.011 | RunEval failed_action at t=46.696 s (line 10): line 10: action 'craft' failed (FAILED: not ok); 0.011 s lost |
| failed_or_retried_action | 1.716 | RunEval no_progress at t=49.185 s (lines 11-13): lines 11-13: 'ensure_axe' succeeded but position and inventory are unchanged; 1.716 s lost |
| failed_or_retried_action | 0.004 | RunEval no_progress at t=52.596 s (lines 14-16): lines 14-16: 'ensure_pickaxe' succeeded but position and inventory are unchanged; 0.004 s lost |
| failed_or_retried_action | 36.942 | RunEval lost_drop at t=59.274 s (lines 18-20): line 20: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 36.942 s wasted |
| failed_or_retried_action | 36.942 | RunEval no_progress at t=59.274 s (lines 18-20): lines 18-20: 'collect_wood' succeeded but position and inventory are unchanged; 36.942 s lost |
| failed_or_retried_action | 0.002 | RunEval no_progress at t=101.316 s (lines 21-23): lines 21-23: 'craft' succeeded but position and inventory are unchanged; 0.002 s lost |
| failed_or_retried_action | 120.003 | RunEval failed_action at t=111.409 s (line 30): line 30: action 'mine_blocks' failed (FAILED: not ok); 120.003 s lost |

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

Total 231.565 s, attributed waste (overlaps merged) 194.243 s, efficiency 0.161, milestones 0/5, findings 12. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| self_report_contradiction | high | 231.565 | 32 | line 32: summary claims finalSplit='stone', but the log shows None (last milestone reached in the log) |
| self_report_contradiction | high | 231.565 | 32 | line 32: summary claims splits=2, but the log shows 0 (milestones reached in the log) |
| agent_server_mismatch | high | 0.0 | 1 (server 18) | agent line 1 reports pos (-211.4, 73.0, 227.5) (overworld); server line 18 (t=0.79) has (-180.5, 70.0, 214.5) (overworld), 33.69 blocks apart |
| agent_server_mismatch | high | 39.285 | 7 (server 63) | agent line 7 reports pos (-211.4, 73.0, 227.5) (overworld); server line 63 (t=38.842) has (-216.5, 73.0, 228.5) (overworld), 5.19 blocks apart |
| agent_server_mismatch | high | 46.707 | 10 (server 73) | agent line 10 reports pos (-211.4, 73.0, 227.5) (overworld); server line 73 (t=46.856) has (-216.5, 74.0, 228.5) (overworld), 5.28 blocks apart |
| agent_server_mismatch | high | 96.216 | 20 (server 133) | agent line 20 reports pos (-211.4, 73.0, 227.5) (overworld); server line 133 (t=95.927) has (-222.5, 73.0, 235.5) (overworld), 13.65 blocks apart |
| agent_server_mismatch | high | 101.318 | 23 (server 139) | agent line 23 reports pos (-211.4, 73.0, 227.5) (overworld); server line 139 (t=100.935) has (-222.5, 73.0, 235.5) (overworld), 13.65 blocks apart |
| agent_server_mismatch | high | 103.445 | 26 (server 142) | agent line 26 reports pos (-211.4, 73.0, 227.5) (overworld); server line 142 (t=103.941) has (-222.5, 73.0, 235.5) (overworld), 13.65 blocks apart |
| agent_server_mismatch | high | 231.412 | 30 (server 295) | agent line 30 reports pos (-211.4, 73.0, 227.5) (overworld); server line 295 (t=231.47) has (-215.6, 64.0, 238.5) (overworld), 14.81 blocks apart |

## Evidence coverage

Server log: `runs/live/live-03/server.jsonl`, 231 samples, t=0.79-231.47 s (agent run t=0.0-231.565 s). Agent snapshots checked against a server sample within +-1.5 s: 10; without one: 0.
- server log covers the whole agent run

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind.
