# Live agent: Minecraft 1.16.5 on seed `8398967436125155523`

Person C's half: a real 1.16.5 world, a headless agent that plays it, server-side evidence, and
footage you can put in the demo. Everything here is reproducible on this Mac.

## Why it is built this way (what the prior work got wrong)

| Evidence | What it implies for the design |
|---|---|
| Gemini 4 Argon finished MC in **27 h 14 min**, wrote 2,783 programs, **died 605 times**, ~$520 | Letting a model emit low-level actions every tick is the expensive, fragile way |
| rmalde/minecraft-agent: **8:43 on this exact seed** vs **2:54.545** for a human, with an LLM planner **plus a separate action model (JEV)** | The winning shape is *judgment on top, deterministic control below* |
| Their 49-minute run: 215 generic waits, 54 failed actions, mined from water, recovered a crafting table it had just placed | The failures are in **execution and state tracking**, not in route knowledge |
| Voyager / Project Sid / JARVIS-1 all pair an LLM with a code/skill layer | Skills beat token-by-token control |

So this agent is five layers, and only two of them call a model:

```
L0 world model      mineflayer + minecraft-data (1.16.5 packet truth, no vision)
L1 reflexes         JS, 4 Hz: lava escape, low-hp abort, stuck detection, jump-free
L2 skill library    deterministic macros: pathfind, dig, craft, loot, build frame, light portal,
                    barter, throw eye, eat, fight, flee  (the JEV replacement)
L3 action classifier nvidia/nemotron-3.5-bolt-e4b (free tier, ~0.7 s): which skill, which args
L4 planner          deepseek-flash (effort low, ~4 s): route branch, risk, when to stop
L5 evaluator        server RCON telemetry + event log -> splits, waste, claims-vs-evidence
```

The model is *not* allowed to do arithmetic or coordinates: `src/math.js` computes portal linking,
eye triangulation, eye/rod counts and barter expectation, and the planner is shown the numbers.

## What runs

| Piece | Command | Notes |
|---|---|---|
| Server | `live/server/start.sh` | vanilla 1.16.5, seed, RCON 25575, `online-mode=false`, **peaceful**, console FIFO |
| Telemetry | `live/server/telemetry.js --run <id>` | 1 Hz RCON: pos/dim/health/food/selected + slot-by-slot inventory, log tail for deaths/advancements |
| Ground truth check | `live/server/verify-groundtruth.js` | scans the surveyed coords for the block each task claims |
| Agent | `live/agent/run.js --goal "..."` | planner + classifier + skills, writes `runs/live/<id>/events.jsonl` |
| Scripted seed route | `live/agent/scripts/play-route.js --viewer --third-person` | chests -> frame -> light -> enter; used for footage |
| Viewer (live stream) | part of `play-route.js --viewer` | `http://localhost:3007`, WebSocket, third- or first-person |
| Clip with stats | `live/footage/overlay.py` | burns server-verified HUD + decisions into a frame sequence |
| Client (optional) | `live/client/launch.js --auth prism` | direct 1.16.5 + LWJGL 3.2.2; Prism's arm64 LWJGL override crashes 1.16.5 on this Mac |

Prism Launcher is installed with `1.16.5` and `1.16.1` instances pointing at the same game dir and
Temurin 8. Prism's own launch of 1.16.5 substitutes an arm64 LWJGL 3.3.1 build and crashes at chunk
tessellation; `live/client/launch.js` uses the official version JSON with 3.2.2 instead.

## Verified on this seed (no client UI involved)

`live/server/verify-groundtruth.js`, from the live world:

- End portal at (−1130, 34, 856): **active** (`end_portal` block + frames). So no blaze rods/eyes are needed.
- Village chest at (−228, 71, 240): **exact**; the other two supply chests are at (−290, 68, 253) and (−284, 66, 262).
- Entry frame at (−285, ~66, 258..261): partial obsidian frame, plus `crying_obsidian` and a tree in the way.
- Nether exit (−141, 40, 104): **does not exist in a fresh world** — it is a portal the reference agent built.

The scripted route looted **obsidian 21, iron pickaxe, flint, iron 6** in 42 s, matching the reference
survey exactly, and crafted `flint_and_steel`.

## Known limits (state these, don't hide them)

- The frame builder places blocks but its verification reads a stale block state (server updates land
  ~200–400 ms late), so it reports failure and does not light the portal. The reference repo fixed the
  same class of bug with an epoch counter; that port is the next change.
- Pathfinding still occasionally stalls on tree/village geometry; the stuck reflex cancels after 20 s.
- The classifier runs on a free NVIDIA tier; it is fast but picks coarse args (counts are clamped).
- The agent plays one seed; nothing here claims a general speedrunning rate.

## Streaming

`prismarine-viewer` is a live stream while the agent runs: `http://localhost:3007`. Watch it on the
LAN or over Tailscale (`tailscale serve 3007` for a URL), or add it as an OBS Browser source. No
Minecraft client is involved. The recorded clips are captured from the same page, so what you stream
and what you submit are the same pixels.

## Footage

`evidence/footage/agent-01-chests.mp4` — 95 s, third-person, overlay from `agent_runs/agent-01/`.
Banner: run id, version, seed, difficulty. HUD: server clock, dimension, position, hp/food, held item,
cumulative loot. Callouts: the agent's own decisions and skill results at their timestamps.
