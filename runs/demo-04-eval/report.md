# Efficiency check: `demo-04`

Log: `runs/live/demo-04/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=62.191 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | 0.182 |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=62.191 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress before failure

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | not reached | no pro time for this step | - | - | not reached |
| chest_2 | not reached | no pro time for this step | - | - | not reached |
| chest_3 | not reached | no pro time for this step | - | - | not reached |
| flint_and_steel | not reached | 60.0-61.0 | - | - | not reached |
| portal_build_attempted | 62.131 | 55.0 | +7.131 | 7 | build_portal skill started |
| portal_built | not reached | 63.0 | - | 8 | build_portal failed: no clear 4x5 site near the bot |
| portal_lit | not reached | 63.0-64.0 | - | - | not reached |
| nether_entered | not reached | 66.7 | - | - | not reached |

run failed at: portal_built (line 8): build_portal failed: no clear 4x5 site near the bot

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (NOT_REACHED)

| Tag | Seconds | Evidence |
|---|---|---|
| failed_or_retried_action | 0.121 | RunEval no_progress at t=62.009 s (lines 4-5): lines 4-5: 'travel_legs' succeeded but position and inventory are unchanged; 0.121 s lost |
| failed_or_retried_action | 0.061 | RunEval failed_action at t=62.13 s (line 8): line 8: action 'build_portal' failed (FAILED: no clear 4x5 site near the bot); 0.061 s lost |

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

Total 62.191 s, attributed waste (overlaps merged) 0.182 s, efficiency 0.997, milestones 0/5, findings 3. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| agent_server_mismatch | high | 62.13 | 5 (server 85) | agent line 5 reports pos (-35.1, 77.0, 32.8) (the_nether); server line 85 (t=61.996) has (-138.5, 41.0, 98.4) (the_nether), 127.67 blocks apart |
| agent_server_mismatch | high | 62.191 | 8 (server 85) | agent line 8 reports pos (-35.1, 77.0, 32.8) (the_nether); server line 85 (t=61.996) has (-138.5, 41.0, 98.4) (the_nether), 127.67 blocks apart |

## Evidence coverage

Server log: `runs/live/demo-04/server.jsonl`, 110 samples, t=0.802-112.105 s (agent run t=0.0-62.191 s). Agent snapshots checked against a server sample within +-1.5 s: 3; without one: 0.
- server log covers the whole agent run

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind.
