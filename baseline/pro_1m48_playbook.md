# Pro playbook: Rayoh 1:48 run (template for a human to fill from the video)

> **Optional.** It would add the pro-side "why" to `analysis/agent_vs_pro.md`. The same questions work for the 2:49 run's video (https://www.youtube.com/watch?v=n1M95cySBQ0), which is now the per-segment baseline.

Video: https://www.youtube.com/watch?v=2NEvhsZG5iY · Run: https://www.speedrun.com/mc/runs/zqe4g39z (IGT 1:48.421, RTA 1:59.331, 1.16.5, Easy, Set Seed).

**About 10 minutes of watching.** Answer each question with what you **see**, plus the video timestamp. Write "not visible" when you can't tell, and never guess. Then copy the answers into `baseline/pro_1m48_playbook.json` (same question ids), or paste them to B in chat and B will fill the JSON.

Known from the agent's survey of this seed, for reference: the village chest is at (−228, 71, 240); the two ruined-portal chests at (−284, 66, 262) and (−290, 68, 253); the ruined portal at (−285, 67, 259); the active End portal at (−1130, 34, 856); 8 beds in the village (positions in `rmalde/minecraft-agent:optimization/nether/config.json:66-107`).

## Segment 1: spawn → Nether entry (M_start → M_portal_in)

- **Q1.1** In what order does the pro visit things? (village chest, beds, ruined-portal chests, the portal) Give a timestamp for each.
- **Q1.2** How many **beds** does the pro pick up before the Nether? Which ones, roughly (near spawn, village centre, by the portal)?
- **Q1.3** How many **obsidian** does the pro end with before building? Which chests does it open (all 3 supply chests? any food chests?)
- **Q1.4** How is the portal lit: flint and steel (crafted when?) or a fire charge?
- **Q1.5** Does the pro complete the ruined frame or build a fresh one? About how many blocks are placed?
- **Q1.6** Does the pro take any **food** or **tools** (crafting table, pickaxe, sword, bucket)?
- **Q1.7** Movement: sprint-jumping in the open? Anything else (boat, pearls, bridging)?

## Segment 2: Nether (M_portal_in → M_portal_out)

- **Q2.1** F3 coordinates on arrival in the Nether (if F3 is shown).
- **Q2.2** Route: straight line, or around terrain? Any digging, bridging, or tunnelling through netherrack?
- **Q2.3** Where is the **exit portal built**? F3 X, Y, Z if visible.
- **Q2.4** How long from arriving at the exit spot to the portal being lit (timestamps)?
- **Q2.5** Is there any bartering, fortress, or other detour? (Expected: none, since the End portal is pre-filled.)

## Segment 3: exit portal → End portal (M_portal_out → M_end_in)

- **Q3.1** Where does the overworld exit land? F3 X, Y, Z if visible. Is it inside the portal room, next to it, or somewhere the pro has to dig or walk from?
- **Q3.2** What does the pro do between arriving and jumping into the End portal (walk, dig, drop down)? Timestamps.
- **Q3.3** Does the pro place any eyes? (Expected: no, since all 12 frames are pre-filled.)

## Segment 4: End (M_end_in → M_finish)

- **Q4.1** Timestamp of the **first bed placed or used** in the End.
- **Q4.2** Strategy: one-cycle (beds on the perched dragon), zero-cycle (beds on the dragon in flight from a pillar), or other?
- **Q4.3** How many **perches/cycles** before the dragon dies?
- **Q4.4** How many **beds are used** on the dragon? How many are left over?
- **Q4.5** Any blocks placed for cover? Any damage taken or near-deaths?
- **Q4.6** Timestamp of the dragon death and of entering the exit portal / timer stop.

## General

- **Q5.1** Is an on-screen IGT timer visible? Where?
- **Q5.2** Any cuts in the edited video (jumps in the timer or scene)? Timestamps.
