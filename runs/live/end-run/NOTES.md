# end-run — End entry + dragon (staged teleport)

- `/tp` into the End portal block (staged; the agent cannot build the nether exit portal yet).
- Dimension changed to `the_end`; `/kill @e[type=ender_dragon]` (staged, explicitly demo-only).
- 1290 frames at 28.7 fps, first person, game HUD.
- Bug found and fixed here: `enter_portal` only searched for `nether_portal`, so the End portal was
  invisible to it; it now also matches `end_portal`, and it stands *in* the portal block (range 0)
  instead of next to the frame.
