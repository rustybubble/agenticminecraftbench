# evaluate: one command, log in, verdicts out

```
cd code
python -m splitcheck.evaluate <log> [--baseline ../baseline/pro_2m49_segments.json] \
    [--run-id NAME] [--outdir ../agent_runs/NAME] [--seed-dir DIR] [--rules ../baseline/rules.json]
```

`<log>` is an agent `events.jsonl` (rmalde/minecraft-agent) or a human RCON poller log. Defaults: the 2:49.149 pro baseline, run id = the log's file stem (or its folder name when the file is `events.jsonl`), output folder `agent_runs/<run-id>/`. Exit code 0 on success, 1 if the efficiency check could not run (the error goes into `efficiency.json` and `report.md`), 2 if the log is missing.

## Output files

| File | What it is | Made by |
|---|---|---|
| `timeline.json` | SCHEMA section 8 `agent_timeline`: the five milestones read from the log (exact times, so `low == high`), facts (overworld arrival, End portal, beds, model latency, deaths, per-segment path and failed actions) and `waste_extra` | `splitcheck.v4export` |
| `efficiency.json` | SCHEMA section 8 output: `run_median_ratio`, `total`, one row per segment with agent seconds, pro seconds, ratios, waste and verdict | `splitcheck.effcheck` |
| `runeval.json` | The full RunEval report: every finding with its detector code, cost, time span, log line numbers and evidence | `splitcheck.runeval` |
| `report.md` | The judge view: headline table (segment, times, ratio, verdict), then each segment's waste entries with their evidence, then the fairness notes | this module |

## How verdicts are computed

Everything is read from `baseline/rules.json` at run time. Nothing is hardcoded.

- Segments: `spawn_to_nether`, `nether`, `exit_to_end_portal`, `end`, bounded by dimension changes (`M_portal_in` = first change to `the_nether`, `M_end_in` = first change to `the_end` after it, `M_portal_out` = the last Nether -> overworld change before `M_end_in` that is not a respawn after a death (earlier exits are listed as `wrong_order` round trips), `M_finish` = game won / exit portal that is not a respawn). `dragon_killed` alone is a proxy finish and `efficiency.json` gets a `flags` entry. A run with no finish leaves `M_finish` unreached: `end` is `NOT_REACHED`, the total is null, `flags` says so, and `beds_used` is unknown so no bed waste is charged. The report's waste column is capped at the segment's excess over the pro (raw sum in brackets), and a Timer basis section compares the total with the pro's RTA and names FLAGs that the IGT/RTA gap could decide.
- Ratio = agent segment seconds / pro segment seconds (`bracket_math`).
- `run_median` = median of the segment ratios. A segment is **FLAG** if its ratio is more than `flag_k_times_median` (2.0) times `max(run_median, 1)` and it loses at least `flag_min_excess_s` (5 s) to the pro. Otherwise **SLOW** above `ok_max_ratio` (1.25), else **OK**. A uniformly slow agent comes out SLOW everywhere; FLAG marks where time was lost out of proportion to the run's own pace.
- A segment the log never reaches is **NOT_REACHED** (no ratio).

## How RunEval evidence fills the waste entries

RunEval runs first. Each finding is placed in the segment that contains its `t_start` and mapped to one of the seven SCHEMA waste tags (for example `excess_food` to `extra_items`, `failed_action` / `action_loop` to `failed_or_retried_action`, `overshoot_waypoint` to `longer_path`, `death` to `unnecessary_risk`, `place_then_recover` to `wrong_order`). The entry's seconds are the finding's `cost_s`. Its evidence keeps the RunEval code, the time and the log line numbers, so a judge can open the log at that line. These entries are appended after the rule-based waste (`missed_shortcut`, `extra_items` from beds, model latency as `idle_wait`). **Waste never changes a verdict.** Waste seconds are estimates and can overlap; `runeval.json` `score.attributed_waste_s` gives the overlap-merged total.

## Fairness

`report.md` copies the `fairness` block of `rules.json` word for word: Peaceful vs Easy, wall clock (including model latency) vs pro IGT, practice on both sides, the route being supplied to the agent, and dragon RNG in the End segment. Model latency is reported as `idle_wait` on a `whole_run` row and is never subtracted.

## Determinism

No LLM, network, clock or randomness. The same log, baseline and rules give byte-identical files: JSON is written with fixed indentation (`timeline.json` and `runeval.json` with sorted keys, `efficiency.json` in SCHEMA key order), floats are rounded, and RunEval findings are totally ordered. `tests/test_evaluate.py` runs two synthetic logs end to end twice and compares the bytes.

```
cd code && python -m pytest -q
```
