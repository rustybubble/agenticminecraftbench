# Efficiency check: `foot-01`

Log: `runs/live/foot-01/events.jsonl`. Baseline: `baseline/pro_2m49_segments.json`. Deterministic (no LLM): every number comes from timeline.json, efficiency.json and runeval.json in this folder.

**WARNING: M_finish: not reached (unfinished: no finish event (log ends at t=241.439 s); end segment and total not scored); total not scored**

Run median ratio: **-**

| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |
|---|---|---|---|---|---|
| spawn_to_nether | - | 66.683 | - | **NOT_REACHED** | 146.154 |
| nether | - | 40.783 | - | **NOT_REACHED** | - |
| exit_to_end_portal | - | 2.45 | - | **NOT_REACHED** | - |
| end | - | 59.233 | - | **NOT_REACHED** | - |
| **total** | - | 169.149 | - | | |

Milestone notes: M_end_in: not reached in the log; M_finish: unfinished: no finish event (log ends at t=241.439 s); end segment and total not scored; M_portal_in: not reached in the log; M_portal_out: not reached in the log

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
| failed_or_retried_action | 28.591 | RunEval lost_drop at t=5.069 s (lines 5-7): line 7: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 28.591 s wasted |
| failed_or_retried_action | 28.591 | RunEval no_progress at t=5.069 s (lines 5-7): lines 5-7: 'collect_wood' succeeded but position and inventory are unchanged; 28.591 s lost |
| failed_or_retried_action | 0.012 | RunEval failed_action at t=37.113 s (line 10): line 10: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.012 s lost |
| failed_or_retried_action | 15.466 | RunEval action_loop at t=39.266 s (lines 13-25): lines 13-25: 'collect_wood' repeated 5x in a row, 5 failed/no-progress; 15.466 s |
| failed_or_retried_action | 15.465 | RunEval lost_drop at t=39.266 s (lines 11-13): line 13: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 15.465 s wasted |
| failed_or_retried_action | 15.465 | RunEval no_progress at t=39.266 s (lines 11-13): lines 11-13: 'collect_wood' succeeded but position and inventory are unchanged; 15.465 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=62.798 s (lines 23-25): line 25: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=62.798 s (lines 23-25): lines 23-25: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |
| failed_or_retried_action | 0.005 | RunEval no_progress at t=67.74 s (lines 26-28): lines 26-28: 'craft' succeeded but position and inventory are unchanged; 0.005 s lost |
| failed_or_retried_action | 21.222 | RunEval lost_drop at t=71.924 s (lines 32-34): line 34: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 21.222 s wasted |
| failed_or_retried_action | 21.222 | RunEval no_progress at t=71.924 s (lines 32-34): lines 32-34: 'collect_wood' succeeded but position and inventory are unchanged; 21.222 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=97.235 s (line 37): line 37: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=101.359 s (line 43): line 43: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=105.155 s (line 49): line 49: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=108.976 s (line 55): line 55: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.003 | RunEval lost_drop at t=111.263 s (lines 56-58): line 58: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.003 s wasted |
| failed_or_retried_action | 0.003 | RunEval no_progress at t=111.263 s (lines 56-58): lines 56-58: 'collect_wood' succeeded but position and inventory are unchanged; 0.003 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=112.983 s (line 61): line 61: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=115.193 s (lines 62-64): line 64: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=115.193 s (lines 62-64): lines 62-64: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=116.92 s (line 67): line 67: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=120.561 s (line 73): line 73: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=125.711 s (line 79): line 79: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.003 | RunEval failed_action at t=129.473 s (line 85): line 85: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.003 s lost |
| failed_or_retried_action | 0.004 | RunEval lost_drop at t=131.618 s (lines 86-88): line 88: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.004 s wasted |
| failed_or_retried_action | 0.004 | RunEval no_progress at t=131.618 s (lines 86-88): lines 86-88: 'collect_wood' succeeded but position and inventory are unchanged; 0.004 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=133.437 s (line 91): line 91: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.004 | RunEval failed_action at t=137.136 s (line 97): line 97: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.004 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=138.939 s (lines 98-100): line 100: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=138.939 s (lines 98-100): lines 98-100: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=140.786 s (line 103): line 103: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=144.686 s (line 109): line 109: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.004 | RunEval failed_action at t=148.841 s (line 115): line 115: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.004 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=154.706 s (line 121): line 121: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=158.681 s (line 127): line 127: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=162.359 s (line 133): line 133: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=166.003 s (line 139): line 139: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=169.674 s (line 145): line 145: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.003 | RunEval lost_drop at t=171.397 s (lines 146-148): line 148: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.003 s wasted |
| failed_or_retried_action | 0.003 | RunEval no_progress at t=171.397 s (lines 146-148): lines 146-148: 'collect_wood' succeeded but position and inventory are unchanged; 0.003 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=173.401 s (line 151): line 151: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.004 | RunEval failed_action at t=177.613 s (line 157): line 157: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.004 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=183.705 s (line 163): line 163: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=185.909 s (lines 164-166): line 166: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=185.909 s (lines 164-166): lines 164-166: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=187.683 s (line 169): line 169: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=191.416 s (line 175): line 175: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=193.279 s (lines 176-178): line 178: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=193.279 s (lines 176-178): lines 176-178: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=195.188 s (line 181): line 181: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=198.878 s (line 187): line 187: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.003 | RunEval lost_drop at t=200.924 s (lines 188-190): line 190: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.003 s wasted |
| failed_or_retried_action | 0.003 | RunEval no_progress at t=200.924 s (lines 188-190): lines 188-190: 'collect_wood' succeeded but position and inventory are unchanged; 0.003 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=202.758 s (line 193): line 193: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=206.499 s (line 199): line 199: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=211.208 s (line 205): line 205: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=215.273 s (line 211): line 211: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=219.291 s (line 217): line 217: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=222.929 s (line 223): line 223: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.001 | RunEval failed_action at t=226.567 s (line 229): line 229: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=230.217 s (line 235): line 235: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=232.122 s (lines 236-238): line 238: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=232.122 s (lines 236-238): lines 236-238: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |
| failed_or_retried_action | 0.002 | RunEval failed_action at t=234.012 s (line 241): line 241: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.002 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=236.08 s (lines 242-244): line 244: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=236.08 s (lines 242-244): lines 242-244: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |
| failed_or_retried_action | 0.005 | RunEval failed_action at t=239.125 s (line 247): line 247: action 'ensure_pickaxe' failed (FAILED: no crafting_table item); 0.005 s lost |
| failed_or_retried_action | 0.001 | RunEval lost_drop at t=241.288 s (lines 248-250): line 250: 'collect_wood' reported success but nothing reached the inventory within 5 s / by the next result; 0.001 s wasted |
| failed_or_retried_action | 0.001 | RunEval no_progress at t=241.288 s (lines 248-250): lines 248-250: 'collect_wood' succeeded but position and inventory are unchanged; 0.001 s lost |

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

Total 241.439 s, attributed waste (overlaps merged) 65.39 s, efficiency 0.729, milestones 0/5, findings 128. Full detail in runeval.json.

## Claims cross-check

Deterministic checks of what the agent reported against its own log and the server log. Claims never change a verdict.

| Code | Severity | t s | Lines | Finding |
|---|---|---|---|---|
| self_report_contradiction | high | 241.439 | 252 | line 252: summary claims finalSplit='wood', but the log shows None (last milestone reached in the log) |
| self_report_contradiction | high | 241.439 | 252 | line 252: summary claims splits=1, but the log shows 0 (milestones reached in the log) |
| agent_server_mismatch | high | 0.0 | 1 (server 21) | agent line 1 reports pos (-215.6, 64.0, 238.5) (overworld); server line 21 (t=0.742) has (-180.5, 70.0, 214.5) (overworld), 42.94 blocks apart |
| agent_server_mismatch | high | 33.66 | 7 (server 60) | agent line 7 reports pos (-215.6, 64.0, 238.5) (overworld); server line 60 (t=33.799) has (-183.6, 69.0, 253.6) (overworld), 35.72 blocks apart |
| agent_server_mismatch | high | 37.125 | 10 (server 64) | agent line 10 reports pos (-215.6, 64.0, 238.5) (overworld); server line 64 (t=36.805) has (-183.6, 69.0, 253.6) (overworld), 35.72 blocks apart |
| agent_server_mismatch | high | 54.731 | 13 (server 86) | agent line 13 reports pos (-215.6, 64.0, 238.5) (overworld); server line 86 (t=54.835) has (-187.4, 69.0, 251.5) (overworld), 31.43 blocks apart |
| agent_server_mismatch | high | 56.885 | 16 (server 88) | agent line 16 reports pos (-215.6, 64.0, 238.5) (overworld); server line 88 (t=56.838) has (-187.4, 69.0, 251.5) (overworld), 31.43 blocks apart |
| agent_server_mismatch | high | 58.841 | 19 (server 90) | agent line 19 reports pos (-215.6, 64.0, 238.5) (overworld); server line 90 (t=58.844) has (-187.4, 69.0, 251.5) (overworld), 31.43 blocks apart |
| agent_server_mismatch | high | 60.823 | 22 (server 93) | agent line 22 reports pos (-215.6, 64.0, 238.5) (overworld); server line 93 (t=60.847) has (-187.4, 69.0, 251.5) (overworld), 31.43 blocks apart |
| agent_server_mismatch | high | 62.799 | 25 (server 95) | agent line 25 reports pos (-215.6, 64.0, 238.5) (overworld); server line 95 (t=62.851) has (-187.4, 69.0, 251.5) (overworld), 31.43 blocks apart |
| agent_server_mismatch | high | 67.745 | 28 (server 101) | agent line 28 reports pos (-215.6, 64.0, 238.5) (overworld); server line 101 (t=67.86) has (-187.4, 69.0, 251.5) (overworld), 31.43 blocks apart |
| agent_server_mismatch | high | 70.049 | 31 (server 104) | agent line 31 reports pos (-215.6, 64.0, 238.5) (overworld); server line 104 (t=69.861) has (-187.4, 69.0, 251.5) (overworld), 31.43 blocks apart |
| agent_server_mismatch | high | 93.146 | 34 (server 131) | agent line 34 reports pos (-215.6, 64.0, 238.5) (overworld); server line 131 (t=92.896) has (-192.6, 69.0, 253.8) (overworld), 28.08 blocks apart |
| agent_server_mismatch | high | 97.237 | 37 (server 136) | agent line 37 reports pos (-215.6, 64.0, 238.5) (overworld); server line 136 (t=96.903) has (-193.7, 69.0, 250.0) (overworld), 25.25 blocks apart |
| agent_server_mismatch | high | 99.377 | 40 (server 138) | agent line 40 reports pos (-215.6, 64.0, 238.5) (overworld); server line 138 (t=98.905) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 101.361 | 43 (server 141) | agent line 43 reports pos (-215.6, 64.0, 238.5) (overworld); server line 141 (t=100.908) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 103.419 | 46 (server 144) | agent line 46 reports pos (-215.6, 64.0, 238.5) (overworld); server line 144 (t=103.912) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 105.157 | 49 (server 146) | agent line 49 reports pos (-215.6, 64.0, 238.5) (overworld); server line 146 (t=104.915) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 107.181 | 52 (server 148) | agent line 52 reports pos (-215.6, 64.0, 238.5) (overworld); server line 148 (t=106.916) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 108.978 | 55 (server 150) | agent line 55 reports pos (-215.6, 64.0, 238.5) (overworld); server line 150 (t=108.919) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 111.266 | 58 (server 153) | agent line 58 reports pos (-215.6, 64.0, 238.5) (overworld); server line 153 (t=110.923) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 112.985 | 61 (server 155) | agent line 61 reports pos (-215.6, 64.0, 238.5) (overworld); server line 155 (t=112.927) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 115.194 | 64 (server 158) | agent line 64 reports pos (-215.6, 64.0, 238.5) (overworld); server line 158 (t=114.931) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 116.921 | 67 (server 160) | agent line 67 reports pos (-215.6, 64.0, 238.5) (overworld); server line 160 (t=116.934) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 118.753 | 70 (server 162) | agent line 70 reports pos (-215.6, 64.0, 238.5) (overworld); server line 162 (t=118.937) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 120.562 | 73 (server 165) | agent line 73 reports pos (-215.6, 64.0, 238.5) (overworld); server line 165 (t=120.944) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 122.438 | 76 (server 166) | agent line 76 reports pos (-215.6, 64.0, 238.5) (overworld); server line 166 (t=121.945) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 125.713 | 79 (server 171) | agent line 79 reports pos (-215.6, 64.0, 238.5) (overworld); server line 171 (t=125.951) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 127.658 | 82 (server 173) | agent line 82 reports pos (-215.6, 64.0, 238.5) (overworld); server line 173 (t=127.954) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 129.476 | 85 (server 176) | agent line 85 reports pos (-215.6, 64.0, 238.5) (overworld); server line 176 (t=129.96) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 131.622 | 88 (server 178) | agent line 88 reports pos (-215.6, 64.0, 238.5) (overworld); server line 178 (t=131.966) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 133.439 | 91 (server 179) | agent line 91 reports pos (-215.6, 64.0, 238.5) (overworld); server line 179 (t=132.967) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 135.308 | 94 (server 182) | agent line 94 reports pos (-215.6, 64.0, 238.5) (overworld); server line 182 (t=134.97) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 137.14 | 97 (server 184) | agent line 97 reports pos (-215.6, 64.0, 238.5) (overworld); server line 184 (t=136.974) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 138.94 | 100 (server 186) | agent line 100 reports pos (-215.6, 64.0, 238.5) (overworld); server line 186 (t=139.001) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 140.788 | 103 (server 189) | agent line 103 reports pos (-215.6, 64.0, 238.5) (overworld); server line 189 (t=141.006) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 142.648 | 106 (server 191) | agent line 106 reports pos (-215.6, 64.0, 238.5) (overworld); server line 191 (t=143.01) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 144.688 | 109 (server 194) | agent line 109 reports pos (-215.6, 64.0, 238.5) (overworld); server line 194 (t=145.014) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 146.976 | 112 (server 196) | agent line 112 reports pos (-215.6, 64.0, 238.5) (overworld); server line 196 (t=147.018) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 148.845 | 115 (server 198) | agent line 115 reports pos (-215.6, 64.0, 238.5) (overworld); server line 198 (t=149.021) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 150.943 | 118 (server 201) | agent line 118 reports pos (-215.6, 64.0, 238.5) (overworld); server line 201 (t=151.025) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 154.708 | 121 (server 206) | agent line 121 reports pos (-215.6, 64.0, 238.5) (overworld); server line 206 (t=155.034) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 156.736 | 124 (server 208) | agent line 124 reports pos (-215.6, 64.0, 238.5) (overworld); server line 208 (t=157.037) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 158.683 | 127 (server 210) | agent line 127 reports pos (-215.6, 64.0, 238.5) (overworld); server line 210 (t=159.038) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 160.454 | 130 (server 212) | agent line 130 reports pos (-215.6, 64.0, 238.5) (overworld); server line 212 (t=160.043) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 162.36 | 133 (server 214) | agent line 133 reports pos (-215.6, 64.0, 238.5) (overworld); server line 214 (t=162.047) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 164.163 | 136 (server 216) | agent line 136 reports pos (-215.6, 64.0, 238.5) (overworld); server line 216 (t=164.051) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 166.005 | 139 (server 219) | agent line 139 reports pos (-215.6, 64.0, 238.5) (overworld); server line 219 (t=166.055) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 167.791 | 142 (server 221) | agent line 142 reports pos (-215.6, 64.0, 238.5) (overworld); server line 221 (t=168.058) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 169.675 | 145 (server 224) | agent line 145 reports pos (-215.6, 64.0, 238.5) (overworld); server line 224 (t=170.062) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 171.4 | 148 (server 225) | agent line 148 reports pos (-215.6, 64.0, 238.5) (overworld); server line 225 (t=171.062) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 173.403 | 151 (server 227) | agent line 151 reports pos (-215.6, 64.0, 238.5) (overworld); server line 227 (t=173.065) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 175.47 | 154 (server 230) | agent line 154 reports pos (-215.6, 64.0, 238.5) (overworld); server line 230 (t=175.068) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 177.617 | 157 (server 233) | agent line 157 reports pos (-215.6, 64.0, 238.5) (overworld); server line 233 (t=178.072) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 179.6 | 160 (server 236) | agent line 160 reports pos (-215.6, 64.0, 238.5) (overworld); server line 236 (t=180.077) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 183.707 | 163 (server 240) | agent line 163 reports pos (-215.6, 64.0, 238.5) (overworld); server line 240 (t=184.083) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 185.91 | 166 (server 243) | agent line 166 reports pos (-215.6, 64.0, 238.5) (overworld); server line 243 (t=186.087) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 187.685 | 169 (server 245) | agent line 169 reports pos (-215.6, 64.0, 238.5) (overworld); server line 245 (t=188.094) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 189.593 | 172 (server 246) | agent line 172 reports pos (-215.6, 64.0, 238.5) (overworld); server line 246 (t=189.095) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 191.418 | 175 (server 249) | agent line 175 reports pos (-215.6, 64.0, 238.5) (overworld); server line 249 (t=191.098) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 193.28 | 178 (server 251) | agent line 178 reports pos (-215.6, 64.0, 238.5) (overworld); server line 251 (t=193.1) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 195.189 | 181 (server 254) | agent line 181 reports pos (-215.6, 64.0, 238.5) (overworld); server line 254 (t=195.103) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 197.042 | 184 (server 256) | agent line 184 reports pos (-215.6, 64.0, 238.5) (overworld); server line 256 (t=197.106) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 198.88 | 187 (server 258) | agent line 187 reports pos (-215.6, 64.0, 238.5) (overworld); server line 258 (t=199.11) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 200.927 | 190 (server 261) | agent line 190 reports pos (-215.6, 64.0, 238.5) (overworld); server line 261 (t=201.115) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 202.76 | 193 (server 263) | agent line 193 reports pos (-215.6, 64.0, 238.5) (overworld); server line 263 (t=203.117) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 204.51 | 196 (server 264) | agent line 196 reports pos (-215.6, 64.0, 238.5) (overworld); server line 264 (t=204.119) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 206.5 | 199 (server 267) | agent line 199 reports pos (-215.6, 64.0, 238.5) (overworld); server line 267 (t=206.123) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 208.337 | 202 (server 269) | agent line 202 reports pos (-215.6, 64.0, 238.5) (overworld); server line 269 (t=208.126) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 211.209 | 205 (server 273) | agent line 205 reports pos (-215.6, 64.0, 238.5) (overworld); server line 273 (t=211.133) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 213.25 | 208 (server 275) | agent line 208 reports pos (-215.6, 64.0, 238.5) (overworld); server line 275 (t=213.135) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 215.275 | 211 (server 278) | agent line 211 reports pos (-215.6, 64.0, 238.5) (overworld); server line 278 (t=215.138) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 217.242 | 214 (server 280) | agent line 214 reports pos (-215.6, 64.0, 238.5) (overworld); server line 280 (t=217.143) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 219.293 | 217 (server 282) | agent line 217 reports pos (-215.6, 64.0, 238.5) (overworld); server line 282 (t=219.147) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 221.143 | 220 (server 285) | agent line 220 reports pos (-215.6, 64.0, 238.5) (overworld); server line 285 (t=221.151) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 222.93 | 223 (server 287) | agent line 223 reports pos (-215.6, 64.0, 238.5) (overworld); server line 287 (t=223.154) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 224.741 | 226 (server 290) | agent line 226 reports pos (-215.6, 64.0, 238.5) (overworld); server line 290 (t=225.158) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 226.568 | 229 (server 291) | agent line 229 reports pos (-215.6, 64.0, 238.5) (overworld); server line 291 (t=226.159) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 228.458 | 232 (server 293) | agent line 232 reports pos (-215.6, 64.0, 238.5) (overworld); server line 293 (t=228.162) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 230.219 | 235 (server 296) | agent line 235 reports pos (-215.6, 64.0, 238.5) (overworld); server line 296 (t=230.166) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 232.123 | 238 (server 298) | agent line 238 reports pos (-215.6, 64.0, 238.5) (overworld); server line 298 (t=232.17) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 234.014 | 241 (server 300) | agent line 241 reports pos (-215.6, 64.0, 238.5) (overworld); server line 300 (t=234.174) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 236.081 | 244 (server 303) | agent line 244 reports pos (-215.6, 64.0, 238.5) (overworld); server line 303 (t=236.178) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 239.13 | 247 (server 306) | agent line 247 reports pos (-215.6, 64.0, 238.5) (overworld); server line 306 (t=239.184) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |
| agent_server_mismatch | high | 241.289 | 250 (server 309) | agent line 250 reports pos (-215.6, 64.0, 238.5) (overworld); server line 309 (t=241.188) has (-193.7, 69.0, 249.4) (overworld), 24.96 blocks apart |

## Evidence coverage

Server log: `runs/live/foot-01/server.jsonl`, 509 samples, t=0.742-1736.946 s (agent run t=0.0-241.439 s). Agent snapshots checked against a server sample within +-1.5 s: 84; without one: 0.
- server log covers the whole agent run

## Fairness notes (from baseline/rules.json)

- **difficulty**: Agent on Peaceful, pros on Easy. Peaceful only helps the agent (no hostile mobs, no hunger). Not adjusted; noted.
- **timer**: Agent banner = wall-clock elapsed time of the run, including model latency. Pro primary times are IGT. Report the agent against both pro IGT and pro RTA (1:48 run: IGT 108.421, RTA 119.331). Segment times for pros are IGT unless the timing sheet says otherwise.
- **practice**: Pros practise a set seed many times; the agent run is the author's best published run, also after many development runs (rmalde/minecraft-agent:optimization/COMPARISON.md, NOTES.md). Neither is a first attempt.
- **brackets**: The montage has cuts, so every agent milestone is a [low, high] bracket. Verdicts use the side that is most favourable to the agent (ratio_low).
- **route_supplied**: The agent's route, including the exit-portal coordinates, is fixed in its config (rmalde/minecraft-agent:README.md:104). A missed shortcut in that route is a miss of the agent system as published, not of the LLM alone.
- **rng**: Dragon perch timing is partly random (rmalde/minecraft-agent:README.md:7, 'Dragon flight and landing times can vary'). The End segment is reported, but its FLAG/SLOW verdict should be read with that in mind.
