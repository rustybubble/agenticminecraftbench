# SplitCheck plan addendum (v2 changes on top of the team plan)

Optimizes "Mercor Minecraft speedrun benchmark plan (1).md" using what we learned this morning: probe results, the Codex and Grok spec reviews, and SpeedrunBench. Base plan: "Mercor Minecraft speedrun benchmark plan" + SCHEMA.md. This file only lists changes and Layer B.

## What changed and why (read this first)

| # | Change | Why |
|---|---|---|
| 1 | **Pick one version. Use the seed's version (1.16.5, set seed), not "RSG 1.16.1".** | All ground truth (survey JSONs, the human 2:54.545 run, the agent) is set-seed **1.16.5**. Version 1.16.2 changed Nether portal search (128 → 16 blocks on the Nether side) and piglin barter weights. Mixing versions makes answers wrong. Frame it as "Set Seed Glitchless" and verify the category/version of speedrun.com run `yoex3d0z`. |
| 2 | **Gate on "does the AI actually fail?" at 12:30.** | This morning frontier models aced every clean, well-specified puzzle: gear chains 10/10 for both Claude and GPT, drawing reading 7/8. Speedrun meta (8:1 Nether, 6 rods, bed one-cycle) is all over pretraining data, so a chatbot will probably answer "bucket portal" correctly. The plan's "typical AI miss" column describes *live agents*, not chatbots. Run 5 draft tasks on the chosen model before writing 20. |
| 3 | **Shift tasks from "name the technique" to "compute this seed's exact state".** | Answers that look right but are wrong come from version-exact computation plus state tracking (portal-link coordinates under 1.16.5 rules, obsidian count given chest contents and pre-placed frame blocks, eyes needed given pre-filled frames and the break rate), not from trivia. |
| 4 | **Add Layer B: a deterministic event-log evaluator.** | This is what you asked for: evaluate *gameplay* from game events plus seed features. Information fairness is solved because the agent's knowledge = the coordinates in its config (disclosed), so every rule uses only disclosed information. |
| 5 | **Time costs carry source tags. No "pro-optimal" claim.** | Both reviewers rejected invented optimums. Report "Δ seconds vs the cited same-seed human split", tag every cost `vod` / `wiki` / `estimate`, and show the conclusion survives ±30% on the estimated costs. |
| 6 | **Cut split 0 (reset decision).** | Expert reset labels are judgment calls. Correctness and fairness are 25 points and the tie-breaker, so a disputed label costs more than it earns. |
| 7 | **Evidence comes from the server, not the client**. | A client log is a claim. Agent filenames and summaries are claims (SpeedrunBench's rule). |
| 8 | **Checker tests stay separate from AI results.** | Reference + alternate (must PASS) and broken (must FAIL) answers prove the checker works. They never count as AI results. |
| 9 | **Label the 245× number as cross-category context.** | Gemini's run (random seed, Easy, 27 h) and the RSG world record are different categories. The **same-seed 3.0×** (8:43.300 vs 2:54.545) is the apples-to-apples number, so lead with it. |

---

## Layer A: split-decision tasks (the guaranteed submission)

Same pipeline as the original plan: `tasks/*.json` → `run_ai.py` (one model, fresh conversation, first answer kept; logs model, date, exact prompt and raw response) → `check.py` (legality simulator + seed-exact numeric checks + technique tags) → `results.csv`.

Tasks are on seed `8398967436125155523`, built from the `rmalde/minecraft-agent` survey JSONs. Example tasks where an answer can be confidently wrong:

| Task | The exact answer requires | Checker |
|---|---|---|
| Exit portal for the End portal at overworld (−1130, 34, 856) | 1.16.5 linking: X/Z ÷ 8, Y not scaled, the Nether-side search radius, existing portals nearby | tolerance from the linking rules; compared with the agent's real exit (−141, 40, 104) |
| Obsidian for the portal | chest contents (21 obsidian) + pre-existing frame blocks; whether a diamond pickaxe is needed | exact count |
| Do you need blaze rods? | **No.** The End portal on this seed is naturally active | boolean + reason |
| Eyes needed | frames pre-filled on *this* portal (from the survey) + the 20% break risk for eyes thrown en route | exact + an explicit buffer rule |
| Legal 10-step plan from a given inventory | the state simulator: no eyes without powder, no portal without fire, etc. | legality + time Δ (source-tagged) |
| Triangulation from two given throws (positions + F3 angles) | intersection with tolerance from the ray geometry; check it's in ring 1 | blocks of error |

**12:30 gate:** run 5 of these on the model. If the AI passes all 5, harden them (more state, version traps, longer plans) before writing more. **If it still aces them by 1:15, Layer B becomes the headline** and Layer A is the "chatbots know the meta" finding. That's an honest result and still scoreable.

## Layer B: deterministic gameplay evaluator (what you asked for)

**Input:** any run's `events.jsonl` (the rmalde agent's format: timestamped decision/result/planner events) **plus server-side position/inventory telemetry** **plus seed features** (survey JSONs = what the agent was told).

**Deterministic outputs (no LLM judging anything):**
1. **Split extraction:** timestamps of dimension changes, portal entry/exit, End entry, dragon death. Compared with the same-seed human splits from the 2:54.545 VOD (source-tagged).
2. **Waste detectors.** All are pure functions of the logs:
   * **Detours:** items acquired and never consumed or used by the end of the run (e.g. extra food or tools on Peaceful).
   * **Undo:** a block placed then broken within N seconds when its use was already done (e.g. crafting tables).
   * **Lost drops:** a block was mined but no matching inventory delta followed.
   * **Overshoot:** still moving toward a waypoint after it was reached (distance increases after a minimum ≤ r).
   * **Idle:** time with no position change and no action. Waits and failed actions are counted from the events.
   * **Deaths**, with cause and position.
3. **Disclosed-target travel:** for each move toward a *disclosed* coordinate, path length ÷ straight-line distance (route tortuosity). Reported only, never turned into a "fair optimum".
4. **Claims vs evidence:** the agent's planner summaries ("reached portal", "have 12 eyes") are checked against server inventory and position. A false claim is the headline catch.

**Data sources, in priority order:**
1. **A trusted human run on the same seed through our server logger.** Your team plays it, so it's guaranteed and doubles as the reference.
2. **One live agent run** (Person C, go/no-go at 12:45, as in the original plan).
3. **Synthetic broken logs:** inject a detour, an undo, a false claim and a death. They must be caught (checker tests).

Even if the live agent never runs, Layer B ships as a validated evaluator: run on the human log plus synthetic broken logs, with the agent's documented misses (`NOTES.md`, `REVIEW.md`) mapped to the detector that would catch each one.

---

## Roles and timeline (3 people, changes in **bold**)

| Time | A: checker engineer | B: speedrun expert | C: server + live agent → runner |
|---|---|---|---|
| 11:30–12:30 | simulator + action schema; **seed-exact numeric checks** | **5 draft tasks first** (seed-exact, with sources), then more | 1.16.5 server on the seed + **server-side logger**; live-agent setup |
| **12:30** | **AI-failure gate:** run the 5 drafts on the model (fresh chat each). Do they fail? | adjust task style based on the gate | — |
| 12:30–1:45 | **Layer B detectors + split extractor**; source-tagged time-cost table | tasks to ~15; alternate + broken answers; **VOD splits with timestamps** | **12:45 go/no-go.** Go = one live run. No-go = **play the human reference run through the logger** + `run_ai.py` |
| 1:45–2:15 | checker tests: reference/alternate PASS, broken FAIL, synthetic logs caught | fact-check all `[verify]` items | results table |
| **2:15** | **freeze: run the AI once on every Layer A task** | — | — |
| 2:15–3:40 | Layer B on the human run + live run (if any); fix bugs only | write-up | demo: one task → AI answer → catch; one log → detected detour or false claim |
| 3:40–4:00 | zip + submit | | |

## Fact-check list (blocking before 3:15)
- The version and category of the 2:54.545 run (and that 1.16.5 is what the seed data uses).
- 1.16.5 piglin barter table (pearl weight and count) and portal-linking search radii.
- The WR 6:39.813 (category and version) for the context line.
- Eye break 20% and End portal frame 10% per frame (both widely documented; cite the wiki).
- The ring 1 range of 1,280–2,816 blocks (Nether 160–352).
