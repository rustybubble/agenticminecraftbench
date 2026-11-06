# runeval: how was the run actually played?

`python -m splitcheck.runeval <log> [--pro ../splits/pro_splits.json] [--route-sheet sheet.json] [--seed-dir DIR] [--out report.json] [--md report.md]`

This reads the game log of a Minecraft Java 1.16.5 speedrun on seed `8398967436125155523`. The player can be a human or an AI agent. It reports what went wrong and how many seconds each mistake cost. It does not grade the plan the player wrote down. It grades the play: mining while standing in water, gathering far more food than the run needs, walking past a chest the player knew about, actions that failed and were retried, loops, deaths, and claims that the inventory contradicts.

## Inputs

| Input | Where it comes from |
|---|---|
| Agent log | `events.jsonl` from rmalde/minecraft-agent (`start`, `decision`, `result`, `position_sample`, `nether_entered`, ...) |
| Human log | `capture/rcon_poller.py`, a server-side RCON poller (`position_sample` with position, dimension, inventory and health, plus `nether_entered`, `end_entered`, `death_suspected`) |
| Seed features | `data/seed_8398967436125155523/` (village, chests and their contents, portals, nether route, end portal). See its `PROVENANCE.md` |
| Pro splits | `splits/pro_splits.json` (optional) |
| Route sheet | What a human runner was told before the run (optional) |

`splitcheck.timeline.load_timeline` turns either log format into one `Timeline`: samples carrying time, log line, position, dimension, inventory, health, food, water and lava flags and the action taken, plus milestone events.

## What is measured

Each detector in `splitcheck.detectors.REGISTRY` (and `SEED_REGISTRY` when present) is a pure function `f(timeline, ctx) -> [Finding]`. Each finding carries:

- `code` and `category`. The category is one of `micro` (execution: failed actions, waits, loops, mining in water, overshoot), `decision` (route and resource choices: too much food, unused items, a detour, a known chest skipped), `safety` (deaths, low health, lava) or `claim` (stated facts the log contradicts).
- `severity`, `t_start` and `t_end` (seconds since the run started), and `cost_s`.
- `lines`: the 1-based log line numbers it rests on.
- `evidence`: the positions, inventory deltas and thresholds behind it.

The thresholds live as named constants at the top of `detectors.py` and of the seed detector module. Change them there. The report lists which detectors ran and which raised errors (`coverage.detectors_run`, `coverage.detector_errors`). A detector that crashes is recorded and skipped, so the rest of the report still runs.

## Information fairness

A finding that depends on seed knowledge only counts against the player if the player was told that fact. For an agent, the disclosed knowledge is the union of every `knownSeed` block across its decision states. That is exactly the information the agent was given. For a human, it is the `--route-sheet`. Without a route sheet, a human is assumed to know nothing about the seed. The full seed features remain available as context, for example to locate a chest, but an undisclosed feature is never charged as a mistake. `coverage.knowledge_features` lists what the player was considered to know.

## How cost_s becomes the score

1. Every finding with `cost_s > 0` claims the interval `[t_start, t_start + cost_s]`. An interval that runs past the end of the log slides back so it ends there, which means a late death still counts. Waste can never exceed the total time.
2. **No double counting.** The attributed waste is the length of the union of those intervals. Where intervals overlap, each stretch of time goes to exactly one finding. Priority goes to higher severity, then larger `cost_s`, then earlier start, then code. Each finding reports its `attributed_s` (its unique share). The category totals sum exactly to `attributed_waste_s`. `overlap_removed_s` is the raw sum of costs minus the attributed waste.
3. `efficiency = (total_time_s - attributed_waste_s) / total_time_s`. `total_time_s` is the span of the log.
4. Milestones are nether entry, nether exit, end entry, dragon kill and game won. Each is reached or not, giving `milestone_completion`.
5. With `--pro`, each split is compared with the pro split, giving a delta in seconds and a ratio (`logeval.compare_splits`).

Every number in `score` can be recomputed from `findings[].attributed_s` and `splits`.

## Determinism

There are no LLM calls, no network access, no clock reads and no randomness. Detectors run in sorted code order. Findings are sorted with a total order: cost descending, then severity, start time, code, first line and message. Floats are rounded to 3 decimal places (efficiency to 4), and the JSON is written with `sort_keys`. Running the same input twice gives byte-identical JSON, which `tests/test_runeval.py` checks.

## Limitations

- `cost_s` is an estimate. Each detector states its rule in `evidence`: time lost to a failed action, the extra time in a loop, the travel time of a detour at sprint speed, and so on. It is not a measured counterfactual.
- Anchoring a finding's cost at `t_start` keeps the arithmetic simple and auditable. When a detector's cost is spread over a longer stretch, the overlap merge can be off by the difference.
- The human poller samples roughly once a second. Events shorter than that, such as a single block mined in water, can be missed. Food level and water flags may be absent from the poller log. A detector that needs a missing field reports nothing; it does not guess.
- An agent's API latency is not player time. It is reported, never charged.
- The seed data covers only what the rmalde surveys recorded. A feature that was never surveyed cannot be checked.
