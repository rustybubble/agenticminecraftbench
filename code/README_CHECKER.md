# SplitCheck checker: how to run it

Python 3.11+, standard library only (pytest for tests). No network, no LLM calls.
All commands run from `code/`:

```bash
cd code

# Layer A: score every attempt in ../attempts against ../reference
python -m splitcheck.check --root ..
#   -> ../runs/results.csv  (task_id, model, verdict, reason, miss_category,
#                            techniques_missed, time_s, pro_time_s)
#   -> ../runs/checker_output/<task_id>.json  (full per-step trace)

# Checker self-test: every reference "alternates" answer must be OK,
# every "broken" answer must get its expected_verdict
python -m splitcheck.check --root .. --self-test

# Layer B: evaluate a gameplay log (rmalde agent events.jsonl format)
python -m splitcheck.logeval path/to/events.jsonl --pro ../splits/pro_splits.json --out report.json

# Tests (contract + unit)
python -m pytest -q
```

Missing `tasks/`, `reference/` or `attempts/` files do not crash the checker; it prints what is missing.

## Verdicts (SCHEMA.md section 3)

| Verdict | Meaning |
|---|---|
| `OK` | Legal and within tolerance; for plans, priced within `tolerance.seconds` of `pro_time_s`. |
| `SLOW` | Plan is legal but more than `tolerance.seconds` slower than `pro_time_s`. Plans only. |
| `ILLEGAL` | Plan breaks a game rule or uses something it does not have (e.g. lights a portal with no flint and steel). The reason names the failing step index and the missing precondition. Plans only. |
| `WRONG` | A number / coordinates / choice answer outside tolerance, or a reply with no parseable JSON object. |

Every non-OK verdict also gets the reference's `miss_category` (one of the 8 tags in SCHEMA section 6) and `techniques_missed` (reference technique tags the simulated plan did not use).

## How plans are checked

`splitcheck.sim.simulate(task, plan)` starts from `task.state` and runs each action in the SCHEMA section 4 vocabulary (`mine`, `craft`, `smelt`, `loot_chest`, `travel`, `build_portal`, `light_portal`, `enter_portal`, `barter`, `kill`, `throw_eye`, `place_eyes`, `bed_explode`, `reset`). Each step checks preconditions (inventory, dimension, location, Peaceful spawning) and updates inventory, position, dimension and time. Travel is priced by straight-line distance; the Nether uses 8:1 coordinate scaling. The first failed precondition makes the plan `ILLEGAL` and the reason cites that step.

## Determinism

- The same input always gives the same output. There is no randomness and no model in the loop.
- Stochastic game mechanics (gravel to flint, bartering, eye breaks, blaze rod drops) use an **expected-value rule**: the sim credits the expected yield, rounded down, and never makes a random draw. Those steps carry the note `stochastic: expected value used`. `throw_eye` always uses up the eye.
- Model replies are parsed by `answers.parse_json_answer`: the first valid JSON object in the reply, with code fences and prose ignored.

## What is verified and what is an estimate

Every time cost carries a `source` and `verified` flag (SCHEMA section 5):

- Built-in defaults in `sim.DEFAULT_COSTS` are all `"source": "estimate", "verified": false` (for example sprint travel at 7.127 blocks/s).
- `../splits/time_costs.json`, when present, is merged over the defaults. Its entries carry a URL or `repo:path:line` source and `verified: true` only when confirmed.
- `splitcheck/time_costs_template.json` lists every key the sim prices (generated from `sim.DEFAULT_COSTS`), so the table can be filled with sourced numbers. The sim also accepts optional per-block or per-mob overrides named `mine_<block>` and `kill_<mob>` (for example `kill_blaze`), which take priority over `mine` and `kill`.
- Reference answers and techniques carry their own `verified` / `source`; unverified items are listed in `UNVERIFIED.md`.

Conclusions are reported as "seconds versus the cited same-seed human split", not as a claimed optimum. They should hold under a ±30% change to the estimated costs.

## Layer B detectors (`splitcheck.logeval`)

Pure functions of the event log, the server telemetry and the seed survey (`minecraft-agent/optimization/nether/*.json`, which is what the agent was told). Each finding cites the event line number and field.

1. **Split extraction**: dimension changes, portal entry/exit, End entry, dragon death; compared with `splits/pro_splits.json` (seconds of difference per split).
2. **Detours**: items acquired and never used or consumed by the end of the run.
3. **Undo**: a block placed and then broken within N seconds after its use was done (e.g. crafting tables).
4. **Lost drops**: a block was mined but no matching inventory change followed.
5. **Overshoot**: still moving away from a waypoint after it was reached (distance rises after a minimum ≤ r).
6. **Idle**: time with no position change and no action, plus waits and failed actions counted from the events.
7. **Deaths**, with cause and position.
8. **Disclosed-target travel**: path length ÷ straight-line distance to each disclosed coordinate. Reported only; it is never turned into an "optimal" time.
9. **Claims vs evidence**: planner summaries ("reached portal", "have 12 eyes") checked against server inventory and position. A false claim is the headline finding.
