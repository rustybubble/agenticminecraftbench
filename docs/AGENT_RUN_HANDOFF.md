# Agent run handoff (from Anshul / checker side)

Your run's log is the input to our whole eval, so the main goal is a **clean, complete, untouched log**.

## Before you start
1. `git pull` in our repo (`rustybubble/agenticminecraftbench`) to get the poller.
2. In the server's `server.properties`, set `enable-rcon=true`, `rcon.port=25575`, `rcon.password=<anything>`, then restart the server.
3. Choose a RUN_ID, for example `agent-01`, and create `agent_runs/<RUN_ID>/` in our repo.

## During the run
1. Run the agent as normal. **Don't change any agent or logging code.** If you have to restart, start a new RUN_ID and keep both logs.
2. In a second terminal, from our repo, start the server-side logger (read-only, safe):
   ```
   python3 capture/rcon_poller.py --player <bot username> --password <rcon pw> --out agent_runs/<RUN_ID>/server_events.jsonl
   ```
   Stop it with Ctrl-C when the run ends.
3. Screen-record if you can (the Prismarine viewer is fine). We need about 20 s of footage for the demo.
4. **When the bot enters the Nether**, copy the current `runs/<RUN_ID>/events.jsonl` from the agent repo into `agent_runs/<RUN_ID>/` and push it, or send it to Anshul, even though the run is still going. We'll test the pipeline on it while you continue.
   - Quick self-check: `cd code && python -m splitcheck.runeval ../agent_runs/<RUN_ID>/events.jsonl --pro ../splits/pro_splits.json` should print a total time, milestones and findings. If it errors, send the error and the first 20 lines of the log.

## After the run, whatever the outcome
A death, a crash and a stall are all results.
1. Copy the full `runs/<RUN_ID>/events.jsonl` into `agent_runs/<RUN_ID>/events.jsonl`. Don't edit or trim it.
2. Add `agent_runs/<RUN_ID>/RUN_NOTES.md`:
   ```
   RUN_ID:
   Planner model (PLANNER_MODEL):        JEV version:
   Server: Minecraft 1.16.5, seed 8398967436125155523, difficulty:
   Start time (local):          End time:
   First attempt? (yes/no, how many runs before):
   Interventions (restarts / code edits / commands / pauses, with times):
   Outcome (reached Nether? End? dragon? finished?):
   Anything weird I noticed (with approx time):
   ```
3. Commit and push `events.jsonl`, `server_events.jsonl`, `RUN_NOTES.md` and the video (or a link to it).

## Timing
- The partial log at Nether entry as soon as possible.
- The full log by about **3:00 PM** at the latest. Submissions close at 4:00.

The more honest the notes (restarts, interventions), the better we score on fairness.
