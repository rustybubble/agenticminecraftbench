# demo-06 — carved exit portal, second attempt (widened standing room)

- Resumed at the reference nether waypoint with 11 obsidian.
- `build_portal_here` widened the carve to 3 deep × y−1..y+5 (108 cells, dug one at a time).
  It exceeded the 240 s skill budget before the frame was complete; no death, still in the Nether.
- Lesson: carving cell-by-cell with `dig` is the slow part, not the frame. Carve a 3×4×5 box with a
  single `fill`-like pass (or dig only the ring cells + one standing column) before building.
