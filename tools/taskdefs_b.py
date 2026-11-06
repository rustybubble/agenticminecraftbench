"""Tasks for splits blind_travel, triangulation, portal_room, dragon, full_route (T12-T21). Owner: B."""
import json

import compute_answers as ca
from taskdefs_common import *  # noqa: F401,F403

ex = ca.seed_nether_exit()
bl = ca.blind_generic()
tri = ca.triangulation()
eb = ca.eye_breaks(3)

TASKS = []

# ---------------------------------------------------------------- blind_travel
TASKS.append({
    "id": "T12_blind_seed_nether_exit",
    "split": "blind_travel", "version": "1.16.5", "seed": SEED, "difficulty": "easy",
    "situation": "You have just come through your first Nether portal and are standing in the Nether at (-47.5, 77, 24.5). "
                 "The stronghold's End portal on this seed is already active, at overworld (-1130, 34, 856). "
                 "You carry 14 obsidian and a flint and steel, and you plan to build a second Nether portal somewhere in the Nether and go back to the overworld through it.",
    "question": "At which Nether coordinates should you build that portal so that you come out in the overworld as close as possible to the End portal? "
                "Give Nether-dimension coordinates.",
    "state": {"dimension": "the_nether", "position": {"x": -47.5, "y": 77, "z": 24.5},
              "inventory": {"obsidian": 14, "flint_and_steel": 1, "iron_pickaxe": 1},
              "known_locations": {"nether_arrival": nth(-47.5, 77, 24.5), "stronghold_end_portal": ow(-1130, 34, 856)},
              "world": {"facts": ["The End portal at overworld (-1130, 34, 856) is already active.", "No other portals exist near the stronghold."]},
              "elapsed_s": 67},
    "answer_type": "coordinates",
    "answer_schema": '{"x": <number>, "y": <number>, "z": <number>, "dimension": "the_nether"}',
    "reference": {
        "answer": {"x": ex["ideal_nether_xz"][0], "y": 34, "z": ex["ideal_nether_xz"][1], "dimension": "the_nether"},
        "tolerance": {"blocks": 2},
        "pro_time_s": None,
        "why": "Nether X and Z are overworld X and Z divided by 8; Y is not scaled. (-1130, 856) / 8 = (-141.25, 107). "
               "Going back, the game converts the portal position x8 and, with no portal nearby, creates the overworld portal at the closest valid spot within 16 blocks horizontally. "
               "So each Nether block of error moves the arrival 8 overworld blocks; 2 Nether blocks of tolerance keeps the arrival within about 16 blocks of the End portal. "
               "The human 2:54.545 run on this seed took 2.450 s from leaving its second portal to entering the End portal, which needs an arrival this close. "
               "The agent built at (-141, 40, 104), 3.0 Nether blocks off, and arrived about 24 overworld blocks from the portal. Y is not scored (building near y 34 helps the arrival land at portal-room depth, but that is not verified).",
        "trap": "(-1130, 856) in the Nether (forgot to divide by 8), (-9040, 6848) (multiplied instead of divided), or scaling Y (34 / 8 = 4.25).",
        "techniques": [
            {"tag": "nether_travel_8to1", "description": "Travel in the Nether; divide overworld X/Z by 8.", "est_time_saved_s": None, "verified": True,
             "source": W + "Nether_Portal (raw lines 61, 70)"},
            {"tag": "precise_portal_link", "description": "Build the exit portal at the exact /8 point so the overworld portal generates next to the target.", "est_time_saved_s": None, "verified": True,
             "source": W + "Nether_Portal (raw line 88: new portal within 16 blocks horizontally); " + HUMAN_RUN_API + " (2.450 s exit to End portal)"},
        ],
        "miss_category": "no_nether_shortcut",
        "sources": [W + "Nether_Portal", CFG + ":34-39,52-56", AGENT + ":optimization/nether/entry-link.json (Nether arrival -47.5, 77, 24.5)",
                    HUMAN_RUN_API, "tools/compute_answers.py seed_nether_exit()"],
        "verified": True,
        "alternates": [{"answer": {"x": -141, "y": 40, "z": 107, "dimension": "the_nether"}, "why_valid": "Rounded to whole blocks; 0.25 off."},
                       {"answer": {"x": -142, "y": 34, "z": 106, "dimension": "the_nether"}, "why_valid": "1.25 blocks off; arrival within about 10 overworld blocks."}],
        "broken": [
            {"answer": {"x": -1130, "y": 34, "z": 856, "dimension": "the_nether"}, "expected_verdict": "WRONG", "why_wrong": "No scaling: links about 8,000 overworld blocks away."},
            {"answer": {"x": -9040, "y": 34, "z": 6848, "dimension": "the_nether"}, "expected_verdict": "WRONG", "why_wrong": "Multiplied by 8."},
            {"answer": {"x": -141.25, "y": 34, "z": 107, "dimension": "overworld"}, "expected_verdict": "WRONG", "why_wrong": "Wrong dimension."},
            {"answer": {"x": -150, "y": 34, "z": 100, "dimension": "the_nether"}, "expected_verdict": "WRONG", "why_wrong": "11 Nether blocks off: arrives about 90 overworld blocks away."},
        ],
    },
})

BLIND_OPTS = {
    "A": "Walk and sprint in the overworld straight to (1800, -900).",
    "B": "Go through your portal, travel in the Nether to about (225, -112), build a portal there and exit to the overworld.",
    "C": "Go through your portal, travel in the Nether to about (1800, -900), build a portal there and exit to the overworld.",
    "D": "Go through your portal, travel in the Nether to about (14400, -7200), build a portal there and exit to the overworld.",
}
TASKS.append({
    "id": "T13_blind_generic_route",
    "split": "blind_travel", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You are in the overworld at (40, 70, -60), standing next to your lit Nether portal. From eye throws you estimate the stronghold is at about overworld (1800, ~, -900). "
                 "You carry 12 obsidian, a flint and steel, 12 eyes of ender and blocks. Terrain in both dimensions is ordinary.",
    "question": "Which way gets you to the stronghold fastest?\n" + "\n".join("{}: {}".format(k, v) for k, v in BLIND_OPTS.items()),
    "state": {"dimension": "overworld", "position": {"x": 40, "y": 70, "z": -60},
              "inventory": {"obsidian": 12, "flint_and_steel": 1, "ender_eye": 12, "cobblestone": 64},
              "known_locations": {"my_portal": ow(40, 70, -60), "stronghold_estimate": ow(1800, 40, -900)},
              "world": {"facts": ["Nether portal at your position is lit and links to the Nether near (5, ~, -7.5)."]},
              "elapsed_s": None},
    "answer_type": "choice", "options": list(BLIND_OPTS),
    "answer_schema": '{"choice": "A" | "B" | "C" | "D"}',
    "reference": {
        "answer": {"choice": "B"},
        "tolerance": {"choices": ["B"]},
        "pro_time_s": None,
        "why": "The overworld trip is {} blocks. In the Nether the same trip is {} blocks, because X and Z are divided by 8: the target is (1800/8, -900/8) = (225, -112.5). "
               "At sprint speed (5.6 blocks/s) that is roughly 350 s versus 45 s, and the extra portal costs far less than the 300 s saved.".format(bl["overworld_distance"], bl["nether_distance"]),
        "trap": "A ignores the Nether shortcut. C forgets to divide by 8 and ends up 8x too far. D multiplies instead of dividing.",
        "techniques": [{"tag": "nether_travel_8to1", "description": "Travel long distances in the Nether.", "est_time_saved_s": None, "verified": True, "source": W + "Nether_Portal (raw line 61)"}],
        "miss_category": "no_nether_shortcut",
        "sources": [W + "Nether_Portal", W + "Sprinting (raw line 33: 5.612 m/s)", "tools/compute_answers.py blind_generic()"],
        "verified": True,
        "alternates": [{"answer": {"choice": "B", "reasoning": "8x shorter in the Nether."}, "why_valid": "Same choice."}],
        "broken": [{"answer": {"choice": "A"}, "expected_verdict": "WRONG", "why_wrong": "8x longer trip."},
                   {"answer": {"choice": "C"}, "expected_verdict": "WRONG", "why_wrong": "No scaling."},
                   {"answer": {"choice": "D"}, "expected_verdict": "WRONG", "why_wrong": "Scaled the wrong way."}],
    },
})

# ---------------------------------------------------------------- triangulation
t1, t2 = tri["throw1"], tri["throw2"]
TRI_SITUATION = (
    "You are in the overworld after leaving the Nether. You threw two eyes of ender. For each throw you put your crosshair on the flying eye and read your "
    "yaw from the F3 screen's Facing line. Throw 1: standing at ({x1}, 70, {z1}), F3 shows Facing: north (Towards negative Z), yaw {y1}. "
    "Throw 2: standing at ({x2}, 70, {z2}), F3 shows Facing: north (Towards negative Z), yaw {y2}. Both eyes survived and you picked them up. "
    "Assume both eyes fly exactly toward the same point."
).format(x1=t1["x"], z1=t1["z"], y1=t1["yaw"], x2=t2["x"], z2=t2["z"], y2=t2["yaw"])
TRI_STATE = {"dimension": "overworld", "position": {"x": t2["x"], "y": 70, "z": t2["z"]}, "inventory": {"ender_eye": 12, "obsidian": 10, "flint_and_steel": 1},
             "known_locations": {"throw_1": ow(t1["x"], 70, t1["z"]), "throw_2": ow(t2["x"], 70, t2["z"])},
             "world": {"facts": ["Throw 1 yaw {}".format(t1["yaw"]), "Throw 2 yaw {}".format(t2["yaw"])]}, "elapsed_s": None}
TRI_SOURCES = [W + "Rotation (raw line 16: yaw -180 north, -90 east, 0 south, 90 west)", W + "Debug_screen (Facing line)",
               W + "Tutorial:Defeating_the_ender_dragon (Triangulation section, raw lines 117-124; eyes point to the staircase chunk's NW corner, raw line 133)",
               W + "Stronghold (raw line 30: first ring 1,280-2,816)", "tools/compute_answers.py triangulation()"]

io = tri["intersection_overworld"]
TASKS.append({
    "id": "T14_triangulation_overworld",
    "split": "triangulation", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": TRI_SITUATION,
    "question": "What overworld X and Z do the eyes point to?",
    "state": TRI_STATE,
    "answer_type": "coordinates",
    "answer_schema": '{"x": <number>, "z": <number>, "dimension": "overworld"}',
    "reference": {
        "answer": {"x": io["x"], "z": io["z"], "dimension": "overworld"},
        "tolerance": {"blocks": 16},
        "pro_time_s": None,
        "why": "Minecraft yaw a means direction (dx, dz) = (-sin a, cos a): -145.0 points north-east. Intersect the two lines "
               "(x1 - t sin a1, z1 + t cos a1) and (x2 - s sin a2, z2 + s cos a2). The intersection is ({}, {}), {} blocks from throw 1 and {} blocks from (0, 0), inside the first ring "
               "(1,280-2,816), so it is plausible. Reading each yaw to 0.1 degrees moves the answer by at most {} blocks; 16 blocks (one chunk) is the tolerance.".format(
                   io["x"], io["z"], tri["distance_from_throw1"], tri["distance_from_origin"], tri["worst_case_error_blocks_for_0.05deg"]),
        "trap": "Using yaw as a math angle from +X ({}, {}), mixing up the sign so the point is south-west, or skipping the math and following eyes one throw at a time.".format(
            tri["trap_math_angle_convention"]["x"], tri["trap_math_angle_convention"]["z"]),
        "techniques": [{"tag": "triangulation", "description": "Intersect two eye throws instead of following eyes.", "est_time_saved_s": None, "verified": True,
                        "source": W + "Tutorial:Defeating_the_ender_dragon (Triangulation)"}],
        "miss_category": "ignores_information",
        "sources": TRI_SOURCES,
        "verified": True,
        "alternates": [{"answer": {"x": tri["staircase_center_4_4"]["x"], "z": tri["staircase_center_4_4"]["z"], "dimension": "overworld"},
                        "why_valid": "Answers with the staircase position (chunk offset 4, 4), which is where a runner digs; 5.7 blocks from the intersection."},
                       {"answer": {"x": 1500, "z": -2120, "dimension": "overworld"}, "why_valid": "Rounded; 8.6 blocks off."}],
        "broken": [{"answer": {"x": tri["trap_math_angle_convention"]["x"], "z": tri["trap_math_angle_convention"]["z"], "dimension": "overworld"},
                    "expected_verdict": "WRONG", "why_wrong": "Math-angle convention instead of Minecraft yaw."},
                   {"answer": {"x": -1504, "z": 2112, "dimension": "overworld"}, "expected_verdict": "WRONG", "why_wrong": "Sign flipped."},
                   {"answer": {"x": tri["intersection_nether"]["x"], "z": tri["intersection_nether"]["z"], "dimension": "overworld"},
                    "expected_verdict": "WRONG", "why_wrong": "Divided by 8 but labelled overworld."}],
    },
})

inn = tri["intersection_nether"]
TASKS.append({
    "id": "T15_triangulation_nether_target",
    "split": "triangulation", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": TRI_SITUATION + " You decide to go back into the Nether and travel there, then build a portal and come out next to the stronghold.",
    "question": "At what Nether X and Z should you build the portal that takes you out next to the stronghold the eyes point to?",
    "state": TRI_STATE,
    "answer_type": "coordinates",
    "answer_schema": '{"x": <number>, "z": <number>, "dimension": "the_nether"}',
    "reference": {
        "answer": {"x": inn["x"], "z": inn["z"], "dimension": "the_nether"},
        "tolerance": {"blocks": 2},
        "pro_time_s": None,
        "why": "First triangulate: the eyes point to overworld ({}, {}) (see T14). Then divide X and Z by 8: ({}, {}). 2 Nether blocks = 16 overworld blocks of tolerance.".format(io["x"], io["z"], inn["x"], inn["z"]),
        "trap": "Giving the overworld coordinates in the Nether (8x too far), or dividing a throw position by 8 instead of the intersection.",
        "techniques": [{"tag": "triangulation", "description": "Intersect two throws.", "est_time_saved_s": None, "verified": True, "source": W + "Tutorial:Defeating_the_ender_dragon"},
                       {"tag": "nether_travel_8to1", "description": "Divide by 8 for the Nether.", "est_time_saved_s": None, "verified": True, "source": W + "Nether_Portal (raw line 61)"}],
        "miss_category": "no_nether_shortcut",
        "sources": TRI_SOURCES + [W + "Nether_Portal"],
        "verified": True,
        "alternates": [{"answer": {"x": 188, "z": -264, "dimension": "the_nether"}, "why_valid": "Rounded."}],
        "broken": [{"answer": {"x": io["x"], "z": io["z"], "dimension": "the_nether"}, "expected_verdict": "WRONG", "why_wrong": "Not divided by 8."},
                   {"answer": {"x": round(t1["x"] / 8, 1), "z": round(t1["z"] / 8, 1), "dimension": "the_nether"}, "expected_verdict": "WRONG", "why_wrong": "Divides throw 1's position, not the target."},
                   {"answer": {"x": inn["x"], "z": inn["z"], "dimension": "overworld"}, "expected_verdict": "WRONG", "why_wrong": "Wrong dimension."}],
    },
})

# ---------------------------------------------------------------- portal_room
FRAMES_TWO = []
for i, f in enumerate(FRAMES_ALL_FILLED):
    FRAMES_TWO.append({"x": f["x"] + 1130 + 70, "y": 30, "z": f["z"] - 856 - 644, "eye": i in (2, 9)})
TASKS.append({
    "id": "T16_portal_room_eyes",
    "split": "portal_room", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You have reached the End portal room. You hold 9 eyes of ender. Looking at the frame, you record each of the 12 End portal frame blocks and whether it already has an eye; "
                 "the list is in \"world.facts\".",
    "question": "(1) How many eyes must you place to activate the portal? (2) How many more eyes than you hold would you need (0 if you have enough)?",
    "state": {"dimension": "overworld", "position": {"x": 70, "y": 30, "z": -644}, "inventory": {"ender_eye": 9},
              "known_locations": {"portal_room": ow(70, 30, -644)},
              "world": {"facts": ["Frames (x, y, z, eye): " + json.dumps(FRAMES_TWO)]}, "elapsed_s": None},
    "answer_type": "number",
    "answer_schema": '{"eyes_to_place": <int>, "eyes_short": <int>}',
    "reference": {
        "answer": {"eyes_to_place": 10, "eyes_short": 1},
        "tolerance": {"abs": 0},
        "pro_time_s": None,
        "why": "Two of the 12 frames already hold an eye (each frame has a 10% chance to generate with one). Only the 10 empty frames need eyes. You hold 9, so you are 1 short.",
        "trap": "12 to place and 3 short: ignores the pre-filled frames.",
        "techniques": [{"tag": "count_prefilled_frames", "description": "Count eyes already in the frame.", "est_time_saved_s": None, "verified": True,
                        "source": W + "End_Portal_Frame (raw lines 16, 117-119)"}],
        "miss_category": "resource_miscount",
        "sources": [W + "End_Portal_Frame"],
        "verified": True,
        "alternates": [{"answer": {"eyes_to_place": 10, "eyes_short": 1, "reasoning": "two pre-filled"}, "why_valid": "Same numbers."}],
        "broken": [{"answer": {"eyes_to_place": 12, "eyes_short": 3}, "expected_verdict": "WRONG", "why_wrong": "Ignores pre-filled frames."},
                   {"answer": {"eyes_to_place": 10, "eyes_short": 0}, "expected_verdict": "WRONG", "why_wrong": "Miscounts the shortfall."}],
    },
})

TASKS.append({
    "id": "T17_portal_room_throw_losses",
    "split": "portal_room", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You hold exactly 12 eyes of ender. Before you reach the portal room you will throw eyes 3 more times (one eye per throw) to locate the stronghold, and pick up every eye that survives.",
    "question": "(1) What is the expected number of eyes you lose over the 3 throws? (2) What is the probability that none of the 3 thrown eyes breaks? Give decimals.",
    "state": {"dimension": "overworld", "position": None, "inventory": {"ender_eye": 12}, "known_locations": {}, "world": {}, "elapsed_s": None},
    "answer_type": "number",
    "answer_schema": '{"expected_eyes_lost": <number>, "p_no_eye_lost": <number>}',
    "reference": {
        "answer": {"expected_eyes_lost": eb["expected_eyes_lost"], "p_no_eye_lost": eb["p_no_eye_lost"]},
        "tolerance": {"abs": 0.02},
        "pro_time_s": None,
        "why": "Each throw breaks the eye with probability 0.2, independently. Expected loss = 3 x 0.2 = 0.6. P(no break) = 0.8^3 = 0.512. "
               "So about half the time you arrive with fewer than 12 eyes, which matters if the portal has no pre-filled frames.",
        "trap": "0.488 for (2): that is the chance at least one breaks. The wiki's own sentence mixes these up ('approximately a 50% overall chance to shatter ... 0.8^3 = 51.2%').",
        "techniques": [{"tag": "eye_break_buffer", "description": "Carry spare eyes for the 20% break rate.", "est_time_saved_s": None, "verified": True,
                        "source": W + "Eye_of_Ender (raw line 32)"}],
        "miss_category": "resource_miscount",
        "sources": [W + "Eye_of_Ender (raw line 32: 20% shatter, 80% survive per throw)", "tools/compute_answers.py eye_breaks()"],
        "verified": True,
        "alternates": [{"answer": {"expected_eyes_lost": 0.6, "p_no_eye_lost": 0.51}, "why_valid": "Rounded."}],
        "broken": [{"answer": {"expected_eyes_lost": 0.6, "p_no_eye_lost": 0.488}, "expected_verdict": "WRONG", "why_wrong": "Complement."},
                   {"answer": {"expected_eyes_lost": 0.6, "p_no_eye_lost": 0.4}, "expected_verdict": "WRONG", "why_wrong": "1 - 3 x 0.2: not independent events."}],
    },
})

# ---------------------------------------------------------------- dragon
DRAGON_OPTS = {
    "A": "Fight with the iron sword: wait for the dragon to perch on the exit portal and hit its head until it dies.",
    "B": "Wait for the dragon to perch on the exit portal, then place and explode beds next to its head, with a block between you and the blast.",
    "C": "Explode the beds on the island while the dragon is flying around the pillars, before it perches.",
    "D": "Climb the obsidian pillars and destroy every end crystal first, then fight the dragon with the sword.",
}
TASKS.append({
    "id": "T18_dragon_method",
    "split": "dragon", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You have just arrived in the End on the obsidian platform. You hold 6 beds, an iron sword, an iron pickaxe and 40 cobblestone. You have no bow.",
    "question": "Which way kills the dragon fastest with what you have?\n" + "\n".join("{}: {}".format(k, v) for k, v in DRAGON_OPTS.items()),
    "state": {"dimension": "the_end", "position": {"x": 100, "y": 49, "z": 0},
              "inventory": {"white_bed": 6, "iron_sword": 1, "iron_pickaxe": 1, "cobblestone": 40}, "known_locations": {}, "world": {}, "elapsed_s": None},
    "answer_type": "choice", "options": list(DRAGON_OPTS),
    "answer_schema": '{"choice": "A" | "B" | "C" | "D"}',
    "reference": {
        "answer": {"choice": "B"},
        "tolerance": {"choices": ["B"]},
        "pro_time_s": None,
        "why": "Beds explode when used in the End, and an explosion next to the perched dragon removes up to a quarter of its health per bed. "
               "The dragon only stays still while perched, so that is when the beds are used. The blast also hurts you, so a block between you and the bed is standard. "
               "Sword damage is small (the dragon takes about a quarter of damage that misses its head), so A takes many perches. "
               "C wastes beds on a moving target. D spends minutes climbing pillars. The agent on this project's seed killed the dragon with six bed explosions on one perch.",
        "trap": "A or D: the 'normal player' sword fight, which is many times slower.",
        "techniques": [{"tag": "bed_one_cycle", "description": "Explode beds on the perched dragon.", "est_time_saved_s": None, "verified": True,
                        "source": W + "Tutorial:Defeating_the_ender_dragon (raw line 89); " + W + "Bed (raw lines 179, 288)"}],
        "miss_category": "brute_force_over_trick",
        "sources": [W + "Bed", W + "Tutorial:Defeating_the_ender_dragon (Beds section)", W + "Ender_Dragon (raw line 72: damage not on the head reduced about 75%)",
                    AGENT + ":README.md:9 (six bed explosions on the first landing)", AGENT + ":optimization/nether/REVIEW.md:41,57"],
        "verified": True,
        "verified_note": "Runner-side source for the one-cycle (mcsr.info/speedrunning/one-cycle, cited in the agent README:88) was blocked from the sandbox.",
        "alternates": [{"answer": {"choice": "B", "reasoning": "One-cycle with beds."}, "why_valid": "Same choice."}],
        "broken": [{"answer": {"choice": "A"}, "expected_verdict": "WRONG", "why_wrong": "Sword only: many perches."},
                   {"answer": {"choice": "C"}, "expected_verdict": "WRONG", "why_wrong": "Beds while flying mostly miss."},
                   {"answer": {"choice": "D"}, "expected_verdict": "WRONG", "why_wrong": "Pillar climbing is slow and risky."}],
    },
})

BREATH_OPTS = {
    "A": "Walk straight through the nearer cloud to the bed spot; it is the shortest path and takes about 2 seconds inside the cloud.",
    "B": "Take a longer path around both clouds to the bed spot, even though it costs about 3 extra seconds and you may miss this perch.",
    "C": "Stand still at the edge of the nearer cloud until it fades, then walk through.",
}
TASKS.append({
    "id": "T19_dragon_breath_safety",
    "split": "dragon", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You are in the End with 6 beds, 8 hearts of health and no potions. The dragon has just started to perch on the exit portal. "
                 "Two purple dragon's-breath clouds lie on the ground: one directly between you and your bed spot next to the portal, and a second one just beyond it to the left.",
    "question": "What do you do?\n" + "\n".join("{}: {}".format(k, v) for k, v in BREATH_OPTS.items()),
    "state": {"dimension": "the_end", "position": None, "inventory": {"white_bed": 6, "cobblestone": 20}, "known_locations": {},
              "world": {"facts": ["Health 16/20", "Two dragon's breath clouds between you and the portal"]}, "elapsed_s": None},
    "answer_type": "choice", "options": list(BREATH_OPTS),
    "answer_schema": '{"choice": "A" | "B" | "C"}',
    "reference": {
        "answer": {"choice": "B"},
        "tolerance": {"choices": ["B"]},
        "pro_time_s": None,
        "why": "Dragon's-breath clouds deal Harming damage, which is magic damage and ignores armor, and they persist. A death ends the run, so a few seconds or one missed perch is the cheaper loss. "
               "The agent this project draws on died exactly this way: it escaped one cloud into another and then walked back through the first.",
        "trap": "A: the shortest path through the cloud. C: standing next to it is also inside the damage zone's edge.",
        "techniques": [{"tag": "avoid_breath_clouds", "description": "Path around every breath cloud.", "est_time_saved_s": None, "verified": True,
                        "source": AGENT + ":optimization/NOTES.md:26 (decision 171/172 crossed two clouds), " + AGENT + ":optimization/nether/REVIEW.md:37"}],
        "miss_category": "unnecessary_risk",
        "sources": [W + "Ender_Dragon (raw lines 147, 171: breath and fireball clouds damage like Harming)", AGENT + ":optimization/NOTES.md:26,54",
                    AGENT + ":optimization/nether/REVIEW.md:37"],
        "verified": True,
        "alternates": [{"answer": {"choice": "B", "reasoning": "Never enter a cloud."}, "why_valid": "Same choice."}],
        "broken": [{"answer": {"choice": "A"}, "expected_verdict": "WRONG", "why_wrong": "Takes Harming damage that ignores armor."},
                   {"answer": {"choice": "C"}, "expected_verdict": "WRONG", "why_wrong": "Waiting at the edge risks damage and still walks through."}],
    },
})

# ---------------------------------------------------------------- full_route (seed)
beds = {name: (pos, block) for name, pos, block in BEDS}
fr_state = {
    "dimension": "overworld", "position": {"x": -181.5, "y": 70, "z": 234.5}, "inventory": {},
    "known_locations": dict(SEED_LOCS),
    "world": {"chests": dict(SEED_CHESTS),
              "structures": {"village_center": {"type": "village", "notes": "plains village"},
                             "ruined_portal": {"type": "ruined_portal", "notes": RUINED_PORTAL_TEXT},
                             "stronghold_end_portal": {"type": "end_portal", "notes": "already active (all 12 frames filled)"}},
              "facts": ["Chest contents and bed positions are known from a survey of this seed.",
                        "The End portal at overworld (-1130, 34, 856) is already active.",
                        "Your first Nether portal at the ruined portal arrives in the Nether at about (-47.5, 77, 24.5)."]},
    "elapsed_s": 0,
}
fr_state["known_locations"]["nether_arrival"] = nth(-47.5, 77, 24.5)
for name, (pos, items) in CHEST_FOOD.items():
    fr_state["known_locations"][name] = ow(pos["x"], pos["y"], pos["z"])
    fr_state["world"]["chests"][name] = items
for name, pos, block in BEDS:
    fr_state["known_locations"][name] = ow(pos["x"], pos["y"], pos["z"])
    fr_state["world"]["structures"][name] = {"type": "bed", "notes": block}

def bed(name):
    return {"action": "mine", "block": beds[name][1], "count": 1, "at": name}

FR_OVERWORLD_1 = [
    bed("bed_1"),
    {"action": "travel", "to": "chest_village"}, {"action": "loot_chest", "at": "chest_village"},
    bed("bed_2"), bed("bed_5"), bed("bed_6"), bed("bed_8"), bed("bed_7"),
    {"action": "travel", "to": "chest_portal_a"}, {"action": "loot_chest", "at": "chest_portal_a"},
    {"action": "travel", "to": "chest_portal_b"}, {"action": "loot_chest", "at": "chest_portal_b"},
    {"action": "craft", "item": "flint_and_steel", "count": 1},
    {"action": "travel", "to": "ruined_portal"},
]
FR_REST = [
    {"action": "light_portal", "with": "flint_and_steel"},
    {"action": "enter_portal"},
    {"action": "travel", "to": {"x": -141, "y": 34, "z": 107}, "dimension": "the_nether"},
    {"action": "build_portal", "method": "chest_obsidian"},
    {"action": "light_portal", "with": "flint_and_steel"},
    {"action": "enter_portal"},
    {"action": "travel", "to": "stronghold_end_portal"},
    {"action": "enter_portal"},
    {"action": "bed_explode", "count": 6},
    {"action": "enter_portal"},
]
FR_REF = FR_OVERWORLD_1 + [{"action": "build_portal", "method": "complete_ruined"}] + FR_REST
FR_ALT = FR_OVERWORLD_1 + [{"action": "build_portal", "method": "chest_obsidian"}] + FR_REST
FR_NO_VILLAGE = [a for a in FR_REF if a.get("at") != "chest_village" and a.get("to") != "chest_village"]
FR_FOOD = [{"action": "loot_chest", "at": n} for n in CHEST_FOOD] + FR_REF
FR_OVERWORLD_WALK = FR_OVERWORLD_1 + [{"action": "travel", "to": "stronghold_end_portal"}, {"action": "enter_portal"},
                                      {"action": "bed_explode", "count": 6}, {"action": "enter_portal"}]
FR_FORTRESS = FR_REF[:FR_REF.index({"action": "enter_portal"}) + 1] + [
    {"action": "kill", "mob": "blaze", "count": 6}, {"action": "craft", "item": "blaze_powder", "count": 12}] + FR_REF[FR_REF.index({"action": "enter_portal"}) + 1:]

TASKS.append({
    "id": "T20_full_route_seed",
    "split": "full_route", "version": "1.16.5", "seed": SEED, "difficulty": "peaceful",
    "situation": "Plan this whole run from spawn. You start at (-181.5, 70, 234.5) with an empty inventory. A survey of this seed gives you every nearby chest's contents, "
                 "the bed positions in the village, the ruined portal frame, where your first Nether portal arrives, and the stronghold's End portal, which is already active. "
                 "Everything you know is in the state.",
    "question": "Give the fastest complete plan: from spawn until you enter the exit portal after killing the ender dragon.",
    "state": fr_state,
    "answer_type": "plan",
    "answer_schema": PLAN_SCHEMA,
    "reference": {
        "answer": {"actions": FR_REF},
        "tolerance": {"seconds": 30},
        "pro_time_s": 169.149,
        "pro_time_note": "Human IGT on this seed (dumbo0116, 1.16.5, Easy, set seed): 2:49.149 IGT, 2:54.545 RTA (official time). Segments from the runner's comment: "
                         "start to first portal 66.683 s, Nether 40.783 s, second portal exit to End portal 2.450 s, End 7.733 + 51.500 s. The human played on Easy, which is no easier than Peaceful.",
        "why": "Obsidian: the frame needs 7 (completing the ruined portal) and the Nether exit needs 10, so 17; the two portal chests have only 15, so the village chest's 6 are needed too (21 total). "
               "Flint (chest_portal_a) + iron (chest_portal_b) make flint and steel. Beds come from the village on the way (6 used; the agent's kill took six). "
               "No blaze rods or pearls: the End portal is already active. No food or armor: Peaceful. In the Nether, go to (-1130/8, 856/8) = (-141.25, 107) and build the exit there so the "
               "overworld portal generates next to the End portal (the human took 2.45 s from that exit to the End portal). Two portal crossings in total, like the human run.",
        "trap": "Skipping the village chest (15 obsidian is 2 short for two portals), walking 1,100 blocks in the overworld, going to a fortress for blaze rods, or collecting food and armor.",
        "techniques": [
            {"tag": "chest_obsidian_portal", "description": "Both portals from chest obsidian.", "est_time_saved_s": None, "verified": True, "source": AGENT + ":optimization/nether/REVIEW.md:7,9"},
            {"tag": "nether_travel_8to1", "description": "Nether shortcut to the stronghold.", "est_time_saved_s": None, "verified": True, "source": W + "Nether_Portal"},
            {"tag": "skip_fortress_active_portal", "description": "No rods or eyes.", "est_time_saved_s": None, "verified": True, "source": AGENT + ":README.md:35"},
            {"tag": "bed_one_cycle", "description": "Beds on the perched dragon.", "est_time_saved_s": None, "verified": True, "source": AGENT + ":README.md:9"},
            {"tag": "no_peaceful_food", "description": "No food on Peaceful.", "est_time_saved_s": None, "verified": True, "source": W + "Difficulty (raw line 29)"},
        ],
        "miss_category": "detour_overprep",
        "sources": [HUMAN_RUN, HUMAN_RUN_API, CFG, AGENT + ":optimization/nether/REVIEW.md:5-9", AGENT + ":README.md:7-9,35",
                    AGENT + ":optimization/nether/chest-survey.json", AGENT + ":optimization/nether/portal-loot.json",
                    AGENT + ":optimization/nether/stronghold-survey.json", AGENT + ":optimization/nether/entry-link.json",
                    W + "Nether_Portal", W + "Difficulty"],
        "verified": True,
        "verified_note": "Which beds and how many the human collected, and the exact exit coordinates the human used, need the VOD. See UNVERIFIED.md.",
        "alternates": [{"answer": {"actions": FR_ALT}, "why_valid": "Builds a fresh 10-block entry frame from chest obsidian (20 of 21 used). Three more placements; within tolerance."}],
        "broken": [
            {"answer": {"actions": FR_NO_VILLAGE}, "expected_verdict": "ILLEGAL", "why_wrong": "15 obsidian: 7 for the entry leaves 8, not enough for the 10-block exit portal."},
            {"answer": {"actions": FR_OVERWORLD_WALK}, "expected_verdict": "SLOW",
             "why_wrong": "Skips the Nether and walks about 1,100 overworld blocks to the stronghold (about 3 minutes at sprint speed) instead of about 140 in the Nether."},
            {"answer": {"actions": FR_FORTRESS}, "expected_verdict": "ILLEGAL", "why_wrong": "Blazes do not spawn on Peaceful, and no blaze rods are needed."},
            {"answer": {"actions": FR_FOOD}, "expected_verdict": "SLOW", "why_wrong": "Loots five food chests on Peaceful, where food cannot even be eaten."},
        ],
    },
})
PREP_OPTS = {
    "A": "Take only what the route uses: the obsidian, the flint and an iron ingot for flint and steel, and the beds. Leave the food, saplings and extra items.",
    "B": "Everything in A, plus all the bread, potatoes and apples from the village chests so your hunger bar stays full.",
    "C": "Everything in A, plus wood to craft a crafting table, a stone pickaxe, a stone sword and a shield.",
}
TASKS.append({
    "id": "T21_full_route_peaceful_prep",
    "split": "full_route", "version": "1.16.5", "seed": SEED, "difficulty": "peaceful",
    "situation": "You are at the village on this seed, Peaceful difficulty. Your route is: loot the chests, take beds, build a portal at the ruined portal, cross the Nether, exit next to the stronghold's already-active End portal, and kill the dragon with beds. "
                 "The village chests contain obsidian, flint, iron, an iron pickaxe, armor and a lot of food (see state).",
    "question": "What do you collect before going to the portal?\n" + "\n".join("{}: {}".format(k, v) for k, v in PREP_OPTS.items()),
    "state": fr_state,
    "answer_type": "choice", "options": list(PREP_OPTS),
    "answer_schema": '{"choice": "A" | "B" | "C"}',
    "reference": {
        "answer": {"choice": "A"},
        "tolerance": {"choices": ["A"]},
        "pro_time_s": None,
        "why": "On Peaceful the hunger bar never depletes, and in Java you cannot eat normal food then (only golden apples, chorus fruit, milk, honey and suspicious stew), so food is useless. "
               "The chests already give an iron pickaxe, so crafting stone tools is wasted time. Every extra chest or craft is seconds off a 3-minute run.",
        "trap": "B and C are the agent's real mistakes: 'The agent collected extra food, wood, and tools on Peaceful difficulty.'",
        "techniques": [{"tag": "no_peaceful_food", "description": "Skip food on Peaceful.", "est_time_saved_s": None, "verified": True, "source": W + "Difficulty (raw line 29)"},
                       {"tag": "no_extra_tools", "description": "Use the looted iron pickaxe.", "est_time_saved_s": None, "verified": True, "source": AGENT + ":optimization/NOTES.md:13-14"}],
        "miss_category": "detour_overprep",
        "sources": [W + "Difficulty (raw line 29)", AGENT + ":optimization/NOTES.md:13-14", AGENT + ":optimization/nether/chest-survey.json"],
        "verified": True,
        "alternates": [{"answer": {"choice": "A", "reasoning": "Food cannot be eaten on Peaceful."}, "why_valid": "Same choice."}],
        "broken": [{"answer": {"choice": "B"}, "expected_verdict": "WRONG", "why_wrong": "Food is useless on Peaceful."},
                   {"answer": {"choice": "C"}, "expected_verdict": "WRONG", "why_wrong": "Tools already looted; crafting wastes time."}],
    },
})
