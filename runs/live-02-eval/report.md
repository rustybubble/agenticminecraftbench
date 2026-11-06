# Efficiency check: `live-02`

Log: `runs/live/live-02/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=151.266 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | 139.758 |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=151.266 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

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
| failed_or_retried_action | 80.796 | RunEval failed_action at t=6.012 s (line 7): line 7: action 'collect_wood' failed (FAILED: not ok); 80.796 s lost |
| failed_or_retried_action | 28.724 | RunEval lost_drop at t=95.193 s (lines 8-10): line 10: 'mine_blocks' reported success but nothing reached the inventory within 5 s / by the next result; 28.724 s wasted |
| failed_or_retried_action | 28.724 | RunEval no_progress at t=95.193 s (lines 8-10): lines 8-10: 'mine_blocks' succeeded but position and inventory are unchanged; 28.724 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=125.724 s (lines 11-13): line 13: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=125.724 s (lines 11-13): lines 11-13: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |
| failed_or_retried_action | 1.504 | RunEval failed_action at t=127.713 s (line 16): line 16: action 'craft' failed (FAILED: no recipe for crafting_table: missing oak_planksx4); 1.504 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=132.859 s (line 22): line 22: action 'craft' failed (FAILED: no recipe for wooden_pickaxe: missing oak_planksx3, stickx2); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=136.519 s (line 28): line 28: action 'craft' failed (FAILED: no recipe for wooden_pickaxe: missing oak_planksx3, stickx2); 0.001 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=140.216 s (line 34): line 34: action 'craft' failed (FAILED: no recipe for wooden_pickaxe: missing oak_planksx3, stickx2); 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=144.863 s (line 40): line 40: action 'craft' failed (FAILED: no recipe for wooden_pickaxe: missing oak_planksx3, stickx2); 0.002 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=149.259 s (line 46): line 46: action 'craft' failed (FAILED: no recipe for wooden_pickaxe: missing oak_planksx3, stickx2); 0.002 s lost |

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

Total 151.266 s, attributed waste (overlaps merged) 111.033 s, efficiency 0.266, milestones 0/5, findings 25. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| self_report_contradiction | high | 151.266 | 51 | line 51: summary claims finalSplit='wood', but the log shows None (last milestone reached in the log) |
| self_report_contradiction | high | 151.266 | 51 | line 51: summary claims splits=1, but the log shows 0 (milestones reached in the log) |
| agent_server_mismatch | high | 0.0 | 1 (server 16) | agent line 1 reports pos (-210.4, 71.0, 225.6) (overworld); server line 16 (t=0.775) has (-180.5, 70.0, 214.5) (overworld), 31.88 blocks apart |
| agent_server_mismatch | high | 86.808 | 7 (server 119) | agent line 7 reports pos (-210.4, 71.0, 225.6) (overworld); server line 119 (t=87.049) has (-213.5, 73.6, 225.5) (overworld), 4.06 blocks apart |
| agent_server_mismatch | high | 123.917 | 10 (server 163) | agent line 10 reports pos (-210.4, 71.0, 225.6) (overworld); server line 163 (t=124.108) has (-215.5, 74.0, 227.7) (overworld), 6.29 blocks apart |
| agent_server_mismatch | high | 125.725 | 13 (server 166) | agent line 13 reports pos (-210.4, 71.0, 225.6) (overworld); server line 166 (t=126.109) has (-215.5, 74.0, 227.7) (overworld), 6.29 blocks apart |
| agent_server_mismatch | high | 129.217 | 16 (server 169) | agent line 16 reports pos (-210.4, 71.0, 225.6) (overworld); server line 169 (t=129.117) has (-211.6, 74.0, 226.8) (overworld), 3.48 blocks apart |

## Evidence coverage

Server log: `runs/live/live-02/server.jsonl`, 151 samples, t=0.775-151.151 s (agent run t=0.0-151.266 s). Agent snapshots checked against a server sample within +-1.5 s: 17; without one: 0.
- server log covers the whole agent run

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind.
