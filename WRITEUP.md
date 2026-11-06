# SplitCheck: is an AI agent as efficient as a pro Minecraft speedrunner?

**Headline.** On the same set seed, the published LLM agent (Astra + JEV) finishes in 516.7 s on its banner. That is **4.8× slower than the 1:48 pro run** (IGT 108.421 s; 4.3× against its RTA of 119.331 s) and **3.1× slower than a 2:49 pro run**. Most segments are a steady 2.7–2.9× slower. One segment is an outlier: getting from the Nether exit to the End portal takes the agent **51.6–56.7 s against the pro's 2.45 s (21–23×)**. The agent's Nether exit portal was placed 3 Nether blocks off the ideal ÷8 point, so it came out in the overworld 21 blocks from the End portal. That is a missed shortcut in the route its authors supplied.

## Exigence

- **Agents can now finish Minecraft, but finishing says little.** Four Gemini 4 agents beat it in 27 h 14 min with 605 deaths on Easy ([Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/google-deepmind-claims-four-gemini-4-agents-beat-minecraft-in-27-hours-by-writing-2-783-programs-of-their-own-the-ai-team-died-605-times-on-easy-difficulty-and-ran-up-an-estimated-usd520-in-tokens)). That is a different category from the 6:39.813 random-seed record ([speedrun.com](https://www.speedrun.com/mc/runs/y44238ky)), so it is context only.
- **The fair comparison is the same seed.** [rmalde/minecraft-agent](https://github.com/rmalde/minecraft-agent) published an LLM agent run on seed `8398967436125155523` (Java 1.16.5). Two verified pro runs exist on that same seed. That allows segment-by-segment comparison against human experts, which is what tells you where an agent wastes time.

## What we built

- **Same-seed baselines** (`baseline/`):
  - Rayoh's **1:48.421 IGT** run ([speedrun.com zqe4g39z](https://www.speedrun.com/mc/runs/zqe4g39z), 1.16.5, Easy, set seed) is the headline. Its segments come from a human timing sheet (`baseline/timing_sheet_1m48.md` → `make_splits.py`), plus a playbook of the pro's actions (`baseline/pro_1m48_playbook.md`).
  - dumbo0116's **2:49.149 IGT** run ([speedrun.com yoex3d0z](https://www.speedrun.com/mc/runs/yoex3d0z), official 2:54.545 RTA) is the backup. Its segments come from the runner's own run comment.
- **Agent timeline** (`agent_runs/published_montage/timeline.json`): the agent's milestones read off the banner of its published montage (true elapsed time, XYZ, planner objective). The montage has cuts, so every milestone is a **[low, high] bracket**.
- **The check** (`baseline/rules.json`; Person A's checker in `code/`; B's reference implementation in `baseline/reference_check.py`):
  - Four segments with the same boundaries for every run: Nether in, Nether out, End in, finish.
  - For each segment: agent seconds (bracketed), pro seconds, ratio, a verdict, and waste entries `{tag, seconds, evidence}`.
- **Diagnosis** (`analysis/agent_vs_pro.md`): per segment, *where* time is lost, *why* (agent evidence from banner frames and the agent repo; pro evidence from the playbook), and *what it missed* (waste tag). Every "why" is labelled **confirmed** or **inferred**.
- **Checker tests** (`fixtures/`, expected outputs included):
  - the pro run fed in as an agent: all OK
  - +50 s on exit → End: only that segment FLAGs, tagged `missed_shortcut`
  - the same total with 50 s moved into the Nether: only the Nether FLAGs
  - 2 extra beds: `extra_items` in segment 1
  - the real montage

## How it checks

1. **Brackets.** Agent segment low = next milestone's earliest time − previous milestone's latest time; high is the reverse. Verdicts use the side most favourable to the agent.
2. **Verdict per segment.**
   - **FLAG:** ratio > 2 × the run's own median ratio *and* at least 5 s over the pro.
   - **SLOW:** ratio > 1.25.
   - **OK:** otherwise.
   - A uniformly slower player comes out SLOW everywhere. FLAG marks the segment where time is lost out of proportion, which is where a missed technique shows. Raw ratios are always reported.
3. **Waste tags with evidence:** `missed_shortcut` (for example, the exit portal arrives more than 8 blocks from the End portal), `extra_items` (beds collected minus beds used, compared with the pro), `idle_wait` (model latency, reported on its own line), `longer_path`, `failed_or_retried_action`, `unnecessary_risk`, `wrong_order`.

## What we found

Against the 2:49 backup (from `fixtures/published_montage.json`). The 1:48 columns fill in from `baseline/pro_1m48_segments.json` once the timing sheet is done.

| Segment | Agent s | Pro s (2:49) | Ratio | Verdict | Pro s (1:48) | Ratio (1:48) |
|---|---|---|---|---|---|---|
| spawn → Nether | 184.7–189.45 | 66.683 | 2.77–2.84× | SLOW | TODO(human) | TODO |
| Nether | 108.7–118.1 | 40.783 | 2.67–2.90× | SLOW | TODO(human) | TODO |
| **exit portal → End portal** | **51.55–56.7** | **2.45** | **21.0–23.1×** | **FLAG** | TODO(human) | TODO |
| End | 161.35–162.35 | 59.233 | 2.72–2.74× | SLOW | TODO(human) | TODO |
| **Total** | **516.2–516.7** | 169.149 | **3.05×** | | **108.421** | **4.76× IGT / 4.33× RTA** |

**Biggest losses and misses:**

1. **`missed_shortcut`, the exit-portal placement (confirmed).**
   - The route's Nether exit is (−141, 40, 104). The ideal is (−1130/8, 856/8) = (−141.25, 107).
   - The game created the overworld portal at y 24–26, z 837 (agent repo `exit-link.json`). The agent came out at (−1129.5, 24, 837.5): 18.5 blocks horizontally and 10 blocks below the End portal.
   - It then digs and walks for about 52 s. The pro's exit lands next to the portal (2.45 s).
   - Up to 49–54 s is lost here. That is an upper bound: some of it is slow execution, not placement.
2. **`extra_items`, beds (agent side confirmed; comparison pending).** The agent collects 8 beds (montage "4th of 8 beds"; route kit of 8), and the bed phase spans about 120 s of the banner (00:14.7 to 02:15.25; frames in between are cut). The dragon died to 6. If the pro takes 6, about 8–30 s is wasted.
3. **Steady slowdown elsewhere (inferred).** The Nether route is only 12 % longer than a straight line, so `longer_path` is mostly rejected. The loss is in digging, descending and building. The End is mostly a 150 s wait for the first perch, followed by a one-cycle with six beds (agent README). Perch timing is partly random.
4. **`idle_wait`.** The run made 131 JEV decisions and 35 Astra calls, but its latency total is not published. An earlier run logged 50 s of API time, which can overlap game actions.

Full evidence, labelled confirmed or inferred: `analysis/agent_vs_pro.md`.

## Ground truth and fairness

- **Every number has a source:** a speedrun.com API record, the runner's own comment, an agent-repo file and line, a montage banner timestamp, or the minecraft.wiki. See `SOURCES.md`. Open items are in `UNVERIFIED.md`.
- **Adjustments, stated rather than hidden:**
  - The agent ran on Peaceful and the pros on Easy, which only helps the agent.
  - The agent's banner is a wall clock that includes model latency. It is compared with both pro IGT and pro RTA.
  - Pros practise set seeds. The agent run is its authors' best published run after many development runs, so neither side is a first attempt.
  - Montage cuts are handled as brackets, and verdicts use the side most favourable to the agent.
  - The agent's route was supplied by its authors (`README.md:104`), so `missed_shortcut` is attributed to the agent *system*.
  - The banner says 8:36.7 and the README says 8:43.300. We use the banner, which favours the agent.
- **Pro variance:** the two pro runs differ by 1.56× in total. That is why the 1.25 "OK" margin is small, and why both baselines are shown.

## Limitations

- **Coverage.** The montage shows about 39 s of a roughly 517 s run (about 7.5 %). Anything inside a cut is diagnosed only from timing and from the agent repo's notes, and those notes describe earlier runs of the same harness.
- **The 1:48 segment times need a human with the video** (5 boundaries, about 5 minutes). The playbook needs about 10 more minutes. Until then, per-segment ratios use the 2:49 run.
- **One seed, one agent run.** We report what it shows, not a general rate.
- **No event log** for the published run, so `failed_or_retried_action` and `longer_path` can't be measured inside cuts.

## Supplementary: decision tasks

- **7 seed decision tasks** (`tasks/`, `reference/`): single decisions on the same seed, each with a sourced answer, alternates that must pass and broken answers that must fail. Examples: where to build the Nether exit (T12), how much obsidian the ruined frame needs (T05: 7), whether blaze rods are needed (T10: 0). AI results: TODO(C), if C ran them.
- **14 generic decision tasks** (`extras/generic_tasks/`): **supplementary, not part of the headline result.** They cover the random-seed splits this seed skips (bastion barter tables for 1.16.1 vs 1.16.5, rod counts, triangulation, eye-break odds, the dragon method).
