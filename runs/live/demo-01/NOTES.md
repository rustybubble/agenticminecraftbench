# demo-01 — full route attempt, 1.16.5 seed 8398967436125155523

**Result: reached the Nether, then died.** This is the farthest the agent has got.

| Time (run s) | Event |
|---|---|
| 0.6 | route start, spawn |
| ~40 | all three supply chests looted: obsidian 21, iron pickaxe, flint, iron 6 |
| ~42–58 | built the 4×5 obsidian frame (14/14 blocks), lit it, **entered the Nether** (`route_portal` run_t 58.2) |
| 58–298 | nether travel toward (−139, 41, 100): `goto` hit the 240 s timeout in netherrack/lava terrain |
| ~300 | exit-portal build aborted: "no obsidian in inventory" (the 7 spare obsidian were gone by then) |
| 379.6 | **death** in the Nether (outside the captured window; server log has it) |

Footage: `evidence/footage/demo-01-nether-entry.mp4` — 33 s, 20.7 fps, 1280×720 → 960×540,
third-person, overlay from `server.jsonl` (RCON, 1 Hz) + `events.jsonl`. Frames in `clipframes/`
(with mtimes preserved), index in `clip_index.json`.

## Fixes that made the Nether possible (this run)

1. **Reach is measured from the eye, not the feet.** The top row is 4 blocks up; a jump adds ~1.2
   blocks of eye height, which is how a player places it.
2. **Reference block = any solid neighbour**, not just the block below. The top-middle blocks have
   the open interior below them; their only neighbour is the top corners, so corners are placed first.
3. **The bot must not path *into* the frame it is building.** It now stands two blocks off the plane
   and slides along it.
4. **Lighting used `activateItem()`** (swings the item at the air). Flint & steel needs
   `activateBlock(block)` → `block_place`. That was the reason frames stayed unlit.
5. Water: pathfinder liquid is impassable, plus a swim-up reflex (the bot used to sink).

## Still broken

- `goto` to the nether waypoint times out: 240 s of digging through netherrack, and the pathfinder
  does not treat lava as a hard no at the route level. Next fix is a segmented tunnel: 32-block legs,
  re-plan at each leg, y held at 40, with a lava scan before each leg.
- The exit-portal step needs the remaining 7 obsidian protected (it was lost before arrival).
