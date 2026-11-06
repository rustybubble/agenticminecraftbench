"""Shared text and seed data for tools/build_tasks.py. Owner: B."""

SEED = "8398967436125155523"
AGENT = "rmalde/minecraft-agent"
CFG = AGENT + ":optimization/nether/config.json"
HUMAN_RUN = "https://www.speedrun.com/mc/runs/yoex3d0z"
HUMAN_RUN_API = "https://www.speedrun.com/api/v1/runs/yoex3d0z (comment field, fetched 2026-11-06)"

W = "https://minecraft.wiki/w/"

PREAMBLE = (
    "You are advising a Minecraft Java Edition speedrunner (Any%, glitchless, single player, Survival). "
    "The goal is to finish the game (kill the ender dragon and enter the exit portal) in the least in-game time. "
    "Answer the way an expert runner would.\n\n"
)

REPLY = (
    "\n\nReply with ONLY one JSON object in exactly this shape (you may add a \"reasoning\" string key; "
    "it is not scored):\n{schema}"
)

ACTIONS_DOC = """
Plan actions (use only these, in order; any other key is ignored):
- {"action": "mine", "block": <block id>, "count": <int>, "at": <optional location name>}  break blocks and collect the drops
- {"action": "craft", "item": <item id>, "count": <int>}
- {"action": "smelt", "item": <output item id>, "count": <int>, "fuel": <item id>}
- {"action": "loot_chest", "at": <location name>}  take everything from that chest
- {"action": "travel", "to": <location name or {"x":..,"y":..,"z":..}>, "dimension": <optional>}  move within the current dimension
- {"action": "build_portal", "method": "bucket_lava" | "chest_obsidian" | "mine_obsidian" | "complete_ruined"}  build a Nether portal frame where you are
- {"action": "light_portal", "with": "flint_and_steel" | "fire_charge"}
- {"action": "enter_portal"}  go through the portal where you are (Nether portal or End portal)
- {"action": "barter", "gold_ingots": <int>}
- {"action": "kill", "mob": <mob id>, "count": <int>}
- {"action": "throw_eye", "at": {"x":..,"y":..,"z":..}}
- {"action": "place_eyes", "count": <int>}
- {"action": "bed_explode", "count": <int>}  place and use beds (for example against the ender dragon)
- {"action": "reset"}  abandon this world
Ids are Minecraft ids without the "minecraft:" prefix (obsidian, flint_and_steel, iron_ingot, white_bed, ...).
""".strip()

PLAN_SCHEMA = '{"actions": [{"action": "...", "...": "..."}]}'

# ---- seed 8398967436125155523 survey (rmalde/minecraft-agent) ----

CHEST_VILLAGE = {"obsidian": 6, "iron_pickaxe": 1, "gold_ingot": 2, "iron_helmet": 2, "bread": 4, "iron_sword": 1}
CHEST_PORTAL_A = {"flint": 1, "golden_leggings": 1, "glistering_melon_slice": 4, "obsidian": 4}
CHEST_PORTAL_B = {"obsidian": 11, "bread": 3, "iron_ingot": 6, "diamond_horse_armor": 1, "saddle": 1}
# Other village chests (food only) from optimization/nether/chest-survey.json
CHEST_FOOD = {
    "chest_food_1": ({"x": -174, "y": 70, "z": 254}, {"potato": 13, "apple": 11, "bread": 3}),
    "chest_food_2": ({"x": -225, "y": 68, "z": 251}, {"bread": 5, "map": 1}),
    "chest_food_3": ({"x": -213, "y": 69, "z": 273}, {"bread": 4, "leather_chestplate": 1}),
    "chest_food_4": ({"x": -244, "y": 72, "z": 254}, {"potato": 6, "oak_sapling": 4, "apple": 2, "bread": 3}),
    "chest_food_5": ({"x": -226, "y": 74, "z": 299}, {"oak_sapling": 3, "bread": 7, "apple": 1}),
}

# Beds: optimization/nether/config.json:66-107 (positions) + portal-survey.json / spawn-survey.json (colours)
BEDS = [
    ("bed_1", {"x": -214, "y": 73, "z": 225}, "white_bed"),
    ("bed_2", {"x": -201, "y": 71, "z": 254}, "yellow_bed"),
    ("bed_3", {"x": -207, "y": 73, "z": 311}, "white_bed"),
    ("bed_4", {"x": -226, "y": 72, "z": 320}, "yellow_bed"),
    ("bed_5", {"x": -224, "y": 74, "z": 302}, "yellow_bed"),
    ("bed_6", {"x": -247, "y": 72, "z": 256}, "yellow_bed"),
    ("bed_7", {"x": -269, "y": 74, "z": 266}, "white_bed"),
    ("bed_8", {"x": -270, "y": 75, "z": 254}, "yellow_bed"),
]

def ow(x, y, z):
    return {"x": x, "y": y, "z": z, "dimension": "overworld"}

def nth(x, y, z):
    return {"x": x, "y": y, "z": z, "dimension": "the_nether"}

SEED_LOCS = {
    "start": ow(-181.5, 70, 234.5),
    "village_center": ow(-225, 71, 255),
    "chest_village": ow(-228, 71, 240),
    "chest_portal_a": ow(-284, 66, 262),
    "chest_portal_b": ow(-290, 68, 253),
    "ruined_portal": ow(-285, 67, 259),
    "stronghold_end_portal": ow(-1130, 34, 856),
}

SEED_CHESTS = {"chest_village": CHEST_VILLAGE, "chest_portal_a": CHEST_PORTAL_A, "chest_portal_b": CHEST_PORTAL_B}

RUINED_PORTAL_TEXT = (
    "The ruined portal frame stands in the vertical plane x = -285. Its remaining blocks (z, y) are: "
    "obsidian at (258,66), (259,66), (260,66), (261,68), (261,69), (259,70), (260,70), (261,70); "
    "crying obsidian at (261,66) and (261,67). Other positions in that plane near the frame are air."
)

FRAMES_ALL_FILLED = [
    {"x": -1129, "y": 34, "z": 854, "eye": True}, {"x": -1128, "y": 34, "z": 855, "eye": True},
    {"x": -1130, "y": 34, "z": 854, "eye": True}, {"x": -1128, "y": 34, "z": 856, "eye": True},
    {"x": -1131, "y": 34, "z": 854, "eye": True}, {"x": -1128, "y": 34, "z": 857, "eye": True},
    {"x": -1132, "y": 34, "z": 855, "eye": True}, {"x": -1129, "y": 34, "z": 858, "eye": True},
    {"x": -1132, "y": 34, "z": 856, "eye": True}, {"x": -1130, "y": 34, "z": 858, "eye": True},
    {"x": -1132, "y": 34, "z": 857, "eye": True}, {"x": -1131, "y": 34, "z": 858, "eye": True},
]
