# herobrine — does an AI agent make the same decisions a pro Minecraft speedrunner makes?

**Same set seed, same version, segment by segment.** Seed `8398967436125155523`, Java **1.16.5**, Easy/Peaceful.

We take a published LLM agent run, a pro run on the *same seed*, and a live agent we built, put them on one timeline, and name every second an agent loses and every shortcut it misses.

## Headline numbers (all reproducible)

| Result | Value | Where |
|---|---|---|
| Published LLM agent (Astra + JEV) vs verified pro, same seed | **516.7 s vs 169.1 s = 3.1× slower** | `runs/results_pack/RESULTS.md` |
| Worst segment: Nether exit → End portal | **51.6–56.7 s vs 2.45 s (21–23×)**, `FLAG` | `analysis/agent_vs_pro.md` |
| Cause of that segment | exit portal placed **3 Nether blocks off** the ÷8 point → lands 21 blocks from the End portal | `analysis/agent_vs_pro.md` |
| Our live agent, spawn → Nether | **60.0 s vs pro 66.7 s = 0.9×** (ahead of the pro pace) | `runs/demo-08-eval/report.md` |
| Chatbot on 7 seed decision tasks (`gpt-6-astra`, high, first answer) | **6 OK / 1 ILLEGAL** | `runs/results.csv` |
| The catch | full-route plan is fast but travels to `the_end` from `the_nether` → `ILLEGAL`, missed `bed_one_cycle`, `skip_fortress_active_portal` | `runs/checker_output/` |

## Watch it

| Clip | What it shows |
|---|---|
| [`evidence/footage/demo-09-spawn-to-dragon.mp4`](evidence/footage/demo-09-spawn-to-dragon.mp4) | **2:43** spawn → chests → portal build → Nether (real) → End → dragon (End leg staged, labelled) |
| [`evidence/footage/demo-08-resources.mp4`](evidence/footage/demo-08-resources.mp4) | 21 obsidian from the three supply chests, first person, game HUD |
| [`evidence/footage/demo-08-portal.mp4`](evidence/footage/demo-08-portal.mp4) | cornerless obsidian frame built block-by-block, lit, walked into the Nether |
| [`evidence/footage/demo-04-nether-travel.mp4`](evidence/footage/demo-04-nether-travel.mp4) | Nether travel in 32-block legs to the reference waypoint |
| [`evidence/footage/agent-01-chests.mp4`](evidence/footage/agent-01-chests.mp4) | the first live take (third person) |

Every clip carries a HUD drawn from **server-side RCON telemetry** (hearts, hunger, inventory counts, position, server clock), so a frame can be matched to a log line.

## How the check works (no LLM judges anything)

1. **Four segments, identical boundaries for every run:** Nether in, Nether out, End in, finish. Agent milestones read from the banner/log are **[low, high] brackets**; verdicts use the side most favourable to the agent.
2. **Verdict per segment** from `baseline/rules.json`: `OK` / `SLOW` / `FLAG` / `NOT_REACHED`, with the run's own median as the reference so one bad segment cannot hide behind a good one.
3. **Waste detectors** on the run log: `failed_action`, `unfinished_skill`, `idle`, `action_loop`, `lost_drop`, `mining_in_water`, `excess_*`, `place_then_recover`, `death`, `self_report_contradiction`, `inventory_loss_without_effect`, `agent_server_mismatch`, plus seed-aware checks (ignored chest obsidian, a full frame over an existing one, overworld travel when the Nether route was known).
4. **Cross-checks against the server, not the agent's word.** `agent_runs/agent-01` is the worked example: its summary claims 0 failures; the log shows a failed `build_portal`. That contradiction is a detector, not an anecdote.

```bash
cd code && python -m pytest -q                       # checker tests
python -m splitcheck.evaluate ../runs/live/demo-08/events.jsonl \
    --server-log ../runs/live/demo-08/server.jsonl --run-id demo-08 --outdir ../runs/demo-08-eval
python -m splitcheck.pack --root .. --out ../runs/results_pack
bash make_submission.sh                               # tests → pack → zip
```

## Repo map

| Path | What |
|---|---|
| `baseline/` | pro segment times (2:49 per segment, 1:48 total), `rules.json` verdicts, reference implementation, fixture generator |
| `agent_runs/published_montage/` | the published agent's milestones from its banner, bracketed |
| `analysis/agent_vs_pro.md` | per segment: where the time goes, why (confirmed vs inferred), what it missed |
| `tasks/`, `reference/`, `attempts/`, `runs/results.csv` | 7 same-seed decision tasks, expert answers, the model's first answers, checker verdicts |
| `extras/generic_tasks/` | 14 generic decision tasks (supplementary) |
| `code/` | checker, evaluator, detectors, perception, demo generator |
| `live/` | **the live agent**: 1.16.5 server + RCON telemetry, mineflayer world model, reflex layer, skill library, DeepSeek/OpenAI planner, NVIDIA classifier, first-person capture |
| `runs/live/`, `runs/*-eval/` | every live take: agent events, server telemetry, notes, evaluator reports |
| `runs/demo/index.html` | interactive demo page (replay synced to the evaluator) |
| `evidence/` | clips, frames indexes, ground-truth block checks |
| `WRITEUP.md`, `SOURCES.md`, `UNVERIFIED.md` | the write-up, every source, every open fact |

## What the live agent can and cannot do (stated plainly)

- **Can:** loot the seed's 21 obsidian in ~40 s, craft the igniter, build a **cornerless 10-obsidian nether frame**, light it with `activateBlock`, enter the **Nether**, and travel to the exact reference waypoint in 32-block legs.
- **Cannot yet:** build the **exit** portal in the Nether (carve timing: a 108-cell carve blows the 240 s skill budget; 9/14 frame blocks placed), so the End leg is **staged** in the demo clip and labelled `staged` in the logs. The dragon kill in the clip is a command.
- Its spawn → Nether segment is nonetheless **faster than the pro's** (0.9×), which is the point: the bottleneck is not "can it move", it is *decisions under a long horizon*.

## Fairness

- Pro and agent run the **same seed and version**; the pro run is a verified speedrun.com submission.
- The published agent ran **Peaceful** and had seed coordinates supplied by its authors, which only helps it; both facts are stated in `analysis/agent_vs_pro.md`.
- Every number has a source in `SOURCES.md`; anything still unverified is in `UNVERIFIED.md` rather than smoothed over.
- Staged steps in our own footage are marked in the clip HUD and in `runs/live/*/NOTES.md`.
