# Timing sheet: Rayoh 1:48 set-seed run (for a human with the video)

> **Optional.** The per-segment baseline is the 2:49 run (`baseline/pro_2m49_segments.json`). Fill this only if there is time; the 1:48 run is otherwise used for its total only.

- Video: https://www.youtube.com/watch?v=2NEvhsZG5iY ("[FWR] Minecraft in 1:48 (Set Seed Speedrun)", 2:08 long, edited)
- speedrun.com: https://www.speedrun.com/mc/runs/zqe4g39z: **IGT 1:48.421, RTA 1:59.331**, Any% Glitchless, Set Seed, Java 1.16.5, Easy, verified 2023-01-25.
- Raw stream VOD, if the edited video cuts anything: https://youtu.be/F1VOO0eHiys (2:08:14 long; the run is somewhere inside it).

**How to fill it (about 5 minutes):** play at 0.25× speed around each boundary. For each row, write the video timestamp of the first frame that shows the cue. If an in-game timer is on screen (SpeedRunIGT, usually top-right), also write what it reads at that frame. Leave a cell empty if you can't see it, and never guess. Then run `python baseline/make_splits.py` to write `baseline/pro_1m48_segments.json`.

| milestone | visual cue (first frame showing it) | video timestamp (m:ss.s) | on-screen IGT timer (m:ss.sss) | notes |
|---|---|---|---|---|
| M_start | timer starts / first frame of gameplay in the new world | | | |
| M_portal_in | Nether loading screen or first Nether frame (red fog, netherrack) after the first portal | | | |
| M_portal_out | first overworld frame after the second portal (sky or stronghold stone bricks) | | | |
| M_end_in | first End frame (black sky, end stone, obsidian platform) | | | |
| M_finish | timer stops / credits start / exit-portal entry | | | |

Optional, if easy to see:

| milestone | visual cue | video timestamp | on-screen IGT timer | notes |
|---|---|---|---|---|
| M_first_chest | first chest GUI opened | | | |
| M_beds_done | last bed picked up | | | |
| M_first_bed_end | first bed placed in the End | | | |
| M_dragon_dead | dragon death animation starts | | | |
