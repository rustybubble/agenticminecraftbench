# Pro playbook: the 2:49.149 run, filled from the video

**Video watched:** the run's VOD, *"[Former PB] Minecraft SSG Any% Speedrun in 2:49"* (sqwishi channel, 1920×1080, 55 fps, 210.5 s). The team supplied a local copy. It matches the speedrun.com VOD link (https://www.youtube.com/watch?v=n1M95cySBQ0, 211 s) for [run yoex3d0z](https://www.speedrun.com/mc/runs/yoex3d0z), whose runner is dumbo0116; the in-game name is I_Like_Tide_Pods. After the run the runner opens F3, which shows `Minecraft 1.16.5 (1.16.5/vanilla)` and `Seed: [8398967436125155523]`.

**Method:**
- B extracted frames with ffmpeg and looked at them: contact sheets at 0.5–1 fps, 4–5 fps around key moments, zoomed hotbar crops, and mean frame colour at 10 fps to find loading screens.
- Video timestamps are given as `m:ss.s`.
- **F3 is not open during the run**, so no in-run coordinates are visible. No in-game timer is on screen.
- Answers are **seen** (visible in a frame) unless marked **inferred**. One count came from the human (beds: 6).

## Segment boundaries (video time)

| Milestone | Video | Cue | Check vs run comment |
|---|---|---|---|
| M_start | 0:22.0 | pause menu closes ("Back to Game"); the world was loaded paused | — |
| M_portal_in | 1:28.7 | Nether "Loading terrain" (dirt screen) begins | 66.7 s after start; comment says 66.683 ✓ |
| Nether arrival | 1:29.3 | first Nether frame (warped forest) | — |
| M_portal_out | 2:10.1 | overworld loading screen begins | 40.8 s after arrival; comment says 40.783 ✓ |
| overworld arrival | 2:10.6 | first overworld frame | — |
| M_end_in | 2:13.0 | End loading screen begins | 2.4 s after arrival; comment says 2.450 ✓ |
| End arrival | 2:13.4 | first End frame | — |
| pause | 2:21.1–2:25.0 | Game Menu, then Options/Video Settings | 7.7 s after arrival; comment says 7.733 ✓ |
| M_finish | 3:16.5 | screen goes black at the exit portal | 51.5 s after resume; comment says 51.500 ✓ |

All four of the runner's segment times are reproduced from the video to within 0.1 s.

## Segment 1: spawn → Nether entry (66.683 s)

- **Q1.1 Order (seen):**
  1. Village beds: yellow at about 0:30, yellow at about 0:35, white at about 0:43.
  2. Village supply chest at about 0:51–0:55: iron pickaxe, 6 obsidian, bread. The "Isn't It Iron Pick" and "Ice Bucket Challenge" advancements appear.
  3. Cobblestone mined ("Stone Age", about 0:55).
  4. Another yellow bed at about 1:04.
  5. Ruined-portal chest with flint and 4 obsidian at about 1:11–1:13, then the chest with 11 obsidian and iron at about 1:16 (21 obsidian; "Acquire Hardware").
  6. Frame built at 1:17–1:25.
  7. Flint and steel crafted in the 2×2 inventory grid at about 1:22–1:23, portal lit at about 1:25–1:26, in the portal until loading at 1:28.7.
- **Q1.2 Beds:** **6** (4 yellow, 2 white). The human counted 6; the hotbar at 2:56 shows 4 yellow and 2 white. Five are in the hotbar by 1:20; the sixth (white) is in the main inventory (the "White Bed" tooltip in the inventory at about 2:45). When the sixth was picked up is not resolved at 1 fps.
- **Q1.3 Obsidian / chests:** all 3 supply chests: the village chest (6) and both ruined-portal chests (+15 = 21). No food chests were opened. The hotbar reads 6 at 1:00, 19 at 1:20 and 14 at 1:26.
- **Q1.4 Lighter:** flint and steel, crafted at about 1:22 in the inventory grid (the flint comes from the portal chest; iron from the other chest).
- **Q1.5 Frame:** completes the ruined portal. **21 → 14 obsidian = 7 placed**, the same as `reference/T05` and REVIEW.md:9.
- **Q1.6 Food / tools:** 4 bread taken (from the village chest; never eaten) and some cobblestone. No crafting table, sword or bucket is used. The iron pickaxe comes from the chest.
- **Q1.7 Movement:** sprinting and sprint-jumping through the village. No boat or pearls.

## Segment 2: Nether (40.783 s)

- **Q2.1 Arrival coordinates:** not visible (no F3).
- **Q2.2 Route (seen):** sprints straight through a warped forest from 1:29 to about 1:52, crossing a small lava stream at about 1:43. From about 1:53 it digs into netherrack above a lava lake (netherrack collected and placed: the hotbar shows 11, then 5).
- **Q2.3 Exit portal coordinates:** not visible (no F3). The frame is built upward from about 1:59 to 2:06 (obsidian 13 → 2). **14 obsidian on entry, 2 left = 12 placed in the Nether** (one placed at about 1:58 before the frame).
- **Q2.4 Exit build time:** about 1:58 (first obsidian) → lit at about 2:06–2:07 → in the portal until loading at 2:10.1. About 8–9 s of building.
- **Q2.5 Detours:** none. No bastion, fortress or bartering.

## Segment 3: exit portal → End portal (2.450 s)

- **Q3.1 Where the exit lands (seen, 2:10.6–2:12.5):** **inside the End portal room**. The new portal is in the room's wall next to the End portal frame. The player steps out (2:10.9, "Eye Spy"), places 2 netherrack (5 → 3) to step across, and looks straight down into the active portal (2:12.4).
- **Q3.2 Actions:** step out, place 2 blocks, drop into the portal. No digging, no walking through the stronghold.
- **Q3.3 Eyes placed:** none. All 12 frames are already filled and the portal is active.

## Segment 4: End (59.233 s IGT, pause excluded)

- **Q4.1 First bed:** placed by about 2:59. That is 2:59 − 2:25.0 resume + 7.7 s before the pause, so **about 41.7 s IGT after arriving in the End**. Before that the pro walks to the fountain with a bed in hand (2:52–2:55).
- **Q4.2 Strategy:** **one-cycle**: beds on the dragon while it is perched on the fountain.
- **Q4.3 Perches:** **1**.
- **Q4.4 Beds used:** **6 of 6** (the hotbar loses one bed per second or two from 2:59 to 3:07), with 0 left over.
- **Q4.5 Cover / damage:** stands against the bedrock fountain and takes blast damage (health about 10 → about 5 hearts). No death.
- **Q4.6 Dragon death and finish:** death beams at about 3:10. Black screen at the exit portal at 3:16.5.

## General

- **Q5.1 Timer on screen:** none.
- **Q5.2 Cuts:** no cuts inside the run (0:22–3:16.5). The video opens with the end of an earlier attempt (0:00–0:06) and world creation.
