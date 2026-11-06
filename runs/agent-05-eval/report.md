# Efficiency check: `agent-05`

Log: `agent_runs/agent-05/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=51.64 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | - |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=51.64 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

Verdict rule (baseline/rules.json): run_median = median over segments of (ratio_low + ratio_high) / 2. FLAG if ratio_low > flag_k_times_median * max(run_median, 1) AND agent_s_low - pro_s >= flag_min_excess_s. Otherwise SLOW if ratio_low > ok_max_ratio, else OK. Always report the raw ratios.
Thresholds: ok_max_ratio=1.25, flag_k_times_median=2.0, flag_min_excess_s=5.0.

## Progress before failure

Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects beds on the way, so a negative delta is not the same work done faster. Report only: no verdict uses this table.

| Step | Agent t s | Pro t s | Delta s | Line | Note |
|---|---|---|---|---|---|
| chest_1 | 15.747 | 29.0-33.0 | -17.253 to -13.253 | 8 | village chest (iron_pickaxe 1, obsidian 6) |
| chest_2 | 37.632 | 54.0 | -16.368 | 14 | obsidian chest (iron_ingot 6, obsidian 11) |
| chest_3 | 42.173 | 49.0-51.0 | -8.827 to -6.827 | 20 | flint chest (flint 1, obsidian 4) |
| flint_and_steel | not reached | 60.0-61.0 | - | - | not reached |
| portal_build_attempted | not reached | 55.0 | - | - | not reached |
| portal_built | not reached | 63.0 | - | - | not reached |
| portal_lit | not reached | 63.0-64.0 | - | - | not reached |
| nether_entered | not reached | 66.7 | - | - | not reached |

run failed at: flint_and_steel (line 20): never attempted after chest_3

## Waste by segment

Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep their detector code and log lines in the evidence. Entries can overlap: see runeval.json `score.attributed_waste_s` for the overlap-merged total.

### spawn_to_nether (NOT_REACHED)

No waste found.

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

Total 51.64 s, attributed waste (overlaps merged) 0.0 s, efficiency 1.0, milestones 0/5, findings 3. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| self_report_contradiction | high | 51.64 | 6, 8, 12, 14, 18, 20, 24, 28 | line 28: summary claims actions=0, but the log shows 7 (skill_result lines: lines 6, 8, 12, 14, 18, 20, 24) |

## Evidence coverage

Server log: `agent_runs/agent-05/server_events.jsonl`, 0 samples, t=--- s (agent run t=0.0-51.64 s). Agent snapshots checked against a server sample within +-1.5 s: 0; without one: 10 (lines 1, 6, 8, 12, 14, 18, 20, 24, 26, 28).
- **no usable server samples** (log empty, unparsed format, or the player was never seen online): there is NO server-side evidence for this run; every finding rests on the agent's own log

## Perception (AI-assisted, validated)

A vision model was used ONLY to say what is visible in footage frames (overlay text cropped out); every finding below is a deterministic rule over those observations, labelled perception-assisted, cost 0 s. Headline verdicts above do not use perception.

Perception file: `runs/perception/agent-05_perception.json`. Model: `claude-sonnet-5-5`. Frames: 57 (57 aligned to run time, t=32.039-43.684 s; 34 distinct frame images).

### Validation against ground truth

| Field | n | Correct | Accuracy | 95% CI | Status |
|---|---|---|---|---|---|
| chest_visible | 32 | 0 | 0.0 | 0.0-0.107 | validated |
| village_visible | 0 | 0 | - |  | no labels |
| obsidian_frame | 32 | 32 | 1.0 | 0.893-1.0 | validated |
| portal_lit | 0 | 0 | - |  | no labels |
| player_in_water | 0 | 0 | - |  | no labels |

Consistent with the agent-log claim (circular, not ground truth, not used for gating): obsidian_frame 25/25.
Consistent with the agent-log claim (circular, not ground truth, not used for gating): portal_lit 57/57.
Unvalidated (no ground truth, findings using them say so): portal_lit, village_visible, lava_visible, water_visible, player_visible, player_in_water, player_activity, confidence.
Note: log_consistency rows compare the model with the agent's own claim; they are not ground truth and are not in per_field

### Perception-assisted findings

| Code | Category | Severity | t s | Lines | Finding |
|---|---|---|---|---|---|
| visible_feature_ignored | decision | low | 32.039-43.684 |  | [perception-assisted] low-confidence observation: lava visible, but the agent log never mentions lava or a bucket (t=32.039-43.684 s) (unvalidated: no ground truth for lava_visible); not used as evidence |
| visible_feature_ignored | decision | low | 32.039-43.684 |  | [perception-assisted] obsidian frame (ruined portal) visible, but the agent never started a portal skill: first seen t=32.039-43.684 s in 54 confident frame(s) (obsidian_frame accuracy 1.0 (n=32)); report only, seeing a feature on camera does not mean the agent perceived it |

### With vs without perception

- Without: verdicts, waste and claims come from the agent log and the server log only.
- With: 1 perception-assisted finding(s) added (visible_feature_ignored), plus 1 low-confidence observation(s) not used as evidence.
- Headline verdicts and segment ratios: unchanged.

## This run

From `agent_runs/agent-05/RUN_NOTES.md` (operator notes, not checked against the log except where another section says so).

- **Run:** agent-05 (the previous takes in this round: agent-02, agent-03, agent-04)
- **Agent:** clean route take (third attempts series)
- **Interventions:** none during the run. World regenerated from the seed immediately before it; player cleared at spawn.
- **Outcome:** looted all three supply chests (obsidian 21, iron pickaxe, flint, iron 6, beds not taken), crafted `flint_and_steel`. The portal build step was not run in this take (it still fails, see below). No deaths, no hostiles engaged.

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind. **does not apply to this run: agent-05 (the previous takes in this round: agent-02, agent-03, agent-04) never reached the End, so dragon RNG plays no part.**
