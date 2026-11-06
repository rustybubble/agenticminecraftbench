"""Seed-aware DECISION detectors (deterministic, stdlib only, no LLM).

Each detector judges a choice only against information the player had:
  * tl.knowledge (agent: union of knownSeed; human: --route-sheet), or
  * when knowledge is empty, seed features (ctx["seed"]) the player came within
    PROXIMITY_BLOCKS of -- such findings are REPORT-ONLY (cost_s = 0, evidence["report_only"]),
    because being near a feature does not mean the player knew of it (it may be underground or
    inside a house). Messages say "nearby (not disclosed)" instead of "known".

Detectors are pure functions f(tl, ctx) -> list[Finding]; SEED_REGISTRY maps code -> function.
ctx keys used: "seed" (load_seed_features output), "pro_splits" (list of {split, time_s}),
"splits" (runeval's canonical splits; recomputed from tl.events when absent).

Constants (all estimates, cited in every finding that uses them):
  SPRINT_BPS 7.127 blocks/s average sprint-JUMP speed (plain sprint is 5.612 b/s, so detour
  times priced with this constant are lower bounds); MINE_OBSIDIAN_S 9.4 s/block with a diamond pickaxe
  (Java 1.16.5, no efficiency); NETHER_SCALE 8; PORTAL_OVERHEAD_S 8 s (two 4 s portal transitions: into and out of the
  Nether, i.e. one Nether crossing).
"""
from __future__ import annotations

import math
import re

from .logeval import SPLIT_ORDER, _canon, _norm_dim

SPRINT_BPS = 7.127
MINE_OBSIDIAN_S = 9.4
PLACE_BLOCK_S = 0.5
NETHER_SCALE = 8.0
PORTAL_OVERHEAD_S = 8.0
PROXIMITY_BLOCKS = 32.0
CHEST_REACH = 4.5
VISIT_RADIUS = 16.0
VISIT_MIN_S = 20.0
REACH = 4.0
PATH_FLAG_RATIO = 2.0
MIN_LEG_BLOCKS = 8.0
MIN_TRAVEL_BLOCKS = 64.0
FULL_PORTAL = 10
MAX_DT = 10.0  # a gap between samples longer than this is not counted as dwell/travel

MINE_RE = re.compile(r"\b(mine|mined|mining|dig|dug|break|broke)\b|mine_|_mine|dig_", re.I)
LOOT_RE = re.compile(r"loot|chest|withdraw", re.I)
# canonical feature roles that are "on the route" when nothing was disclosed
ROUTE_ROLES = ("entryportal", "entryportalnetherside", "exitportal", "exitportaloverworldside",
               "endportal", "netherroute", "nethertravel", "stronghold", "activeportal", "beds",
               "preparationbeds", "spawn")
NEVER_DETOUR = ("spawn",)  # dwelling at spawn is the run start, never a detour


# ---------------------------------------------------------------- Finding (lazy import)
def _finding(**kw):
    """Build detectors.Finding lazily (avoids a circular import if detectors imports us)."""
    try:
        from .detectors import Finding
    except ImportError:  # pragma: no cover - fallback when detectors.py is absent
        from dataclasses import make_dataclass
        Finding = make_dataclass("Finding", ["code", "category", "severity", "t_start", "t_end",
                                             "cost_s", "lines", "message", "evidence"])
    kw["t_start"] = round(float(kw["t_start"]), 3)
    kw["t_end"] = round(float(kw["t_end"]), 3)
    kw["cost_s"] = round(max(0.0, float(kw["cost_s"])), 3)
    kw["lines"] = sorted({int(x) for x in kw["lines"] if x is not None})
    return Finding(**kw)


# ---------------------------------------------------------------- geometry / features
def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _role(name: str) -> str:
    """'entryPortal' / 'entry_portal' / 'chests_2' -> 'entryportal' / 'chests'."""
    base = re.sub(r"_\d+$", "", str(name))
    return base.replace("_", "").lower()


def _hd(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def _d3(a, b):
    ya, yb = a[1], b[1]
    dy = (ya - yb) if ya is not None and yb is not None else 0.0
    return math.sqrt((a[0] - b[0]) ** 2 + dy ** 2 + (a[2] - b[2]) ** 2)


def _same_dim(sdim, fdim):
    return sdim is None or fdim is None or _norm_dim(sdim) == _norm_dim(fdim)


def _point(p):
    if isinstance(p, dict) and isinstance(p.get("position"), dict):
        q = dict(p)
        q.update(p["position"])
        p = q
    if isinstance(p, dict):
        x, y, z = _num(p.get("x")), _num(p.get("y")), _num(p.get("z"))
        if x is not None and z is not None:
            return p, (x, y, z)
    return None, None


def _features_from(src: dict, source_label: str) -> list[dict]:
    """{name: point | [points]} -> [{name, role, pos, dim, raw, source}] (sorted, deterministic)."""
    out = []
    if not isinstance(src, dict):
        return out
    for key in sorted(src):
        if _role(key) == "remainingchests":
            continue
        val = src[key]
        items = [(key, val)] if not isinstance(val, list) else [(f"{key}_{i}", v) for i, v in enumerate(val)]
        for name, v in items:
            raw, pos = _point(v)
            if pos is None:
                continue
            role = _role(name)
            dim = _norm_dim(raw.get("dim") or raw.get("dimension"))
            if dim is None:
                dim = "the_nether" if role in ("exitportal", "netherroute", "nethertravel") else "overworld"
            out.append({"name": name, "role": role, "pos": pos, "dim": dim, "raw": dict(raw),
                        "source": raw.get("source") or source_label})
    return out


def _seed_features(ctx) -> list[dict]:
    out, seen = [], set()
    for f in _features_from((ctx or {}).get("seed") or {}, "seed_features"):
        key = (f["dim"], round(f["pos"][0]), round(f["pos"][1] or 0), round(f["pos"][2]))
        if key not in seen:  # e.g. supply_chests duplicates chests
            seen.add(key)
            out.append(f)
    return out


def _samples(tl):
    return sorted((s for s in tl.samples if s.t is not None), key=lambda s: (s.t, s.line))


def _pos_samples(tl):
    return [s for s in _samples(tl) if s.pos is not None]


def _min_dist(tl, feat):
    best = None
    for s in _pos_samples(tl):
        if _same_dim(s.dim, feat["dim"]):
            d = _d3(s.pos, feat["pos"])
            if best is None or d < best[0]:
                best = (d, s)
    return best


def _knowledge(tl, ctx):
    """Features the player is judged against + basis label.

    knowledge non-empty -> (knowledge features enriched with seed data at the same spot, 'disclosed')
    empty             -> (seed features the player came within 32 blocks of, 'proximity_32')
    """
    seed = _seed_features(ctx)
    kn = getattr(tl, "knowledge", None) or {}
    if kn:
        feats = _features_from(kn, "knowledge")
        for f in feats:  # enrich with seed contents (e.g. chest loot) at the same position
            for sf in seed:
                if _same_dim(sf["dim"], f["dim"]) and _d3(sf["pos"], f["pos"]) <= 1.5:
                    for k, v in sf["raw"].items():
                        f["raw"].setdefault(k, v)
                    f.setdefault("seed_name", sf["name"])
        return feats, "disclosed"
    near = []
    for f in seed:
        md = _min_dist(tl, f)
        if md and md[0] <= PROXIMITY_BLOCKS:
            f = dict(f, closest_approach=round(md[0], 2), closest_line=md[1].line)
            near.append(f)
    return near, "proximity_32"


def _basis_note(basis):
    if basis == "disclosed":
        return "judged against features disclosed to the player (Timeline.knowledge)"
    return ("no disclosed knowledge: judged only against seed features the player came within "
            f"{PROXIMITY_BLOCKS:.0f} blocks of")


def _kref(f):
    return {"name": f["name"], "pos": list(f["pos"]), "dim": f["dim"], "source": f["source"]}


# ---------------------------------------------------------------- inventory helpers
def _count(inv, item):
    if not isinstance(inv, dict):
        return 0
    n = 0
    for k, v in inv.items():
        if str(k).replace("minecraft:", "") == item:
            try:
                n += int(v)
            except (TypeError, ValueError):
                pass
    return n


def _contents_count(raw, item):
    c = None
    for key in ("contents", "items", "loot"):
        if key in raw:
            c = raw[key]
            break
    if c is None:
        return None
    if isinstance(c, dict):
        return _count(c, item)
    n = 0
    for it in c if isinstance(c, list) else []:
        if isinstance(it, dict):
            if str(it.get("name", "")).replace("minecraft:", "") == item:
                n += int(it.get("count", 1) or 1)
        elif str(it).replace("minecraft:", "") == item:
            n += 1
    return n


def _text(s):
    return " ".join(str(x) for x in (s.action, getattr(s, "action_desc", None),
                                     getattr(s, "result", None)) if x)


def _inv_deltas(tl, item):
    """[(prev_sample, sample, delta)] where the item count changes between inventory samples."""
    out, prev = [], None
    for s in _samples(tl):
        if not s.inv and prev is not None and _count(prev.inv, item) > 0:
            continue  # sample without inventory info: skip, don't read as a drop to zero
        if prev is not None:
            d = _count(s.inv, item) - _count(prev.inv, item)
            if d:
                out.append((prev, s, d))
        prev = s
    return out


def _visit_time(tl, feat, radius):
    """(first t within `radius` blocks horizontally, same dim) or None."""
    for s in _pos_samples(tl):
        if _same_dim(s.dim, feat["dim"]) and _hd(s.pos, feat["pos"]) <= radius and \
                (s.pos[1] is None or feat["pos"][1] is None or abs(s.pos[1] - feat["pos"][1]) <= 6):
            return s.t, s.line
    return None


# ---------------------------------------------------------------- detector 1: obsidian_source
def detect_obsidian_source(tl, ctx) -> list:
    feats, basis = _knowledge(tl, ctx)
    chests = []
    for f in feats:
        if "chest" not in f["role"]:
            continue
        n = _contents_count(f["raw"], "obsidian")
        if n:
            chests.append((f, n, _visit_time(tl, f, CHEST_REACH)))
    if not chests:
        return []
    all_chests = [f for f in feats + _seed_features(ctx) if "chest" in f["role"]]
    mined = []  # (sample, count, unlooted chests at that time)
    for prev, s, d in _inv_deltas(tl, "obsidian"):
        if d <= 0:
            continue
        txt = _text(s)
        near_chest = s.pos is not None and any(
            _same_dim(s.dim, c["dim"]) and _d3(s.pos, c["pos"]) <= CHEST_REACH + 1 for c in all_chests)
        if MINE_RE.search(txt) and not LOOT_RE.search(txt):
            how = "action text says mined"
        elif not txt and not near_chest:
            how = "obsidian gained away from any chest, no action recorded (inferred mined)"
        else:
            continue
        unlooted = [(c, n) for c, n, v in chests if v is None or v[0] > s.t]
        if unlooted:
            mined.append((s, d, unlooted, how))
    if not mined:
        return []
    n_mined = sum(d for _, d, _, _ in mined)
    first = mined[0]
    # obsidian still sitting in chests unlooted at the first mining moment
    avail = sum(n for _, n in first[2])
    blocks = min(n_mined, avail)
    origin = first[0].pos
    near = [(c, n) for c, n in first[2]]
    if origin is not None:
        near.sort(key=lambda cn: (_hd(origin, cn[0]["pos"]), cn[0]["name"]))
        detour_blocks = 2.0 * _hd(origin, near[0][0]["pos"])
    else:
        detour_blocks = 0.0
    mine_s = blocks * MINE_OBSIDIAN_S
    detour_s = detour_blocks / SPRINT_BPS
    cost = mine_s - detour_s
    if cost <= 0:
        return []
    names = [c["name"] for c, _ in first[2]]
    return [_finding(
        code="obsidian_source", category="decision",
        severity="high" if cost >= 30 else "medium" if cost >= 10 else "low",
        t_start=first[0].t, t_end=mined[-1][0].t, cost_s=cost,
        lines=[m[0].line for m in mined],
        message=(f"Mined {n_mined} obsidian (lines {', '.join(str(m[0].line) for m in mined)}) while "
                 f"known chest(s) {', '.join(names)} holding {avail} obsidian were not yet looted; "
                 f"estimate {blocks} x {MINE_OBSIDIAN_S} s mining = {mine_s:.1f} s vs "
                 f"{detour_blocks:.1f}-block round-trip detour = {detour_s:.1f} s at {SPRINT_BPS} b/s "
                 f"-> {cost:.1f} s lost (estimate). {_basis_note(basis)}."),
        evidence={"estimate": True, "knowledge_basis": basis, "obsidian_mined": n_mined,
                  "blocks_replaceable_by_chests": blocks, "mining_s_per_block": MINE_OBSIDIAN_S,
                  "sprint_bps": SPRINT_BPS, "detour_blocks": round(detour_blocks, 2),
                  "mining_events": [{"t": m[0].t, "line": m[0].line, "count": m[1], "how": m[3],
                                     "pos": list(m[0].pos) if m[0].pos else None} for m in mined],
                  "knowledge_used": [dict(_kref(c), obsidian=n) for c, n in first[2]]})]


# ---------------------------------------------------------------- detector 2: portal_method
def _existing_frame(raw):
    if _num(raw.get("essential_existing")) is not None:  # curated: frame blocks that count (REVIEW.md:9)
        return int(_num(raw["essential_existing"]))
    for k in ("existing_frame_obsidian", "existing_frame_blocks", "existingFrameBlocks", "existing_obsidian", "frame_blocks",
              "frameBlocks", "existing_frame"):
        v = raw.get(k)
        if isinstance(v, list):
            return len(v)
        if _num(v) is not None:
            return int(_num(v))
    return None


def detect_portal_method(tl, ctx) -> list:
    feats, basis = _knowledge(tl, ctx)
    sites = [f for f in feats if f["role"] == "entryportal" and _existing_frame(f["raw"])]
    if not sites:
        return []
    site = sites[0]
    existing = _existing_frame(site["raw"])
    entry = next((e for e in sorted(tl.events, key=lambda e: (e["t"], e["line"]))
                  if e.get("type") == "nether_entered"), None)
    t_entry = entry["t"] if entry else float("inf")
    used, lines, t0, t1 = 0, [], None, None
    for prev, s, d in _inv_deltas(tl, "obsidian"):
        if d >= 0 or s.t > t_entry or not _same_dim(s.dim, "overworld"):
            continue
        used += -d
        lines.append(s.line)
        t0 = s.t if t0 is None else t0
        t1 = s.t
    if used <= FULL_PORTAL - existing:
        return []
    extra = min(used - (FULL_PORTAL - existing), existing)
    if extra <= 0:
        return []
    any_mined = any(d > 0 and MINE_RE.search(_text(s)) for _, s, d in _inv_deltas(tl, "obsidian"))
    per = MINE_OBSIDIAN_S if any_mined else PLACE_BLOCK_S
    cost = extra * per
    return [_finding(
        code="portal_method", category="decision", severity="medium" if cost >= 10 else "low",
        t_start=t0, t_end=t1, cost_s=cost, lines=lines + ([entry["line"]] if entry else []),
        message=(f"Placed {used} obsidian for the Nether portal (lines {lines[0]}-{lines[-1]}) although the "
                 f"known entry portal site {site['name']} {tuple(site['pos'])} already has {existing} frame "
                 f"blocks: {extra} extra block(s) x {per} s ("
                 f"{'mining time, obsidian was mined this run' if any_mined else 'placement time'}) = "
                 f"{cost:.1f} s (estimate). {_basis_note(basis)}."),
        evidence={"estimate": True, "knowledge_basis": basis, "obsidian_placed": used,
                  "existing_frame_blocks": existing, "extra_blocks": extra, "s_per_block": per,
                  "knowledge_used": [_kref(site)]})]


# ---------------------------------------------------------------- legs / travel helpers
def _dim_runs(tl):
    """Contiguous runs of position samples in one dimension."""
    runs, cur = [], []
    for s in _pos_samples(tl):
        if cur and s.dim and cur[-1].dim and s.dim != cur[-1].dim:
            runs.append(cur)
            cur = []
        cur.append(s)
    if cur:
        runs.append(cur)
    return runs


def _path_len(samples):
    total = 0.0
    for a, b in zip(samples, samples[1:]):
        if b.t - a.t <= MAX_DT:
            total += _hd(a.pos, b.pos)
    return total


# ---------------------------------------------------------------- detector 3: overworld travel
def detect_overworld_travel_when_nether_known(tl, ctx) -> list:
    feats, basis = _knowledge(tl, ctx)
    portals = [f for f in feats if f["role"] == "entryportal" and f["dim"] == "overworld"]
    targets = [f for f in feats if f["dim"] == "overworld" and f["role"] != "entryportal"]
    if not portals or not targets:
        return []
    out = []
    entries = sorted(e["t"] for e in tl.events if e.get("type") == "nether_entered")
    for run in _dim_runs(tl):
        if not run or not _same_dim(run[0].dim, "overworld") or len(run) < 2:
            continue
        # The Nether route only exists once the portal can be used: the player has already
        # entered the Nether, or holds a flint_and_steel (portal can be lit). Before that,
        # Overworld travel is the only option.
        # Feasible = already been through the Nether, or holding flint_and_steel AND the obsidian
        # for the entry frame (10 - existing frame blocks) plus a 10-block exit frame.
        need = (FULL_PORTAL - min(_existing_frame(p["raw"]) or 0 for p in portals)) + FULL_PORTAL
        k0 = next((i for i, s in enumerate(run)
                   if (entries and entries[0] <= s.t)
                   or (_count(s.inv, "flint_and_steel") > 0 and _count(s.inv, "obsidian") >= need)), None)
        if k0 is None:
            continue
        run = run[k0:]
        if len(run) < 2:
            continue
        start = run[0]
        best = None
        for tf in targets:
            straight = _hd(start.pos, tf["pos"])
            closest = min(run, key=lambda s: (_hd(s.pos, tf["pos"]), s.t))
            progress = straight - _hd(closest.pos, tf["pos"])  # net straight-line progress
            if progress > 0 and (best is None or progress > best[1]):
                best = (tf, progress, closest)
        if not best or best[1] < MIN_TRAVEL_BLOCKS:
            continue
        tf, toward, closest = best
        lines = [s.line for s in run if s.t <= closest.t]
        straight = _hd(start.pos, tf["pos"])
        portal = min(portals, key=lambda p: (_hd(start.pos, p["pos"]), p["name"]))
        to_portal = _hd(start.pos, portal["pos"])
        # Nether alternative for the same Overworld progress: walk to the known portal, cross the
        # portal->target distance at 1/8 scale, exit near the target; two portal transfers.
        nether_blocks = to_portal + _hd(portal["pos"], tf["pos"]) / NETHER_SCALE
        build_exit_s = FULL_PORTAL * PLACE_BLOCK_S  # place the 10-block exit frame
        nether_s = nether_blocks / SPRINT_BPS + PORTAL_OVERHEAD_S + build_exit_s
        ow_s = toward / SPRINT_BPS
        if ow_s <= nether_s:
            continue
        cost = ow_s - nether_s
        out.append(_finding(
            code="overworld_travel_when_nether_known", category="decision",
            severity="high" if cost >= 60 else "medium",
            t_start=start.t, t_end=closest.t, cost_s=cost, lines=[start.line, lines[0], lines[-1]],
            message=(f"Made {toward:.0f} blocks of straight-line progress through the Overworld toward known {tf['name']} "
                     f"{tuple(tf['pos'])} (lines {lines[0]}-{lines[-1]}; straight {straight:.0f} blocks) "
                     f"although the Nether route via known {portal['name']} was available: "
                     f"{to_portal:.0f} blocks to the portal + {_hd(portal['pos'], tf['pos']) / NETHER_SCALE:.0f} "
                     f"Nether blocks (portal->target / {NETHER_SCALE:.0f}) + {PORTAL_OVERHEAD_S:.0f} s portal transfers "
                     f"+ {build_exit_s:.0f} s exit-frame placement = {nether_s:.1f} s vs "
                     f"{ow_s:.1f} s at {SPRINT_BPS} b/s -> {cost:.1f} s (estimate). {_basis_note(basis)}."),
            evidence={"estimate": True, "knowledge_basis": basis, "overworld_toward_blocks": round(toward, 2),
                      "straight_blocks": round(straight, 2), "nether_alternative_blocks": round(nether_blocks, 2),
                      "portal_overhead_s": PORTAL_OVERHEAD_S, "exit_build_s": build_exit_s,
                      "obsidian_needed": need, "overworld_s": round(ow_s, 2),
                      "nether_s": round(nether_s, 2), "knowledge_used": [_kref(tf), _kref(portal)]}))
    return out


# ---------------------------------------------------------------- detector 4: unneeded visit
def detect_unneeded_structure_visit(tl, ctx) -> list:
    feats, basis = _knowledge(tl, ctx)
    seed = _seed_features(ctx)
    if basis == "disclosed":
        route = feats
        cands = [f for f in seed if f["role"] not in NEVER_DETOUR
                 and not any(_d3(f["pos"], r["pos"]) <= 4 for r in route)]
        note = "feature not in the disclosed route/knowledge"
    else:
        on = lambda f: f["role"] in ROUTE_ROLES or f["raw"].get("supply") is True
        route = [f for f in feats if on(f)]
        cands = [f for f in feats if not on(f) and f["role"] not in NEVER_DETOUR]
        note = ("no disclosed knowledge: route taken as canonical roles "
                f"({', '.join(ROUTE_ROLES)}) among features within {PROXIMITY_BLOCKS:.0f} blocks")
    out = []
    for f in cands:
        dwell, lines, t0, t1 = 0.0, [], None, None
        ps = _pos_samples(tl)
        for a, b in zip(ps, ps[1:]):
            if b.t - a.t > MAX_DT or not _same_dim(a.dim, f["dim"]):
                continue
            if _hd(a.pos, f["pos"]) > VISIT_RADIUS:
                continue
            if any(_same_dim(a.dim, r["dim"]) and _hd(a.pos, r["pos"]) <= VISIT_RADIUS for r in route):
                continue  # also near a route feature: not attributable to this detour
            dwell += b.t - a.t
            lines.append(a.line)
            t0 = a.t if t0 is None else t0
            t1 = b.t
        if dwell <= VISIT_MIN_S:
            continue
        transit = 2 * VISIT_RADIUS / SPRINT_BPS
        cost = dwell - transit
        out.append(_finding(
            code="unneeded_structure_visit", category="decision",
            severity="medium" if cost >= 30 else "low",
            t_start=t0, t_end=t1, cost_s=cost, lines=[lines[0], lines[-1]],
            message=(f"Spent {dwell:.1f} s within {VISIT_RADIUS:.0f} blocks of {f['name']} {tuple(f['pos'])} "
                     f"(lines {lines[0]}-{lines[-1]}), which is not on the known route ({note}); "
                     f"cost = dwell - {transit:.1f} s pass-through = {cost:.1f} s. {_basis_note(basis)}."),
            evidence={"knowledge_basis": basis, "dwell_s": round(dwell, 3), "radius": VISIT_RADIUS,
                      "pass_through_s": round(transit, 3), "samples": len(lines),
                      "feature": _kref(f), "knowledge_used": [r["name"] for r in route]}))
    return out


# ---------------------------------------------------------------- detector 5: stage_time
_EVENT_TO_SPLIT = {"nether_entered": "nether_entry", "nether_exited": "nether_exit",
                   "end_entered": "end_entry", "dragon_killed": "dragon_kill", "game_won": "game_won",
                   "start": "start"}


def _our_splits(tl, ctx):
    if ctx.get("splits"):
        return {_canon(s["split"]): s for s in ctx["splits"] if s.get("time_s") is not None}
    out = {"start": {"split": "start", "time_s": 0.0, "line": None}}
    for e in sorted(tl.events, key=lambda e: (e["t"], e["line"])):
        n = _EVENT_TO_SPLIT.get(e.get("type"))
        if n and (n not in out or n == "start" and out[n]["line"] is None):
            out[n] = {"split": n, "time_s": e["t"], "line": e["line"]}
    return out


def detect_stage_time(tl, ctx) -> list:
    """Per-stage duration vs pro. REPORT-ONLY (cost_s = 0): the excess is already explained by the
    specific findings inside the stage, so counting it again would double count."""
    pro = ctx.get("pro_splits")
    if isinstance(pro, dict):
        pro = pro.get("splits", [])
    if not pro:
        return []
    pros = {}
    for p in pro:
        c = _canon(p.get("split", ""))
        if c not in pros and isinstance(p.get("time_s"), (int, float)):
            pros[c] = p
    pros.setdefault("start", {"split": "start", "time_s": 0.0})
    ours = _our_splits(tl, ctx)
    common = [n for n in SPLIT_ORDER if n in ours and n in pros]
    out = []
    for a, b in zip(common, common[1:]):
        ours_d = ours[b]["time_s"] - ours[a]["time_s"]
        pro_d = pros[b]["time_s"] - pros[a]["time_s"]
        if pro_d <= 0 or ours_d <= pro_d:
            continue
        ratio = ours_d / pro_d
        out.append(_finding(
            code="stage_time", category="decision",
            severity="high" if ratio >= 3 else "medium" if ratio >= 1.5 else "low",
            t_start=ours[a]["time_s"], t_end=ours[b]["time_s"], cost_s=0.0,
            lines=[ours[a].get("line"), ours[b].get("line")],
            message=(f"Stage {a} -> {b} took {ours_d:.1f} s vs pro {pro_d:.1f} s "
                     f"(+{ours_d - pro_d:.1f} s, x{ratio:.2f}); report-only, not added to waste "
                     f"(the in-stage findings carry the cost)."),
            evidence={"report_only": True, "stage": f"{a}->{b}", "duration_s": round(ours_d, 3),
                      "pro_duration_s": round(pro_d, 3), "excess_s": round(ours_d - pro_d, 3),
                      "ratio": round(ratio, 3),
                      "pro_source": pros[b].get("run") or pros[b].get("source")}))
    return out


# ---------------------------------------------------------------- detector 6: path_efficiency
def path_legs(tl, ctx) -> list[dict]:
    """Every leg to a known target (first arrival within REACH blocks), with path stats."""
    feats, basis = _knowledge(tl, ctx)
    legs = []
    for run in _dim_runs(tl):
        arrivals = []
        for f in feats:
            if not _same_dim(run[0].dim, f["dim"]):
                continue
            for i, s in enumerate(run):
                if _hd(s.pos, f["pos"]) <= REACH:
                    arrivals.append((i, f))
                    break
        arrivals.sort(key=lambda a: (a[0], a[1]["name"]))
        start_i = 0
        for i, f in arrivals:
            if i <= start_i:
                start_i = max(start_i, i)
                continue
            seg = run[start_i:i + 1]
            straight = _hd(seg[0].pos, f["pos"])
            path = _path_len(seg)
            dt = seg[-1].t - seg[0].t
            if straight >= MIN_LEG_BLOCKS:
                ideal = straight / SPRINT_BPS
                legs.append({"target": f, "basis": basis, "t_start": seg[0].t, "t_end": seg[-1].t,
                             "line_start": seg[0].line, "line_end": seg[-1].line,
                             "path_blocks": round(path, 2), "straight_blocks": round(straight, 2),
                             "path_ratio": round(path / straight, 3), "time_s": round(dt, 3),
                             "ideal_time_s": round(ideal, 3),
                             "time_ratio": round(dt / ideal, 3) if ideal else None})
            start_i = i
    return legs


def detect_path_efficiency(tl, ctx) -> list:
    out = []
    for leg in path_legs(tl, ctx):
        if leg["path_ratio"] <= PATH_FLAG_RATIO:
            continue
        f = leg["target"]
        cost = (leg["path_blocks"] - leg["straight_blocks"]) / SPRINT_BPS
        out.append(_finding(
            code="path_efficiency", category="decision",
            severity="medium" if cost >= 20 else "low",
            t_start=leg["t_start"], t_end=leg["t_end"], cost_s=cost,
            lines=[leg["line_start"], leg["line_end"]],
            message=(f"Leg to known {f['name']} {tuple(f['pos'])} (lines {leg['line_start']}-{leg['line_end']}): "
                     f"path {leg['path_blocks']:.0f} blocks vs straight {leg['straight_blocks']:.0f} "
                     f"(x{leg['path_ratio']:.2f} > {PATH_FLAG_RATIO}); took {leg['time_s']:.1f} s vs "
                     f"{leg['ideal_time_s']:.1f} s at {SPRINT_BPS} b/s; extra distance = {cost:.1f} s. "
                     f"{_basis_note(leg['basis'])}."),
            evidence={"knowledge_basis": leg["basis"], "knowledge_used": [_kref(f)],
                      **{k: v for k, v in leg.items() if k not in ("target", "basis")}}))
    return out


def _disclosed_only(fn):
    """Decision costs only count against DISCLOSED knowledge. A finding judged on proximity alone
    (no route sheet / knownSeed) is kept as report-only with cost_s = 0."""
    def run(tl, ctx):
        out = []
        for f in fn(tl, ctx):
            ev = f.evidence if isinstance(f.evidence, dict) else {}
            if ev.get("knowledge_basis") == "proximity_32":
                ev["report_only"] = True
                ev["cost_if_known_s"] = f.cost_s
                f.cost_s = 0.0
                f.severity = "low"
                f.message = (f.message.replace("known ", "nearby (not disclosed) ")
                             + " Report-only: not charged, the player was never told about it.")
            out.append(f)
        return out
    run.__name__ = fn.__name__
    run.__doc__ = fn.__doc__
    return run


SEED_REGISTRY = {
    "obsidian_source": _disclosed_only(detect_obsidian_source),
    "portal_method": _disclosed_only(detect_portal_method),
    "overworld_travel_when_nether_known": _disclosed_only(detect_overworld_travel_when_nether_known),
    "unneeded_structure_visit": _disclosed_only(detect_unneeded_structure_visit),
    "stage_time": detect_stage_time,
    "path_efficiency": _disclosed_only(detect_path_efficiency),
}
