# demo-05 — carved exit-portal site in the Nether

- Resumed at the reference nether waypoint (−138.5, 41, 98.4), 11 obsidian left.
- `build_portal` (open-site search) failed: nether terrain has no clear 4×5 plane.
- `build_portal_here` carved **13 blocks** out of the netherrack and placed **9/14** frame blocks.
  The far side column (z=100) failed with `place`: its lower neighbour is the carved floor, but the
  standing column at x+2 was only carved 0..4 high, so the bot could not get a reference face for
  the bottom corner scaffold that the side column rests on.
- No death. Dimension stayed `the_nether`.

Fix for the next take: carve the standing column to y−1..y+5 and 3 blocks deep, and place the two
bottom corner scaffolds before the side columns (that ordering already exists; the carve height was
the blocker).

First-person frames: `runs/live/demo-05/frames/` (1345 frames, 26.9 fps), telemetry in
`runs/live/demo-05/server.jsonl`.
