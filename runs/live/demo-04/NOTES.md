# demo-04 — Nether travel, first person

Resumed from the portal built in demo-03 (bot in `the_nether`, 11 obsidian).

- `travel_legs` (32-block legs, lava scan, re-plan each leg) reached the reference waypoint
  **(−138.5, 41, 98.4)** from (−34, 77, 29) in **3 legs** — the same single long `goto` that
  timed out at 240 s in demo-01.
- Exit portal then failed with "no clear 4x5 site" (nether terrain). Carving was added for the
  next take (demo-05): 13 blocks carved, 9/14 frame blocks placed, far side column unreachable.
- Clip: `evidence/footage/demo-04-nether-travel.mp4`, first person, 960×540, ~13 fps
  (893 frames captured at 17.9 fps), overlay from `server.jsonl` + `events.jsonl`.

First person is now the default for both the viewer stream and captures: the eval compares against
speedrun VODs, so POV-to-POV is the only fair comparison.
