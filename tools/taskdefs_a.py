"""Tasks for splits reset, nether_entry, bastion, fortress (T01-T11). Owner: B."""
import json

import compute_answers as ca
from taskdefs_common import *  # noqa: F401,F403

WP_SPEEDRUN = "https://en.wikipedia.org/wiki/Minecraft_speedrunning (section on resetting; raw wikitext line 48, fetched 2026-11-06)"
BARTER_1161 = "https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets/1.16.1/data/minecraft/loot_tables/gameplay/piglin_bartering.json (ender_pearl weight 20 of 423, count uniform 4-8)"
BARTER_1165 = "https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets/1.16.5/data/minecraft/loot_tables/gameplay/piglin_bartering.json (ender_pearl weight 10 of 459, count uniform 2-4)"
BARTER_WIKI_OLD = W + "Bartering/Outdated_loot_tables (sections 20w20a-20w27a and 20w28a-25w17a)"

barter = ca.barter(32)
rods = ca.rods_needed(pearls=11, rods=2, powder=1)
rp = ca.ruined_portal_seed()

SEED_STATE_START = {
    "dimension": "overworld",
    "position": {"x": -181.5, "y": 70, "z": 234.5},
    "inventory": {},
    "known_locations": dict(SEED_LOCS),
    "world": {
        "chests": dict(SEED_CHESTS),
        "structures": {
            "village_center": {"type": "village", "notes": "plains village"},
            "ruined_portal": {"type": "ruined_portal", "notes": RUINED_PORTAL_TEXT},
        },
        "facts": ["Chest contents are known from a survey of this seed."],
    },
    "elapsed_s": 0,
}

TASKS = []

# ---------------------------------------------------------------- reset
TASKS.append({
    "id": "T01_reset_hopeless_plains",
    "split": "reset", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You have just loaded into a new random-seed world (about 5 seconds of in-game time used). "
                 "You spawned in the middle of a large plains biome. Looking around to the edge of your render distance (about 100 blocks), "
                 "you see no trees, no water, no lava, no village, no ruined portal, no shipwreck and no ocean. Your inventory is empty.",
    "question": "Do you keep playing this world or reset and generate a new one? Answer with \"keep\" or \"reset\".",
    "state": {"dimension": "overworld", "position": None, "inventory": {}, "known_locations": {},
              "world": {"facts": ["Plains in every direction to render distance; no trees, water, lava or structures visible."]},
              "elapsed_s": 5},
    "answer_type": "choice", "options": ["keep", "reset"],
    "answer_schema": '{"choice": "keep" | "reset"}',
    "reference": {
        "answer": {"choice": "reset"},
        "tolerance": {"choices": ["reset"]},
        "pro_time_s": None,
        "why": "RSG runners reset constantly and only keep spawns that give fast early resources: wood for tools, and a fast portal (village, ruined portal, beach with buried treasure and magma ravines). "
               "With no trees in sight there is no wood for a crafting table or pickaxe, and with no water, lava or structure there is no route to a portal. "
               "Walking around to look for any of these costs minutes, while a reset costs seconds, so the expected time of a new seed is far better.",
        "trap": "Keep and walk until trees appear. The run is not lost, but the expected time is far worse than resetting.",
        "techniques": [
            {"tag": "reset_judgment", "description": "Reset spawns with no early resources or portal route within view.",
             "est_time_saved_s": None, "verified": False,
             "source": WP_SPEEDRUN + " says runners reset to find villages, ruined portals or beaches; a runner guide quote for 'no trees = reset' is still needed (mcsr.info blocked from sandbox)."},
        ],
        "miss_category": "no_reset_judgment",
        "sources": [WP_SPEEDRUN],
        "verified": False,
        "alternates": [{"answer": {"choice": "reset", "reasoning": "No wood means no tools; reset is cheaper than exploring."},
                        "why_valid": "Same decision with different reasoning; reasoning is not scored."}],
        "broken": [{"answer": {"choice": "keep"}, "expected_verdict": "WRONG",
                    "why_wrong": "Commits minutes to a spawn with no wood and no portal route."}],
    },
})

TASKS.append({
    "id": "T02_reset_keep_seed_spawn",
    "split": "reset", "version": "1.16.5", "seed": SEED, "difficulty": "easy",
    "situation": "You have just spawned at (-181.5, 70, 234.5). About 50 blocks to the west-southwest is a plains village (center about (-225, 71, 255)) "
                 "with houses, beds and chests. About 105 blocks to the west is a ruined portal at about (-285, 67, 259) with two chests next to it. "
                 "Trees are nearby. You have not opened any chest yet, and you do not yet know where the stronghold is. Your inventory is empty.",
    "question": "Do you keep playing this world or reset and generate a new one? Answer with \"keep\" or \"reset\".",
    "state": {"dimension": "overworld", "position": {"x": -181.5, "y": 70, "z": 234.5}, "inventory": {},
              "known_locations": {"village_center": ow(-225, 71, 255), "ruined_portal": ow(-285, 67, 259)},
              "world": {"structures": {"village_center": {"type": "village", "notes": "beds and chests visible"},
                                       "ruined_portal": {"type": "ruined_portal", "notes": "two chests next to it"}}},
              "elapsed_s": 0},
    "answer_type": "choice", "options": ["keep", "reset"],
    "answer_schema": '{"choice": "keep" | "reset"}',
    "reference": {
        "answer": {"choice": "keep"},
        "tolerance": {"choices": ["keep"]},
        "pro_time_s": None,
        "why": "A village plus a ruined portal with chests next to spawn is the kind of spawn runners reset to find: quick loot and a fast portal. "
               "This exact seed and spawn produced a verified 2:54.545 Any% Glitchless run (dumbo0116, 1.16.5, Easy, set seed), so keeping it is correct.",
        "trap": "Reset because the stronghold location is unknown or because there is no lava visible. The chests and the ruined portal make the portal fast without lava.",
        "techniques": [
            {"tag": "reset_judgment", "description": "Keep spawns with a village and a ruined portal in view.", "est_time_saved_s": None, "verified": True,
             "source": HUMAN_RUN + " (verified run on this seed); " + WP_SPEEDRUN},
        ],
        "miss_category": "no_reset_judgment",
        "sources": [HUMAN_RUN, HUMAN_RUN_API, WP_SPEEDRUN, CFG + ":6-10,28-33",
                    AGENT + ":optimization/nether/spawn-survey.json (position -181.5, 70, 234.5)"],
        "verified": True,
        "alternates": [{"answer": {"choice": "keep", "reasoning": "Village loot plus ruined portal chests."}, "why_valid": "Same decision."}],
        "broken": [{"answer": {"choice": "reset"}, "expected_verdict": "WRONG",
                    "why_wrong": "Throws away a seed that a human finished in 2:54.545."}],
    },
})

TASKS.append({
    "id": "T03_reset_keep_beach_treasure",
    "split": "reset", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You have just loaded into a new random-seed world (about 5 seconds used). You spawned on a beach next to an ocean. "
                 "There are trees about 20 blocks inland, and a shipwreck is visible in the shallow water about 40 blocks away. Your inventory is empty.",
    "question": "Do you keep playing this world or reset and generate a new one? Answer with \"keep\" or \"reset\".",
    "state": {"dimension": "overworld", "position": None, "inventory": {}, "known_locations": {},
              "world": {"facts": ["Beach spawn next to ocean", "Trees 20 blocks inland", "Shipwreck about 40 blocks away in shallow water"]},
              "elapsed_s": 5},
    "answer_type": "choice", "options": ["keep", "reset"],
    "answer_schema": '{"choice": "keep" | "reset"}',
    "reference": {
        "answer": {"choice": "keep"},
        "tolerance": {"choices": ["keep"]},
        "pro_time_s": None,
        "why": "Beaches are one of the spawn types runners reset to find. Buried treasure gives iron and food early; shipwrecks hold the treasure map and supplies; "
               "the ocean gives access to magma ravines with obsidian and lava for a quick portal. Trees give wood for tools.",
        "trap": "Reset because there is no village or ruined portal in sight.",
        "techniques": [
            {"tag": "reset_judgment", "description": "Keep beach spawns with wood and a shipwreck/buried treasure.", "est_time_saved_s": None, "verified": True,
             "source": WP_SPEEDRUN},
        ],
        "miss_category": "no_reset_judgment",
        "sources": [WP_SPEEDRUN],
        "verified": True,
        "alternates": [{"answer": {"choice": "keep", "reasoning": "Buried treasure iron, ocean ravines for the portal."}, "why_valid": "Same decision."}],
        "broken": [{"answer": {"choice": "reset"}, "expected_verdict": "WRONG",
                    "why_wrong": "Resets one of the spawn types runners reset to find."}],
    },
})

# ---------------------------------------------------------------- nether_entry
T04_ref_plan = [
    {"action": "travel", "to": "chest_portal_b"},
    {"action": "loot_chest", "at": "chest_portal_b"},
    {"action": "travel", "to": "chest_portal_a"},
    {"action": "loot_chest", "at": "chest_portal_a"},
    {"action": "craft", "item": "flint_and_steel", "count": 1},
    {"action": "travel", "to": "ruined_portal"},
    {"action": "build_portal", "method": "complete_ruined"},
    {"action": "light_portal", "with": "flint_and_steel"},
    {"action": "enter_portal"},
]
T04_alt_chest = [
    {"action": "travel", "to": "chest_village"}, {"action": "loot_chest", "at": "chest_village"},
] + T04_ref_plan[:6] + [{"action": "build_portal", "method": "chest_obsidian"},
                        {"action": "light_portal", "with": "flint_and_steel"}, {"action": "enter_portal"}]
T04_detour = [
    {"action": "travel", "to": "chest_food_1"}, {"action": "loot_chest", "at": "chest_food_1"},
    {"action": "travel", "to": "chest_food_5"}, {"action": "loot_chest", "at": "chest_food_5"},
    {"action": "travel", "to": "chest_food_3"}, {"action": "loot_chest", "at": "chest_food_3"},
    {"action": "travel", "to": "chest_food_2"}, {"action": "loot_chest", "at": "chest_food_2"},
    {"action": "travel", "to": "chest_village"}, {"action": "loot_chest", "at": "chest_village"},
    {"action": "travel", "to": "chest_food_4"}, {"action": "loot_chest", "at": "chest_food_4"},
] + T04_ref_plan

t04_state = json.loads(json.dumps(SEED_STATE_START))
for name, (pos, items) in CHEST_FOOD.items():
    t04_state["known_locations"][name] = ow(pos["x"], pos["y"], pos["z"])
    t04_state["world"]["chests"][name] = items

TASKS.append({
    "id": "T04_nether_entry_seed_chests",
    "split": "nether_entry", "version": "1.16.5", "seed": SEED, "difficulty": "easy",
    "situation": "You have just spawned with an empty inventory. A survey of this seed tells you exactly what is in each nearby chest "
                 "(see \"world.chests\" in the state) and what the ruined portal frame looks like. Only the chests listed exist nearby. "
                 "You have no pickaxe, bucket or lava source.",
    "question": "Give the fastest plan from now until you are standing in the Nether. Ignore what you will need later in the run; "
                "this question ends when you arrive in the Nether.",
    "state": t04_state,
    "answer_type": "plan",
    "answer_schema": PLAN_SCHEMA,
    "reference": {
        "answer": {"actions": T04_ref_plan},
        "tolerance": {"seconds": 15},
        "pro_time_s": None,
        "pro_time_note": "Price `answer` with splits/time_costs.json. Upper bound from the human run: 66.683 s from start to first portal enter, which also includes whatever else the runner collected (beds) before entering.",
        "why": "Both ruined-portal chests sit next to the portal: chest_portal_b has 11 obsidian and 6 iron ingots, chest_portal_a has 4 obsidian and 1 flint. "
               "That is 15 obsidian, plus 1 iron ingot + 1 flint for flint and steel (crafted in the 2x2 inventory grid, no table needed). "
               "The ruined frame already holds 3 usable obsidian for a 4x5 frame shifted one block along Z, so completing it takes 7 placements and avoids the crying obsidian. "
               "The village chest (6 obsidian, iron pickaxe) is not needed just to enter the Nether. No obsidian has to be mined, and there is no diamond pickaxe to mine it with.",
        "trap": "Mining obsidian (impossible here: no diamond pickaxe), looking for lava, or looting every village chest for food and armor before going to the portal.",
        "techniques": [
            {"tag": "chest_obsidian_portal", "description": "Build the portal from looted chest obsidian instead of mining or casting it.", "est_time_saved_s": None, "verified": True,
             "source": AGENT + ":optimization/nether/REVIEW.md:7,9; " + AGENT + ":optimization/nether/portal-loot.json"},
            {"tag": "complete_ruined_portal", "description": "Reuse the ruined frame's usable obsidian (3 blocks) and skip the crying obsidian.", "est_time_saved_s": None, "verified": True,
             "source": AGENT + ":optimization/nether/REVIEW.md:9; tools/compute_answers.py ruined_portal_seed()"},
            {"tag": "inventory_crafting", "description": "Craft flint and steel in the 2x2 inventory grid.", "est_time_saved_s": None, "verified": True,
             "source": W + "Flint_and_Steel (recipe: 1 iron ingot + 1 flint); " + AGENT + ":optimization/nether/REVIEW.md:21-25"},
        ],
        "miss_category": "brute_force_over_trick",
        "sources": [CFG + ":11-33", AGENT + ":optimization/nether/portal-loot.json", AGENT + ":optimization/nether/chest-survey.json",
                    AGENT + ":optimization/nether/portal-survey.json", AGENT + ":optimization/nether/REVIEW.md:7,9",
                    W + "Flint_and_Steel", W + "Crying_Obsidian (cannot be used in a Nether portal frame; needs diamond pickaxe)", W + "Nether_Portal (4x5 frame, corners optional)"],
        "verified": True,
        "alternates": [{"answer": {"actions": T04_alt_chest},
                        "why_valid": "Also loots the village chest on the way and builds a fresh 10-block frame from chest obsidian. Legal; a few seconds slower (small detour, 3 extra placements), within the 15 s tolerance."}],
        "broken": [
            {"answer": {"actions": [{"action": "travel", "to": "ruined_portal"}, {"action": "build_portal", "method": "mine_obsidian"},
                                    {"action": "light_portal", "with": "flint_and_steel"}, {"action": "enter_portal"}]},
             "expected_verdict": "ILLEGAL", "why_wrong": "No diamond pickaxe to mine obsidian, and no flint and steel was crafted."},
            {"answer": {"actions": [{"action": "travel", "to": "chest_portal_b"}, {"action": "loot_chest", "at": "chest_portal_b"},
                                    {"action": "craft", "item": "flint_and_steel", "count": 1}, {"action": "travel", "to": "ruined_portal"},
                                    {"action": "build_portal", "method": "complete_ruined"}, {"action": "light_portal", "with": "flint_and_steel"},
                                    {"action": "enter_portal"}]},
             "expected_verdict": "ILLEGAL", "why_wrong": "Skips chest_portal_a, the only flint, so flint and steel cannot be crafted."},
            {"answer": {"actions": [{"action": "travel", "to": "chest_village"}, {"action": "loot_chest", "at": "chest_village"},
                                    {"action": "travel", "to": "ruined_portal"}, {"action": "build_portal", "method": "chest_obsidian"},
                                    {"action": "light_portal", "with": "fire_charge"}, {"action": "enter_portal"}]},
             "expected_verdict": "ILLEGAL", "why_wrong": "6 obsidian is not enough for a 10-block frame, and there is no fire charge."},
            {"answer": {"actions": T04_detour}, "expected_verdict": "SLOW",
             "why_wrong": "Loots all six village chests (food, armor) first: legal but a long detour through the village before the portal."},
        ],
    },
})

TASKS.append({
    "id": "T05_nether_entry_ruined_portal_count",
    "split": "nether_entry", "version": "1.16.5", "seed": SEED, "difficulty": "easy",
    "situation": "You are standing at the ruined portal. " + RUINED_PORTAL_TEXT + " "
                 "You have looted the chests and hold 21 obsidian, an iron pickaxe and a flint and steel. You have no diamond pickaxe.",
    "question": "You want a working Nether portal here as fast as possible, reusing the existing frame where you can. "
                "A portal needs a rectangular frame with an interior at least 2 wide and 3 tall; corners are optional. "
                "What is the minimum number of obsidian blocks you must place?",
    "state": {"dimension": "overworld", "position": {"x": -284, "y": 67, "z": 259},
              "inventory": {"obsidian": 21, "iron_pickaxe": 1, "flint_and_steel": 1},
              "known_locations": {"ruined_portal": ow(-285, 67, 259)},
              "world": {"structures": {"ruined_portal": {"type": "ruined_portal", "notes": RUINED_PORTAL_TEXT}}},
              "elapsed_s": None},
    "answer_type": "number",
    "answer_schema": '{"obsidian_to_place": <int>}',
    "reference": {
        "answer": {"obsidian_to_place": rp["best_without_diamond_pickaxe"]["place"]},
        "tolerance": {"abs": 0},
        "pro_time_s": None,
        "why": "A cornerless 4x5 frame needs 10 obsidian: 2 bottom, 2 top, 3 on each side. Crying obsidian cannot be part of a portal frame, and it needs a diamond pickaxe to remove, so any frame "
               "that uses z = 261 at y = 67 is out. The most complete frame is interior z 259-260 (6 usable blocks) but its right side is the crying block at (261,67). "
               "Shifting one block along Z to interior z 258-259, y 67-69 reuses (258,66), (259,66) and (259,70) and needs 7 new blocks: (258,70), z = 257 at y 67-69, and z = 260 at y 67-69. "
               "tools/compute_answers.py ruined_portal_seed() checks every 2x3 placement.",
        "trap": "4: completes the most intact frame by counting the crying obsidian at (261,67) as frame or by mining it (impossible without a diamond pickaxe). "
                "10: ignores the existing frame. 9: the 'rotated open frame' in the agent's config note.",
        "techniques": [
            {"tag": "complete_ruined_portal", "description": "Reuse usable ruined-portal obsidian; route around crying obsidian.", "est_time_saved_s": None, "verified": True,
             "source": AGENT + ":optimization/nether/REVIEW.md:9"},
        ],
        "miss_category": "resource_miscount",
        "sources": [AGENT + ":optimization/nether/portal-survey.json (groups.obsidian, groups.crying_obsidian at x = -285)",
                    AGENT + ":optimization/nether/REVIEW.md:9 (three essential obsidian exist, seven must be placed, avoids crying obsidian)",
                    W + "Crying_Obsidian (raw line 38: cannot be used to create a nether portal frame; line 24: needs diamond pickaxe)",
                    W + "Nether_Portal (raw line 24: 4x5 minimum frame, corners not required)"],
        "verified": True,
        "verified_note": "The prompt states that the other blocks in the plane are air. That matches REVIEW.md:9 (the 7-block frame was built in practice) but the air blocks themselves are not in the survey file. See UNVERIFIED.md.",
        "alternates": [{"answer": {"obsidian_to_place": 7, "reasoning": "Interior z 258-259; reuse three blocks."}, "why_valid": "Same count."}],
        "broken": [
            {"answer": {"obsidian_to_place": 4}, "expected_verdict": "WRONG", "why_wrong": "Uses or mines crying obsidian."},
            {"answer": {"obsidian_to_place": 10}, "expected_verdict": "WRONG", "why_wrong": "Ignores the reusable frame blocks."},
            {"answer": {"obsidian_to_place": 9}, "expected_verdict": "WRONG", "why_wrong": "Rotated frame from config.json:65; not minimal."},
        ],
    },
})

T06_ref = [
    {"action": "travel", "to": "gravel_patch"},
    {"action": "mine", "block": "gravel", "count": 10},
    {"action": "craft", "item": "flint_and_steel", "count": 1},
    {"action": "travel", "to": "lava_pool"},
    {"action": "build_portal", "method": "bucket_lava"},
    {"action": "light_portal", "with": "flint_and_steel"},
    {"action": "enter_portal"},
]
TASKS.append({
    "id": "T06_nether_entry_lava_pool",
    "split": "nether_entry", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "Random seed, 2:10 into the run. You are at (100, 64, -40). There is no village, ruined portal or known obsidian within 300 blocks, and you have found no diamonds. "
                 "A surface lava pool with more than 20 lava source blocks is at about (130, 62, -15). A patch of exposed gravel (30+ blocks) is at about (110, 63, -55).",
    "question": "Give the fastest plan from now until you are standing in the Nether.",
    "state": {"dimension": "overworld", "position": {"x": 100, "y": 64, "z": -40},
              "inventory": {"water_bucket": 1, "iron_ingot": 2, "stone_pickaxe": 1, "cobblestone": 24, "oak_planks": 6, "crafting_table": 1},
              "known_locations": {"lava_pool": ow(130, 62, -15), "gravel_patch": ow(110, 63, -55)},
              "world": {"structures": {"lava_pool": {"type": "lava_pool", "notes": "surface pool, 20+ source blocks"},
                                       "gravel_patch": {"type": "gravel_patch", "notes": "30+ exposed gravel blocks"}},
                        "facts": ["No village, ruined portal or obsidian within 300 blocks.", "No diamonds found."]},
              "elapsed_s": 130},
    "answer_type": "plan",
    "answer_schema": PLAN_SCHEMA,
    "reference": {
        "answer": {"actions": T06_ref},
        "tolerance": {"seconds": 15},
        "pro_time_s": None,
        "pro_time_note": "Price `answer` with splits/time_costs.json.",
        "why": "Without a diamond pickaxe obsidian cannot be mined, and there are no diamonds. The standard method is to cast the frame at the lava pool: place blocks as a mold, "
               "and use the water bucket on lava to turn the frame positions into obsidian. You still need a lighter: gravel drops flint 10% of the time, so mine gravel until flint "
               "(10 blocks at the expected rate), then craft flint and steel from 1 iron ingot + 1 flint.",
        "trap": "Go looking for diamonds to mine obsidian with a diamond pickaxe, or forget that the portal needs a lighter.",
        "techniques": [
            {"tag": "lava_pool_portal", "description": "Cast the obsidian frame with a water bucket on a lava pool.", "est_time_saved_s": None, "verified": True,
             "source": W + "Tutorial:Nether_portals (raw lines 18-22: lava pool method needs a water bucket, a lava pool, blocks and flint and steel)"},
            {"tag": "gravel_flint", "description": "Mine gravel for flint (10% per block).", "est_time_saved_s": None, "verified": True, "source": W + "Gravel (raw line 18)"},
        ],
        "miss_category": "brute_force_over_trick",
        "sources": [W + "Tutorial:Nether_portals", W + "Gravel", W + "Obsidian (needs diamond pickaxe; 9.4 s per block)", W + "Flint_and_Steel"],
        "verified": True,
        "alternates": [{"answer": {"actions": [T06_ref[0], T06_ref[1], T06_ref[3], T06_ref[2], T06_ref[4], T06_ref[5], T06_ref[6]]},
                        "why_valid": "Crafts the flint and steel after walking to the lava. Same actions, same time."}],
        "broken": [
            {"answer": {"actions": [{"action": "travel", "to": "lava_pool"}, {"action": "build_portal", "method": "mine_obsidian"},
                                    {"action": "light_portal", "with": "flint_and_steel"}, {"action": "enter_portal"}]},
             "expected_verdict": "ILLEGAL", "why_wrong": "No diamond pickaxe; no flint and steel."},
            {"answer": {"actions": [{"action": "travel", "to": "lava_pool"}, {"action": "build_portal", "method": "bucket_lava"},
                                    {"action": "light_portal", "with": "flint_and_steel"}, {"action": "enter_portal"}]},
             "expected_verdict": "ILLEGAL", "why_wrong": "Never gets flint, so there is no flint and steel to light the portal."},
            {"answer": {"actions": [{"action": "craft", "item": "diamond_pickaxe", "count": 1}] + T06_ref},
             "expected_verdict": "ILLEGAL", "why_wrong": "No diamonds to craft a diamond pickaxe."},
        ],
    },
})

# ---------------------------------------------------------------- bastion
def barter_task(tid, version, exp, ingots12, src, trap_exp, trap_ing):
    return {
        "id": tid,
        "split": "bastion", "version": version, "seed": None, "difficulty": "easy",
        "situation": "You are at a bastion remnant in the Nether, wearing a golden helmet, with several adult piglins nearby. You hold 32 gold ingots and no ender pearls. "
                     "You will barter by throwing gold ingots to the piglins one at a time.",
        "question": "(1) What is the expected (average) number of ender pearls you get from bartering all 32 ingots? "
                    "(2) On average, how many gold ingots does it take to get 12 ender pearls? Give decimals, not ranges.",
        "state": {"dimension": "the_nether", "position": None, "inventory": {"gold_ingot": 32, "golden_helmet": 1},
                  "known_locations": {}, "world": {"facts": ["Golden helmet is worn.", "Adult piglins nearby."]}, "elapsed_s": None},
        "answer_type": "number",
        "answer_schema": '{"expected_pearls": <number>, "ingots_for_12_pearls": <number>}',
        "reference": {
            "answer": {"expected_pearls": exp, "ingots_for_12_pearls": ingots12},
            "tolerance": {"fields": {"expected_pearls": {"abs": round(max(0.3, exp * 0.05), 2)}, "ingots_for_12_pearls": {"abs": round(max(2, ingots12 * 0.05), 1)}}},
            "pro_time_s": None,
            "why": "Each barter is one roll on the piglin_bartering loot table. Expected pearls per ingot = (pearl weight / total weight) x (mean stack size). "
                   + ("In 1.16.1 the pearl entry has weight 20 of 423 and gives 4-8 pearls (mean 6): 0.2837 pearls per ingot. "
                      if version == "1.16.1" else
                      "In 1.16.5 (since 1.16.2) the pearl entry has weight 10 of 459 and gives 2-4 pearls (mean 3): 0.0654 pearls per ingot. ")
                   + "32 ingots give {} pearls on average; 12 pearls need {} ingots on average.".format(exp, ingots12),
            "trap": "Using the other version's table ({} pearls, {} ingots) or today's table (weight 10 of 469). Pearl rates were cut about 4.3x in 1.16.2, which is why runners pick 1.16.1 for bastion routes.".format(trap_exp, trap_ing),
            "techniques": [
                {"tag": "version_barter_rates", "description": "Know the barter table of the version being run.", "est_time_saved_s": None, "verified": True, "source": src},
            ],
            "miss_category": "resource_miscount",
            "sources": [src, BARTER_WIKI_OLD, "tools/compute_answers.py barter()"],
            "verified": True,
            "alternates": [{"answer": {"expected_pearls": round(exp, 1), "ingots_for_12_pearls": float(int(ingots12) + 1)},
                            "why_valid": "Rounded; rounding up to whole ingots is reasonable and within tolerance."}],
            "broken": [{"answer": {"expected_pearls": trap_exp, "ingots_for_12_pearls": trap_ing}, "expected_verdict": "WRONG",
                        "why_wrong": "Uses the other 1.16 version's barter table."},
                       {"answer": {"expected_pearls": 32 * 6.0, "ingots_for_12_pearls": 2}, "expected_verdict": "WRONG",
                        "why_wrong": "Assumes every barter gives pearls."}],
        },
    }

TASKS.append(barter_task("T07_bastion_pearls_1161", "1.16.1", barter["expected_pearls_1.16.1"], barter["ingots_for_12_expected_1.16.1"],
                         BARTER_1161, barter["expected_pearls_1.16.5"], barter["ingots_for_12_expected_1.16.5"]))
TASKS.append(barter_task("T08_bastion_pearls_1165", "1.16.5", barter["expected_pearls_1.16.5"], barter["ingots_for_12_expected_1.16.5"],
                         BARTER_1165, barter["expected_pearls_1.16.1"], barter["ingots_for_12_expected_1.16.1"]))

PIGLIN_OPTS = {
    "A": "Put on the golden helmet, throw gold ingots to the piglins, and do not open any chest while piglins can see you.",
    "B": "Leave the golden helmet in your inventory (not worn) and throw gold ingots to the piglins.",
    "C": "Put on the golden helmet, then open the bastion chests next to the piglins to collect extra gold first, then barter.",
    "D": "Put on the golden helmet, then mine the blocks of gold next to the piglins for extra gold, then barter.",
}
TASKS.append({
    "id": "T09_bastion_piglin_rules",
    "split": "bastion", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You are entering a bastion remnant with about 8 adult piglins in view, within 10 blocks. You hold 20 gold ingots and a golden helmet (in your inventory, not worn), "
                 "and you are wearing no armor. There are chests and blocks of gold in the room with the piglins.",
    "question": "Which approach gets you pearls fastest without a fight? Options:\n" + "\n".join("{}: {}".format(k, v) for k, v in PIGLIN_OPTS.items()),
    "state": {"dimension": "the_nether", "position": None, "inventory": {"gold_ingot": 20, "golden_helmet": 1}, "known_locations": {},
              "world": {"facts": ["8 adult piglins within 10 blocks with line of sight", "Chests and blocks of gold in the same room"]}, "elapsed_s": None},
    "answer_type": "choice", "options": list(PIGLIN_OPTS),
    "answer_schema": '{"choice": "A" | "B" | "C" | "D"}',
    "reference": {
        "answer": {"choice": "A"},
        "tolerance": {"choices": ["A"]},
        "pro_time_s": None,
        "why": "Adult piglins are hostile unless the player wears at least one piece of golden armor (carrying it does not count). "
               "Opening a chest within about 15 blocks of a piglin with line of sight angers it, and breaking a block of gold angers piglins within 16 blocks even without line of sight. "
               "So: wear the helmet, barter, and leave the chests and gold blocks alone while piglins are near.",
        "trap": "B: carrying gold armor is not wearing it. C and D: looting the bastion while piglins watch starts a fight.",
        "techniques": [
            {"tag": "gold_armor_neutral", "description": "Wear one golden armor piece so piglins stay neutral.", "est_time_saved_s": None, "verified": True, "source": W + "Piglin (raw lines 63, 145, 156)"},
            {"tag": "no_chest_near_piglins", "description": "Do not open chests or break gold blocks near piglins.", "est_time_saved_s": None, "verified": True, "source": W + "Piglin (raw lines 160-170)"},
        ],
        "miss_category": "mob_rule_unaware",
        "sources": [W + "Piglin (Aggravation section; current-version page, rules unchanged since 1.16 apart from newer container types)"],
        "verified": True,
        "alternates": [{"answer": {"choice": "A", "reasoning": "Gold armor keeps them neutral; containers and gold blocks anger them."}, "why_valid": "Same choice."}],
        "broken": [{"answer": {"choice": "B"}, "expected_verdict": "WRONG", "why_wrong": "Helmet not worn: piglins attack."},
                   {"answer": {"choice": "C"}, "expected_verdict": "WRONG", "why_wrong": "Opening chests near piglins angers them."},
                   {"answer": {"choice": "D"}, "expected_verdict": "WRONG", "why_wrong": "Breaking gold blocks angers piglins within 16 blocks."}],
    },
})

# ---------------------------------------------------------------- fortress
TASKS.append({
    "id": "T10_fortress_rods_seed",
    "split": "fortress", "version": "1.16.5", "seed": SEED, "difficulty": "peaceful",
    "situation": "You are planning the route for this seed before the run. A survey of the stronghold under (-1130, 34, 856) lists the 12 End portal frame blocks "
                 "and their state; it is in \"world.facts\". You currently have no ender pearls, no blaze rods and no eyes of ender.",
    "question": "How many blaze rods and how many ender pearls must you collect during the run in order to enter the End through this stronghold's portal?",
    "state": {"dimension": "overworld", "position": {"x": -181.5, "y": 70, "z": 234.5}, "inventory": {},
              "known_locations": {"stronghold_end_portal": ow(-1130, 34, 856)},
              "world": {"structures": {"stronghold_end_portal": {"type": "end_portal", "notes": "portal room survey below"}},
                        "facts": ["End portal frame survey (x, y, z, eye): " + json.dumps(FRAMES_ALL_FILLED)]},
              "elapsed_s": 0},
    "answer_type": "number",
    "answer_schema": '{"blaze_rods": <int>, "ender_pearls": <int>}',
    "reference": {
        "answer": {"blaze_rods": 0, "ender_pearls": 0},
        "tolerance": {"abs": 0},
        "pro_time_s": None,
        "why": "All 12 frames in the survey have eye = true, so the End portal is already active (the 9 end_portal blocks are present in the survey). "
               "No eyes are needed to light it, and the stronghold location is already known, so no eyes are needed to find it either. "
               "So no blaze rods and no pearls: the whole fortress and bastion splits are skipped. The human 2:54.545 run on this seed has only two Nether portal crossings and no fortress.",
        "trap": "6 rods and 12 pearls (or 7 and 14 with spares): the default RSG count, which ignores the survey.",
        "techniques": [
            {"tag": "skip_fortress_active_portal", "description": "Skip blaze rods and pearls when the End portal is pre-filled.", "est_time_saved_s": None, "verified": True,
             "source": AGENT + ":README.md:35; " + AGENT + ":optimization/nether/REVIEW.md:7"},
        ],
        "miss_category": "ignores_information",
        "sources": [AGENT + ":optimization/nether/stronghold-survey.json (groups.end_portal_frame: 12 frames, all eye = true; groups.end_portal: 9 blocks)",
                    AGENT + ":README.md:35", AGENT + ":optimization/nether/REVIEW.md:7", HUMAN_RUN_API, W + "End_Portal_Frame (raw lines 16, 30)"],
        "verified": True,
        "alternates": [{"answer": {"blaze_rods": 0, "ender_pearls": 0, "reasoning": "Portal already active."}, "why_valid": "Same numbers."}],
        "broken": [{"answer": {"blaze_rods": 6, "ender_pearls": 12}, "expected_verdict": "WRONG", "why_wrong": "Ignores the pre-filled frames."},
                   {"answer": {"blaze_rods": 7, "ender_pearls": 14}, "expected_verdict": "WRONG", "why_wrong": "Default count with spares; ignores the survey."}],
    },
})

TASKS.append({
    "id": "T11_fortress_rods_generic",
    "split": "fortress", "version": "1.16.5", "seed": None, "difficulty": "easy",
    "situation": "You are in a Nether fortress next to a blaze spawner. You hold 11 ender pearls, 2 blaze rods and 1 blaze powder. You want to craft an eye of ender from every pearl you have.",
    "question": "What is the minimum number of additional blaze rods you must get from blazes?",
    "state": {"dimension": "the_nether", "position": None, "inventory": {"ender_pearl": 11, "blaze_rod": 2, "blaze_powder": 1}, "known_locations": {},
              "world": {"structures": {}, "facts": ["Next to a blaze spawner in a fortress."]}, "elapsed_s": None},
    "answer_type": "number",
    "answer_schema": '{"additional_blaze_rods": <int>}',
    "reference": {
        "answer": {"additional_blaze_rods": rods["additional_blaze_rods"]},
        "tolerance": {"abs": 0},
        "pro_time_s": None,
        "why": "Each eye takes 1 pearl + 1 blaze powder, so 11 eyes need 11 powder. You have 1 powder, and your 2 rods make 4 more: 5. "
               "You need 6 more powder, and each rod gives 2, so 3 more rods.",
        "trap": "9 (one rod per eye, minus the 2 held), 4 (forgets the loose powder), or 5 (forgets the rods already held).",
        "techniques": [
            {"tag": "rod_count", "description": "1 rod = 2 powder; count held rods and powder.", "est_time_saved_s": None, "verified": True,
             "source": W + "Blaze_Powder (raw line 12: Output Blaze Powder,2); " + W + "Eye_of_Ender (recipe)"},
        ],
        "miss_category": "resource_miscount",
        "sources": [W + "Blaze_Powder", W + "Eye_of_Ender", "tools/compute_answers.py rods_needed()"],
        "verified": True,
        "alternates": [{"answer": {"additional_blaze_rods": 3, "reasoning": "6 powder short."}, "why_valid": "Same number."}],
        "broken": [{"answer": {"additional_blaze_rods": rods["trap_rods_one_per_eye"]}, "expected_verdict": "WRONG", "why_wrong": "One rod per eye."},
                   {"answer": {"additional_blaze_rods": rods["trap_ignore_loose_powder"]}, "expected_verdict": "WRONG", "why_wrong": "Ignores the held powder."},
                   {"answer": {"additional_blaze_rods": 5}, "expected_verdict": "WRONG", "why_wrong": "Ignores the held rods."}],
    },
})

