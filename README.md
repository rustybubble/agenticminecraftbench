# SplitCheck: checking AI against pro Minecraft speedrunners

SplitCheck splits a pro Minecraft Java Any% (1.16) run into its real stages ("splits") and poses one decision task per split.
The AI answers in structured JSON. A deterministic checker asks: is the plan legal, how many seconds slower than the pro route is it, and which pro techniques did it miss?
Any legal route is accepted and scored only by its time. A different route that is just as fast is not "wrong".
Ground truth comes from a surveyed real seed (8398967436125155523, from rmalde/minecraft-agent) and from cited Minecraft wiki and source facts.
See `WRITEUP.md` for results and `SCHEMA.md` for the file formats.

| Path | Owner | Contents |
|---|---|---|
| `SCHEMA.md` | B | Task, reference, split and plan-action formats (the checker codes against this) |
| `tasks/` | B | `<id>.json`: what the AI sees. No answers. |
| `reference/` | B | `<id>.json`: correct answer, why, trap, techniques, alternates, broken answers. Never shown to the AI. |
| `splits/` | B | `pro_splits.json` (human split times), `time_costs.json` (seconds per action at pro pace) |
| `tools/` | B | `compute_answers.py`: reproducible math for coordinate and triangulation answers |
| `code/` | A | Simulator, legality rules, time costs, technique tagging, `check.py` |
| `attempts/` | C | The AI's first answers, with model, date and exact prompt |
| `runs/` | C | Checker output on the attempts |
| `SOURCES.md`, `UNVERIFIED.md`, `WRITEUP.md` | B | Sources per task, facts still to check, the write-up |
