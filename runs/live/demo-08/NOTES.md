# demo-08 — first-person capture with game-style HUD

Fresh world, Peaceful, one continuous first-person capture (2492 frames, 20.4 fps).

| run_t (s) | What happens | Clip |
|---|---|---|
| 0–15 | walk from spawn to the village | — |
| 15.2 | chest 1 looted (obsidian 6, iron pickaxe, sword) | `demo-08-resources.mp4` (22–50 s) |
| 37.0 / 41.5 | chest 2 / chest 3 (21 obsidian total, flint, iron) | `demo-08-resources.mp4` |
| 42–58 | **cornerless portal frame built** (10 obsidian + 4 dirt corner scaffolds), lit | `demo-08-portal.mp4` (38–68 s) |
| 60.0 | **entered the Nether** | `demo-08-portal.mp4` |

HUD (drawn by `live/footage/overlay.py --game-hud`), all from server telemetry at 1 Hz:
hearts and hunger (10 each), inventory line with counts, position/dimension, and the server clock.
Capture: `prismarine-viewer` first person → `page.screenshot` loop at ~20–29 fps.

Source frames: `frames/` (gitignored), windows in `clip-resources/` and `clip-portal/`.
