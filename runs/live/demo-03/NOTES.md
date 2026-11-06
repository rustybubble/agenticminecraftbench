# demo-03 — cornerless portal, lit, entered the Nether (first-person take)

Successful chain on a fresh world (Peaceful), no deaths:

1. three supply chests → obsidian 21, iron pickaxe, flint, iron 6 (~40 s)
2. **cornerless** frame (10 obsidian) with dirt corner scaffolding: `placed 14` targets = 10 obsidian
   + 4 scaffolds, `ok: true`
3. lit with `activateBlock` → `lit.ok: true`
4. **entered the Nether** → `entered.ok: true`, `dimension: the_nether`

Why cornerless matters: 21 obsidian must cover both portals (entry + exit). A full 14-block frame
leaves 7, which cannot build the 10-block exit frame. 10 + 10 leaves 1 spare.

After entry, `travel_legs` failed with `s.travelLegs is not a function` (a rewrite of the frame
builder had deleted the method). That is fixed and demonstrated in demo-04.
