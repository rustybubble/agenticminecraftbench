# Efficiency check: `agent-01`

Log: `agent_runs/agent-01/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=83.267 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | 4.345 |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=83.267 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress before failure

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | 16.108 | 29.0-33.0 | -16.892 to -12.892 | 8 | village chest (iron_pickaxe 1, obsidian 6) |
| chest_2 | 38.105 | 54.0 | -15.895 | 14 | obsidian chest (iron_ingot 6, obsidian 11) |
| chest_3 | 42.654 | 49.0-51.0 | -8.346 to -6.346 | 20 | flint chest (flint 1, obsidian 4) |
| flint_and_steel | 42.654-48.048 | 60.0-61.0 | -12.952 to -11.952 | 30 | first seen in inventory at line 30 (no craft event in the log); crafted after the flint pickup at t=42.654 (line 20) |
| portal_build_attempted | 44.101 | 55.0 | -10.899 | 26 | build_portal skill started |
| portal_built | not reached | 63.0 | - | 27 | build_portal failed: frame incomplete, placed 0 |
| portal_lit | not reached | 63.0-64.0 | - | - | not reached |
| nether_entered | not reached | 66.7 | - | - | not reached |

run failed at: portal_built (line 27): build_portal failed: frame incomplete, placed 0

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (NOT_REACHED)

| Tag | Seconds | Evidence |
|---|---|---|
| failed_or_retried_action | 4.345 | RunEval failed_action at t=43.7 s (line 27): line 27: action 'build_portal' failed (FAILED: frame incomplete); 4.345 s lost |

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

Total 83.267 s, attributed waste (overlaps merged) 4.345 s, efficiency 0.948, milestones 0/5, findings 6. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| inventory_loss_without_effect | high | 44.101 | 20, 25, 27, 30 | lines 25->30: obsidian 21 -> 17 (-4) across failed build_portal (line 27: placed 0, frame incomplete); items consumed, nothing built |
| self_report_contradiction | high | 83.267 | 6, 8, 12, 14, 18, 20, 24, 27, 32 | line 32: summary claims actions=0, but the log shows 8 (skill_result lines: lines 6, 8, 12, 14, 18, 20, 24, 27) |
| self_report_contradiction | high | 83.267 | 27, 32 | line 32: summary claims failures=0, but the log shows 1 (skill_result lines with ok:false: lines 27) |

## Evidence coverage

Server log: `agent_runs/agent-01/server_events.jsonl`, 88 samples, t=0.573-44.322 s (agent run t=0.0-83.267 s). Agent snapshots checked against a server sample within +-1.5 s: 8; without one: 3 (lines 27, 30, 32).
- server log ends at t=44.322 s, 38.945 s before the agent run ends (t=83.267 s)
- server log ends during the build_portal attempt (started t=44.101 s, line 26; result t=48.045 s, line 27)
- no server evidence for build_portal result at t=48.045 s (line 27, FAILED)
- no server evidence for the inventory snapshot at t=48.048 s (line 30)

## Perception (AI-assisted, validation insufficient)

A vision model was used ONLY to say what is visible in footage frames (overlay text cropped out); every finding below is a deterministic rule over those observations, labelled perception-assisted, cost 0 s. Headline verdicts above do not use perception.

Perception file: `runs/perception/agent-01_perception.json`. Model: `gpt-6-astra`. Frames: 48 (48 aligned to run time, t=48.56-142.56 s; 29 distinct frame images). 30 of these frames fall after the agent run log ends (t=83.267 s) and are not used by any perception finding.

No field has at least 10 non-circular ground-truth labels, so every perception result below is a low-confidence observation, not evidence.

### Validation against ground truth

| Field | n | Correct | Accuracy | 95% CI | Status |
|---|---|---|---|---|---|
| chest_visible | 2 | 2 | 1.0 | 0.342-1.0 | insufficient (n < 10) |
| village_visible | 0 | 0 | - |  | no labels |
| obsidian_frame | 2 | 2 | 1.0 | 0.342-1.0 | insufficient (n < 10) |
| portal_lit | 0 | 0 | - |  | no labels |
| player_in_water | 0 | 0 | - |  | no labels |

Consistent with the agent-log claim (circular, not ground truth, not used for gating): portal_lit 48/48.
Consistent with the agent-log claim (circular, not ground truth, not used for gating): obsidian_frame 46/46.
Unvalidated (no ground truth, findings using them say so): portal_lit, village_visible, lava_visible, water_visible, player_visible, player_in_water, player_activity, confidence.
Note: insufficient ground truth (n < 10) for: chest_visible (n=2), obsidian_frame (n=2); these accuracies must not gate findings
Note: log_consistency rows compare the model with the agent's own claim; they are not ground truth and are not in per_field

### Perception-assisted findings

| Code | Category | Severity | t s | Lines | Finding |
|---|---|---|---|---|---|
| portal_outcome_check | claim | low | 48.045-68.045 | 27 | [perception-assisted] low-confidence observation: agent log line 27: build_portal FAILED (placed 0), error 'frame incomplete' (unvalidated: no ground truth for portal_lit); not used as evidence |

### With vs without perception

- Without: verdicts, waste and claims come from the agent log and the server log only.
- With: 0 perception-assisted finding(s) added, plus 1 low-confidence observation(s) not used as evidence.
- Coverage: 18 frame(s) fall after the server log's last sample (t=44.322 s).
- Headline verdicts and segment ratios: unchanged.

## This run

From `agent_runs/agent-01/RUN_NOTES.md` (operator notes, not checked against the log except where another section says so).

- **Run:** agent-01
- **Agent:** live agent
- **Planner model:** `deepseek-flash` (effort low) · Action classifier: `nvidia/nemotron-3.5-bolt-e4b` (free tier)
- **Difficulty:** easy
- **First attempt:** No for the harness, yes for this world: the world was regenerated from the seed immediately before the take, and the player was cleared (`/clear @s`) at spawn.
- **Interventions:** none (no restarts, no code edits, no console commands, no pauses). The world reset, spawn clear and RCON start happened before the take.
- **Outcome:** looted all three supply chests (obsidian 21, iron pickaxe, flint, iron, beds not taken), crafted `flint_and_steel`, then attempted a portal build near the ruined frame at x=−281. The frame build placed 0 verified blocks (4 obsidian left the inventory, verification still read air), so the portal was never lit and the bot never entered the Nether. No deaths. 0 hostile encounters.

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted. **does not apply to this run: the rules say the agent played on Peaceful, but agent-01 was on Easy (RUN_NOTES).**
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt. **does not apply to this run: the agent half: agent-01 is a live run, not the author's best published run; first attempt: No for the harness, yes for this world: the world was regenerated from the seed immediately before the take, and the player was cleared (`/clear @s`) at spawn.**
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low). **does not apply to this run: agent-01 is a live run with a continuous timestamped event log, not the published montage; its milestones are exact log times, not brackets.**
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone. **does not apply to this run: the note describes the published rmalde/minecraft-agent config; agent-01 is a live agent whose route is fixed in its own route_start event (the point that the route is supplied, not chosen by the LLM, still holds).**
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind. **does not apply to this run: agent-01 never reached the End, so dragon RNG plays no part.**
