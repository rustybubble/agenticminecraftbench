# Evaluator handoff: checking runs yourself

This is for whoever runs the agent. It explains how to evaluate any new run with the **deterministic evaluator** and the **AI perception checker**, without help. Everything is in `code/splitcheck/`. It uses the standard library only (Python 3.10+) plus `ffmpeg` for perception.

## 0. Setup (once)
```bash
git pull
cd code
python -m pytest -q          # should print "360 passed" (or more)
```
Every command below runs from `code/`.

## 1. Evaluate a run: one command
```bash
python -m splitcheck.evaluate ../runs/live/<RUN>/events.jsonl \
    --server-log ../runs/live/<RUN>/server.jsonl \
    --run-id <RUN> --outdir ../runs/<RUN>-eval
```
* **Agent log formats:** auto-detected. Your live agent (`skill_start`/`skill_result`/`route_*`/`summary`), the rmalde agent (`decision`/`result`), and `capture/rcon_poller.py` logs all work.
* **Server log formats:** both `live/server/telemetry.js` (`sample`/`inventory`/`log`) and `capture/rcon_poller.py` work. The server's advancement message ("We Need to Go Deeper") counts as Nether-entry evidence, and its death message counts as death evidence.
* `--run-notes PATH` (optional): defaults to `RUN_NOTES.md`/`NOTES.md` next to the log. Its facts go into a "This run" section, and any `rules.json` fairness note that contradicts them is flagged.
* **Outputs** in `--outdir`:
  * `report.md`: read this. It contains:
    * the segment table vs the pro (2:49 baseline), with OK, SLOW, FLAG or NOT_REACHED per segment
    * waste per segment, with log lines
    * the claims cross-check (`self_report_contradiction`, `inventory_loss_without_effect`, `agent_server_mismatch`)
    * evidence coverage (where the server log is missing)
    * progress before failure
    * fairness notes
  * `efficiency.json`, `runeval.json`, `timeline.json`: the data behind every number.
* **Deterministic:** run it twice and the outputs are byte-identical.

### What it detects (all rule-based, no AI)
| Detector | Fires when |
|---|---|
| `failed_action` | a skill returns `ok:false` (cost = its duration) |
| `unfinished_skill` | a skill started and never returned before the log ended |
| `skill_warnings` | `skill_warn` lines (pathfinding timeouts, "lava ahead"); report only |
| `idle` | no movement or inventory change for ≥ 3 s **and** no skill executing |
| `no_progress`, `action_loop`, `oscillation` | a success with no state change; repeats; back-and-forth |
| `lost_drop`, `mining_in_water` | mined but nothing picked up; mining while the eyes are underwater (needs server blocks) |
| `excess_food`/`excess_tools`/`excess_materials` | gathered things the route doesn't need |
| `place_then_recover` | a crafting table placed and then picked back up |
| `death`, `damage_taken` | from agent and server logs |
| `self_report_contradiction` | the summary's actions/failures/deaths/splits disagree with the log |
| `inventory_loss_without_effect` | obsidian used by a failed build that placed 0 blocks |
| `agent_server_mismatch` | the agent's logged position or inventory disagrees with the server's within ±1.5 s |
| seed-aware decisions | ignored known chest obsidian, a full frame over existing blocks, overworld travel when the Nether route was known, bad paths |

Thresholds are in the `THRESHOLDS` dict at the top of `detectors.py`. Verdict rules live in `../baseline/rules.json` (B's file; don't edit it).

## 2. AI perception checker (optional, supporting evidence)
The AI only says what is visible. It never decides a verdict. Every answer is cached, so reruns are identical, and each field is scored against ground truth.

**Best input: clean frames + `frames_index.json`.** No overlay, exact run times:
```json
{"frames": [{"file": "f00001.jpg", "run_t": 12.345}, ...]}
```
`file` is resolved next to the index or inside any `frames*/` folder beside it. `run_t` is seconds since the agent's first log line (`spawn`).
```bash
python -m splitcheck.perception none.mp4 --frames-index ../runs/live/<RUN>/frames_index.json \
    --run-log ../runs/live/<RUN>/events.jsonl --out ../runs/perception/<RUN>_perception.json \
    --every 1 --adaptive --backend claude
```

**From a video with an overlay:** the overlay is cropped and masked automatically for 1280×720 and 960×540 clips. Give it an offset (`run_t = video_t + offset`):
```bash
python -m splitcheck.perception ../evidence/footage/<clip>.mp4 --run-log ../runs/live/<RUN>/events.jsonl \
    --out ../runs/perception/<RUN>_perception.json --every 2 --adaptive --offset <S> --backend claude
```
If you have a per-frame index for a video, as with demo-01's `clip_index.json`, see the "extract frames + build frames_index" snippet in `docs/EVALUATOR_HANDOFF.md` §5.

**Backends:**
* `claude`: uses the Claude Code CLI (`claude -p`) with your subscription login. It **removes `ANTHROPIC_API_KEY` from the environment** automatically, because that key in our shell is invalid. About 10 s per frame, 4 in parallel.
* `codex`: `gpt-6-astra` via the Codex CLI. **Usage-limited until about 7:16 PM today.**
* `fake`: offline, for tests.

**Then:**
```bash
python -m splitcheck.perception_validate ../runs/perception/<RUN>_perception.json \
    --run-log ../runs/live/<RUN>/events.jsonl --server-log ../runs/live/<RUN>/server.jsonl
python -m splitcheck.evaluate ... --perception ../runs/perception/<RUN>_perception.json   # adds the Perception section
```

**What we learned (read before trusting perception):**
* Reliable: **obsidian portal frame** (32/32 on agent-05 clean frames). Coarse facts (frame, lit, water, village, player visible) agree 41/41 between Claude and Codex.
* Unreliable:
  * Small objects from the overhead camera: chests 0/32, lava disagreement 0/41.
  * The finished or lit portal in demo-01, never seen.
* Ground-truth rules (`perception_validate.py`) are proximity-based, so "near a chest" is not the same as "chest visible". Fields with n < 10 or accuracy < 0.8 are kept out of the rules automatically, and the report says so.
* **Want better perception?** Capture first-person or a close follow camera with clean frames + `frames_index.json`, and ask about large things only.

## 3. Regenerate everything (results pack, demo page, zip)
```bash
python -m splitcheck.pack --root .. --out ../runs/results_pack    # RESULTS.md over every run + determinism check
python -m splitcheck.demo --root .. --out ../runs/demo           # interactive demo page: open runs/demo/index.html
cd .. && bash make_submission.sh                                  # tests -> pack -> zip (../agenticminecraftbench_submission.zip)
```
* The pack picks up `agent_runs/*/events.jsonl` and `runs/live/{demo-,live-,foot-}*/events.jsonl` automatically.
* The demo page's Tab 1 is built from demo-01. To feature another run, edit `RUN` and the clip paths at the top of `code/splitcheck/demo.py`.

## 4. Gotchas
* **zsh doesn't split variables:** `S="--server-log x"; cmd $S` passes ONE argument. Write the flags out, or use an array.
* **Live-agent logs only report position when a skill returns.** That's why idle detection is suppressed while a skill is executing, and why the server log matters. Keep `telemetry.js` running for the whole run. (Of 621 demo-01 samples, `online` was never true, but the `pos` fields were filled; the adapter uses `pos`.)
* **`capture/rcon_poller.py` no longer crashes:** errors become `poll_error` lines, and it reconnects.
* **Don't edit** `baseline/`, `fixtures/`, `SCHEMA.md`, `rules.json` (B's), or attempts. Tell B if a fixture's expected output looks wrong.
* **After any code change:** `python -m pytest -q`, then re-run the pack. It checks determinism itself.

## 5. Snippet: frames_index from a video + clip_index (what we did for demo-01)
```python
import json, os, subprocess
from splitcheck import perception as P
vid = "../evidence/footage/<clip>.mp4"; info = P.probe(vid)
idx = json.load(open("../runs/live/<RUN>/clip_index.json"))["frames"]   # [{file, run_t}] per video frame
out = "../runs/perception/<RUN>_frames"; os.makedirs(out, exist_ok=True)
vf = P.scene_filter(info["width"], info["height"])                        # crops/masks the overlay
picked, last = [], -9
for i, f in enumerate(idx):
    if f["run_t"] - last >= 0.5: picked.append((i, f["run_t"])); last = f["run_t"]
fi = []
for i, rt in picked:
    p = os.path.join(out, f"f{i:05d}.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{i / info['fps']:.3f}", "-i", vid,
                    "-frames:v", "1", "-vf", vf, p], check=True)
    fi.append({"file": os.path.basename(p), "run_t": rt})
json.dump({"frames": fi}, open(os.path.join(out, "frames_index.json"), "w"), indent=1)
```
Check one output frame by eye: no overlay text may remain, or the model could read the answers.

## 6. Where things are
| Path | What |
|---|---|
| `code/splitcheck/evaluate.py` | one-command evaluator (calls the rest) |
| `code/splitcheck/timeline.py` | log parsers (agent, live agent, poller, telemetry) |
| `code/splitcheck/detectors*.py` | all detection rules |
| `code/splitcheck/effcheck.py`, `v4export.py` | segment verdicts vs pro (`rules.json`), log → timeline |
| `code/splitcheck/perception*.py`, `detectors_perception.py` | AI perception, validation, rules |
| `code/.perception_cache/` | cached model answers (tracked; frames are not) |
| `runs/<RUN>-eval/` | evaluator outputs per run |
| `runs/results_pack/RESULTS.md` | every headline number in one place |
| `runs/demo/index.html` | the interactive demo |
| `docs/AGENT_RUN_HANDOFF.md` | how to capture a run (poller, notes, frames) |
