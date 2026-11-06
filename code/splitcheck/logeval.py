"""Layer B: deterministic gameplay-log evaluator for rmalde/minecraft-agent events.jsonl.

Input lines look like {"time": ISO, "type": ..., ...data} (nether-agent.mjs `log`).
Every finding cites the 1-based line number of the event(s) it is derived from.
No LLM calls; same input -> same output.

CLI: python -m splitcheck.logeval <events.jsonl> [--pro pro_splits.json] [--out report.json]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import re
import sys
from pathlib import Path

# Items the speedrun route needs (anything else that only accumulates is a detour).
NEEDED = {
    "obsidian", "flint_and_steel", "ender_pearl", "blaze_rod", "blaze_powder", "ender_eye",
    "bucket", "water_bucket", "lava_bucket", "gold_ingot", "gold_nugget", "gold_block",
    "golden_helmet", "golden_chestplate", "golden_leggings", "golden_boots",
    "fire_resistance_potion", "potion", "splash_potion",
    "wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "diamond_pickaxe",
    "wooden_axe", "stone_axe", "iron_axe", "wooden_sword", "stone_sword", "iron_sword",
    "wooden_shovel", "stone_shovel", "iron_shovel", "oak_boat", "boat",
}
# Blocks picked up incidentally while mining/pathing; reported separately, never as waste.
INCIDENTAL = {
    "netherrack", "dirt", "cobblestone", "gravel", "sand", "stone", "blackstone", "basalt",
    "soul_sand", "soul_soil", "end_stone", "flint", "cobbled_deepslate", "granite", "diorite",
    "andesite", "magma_block", "grass_block", "coarse_dirt",
}
FOOD = {
    "apple", "bread", "cooked_beef", "beef", "cooked_porkchop", "porkchop", "cooked_chicken",
    "chicken", "cooked_mutton", "mutton", "cooked_cod", "cod", "cooked_salmon", "salmon",
    "baked_potato", "potato", "carrot", "golden_carrot", "golden_apple", "melon_slice",
    "sweet_berries", "cooked_rabbit", "rabbit", "pumpkin_pie", "mushroom_stew",
}
# Utility blocks whose place-then-mine-back is a classic undo.
UTILITY = {"crafting_table", "furnace", "smithing_table", "blast_furnace", "smoker", "chest"}

SPLIT_ORDER = ["start", "nether_entry", "nether_exit", "end_entry", "dragon_kill", "game_won"]
SPLIT_ALIASES = {
    "start": "start", "run_start": "start",
    "nether_entry": "nether_entry", "nether_enter": "nether_entry", "nether_entered": "nether_entry",
    "enter_nether": "nether_entry", "nether": "nether_entry",
    "nether_exit": "nether_exit", "nether_exited": "nether_exit", "exit_nether": "nether_exit",
    "end_entry": "end_entry", "end_enter": "end_entry", "enter_end": "end_entry", "end": "end_entry",
    "the_end": "end_entry", "end_entered": "end_entry",
    "dragon_kill": "dragon_kill", "dragon_killed": "dragon_kill", "dragon": "dragon_kill",
    "dragon_death": "dragon_kill",
    "game_won": "game_won", "credits": "game_won", "finish": "game_won", "run_end": "game_won",
}
EXPECTED_TYPES = ["start", "decision", "result", "plan", "nether_entered", "nether_exited",
                  "dragon_killed", "game_won"]
# actions whose effect is on the world, not on position or item counts (portal lighting keeps
# flint_and_steel in 1.16.5; attacks/throws/placing eyes change mobs or blocks)
WORLD_EFFECT_RE = re.compile(r"light|ignite|portal|attack|throw|place_eye|fill|build|fight|hit|bed", re.I)
WAIT_RE = re.compile(r"\b(wait|waits|waiting|idle)\b|wait_|_wait|idle_|_idle", re.I)
PLACE_RE = re.compile(r"place|put down|set down", re.I)
RECOVER_RE = re.compile(r"mine|break|collect|pick ?up|recover|retrieve|dig", re.I)
CRAFT_RE = re.compile(r"craft(?!ing[ _]table)", re.I)
COORD_RE = re.compile(r"\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?")

OVERSHOOT_REACH = 3.0      # "reached" = within this many blocks (horizontal)
OVERSHOOT_MARGIN = 2.0     # distance must grow by more than this after the minimum
LOOP_MIN = 3               # identical consecutive keys


# ---------------------------------------------------------------- loading
def _ts(s: str) -> float:
    return _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def load_events(path) -> list[dict]:
    """Read events.jsonl. Each event gets "_line" (1-based). Bad lines become
    {"type": "_parse_error", "_line": n, "_raw": ...} so coverage can report them."""
    out = []
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                e = json.loads(raw)
                if not isinstance(e, dict):
                    raise ValueError("not an object")
            except ValueError:
                out.append({"type": "_parse_error", "_line": n, "_raw": raw[:200]})
                continue
            e["_line"] = n
            try:
                e["_t"] = _ts(e["time"])
            except (KeyError, ValueError, TypeError):
                e["_t"] = None
            out.append(e)
    return out


def _t0(events) -> float | None:
    for e in events:
        if e.get("type") == "start" and e.get("_t") is not None:
            return e["_t"]
    for e in events:
        if e.get("_t") is not None:
            return e["_t"]
    return None


def _rel(e, t0):
    if e.get("_t") is None or t0 is None:
        return None
    return round(e["_t"] - t0, 3)


def _req_state(dec: dict) -> dict:
    req = dec.get("request") or {}
    st = req.get("state") if isinstance(req, dict) else None
    if isinstance(st, str):
        try:
            st = json.loads(st)
        except ValueError:
            st = None
    return st if isinstance(st, dict) else {}


def _dim(e: dict):
    if e.get("dimension"):
        return e["dimension"]
    st = e.get("state")
    if isinstance(st, dict) and st.get("dimension"):
        return st["dimension"]
    if e.get("type") == "decision":
        return _req_state(e).get("dimension")
    return None


def _pos(e: dict):
    p = e.get("position")
    if not isinstance(p, dict):
        st = e.get("state") if isinstance(e.get("state"), dict) else None
        if st is None and e.get("type") == "decision":
            st = _req_state(e)
        p = (st or {}).get("position")
    if isinstance(p, dict) and all(isinstance(p.get(k), (int, float)) for k in ("x", "z")):
        return p
    return None


def _hdist(a, b) -> float:
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


def _norm_dim(d):
    if not d:
        return None
    d = str(d).replace("minecraft:", "")
    return {"nether": "the_nether", "end": "the_end"}.get(d, d)


# ---------------------------------------------------------------- splits
def extract_splits(events: list[dict]) -> list[dict]:
    t0 = _t0(events)
    splits, seen = [], set()

    def add(name, e, reason):
        if name != "death" and name in seen:
            return
        seen.add(name)
        splits.append({"split": name, "time_s": _rel(e, t0), "line": e["_line"],
                       "event_type": e.get("type"), "position": _pos(e), "reason": reason})

    for e in events:
        t = e.get("type")
        ln = e["_line"]
        if t == "start":
            add("start", e, f"line {ln}: start event (t=0)")
        elif t == "nether_entered":
            add("nether_entry", e, f"line {ln}: nether_entered event")
        elif t == "nether_exited":
            add("nether_exit", e, f"line {ln}: nether_exited event")
        elif t in ("end_entered", "end_entry"):
            add("end_entry", e, f"line {ln}: {t} event")
        elif t == "dragon_killed":
            add("dragon_kill", e, f"line {ln}: dragon_killed event")
        elif t == "game_won":
            add("game_won", e, f"line {ln}: game_won event")
        elif t == "death":
            add("death", e, f"line {ln}: death event")
        if "end_entry" not in seen and t not in ("decision",) and _norm_dim(_dim(e)) == "the_end":
            add("end_entry", e, f"line {ln}: first {t} event with dimension the_end")
        elif "end_entry" not in seen and t == "decision" and _norm_dim(_dim(e)) == "the_end":
            add("end_entry", e, f"line {ln}: first decision whose request state dimension is the_end")
    # stable order: by line
    splits.sort(key=lambda s: s["line"])
    return splits


# ---------------------------------------------------------------- pairing
def _pairs(events):
    """Yield (decision, result) pairs: each result is paired with the most recent unpaired decision."""
    pairs, last = [], None
    for e in events:
        if e.get("type") == "decision":
            last = e
        elif e.get("type") == "result":
            pairs.append((last, e))
            last = None
    return pairs


def _inv(e):
    if e is None:
        return None
    inv = e.get("inventory")
    if inv is None and isinstance(e.get("state"), dict):
        inv = e["state"].get("inventory")
    if inv is None and e.get("type") == "decision":
        inv = _req_state(e).get("inventory")
    if not isinstance(inv, dict):
        return None
    out = {}
    for k, v in inv.items():  # tolerate string/float counts; drop values that are not numbers
        try:
            out[str(k)] = int(float(v))
        except (TypeError, ValueError, OverflowError):
            continue
    return out


def _label(dec, res):
    key = (dec or {}).get("selected") or ""
    action = (res or {}).get("action") or ""
    return str(key), str(action)


# ---------------------------------------------------------------- waste
def detect_waste(events: list[dict]) -> dict:
    t0 = _t0(events)
    pairs = _pairs(events)
    start = next((e for e in events if e.get("type") == "start"), None)
    difficulty = str((start or {}).get("difficulty") or
                     ((start or {}).get("state") or {}).get("difficulty") or "").lower()
    peaceful = difficulty == "peaceful"

    failed, no_progress, waits, loops, place_recover = [], [], [], [], []
    rows = []  # normalized action rows
    for dec, res in pairs:
        key, action = _label(dec, res)
        dur = None
        if dec is not None and dec.get("_t") is not None and res.get("_t") is not None:
            dur = round(max(0.0, res["_t"] - dec["_t"]), 3)
        result_text = str(res.get("result", ""))
        inv_before = _inv(dec)
        inv_after = _inv(res)
        rows.append({"dec": dec, "res": res, "key": key, "action": action, "dur": dur,
                     "result": result_text, "failed": result_text.startswith("FAILED"),
                     "inv_before": inv_before, "inv_after": inv_after})
    # inventory "before" fallback = previous result inventory
    prev_inv = _inv(start)
    for r in rows:
        if r["inv_before"] is None:
            r["inv_before"] = prev_inv
        if r["inv_after"] is not None:
            prev_inv = r["inv_after"]

    def cite(r):
        d = f"decision line {r['dec']['_line']}, " if r["dec"] else ""
        return f"{d}result line {r['res']['_line']} (step {r['res'].get('step')})"

    for r in rows:
        res, dec = r["res"], r["dec"]
        if r["failed"]:
            failed.append({"line": res["_line"], "decision_line": dec["_line"] if dec else None,
                           "step": res.get("step"), "key": r["key"], "action": r["action"],
                           "time_s": r["dur"], "result": r["result"],
                           "reason": f"{cite(r)}: result starts with FAILED ({r['result'][:80]}); "
                                     f"cost {r['dur']} s"})
        p0 = _pos(dec) if dec else None
        p1 = _pos(res)
        moved = None
        if p0 and p1:
            moved = math.dist([p0["x"], p0.get("y", 0), p0["z"]], [p1["x"], p1.get("y", 0), p1["z"]])
        r["moved"] = moved
        inv_changed = (r["inv_before"] or {}) != (r["inv_after"] or {}) if r["inv_after"] is not None else None
        r["inv_changed"] = inv_changed
        world_effect = bool(WORLD_EFFECT_RE.search(r["key"]) or WORLD_EFFECT_RE.search(r["action"]))
        r["world_effect"] = world_effect
        if moved is not None and moved < 0.01 and inv_changed is False and not r["failed"] and not world_effect:
            no_progress.append({"line": res["_line"], "decision_line": dec["_line"], "step": res.get("step"),
                                "key": r["key"], "action": r["action"], "time_s": r["dur"],
                                "reason": f"{cite(r)}: position unchanged vs decision request state "
                                          f"and inventory unchanged; cost {r['dur']} s"})
        if WAIT_RE.search(r["key"]) or WAIT_RE.search(r["action"]):
            waits.append({"line": res["_line"], "decision_line": dec["_line"] if dec else None,
                          "step": res.get("step"), "key": r["key"], "action": r["action"],
                          "time_s": r["dur"],
                          "reason": f"{cite(r)}: action '{r['key'] or r['action']}' is a wait/idle; "
                                    f"cost {r['dur']} s"})

    # loops: >= LOOP_MIN identical consecutive keys where at least half failed or made no progress
    i = 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1]["key"] and rows[j + 1]["key"] == rows[i]["key"]:
            j += 1
        n = j - i + 1
        if n >= LOOP_MIN and rows[i]["key"]:
            seg = rows[i:j + 1]
            bad = sum(1 for r in seg if r["failed"] or (r["moved"] is not None and r["moved"] < 0.01
                                                         and r["inv_changed"] is False))
            if bad * 2 >= n:
                secs = round(sum(r["dur"] or 0 for r in seg), 3)
                lines = [r["res"]["_line"] for r in seg]
                loops.append({"line": seg[0]["dec"]["_line"] if seg[0]["dec"] else lines[0],
                              "end_line": lines[-1], "key": rows[i]["key"], "count": n,
                              "unproductive": bad, "time_s": secs,
                              "reason": f"lines {lines[0]}-{lines[-1]}: action '{rows[i]['key']}' repeated "
                                        f"{n}x in a row, {bad} failed/no-progress; cost {secs} s"})
        i = j + 1

    # place-then-recover
    open_places = {}  # item -> (row index, row)
    for idx, r in enumerate(rows):
        b, a = r["inv_before"] or {}, r["inv_after"] or {}
        if r["inv_after"] is None:
            continue
        text = f"{r['key']} {r['action']}"
        for item in sorted(set(b) | set(a)):
            d = a.get(item, 0) - b.get(item, 0)
            if d < 0 and (PLACE_RE.search(text) or item in UTILITY) and not CRAFT_RE.search(text):
                open_places[item] = (idx, r)
            elif d > 0 and item in open_places and RECOVER_RE.search(text):
                pidx, pr = open_places.pop(item)
                crafts = sum(1 for q in rows[pidx + 1:idx] if CRAFT_RE.search(q["key"] + " " + q["action"]))
                span = None
                if pr["res"].get("_t") is not None and r["res"].get("_t") is not None:
                    span = round(r["res"]["_t"] - pr["res"]["_t"], 3)
                cost = round(sum(q["dur"] or 0 for q in rows[idx:idx + 1]), 3)
                place_recover.append({
                    "item": item, "line": pr["res"]["_line"], "recover_line": r["res"]["_line"],
                    "place_key": pr["key"], "recover_key": r["key"], "crafts_between": crafts,
                    "span_s": span, "time_s": cost,
                    "reason": f"{item} placed at result line {pr['res']['_line']} ('{pr['key']}') and "
                              f"recovered at result line {r['res']['_line']} ('{r['key']}') after "
                              f"{crafts} craft action(s); recovery cost {cost} s"})

    # items acquired and never consumed
    first_inv = _inv(start) or (rows[0]["inv_before"] if rows else None) or {}
    series, first_line = [], None
    if rows:
        series = [(None, first_inv)] + [(r["res"]["_line"], r["inv_after"]) for r in rows if r["inv_after"] is not None]
    decreased, first_gain = set(), {}
    for (l0, i0), (l1, i1) in zip(series, series[1:]):
        for item in set(i0) | set(i1):
            if i1.get(item, 0) < i0.get(item, 0):
                decreased.add(item)
            elif i1.get(item, 0) > i0.get(item, 0) and item not in first_gain:
                first_gain[item] = l1
    last_inv = series[-1][1] if series else {}
    last_line = series[-1][0] if series else None
    unused, incidental = [], []
    for item in sorted(last_inv):
        gained = last_inv.get(item, 0) - first_inv.get(item, 0)
        if gained <= 0 or item in decreased:
            continue
        needed = item in NEEDED or item.endswith("_bed") or item == "bed" or (item in FOOD and not peaceful)
        if needed:
            continue
        entry = {"item": item, "count": gained, "line": first_gain.get(item), "last_line": last_line,
                 "reason": f"{item} first gained at result line {first_gain.get(item)}, +{gained} by "
                           f"result line {last_line}, never decreased"}
        if item in INCIDENTAL:
            incidental.append(entry)
        else:
            entry["reason"] += (" and not needed by the route" +
                                (" (food on Peaceful)" if item in FOOD else ""))
            unused.append(entry)

    # overshoot: targets parsed from decision text (key/description/action) with coordinates
    overshoot = _overshoot(events, rows)

    deaths = []
    for e in events:
        if e.get("type") == "death":
            st = e.get("state") if isinstance(e.get("state"), dict) else {}
            deaths.append({"line": e["_line"], "time_s": _rel(e, t0), "position": _pos(e),
                           "dimension": st.get("dimension"), "health": st.get("health"),
                           "active": st.get("active"),
                           "reason": f"line {e['_line']}: death at {_pos(e)} in {st.get('dimension')} "
                                     f"while '{st.get('active')}'"})

    dec_ms = sum(float(e.get("latencyMs") or 0) for e in events if e.get("type") == "decision")
    plan_ms = sum(float(e.get("latencyMs") or 0) for e in events if e.get("type") == "plan")
    latency = {"decisions": sum(1 for e in events if e.get("type") == "decision"),
               "planner_calls": sum(1 for e in events if e.get("type") == "plan"),
               "jev_api_s": round(dec_ms / 1000, 3), "planner_api_s": round(plan_ms / 1000, 3),
               "note": "API latency is reported separately and NOT counted as player time; planner calls can overlap actions."}

    def tot(lst, k="time_s"):
        return round(sum(x.get(k) or 0 for x in lst), 3)

    totals = {"failed_actions": len(failed), "failed_s": tot(failed), "no_progress": len(no_progress),
              "no_progress_s": tot(no_progress), "waits": len(waits), "wait_s": tot(waits),
              "loops": len(loops), "place_recover": len(place_recover), "unused_items": len(unused),
              "overshoot": len(overshoot), "deaths": len(deaths)}
    return {"difficulty": difficulty or None, "failed_actions": failed, "no_progress": no_progress,
            "waits": waits, "loops": loops, "place_recover": place_recover, "unused_items": unused,
            "incidental_items": incidental, "overshoot": overshoot, "deaths": deaths,
            "latency": latency, "totals": totals}


def _targets_in(text: str):
    out = []
    for m in COORD_RE.finditer(text or ""):
        x, y, z = (float(v) for v in m.groups())
        out.append({"x": x, "y": y, "z": z})
    return out


def _overshoot(events, rows):
    """A target is the first (x, y, z) in the decision key/description. While consecutive decisions keep
    the same target, track horizontal distance from every position event in that window; if the minimum
    is <= OVERSHOOT_REACH and a later distance exceeds min + OVERSHOOT_MARGIN, flag it."""
    findings = []
    by_line = sorted(events, key=lambda e: e["_line"])
    i = 0
    while i < len(rows):
        r = rows[i]
        text = f"{r['key']} {r['action']}"
        if r["dec"]:
            text += " " + str(_req_state(r["dec"]).get("active") or "")
        tg = _targets_in(f"{r['key']} {r['action']}")
        if not tg:
            i += 1
            continue
        target = tg[0]
        j = i
        while j + 1 < len(rows):
            t2 = _targets_in(f"{rows[j + 1]['key']} {rows[j + 1]['action']}")
            if t2 and _hdist(t2[0], target) < 0.5:
                j += 1
            else:
                break
        lo = rows[i]["dec"]["_line"] if rows[i]["dec"] else rows[i]["res"]["_line"]
        hi = rows[j]["res"]["_line"]
        best, best_line, flagged = None, None, None
        for e in by_line:
            if e["_line"] < lo or e["_line"] > hi:
                continue
            p = _pos(e)
            if p is None:
                continue
            d = _hdist(p, target)
            if best is None or d < best:
                best, best_line = d, e["_line"]
            elif best <= OVERSHOOT_REACH and d > best + OVERSHOOT_MARGIN:
                flagged = (e["_line"], d)
                break
        if flagged:
            findings.append({"line": flagged[0], "reached_line": best_line,
                             "target": target, "min_distance": round(best, 2),
                             "distance": round(flagged[1], 2), "key": r["key"],
                             "reason": f"target ({target['x']:g}, {target['y']:g}, {target['z']:g}) reached "
                                       f"within {best:.2f} blocks at line {best_line}, then distance grew to "
                                       f"{flagged[1]:.2f} at line {flagged[0]} while still targeting it"})
        i = j + 1
    return findings


# ---------------------------------------------------------------- claims
ITEM_WORDS = [
    (r"eyes?(?: of ender)?|ender eyes?|ender_eyes?", "ender_eye"),
    (r"ender pearls?|pearls?|ender_pearls?", "ender_pearl"),
    (r"blaze rods?|rods?|blaze_rods?", "blaze_rod"),
    (r"blaze powder|blaze_powder", "blaze_powder"),
    (r"obsidian", "obsidian"),
    (r"beds?", "_bed"),
]
_HAVE = r"(?:have|has|holding|hold|carrying|got|own|possess)"
HAVE_RE = re.compile(
    r"(?<![a-z])(?P<pre>(?:\w+\s+){0,2})" + _HAVE + r"\s+(?:all\s+|the\s+)?(?P<n>\d+)\s+(?P<item>" +
    "|".join(f"(?:{w})" for w, _ in ITEM_WORDS) + r")\b", re.I)
NEGATION_RE = re.compile(r"(?:\bnot\b|n't\b|\bno\b|\bnever\b|\bwithout\b)", re.I)
FUTURE_RE = re.compile(r"\b(will|should|need|needs|must|to|until|once|if|when|would|can|could)\b", re.I)
ARRIVE_RE = [
    (re.compile(r"\b(?:entered|am in|are in|is in|now in|arrived in|inside)\s+the\s+nether\b", re.I),
     "the_nether", "nether_entered"),
    (re.compile(r"\b(?:entered|am in|are in|is in|now in|arrived in|inside)\s+the\s+end\b", re.I),
     "the_end", None),
    (re.compile(r"\b(?:killed|defeated|slain)\s+the\s+(?:ender\s+)?dragon\b|\bdragon\s+(?:is\s+)?dead\b",
                re.I), None, "dragon_killed"),
]
REACHED_RE = re.compile(r"\b(?:reached|arrived at|at)\s+(?:the\s+)?(?P<what>[a-z_ ]{0,30}?portal)"
                        r"(?:\s+at)?\s*\(?\s*(?P<x>-?\d+(?:\.\d+)?)\s*,\s*(?P<y>-?\d+(?:\.\d+)?)\s*,\s*"
                        r"(?P<z>-?\d+(?:\.\d+)?)", re.I)


def _claim_texts(e):
    t = e.get("type")
    if t == "plan":
        res = e.get("result")
        return json.dumps(res, sort_keys=True) if not isinstance(res, str) else res
    if t == "decision":
        resp = e.get("response")
        if isinstance(resp, (dict, list)):
            return json.dumps(resp, sort_keys=True)
        return str(resp or "")
    return ""


def _count(inv, item):
    if item == "_bed":
        return sum(v for k, v in inv.items() if k.endswith("_bed") or k == "bed")
    return inv.get(item, 0)


def detect_claims(events: list[dict]) -> list[dict]:
    findings = []
    for idx, e in enumerate(events):
        if e.get("type") not in ("plan", "decision"):
            continue
        text = _claim_texts(e)
        if not text:
            continue
        nxt = next((q for q in events[idx + 1:] if q.get("type") == "result"), None)
        if nxt is None:
            nxt = next((q for q in reversed(events[:idx]) if q.get("type") == "result"), None)
        # a "have N X" claim is about the state BEFORE the action: use the decision's own
        # request-state inventory, else the previous result; never the post-action result.
        prev = next((q for q in reversed(events[:idx]) if q.get("type") in ("result", "start")), None)
        own = _inv(e) if e.get("type") == "decision" else None
        if own is not None:
            inv_src, inv = e, own
        else:
            inv_src = prev
            inv = _inv(prev) or {}
        for m in HAVE_RE.finditer(text):
            pre = m.group("pre") or ""
            neg_ctx = text[max(0, m.start() - 12):m.start()] + pre
            if FUTURE_RE.search(pre) or NEGATION_RE.search(neg_ctx) or NEGATION_RE.search(m.group(0)):
                continue
            n = int(m.group("n"))
            word = m.group("item").lower()
            item = next(it for w, it in ITEM_WORDS if re.fullmatch(w, word, re.I))
            actual = _count(inv, item)
            if inv_src is not None and actual < n:
                where = ("its own request state" if inv_src is e else
                         f"{inv_src.get('type')} line {inv_src['_line']} (state before the action)")
                findings.append({"label": "claim_contradicted", "line": e["_line"],
                                 "evidence_line": inv_src["_line"], "claim": m.group(0).strip(),
                                 "item": item, "claimed": n, "actual": actual,
                                 "reason": f"{e['type']} at line {e['_line']} claims '{m.group(0).strip()}' "
                                           f"but {where} inventory has {item}={actual}"})
        for rx, dim, ev in ARRIVE_RE:
            m = rx.search(text)
            if not m:
                continue
            happened = ev is not None and any(q.get("type") == ev for q in events[:idx + 1])
            nxt_dim = _norm_dim(_dim(nxt)) if nxt else None
            in_dim = dim is not None and (nxt_dim == dim or _norm_dim(_dim(e)) == dim)
            if not happened and not in_dim:
                findings.append({"label": "claim_contradicted", "line": e["_line"],
                                 "evidence_line": nxt["_line"] if nxt else None, "claim": m.group(0),
                                 "reason": f"{e['type']} at line {e['_line']} claims '{m.group(0)}' but no "
                                           f"{ev or 'dimension'} event precedes it and next result "
                                           f"(line {nxt['_line'] if nxt else None}) dimension is {nxt_dim or 'not reported'}"})
        for m in REACHED_RE.finditer(text):
            tgt = {"x": float(m.group("x")), "y": float(m.group("y")), "z": float(m.group("z"))}
            p = _pos(nxt) if nxt else None
            if p is not None and _hdist(p, tgt) > 5:
                findings.append({"label": "claim_contradicted", "line": e["_line"],
                                 "evidence_line": nxt["_line"], "claim": m.group(0),
                                 "distance": round(_hdist(p, tgt), 2),
                                 "reason": f"{e['type']} at line {e['_line']} claims '{m.group(0)}' but result "
                                           f"line {nxt['_line']} position is {_hdist(p, tgt):.1f} blocks away"})
    return findings


# ---------------------------------------------------------------- comparison
def _canon(name):
    return SPLIT_ALIASES.get(str(name).strip().lower().replace(" ", "_").replace("-", "_"),
                             str(name).strip().lower())


def compare_splits(splits: list[dict], pro_splits: list[dict]) -> list[dict]:
    ours = {}
    for s in splits:
        c = _canon(s["split"])
        if c != "death" and c not in ours:
            ours[c] = s
    pros = {}
    for p in pro_splits or []:
        c = _canon(p.get("split"))
        if c not in pros:
            pros[c] = p
    names = [n for n in SPLIT_ORDER if n in ours or n in pros]
    names += sorted(n for n in set(ours) | set(pros) if n not in SPLIT_ORDER)
    out = []
    for n in names:
        if n == "start":
            continue
        s, p = ours.get(n), pros.get(n)
        row = {"split": n, "time_s": s["time_s"] if s else None, "line": s["line"] if s else None,
               "pro_time_s": p.get("time_s") if p else None,
               "pro_verified": p.get("verified") if p else None,
               "pro_source": (p.get("run") or p.get("source")) if p else None,
               "delta_s": None, "ratio": None}
        if s and p and s["time_s"] is not None and isinstance(p.get("time_s"), (int, float)):
            row["delta_s"] = round(s["time_s"] - p["time_s"], 3)
            row["ratio"] = round(s["time_s"] / p["time_s"], 3) if p["time_s"] else None
            row["reason"] = (f"line {s['line']}: {n} at {s['time_s']} s vs pro {p['time_s']} s "
                             f"(delta {row['delta_s']:+} s, x{row['ratio']})")
        elif s:
            row["reason"] = f"line {s['line']}: {n} at {s['time_s']} s; no pro split"
        else:
            row["reason"] = f"{n} missing from log; pro {p.get('time_s')} s"
        out.append(row)
    return out


# ---------------------------------------------------------------- evaluate
def _survey_points(survey_dir):
    files = []
    if survey_dir and Path(survey_dir).is_dir():
        for f in sorted(Path(survey_dir).glob("*.json")):
            try:
                json.loads(f.read_text())
                files.append(f.name)
            except (ValueError, OSError):
                pass
    return files


def evaluate(events_path, pro_splits_path=None, survey_dir=None) -> dict:
    events = load_events(events_path)
    good = [e for e in events if e.get("type") != "_parse_error"]
    splits = extract_splits(good)
    waste = detect_waste(good)
    claims = detect_claims(good)
    pro = None
    if pro_splits_path and Path(pro_splits_path).exists():
        pro = json.loads(Path(pro_splits_path).read_text())
        if isinstance(pro, dict):
            pro = pro.get("splits", [])
    comparison = compare_splits(splits, pro) if pro is not None else []
    times = [e["time"] for e in good if e.get("_t") is not None]
    types = {e.get("type") for e in good}
    coverage = {"events": len(good), "parse_errors": [e["_line"] for e in events if e.get("type") == "_parse_error"],
                "first_time": times[0] if times else None, "last_time": times[-1] if times else None,
                "duration_s": round(max(e["_t"] for e in good if e.get("_t") is not None) -
                                    _t0(good), 3) if times else None,
                "types": {t: sum(1 for e in good if e.get("type") == t) for t in sorted(types, key=str)},
                "missing_types": [t for t in EXPECTED_TYPES if t not in types],
                "survey_files": _survey_points(survey_dir),
                "pro_splits": str(pro_splits_path) if pro is not None else None}
    return {"events_path": str(events_path), "splits": splits, "waste": waste, "claims": claims,
            "comparison": comparison, "coverage": coverage}


def summarize(rep: dict) -> str:
    L = [f"SplitCheck Layer B: {rep['events_path']}"]
    c = rep["coverage"]
    L.append(f"  events={c['events']} span={c['duration_s']} s missing_types={c['missing_types'] or 'none'}")
    L.append("  Splits:")
    for s in rep["splits"]:
        L.append(f"    {s['split']:<13} {s['time_s']!s:>9} s  ({s['reason']})")
    if rep["comparison"]:
        L.append("  Vs pro:")
        for r in rep["comparison"]:
            L.append(f"    {r['split']:<13} {r['reason']}")
    w = rep["waste"]
    L.append(f"  Waste totals: {json.dumps(w['totals'])}")
    for k in ("failed_actions", "no_progress", "waits", "loops", "place_recover", "unused_items",
              "overshoot", "deaths"):
        for f in w[k]:
            L.append(f"    [{k}] {f['reason']}")
    lat = w["latency"]
    L.append(f"  API latency (not player time): JEV {lat['jev_api_s']} s over {lat['decisions']} decisions, "
             f"planner {lat['planner_api_s']} s over {lat['planner_calls']} calls")
    L.append(f"  Claims contradicted: {len(rep['claims'])}")
    for f in rep["claims"]:
        L.append(f"    [claim_contradicted] {f['reason']}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m splitcheck.logeval")
    ap.add_argument("events")
    ap.add_argument("--pro", default=None, help="splits/pro_splits.json")
    ap.add_argument("--survey", default=None, help="dir of seed survey JSONs (recorded in coverage)")
    ap.add_argument("--out", default=None, help="write JSON report here")
    a = ap.parse_args(argv)
    if not Path(a.events).exists():
        print(f"events file not found: {a.events}", file=sys.stderr)
        return 2
    rep = evaluate(a.events, a.pro, a.survey)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(rep, indent=2, sort_keys=True))
    print(summarize(rep))
    if a.out:
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
