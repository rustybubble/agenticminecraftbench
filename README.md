# SplitCheck: is an AI agent as efficient as a pro Minecraft speedrunner?

SplitCheck compares an AI agent's run with a pro's run on the **same set seed** (`8398967436125155523`, Java 1.16.5), segment by segment: spawn → Nether, Nether, exit portal → End portal, End.
It reports how much slower the agent is in each segment, flags segments that lose time out of proportion to the run's own pace, and tags the waste (`missed_shortcut`, `extra_items`, ...) with evidence.
Agent data: the published Astra + JEV agent run (rmalde/minecraft-agent), 8:36.7 on its banner and 8:43.300 in its README. Pro baselines: Rayoh's 1:48.421 IGT run (headline) and dumbo0116's 2:49.149 IGT run (backup).
A secondary set of 7 decision tasks on the same seed checks single decisions such as portal placement, obsidian count and whether blaze rods are needed. 14 generic tasks are supplementary.
See `WRITEUP.md` for results, `SCHEMA.md` for formats and `baseline/rules.json` for what counts as efficient.

| Path | Owner | Contents |
|---|---|---|
| `baseline/` | B | Pro segment times (`pro_2m49_segments.json`; `pro_1m48_segments.json` once timed), the 1:48 timing sheet and playbook, `rules.json` (thresholds, waste rules, fairness), `make_splits.py`, `reference_check.py`, `make_fixtures.py` |
| `agent_runs/published_montage/` | B | Agent milestone brackets read from the published montage banner |
| `analysis/agent_vs_pro.md` | B | Per segment: where, why, what it missed |
| `fixtures/` | B | Checker tests with expected outputs |
| `tasks/`, `reference/` | B | 7 seed decision tasks (secondary) |
| `extras/generic_tasks/` | B | 14 generic decision tasks (**supplementary, not part of the headline result**) |
| `splits/` | B | Earlier split table and per-action time costs for the decision-task plans |
| `tools/` | B | Answer math, task builder, validators |
| `code/` | A | The checker |
| `attempts/`, `runs/` | C | AI attempts and checker output |
| `SOURCES.md`, `UNVERIFIED.md`, `WRITEUP.md` | B | Sources, open checks, write-up |
