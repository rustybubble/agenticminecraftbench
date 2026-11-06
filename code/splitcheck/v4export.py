"""Export a game log as a SCHEMA section 8 `agent_timeline` (the v4 efficiency-check input).

to_timeline(tl_or_log_path, seed_dir=None, baseline_path=None, findings=None) -> dict

Built on RunEval: `timeline.load_timeline` (both log formats), `seedfeatures` (end portal
fallback) and `runeval.evaluate_run` (findings -> waste_extra). Deterministic: no clock,
no randomness, no network; floats rounded to 3 places; lists in a fixed order.

Milestones (low == high, seconds since the run's start event):
  M_start      = 0 (run start)
  M_portal_in  = first dimension change to the_nether (logged event or sample change, earliest)
  M_end_in     = first change to the_end after M_portal_in
  M_portal_out = LAST the_nether -> overworld change before M_end_in, skipping respawns (a change
                 to the overworld within RESPAWN_WINDOW_S of a death/death_suspected event);
                 earlier exits are extra round trips, listed as wrong_order waste
  M_finish     = game_won / exit portal (the_end -> overworld, not a respawn); else dragon_killed
                 as a flagged proxy ("finish_flag"); else NOT reached (the last sample never stands
                 in for a finish, so the end segment and the total are not scored).
A milestone that never happened is {"low": null, "high": null, "reached": false, "note": ...}.

CLI: python -m splitcheck.v4export <log> [--out agent_runs/<run>/timeline.json]
         [--seed-dir DIR] [--baseline PATH] [--rules PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from .logeval import _inv, load_events
from .timeline import Timeline, load_timeline

DEFAULT_BASELINE = "baseline/pro_2m49_segments.json"
DEFAULT_RULES = Path(__file__).resolve().parents[2] / "baseline" / "rules.json"
MILESTONE_IDS = ("M_start", "M_portal_in", "M_portal_out", "M_end_in", "M_finish")
WASTE_TAGS = ("extra_items", "longer_path", "failed_or_retried_action", "idle_wait",
              "unnecessary_risk", "wrong_order", "missed_shortcut")
# RunEval finding code -> SCHEMA section 8 waste tag
CODE_TO_TAG = {
    "excess_food": "extra_items", "excess_tools": "extra_items", "excess_materials": "extra_items",
    "path_efficiency": "longer_path", "overshoot_waypoint": "longer_path",
    "oscillation": "longer_path", "unneeded_structure_visit": "longer_path",
    "overworld_travel_when_nether_known": "missed_shortcut",
    "failed_action": "failed_or_retried_action", "action_loop": "failed_or_retried_action",
    "lost_drop": "failed_or_retried_action", "mining_in_water": "failed_or_retried_action",
    "no_progress": "failed_or_retried_action",
    "idle": "idle_wait",
    "damage_taken": "unnecessary_risk", "death": "unnecessary_risk",
    "place_then_recover": "wrong_order", "portal_method": "wrong_order",
    "obsidian_source": "wrong_order",
}
# zero-cost findings still worth listing (a death ends a real run)
KEEP_ZERO_COST = ("death",)
# consecutive same-dimension samples further apart than this are a teleport/respawn, not walking
TELEPORT_BLOCKS = 64.0
# a change to the overworld this soon after a death event is a respawn, not a portal
RESPAWN_WINDOW_S = 15.0
RESPAWN_LEAD_S = 2.0  # poller death_suspected is logged on the health reset, at or just after respawn
FALLBACK_SEGMENTS = [
    {"segment": "spawn_to_nether", "from": "M_start", "to": "M_portal_in"},
    {"segment": "nether", "from": "M_portal_in", "to": "M_portal_out"},
    {"segment": "exit_to_end_portal", "from": "M_portal_out", "to": "M_end_in"},
    {"segment": "end", "from": "M_end_in", "to": "M_finish"},
]


def _rel(p) -> str:
    """Repo-relative POSIX path when inside the repo, so output does not depend on how the path
    was typed (relative vs absolute)."""
    try:
        return Path(p).resolve().relative_to(Path(__file__).resolve().parents[2]).as_posix()
    except (ValueError, OSError):
        return str(p)


def _r(x, nd=3):
    return None if x is None else round(float(x), nd)


def _xyz(p):
    if p is None:
        return None
    return {"x": _r(p[0]), "y": _r(p[1]) if p[1] is not None else None, "z": _r(p[2])}


def _segments(rules_path=None):
    p = Path(rules_path) if rules_path else DEFAULT_RULES
    try:
        segs = json.loads(p.read_text(encoding="utf-8")).get("segments")
        if segs:
            return [{"segment": s["segment"], "from": s["from"], "to": s["to"]} for s in segs]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return [dict(s) for s in FALLBACK_SEGMENTS]


# ---------------------------------------------------------------- milestones
def _dim_changes(tl: Timeline):
    """[(t, line, prev_dim, new_dim, pos)] from the samples' dimension field."""
    out, prev = [], None
    for s in tl.samples:
        if not s.dim:
            continue
        if prev and s.dim != prev:
            out.append((s.t, s.line, prev, s.dim, s.pos))
        prev = s.dim
    return out


def _first(cands, after):
    """Earliest (t, line, pos, how) with t >= after."""
    ok = [c for c in cands if c[0] is not None and c[0] >= after]
    return min(ok, key=lambda c: (c[0], c[1])) if ok else None


def _deaths_t(ev):
    return sorted(e["t"] for e in ev if e["type"] in ("death", "death_suspected"))


def _is_respawn(t, death_ts):
    """A dimension change to the overworld within RESPAWN_WINDOW_S after (or just before) a
    death / death_suspected event is a respawn, not a portal."""
    return any(d - RESPAWN_LEAD_S <= t and t - d <= RESPAWN_WINDOW_S for d in death_ts)


def _milestones(tl: Timeline):
    """Returns (milestones, finish_note, finish_flag, extra_trips).

    M_portal_in  = first change to the_nether.
    M_end_in     = first change to the_end after M_portal_in.
    M_portal_out = LAST the_nether -> overworld change before M_end_in (or before the log ends),
                   skipping respawns after a death; earlier exits are extra round trips.
    M_finish     = game_won, or the_end -> overworld that is not a respawn; dragon_killed is a
                   flagged proxy; otherwise not reached (never the last sample)."""
    changes = _dim_changes(tl)
    ev = [e for e in tl.events if isinstance(e.get("t"), (int, float))]
    death_ts = _deaths_t(ev)

    def evc(typ):
        return [(e["t"], e["line"], e.get("pos"), f"{typ} event" + (" (derived)" if e.get("derived") else ""))
                for e in ev if e["type"] == typ]

    def chg(pred, label):
        return [(t, ln, pos, label) for t, ln, prev, new, pos in changes if pred(prev, new)]

    start = next((e for e in ev if e["type"] == "start"), None)
    ms = {"M_start": (0.0, start["line"] if start else None, start.get("pos") if start else None,
                      "run start")}
    pin = _first(evc("nether_entered") + chg(lambda a, b: b == "the_nether", "dimension -> the_nether"), 0.0)
    ms["M_portal_in"] = pin
    end_in = _first(evc("end_entered") + chg(lambda a, b: b == "the_end", "dimension -> the_end"),
                    pin[0]) if pin else None
    pout, extra_trips = None, []
    if pin:
        lim = end_in[0] if end_in else math.inf
        exits = [c for c in evc("nether_exited") + chg(lambda a, b: a == "the_nether" and b == "overworld",
                                                         "dimension the_nether -> overworld")
                 if c[0] >= pin[0] and c[0] <= lim and not _is_respawn(c[0], death_ts)]
        # one exit per time (a logged event and the sample change at the same moment)
        by_t = {}
        for c in sorted(exits, key=lambda c: (c[0], c[1])):
            by_t.setdefault(_r(c[0]), c)
        exits = [by_t[k] for k in sorted(by_t)]
        if exits:
            pout = exits[-1]
            reentries = sorted(t for t, *_ in evc("nether_entered") + chg(lambda a, b: b == "the_nether", ""))
            for c in exits[:-1]:
                back = next((t for t in reentries if t > c[0]), None)
                if back is not None and back <= pout[0]:
                    extra_trips.append((c[0], back, c[1]))
    ms["M_portal_out"] = pout
    ms["M_end_in"] = end_in

    fin, note, flag = None, None, None
    if end_in:
        exits = [c for c in chg(lambda a, b: a == "the_end" and b == "overworld",
                                "exit portal (the_end -> overworld)")
                 if not _is_respawn(c[0], death_ts)]
        fin = _first(evc("game_won") + exits, end_in[0])
        if fin is None:
            fin = _first(evc("dragon_killed"), end_in[0])
            if fin:
                note = "no game_won/exit-portal event; dragon_killed used as a proxy finish"
                flag = "proxy_finish_dragon_killed"
    if fin is None:
        last_t = max([s.t for s in tl.samples] + [e["t"] for e in ev] + [0.0])
        note = (f"unfinished: no finish event (log ends at t={_r(last_t)} s"
                + (", after a death" if death_ts else "") + "); end segment and total not scored")
        flag = "unfinished"
    ms["M_finish"] = fin
    return ms, note, flag, extra_trips


# ---------------------------------------------------------------- facts
def _seg_of(t, bounds):
    """Segment name for time t; bounds = [(name, t_from, t_to)] with None for unreached."""
    name = None
    for nm, a, b in bounds:
        if a is None:
            break
        name = nm
        if b is None or t < b:
            return nm
    return name  # past the finish -> last reached segment


def _beds(tl: Timeline, raw: list[dict], finished: bool = True):
    """(beds_collected, beds_used). collected = most beds held at once (placing a bed and picking
    it back up is not a new bed). used = beds consumed in the_end / bed_explode events; None when
    the run never finished the dragon fight, since unused beds then say nothing about waste."""
    known = {e["_line"] for e in raw if _inv(e) is not None}
    held = used = 0
    prev = None
    for s in tl.samples:
        if s.line not in known:
            continue
        n = sum(v for k, v in s.inv.items() if k.endswith("_bed"))
        held = max(held, n)
        if prev is not None and n < prev and s.dim == "the_end":
            used += prev - n
        prev = n
    explodes = sum(1 for e in raw if e.get("type") == "bed_explode")
    return held, (max(used, explodes) if finished else None)


def _latency(raw: list[dict], source: str):
    if source != "agent":
        return None
    ms = 0.0
    for e in raw:
        if e.get("type") in ("decision", "plan"):
            try:
                ms += float(e.get("latencyMs") or 0)
            except (TypeError, ValueError):
                pass
    return _r(ms / 1000.0)


# a segment with no single destination: straight-line distance is not meaningful
NO_DESTINATION = {"end": "dragon fight: no single destination, straight_blocks not computed"}


def _seg_facts(tl: Timeline, bounds):
    """Per segment: path_blocks (horizontal walk between consecutive same-dimension samples,
    teleports skipped), straight_blocks (first -> last sample in the segment's main dimension)
    and failed_actions (results starting with FAILED)."""
    out = {nm: {"path_blocks": 0.0, "straight_blocks": None, "failed_actions": 0}
           for nm, _, _ in bounds}
    pts, prev = {}, {}
    for s in tl.samples:
        nm = _seg_of(s.t, bounds)
        if nm is None:
            continue
        if s.action_failed:
            out[nm]["failed_actions"] += 1
        if s.pos is None or s.dim is None:
            continue
        p = prev.get(nm)
        if p is not None and p[0] == s.dim:
            d = math.hypot(s.pos[0] - p[1][0], s.pos[2] - p[1][2])
            if d <= TELEPORT_BLOCKS:
                out[nm]["path_blocks"] += d
        prev[nm] = (s.dim, s.pos)
        pts.setdefault(nm, []).append((s.dim, s.pos))
    for nm, o in out.items():
        o["path_blocks"] = _r(o["path_blocks"])
        o["distance"] = "horizontal (x,z) blocks"
        if nm in NO_DESTINATION:
            o["straight_note"] = NO_DESTINATION[nm]
            continue
        ps = pts.get(nm, [])
        if not ps:
            continue
        counts = {}
        for d, _ in ps:
            counts[d] = counts.get(d, 0) + 1
        main = min(counts, key=lambda d: (-counts[d], d))
        sub = [p for d, p in ps if d == main]
        a, b = sub[0], sub[-1]
        o["straight_blocks"] = _r(math.hypot(b[0] - a[0], b[2] - a[2]))
        o["dimension"] = main
    return out


def _end_portal(tl: Timeline, seed_dir):
    k = tl.knowledge or {}
    for key in ("endPortal", "activePortal", "end_portal"):
        v = k.get(key)
        if isinstance(v, dict) and v.get("x") is not None and v.get("z") is not None:
            return ({"x": _r(v["x"]), "y": _r(v.get("y")), "z": _r(v["z"])},
                    f"disclosed to the player (knownSeed {key})")
    try:
        from .seedfeatures import load_seed_features
        ep = (load_seed_features(seed_dir) or {}).get("end_portal")
        if ep:
            return ({"x": _r(ep["x"]), "y": _r(ep.get("y")), "z": _r(ep["z"])},
                    f"seed features ({ep.get('source')}); not disclosed to the player")
    except Exception as ex:  # seed features are optional context
        return None, f"unavailable: {type(ex).__name__}: {ex}"
    return None, "unavailable"


# ---------------------------------------------------------------- waste_extra
def _findings_list(findings):
    if isinstance(findings, dict):
        findings = findings.get("findings", [])
    return list(findings or [])


def _waste_extra(findings, bounds):
    out, unmapped = [], {}
    for f in findings:
        code = str(f.get("code"))
        tag = CODE_TO_TAG.get(code)
        cost = float(f.get("cost_s") or 0.0)
        if tag is None:
            unmapped[code] = unmapped.get(code, 0) + 1
            continue
        if cost <= 0 and code not in KEEP_ZERO_COST:
            continue
        lines = sorted({int(n) for n in (f.get("lines") or []) if n is not None})
        t0 = float(f.get("t_start") or 0.0)
        seg = _seg_of(t0, bounds) or bounds[0][0]
        span = (f"line {lines[0]}" if len(lines) == 1 else
                f"lines {lines[0]}-{lines[-1]}" if lines else "no log line")
        out.append({
            "segment": seg, "tag": tag, "seconds": _r(cost),
            "evidence": f"RunEval {code} at t={_r(t0)} s ({span}): {f.get('message', '')}",
            "runeval_code": code, "lines": lines, "t_start": _r(t0),
            "attributed_s": _r(f.get("attributed_s")) if f.get("attributed_s") is not None else None,
        })
    seg_order = {nm: i for i, (nm, _, _) in enumerate(bounds)}
    out.sort(key=lambda w: (seg_order.get(w["segment"], 99), w["t_start"], w["runeval_code"],
                            w["lines"][:1] or [0], -w["seconds"]))
    return out, dict(sorted(unmapped.items()))


# ---------------------------------------------------------------- main entry
def to_timeline(tl_or_log_path, seed_dir=None, baseline_path=None, findings=None, rules_path=None) -> dict:
    if isinstance(tl_or_log_path, Timeline):
        tl = tl_or_log_path
        log_path = (tl.meta or {}).get("path")
    else:
        log_path = str(tl_or_log_path)
        tl = load_timeline(log_path)
    raw = load_events(log_path) if log_path else []
    raw = [e for e in raw if e.get("type") != "_parse_error"]

    ms, finish_note, finish_flag, extra_trips = _milestones(tl)
    milestones = {}
    for mid in MILESTONE_IDS:
        m = ms.get(mid)
        if m is None:
            milestones[mid] = {"low": None, "high": None, "reached": False,
                               "note": finish_note if mid == "M_finish" and finish_note else "not reached in the log"}
            continue
        t, ln, _pos, how = m
        entry = {"low": _r(t), "high": _r(t), "line": ln, "evidence": how}
        if mid == "M_finish" and finish_note:
            entry["note"] = finish_note
        if mid == "M_finish" and finish_flag:
            entry["proxy"] = True
        milestones[mid] = entry

    segs = _segments(rules_path)
    bounds = [(s["segment"], milestones.get(s["from"], {}).get("low"),
               milestones.get(s["to"], {}).get("low")) for s in segs]

    pout = ms.get("M_portal_out")
    arrival = pout[2] if pout else None
    if arrival is None and pout:  # event without position: first sample at/after it
        s = next((s for s in tl.samples if s.t >= pout[0] and s.pos and s.dim == "overworld"), None)
        arrival = s.pos if s else None
    end_xyz, end_src = _end_portal(tl, seed_dir)
    collected, used = _beds(tl, raw, finished=ms.get("M_finish") is not None)
    deaths = sum(1 for e in raw if e.get("type") in ("death", "death_suspected"))

    if findings is None and log_path:
        from .runeval import evaluate_run
        findings = evaluate_run(log_path, seed_dir=seed_dir)
    waste, unmapped = _waste_extra(_findings_list(findings), bounds)
    for t_out, t_back, ln in extra_trips:  # extra Nether round trips before the real exit
        waste.append({"segment": _seg_of(t_out, bounds) or bounds[0][0], "tag": "wrong_order",
                      "seconds": _r(t_back - t_out),
                      "evidence": f"extra Nether exit at t={_r(t_out)} s (line {ln}), back in at "
                                  f"t={_r(t_back)} s; the real exit is the last one before the End",
                      "runeval_code": "extra_nether_round_trip", "lines": [ln] if ln else [],
                      "t_start": _r(t_out), "attributed_s": None})

    facts = {
        "overworld_arrival_xyz": _xyz(arrival),
        "end_portal_xyz": end_xyz,
        "end_portal_source": end_src,
        "beds_collected": collected,
        "beds_used": used,
        "model_latency_s": _latency(raw, tl.source),
        "deaths": deaths,
    }
    if facts["overworld_arrival_xyz"] is None:
        del facts["overworld_arrival_xyz"]
    if used is None:
        facts["beds_used_note"] = "unknown: the run did not finish the dragon fight"
    if facts["end_portal_xyz"] is None:
        del facts["end_portal_xyz"]
    facts.update(_seg_facts(tl, bounds))

    run_id = Path(log_path).stem if log_path else "run"
    return {
        "run_id": run_id,
        "kind": "agent_timeline",
        "source": tl.source,
        "log": _rel(log_path) if log_path else None,
        "baseline": str(baseline_path) if baseline_path else DEFAULT_BASELINE,
        "milestones": milestones,
        "finish_flag": finish_flag,
        "facts": facts,
        "waste_extra": waste,
        "waste_extra_unmapped_codes": unmapped,
        "notes": [
            "Milestones read from the game log: low == high (no montage cuts).",
            "waste_extra comes from RunEval findings (cost_s estimates); it is listed per segment and "
            "does not change verdicts. attributed_s is RunEval's de-duplicated share.",
        ],
    }


def to_json(d: dict) -> str:
    return json.dumps(d, indent=1, sort_keys=True) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m splitcheck.v4export", description=__doc__.split("\n")[0])
    ap.add_argument("log")
    ap.add_argument("--out")
    ap.add_argument("--seed-dir")
    ap.add_argument("--baseline")
    ap.add_argument("--rules")
    a = ap.parse_args(argv)
    txt = to_json(to_timeline(a.log, seed_dir=a.seed_dir, baseline_path=a.baseline, rules_path=a.rules))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(txt, encoding="utf-8")
    else:
        sys.stdout.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
