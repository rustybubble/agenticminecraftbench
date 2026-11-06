"""Minecraft Java 1.16.5 game data used by the SplitCheck simulator.

Every fact is a plain dict carrying "verified" (bool) and "source" (str).
Only facts we are certain of are verified=True; everything else is data with
verified=False so it can be listed and fact-checked (see UNVERIFIED.md).

Ingredient keys starting with "any_" are wildcard groups resolved by
ingredient_matches():
  any_log     -> any id ending in "_log" or "_stem" (crimson/warped stems), or "log"
  any_planks  -> any id ending in "_planks", or "planks"
  any_wool    -> any id ending in "_wool", or "wool"
  any_stone   -> cobblestone or blackstone (both make stone tools / furnaces in 1.16)
"""
from __future__ import annotations

VERSION = "1.16.5"
WIKI = "https://minecraft.wiki"

# --------------------------------------------------------------------------- recipes
# output_count = items produced per craft; needs_table = needs a 3x3 crafting table.
RECIPES: dict[str, dict] = {
    "planks": {"output_count": 4, "ingredients": {"any_log": 1}, "needs_table": False,
               "verified": True, "source": WIKI + "/w/Planks#Crafting"},
    "stick": {"output_count": 4, "ingredients": {"any_planks": 2}, "needs_table": False,
              "verified": True, "source": WIKI + "/w/Stick#Crafting"},
    "crafting_table": {"output_count": 1, "ingredients": {"any_planks": 4}, "needs_table": False,
                       "verified": True, "source": WIKI + "/w/Crafting_Table#Crafting"},
    "wooden_pickaxe": {"output_count": 1, "ingredients": {"any_planks": 3, "stick": 2}, "needs_table": True,
                       "verified": True, "source": WIKI + "/w/Pickaxe#Crafting"},
    "stone_pickaxe": {"output_count": 1, "ingredients": {"any_stone": 3, "stick": 2}, "needs_table": True,
                      "verified": True, "source": WIKI + "/w/Pickaxe#Crafting"},
    "iron_pickaxe": {"output_count": 1, "ingredients": {"iron_ingot": 3, "stick": 2}, "needs_table": True,
                     "verified": True, "source": WIKI + "/w/Pickaxe#Crafting"},
    "diamond_pickaxe": {"output_count": 1, "ingredients": {"diamond": 3, "stick": 2}, "needs_table": True,
                        "verified": True, "source": WIKI + "/w/Pickaxe#Crafting"},
    "bucket": {"output_count": 1, "ingredients": {"iron_ingot": 3}, "needs_table": True,
               "verified": True, "source": WIKI + "/w/Bucket#Crafting"},
    "flint_and_steel": {"output_count": 1, "ingredients": {"iron_ingot": 1, "flint": 1}, "needs_table": False,
                        "verified": True, "source": WIKI + "/w/Flint_and_Steel#Crafting"},
    "blaze_powder": {"output_count": 2, "ingredients": {"blaze_rod": 1}, "needs_table": False,
                     "verified": True, "source": WIKI + "/w/Blaze_Powder#Crafting"},
    "ender_eye": {"output_count": 1, "ingredients": {"ender_pearl": 1, "blaze_powder": 1}, "needs_table": False,
                  "verified": True, "source": WIKI + "/w/Eye_of_Ender#Crafting"},
    "bed": {"output_count": 1, "ingredients": {"any_wool": 3, "any_planks": 3}, "needs_table": True,
            "verified": True, "source": WIKI + "/w/Bed#Crafting"},
    "furnace": {"output_count": 1, "ingredients": {"any_stone": 8}, "needs_table": True,
                "verified": True, "source": WIKI + "/w/Furnace#Crafting"},
    "golden_helmet": {"output_count": 1, "ingredients": {"gold_ingot": 5}, "needs_table": True,
                      "verified": True, "source": WIKI + "/w/Golden_Helmet"},
    "golden_chestplate": {"output_count": 1, "ingredients": {"gold_ingot": 8}, "needs_table": True,
                          "verified": True, "source": WIKI + "/w/Golden_Chestplate"},
    "golden_leggings": {"output_count": 1, "ingredients": {"gold_ingot": 7}, "needs_table": True,
                        "verified": True, "source": WIKI + "/w/Golden_Leggings"},
    "golden_boots": {"output_count": 1, "ingredients": {"gold_ingot": 4}, "needs_table": True,
                     "verified": True, "source": WIKI + "/w/Golden_Boots"},
    "gold_ingot": {"output_count": 1, "ingredients": {"gold_nugget": 9}, "needs_table": True,
                   "verified": True, "source": WIKI + "/w/Gold_Ingot#Crafting"},
    "iron_ingot": {"output_count": 1, "ingredients": {"iron_nugget": 9}, "needs_table": True,
                   "verified": True, "source": WIKI + "/w/Iron_Ingot#Crafting"},
}


def recipe_for(item: str) -> dict | None:
    """Recipe for an item id. Any *_planks maps to the planks recipe, any *_bed to bed."""
    if item in RECIPES:
        return RECIPES[item]
    if item.endswith("_planks"):
        return RECIPES["planks"]
    if item.endswith("_bed"):
        return RECIPES["bed"]
    return None


def ingredient_matches(group: str, item_id: str) -> bool:
    if not group.startswith("any_"):
        return group == item_id
    if group == "any_log":
        return item_id == "log" or item_id.endswith("_log") or item_id.endswith("_stem")
    if group == "any_planks":
        return item_id == "planks" or item_id.endswith("_planks")
    if group == "any_wool":
        return item_id == "wool" or item_id.endswith("_wool")
    if group == "any_bed":
        return item_id == "bed" or item_id.endswith("_bed")
    if group == "any_stone":
        return item_id in ("cobblestone", "blackstone")
    return False


# --------------------------------------------------------------------------- smelting
SMELTING: dict[str, dict] = {
    "iron_ingot": {"input": "iron_ore", "verified": True, "source": WIKI + "/w/Iron_Ingot#Smelting"},
    "gold_ingot": {"input": "gold_ore", "verified": True, "source": WIKI + "/w/Gold_Ingot#Smelting"},
    "glass": {"input": "sand", "verified": True, "source": WIKI + "/w/Glass#Smelting"},
    "stone": {"input": "cobblestone", "verified": True, "source": WIKI + "/w/Stone#Smelting"},
    "charcoal": {"input": "any_log", "verified": True, "source": WIKI + "/w/Charcoal"},
    "cooked_porkchop": {"input": "porkchop", "verified": True, "source": WIKI + "/w/Cooked_Porkchop"},
    "cooked_beef": {"input": "beef", "verified": True, "source": WIKI + "/w/Steak"},
}

# items smelted per fuel item
FUEL_ITEMS_PER_UNIT: dict[str, dict] = {
    "coal": {"items": 8, "verified": True, "source": WIKI + "/w/Smelting#Fuel"},
    "charcoal": {"items": 8, "verified": True, "source": WIKI + "/w/Smelting#Fuel"},
    "blaze_rod": {"items": 12, "verified": True, "source": WIKI + "/w/Smelting#Fuel"},
    "lava_bucket": {"items": 100, "verified": True, "source": WIKI + "/w/Smelting#Fuel"},
    "coal_block": {"items": 80, "verified": True, "source": WIKI + "/w/Smelting#Fuel"},
    "any_log": {"items": 1.5, "verified": True, "source": WIKI + "/w/Smelting#Fuel"},
    "any_planks": {"items": 1.5, "verified": True, "source": WIKI + "/w/Smelting#Fuel"},
    "stick": {"items": 0.5, "verified": True, "source": WIKI + "/w/Smelting#Fuel"},
}

# --------------------------------------------------------------------------- mining
# tool tiers: 0 = hand, 1 = wooden, 2 = stone, 3 = iron, 4 = diamond/netherite
PICKAXE_TIER = {"wooden_pickaxe": 1, "golden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3,
                "diamond_pickaxe": 4, "netherite_pickaxe": 4}

# block -> {"tier": minimum pickaxe tier for a drop, "drops": {item: expected count per block}}
MINING: dict[str, dict] = {
    "obsidian": {"tier": 4, "drops": {"obsidian": 1}, "verified": True, "source": WIKI + "/w/Obsidian#Breaking"},
    "crying_obsidian": {"tier": 4, "drops": {"crying_obsidian": 1}, "verified": True, "source": WIKI + "/w/Crying_Obsidian"},
    "stone": {"tier": 1, "drops": {"cobblestone": 1}, "verified": True, "source": WIKI + "/w/Stone#Breaking"},
    "cobblestone": {"tier": 1, "drops": {"cobblestone": 1}, "verified": True, "source": WIKI + "/w/Cobblestone"},
    "blackstone": {"tier": 1, "drops": {"blackstone": 1}, "verified": True, "source": WIKI + "/w/Blackstone"},
    "netherrack": {"tier": 1, "drops": {"netherrack": 1}, "verified": True, "source": WIKI + "/w/Netherrack"},
    "coal_ore": {"tier": 1, "drops": {"coal": 1}, "verified": True, "source": WIKI + "/w/Coal_Ore"},
    "iron_ore": {"tier": 2, "drops": {"iron_ore": 1}, "verified": True, "source": WIKI + "/w/Iron_Ore"},
    "gold_ore": {"tier": 3, "drops": {"gold_ore": 1}, "verified": True, "source": WIKI + "/w/Gold_Ore"},
    "diamond_ore": {"tier": 3, "drops": {"diamond": 1}, "verified": True, "source": WIKI + "/w/Diamond_Ore"},
    # nether gold ore drops 2-6 nuggets (no fortune): expected 4
    "nether_gold_ore": {"tier": 1, "drops": {"gold_nugget": 4}, "stochastic": True,
                        "verified": True, "source": WIKI + "/w/Nether_Gold_Ore"},
    # gravel: 10% flint (no fortune) in 1.16; otherwise drops gravel
    "gravel": {"tier": 0, "drops": {"flint": 0.1, "gravel": 0.9}, "stochastic": True,
               "verified": True, "source": WIKI + "/w/Gravel#Breaking"},
    "dirt": {"tier": 0, "drops": {"dirt": 1}, "verified": True, "source": WIKI + "/w/Dirt"},
    "grass_block": {"tier": 0, "drops": {"dirt": 1}, "verified": True, "source": WIKI + "/w/Grass_Block"},
    "sand": {"tier": 0, "drops": {"sand": 1}, "verified": True, "source": WIKI + "/w/Sand"},
    "white_wool": {"tier": 0, "drops": {"white_wool": 1}, "verified": True, "source": WIKI + "/w/Wool"},
}


def mining_rule(block: str) -> dict | None:
    """Rule for a block, or None when the simulator has no 1.16.5 rule for it.

    Logs/stems/planks/wool/beds drop themselves. Leaves without shears drop no leaf block
    (sapling/stick/apple chances are not modelled). Anything else (including items such as
    tools, eyes, flint_and_steel) has no rule: the caller must treat mining it as illegal.
    """
    if block in MINING:
        return MINING[block]
    if block.endswith("_leaves"):
        return {"tier": 0, "drops": {}, "verified": False,
                "source": WIKI + "/w/Leaves#Breaking (no shears: sapling/stick/apple chance not modelled)"}
    if block.endswith(("_log", "_stem", "_planks", "_wool", "_bed")):
        return {"tier": 0, "drops": {block: 1}, "verified": True, "source": WIKI}
    return None


# --------------------------------------------------------------------------- portals
NETHER_PORTAL = {
    "frame_obsidian_cornerless": 10,  # 4 wide x 5 tall frame without the 4 corners
    "frame_obsidian_full": 14,
    "coordinate_scale": 8,            # overworld x,z = nether x,z * 8; y not scaled
    "verified": True,
    "source": WIKI + "/w/Nether_portal",
}

END_PORTAL = {
    "frames": 12,
    "frame_prefill_chance": 0.1,     # each frame independently has an eye when generated
    "verified": True,
    "source": WIKI + "/w/End_portal_frame",
}

EYE_OF_ENDER = {
    "break_chance": 0.2,             # 20% shatter when thrown, 80% drop back
    "verified": True,
    "source": WIKI + "/w/Eye_of_Ender#Usage",
}

# --------------------------------------------------------------------------- piglin barter (1.16.2+ table)
# weight out of BARTER_TOTAL_WEIGHT; count = (min, max). Recalled from the wiki history for
# 1.16.2+ (pearls reduced from weight 20 / 4-8 to weight 10 / 2-4). NOT verified against the
# 1.16.5 loot table JSON in-session, hence verified=False.
_BARTER_SRC = WIKI + "/w/Bartering (1.16.2+ table; unverified recall)"
BARTER_TABLE: dict[str, dict] = {
    "enchanted_book_soul_speed": {"weight": 5, "count": (1, 1)},
    "iron_boots_soul_speed": {"weight": 8, "count": (1, 1)},
    "potion_fire_resistance": {"weight": 8, "count": (1, 1)},
    "splash_potion_fire_resistance": {"weight": 8, "count": (1, 1)},
    "potion_water": {"weight": 10, "count": (1, 1)},
    "iron_nugget": {"weight": 10, "count": (10, 36)},
    "ender_pearl": {"weight": 10, "count": (2, 4)},
    "string": {"weight": 20, "count": (3, 9)},
    "quartz": {"weight": 20, "count": (5, 12)},
    "obsidian": {"weight": 40, "count": (1, 1)},
    "crying_obsidian": {"weight": 40, "count": (1, 3)},
    "fire_charge": {"weight": 40, "count": (1, 1)},
    "leather": {"weight": 40, "count": (2, 4)},
    "soul_sand": {"weight": 40, "count": (2, 8)},
    "nether_brick": {"weight": 40, "count": (2, 8)},
    "spectral_arrow": {"weight": 40, "count": (6, 12)},
    "gravel": {"weight": 40, "count": (8, 16)},
    "blackstone": {"weight": 40, "count": (8, 16)},
}
for _e in BARTER_TABLE.values():
    _e["verified"] = False
    _e["source"] = _BARTER_SRC
BARTER_TOTAL_WEIGHT = sum(e["weight"] for e in BARTER_TABLE.values())  # 459


# 1.16.0/1.16.1 table: only the ender pearl entry is modelled (weight 20 of 423, 4-8 pearls),
# taken from reference/T07_bastion_pearls_1161.json. Other 1.16.1 yields are not tracked.
BARTER_TABLE_1161: dict[str, dict] = {
    "ender_pearl": {"weight": 20, "count": (4, 8), "verified": False,
                    "source": "reference/T07_bastion_pearls_1161.json (1.16.1: weight 20/423, 4-8)"},
}
BARTER_TOTAL_WEIGHT_1161 = 423

BARTER_TABLES = {
    "1.16.2+": (BARTER_TABLE, BARTER_TOTAL_WEIGHT),
    "1.16.1": (BARTER_TABLE_1161, BARTER_TOTAL_WEIGHT_1161),
}


def barter_table_for(version) -> str:
    """'1.16.1' for Java 1.16.0/1.16.1, else '1.16.2+' (the default 1.16.5 table)."""
    v = str(version or VERSION).strip()
    return "1.16.1" if v in ("1.16", "1.16.0", "1.16.1") else "1.16.2+"


def barter_expected_per_ingot(item: str, table: str = "1.16.2+") -> float:
    entries, total = BARTER_TABLES.get(table, BARTER_TABLES["1.16.2+"])
    e = entries.get(item)
    if not e:
        return 0.0
    lo, hi = e["count"]
    return e["weight"] / total * (lo + hi) / 2


# barter results that are real inventory items (the potions/enchanted gear are not tracked)
BARTER_TRACKED_ITEMS = ("ender_pearl", "string", "obsidian", "crying_obsidian", "fire_charge", "leather",
                        "soul_sand", "nether_brick", "spectral_arrow", "gravel", "blackstone", "quartz",
                        "iron_nugget")

GOLD_ARMOR = ("golden_helmet", "golden_chestplate", "golden_leggings", "golden_boots")

# --------------------------------------------------------------------------- mobs
MOBS: dict[str, dict] = {
    "blaze": {"hostile": True, "dimension": "the_nether", "drops": {"blaze_rod": 0.5},
              "verified": True, "source": WIKI + "/w/Blaze (0-1 rods without looting)"},
    "enderman": {"hostile": True, "dimension": None, "drops": {"ender_pearl": 0.5},
                 "verified": True, "source": WIKI + "/w/Enderman (does not spawn on Peaceful; 0-1 pearls)"},
    "piglin_brute": {"hostile": True, "dimension": "the_nether", "drops": {},
                     "verified": True, "source": WIKI + "/w/Piglin_Brute"},
    "wither_skeleton": {"hostile": True, "dimension": "the_nether", "drops": {},
                        "verified": True, "source": WIKI + "/w/Wither_Skeleton"},
    "ghast": {"hostile": True, "dimension": "the_nether", "drops": {}, "verified": True, "source": WIKI + "/w/Ghast"},
    "magma_cube": {"hostile": True, "dimension": "the_nether", "drops": {}, "verified": True, "source": WIKI + "/w/Magma_Cube"},
    "hoglin": {"hostile": True, "dimension": "the_nether", "drops": {"porkchop": 3}, "verified": True,
               "source": WIKI + "/w/Hoglin"},
    "zombie": {"hostile": True, "dimension": None, "drops": {}, "verified": True, "source": WIKI + "/w/Zombie"},
    "skeleton": {"hostile": True, "dimension": None, "drops": {}, "verified": True, "source": WIKI + "/w/Skeleton"},
    "creeper": {"hostile": True, "dimension": None, "drops": {}, "verified": True, "source": WIKI + "/w/Creeper"},
    "spider": {"hostile": True, "dimension": None, "drops": {"string": 1}, "verified": True, "source": WIKI + "/w/Spider"},
    "piglin": {"hostile": False, "dimension": "the_nether", "drops": {}, "verified": True,
               "source": WIKI + "/w/Piglin (neutral; spawns on Peaceful)"},
    "ender_dragon": {"hostile": False, "dimension": "the_end", "drops": {}, "verified": True,
                     "source": WIKI + "/w/Ender_Dragon (present on Peaceful)"},
    "sheep": {"hostile": False, "dimension": "overworld", "drops": {"white_wool": 1}, "verified": True,
              "source": WIKI + "/w/Sheep"},
    "pig": {"hostile": False, "dimension": "overworld", "drops": {"porkchop": 2}, "verified": True, "source": WIKI + "/w/Pig"},
    "cow": {"hostile": False, "dimension": "overworld", "drops": {"beef": 2}, "verified": True, "source": WIKI + "/w/Cow"},
}

BED_EXPLODES_IN = ("the_nether", "the_end")
BED_RULE = {"explodes_in": BED_EXPLODES_IN, "verified": True, "source": WIKI + "/w/Bed#Explosion"}
