# RUN agent-05 — clean route take (third attempts series)

This file documents the take that should be used from the agent-02 handoff round. It is the
third capture attempt after the handoff at 2:25 PM; the earlier ones are kept and their defects
are named below.

## Headline

- **RUN_ID:** agent-05 (the previous takes in this round: agent-02, agent-03, agent-04)
- **Server:** vanilla 1.16.5, seed `8398967436125155523`, **Peaceful** (handoff allowed a change if stated)
- **Planner/classifier:** scripted seed route for this take (`play-route.js`), so the decisions are
  deterministic and repeatable; the LLM loop was used in agent-01 and is unchanged.
- **Outcome:** looted all three supply chests (obsidian 21, iron pickaxe, flint, iron 6, beds not taken),
  crafted `flint_and_steel`. The portal build step was **not** run in this take (it still fails, see below).
  No deaths, no hostiles engaged.
- **Interventions:** none during the run. World regenerated from the seed immediately before it;
  player cleared at spawn.

## Defects in the earlier takes (kept, not hidden)

| Take | Defect |
|---|---|
| agent-02 | world had already been looted, so every chest returned nothing; portal step aborted for lack of flint/iron |
| agent-03 | capture started after the route (run_t 203–308 s), so the clip showed the post-run linger; `capture/rcon_poller.py` was launched from the wrong cwd |
| agent-04 | `capture/rcon_poller.py` **crashes after ~4 s** (traceback in `/tmp/poller4.log`; 6 lines written). Frames were fine. |
| agent-05 | uses `live/server/telemetry.js` instead of the poller, because the poller crash blocks the HUD |

## Files

| File | Contents |
|---|---|
| `events.jsonl` | agent events, unedited |
| `server_events.jsonl` | **RCON telemetry** (`live/server/telemetry.js`, 1 Hz): position, dimension, health, food, selected item, slot-by-slot inventory |
| `frames/` | raw 1280×720 JPEG frames at ~25 fps (not committed; 1.1 GB) |
| `frames-clean/` | 290 frames, 960×540, no overlay, contiguous 12 s window |
| `frames_index.json` | `{file, run_t}` where `run_t` = seconds since the agent's `spawn` event |
| `../../evidence/footage/agent-05-route.mp4` | 45 s, 24.8 fps, overlay burned in from the two logs |

## What the footage proves

Banner: run id, MC version, seed, difficulty. HUD: server clock, dimension, position, hp/food,
held item, cumulative loot. Callouts: the agent's own decisions and skill results at their
timestamps. The frames are captured from the agent's own world via `prismarine-viewer`, not from a
screen recording of a person.

## Still blocking the Nether (precise)

`buildPortalFrame` calls `bot.placeBlock` into a 4×5 plane and then verifies. Obsidian leaves the
inventory (21 → 17) but the verification reads air even after 900 ms of polling, and later
placements in the same call fail. The reference repo hit this and fixed it with an epoch counter
plus a re-read of the server's block update; our `findPortalSite` also picks a plane whose bottom
row is at the bot's feet, so the reference block can be inside the player's own collision box.
Next change: place from a stand-back position with `bot.placeBlock` against the block *below* the
target, and accept the inventory delta (already implemented) as the primary success signal.

Until that is fixed the bot cannot build the frame, so it cannot light a portal, so the Nether
segment of the plan does not start. That is the honest blocker; everything up to the frame is
reproducible in ~45 s.

## Streaming / fps

- `prismarine-viewer` is a live stream at `http://localhost:3007` (third- or first-person).
- Capture rate measured in this take: **24.8 fps** at 1280×720 JPEG (`page.screenshot` in a loop,
  no fixed sleep). Higher rates are possible with Playwright `recordVideo`, at the cost of losing
  the frame↔event alignment that the overlay depends on.
