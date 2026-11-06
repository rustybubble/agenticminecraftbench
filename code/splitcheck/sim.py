"""SplitCheck state simulator for plan answers (SCHEMA.md section 4), Minecraft Java 1.16.5.

simulate(task, plan, costs) walks the plan's actions from task["state"], checks each
action's preconditions, applies its effects to inventory/position/dimension, and prices
it with the time-cost table. The first failed precondition makes the plan ILLEGAL
(legal=False, failed_step=index, reason cites the step and the missing thing).

Determinism: stochastic outcomes (barter yields, gravel->flint, mob drops, nether gold
ore nuggets) use the expected value rounded down; such steps carry the note
"stochastic: expected value used". Eye throws break at floor(0.2 * throws), cumulative.

time_s is the time of the plan itself (it does not include state.elapsed_s);
final_state["elapsed_s"] = state.elapsed_s + time_s.
"""
from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import rules_1165 as R

STOCHASTIC_NOTE = "stochastic: expected value used"
NEAR_BLOCKS = 8.0          # "at a location" = within this horizontal distance, same dimension
SPRINT_BPS = 7.127         # flat sprint-jump blocks per second (estimate)

DEFAULT_COSTS_PATH = Path(__file__).resolve().parents[2] / "splits" / "time_costs.json"


def _e(seconds, per, notes=""):
    return {"seconds": seconds, "per": per, "source": "estimate", "verified": False, "notes": notes}


DEFAULT_COSTS: dict[str, dict] = {
    "travel": _e(round(100 / SPRINT_BPS, 3), "100_blocks", "horizontal sprint-jump 7.127 blocks/s"),
    "travel_nether": _e(round(100 / SPRINT_BPS, 3), "100_blocks", "same speed as overworld"),
    "mine": _e(1.0, "block", "generic block with the right tool"),
    "mine_obsidian": _e(9.4, "block", "diamond pickaxe, no efficiency"),
    "mine_gravel": _e(1.0, "block", "flint chance 10%"),
    "craft": _e(1.5, "item", "per craft operation"),
    "smelt": _e(10.0, "item", "furnace 10 s per item"),
    "loot_chest": _e(3.0, "action", "open + take all"),
    "build_portal_bucket_lava": _e(30.0, "action", "lava-pool portal with water + lava bucket"),
    "build_portal_chest_obsidian": _e(12.0, "action", "place 10 obsidian, cornerless"),
    "build_portal_complete_ruined": _e(8.0, "action", "place the missing blocks"),
    "build_portal_mine_obsidian": _e(0.0, "action", "mining is priced by the mine action"),
    "light_portal": _e(1.0, "action"),
    "enter_portal": _e(4.0, "action", "portal animation"),
    "barter": _e(6.0, "item", "per gold ingot"),
    "kill": _e(5.0, "item", "per mob"),
    "throw_eye": _e(3.0, "action", "throw + read angle"),
    "place_eyes": _e(0.5, "item", "per eye"),
    "bed_explode": _e(6.0, "item", "per bed"),
    "reset": _e(0.0, "action", "ends the plan"),
}


def load_costs(path=None) -> dict:
    """DEFAULT_COSTS merged with splits/time_costs.json (SCHEMA section 5) when present.

    Returns a flat {key: {"seconds","per","source","verified","notes"}} dict.
    """
    costs = copy.deepcopy(DEFAULT_COSTS)
    p = Path(path) if path is not None else DEFAULT_COSTS_PATH
    try:
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            entries = data.get("actions", data) if isinstance(data, dict) else {}
            if isinstance(data, dict) and isinstance(data.get("rules"), dict):
                costs["__rules__"] = data["rules"]
            for k, v in entries.items():
                if isinstance(v, dict) and isinstance(v.get("seconds"), (int, float)):
                    merged = dict(costs.get(k, {}))
                    merged.update(v)
                    merged.setdefault("per", "action")
                    costs[k] = merged
    except (OSError, ValueError):
        pass
    return costs


@dataclass
class SimResult:
    legal: bool
    reason: str | None
    failed_step: int | None
    time_s: float
    steps: list = field(default_factory=list)
    final_state: dict = field(default_factory=dict)
    techniques_used: list = field(default_factory=list)


class Illegal(Exception):
    pass


# --------------------------------------------------------------------------- helpers

def _num(v, default=0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(v, name):
    if isinstance(v, bool):
        raise Illegal(f"'{name}' must be an integer (got {v!r})")
    try:
        n = int(v)
    except (TypeError, ValueError, OverflowError):
        raise Illegal(f"'{name}' must be a finite integer (got {v!r})")
    if n < 0:
        raise Illegal(f"'{name}' must be >= 0 (got {n})")
    return n


def _id(a, key, action):
    v = a.get(key)
    if not v:
        raise Illegal(f"{action} needs '{key}'")
    if not isinstance(v, str):
        raise Illegal(f"{action} '{key}' must be an id string (got {v!r})")
    return v


def _hdist(a, b):
    if not a or not b:
        return None
    return math.hypot(_num(a.get("x")) - _num(b.get("x")), _num(a.get("z")) - _num(b.get("z")))


def _pos(d):
    if not isinstance(d, dict) or "x" not in d or "z" not in d:
        return None
    return {"x": _num(d.get("x")), "y": _num(d.get("y"), 0), "z": _num(d.get("z"))}


class _Sim:
    def __init__(self, task, costs):
        st = copy.deepcopy(task.get("state") or {})
        self.task = task
        self.costs = costs
        self.dim = st.get("dimension") or "overworld"
        self.pos = _pos(st.get("position"))
        self.inv = {k: int(v) for k, v in (st.get("inventory") or {}).items() if _num(v) > 0}
        self.locs = st.get("known_locations") or {}
        world = st.get("world") or {}
        self.chests = world.get("chests") or {}
        self.structures = copy.deepcopy(world.get("structures") or {})
        self.facts = [str(f) for f in (world.get("facts") or [])]
        self.elapsed0 = _num(st.get("elapsed_s"), 0)
        self.peaceful = str(task.get("difficulty", "")).lower() == "peaceful"
        self.looted = []
        self.portals = []          # {"x","z","dimension","lit","method"}
        self.table_placed = False
        self.furnace_placed = False
        self.throws = []           # positions of eye throws (since last place_eyes)
        self.eyes_thrown = 0
        self.dragon_killed = False
        self.beds_in_end = 0
        self.finished = False
        self.dragon_beds_required = int(_num((costs.get("__rules__", {}).get("dragon_beds_required", {}) or {}).get("value", R.DRAGON_BEDS_DEFAULT if hasattr(R, "DRAGON_BEDS_DEFAULT") else 6)))
        self.eyes_broken = 0
        self.techniques = []
        self.reset = False
        self.end_frames = {}       # end_portal location name -> filled count
        self.end_active = {}

    # ---------------- costs
    def cost(self, keys, qty=1):
        for k in keys:
            e = self.costs.get(k)
            if e:
                per = e.get("per", "action")
                s = _num(e.get("seconds"))
                if per == "100_blocks":
                    return s * qty / 100.0
                if per in ("block", "item"):
                    return s * qty
                return s
        return 0.0

    def tag(self, t):
        if t not in self.techniques:
            self.techniques.append(t)

    # ---------------- inventory
    def has(self, item, n=1):
        return self.inv.get(item, 0) >= n

    def count_group(self, group):
        return sum(v for k, v in self.inv.items() if R.ingredient_matches(group, k))

    def take(self, item, n):
        self.inv[item] = self.inv.get(item, 0) - n
        if self.inv[item] <= 0:
            del self.inv[item]

    def take_group(self, group, n, prefer=None):
        keys = sorted(k for k in self.inv if R.ingredient_matches(group, k))
        if prefer and prefer in keys:
            keys.remove(prefer)
            keys.insert(0, prefer)
        for k in keys:
            if n <= 0:
                break
            t = min(n, self.inv[k])
            self.take(k, t)
            n -= t

    def give(self, item, n):
        if n > 0:
            self.inv[item] = self.inv.get(item, 0) + int(n)

    # ---------------- locations
    def loc_dim(self, loc):
        return loc.get("dimension") or "overworld"

    def here_names(self):
        if self.pos is None:
            return []
        out = []
        for name, loc in self.locs.items():
            if isinstance(loc, dict) and self.loc_dim(loc) == self.dim:
                d = _hdist(self.pos, loc)
                if d is not None and d <= NEAR_BLOCKS:
                    out.append(name)
        return out

    def structure_here(self, stype):
        for name in self.here_names():
            s = self.structures.get(name)
            if isinstance(s, dict) and s.get("type") == stype:
                return name, s
        return None, None

    def move_to(self, target, note_list, implicit=False):
        d = _hdist(self.pos, target) if self.pos else None
        t = 0.0
        if d is None:
            note_list.append("start position unknown: travel distance not priced")
        else:
            key = ["travel_nether", "travel"] if self.dim == "the_nether" else ["travel"]
            t = self.cost(key, d)
            note_list.append(f"{'implicit travel ' if implicit else ''}{d:.1f} blocks in {self.dim}")
            if self.dim == "the_nether" and d > 0:
                self.tag("nether_travel_8to1")
        self.pos = dict(target)
        return t

    def ensure_at(self, name, notes):
        """Travel implicitly to a named location in the current dimension."""
        loc = self.locs.get(name)
        if not isinstance(loc, dict):
            raise Illegal(f"location {name!r} is not in state.known_locations")
        if self.loc_dim(loc) != self.dim:
            raise Illegal(f"{name!r} is in {self.loc_dim(loc)} but you are in {self.dim}; "
                          f"change dimension with enter_portal first")
        if name in self.here_names():
            return 0.0
        return self.move_to(_pos(loc), notes, implicit=True)

    # ---------------- end portal state
    def end_portal_state(self, name, s):
        if name not in self.end_frames:
            filled = None
            for k in ("frames_filled", "eyes_filled", "filled_frames", "prefilled", "eyes_placed"):
                if isinstance(s.get(k), (int, float)):
                    filled = int(s[k])
                    break
            notes = str(s.get("notes", ""))
            if filled is None:
                m = re.search(r"(\d+)\s*(?:of 12\s*)?(?:frames?|eyes?)\s*(?:already\s*)?(?:filled|pre-?filled|placed|in)", notes, re.I)
                filled = int(m.group(1)) if m else 0
            active = bool(s.get("active")) or filled >= R.END_PORTAL["frames"]
            if "active" not in s:
                # free text is only used per sentence: that sentence must name an End portal
                # (or this location) and say it is active, with no negation.
                for fact in [notes] + list(self.facts):
                    f = fact.lower()
                    names_it = ("end portal" in f or "end_portal" in f) or name.lower() in f
                    if names_it and re.search(r"(?<!in)\bactive\b", f) and \
                            not re.search(r"\b(?:not|isn't|is not|never|no)\b[^.]*\bactive|inactive|can be made active", f):
                        active = True
            self.end_frames[name] = R.END_PORTAL["frames"] if active else filled
            self.end_active[name] = active
        return self.end_frames[name], self.end_active[name]

    # ---------------- actions
    def do(self, a, notes):
        act = a.get("action")
        if not isinstance(act, str):
            raise Illegal(f"'action' must be a string (got {act!r})")
        fn = DISPATCH.get(act)
        if fn is None:
            raise Illegal(f"unknown action {act!r} (not in SCHEMA section 4 vocabulary)")
        return fn(self, a, notes)


def _mine(s, a, notes):
    block = _id(a, "block", "mine")
    n = _int(a.get("count", 1), "count")
    rule = R.mining_rule(block)
    if rule is None:
        raise Illegal(f"no 1.16.5 mining rule for {block!r} (not a known world block; items cannot be mined)")
    tier = max([R.PICKAXE_TIER[p] for p in R.PICKAXE_TIER if s.has(p)] or [0])
    if tier < rule["tier"]:
        need = {1: "wooden_pickaxe", 2: "stone_pickaxe", 3: "iron_pickaxe", 4: "diamond_pickaxe"}[rule["tier"]]
        raise Illegal(f"mining {block} needs a {need} (or better) in inventory; best pickaxe tier held is {tier}")
    stochastic = rule.get("stochastic", False)
    for item, per in rule["drops"].items():
        got = math.floor(n * per + 1e-9)
        s.give(item, got)
    if stochastic:
        notes.append(STOCHASTIC_NOTE)
    if not rule.get("verified"):
        notes.append(f"drop rule for {block} unverified ({rule.get('source')})")
    return s.cost(([f"mine_{block}_diamond"] if block == "obsidian" else []) + [f"mine_{block}", "mine_other", "mine"], n)


def _craft(s, a, notes):
    item = _id(a, "item", "craft")
    n = _int(a.get("count", 1), "count")
    rec = R.recipe_for(item)
    if rec is None:
        raise Illegal(f"no known 1.16.5 recipe for {item!r} in the simulator")
    if rec["needs_table"] and not (s.table_placed or s.has("crafting_table")):
        raise Illegal(f"crafting {item} needs a crafting_table in inventory or placed")
    crafts = math.ceil(n / rec["output_count"]) if n else 0
    prefer_log = item[: -len("_planks")] + "_log" if item.endswith("_planks") else None
    ingredients = dict(rec["ingredients"])
    if item.endswith("_bed") and item != "bed":
        # 1.16: a coloured bed needs 3 wool of that colour
        ingredients.pop("any_wool", None)
        ingredients[item[: -len("_bed")] + "_wool"] = 3
    if item.endswith("_planks") and item != "planks":
        wood = item[: -len("_planks")]
        src = wood + ("_stem" if wood in ("crimson", "warped") else "_log")
        ingredients.pop("any_log", None)
        ingredients[src] = 1
    for ing, q in ingredients.items():
        need = q * crafts
        have = s.count_group(ing) if ing.startswith("any_") else s.inv.get(ing, 0)
        if have < need:
            raise Illegal(f"crafting {n} {item} ({crafts} craft(s)) needs {need} {ing}, have {have}")
    for ing, q in ingredients.items():
        if ing.startswith("any_"):
            s.take_group(ing, q * crafts, prefer=prefer_log)
        else:
            s.take(ing, q * crafts)
    s.give(item, crafts * rec["output_count"])
    if crafts * rec["output_count"] != n:
        notes.append(f"{crafts} craft(s) produce {crafts * rec['output_count']} {item}")
    return s.cost(["craft"], crafts)


def _smelt(s, a, notes):
    item = _id(a, "item", "smelt")
    n = _int(a.get("count", 1), "count")
    fuel = _id(a, "fuel", "smelt")
    rec = R.SMELTING.get(item)
    if rec is None:
        raise Illegal(f"no known smelting recipe producing {item!r}")
    if not (s.furnace_placed or s.has("furnace")):
        raise Illegal("smelting needs a furnace in inventory or placed")
    inp = rec["input"]
    have = s.count_group(inp) if inp.startswith("any_") else s.inv.get(inp, 0)
    if have < n:
        raise Illegal(f"smelting {n} {item} needs {n} {inp}, have {have}")
    if not fuel:
        raise Illegal("smelt needs 'fuel'")
    fkey = fuel if fuel in R.FUEL_ITEMS_PER_UNIT else next(
        (g for g in ("any_log", "any_planks") if R.ingredient_matches(g, fuel)), None)
    if fkey is None:
        raise Illegal(f"{fuel!r} is not a known furnace fuel")
    units = math.ceil(n / R.FUEL_ITEMS_PER_UNIT[fkey]["items"]) if n else 0
    fuel_have = s.inv.get(fuel, 0)
    if inp.startswith("any_") and R.ingredient_matches(inp, fuel):
        fuel_have -= n
    if fuel_have < units:
        raise Illegal(f"smelting {n} items needs {units} {fuel} as fuel, have {max(fuel_have, 0)}")
    if inp.startswith("any_"):
        s.take_group(inp, n)
    else:
        s.take(inp, n)
    s.take(fuel, units)
    if fuel == "lava_bucket":
        s.give("bucket", units)
    s.give(item, n)
    if s.has("furnace") and not s.furnace_placed:
        s.take("furnace", 1)
        s.furnace_placed = True
        notes.append("furnace placed")
    return s.cost(["smelt"], n)


def _loot_chest(s, a, notes):
    name = a.get("at")
    if not isinstance(name, str) or name not in s.chests:
        raise Illegal(f"no chest {name!r} in state.world.chests")
    if name in s.looted:
        raise Illegal(f"chest {name!r} was already looted")
    t = s.ensure_at(name, notes)
    for item, c in (s.chests[name] or {}).items():
        s.give(item, int(_num(c)))
    s.looted.append(name)
    return t + s.cost(["loot_chest"])


def _travel(s, a, notes):
    to = a.get("to")
    want_dim = a.get("dimension")
    if want_dim is not None and not isinstance(want_dim, str):
        raise Illegal(f"travel 'dimension' must be a string (got {want_dim!r})")
    if isinstance(to, str):
        loc = s.locs.get(to)
        if not isinstance(loc, dict):
            raise Illegal(f"travel target {to!r} is not in state.known_locations")
        tdim = s.loc_dim(loc)
        target = _pos(loc)
    else:
        target = _pos(to)
        if target is None:
            raise Illegal("travel 'to' must be a known_locations name or {x,y,z}")
        tdim = (to.get("dimension") if isinstance(to, dict) else None) or s.dim
    if want_dim and want_dim != s.dim:
        raise Illegal(f"travel to dimension {want_dim} while in {s.dim}: change dimension with enter_portal")
    if tdim != s.dim:
        raise Illegal(f"travel target {to!r} is in {tdim} but you are in {s.dim}: change dimension with enter_portal")
    return s.move_to(target, notes)


def _build_portal(s, a, notes):
    method = a.get("method")
    if s.pos is None:
        raise Illegal("build_portal needs a known current position")
    if s.dim == "the_end":
        raise Illegal("nether portals cannot be lit in the_end")
    if method == "bucket_lava":
        if not s.has("water_bucket"):
            raise Illegal("bucket_lava portal needs a water_bucket")
        pool, _ = s.structure_here("lava_pool")
        if pool is not None:
            notes.append(f"cast in place over lava_pool {pool!r} (water_bucket only, SCHEMA v2)")
        elif not (s.has("bucket") or s.has("lava_bucket")):
            raise Illegal("bucket_lava portal away from a lava_pool needs a bucket (or lava_bucket) to carry lava")
        else:
            notes.append("no lava_pool here: lava carried in a bucket, source assumed nearby")
        s.tag("lava_pool_portal")
    elif method == "chest_obsidian":
        need = R.NETHER_PORTAL["frame_obsidian_cornerless"]
        if not s.has("obsidian", need):
            raise Illegal(f"chest_obsidian portal needs {need} obsidian, have {s.inv.get('obsidian', 0)}")
        s.take("obsidian", need)
        s.tag("chest_obsidian_portal")
    elif method == "mine_obsidian":
        if not s.has("diamond_pickaxe"):
            raise Illegal("mine_obsidian portal needs a diamond_pickaxe")
        need = R.NETHER_PORTAL["frame_obsidian_cornerless"]
        if not s.has("obsidian", need):
            raise Illegal(f"mine_obsidian portal needs {need} obsidian (mine it first), have {s.inv.get('obsidian', 0)}")
        s.take("obsidian", need)
        s.tag("mine_obsidian_portal")
    elif method == "complete_ruined":
        name, st = s.structure_here("ruined_portal")
        if st is None:
            raise Illegal("complete_ruined needs a ruined_portal structure at the current location")
        missing = None
        for k in ("missing_obsidian", "obsidian_needed", "missing_blocks"):
            if isinstance(st.get(k), (int, float)):
                missing = int(st[k])
        if missing is None:
            for k in ("existing_obsidian", "frame_blocks", "obsidian_present"):
                if isinstance(st.get(k), (int, float)):
                    missing = max(0, R.NETHER_PORTAL["frame_obsidian_cornerless"] - int(st[k]))
        if missing is None:
            txt = str(st.get("notes", ""))
            missing = ruined_missing_from_blocks(txt)
            if missing is not None:
                notes.append(f"ruined portal {name!r}: {missing} missing obsidian computed from the block list "
                             f"(best 2x3 cornerless frame; crying obsidian never counts)")
            else:
                m = re.search(r"(\d+)\s*(?:obsidian\s*)?(?:blocks?\s*)?(?:missing|needed)", txt, re.I) or \
                    re.search(r"(?:missing|needs?)\s*(\d+)", txt, re.I)
                if m:
                    missing = int(m.group(1))
        if missing is None:
            raise Illegal(f"ruined portal {name!r}: missing-obsidian count unknown (task data error: give "
                          f"structures[{name!r}].missing_obsidian or a block list); not assumed 0")
        if not s.has("obsidian", missing):
            raise Illegal(f"completing ruined portal {name!r} needs {missing} obsidian, have {s.inv.get('obsidian', 0)}")
        if missing:
            s.take("obsidian", missing)
        notes.append(f"ruined portal {name!r}: placed {missing} obsidian")
        s.tag("ruined_portal_completion")
    else:
        raise Illegal(f"unknown build_portal method {method!r}")
    s.portals.append({"x": s.pos["x"], "z": s.pos["z"], "dimension": s.dim, "lit": False, "method": method})
    return s.cost([f"build_portal_{method}", "build_portal"])


_BLOCKS_RE = re.compile(r"(crying\s+)?obsidian\s+at\s+((?:\(\s*-?\d+\s*,\s*-?\d+\s*\)(?:\s*,\s*|\s+and\s+|\s*)?)+)", re.I)
_PAIR_RE = re.compile(r"\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)")


def ruined_missing_from_blocks(text):
    """Missing obsidian for the best 4x5 cornerless frame, from a block list in the notes.

    Notes list '(a, b)' in-plane coordinates for 'obsidian at ...' and 'crying obsidian at ...'.
    A frame (2 wide x 3 tall interior) reuses obsidian on its 10 frame cells; a frame cell or
    interior cell holding crying obsidian, or an interior cell holding obsidian, rules that
    placement out (removing them needs a diamond pickaxe). Returns None if no list is found.
    """
    obs, cry = set(), set()
    for m in _BLOCKS_RE.finditer(text or ""):
        pts = {(int(a), int(b)) for a, b in _PAIR_RE.findall(m.group(2))}
        (cry if m.group(1) else obs).update(pts)
    if not obs and not cry:
        return None
    allp = obs | cry
    a_lo, a_hi = min(p[0] for p in allp) - 4, max(p[0] for p in allp) + 1
    b_lo, b_hi = min(p[1] for p in allp) - 5, max(p[1] for p in allp) + 1
    best = None
    for a0 in range(a_lo, a_hi + 1):
        for b0 in range(b_lo, b_hi + 1):
            frame = [(a0 + 1, b0), (a0 + 2, b0), (a0 + 1, b0 + 4), (a0 + 2, b0 + 4)] + \
                    [(a0, b0 + k) for k in (1, 2, 3)] + [(a0 + 3, b0 + k) for k in (1, 2, 3)]
            interior = [(a0 + i, b0 + k) for i in (1, 2) for k in (1, 2, 3)]
            if any(c in cry for c in frame) or any(c in allp for c in interior):
                continue
            need = sum(1 for c in frame if c not in obs)
            if best is None or need < best:
                best = need
    return best


def _portal_here(s):
    for p in s.portals:
        if p["dimension"] == s.dim and _hdist(p, s.pos) is not None and _hdist(p, s.pos) <= NEAR_BLOCKS:
            return p
    return None


def _light_portal(s, a, notes):
    w = a.get("with")
    if w not in ("flint_and_steel", "fire_charge"):
        raise Illegal(f"light_portal 'with' must be flint_and_steel or fire_charge (got {w!r})")
    if not s.has(w):
        raise Illegal(f"light_portal with {w} but no {w} in inventory")
    p = _portal_here(s) if s.pos else None
    if p is None:
        raise Illegal("light_portal: no built portal frame at the current position")
    if p["lit"]:
        notes.append("portal already lit")
    p["lit"] = True
    if w == "fire_charge":
        s.take("fire_charge", 1)
    return s.cost(["light_portal"])


def _enter_portal(s, a, notes):
    if s.pos is None:
        raise Illegal("enter_portal needs a known current position")
    p = _portal_here(s)
    if p is not None and p["lit"]:
        if s.dim == "overworld":
            new_dim, f = "the_nether", 1 / R.NETHER_PORTAL["coordinate_scale"]
        elif s.dim == "the_nether":
            new_dim, f = "overworld", R.NETHER_PORTAL["coordinate_scale"]
        else:
            raise Illegal("nether portal in the_end")
        newpos = {"x": s.pos["x"] * f, "y": s.pos.get("y", 0), "z": s.pos["z"] * f}
        notes.append(f"{s.dim} ({s.pos['x']:.0f}, {s.pos['z']:.0f}) -> {new_dim} ({newpos['x']:.1f}, {newpos['z']:.1f})")
        s.dim, s.pos = new_dim, newpos
        s.portals.append({"x": newpos["x"], "z": newpos["z"], "dimension": new_dim, "lit": True, "method": "linked"})
        return s.cost(["enter_portal_nether", "enter_portal"])
    if p is not None:
        raise Illegal("enter_portal: the portal at the current position is not lit")
    name, st = s.structure_here("end_portal")
    if st is not None:
        filled, active = s.end_portal_state(name, st)
        if not active:
            raise Illegal(f"enter_portal: End portal {name!r} is not active ({filled}/12 frames filled)")
        s.dim = "the_end"
        s.pos = {"x": 100.0, "y": 49.0, "z": 0.0}  # obsidian platform
        notes.append(f"entered End portal {name!r} -> the_end platform (100, 49, 0)")
        return s.cost(["enter_portal_end", "enter_portal"])
    if s.dim == "the_end":
        # SCHEMA v2 section 7: a full_route plan finishes with enter_portal in the_end after the dragon is dead
        if not s.dragon_killed:
            raise Illegal("enter_portal in the_end: the exit portal only opens after the ender dragon is dead "
                          f"(beds exploded in the_end so far: {s.beds_in_end}, need {s.dragon_beds_required})")
        s.finished = True
        s.dim = "overworld"
        notes.append("entered the End exit portal after the dragon died: run complete")
        return s.cost(["enter_portal_exit", "enter_portal"])
    raise Illegal(f"enter_portal: no lit Nether portal or active End portal at the current position in {s.dim}")


def _barter(s, a, notes):
    n = _int(a.get("gold_ingots", 0), "gold_ingots")
    if s.dim != "the_nether":
        raise Illegal(f"barter needs piglins (the_nether); you are in {s.dim}")
    if not any(s.has(g) for g in R.GOLD_ARMOR):
        raise Illegal("barter without gold armor: piglins turn hostile (need a golden helmet/chestplate/leggings/boots)")
    if not s.has("gold_ingot", n):
        raise Illegal(f"barter {n} gold_ingot but have {s.inv.get('gold_ingot', 0)}")
    s.take("gold_ingot", n)
    table = R.barter_table_for(s.task.get("version"))
    got = []
    for item in R.BARTER_TRACKED_ITEMS:
        q = math.floor(n * R.barter_expected_per_ingot(item, table) + 1e-9)
        if q:
            s.give(item, q)
            got.append(f"{q} {item}")
    notes.append(STOCHASTIC_NOTE)
    notes.append(f"barter table {table} (unverified); yields: " + (", ".join(got) or "nothing"))
    s.tag("piglin_barter")
    return s.cost(["barter"]) + s.cost(["barter_per_ingot"], n) if "barter_per_ingot" in s.costs else s.cost(["barter"], n)


def _kill(s, a, notes):
    mob = _id(a, "mob", "kill")
    n = _int(a.get("count", 1), "count")
    info = R.MOBS.get(mob)
    if info is None:
        notes.append(f"mob {mob!r} not in rules table: no drops, rules unchecked")
        info = {"hostile": False, "dimension": None, "drops": {}}
    if info["hostile"] and s.peaceful:
        raise Illegal(f"{mob} is hostile and does not spawn on Peaceful")
    if info.get("dimension") and info["dimension"] != s.dim:
        raise Illegal(f"{mob} is found in {info['dimension']}, you are in {s.dim}")
    for item, per in info["drops"].items():
        s.give(item, math.floor(n * per + 1e-9))
    if mob == "ender_dragon" and n >= 1:
        s.dragon_killed = True
    if any(per != int(per) for per in info["drops"].values()):
        notes.append(STOCHASTIC_NOTE)
    return s.cost([f"kill_{mob}_melee", f"kill_{mob}", "kill"], n)


def _throw_eye(s, a, notes):
    if s.dim != "overworld":
        raise Illegal(f"an eye of ender cannot be thrown in {s.dim} (no stronghold there; Java 1.16.5)")
    if not s.has("ender_eye"):
        raise Illegal("throw_eye with no ender_eye in inventory")
    t = 0.0
    at = _pos(a.get("at"))
    if at is not None:
        if s.pos is not None and _hdist(s.pos, at) > 1.0:
            t += s.move_to(at, notes, implicit=True)
        s.pos = at
    s.throws.append(dict(s.pos) if s.pos else None)
    s.eyes_thrown += 1
    chance = R.EYE_OF_ENDER["break_chance"]
    broken = math.floor(s.eyes_thrown * chance + 1e-9) - s.eyes_broken
    if broken > 0:
        s.take("ender_eye", broken)
        s.eyes_broken += broken
        notes.append(f"eye broke (expected break rate {chance}, cumulative {s.eyes_broken}/{s.eyes_thrown})")
    else:
        notes.append(f"eye dropped back (expected break rate {chance}, cumulative {s.eyes_broken}/{s.eyes_thrown})")
    notes.append(STOCHASTIC_NOTE)
    return t + s.cost(["throw_eye"])


def _place_eyes(s, a, notes):
    n = _int(a.get("count", 1), "count")
    name, st = s.structure_here("end_portal")
    if st is None:
        raise Illegal("place_eyes: no End portal at the current position")
    filled, active = s.end_portal_state(name, st)
    empty = R.END_PORTAL["frames"] - filled
    if n > empty:
        raise Illegal(f"place_eyes {n} but End portal {name!r} has only {empty} empty frames")
    if not s.has("ender_eye", n):
        raise Illegal(f"place_eyes {n} but only {s.inv.get('ender_eye', 0)} ender_eye held")
    s.take("ender_eye", n)
    s.end_frames[name] = filled + n
    if s.end_frames[name] >= R.END_PORTAL["frames"]:
        s.end_active[name] = True
        notes.append(f"End portal {name!r} activated")
    pts = [p for p in s.throws if p]
    distinct = {(round(p["x"]), round(p["z"])) for p in pts}
    if len(pts) >= 2 and len(distinct) >= 2:
        s.tag("triangulation")
    return s.cost(["place_eyes"], n)


def _bed_explode(s, a, notes):
    n = _int(a.get("count", 1), "count")
    if s.dim not in R.BED_EXPLODES_IN:
        raise Illegal("beds only explode in the_nether/the_end")
    have = s.count_group("any_bed")
    if have < n:
        raise Illegal(f"bed_explode {n} but only {have} bed(s) held")
    s.take_group("any_bed", n)
    extra = 0.0
    if s.dim == "the_end":
        s.beds_in_end += n
        if not s.dragon_killed and s.beds_in_end >= s.dragon_beds_required:
            s.dragon_killed = True
            notes.append(f"dragon killed: {s.beds_in_end} bed explosions in the_end >= rules.dragon_beds_required "
                         f"({s.dragon_beds_required})")
            if "end_fight_beds" in s.costs:  # SCHEMA v3: fixed cost for a whole bed kill
                notes.append("priced with end_fight_beds (fixed cost for the bed kill)")
                return s.cost(["end_fight_beds"])
    s.tag("bed_explosion")
    if "end_fight_beds" in s.costs and s.dim == "the_end":
        return 0.0  # included in the fixed end_fight_beds cost
    return s.cost(["bed_explode"], n) + extra


def _reset(s, a, notes):
    s.reset = True
    notes.append("reset: plan ends")
    return s.cost(["reset"])


DISPATCH = {
    "mine": _mine,
    "craft": _craft,
    "smelt": _smelt,
    "loot_chest": _loot_chest,
    "travel": _travel,
    "build_portal": _build_portal,
    "light_portal": _light_portal,
    "enter_portal": _enter_portal,
    "barter": _barter,
    "kill": _kill,
    "throw_eye": _throw_eye,
    "place_eyes": _place_eyes,
    "bed_explode": _bed_explode,
    "reset": _reset,
}

def simulate(task: dict, plan: dict, costs: dict | None = None) -> SimResult:
    if costs is None:
        costs = load_costs()
    rules = costs.get("__rules__") or costs.get("rules") if isinstance(costs, dict) else None
    costs = costs.get("actions", costs) if isinstance(costs, dict) else {}
    if rules:
        costs = {**costs, "__rules__": rules}
    costs = {**DEFAULT_COSTS, **costs}  # keys missing from a partial table fall back to defaults
    s = _Sim(task or {}, costs)
    actions = plan.get("actions") if isinstance(plan, dict) else None
    if not isinstance(actions, list):
        return SimResult(False, "plan has no 'actions' list", None, 0.0, [], _final(s, 0.0), [])
    steps, total = [], 0.0
    legal, reason, failed = True, None, None
    for i, a in enumerate(actions):
        if s.reset:
            steps.append({"index": i, "action": a.get("action") if isinstance(a, dict) else None,
                          "ok": True, "time_s": 0.0, "note": "ignored: after reset"})
            continue
        notes = []
        if not isinstance(a, dict):
            legal, reason, failed = False, f"step {i}: action is not an object ({a!r})", i
            steps.append({"index": i, "action": None, "ok": False, "time_s": 0.0, "note": reason})
            break
        try:
            t = round(s.do(a, notes), 3)
        except Exception as e:  # Illegal, or malformed parameters that broke an action
            legal, failed = False, i
            msg = str(e) if isinstance(e, Illegal) else f"malformed parameters ({type(e).__name__}: {e})"
            e = msg
            act_name = a.get("action")
            reason = f"step {i} ({act_name if isinstance(act_name, str) else repr(act_name)}): {msg}"
            steps.append({"index": i, "action": a.get("action"), "ok": False, "time_s": 0.0,
                          "note": "; ".join(notes + [str(e)])})
            break
        total += t
        steps.append({"index": i, "action": a.get("action"), "ok": True, "time_s": t, "note": "; ".join(notes)})
    total = round(total, 3)
    return SimResult(legal, reason, failed, total, steps, _final(s, total), list(s.techniques))


def _final(s, total):
    return {
        "dimension": s.dim,
        "position": s.pos,
        "inventory": dict(sorted(s.inv.items())),
        "looted_chests": list(s.looted),
        "portals": copy.deepcopy(s.portals),
        "end_portal_frames": dict(s.end_frames),
        "eye_throws": [p for p in s.throws],
        "reset": s.reset,
        "dragon_killed": s.dragon_killed,
        "beds_exploded_in_end": s.beds_in_end,
        "elapsed_s": round(s.elapsed0 + total, 3),
    }


if __name__ == "__main__":  # python -m splitcheck.sim <task.json> <plan.json>
    import sys
    t = json.loads(Path(sys.argv[1]).read_text())
    p = json.loads(Path(sys.argv[2]).read_text())
    r = simulate(t, p)
    print(json.dumps(r.__dict__, indent=2, default=str))
