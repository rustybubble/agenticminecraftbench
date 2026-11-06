"""Normalized gameplay timeline for both log formats (deterministic, stdlib only).

Formats:
  * agent        -- rmalde/minecraft-agent events.jsonl (nether-agent.mjs `log(type, data)`):
                    start/decision/result/plan/position_sample/display_state/death/... events.
  * live_agent   -- live/agent (mineflayer) events.jsonl: spawn/route_start/route_step/skill_start/
                    skill_result/route_loot/route_portal/route_state/route_inventory/linger/summary,
                    timed by ts (ISO) / epoch (ms). Loot lists are "namexN" strings.
  * human_poller -- capture/rcon_poller.py output: start{source:"rcon_poller"}, position_sample
                    {player, position[x,y,z], dimension, inventory, health, feet_block?, head_block?},
                    nether_entered, nether_exited, end_entered, death_suspected, stop.

load_timeline(path, route_sheet=None) -> Timeline. Every Sample/event keeps its 1-based log line.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .logeval import _inv, _norm_dim, _req_state, load_events

MILESTONES = ("start", "nether_entered", "nether_exited", "end_entered", "dragon_killed",
              "game_won", "death", "death_suspected", "stop")
_EVENT_ALIASES = {"end_entry": "end_entered", "nether_entry": "nether_entered",
                  "nether_exit": "nether_exited"}
# knownSeed point features whose dimension is not the overworld
_DIM_HINT = {"exitportal": "the_nether", "netherroute": "the_nether", "nethertravel": "the_nether",
             "exit_portal": "the_nether", "nether_route": "the_nether"}
_SKIP_KNOWLEDGE = {"remainingchests"}  # subset of chests; tracked per-decision, not new knowledge


@dataclass
class Sample:
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
    kind: str | None = None          # source event type (position_sample, decision, result, ...)
    action_desc: str | None = None   # agent result.action (human-readable description)
    result: str | None = None        # agent result string
    selected_item: str | None = None # poller: item id in the main hand (None if empty/unknown)


@dataclass
class Timeline:
    source: str
    samples: list = field(default_factory=list)
    events: list = field(default_factory=list)
    knowledge: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------- helpers
def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # drop NaN


def _pos_tuple(p):
    if isinstance(p, dict):
        vals = [_num(p.get(k)) for k in ("x", "y", "z")]
    elif isinstance(p, (list, tuple)) and len(p) >= 3:
        vals = [_num(v) for v in p[:3]]
    else:
        return None
    if vals[0] is None or vals[2] is None:
        return None
    return tuple(vals)


def _block_flags(e: dict):
    """(in_water, in_lava) from explicit flags or poller feet_block/head_block; None if unknown."""
    if isinstance(e.get("in_water"), bool) or isinstance(e.get("in_lava"), bool):
        w, l = e.get("in_water"), e.get("in_lava")
        return (w if isinstance(w, bool) else None, l if isinstance(l, bool) else None)
    blocks = [e.get(k) for k in ("feet_block", "head_block", "eye_block") if k in e]
    if not blocks:
        return None, None

    def nm(b):
        return str(b or "").replace("minecraft:", "").lower()
    names = [nm(b) for b in blocks]
    # in_water = EYES submerged (the 1.16.5 5x dig penalty is isEyeInFluid). Use the poller's
    # eye_block (floor(y + 1.62)) when logged, else head_block (floor(y) + 1). Feet-only water is
    # wading: no dig penalty, so in_water stays False.
    eye_key = "eye_block" if "eye_block" in e else "head_block" if "head_block" in e else None
    water = (nm(e.get(eye_key)) in ("water", "flowing_water", "bubble_column", "kelp", "kelp_plant",
                                    "seagrass", "tall_seagrass")) if eye_key else False
    lava = any(n in ("lava", "flowing_lava") for n in names)
    return water, lava


def _is_point(v):
    return isinstance(v, dict) and _num(v.get("x")) is not None and _num(v.get("z")) is not None


def normalize_knowledge(src: dict, into: dict | None = None) -> dict:
    """knownSeed / route-sheet dict -> {name: {x,y,z,dim,...}}. Lists of points become name_0..n."""
    out = into if into is not None else {}
    if not isinstance(src, dict):
        return out

    def put(name, p, key):
        d = _norm_dim(p.get("dim") or p.get("dimension")) or _DIM_HINT.get(key.lower(), "overworld")
        entry = {"x": _num(p.get("x")), "y": _num(p.get("y")), "z": _num(p.get("z")), "dim": d}
        for k, v in p.items():
            if k not in ("x", "y", "z", "dim", "dimension"):
                entry[k] = v
        out.setdefault(name, entry)

    for key, val in src.items():
        if key.lower() in _SKIP_KNOWLEDGE:
            continue
        if _is_point(val):
            put(key, val, key)
        elif isinstance(val, list):
            for i, p in enumerate(val):
                if _is_point(p):
                    put(f"{key}_{i}", p, key)
    return out


_LIVE_TYPES = ("skill_result", "skill_start", "route_start")


def _detect_source(events: list[dict]) -> str:
    types = {e.get("type") for e in events}
    if (types & set(_LIVE_TYPES)) or {"spawn", "summary"} <= types:
        if not any(e.get("source") == "rcon_poller" for e in events):
            return "live_agent"
    for e in events:
        if e.get("source") == "rcon_poller":
            return "human_poller"
        if e.get("type") in ("decision", "result", "plan"):
            return "agent"
    for e in events:
        if e.get("type") == "position_sample":
            if isinstance(e.get("position"), list) or "player" in e or "feet_block" in e:
                return "human_poller"
    return "agent"


# ---------------------------------------------------------------- loader
def _is_telemetry(events: list[dict]) -> bool:
    """live/server/telemetry.js output: start{note:'server-authoritative telemetry...'} + sample{pos{}}
    + inventory{items{}} + log{kind,line}."""
    return any(e.get("type") == "sample" and isinstance(e.get("pos"), (dict, type(None))) and "runId" in e
               for e in events) and not any(e.get("type") in ("position_sample", "skill_result") for e in events)


def _telemetry_to_poller(events: list[dict]) -> list[dict]:
    """Map telemetry.js records onto the rcon_poller shape (same server-side evidence, different writer)."""
    out, inv = [], {}
    for e in events:
        typ = e.get("type")
        if typ == "start":
            out.append({**e, "source": "rcon_poller", "telemetry": "live/server/telemetry.js"})
        elif typ == "inventory":
            inv = dict(e.get("items") or {})
        elif typ == "sample":
            p = e.get("pos")
            if not isinstance(p, dict):
                continue  # player not visible to the server at this tick
            out.append({**{k: v for k, v in e.items() if k not in ("pos", "type")},
                        "type": "position_sample", "position": [p.get("x"), p.get("y"), p.get("z")],
                        "dimension": e.get("dimension"), "inventory": dict(inv),
                        "health": e.get("health"), "food": e.get("food"), "selected_item": e.get("selected")})
        elif typ == "log":
            line = str(e.get("line") or "")
            out.append(e)
            if e.get("kind") == "death" or " died" in line or "tried to swim in lava" in line or "was slain" in line:
                out.append({**e, "type": "death", "note": line})
            elif "We Need to Go Deeper" in line:
                out.append({**e, "type": "nether_entered", "note": "server advancement: " + line})
        else:
            out.append(e)
    return out


def load_timeline(path, route_sheet=None) -> Timeline:
    events = load_events(path)
    if _is_telemetry(events):
        events = _telemetry_to_poller(events)
    source = _detect_source(events)
    if source == "live_agent":
        return _load_live_agent(path, events)
    malformed = [e["_line"] for e in events if e.get("type") == "_parse_error"]
    good = [e for e in events if e.get("type") != "_parse_error"]
    untimed = [e["_line"] for e in good if e.get("_t") is None]

    t0 = next((e["_t"] for e in good if e.get("type") == "start" and e.get("_t") is not None), None)
    if t0 is None:
        t0 = next((e["_t"] for e in good if e.get("_t") is not None), None)

    tl = Timeline(source=source)
    knowledge: dict = {}
    last_dec = None
    seen_types = set()
    dim_changes = []  # (t, line, prev, new, pos)
    prev_dim = None

    for e in good:
        if e.get("_t") is None:
            continue
        t = round(e["_t"] - t0, 3)
        ln = e["_line"]
        typ = _EVENT_ALIASES.get(e.get("type"), e.get("type"))
        st = e.get("state") if isinstance(e.get("state"), dict) else None
        if typ == "decision":
            st = _req_state(e)
            last_dec = e
        if st:
            ks = st.get("knownSeed")
            if isinstance(ks, dict):
                normalize_knowledge(ks, knowledge)

        if typ in MILESTONES:
            ev = {"t": t, "line": ln, "type": typ}
            p = _pos_tuple(e.get("position") or (st or {}).get("position"))
            if p:
                ev["pos"] = p
            if typ == "start" and seen_types & {"start"}:
                pass  # keep only the first start
            else:
                tl.events.append(ev)
                seen_types.add(typ)

        s = None
        if typ == "position_sample":
            w, l = _block_flags(e)
            s = Sample(t=t, line=ln, pos=_pos_tuple(e.get("position")),
                       dim=_norm_dim(e.get("dimension")), inv=_inv(e) or {},
                       health=_num(e.get("health")), food=_num(e.get("food")),
                       in_water=w, in_lava=l, kind=typ,
                       selected_item=(str(e["selected_item"]).replace("minecraft:", "")
                                      if e.get("selected_item") else None))
        elif typ == "result":
            res = e.get("result")
            res_s = res if isinstance(res, str) else None
            key = (last_dec or {}).get("selected")
            s = Sample(t=t, line=ln, pos=_pos_tuple(e.get("position")),
                       dim=_norm_dim(e.get("dimension")) or prev_dim, inv=_inv(e) or {},
                       action=str(key) if key else (str(e.get("action")) if e.get("action") else None),
                       action_failed=bool(res_s and res_s.startswith("FAILED")),
                       stage=_req_state(last_dec).get("stage") if last_dec else None,
                       kind=typ, action_desc=e.get("action"), result=res_s)
            last_dec = None
        elif st and typ in ("decision", "display_state", "start", "death"):
            w, l = _block_flags(st)
            s = Sample(t=t, line=ln, pos=_pos_tuple(st.get("position")),
                       dim=_norm_dim(st.get("dimension")), inv=_inv({"inventory": st.get("inventory")}) or {},
                       health=_num(st.get("health")), food=_num(st.get("food")),
                       in_water=w, in_lava=l, stage=st.get("stage"), kind=typ,
                       action=str(e.get("selected")) if typ == "decision" and e.get("selected") else None)
        if s is not None:
            tl.samples.append(s)
            if s.dim:
                if prev_dim and s.dim != prev_dim:
                    dim_changes.append((t, ln, prev_dim, s.dim, s.pos))
                prev_dim = s.dim

    # derive milestones from dimension changes when the log did not record them
    for t, ln, prev, new, pos in dim_changes:
        typ = None
        if new == "the_end":
            typ = "end_entered"
        elif new == "the_nether":
            typ = "nether_entered"
        elif prev == "the_nether" and new == "overworld":
            typ = "nether_exited"
        if typ and typ not in seen_types:
            ev = {"t": t, "line": ln, "type": typ, "derived": "dimension_change"}
            if pos:
                ev["pos"] = pos
            tl.events.append(ev)
            seen_types.add(typ)
    tl.events.sort(key=lambda ev: (ev["t"], ev["line"]))

    if source == "human_poller" or route_sheet is not None:
        knowledge = {}
        if route_sheet is not None:
            sheet = route_sheet
            if not isinstance(sheet, dict):
                sheet = json.loads(Path(sheet).read_text(encoding="utf-8"))
            normalize_knowledge(sheet.get("knownSeed", sheet), knowledge)
    tl.knowledge = knowledge

    timed = [e for e in good if e.get("_t") is not None]
    tl.meta = {
        "path": str(path),
        "lines": len(events),
        "malformed_lines": len(malformed),
        "malformed_line_numbers": malformed[:50],
        "untimed_lines": len(untimed),
        "t0_epoch": t0,
        "duration_s": round(timed[-1]["_t"] - t0, 3) if timed and t0 is not None else 0.0,
        "event_type_counts": _counts(e.get("type") for e in good),
        "knowledge_source": ("route_sheet" if route_sheet is not None else
                             "knownSeed" if source == "agent" else "none"),
    }
    start = next((e for e in good if e.get("type") == "start"), None)
    if start:
        for k in ("seed", "version", "difficulty", "player"):
            if k in start:
                tl.meta[k] = start[k]
    return tl


def _counts(it):
    out = {}
    for x in it:
        out[str(x)] = out.get(str(x), 0) + 1
    return dict(sorted(out.items()))


# ---------------------------------------------------------------- live_agent format
_ITEM_N_RE = re.compile(r"^(.*?)x(\d+)$")
BUILD_SKILL_RE = re.compile(r"build|place|portal_frame", re.I)


def parse_item_list(items) -> dict:
    """["obsidianx4", "breadx1", "obsidianx1"] -> {"bread": 1, "obsidian": 5} (duplicates summed)."""
    out: dict = {}
    for it in items or []:
        if isinstance(it, dict):
            name, n = it.get("name"), it.get("count", 1)
        else:
            m = _ITEM_N_RE.match(str(it).strip())
            name, n = (m.group(1), m.group(2)) if m else (str(it).strip(), 1)
        if not name:
            continue
        name = str(name).replace("minecraft:", "")
        try:
            out[name] = out.get(name, 0) + int(n)
        except (TypeError, ValueError):
            continue
    return dict(sorted(out.items()))


def _load_live_agent(path, events) -> Timeline:
    malformed = [e["_line"] for e in events if e.get("type") == "_parse_error"]
    good = [e for e in events if e.get("type") != "_parse_error"]
    untimed = [e["_line"] for e in good if e.get("_t") is None]
    timed = [e for e in good if e.get("_t") is not None]
    t0 = timed[0]["_t"] if timed else None
    tl = Timeline(source="live_agent")
    knowledge: dict = {}
    inv: dict = {}
    pos, dim, prev_dim = None, None, None
    last_loot_got = None   # skill_result loot_chest got list not yet echoed by route_loot
    live = {"summary": None, "skill_results": [], "inventory_snapshots": [], "loot_lines": [],
            "deaths": [], "split_events": [], "skill_starts": []}
    seen = set()

    def add_event(typ, t, ln, p=None, **extra):
        if typ in seen and typ != "death":
            return
        ev = {"t": t, "line": ln, "type": typ}
        if p:
            ev["pos"] = p
        ev.update(extra)
        tl.events.append(ev)
        seen.add(typ)

    for e in timed:
        t = round(e["_t"] - t0, 3)
        ln = e["_line"]
        typ = e.get("type")
        res = e.get("result") if isinstance(e.get("result"), dict) else {}
        action = failed = None
        new_dim = _norm_dim(e.get("dimension")) if e.get("dimension") else None
        if typ == "spawn":
            pos = _pos_tuple(e.get("pos")) or pos
            dim = new_dim or "overworld"
            add_event("start", t, ln, pos)
        elif typ == "route_start":
            for st in e.get("route") or []:
                if isinstance(st, dict) and st.get("step") and _is_point(st):
                    knowledge.setdefault(str(st["step"]), {"x": _num(st.get("x")), "y": _num(st.get("y")),
                                                           "z": _num(st.get("z")), "dim": "overworld"})
            for k in ("seed", "version"):
                if k in e:
                    tl.meta.setdefault(k, e[k])
        elif typ == "skill_start":
            live["skill_starts"].append({"line": ln, "t": t, "skill": e.get("skill")})
        elif typ == "skill_result":
            ok = bool(e.get("ok")) and res.get("ok", True) is not False
            action, failed = str(e.get("skill") or "skill"), not ok
            pos = _pos_tuple(res.get("pos")) or pos
            got = res.get("got")
            if isinstance(got, list) and e.get("skill") == "loot_chest":
                for k, n in parse_item_list(got).items():
                    inv[k] = inv.get(k, 0) + n
                last_loot_got = got
                live["loot_lines"].append(ln)
            frame = res.get("frame") if isinstance(res.get("frame"), dict) else {}
            live["skill_results"].append({"line": ln, "t": t, "skill": action, "ok": ok,
                                          "placed": frame.get("placed") if frame else None,
                                          "error": res.get("error")})
        elif typ == "route_loot":
            got = res.get("got")
            if isinstance(got, list):
                if got != last_loot_got:  # not an echo of the loot_chest skill_result
                    for k, n in parse_item_list(got).items():
                        inv[k] = inv.get(k, 0) + n
                    live["loot_lines"].append(ln)
                last_loot_got = None
        elif typ == "route_inventory":
            inv = parse_item_list(e.get("items"))
            live["inventory_snapshots"].append({"line": ln, "t": t, "inv": dict(inv)})
        elif typ == "summary":
            pos = _pos_tuple(e.get("positions") or e.get("pos")) or pos
            live["summary"] = {"line": ln, "t": t,
                               **{k: e.get(k) for k in ("elapsedS", "actions", "failures", "deaths",
                                                        "splits", "finalSplit", "runId")}}
            if e.get("runId"):
                tl.meta.setdefault("run_id", e["runId"])
        elif typ in ("death", "died", "death_suspected"):
            add_event("death" if typ != "death_suspected" else typ, t, ln, _pos_tuple(e.get("pos")) or pos)
            live["deaths"].append(ln)
        elif typ in ("split", "milestone"):
            name = _EVENT_ALIASES.get(str(e.get("split") or e.get("name") or ""),
                                      str(e.get("split") or e.get("name") or ""))
            if name:
                add_event(name, t, ln, pos, derived="split_event")
                live["split_events"].append(ln)
        elif typ in MILESTONES or typ in _EVENT_ALIASES:
            add_event(_EVENT_ALIASES.get(typ, typ), t, ln, pos)
            live["split_events"].append(ln)
        if new_dim:
            dim = new_dim
        if dim and prev_dim and dim != prev_dim:
            mt = ("end_entered" if dim == "the_end" else "nether_entered" if dim == "the_nether"
                  else "nether_exited" if prev_dim == "the_nether" else None)
            if mt:
                add_event(mt, t, ln, pos, derived="dimension_change")
        prev_dim = dim or prev_dim
        tl.samples.append(Sample(t=t, line=ln, pos=pos, dim=dim or "overworld", inv=dict(inv),
                                 action=action, action_failed=failed, kind=typ,
                                 action_desc=(res.get("error") if failed else None),
                                 result=("FAILED: " + str(res.get("error") or "not ok")) if failed
                                 else ("ok" if action else None)))
    tl.events.sort(key=lambda ev: (ev["t"], ev["line"]))
    tl.knowledge = knowledge
    tl.meta.update({
        "path": str(path), "lines": len(events), "malformed_lines": len(malformed),
        "malformed_line_numbers": malformed[:50], "untimed_lines": len(untimed), "t0_epoch": t0,
        "duration_s": round(timed[-1]["_t"] - t0, 3) if timed else 0.0,
        "event_type_counts": _counts(e.get("type") for e in good),
        "knowledge_source": "route_start" if knowledge else "none",
        "live_agent": live,
    })
    return tl
