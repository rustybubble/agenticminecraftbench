# Efficiency check: `agent-06`

Log: `agent_runs/agent-06/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=383.041 s, after a death); end segment and total not scored); total not scored**

Run median ratio: **0.873**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | 58.221 | 66.683 | 0.873 | **OK** | - |
| nether | - | 40.783 | - | **NOT_REACHED** | 324.821 |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=383.041 s, after a death); end segment and total not scored; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress by step

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | 12.969 | 29.0-33.0 | -20.031 to -16.031 | 8 | village chest (iron_pickaxe 1, obsidian 6) |
| chest_2 | 35.315 | 54.0 | -18.685 | 14 | obsidian chest (iron_ingot 6, obsidian 11) |
| chest_3 | 39.864 | 49.0-51.0 | -11.136 to -9.136 | 20 | flint chest (flint 1, obsidian 4) |
| flint_and_steel | 39.864-357.195 | 60.0-61.0 | 296.195 to 297.195 | 37 | first seen in inventory at line 37 (no craft event in the log); crafted after the flint pickup at t=39.864 (line 20) |
| portal_build_attempted | 41.312 | 55.0 | -13.688 | 26 | build_portal skill started |
| portal_built | 58.216 | 63.0 | -4.784 | 27 | build_portal ok |
| portal_lit | 58.221 | 63.0-64.0 | -5.779 to -4.779 | 28 | implied by nether entry (no lit event) |
| nether_entered | 58.221 | 66.7 | -8.479 | 28 | nether_entered |

run reached every step in this table.

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (OK)

No waste found.

### nether (NOT_REACHED)

| Tag | Seconds | Evidence |
|---|---|---|
| failed_or_retried_action | 240.0 | RunEval failed_action at t=58.216 s (line 31): line 31: action 'goto' failed (FAILED: not ok); 240.0 s lost |
| failed_or_retried_action | 58.975 | RunEval failed_action at t=298.216 s (line 34): line 34: action 'build_portal' failed (FAILED: frame incomplete); 58.975 s lost |
| idle_wait | 22.418 | RunEval idle at t=357.195 s (lines 37-39): lines 37-39: no movement or inventory change for 22.418 s at (-285.5, 67.0, 260.5) (22.418 s excluding API waits) |
| unnecessary_risk | 3.428 | RunEval death at t=379.613 s (line 39): line 39: death at (-127.25199223336416, 28.130302127825992, 105.35856444201643) in the_nether; never returned to the death spot (default cost, capped at run end); 3.428 s |

### exit_to_end_portal (NOT_REACHED)

No waste found.

### end (NOT_REACHED)

No waste found.

## Timer basis (fairness.timer)

The agent clock is wall clock (portal loading and model latency included). Pro segment times are IGT (total 169.149 s); the pro's RTA is 174.545 s.
Agent total vs pro RTA: not scored (run unfinished).
The pro's RTA-IGT gap is 5.396 s, mostly portal loads that the agent's segments include. No FLAG verdict depends on it.

## RunEval summary

Total 383.041 s, attributed waste (overlaps merged) 324.821 s, efficiency 0.152, milestones 1/5, findings 10. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| self_report_contradiction | high | 383.041 | 6, 8, 12, 14, 18, 20, 24, 27, 31, 34, 40 | line 40: summary claims actions=0, but the log shows 10 (skill_result lines: lines 6, 8, 12, 14, 18, 20, 24, 27, 31, 34) |
| self_report_contradiction | high | 383.041 | 28, 40 | line 40: summary claims finalSplit=None, but the log shows 'nether_entered' (last milestone reached in the log: lines 28) |
| self_report_contradiction | high | 383.041 | 28, 40 | line 40: summary claims splits=0, but the log shows 1 (milestones reached in the log: lines 28) |
| self_report_contradiction | high | 383.041 | 31, 34, 40 | line 40: summary claims failures=0, but the log shows 2 (skill_result lines with ok:false: lines 31, 34) |

## Evidence coverage

Server log: `agent_runs/agent-06/server_events.jsonl`, 0 samples, t=--- s (agent run t=0.0-383.041 s). Agent snapshots checked against a server sample within +-1.5 s: 0; without one: 13 (lines 1, 6, 8, 12, 14, 18, 20, 24, 27, 31, 34, 37, 40).
- **no usable server samples** (log empty, unparsed format, or the player was never seen online): there is NO server-side evidence for this run; every finding rests on the agent's own log

## This run

From `agent_runs/agent-06/RUN_NOTES.md` (operator notes, not checked against the log except where another section says so).

- **Agent:** full route attempt

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind. **does not apply to this run: this run never reached the End, so dragon RNG plays no part.**
