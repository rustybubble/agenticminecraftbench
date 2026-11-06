"""Deterministic micro + safety detectors over a normalized Timeline (no LLM; same input -> same output).

Each detector is a pure function f(tl: Timeline, ctx: dict) -> list[Finding]. Every Finding cites log
lines, a time interval (seconds since run start) and a cost_s attribution. runeval merges overlapping
intervals, so detectors may overlap without double counting in the score.

Logic is reused from logeval.py (Layer B v1): item sets, regexes, loop/no-progress rules, overshoot rule.
Decision (seed-knowledge) detectors live in detectors_seed.py and are merged into REGISTRY lazily.

ctx keys (all optional): difficulty (str), seed (dict from seedfeatures.load_seed_features).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .logeval import (CRAFT_RE, FOOD, NEEDED, LOOP_MIN, OVERSHOOT_MARGIN, OVERSHOOT_REACH, PLACE_RE,
                      RECOVER_RE, UTILITY, WAIT_RE, WORLD_EFFECT_RE, COORD_RE, _norm_dim)

try:  # binding contract types
    from .timeline import Sample, Timeline  # noqa: F401  (re-exported for callers/tests)
except ImportError:  # pragma: no cover - only if timeline.py is absent
    @dataclass
    class Sample:  # type: ignore[no-redef]
        t: float
        line: int
        pos: tuple | None = None
        dim: str | None = None
        inv: dict = field(default_factory=dict)
        health: float | None = None
        food: float | None = None
        in_water: bool | None = None
        in_lava: bool | None = None
        action: str | None = None
        action_failed: bool | None = None
        stage: str | None = None
        kind: str | None = None
        action_desc: str | None = None
        result: str | None = None

    @dataclass
    class Timeline:  # type: ignore[no-redef]
        source: str
        samples: list = field(default_factory=list)
        events: list = field(default_factory=list)
        knowledge: dict = field(default_factory=dict)
        meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------- thresholds (all documented)
THRESHOLDS = {
    "no_progress_move_blocks": 0.01,   # logeval rule: position unchanged within this (3D) distance
    "idle_min_s": 3.0,                 # no position/inventory change for at least this long
    "idle_move_blocks": 0.5,           # movement below this counts as "no position change"
    "portal_transfer_s": 4.0,          # 1.16.5 survival nether-portal wait (80 ticks), excused from idle
    "idle_merge_jump_blocks": 1.0,     # adjacent idle windows split by a smaller jump merge (stuck drift)
    # idle is not reported in the_end: waiting for the dragon to perch is part of the route
    "loop_min": LOOP_MIN,              # identical consecutive actions (>= half unproductive)
    "oscillation_cell_blocks": 2.0,    # cell size for revisit detection (x,z)
    "oscillation_min_visits": 3,       # entries into the same cell ...
    "oscillation_window_s": 30.0,      # ... within this window, inventory unchanged
    "oscillation_min_excursion": 2.0,  # must leave the cell centre by this much between visits
    "water_mining_slowdown": 5.0,      # 1.16.5: underwater w/o Aqua Affinity mines 5x slower
    "water_context_blocks": 4.0,       # agent: mining within this of where a swim action ended
    "lost_drop_window_s": 5.0,         # mined item must arrive within this or by the next result
    "food_full": 20.0,                 # hunger bar full
    "materials_slack": 4,              # items allowed beyond what later crafts/placements consumed
    "overshoot_reach": OVERSHOOT_REACH,     # "reached" = within this many blocks (horizontal)
    "overshoot_margin": OVERSHOOT_MARGIN,   # then distance grows by more than this
    "overshoot_return_window_s": 60.0,      # human/any: came back within reach inside this window
    "overshoot_min_excursion": 8.0,         # ... after getting at least this far away
    "damage_group_s": 2.0,             # health drops closer than this are one damage event
    "fall_min_drop_blocks": 4.0,       # y drop within fall_lookback_s preceding damage => fall
    "fall_lookback_s": 3.0,
    "death_return_radius": 10.0,       # back within this of the death spot => recovery done
    "death_default_cost_s": 60.0,      # cost when the player never returns (capped at run end)
    # fixed per-unit estimates used only when the log has no action duration (human logs)
    "est_break_s": {"crafting_table": 3.75, "furnace": 1.75, "default": 2.0},
    "est_craft_s": 2.0,
    "est_gather_s": {"wood": 2.0, "stone": 1.2},
}

POSITIVE_PICKAXE_BLOCKS = {"cobblestone", "stone", "coal", "iron_ore", "gold_ore", "obsidian",
                           "netherrack", "blackstone", "basalt", "diamond", "redstone", "lapis_lazuli",
                           "gilded_blackstone", "nether_gold_ore", "gold_nugget", "quartz", "end_stone",
                           "cobbled_deepslate", "andesite", "diorite", "granite"}
SHOVEL_BLOCKS = {"dirt", "gravel", "sand", "soul_sand", "soul_soil", "clay_ball", "red_sand", "flint"}
WOOD_LOG_RE = re.compile(r"(_log|_stem|_wood|_hyphae)$")
MINE_RE = re.compile(r"\b(mine|mining|dig|break|collect|chop|harvest|gather)", re.I)
WATER_RE = re.compile(r"water|swim|underwater|submerged|river|ocean|lake", re.I)
MAGMA_RE = re.compile(r"magma", re.I)
TRAVEL_RE = re.compile(r"\b(path|walk|follow|travel|go|approach|route|head|move|bridge|pillar)\b|_travel|go_", re.I)
TOOL_RE = re.compile(r"^(wooden|stone|iron|golden|diamond|netherite)_(pickaxe|axe|shovel|sword|hoe)$")
TIER = {"wooden": 0, "golden": 0, "stone": 1, "iron": 2, "diamond": 3, "netherite": 4}
STONE_ITEMS = {"cobblestone", "blackstone", "cobbled_deepslate"}
# what a mined block drops (for lost_drop expectations parsed from action text)
DROP = {"stone": "cobblestone", "grass_block": "dirt", "coal_ore": "coal", "diamond_ore": "diamond",
        "gravel": "gravel", "nether_gold_ore": "gold_nugget", "nether_quartz_ore": "quartz"}
ITEM_TOKEN_RE = re.compile(r"[a-z][a-z_]+[a-z]")


@dataclass
class Finding:
    code: str
    category: str      # 'micro' | 'decision' | 'safety' | 'claim'
    severity: str      # 'high' | 'medium' | 'low'
    t_start: float
    t_end: float
    cost_s: float
    lines: list
    message: str
    evidence: dict = field(default_factory=dict)


# ---------------------------------------------------------------- helpers
def _r(x):
    return round(float(x), 3)


def _is_action(s) -> bool:
    return s.action is not None and getattr(s, "kind", None) != "decision"


def _text(s) -> str:
    return f"{s.action or ''} {getattr(s, 'action_desc', None) or ''}"


def _d3(a, b):
    return math.dist([a[0], a[1] or 0, a[2]], [b[0], b[1] or 0, b[2]])


def _dh(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def _delta(b: dict, a: dict) -> dict:
    out = {}
    for k in set(b) | set(a):
        d = a.get(k, 0) - b.get(k, 0)
        if d:
            out[k] = d
    return dict(sorted(out.items()))


def _difficulty(tl, ctx):
    d = ((ctx or {}).get("difficulty") or tl.meta.get("difficulty")
         or ((ctx or {}).get("seed") or {}).get("difficulty"))
    return str(d or "").lower()


def _actions(tl):
    """[(i, sample, start_t, dur, before)] for every action sample. Start = the preceding decision
    sample after the previous action (agent: decision is logged when the model answered, so API
    latency is excluded), else the previous action sample (or run start). `before` = the sample
    whose state precedes the action (decision if present, else previous sample with a position/inv)."""
    out, prev_action_t, pending_dec = [], 0.0, None
    prev_any = None
    for i, s in enumerate(tl.samples):
        if getattr(s, "kind", None) == "decision":
            pending_dec = s
            prev_any = s
            continue
        if _is_action(s):
            start = pending_dec.t if pending_dec is not None else (prev_action_t if out else
                                                                   (prev_any.t if prev_any else 0.0))
            before = pending_dec if pending_dec is not None else prev_any
            out.append((i, s, start, _r(max(0.0, s.t - start)), before))
            prev_action_t, pending_dec = s.t, None
        prev_any = s
    return out


def _api_waits(tl):
    """Intervals [result.t, next decision.t] = waiting for the model (agent logs only)."""
    out, last_res = [], None
    for s in tl.samples:
        k = getattr(s, "kind", None)
        if k == "result":
            last_res = s
        elif k == "decision" and last_res is not None:
            if s.t > last_res.t:
                out.append((last_res.t, s.t))
            last_res = None
    return out


def _overlap(a0, a1, ivs):
    return sum(max(0.0, min(a1, b1) - max(a0, b0)) for b0, b1 in ivs)


def _inv_series(tl):
    """Samples carrying an inventory, deduped so consecutive deltas are meaningful."""
    out = []
    for s in tl.samples:
        # a sample with an empty inventory after a non-empty one usually means "not reported"
        # (e.g. agent position_sample); keep only the first empty one (true empty start).
        if s.inv is None or (not s.inv and (out or getattr(s, "kind", None) == "position_sample"
                                            and tl.source == "agent")):
            continue
        out.append(s)
    return out


def _wood_units(item, n):
    if WOOD_LOG_RE.search(item):
        return n * 1.0
    if item.endswith("_planks"):
        return n / 4.0
    if item == "stick":
        return n / 8.0
    return 0.0


def _dur_lookup(tl):
    acts = _actions(tl)
    return {s.line: (start, dur) for _, s, start, dur, _ in acts}


def _prev_t(tl, idx):
    return tl.samples[idx - 1].t if idx > 0 else 0.0


# ---------------------------------------------------------------- micro detectors
def failed_action(tl, ctx):
    out = []
    for _, s, start, dur, _b in _actions(tl):
        if s.action_failed:
            out.append(Finding("failed_action", "micro", "high" if dur >= 30 else "medium", start, s.t, dur,
                               [s.line], f"line {s.line}: action '{s.action}' failed "
                               f"({(getattr(s, 'result', None) or 'FAILED')[:80]}); {dur} s lost",
                               {"action": s.action, "result": getattr(s, "result", None)}))
    return out


def no_progress(tl, ctx):
    out, eps = [], THRESHOLDS["no_progress_move_blocks"]
    for _, s, start, dur, b in _actions(tl):
        if s.action_failed or b is None or b.pos is None or s.pos is None:
            continue
        txt = _text(s)
        if WORLD_EFFECT_RE.search(txt) or WAIT_RE.search(txt):
            continue
        if _d3(b.pos, s.pos) < eps and (b.inv or {}) == (s.inv or {}):
            out.append(Finding("no_progress", "micro", "medium", start, s.t, dur, [b.line, s.line],
                               f"lines {b.line}-{s.line}: '{s.action}' succeeded but position and inventory "
                               f"are unchanged; {dur} s lost", {"action": s.action, "pos": s.pos}))
    return out


def idle(tl, ctx):
    """No position (> idle_move_blocks) or inventory change for >= idle_min_s, API-wait time excluded.
    Explicit wait/idle actions are flagged too. Windows containing world-effect actions are skipped."""
    out, waits = [], _api_waits(tl)
    eps, min_s = THRESHOLDS["idle_move_blocks"], THRESHOLDS["idle_min_s"]
    pts = [s for s in tl.samples if s.pos is not None]
    wins = []  # (i, j) index ranges into pts
    i = 0
    while i < len(pts):
        a, j = pts[i], i
        while (j + 1 < len(pts) and pts[j + 1].dim == a.dim and _d3(pts[j + 1].pos, a.pos) <= eps
               and (pts[j + 1].inv or {}) == (a.inv or {})):
            j += 1
        if j > i:
            if (wins and wins[-1][1] == i - 1 and (pts[i - 1].inv or {}) == (a.inv or {})
                    and _d3(pts[i - 1].pos, pts[i].pos) < THRESHOLDS["idle_merge_jump_blocks"]):
                wins[-1] = (wins[-1][0], j)  # slow drift (stuck against a block): one episode
            else:
                wins.append((i, j))
        i = j + 1
    for i, j in wins:
        a, b = pts[i], pts[j]
        if True:
            span = b.t - a.t
            seg = [s for s in tl.samples if a.line <= s.line <= b.line]
            world = any(_is_action(s) and (WORLD_EFFECT_RE.search(_text(s)) or WAIT_RE.search(_text(s)))
                        for s in seg)
            # standing still while mining/crafting is work, not idle: the action in progress is a
            # mine/craft (agent), or the very next sample gains an item (human: block finished breaking)
            cur = next((s for s in tl.samples if s.line > a.line and _is_action(s)), None)
            if cur is not None and cur.t - b.t <= 1.5 and (MINE_RE.search(_text(cur)) or CRAFT_RE.search(_text(cur))):
                world = True
            if j + 1 < len(pts) and pts[j + 1].t - b.t <= 1.5 and any(
                    v > 0 for v in _delta(b.inv or {}, pts[j + 1].inv or {}).values()):
                world = True
            cost = span - _overlap(a.t, b.t, waits)
            portal = j + 1 < len(pts) and _norm_dim(pts[j + 1].dim) != _norm_dim(b.dim)
            if portal:  # standing in a nether portal for the 80-tick transfer is required
                cost -= THRESHOLDS["portal_transfer_s"]
            cost = _r(max(0.0, cost))
            if not world and cost >= min_s and _norm_dim(a.dim) != "the_end":
                out.append(Finding("idle", "micro", "medium" if cost >= 15 else "low", a.t, b.t, cost,
                                   [a.line, b.line], f"lines {a.line}-{b.line}: no movement or inventory change "
                                   f"for {_r(span)} s at {tuple(round(v, 1) for v in a.pos if v is not None)}"
                                   f" ({cost} s excluding API waits)",
                                   {"pos": a.pos, "span_s": _r(span), "api_wait_s": _r(span - cost)}))
    for _, s, start, dur, _b in _actions(tl):
        if WAIT_RE.search(_text(s)) and dur > 0 and _norm_dim(s.dim) != "the_end":
            out.append(Finding("idle", "micro", "low", start, s.t, dur, [s.line],
                               f"line {s.line}: explicit wait action '{s.action}'; {dur} s",
                               {"action": s.action, "explicit_wait": True}))
    return out


def action_loop(tl, ctx):
    """logeval rule: >= loop_min identical consecutive actions, at least half failed/no-progress."""
    acts = _actions(tl)
    eps = THRESHOLDS["no_progress_move_blocks"]

    def bad(row):
        _, s, _, _, b = row
        if s.action_failed:
            return True
        return (b is not None and b.pos is not None and s.pos is not None and _d3(b.pos, s.pos) < eps
                and (b.inv or {}) == (s.inv or {}))

    out, i = [], 0
    while i < len(acts):
        j = i
        while j + 1 < len(acts) and acts[j + 1][1].action == acts[i][1].action:
            j += 1
        n = j - i + 1
        if n >= THRESHOLDS["loop_min"]:
            seg = acts[i:j + 1]
            nb = sum(1 for r in seg if bad(r))
            if nb * 2 >= n:
                cost = _r(sum(r[3] for r in seg))
                out.append(Finding("action_loop", "micro", "high" if n >= 5 else "medium", seg[0][2],
                                   seg[-1][1].t, cost, [r[1].line for r in seg],
                                   f"lines {seg[0][1].line}-{seg[-1][1].line}: '{acts[i][1].action}' repeated "
                                   f"{n}x in a row, {nb} failed/no-progress; {cost} s",
                                   {"action": acts[i][1].action, "count": n, "unproductive": nb}))
        i = j + 1
    return out


def oscillation(tl, ctx):
    c = THRESHOLDS["oscillation_cell_blocks"]
    pts = [s for s in tl.samples if s.pos is not None]
    entries, prev_cell = [], None  # (idx in pts, cell)
    for k, s in enumerate(pts):
        cell = (s.dim, math.floor(s.pos[0] / c), math.floor(s.pos[2] / c))
        if cell != prev_cell:
            entries.append((k, cell))
        prev_cell = cell
    out, used, until = [], set(), -math.inf
    for e_i, (k, cell) in enumerate(entries):
        a = pts[k]
        if e_i in used or a.t <= until:  # one finding per back-and-forth episode
            continue
        if _norm_dim(a.dim) == "the_end":  # circling the fountain while the dragon perches is the route
            continue
        centre = ((cell[1] + 0.5) * c, None, (cell[2] + 0.5) * c)
        hits = [e_i]
        for e_j in range(e_i + 1, len(entries)):
            k2, cell2 = entries[e_j]
            b = pts[k2]
            if b.t - a.t > THRESHOLDS["oscillation_window_s"]:
                break
            if (b.inv or {}) != (a.inv or {}):
                break
            if cell2 == cell:
                between = pts[entries[hits[-1]][0]:k2]
                if max((_dh(p.pos, centre) for p in between), default=0) >= THRESHOLDS["oscillation_min_excursion"]:
                    hits.append(e_j)
        if len(hits) >= THRESHOLDS["oscillation_min_visits"]:
            first, last = pts[entries[hits[0]][0]], pts[entries[hits[-1]][0]]
            hp = [s.health for s in tl.samples if first.t <= s.t <= last.t and s.health is not None]
            if hp and min(hp) < max(hp):  # health changing = combat/strafing, not dithering
                continue
            used.update(hits)
            until = last.t
            cost = _r(last.t - first.t)
            out.append(Finding("oscillation", "micro", "medium", first.t, last.t, cost,
                               [pts[entries[h][0]].line for h in hits],
                               f"lines {first.line}-{last.line}: re-entered the same {c:g}-block cell "
                               f"{len(hits)}x in {cost} s with no inventory change",
                               {"cell": cell[1:], "dim": cell[0], "visits": len(hits)}))
    return out


def place_then_recover(tl, ctx):
    """Utility block (crafting_table/furnace/...) leaves the inventory without a craft, then comes back
    without a craft (agent: recover action; human: no material spent in the same delta)."""
    out, open_places = [], {}
    durs = _dur_lookup(tl)
    series = _inv_series(tl)
    for prev, s in zip(series, series[1:]):
        d = _delta(prev.inv or {}, s.inv or {})
        txt = _text(s)
        crafted = bool(CRAFT_RE.search(txt)) if s.action else any(v < 0 and k not in UTILITY for k, v in d.items())
        for item, v in d.items():
            if item not in UTILITY:
                continue
            if v < 0 and not crafted:
                open_places[item] = s
            elif v > 0 and item in open_places and not crafted and (not s.action or RECOVER_RE.search(txt)
                                                                    or not PLACE_RE.search(txt)):
                p = open_places.pop(item)
                if s.line in durs:
                    t0, cost = durs[s.line]
                else:
                    cost = THRESHOLDS["est_break_s"].get(item, THRESHOLDS["est_break_s"]["default"])
                    t0 = max(prev.t, s.t - cost)
                out.append(Finding("place_then_recover", "micro", "low", t0, s.t, _r(cost), [p.line, s.line],
                                   f"{item} placed (line {p.line}) and re-collected (line {s.line}); "
                                   f"{_r(cost)} s spent recovering it", {"item": item, "span_s": _r(s.t - p.t)}))
    return out


def _mined_gain(d):
    return {k: v for k, v in d.items() if v > 0 and (k in POSITIVE_PICKAXE_BLOCKS or k in SHOVEL_BLOCKS
                                                       or WOOD_LOG_RE.search(k))}


def _water_hint(s, last_water):
    """Agent logs carry no in_water flag: the action names water/swimming, or the previous water
    action ended within water_context_blocks of here (agent still in the water it swam through)."""
    if WATER_RE.search(_text(s)):
        return True
    return (last_water is not None and last_water is not s and last_water.pos is not None
            and s.pos is not None and _d3(last_water.pos, s.pos) <= THRESHOLDS["water_context_blocks"])


def _dig_window(tl, idx, gain):
    """(t0, dig_s) for a mined-block gain with no logged action duration (human logs): only the dig
    itself, i.e. the contiguous run of eyes-in-water samples at the same spot (<= 0.5 block) with an
    unchanged inventory just before the gain. Never the whole swim. Capped at
    est_break_s.default x water_mining_slowdown per gained block."""
    s = tl.samples[idx]
    cap = max(1, sum(gain.values())) * THRESHOLDS["est_break_s"]["default"] * THRESHOLDS["water_mining_slowdown"]
    t0 = _prev_t(tl, idx)
    base = None
    for q in reversed(tl.samples[:idx]):
        if q.pos is None or getattr(q, "kind", None) == "decision":
            continue
        if base is None:
            base = q.inv or {}
        if (q.in_water is not True or s.pos is None or _d3(q.pos, s.pos) > 0.5
                or (q.inv or {}) != base):
            break
        t0 = q.t
    t0 = max(t0, s.t - cap)
    return t0, max(0.0, s.t - t0)


def mining_in_water(tl, ctx):
    """Mining while submerged (5x slower in 1.16.5 without Aqua Affinity, drops float away).
    in_water known: mine action or mined-block gain while in_water. Unknown (agent logs): action text
    mentions water/swimming and the collect failed or gained nothing."""
    out = []
    durs = _dur_lookup(tl)
    slow = THRESHOLDS["water_mining_slowdown"]
    series = _inv_series(tl)
    prev_by_line = {s.line: p for p, s in zip(series, series[1:])}
    hits = []  # (t0, t1, cost, line, evidence)
    last_water = None   # last action sample whose text mentions water/swimming (agent logs)
    for idx, s in enumerate(tl.samples):
        if getattr(s, "kind", None) == "decision":
            continue
        if _is_action(s) and WATER_RE.search(_text(s)):
            last_water = s
            if not (s.action and MINE_RE.search(_text(s))):
                continue
        prev = prev_by_line.get(s.line)
        d = _delta(prev.inv or {}, s.inv or {}) if prev is not None else {}
        gain = _mined_gain(d)
        mining = bool(s.action and MINE_RE.search(_text(s)))
        if s.in_water is True and (mining or gain):
            if s.line in durs:
                t0, dur = durs[s.line]
            else:
                t0, dur = _dig_window(tl, idx, gain)
            hits.append((t0, s.t, dur * (1 - 1 / slow), s.line, {"gained": gain, "action": s.action,
                                                                  "dig_s": _r(dur)}))
        elif s.in_water is None and mining and _water_hint(s, last_water) and (s.action_failed or not gain):
            t0, dur = durs.get(s.line, (_prev_t(tl, idx), s.t - _prev_t(tl, idx)))
            hits.append((t0, s.t, dur, s.line, {"action": s.action, "failed": bool(s.action_failed),
                                                 "result": getattr(s, "result", None)}))
    # group consecutive hits that touch (<= 1 s gap)
    group = []
    for h in hits + [None]:
        if group and (h is None or h[0] - group[-1][1] > 1.0):
            cost = _r(sum(g[2] for g in group))
            out.append(Finding("mining_in_water", "micro", "medium" if cost >= 5 else "low", group[0][0],
                               group[-1][1], cost, [g[3] for g in group],
                               f"lines {group[0][3]}-{group[-1][3]}: mining while in water ({len(group)} "
                               f"sample(s)); {cost} s lost to the underwater mining penalty/failed collects",
                               {"samples": [g[4] for g in group]}))
            group = []
        if h is not None:
            group.append(h)
    return out


def lost_drop(tl, ctx):
    """A mine/collect action succeeded but nothing reached the inventory within lost_drop_window_s or
    by the next action result (drop fell into water/lava, despawned, or was never picked up)."""
    out, acts = [], _actions(tl)
    win = THRESHOLDS["lost_drop_window_s"]
    for n, (_, s, start, dur, b) in enumerate(acts):
        txt = _text(s)
        mine_key = bool(MINE_RE.search(s.action or ""))
        mine_desc = bool(MINE_RE.search(getattr(s, "action_desc", None) or "")) and not TRAVEL_RE.search(txt)
        if s.action_failed or b is None or not (mine_key or mine_desc) or WORLD_EFFECT_RE.search(txt):
            continue
        nxt_line = acts[n + 1][1].line if n + 1 < len(acts) else math.inf
        later = [q for q in tl.samples if q.line >= s.line and getattr(q, "kind", None) != "decision"
                 and (q.t <= s.t + win or q.line <= nxt_line)]
        base = b.inv or {}
        if any(v > 0 for q in later for v in _delta(base, q.inv or {}).values()):
            continue
        out.append(Finding("lost_drop", "micro", "medium", start, s.t, dur, [b.line, s.line],
                           f"line {s.line}: '{s.action}' reported success but nothing reached the inventory "
                           f"within {win:g} s / by the next result; {dur} s wasted",
                           {"action": s.action, "result": getattr(s, "result", None)}))
    return out


def excess_food(tl, ctx):
    peaceful = _difficulty(tl, ctx) == "peaceful"
    full = THRESHOLDS["food_full"]
    durs = _dur_lookup(tl)
    series = _inv_series(tl)
    food_stat = None
    gains = []  # (prev, s, d_food)
    eaten_after = {}  # item -> last line where it decreased
    for prev, s in zip(series, series[1:]):
        d = _delta(prev.inv or {}, s.inv or {})
        for k, v in d.items():
            if k in FOOD and v < 0:
                eaten_after[k] = s.line
        fg = {k: v for k, v in d.items() if k in FOOD and v > 0}
        if fg:
            gains.append((prev, s, fg))
    stat_by_line = {}
    for s in tl.samples:
        if s.food is not None:
            food_stat = s.food
        stat_by_line[s.line] = food_stat
    out = []
    for prev, s, fg in gains:
        stat = stat_by_line.get(prev.line)
        never_eaten = {k: v for k, v in fg.items() if eaten_after.get(k, -1) <= s.line}
        if peaceful:
            items, why = fg, "difficulty is peaceful (hunger never drops)"
        elif never_eaten and (stat is None or stat >= full):
            items, why = never_eaten, f"food bar was {'full' if stat is not None else 'unknown'} and it was never eaten"
        else:
            continue
        d = _delta(prev.inv or {}, s.inv or {})
        only_food = all(k in FOOD or k not in NEEDED for k, v in d.items() if v > 0)
        if s.line in durs:
            t0, dur = durs[s.line]
        else:
            t0, dur = prev.t, s.t - prev.t
        cost = _r(dur if only_food else 0.0)
        out.append(Finding("excess_food", "micro", "medium" if cost >= 10 else "low", t0, s.t, cost,
                           [s.line], f"line {s.line}: gathered {items} but {why}; {cost} s"
                           + ("" if only_food else " (picked up alongside route items, no time charged)"),
                           {"items": items, "food_stat": stat, "difficulty": _difficulty(tl, ctx) or None}))
    return out


def _tool_used(tool_kind, d):
    gains = {k for k, v in d.items() if v > 0}
    if tool_kind == "pickaxe":
        return bool(gains & POSITIVE_PICKAXE_BLOCKS)
    if tool_kind == "shovel":
        return bool(gains & SHOVEL_BLOCKS)
    if tool_kind == "axe":
        return any(WOOD_LOG_RE.search(k) for k in gains)
    return None  # sword/hoe: no observable proxy


def excess_tools(tl, ctx):
    """Duplicate tools of the same tier held at once, a lower tier acquired while a higher tier of the
    same kind is held, and tools never used afterwards (no gain of blocks that tool mines)."""
    out, durs = [], _dur_lookup(tl)
    series = _inv_series(tl)
    acquired = {}  # tool -> (sample idx in series, cost, t0)
    reported_dup = set()
    for n, (prev, s) in enumerate(zip(series, series[1:]), 1):
        d = _delta(prev.inv or {}, s.inv or {})
        for tool, v in d.items():
            m = TOOL_RE.match(tool)
            if not m or v <= 0:
                continue
            crafty = bool(CRAFT_RE.search(_text(s))) if s.action else any(x < 0 for x in d.values())
            if s.line in durs and crafty:
                t0, cost = durs[s.line]
            else:
                cost = THRESHOLDS["est_craft_s"] if crafty else 0.0
                t0 = max(prev.t, s.t - cost)
            acquired.setdefault(tool, (n, cost, t0, s))
            inv = s.inv or {}
            tier, kind = m.group(1), m.group(2)
            better = [k for k in inv if TOOL_RE.match(k) and TOOL_RE.match(k).group(2) == kind
                      and TIER[TOOL_RE.match(k).group(1)] > TIER[tier] and k != tool]
            if inv.get(tool, 0) >= 2 and tool not in reported_dup:
                reported_dup.add(tool)
                out.append(Finding("excess_tools", "micro", "low", t0, s.t, _r(cost), [s.line],
                                   f"line {s.line}: holding {inv[tool]}x {tool} (duplicate of the same tier); "
                                   f"{_r(cost)} s", {"tool": tool, "count": inv[tool], "reason": "duplicate"}))
            elif better:
                out.append(Finding("excess_tools", "micro", "low", t0, s.t, _r(cost), [s.line],
                                   f"line {s.line}: acquired {tool} while already holding {sorted(better)}; "
                                   f"{_r(cost)} s", {"tool": tool, "better": sorted(better), "reason": "superseded"}))
    for tool, (n, cost, t0, s) in sorted(acquired.items()):
        kind = TOOL_RE.match(tool).group(2)
        if _tool_used(kind, {}) is None:
            continue  # sword/hoe: no observable proxy for use
        used = any(_tool_used(kind, _delta(p2.inv or {}, s2.inv or {}))
                   for p2, s2 in zip(series[n:], series[n + 1:]))
        if not used:
            out.append(Finding("excess_tools", "micro", "low", t0, s.t, _r(cost), [s.line],
                               f"line {s.line}: {tool} acquired but no block it mines was ever gained "
                               f"afterwards (never used); {_r(cost)} s", {"tool": tool, "reason": "never_used"}))
    return out


def _incidental(prev, s):
    """Stone picked up while moving (> 0.5 block since the previous sample) or descending
    (staircase/dig-down): the block had to be broken to pass (logeval INCIDENTAL rule)."""
    if prev.pos is None or s.pos is None:
        return False
    if _d3(prev.pos, s.pos) > 0.5:
        return True
    return prev.pos[1] is not None and s.pos[1] is not None and s.pos[1] < prev.pos[1] - 0.25


def excess_materials(tl, ctx):
    """Wood (log-equivalents) / stone gathered beyond what later crafts or placements consumed + slack."""
    series = _inv_series(tl)
    if len(series) < 2:
        return []
    durs = _dur_lookup(tl)
    out = []
    for group in ("wood", "stone"):
        def units(inv):
            if group == "wood":
                return sum(_wood_units(k, v) for k, v in inv.items())
            return float(sum(v for k, v in inv.items() if k in STONE_ITEMS))
        gathered, lines, gather_time, t_first, t_last = 0.0, [], 0.0, None, None
        incidental = 0.0
        for prev, s in zip(series, series[1:]):
            if group == "wood":
                g = sum(v for k, v in _delta(prev.inv or {}, s.inv or {}).items() if v > 0 and WOOD_LOG_RE.search(k))
            else:
                g = sum(v for k, v in _delta(prev.inv or {}, s.inv or {}).items() if v > 0 and k in STONE_ITEMS)
            if g > 0 and group == "stone" and _incidental(prev, s):
                incidental += g  # broken to pass (tunnel/staircase): no extra time, not surplus
                continue
            if g > 0:
                gathered += g
                lines.append(s.line)
                if s.line in durs:
                    gather_time += durs[s.line][1]
                else:
                    gather_time += g * THRESHOLDS["est_gather_s"][group]
                t_first = s.t if t_first is None else t_first
                t_last = s.t
        leftover = units(series[-1].inv or {}) - units(series[0].inv or {}) - incidental
        excess = leftover - THRESHOLDS["materials_slack"]
        if gathered > 0 and excess > 0:
            per = gather_time / gathered
            cost = _r(min(gather_time, excess * per))
            out.append(Finding("excess_materials", "micro", "medium" if cost >= 15 else "low", t_first, t_last,
                               cost, lines, f"{group}: gathered {gathered:g} but {leftover:g} "
                               f"{'log-equivalents' if group == 'wood' else 'blocks'} were never consumed "
                               f"(slack {THRESHOLDS['materials_slack']}); {cost} s of gathering was surplus",
                               {"group": group, "gathered": gathered, "leftover": leftover,
                                "excess": excess, "per_unit_s": _r(per), "final_line": series[-1].line,
                                "incidental_excluded": incidental}))
    return out


def _targets(tl):
    out = []
    for name, v in sorted((tl.knowledge or {}).items()):
        pts = v if isinstance(v, list) else [v]
        for i, p in enumerate(pts):
            if isinstance(p, dict) and p.get("x") is not None and p.get("z") is not None:
                out.append((name if len(pts) == 1 else f"{name}_{i}",
                            (float(p["x"]), p.get("y"), float(p["z"])), _norm_dim(p.get("dim"))))
    # agent: coordinates named in action text are targets too (logeval overshoot rule)
    seen = {(round(t[1][0]), round(t[1][2]), t[2]) for t in out}
    for s in tl.samples:
        if not _is_action(s):
            continue
        for m in COORD_RE.finditer(_text(s)):
            x, y, z = (float(v) for v in m.groups())
            key = (round(x), round(z), _norm_dim(s.dim))
            if key not in seen:
                seen.add(key)
                out.append((f"action_target({x:g},{y:g},{z:g})", (x, y, z), _norm_dim(s.dim)))
    return out


def _productive_excursion(tl, pts, bi, ret, name):
    """The excursion reached ANOTHER known target (within overshoot_reach+1.5, chest reach) and the
    inventory changed while away: a side-trip to that target, not an overshoot."""
    others = [(n, p, d) for n, p, d in _targets(tl) if n != name]
    reached = any(_dh(pts[q].pos, p) <= THRESHOLDS["overshoot_reach"] + 1.5
                  and (not d or not pts[q].dim or _norm_dim(pts[q].dim) == d)
                  for q in range(bi + 1, ret) for n, p, d in others)
    return reached and (pts[bi].inv or {}) != (pts[ret].inv or {})


def overshoot_waypoint(tl, ctx):
    """Distance to a known target reaches <= overshoot_reach, then grows past min + margin while still
    targeting it: either the action text names the target's coordinates (agent, logeval rule) or the
    player comes back within reach inside overshoot_return_window_s (any source)."""
    reach, margin = THRESHOLDS["overshoot_reach"], THRESHOLDS["overshoot_margin"]
    win = THRESHOLDS["overshoot_return_window_s"]
    pts = [s for s in tl.samples if s.pos is not None]
    out, seen_iv = [], set()
    for name, tg, tdim in _targets(tl):
        def names_target(s):
            for m in COORD_RE.finditer(_text(s)):
                x, _, z = (float(v) for v in m.groups())
                if math.hypot(x - tg[0], z - tg[2]) < 0.5:
                    return True
            return False
        k = 0
        while k < len(pts):
            s = pts[k]
            if (tdim and s.dim and _norm_dim(s.dim) != tdim) or _dh(s.pos, tg) > reach:
                k += 1
                continue
            # reached: find the minimum of this approach
            best, bi = _dh(s.pos, tg), k
            j = k + 1
            while j < len(pts) and _dh(pts[j].pos, tg) <= best:
                best, bi = _dh(pts[j].pos, tg), j
                j += 1
            # first sample beyond min + margin
            seg_end = next((q for q in range(bi + 1, len(pts))
                            if _norm_dim(pts[q].dim) != _norm_dim(pts[bi].dim)), len(pts))
            m = next((q for q in range(bi + 1, seg_end) if _dh(pts[q].pos, tg) > best + margin), None)
            if m is None:
                k = seg_end if seg_end > k else k + 1
                continue
            far = max(_dh(pts[q].pos, tg) for q in range(m, seg_end))
            ret = None
            if far >= THRESHOLDS["overshoot_min_excursion"]:
                ret = next((q for q in range(m + 1, seg_end) if pts[q].t - pts[bi].t <= win
                            and _dh(pts[q].pos, tg) <= reach), None)
                if ret is not None and max(_dh(pts[q].pos, tg) for q in range(m, ret)) < THRESHOLDS["overshoot_min_excursion"]:
                    ret = None
            # still targeting = the action in progress when distance grew names the target
            cur = next((q for q in pts[m:seg_end] if _is_action(q)), None)
            targeting = cur is not None and names_target(cur)
            if ret is not None and not targeting and _productive_excursion(tl, pts, bi, ret, name):
                k = ret + 1  # went to loot/visit another known target and came back: not overshoot
                continue
            if ret is not None or targeting:
                end = pts[ret] if ret is not None else pts[m]
                cost = _r(end.t - pts[bi].t)
                iv = (pts[bi].t, end.t)
                if any(min(iv[1], e1) - max(iv[0], e0) > 0.5 * (iv[1] - iv[0]) for e0, e1 in seen_iv):
                    # nearby targets (portal + chest + action coords) share one episode
                    k = (ret if ret is not None else m) + 1
                    continue
                seen_iv.add(iv)
                out.append(Finding("overshoot_waypoint", "micro", "low" if cost < 10 else "medium", pts[bi].t,
                                   end.t, cost, [pts[bi].line, pts[m].line] + ([end.line] if ret is not None else []),
                                   f"{name} ({tg[0]:g}, {tg[2]:g}) reached within {best:.2f} blocks at line "
                                   f"{pts[bi].line}, then {_dh(pts[m].pos, tg):.2f} blocks away at line {pts[m].line}"
                                   + (f", back at line {end.line}" if ret is not None else " while still targeting it")
                                   + f"; {cost} s", {"target": name, "min_distance": round(best, 2),
                                                      "returned": ret is not None}))
                k = (ret if ret is not None else m) + 1
                # skip the rest of this approach
                while k < len(pts) and _dh(pts[k].pos, tg) <= reach:
                    k += 1
            else:
                k = m
    return out


# ---------------------------------------------------------------- safety detectors
LAVA_MAX_DT = 10.0  # a gap between in_lava samples longer than this is not counted as lava time


def _lava_episode_s(tl, before, last):
    """Seconds in lava for THIS damage episode only: sum of dt between consecutive in_lava samples
    of the contiguous lava run(s) touching [before.t - fall_lookback_s, last.t], gaps capped."""
    lo, hi = before.t - THRESHOLDS["fall_lookback_s"], last.t
    flagged = [s for s in tl.samples if s.in_lava is not None]
    total = 0.0
    for a, b in zip(flagged, flagged[1:]):
        if a.in_lava and b.in_lava and b.t >= lo and a.t <= hi:
            total += min(b.t - a.t, LAVA_MAX_DT)
    return total


def damage_taken(tl, ctx):
    pts = [s for s in tl.samples if s.health is not None]
    out, i = [], 1
    gap = THRESHOLDS["damage_group_s"]
    while i < len(pts):
        if pts[i].health >= pts[i - 1].health:
            i += 1
            continue
        a, j = i, i
        while j + 1 < len(pts) and pts[j + 1].health < pts[j].health and pts[j + 1].t - pts[j].t <= gap:
            j += 1
        before, last = pts[a - 1], pts[j]
        lost = before.health - last.health
        seg = [s for s in tl.samples if before.line <= s.line <= last.line]
        cause, cost = "other", 0.0
        if any(s.in_lava for s in seg):
            cause = "lava"
            cost = _lava_episode_s(tl, before, last)
        elif any(MAGMA_RE.search(_text(s)) for s in seg if s.action):
            cause = "magma"
        else:
            look = [s for s in tl.samples if s.pos is not None and s.pos[1] is not None
                    and pts[a].t - THRESHOLDS["fall_lookback_s"] <= s.t <= pts[a].t]
            if look and max(s.pos[1] for s in look) - look[-1].pos[1] >= THRESHOLDS["fall_min_drop_blocks"]:
                cause = "fall"
        sev = "high" if lost >= 10 else "medium" if lost >= 4 else "low"
        out.append(Finding("damage_taken", "safety", sev, before.t, last.t, _r(cost), [before.line, last.line],
                           f"lines {before.line}-{last.line}: health {before.health:g} -> {last.health:g} "
                           f"(-{lost:g}, {cause})" + (f"; {_r(cost)} s in lava" if cost else ""),
                           {"cause": cause, "hp_lost": lost, "pos": last.pos, "dim": last.dim}))
        i = j + 1
    return out


def death(tl, ctx):
    out = []
    dur = float(tl.meta.get("duration_s") or (tl.samples[-1].t if tl.samples else 0.0))
    deaths = [ev for ev in tl.events if ev.get("type") in ("death", "death_suspected")]
    lines_seen = {ev["line"] for ev in deaths}
    prev = None
    for s in tl.samples:  # health hitting 0 with no logged death event nearby
        if s.health is not None and s.health <= 0 and (prev is None or (prev.health or 0) > 0):
            if not any(abs(ev["t"] - s.t) <= 5 for ev in deaths):
                deaths.append({"t": s.t, "line": s.line, "type": "health_zero", "pos": s.pos})
        prev = s if s.health is not None else prev
    for ev in sorted(deaths, key=lambda e: (e["t"], e["line"])):
        pos = ev.get("pos")
        before = [s for s in tl.samples if s.pos is not None and s.t <= ev["t"]]
        dim = before[-1].dim if before else None
        if pos is None and before:
            pos = before[-1].pos
        after = [s for s in tl.samples if s.t > ev["t"] and s.pos is not None]
        ret = next((s for s in after if pos is not None and s.dim == dim
                    and _dh(s.pos, pos) <= THRESHOLDS["death_return_radius"]
                    and any(_dh(q.pos, pos) > THRESHOLDS["death_return_radius"] for q in after if q.t < s.t)),
                   None)
        if ret is not None:
            cost, end, how = ret.t - ev["t"], ret.t, f"back at the death spot at line {ret.line}"
        else:
            cost = min(THRESHOLDS["death_default_cost_s"], max(0.0, dur - ev["t"]))
            end, how = ev["t"] + cost, "never returned to the death spot (default cost, capped at run end)"
        inv = before[-1].inv if before else {}
        out.append(Finding("death", "safety", "high", ev["t"], end, _r(cost),
                           [ev["line"]] + ([ret.line] if ret is not None else []),
                           f"line {ev['line']}: {ev['type']} at {pos} in {dim}; {how}; {_r(cost)} s",
                           {"pos": pos, "dim": dim, "inventory_at_death": inv, "event": ev["type"],
                            "logged": ev["line"] in lines_seen}))
    return out


# ---------------------------------------------------------------- claims (live_agent self-report)
_MILESTONE_SPLITS = ("nether_entered", "nether_exited", "end_entered", "dragon_killed", "game_won")
PLACEABLE = ("obsidian",)


def _live(tl):
    return (getattr(tl, "meta", None) or {}).get("live_agent") or {}


def self_report_contradiction(tl, ctx):
    """The agent's summary line vs its own logged evidence (skill results, deaths, milestones)."""
    lv = _live(tl)
    sm = lv.get("summary")
    if not sm:
        return []
    srs = lv.get("skill_results") or []
    failed = [r["line"] for r in srs if not r["ok"]]
    deaths = [ev["line"] for ev in tl.events if ev.get("type") in ("death", "death_suspected")]
    reached = [ev for ev in tl.events if ev.get("type") in _MILESTONE_SPLITS]
    checks = [("failures", sm.get("failures"), len(failed), failed,
               "skill_result lines with ok:false"),
              ("actions", sm.get("actions"), len(srs), [r["line"] for r in srs], "skill_result lines"),
              ("deaths", sm.get("deaths"), len(deaths), deaths, "death events")]
    sp = sm.get("splits")
    if isinstance(sp, list):
        checks.append(("splits", len(sp), len(reached), [ev["line"] for ev in reached],
                       "milestones reached in the log"))
    if "finalSplit" in sm:
        last = reached[-1]["type"] if reached else None
        fs = sm.get("finalSplit")
        fs_n = _EV_ALIAS.get(str(fs), str(fs)) if fs is not None else None
        if fs_n != last:
            checks.append(("finalSplit", fs, last, [reached[-1]["line"]] if reached else [],
                           "last milestone reached in the log"))
    out = []
    for field_, claimed, actual, lines, what in checks:
        if field_ != "finalSplit":
            if not isinstance(claimed, (int, float)) or claimed == actual:
                continue
        out.append(Finding("self_report_contradiction", "claim", "high", sm["t"], sm["t"], 0.0,
                           [sm["line"]] + list(lines),
                           f"line {sm['line']}: summary claims {field_}={claimed!r}, but the log shows "
                           f"{actual!r} ({what}" + (f": lines {', '.join(map(str, lines[:20]))})" if lines
                                                     else ")"),
                           {"field": field_, "claimed": claimed, "logged": actual,
                            "summary_line": sm["line"], "evidence_lines": list(lines)}))
    return out


_EV_ALIAS = {"end_entry": "end_entered", "nether_entry": "nether_entered", "nether_exit": "nether_exited"}


def inventory_loss_without_effect(tl, ctx):
    """A placeable block (obsidian) left the inventory across a failed build skill that placed 0."""
    lv = _live(tl)
    snaps = lv.get("inventory_snapshots") or []
    out = []
    by_line = {s.line: s for s in tl.samples}
    for r in lv.get("skill_results") or []:
        if r["ok"] or r.get("placed") != 0 or not BUILD_RE.search(r["skill"] or ""):
            continue
        s = by_line.get(r["line"])
        idx = tl.samples.index(s) if s is not None else None
        before = tl.samples[idx - 1] if idx else None
        # inventory just before the skill: the sample preceding its skill_start
        st = [x for x in (lv.get("skill_starts") or []) if x["line"] < r["line"]]
        if st:
            bl = st[-1]["line"]
            prior = [x for x in tl.samples if x.line < bl]
            before = prior[-1] if prior else before
        after = next((sn for sn in snaps if sn["line"] > r["line"]), None)
        if before is None or after is None:
            continue
        for item in PLACEABLE:
            b, a = before.inv.get(item, 0), after["inv"].get(item, 0)
            if a < b:
                lines = sorted(set((lv.get("loot_lines") or [])[-1:] + [before.line, r["line"], after["line"]]))
                out.append(Finding("inventory_loss_without_effect", "claim", "high", before.t, after["t"], 0.0,
                                   lines,
                                   f"lines {before.line}->{after['line']}: {item} {b} -> {a} (-{b - a}) across "
                                   f"failed {r['skill']} (line {r['line']}: placed 0, "
                                   f"{r.get('error') or 'not ok'}); items consumed, nothing built",
                                   {"item": item, "before": b, "after": a, "skill_line": r["line"],
                                    "before_line": before.line, "snapshot_line": after["line"]}))
    return out


BUILD_RE = re.compile(r"build|place|portal_frame", re.I)


REGISTRY = {
    "failed_action": failed_action,
    "no_progress": no_progress,
    "idle": idle,
    "action_loop": action_loop,
    "oscillation": oscillation,
    "place_then_recover": place_then_recover,
    "mining_in_water": mining_in_water,
    "lost_drop": lost_drop,
    "excess_food": excess_food,
    "excess_tools": excess_tools,
    "excess_materials": excess_materials,
    "overshoot_waypoint": overshoot_waypoint,
    "damage_taken": damage_taken,
    "death": death,
    "self_report_contradiction": self_report_contradiction,
    "inventory_loss_without_effect": inventory_loss_without_effect,
}


def _merge_seed_detectors():
    try:
        from . import detectors_seed  # noqa: WPS433 (lazy: written by another builder)
    except ImportError:
        return
    for attr in ("REGISTRY", "SEED_REGISTRY", "DETECTORS"):
        reg = getattr(detectors_seed, attr, None)
        if isinstance(reg, dict):
            for k, f in reg.items():
                REGISTRY.setdefault(k, f)


def get_registry() -> dict:
    _merge_seed_detectors()
    return REGISTRY


def run_all(tl, ctx=None, codes=None) -> list:
    """Run every (or the named) detector; findings sorted by (t_start, code, first line)."""
    ctx = ctx or {}
    out = []
    for code, f in sorted(get_registry().items()):
        if codes is None or code in codes:
            out.extend(f(tl, ctx))
    return sorted(out, key=lambda x: (x.t_start, x.code, x.lines[0] if x.lines else 0))


_merge_seed_detectors()
