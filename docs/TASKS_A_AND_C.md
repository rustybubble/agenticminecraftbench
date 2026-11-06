# Today's split: Anshul (Person A, checker) and friend (Minecraft + evidence)

Hard deadline: **submit by 3:50** (closes 4:00). AI attempts are frozen at **2:15**.

## Friend: Minecraft server and real evidence (your own machine)

### F1. Server on the seed (by 1:15)
- Minecraft **Java 1.16.5** server (or a singleplayer world with cheats on for F2). Seed `8398967436125155523`.
- `server.properties`: `level-seed=8398967436125155523`, `enable-rcon=true`, `rcon.port=25575`, `rcon.password=<pick one>`, `online-mode=false` if needed, `difficulty=peaceful` (matches the agent repo).
- 1.16.5 needs **Java 8–16**. If it won't start on a newer Java: `brew install openjdk@16`.

### F2. Ground-truth screenshots (by 1:45): correctness evidence
Teleport to each point (`/tp`) and take a screenshot **with F3 open**. Save them to `evidence/screenshots/<name>.png` and push:
| name | where | what the screenshot must show |
|---|---|---|
| `end_portal` | overworld (−1130, 34, 856) | the End portal, active or with its frame, and the coordinates |
| `exit_portal` | Nether (−141, 40, 104) | the Nether portal used to exit, and the coordinates |
| `entry_portal` | overworld (−285, 67, 259) | the entry portal site, and the coordinates |
| `village_chest` | overworld (−228, 71, 240) | the chest's contents (the GUI opened) |
If anything does **not** match those numbers, tell Anshul and Person B right away, because a task's answer is wrong.

### F3. One real gameplay log (by 2:30, optional but valuable)
1. Start the server and join as a player.
2. In another terminal, from the repo: `python3 capture/rcon_poller.py --player <yourname> --password <pw> --out runs/human-01/events.jsonl`
3. Play 3–5 minutes, **spawn → village chests → build the portal → enter the Nether**. Play normally and quickly; it's fine to make a mistake or two.
4. Ctrl-C the poller, then push `runs/human-01/events.jsonl` and note the time you entered the Nether.

### F4. If time is left: help Person B
Write and run task drafts on the chosen AI (fresh chat each time, first answer saved to `attempts/<task_id>.json` with model, date and exact prompt).

## Anshul: checker (Person A)

### A1. Watch the build workflow and accept its output (now → ~1:30)
- `cd code && python -m pytest -q` passes.
- `python -m splitcheck.check --root tests/fixtures --self-test`: every alternate is OK, every broken answer gets its expected verdict.
- Review the reviewers' high-severity fixes. Commit.

### A2. Run on Person B's real tasks (as they land, by 2:15)
- `python -m splitcheck.check --root .. --self-test` on the real `tasks/` and `reference/`. A failure means either the checker or the reference answer is wrong: resolve it with B.
- Cross-check 2–3 answers against B's `tools/compute_answers.py` or by hand.
- Write 3 "looks right but is wrong" answers (Y divided by 8; eyes counted without the pre-filled frames; a portal lit with no flint and steel). All must be caught, each with a reason.

### A3. Determinism and the results table (2:15–2:45)
- After the 2:15 freeze, run the checker on `attempts/` twice and confirm `runs/results.csv` is identical both times (`shasum`).
- Hand `runs/results.csv` and the per-task reasons to B for the write-up.

### A4. Layer B on real data (2:30–3:15)
- `python -m splitcheck.logeval runs/human-01/events.jsonl --pro ../splits/pro_splits.json --out runs/human-01/report.json`
- Also run it on the synthetic wasteful and false-claim logs to show the detectors catch them.
- If the real log has odd formats, fix the parser and nothing else.

### A5. Demo pieces (3:15–3:40)
One task → the AI's answer → the checker's catch with its reason; then one Layer B finding from a log. No reruns of the AI.
