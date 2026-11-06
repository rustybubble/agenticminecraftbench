# demo-07 — fallback finish route (nether → overworld → End portal)

After the carved exit portal stalled (demo-06: `build_portal_here` carved 100+ cells and hit its
240 s budget), the fallback was: return through the **entry** portal and walk to the active End
portal in the overworld.

- `travel_legs` took the bot from (−135, 41, 98) toward the entry portal (−36, 77, 32); it ended at
  (−35.5, 33, 47.5) — right x/z, 44 blocks of vertical/short distance away, because `GoalXZ` does
  not control Y and the portal sits on a ledge at y=77.
- `enter_portal` therefore found no portal in range; the run stopped there, in the Nether, alive.

Next single change: after `GoalXZ` legs, do a **vertical leg** to the portal's y (`goto` with the
portal's exact y and range 2) before `enter_portal`. That is ~10 lines and unblocks both the exit
portal attempt and this fallback.
