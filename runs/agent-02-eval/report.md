# Efficiency check: `agent-02`

Log: `agent_runs/agent-02/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=249.039 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | 34.123 |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=249.039 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress before failure

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | 185.94 | 29.0-33.0 | 152.94 to 156.94 | 40 | village chest (iron_pickaxe 1, obsidian 6) |
| chest_2 | 208.121 | 54.0 | +154.121 | 46 | obsidian chest (iron_ingot 6, obsidian 11) |
| chest_3 | 212.637 | 49.0-51.0 | 161.637 to 163.637 | 52 | flint chest (flint 1, obsidian 4) |
| flint_and_steel | 212.637-218.606 | 60.0-61.0 | 157.606 to 158.606 | 62 | first seen in inventory at line 62 (no craft event in the log); crafted after the flint pickup at t=212.637 (line 52) |
| portal_build_attempted | 49.515 | 55.0 | -5.485 | 26 | build_portal skill started |
| portal_built | not reached | 63.0 | - | 27 | build_portal failed: need flint + iron_ingot for flint_and_steel |
| portal_lit | not reached | 63.0-64.0 | - | - | not reached |
| nether_entered | not reached | 66.7 | - | - | not reached |

run failed at: portal_built (line 27): build_portal failed: need flint + iron_ingot for flint_and_steel

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (NOT_REACHED)

| Tag | Seconds | Evidence |
|---|---|---|
| longer_path | 27.79 | path 200.4 blocks vs straight 2.3 blocks (87.72x) |
| failed_or_retried_action | 0.305 | RunEval failed_action at t=27.249 s (line 8): line 8: action 'loot_chest' failed (FAILED: not ok); 0.305 s lost |
| failed_or_retried_action | 0.657 | RunEval failed_action at t=44.306 s (line 14): line 14: action 'loot_chest' failed (FAILED: not ok); 0.657 s lost |
| failed_or_retried_action | 0.051 | RunEval failed_action at t=48.051 s (line 20): line 20: action 'loot_chest' failed (FAILED: not ok); 0.051 s lost |
| failed_or_retried_action | 0.401 | RunEval failed_action at t=49.114 s (line 27): line 27: action 'build_portal' failed (FAILED: need flint + iron_ingot for flint_and_steel); 0.401 s lost |
| failed_or_retried_action | 4.919 | RunEval failed_action at t=213.683 s (line 59): line 59: action 'build_portal' failed (FAILED: frame incomplete); 4.919 s lost |

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

Total 249.039 s, attributed waste (overlaps merged) 6.333 s, efficiency 0.975, milestones 0/5, findings 10. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| inventory_loss_without_effect | high | 214.084 | 52, 57, 59, 62 | lines 57->62: obsidian 21 -> 17 (-4) across failed build_portal (line 59: placed 0, frame incomplete); items consumed, nothing built |
| self_report_contradiction | high | 249.039 | 6, 8, 12, 14, 18, 20, 24, 27, 38, 40, 44, 46, 50, 52, 56, 59, 64 | line 64: summary claims actions=0, but the log shows 16 (skill_result lines: lines 6, 8, 12, 14, 18, 20, 24, 27, 38, 40, 44, 46, 50, 52, 56, 59) |
| self_report_contradiction | high | 249.039 | 8, 14, 20, 27, 59, 64 | line 64: summary claims failures=0, but the log shows 5 (skill_result lines with ok:false: lines 8, 14, 20, 27, 59) |

## Evidence coverage

Server log: `agent_runs/agent-02/server_events.jsonl`, 60 samples, t=0.526-30.177 s (agent run t=0.0-249.039 s). Agent snapshots checked against a server sample within +-1.5 s: 3; without one: 19 (lines 12, 14, 18, 20, 24, 27, 30, 32, 33, 38, 40, 44, 46, 50, 52, 56, 59, 62, 64).
- server log ends at t=30.177 s, 218.862 s before the agent run ends (t=249.039 s)
- server log ends during the goto attempt (started t=27.955 s, line 11; result t=44.306 s, line 12)
- no server evidence for goto result at t=44.306 s (line 12)
- no server evidence for loot_chest result at t=44.963 s (line 14, FAILED)
- no server evidence for goto result at t=48.051 s (line 18)
- no server evidence for loot_chest result at t=48.102 s (line 20, FAILED)
- no server evidence for goto result at t=49.114 s (line 24)
- no server evidence for build_portal result at t=49.515 s (line 27, FAILED)
- no server evidence for goto result at t=185.781 s (line 38)
- no server evidence for loot_chest result at t=185.94 s (line 40)
- no server evidence for goto result at t=207.089 s (line 44)
- no server evidence for loot_chest result at t=208.121 s (line 46)
- no server evidence for goto result at t=212.583 s (line 50)
- no server evidence for loot_chest result at t=212.637 s (line 52)
- no server evidence for goto result at t=213.683 s (line 56)
- no server evidence for build_portal result at t=218.602 s (line 59, FAILED)
- no server evidence for the inventory snapshot at t=49.519 s (line 30)
- no server evidence for the inventory snapshot at t=218.606 s (line 62)

## This run

From `agent_runs/agent-02/RUN_NOTES.md` (operator notes, not checked against the log except where another section says so).

- **Agent:** status

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind. **does not apply to this run: this run never reached the End, so dragon RNG plays no part.**
