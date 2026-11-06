# RUN agent-01 — live agent, seed 8398967436125155523

- **RUN_ID:** agent-01
- **Planner model:** `deepseek-flash` (effort low) · **Action classifier:** `nvidia/nemotron-3.5-bolt-e4b` (free tier)
- **Server:** Minecraft 1.16.5 (vanilla), seed `8398967436125155523`, **difficulty easy for this take**
  (`server.properties` is now `peaceful` for future takes; the handoff/rmalde config is Peaceful)
- **Start / end (local):** 2026-11-06 13:45:39 → 13:47:05 (84 s agent process; footage 95 s)
- **First attempt?** No for the harness, yes for this world: the world was regenerated from the seed
  immediately before the take, and the player was cleared (`/clear @s`) at spawn.
- **Interventions during the run:** none (no restarts, no code edits, no console commands, no pauses).
  The world reset, spawn clear and RCON start happened before the take.
- **Outcome:** looted all three supply chests (**obsidian 21**, iron pickaxe, flint, iron, beds not taken),
  crafted `flint_and_steel`, then attempted a portal build near the ruined frame at x=−281.
  **The frame build placed 0 verified blocks** (4 obsidian left the inventory, verification still read air),
  so the portal was never lit and the bot never entered the Nether. No deaths. 0 hostile encounters.
- **Anything weird:** the placement verification reads a stale block state on this server (the block
  appears ~200–400 ms late), which is why the frame counted as failed. The reference repo hit the same
  class of bug and fixed it with an epoch counter; ours needs the same.

## Files

| File | What it is |
|---|---|
| `events.jsonl` | the agent's own event log (decisions, skill start/result, loot, splits), unedited |
| `server_events.jsonl` | server-side RCON poller (`capture/rcon_poller.py`, 2 Hz) — position, dimension, inventory, health, food |
| `splits.json` | split timestamps the agent recorded |
| `../evidence/footage/agent-01-chests.mp4` | 95 s, 4.5 fps, third-person Prismarine view, overlay burned in from the two logs |

## Footage provenance

The clip is the **agent's own world** rendered headlessly by `prismarine-viewer` (`firstPerson: false`)
and captured frame-by-frame with Playwright. Every overlay line is read from
`server_events.jsonl` (position/dimension/health/food, 2 Hz) and `events.jsonl` (decisions, loot),
aligned to each frame's file mtime. Rebuild it with:

```
python3 live/footage/overlay.py --frames evidence/footage/frames-agent01 \
  --server agent_runs/agent-01/server_events.jsonl --agent agent_runs/agent-01/events.jsonl \
  --run-id agent-01 --seed 8398967436125155523 --difficulty "easy (this take)" \
  --out evidence/footage/agent-01-chests.mp4
```

## Streaming (asked during the run)

**Yes.** `prismarine-viewer` is already a live web stream: while the agent runs, `http://localhost:3007`
serves the world over WebSocket at ~10–20 fps. It can be watched on the LAN, over Tailscale
(`http://<tailscale-ip>:3007`), or as an OBS "Browser" source for a real stream. No public deploy is
needed; if a public URL is wanted, `tailscale serve 3007` or an ngrok tunnel is enough. Latency is
~100–300 ms and there is no client-side Minecraft install involved.

## Reproduce

```
live/server/start.sh                                  # 1.16.5, seed, RCON 25575, peaceful
python3 capture/rcon_poller.py --player SplitAgent --password splitcheck-live \
  --out agent_runs/agent-01/server_events.jsonl --hz 2
cd live/agent && node scripts/play-route.js --viewer --third-person --portal \
  --run agent-01 --linger 35
```
