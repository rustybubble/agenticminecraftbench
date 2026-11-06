"""Validate AI perception observations against ground truth we already have.

validate(perception, timeline, server_timeline=None, seed_features=None)
    -> {"per_field": {field: {n, correct, accuracy}}, "cases": [...],
        "validated_fields": [...], "unvalidated_fields": [...], "rules": {...}, "notes": [...]}

The VLM only *perceives*; this module checks how often that perception agrees with labels that are
derived deterministically (pure functions, no AI) from the agent log, the server poller log and the
seed features. Only fields that have such a label are scored; every other OBS_SCHEMA field is listed
in ``unvalidated_fields`` and must be treated as unverified.

Time base: ``run_t`` on a perception entry is seconds since the agent run start (the agent
timeline's ``meta.t0_epoch``, i.e. the ``t+<N>s`` overlay clock). Server samples are mapped onto that
clock with their own ``t0_epoch`` (abs = t0 + t), as in evaluate.server_crosscheck.

Bot position at a frame (camera target), first rule that applies:
  1. nearest server position sample within POS_WINDOW_S (1.0 s) of run_t;
  2. nearest agent-log sample within POS_WINDOW_S;
  3. run_t lies between two consecutive agent samples whose positions are within STATIONARY_TOL
     (2 blocks) of each other (bot stationary, e.g. looting / building / lingering) -> the earlier one;
  otherwise the position is unknown and position-based labels are skipped for that frame.
Distances are horizontal (x/z), because the camera looks down from above. Overworld only.

Ground-truth label table (each label is a set of allowed values; a case is correct when the
observed value is in the set; frames in the ambiguous band between "near" and "far" get no label):

| field           | label                         | rule (d = horizontal distance from bot)                        |
|-----------------|-------------------------------|----------------------------------------------------------------|
| chest_visible   | {true}                        | d(nearest seed chest) <= CHEST_NEAR (8)                        |
| chest_visible   | {false}                       | d(nearest seed chest) >  CHEST_FAR (16)                        |
| village_visible | {true}                        | d(village center) <= VILLAGE_NEAR (24)                         |
|                 |                               | (no {false} label: the seed gives one center point, not the    |
|                 |                               | village extent; houses are visible 60 blocks away at the       |
|                 |                               | entry portal, so "far from the center" does not mean "none")   |
| obsidian_frame  | {partial} (+complete if built)| d(entry portal site) <= PORTAL_NEAR (10): ruined frame exists  |
|                 |                               | (seed features existing_frame_obsidian / groundtruth-check)    |
| obsidian_frame  | {none}                        | d(entry portal site) >  PORTAL_FAR (20)                        |
| obsidian_frame  | {none, partial}   LOG-DERIVED | any frame (incl. unknown position) when no build_portal result |
|                 |                               | with ok=true / placed>0 exists at or before run_t              |
| portal_lit      | {false}           LOG-DERIVED | no build_portal ok=true and no light/nether event <= run_t     |
| player_in_water | {true}/{false}                | server sample within WATER_WINDOW_S (1.0 s) with feet_block or |
|                 |                               | eye_block known: true iff either contains "water"              |

LOG-DERIVED labels come from the agent's own claim (build_portal ok/placed), which is exactly what
the footage is meant to check independently. Scoring the model against them would be circular, so
they are NOT counted in ``per_field``; they are reported separately in ``log_consistency`` as
"consistent with the agent-log claim". Only position/server-based labels are ground truth.

Every per_field row carries n, a 95% Wilson interval and ``sufficient`` (n >= MIN_N = 10). A field is
in ``validated_fields`` only when it is sufficient; fields with 0 < n < MIN_N are listed in
``insufficient_fields`` and must not gate a finding.

For agent-01: build_portal returned ok=false, placed=0 ("frame incomplete") and the bot never entered
the Nether (RUN_NOTES), so obsidian_frame is never "complete" and portal_lit is false at all times.

Unvalidated (no ground truth): lava_visible, water_visible, player_visible, player_activity, confidence.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

POS_WINDOW_S = 1.0
STATIONARY_TOL = 2.0
WATER_WINDOW_S = 1.0
CHEST_NEAR, CHEST_FAR = 8.0, 16.0
VILLAGE_NEAR, VILLAGE_FAR = 24.0, 48.0
PORTAL_NEAR, PORTAL_FAR = 10.0, 20.0
MIN_N = 10   # fewer ground-truth labels than this -> accuracy reported as insufficient

ALL_FIELDS = ["obsidian_frame", "portal_lit", "chest_visible", "village_visible", "lava_visible",
              "water_visible", "player_visible", "player_in_water", "player_activity", "confidence"]
LABELLED_FIELDS = ["chest_visible", "village_visible", "obsidian_frame", "portal_lit", "player_in_water"]

RULES = {
    "position": f"server sample within {POS_WINDOW_S}s, else agent sample within {POS_WINDOW_S}s, else "
                f"between two agent samples <= {STATIONARY_TOL} blocks apart; horizontal distance",
    "chest_visible": f"true if <= {CHEST_NEAR} blocks from a seed chest; false if > {CHEST_FAR}",
    "village_visible": f"true if <= {VILLAGE_NEAR} blocks from village center; no false label (extent unknown)",
    "obsidian_frame": f"partial (ruined frame) if <= {PORTAL_NEAR} blocks from entry portal site; none if "
                      f"> {PORTAL_FAR} (position-based ground truth); 'never complete before a "
                      f"successful build_portal' is log-derived and reported as log consistency only",
    "portal_lit": "log-derived only (false until a successful build_portal / light / nether event): "
                  "reported as log consistency, not ground truth",
    "player_in_water": f"server feet_block/eye_block contains 'water' (nearest sample within {WATER_WINDOW_S}s)",
}


# ---------------------------------------------------------------- inputs
def _entries(perception) -> list:
    """Accept a list of entries, or a perception.json dict holding one."""
    if isinstance(perception, (str, Path)):
        with open(perception, encoding="utf-8") as f:
            perception = json.load(f)
    if isinstance(perception, list):
        return perception
    for k in ("observations", "frames", "entries", "results", "perception"):
        v = perception.get(k)
        if isinstance(v, list):
            return v
    for v in perception.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "obs" in v[0]:
            return v
    return []


def _tl(x):
    if x is None or not isinstance(x, (str, Path)):
        return x
    from .timeline import load_timeline
    return load_timeline(str(x))


def _raw_lines(tl) -> dict:
    """line number -> raw event dict (for poller fields the Sample does not keep, e.g. feet_block)."""
    p = (getattr(tl, "meta", None) or {}).get("path")
    out = {}
    if not p or not os.path.exists(p):
        return out
    with open(p, encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            try:
                out[i] = json.loads(ln)
            except ValueError:
                pass
    return out


def _rel_samples(tl, origin):
    """[(run_t, sample)] on the agent-run clock."""
    if tl is None:
        return []
    t0 = (tl.meta or {}).get("t0_epoch")
    off = (t0 - origin) if (t0 is not None and origin is not None) else 0.0
    return [(round(s.t + off, 3), s) for s in tl.samples]


def _nearest(pairs, t, window):
    best = None
    for st, s in pairs:
        d = abs(st - t)
        if d <= window and (best is None or d < best[0]):
            best = (d, st, s)
    return best


def _hdist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


# ---------------------------------------------------------------- pure label derivation
def bot_position(run_t, agent_samples, server_samples):
    """(pos, basis) or (None, reason). Pure: depends only on its arguments."""
    sv = [(t, s) for t, s in server_samples if s.pos is not None and (s.dim in (None, "overworld"))]
    hit = _nearest(sv, run_t, POS_WINDOW_S)
    if hit:
        return hit[2].pos, f"server line {hit[2].line} (dt={round(hit[0], 3)}s)"
    ag = [(t, s) for t, s in agent_samples if s.pos is not None]
    hit = _nearest(ag, run_t, POS_WINDOW_S)
    if hit:
        return hit[2].pos, f"agent line {hit[2].line} (dt={round(hit[0], 3)}s)"
    for (ta, a), (tb, b) in zip(ag, ag[1:]):
        if ta <= run_t <= tb and math.dist(a.pos, b.pos) <= STATIONARY_TOL:
            return a.pos, f"agent stationary between lines {a.line}-{b.line}"
    return None, "position unknown"


def portal_state(run_t, agent_tl) -> dict:
    """Was a portal successfully built / lit at or before run_t, per the agent log?"""
    live = (agent_tl.meta or {}).get("live_agent") or {}
    built = any(r.get("skill") in ("build_portal", "light_portal") and r.get("t", 1e18) <= run_t
                and (r.get("ok") or (r.get("placed") or 0) > 0) for r in live.get("skill_results", []))
    lit = any(r.get("skill") == "build_portal" and r.get("ok") and r.get("t", 1e18) <= run_t
              for r in live.get("skill_results", []))
    lit = lit or any(s.dim == "the_nether" and s.t <= run_t for s in agent_tl.samples)
    lit = lit or any(str(e.get("type", "")).lower() in ("portal_lit", "light_portal", "enter_nether")
                     and e.get("t", 1e18) <= run_t for e in agent_tl.events)
    return {"built": built, "lit": lit}


LOG = "agent_log_claim"   # label source marker: derived from the claim under test, not ground truth


def is_log_derived(label) -> bool:
    return len(label) > 2 and label[2] == LOG


def wilson(correct: int, n: int, z: float = 1.96):
    if not n:
        return None
    p = correct / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def labels_for(run_t, pos, feats, pstate, water) -> dict:
    """field -> (allowed_values list, basis[, LOG]). Pure. A third element LOG marks a label that is
    derived from the agent's own claim (not ground truth; see module docstring)."""
    out = {}
    if pos is not None:
        chests = feats.get("supply_chests") or feats.get("chests") or []
        if chests:
            d = min(_hdist(pos, (c["x"], c["y"], c["z"])) for c in chests)
            if d <= CHEST_NEAR:
                out["chest_visible"] = ([True], f"{d:.1f} blocks from nearest chest")
            elif d > CHEST_FAR:
                out["chest_visible"] = ([False], f"{d:.1f} blocks from nearest chest")
        v = feats.get("village")
        if v:
            d = _hdist(pos, (v["x"], v["y"], v["z"]))
            if d <= VILLAGE_NEAR:
                out["village_visible"] = ([True], f"{d:.1f} blocks from village center")
        ep = feats.get("entry_portal")
        if ep:
            d = _hdist(pos, (ep["x"], ep["y"], ep["z"]))
            ruined = bool(ep.get("existing_frame_obsidian", True))
            if d <= PORTAL_NEAR and ruined:
                out["obsidian_frame"] = (["partial", "complete"] if pstate["built"] else ["partial"],
                                         f"{d:.1f} blocks from entry portal site (ruined frame)")
            elif d > PORTAL_FAR:
                out["obsidian_frame"] = (["none"] if not pstate["built"] else ["none", "partial", "complete"],
                                         f"{d:.1f} blocks from entry portal site")
    if "obsidian_frame" not in out and not pstate["built"]:
        out["obsidian_frame"] = (["none", "partial"], "no successful build_portal yet (never complete)", LOG)
    if out.get("obsidian_frame", ([],))[0] == ["none", "partial", "complete"]:
        del out["obsidian_frame"]  # no constraint
    if not pstate["lit"]:
        out["portal_lit"] = ([False], "no successful build/light/nether event yet", LOG)
    if water is not None:
        out["player_in_water"] = ([water[0]], water[1])
    return out


def water_label(run_t, server_samples, raw):
    """(in_water, basis) from the nearest server sample with feet/eye block, or None."""
    cands = []
    for t, s in server_samples:
        e = raw.get(s.line, {})
        blocks = [e.get(k) for k in ("feet_block", "eye_block") if e.get(k) is not None]
        if blocks:
            cands.append((t, (s, blocks)))
        elif s.in_water is not None:
            cands.append((t, (s, ["water"] if s.in_water else ["other"])))
    hit = _nearest(cands, run_t, WATER_WINDOW_S)
    if not hit:
        return None
    s, blocks = hit[2]
    wet = any("water" in str(b) for b in blocks)
    return wet, f"server line {s.line} feet/eye={blocks} (dt={round(hit[0], 3)}s)"


# ---------------------------------------------------------------- validate
def validate(perception, timeline, server_timeline=None, seed_features=None) -> dict:
    entries = _entries(perception)
    atl = _tl(timeline)
    stl = _tl(server_timeline)
    if seed_features is None:
        from .seedfeatures import load_seed_features
        seed_features = load_seed_features()
    origin = (atl.meta or {}).get("t0_epoch")
    ag = _rel_samples(atl, origin)
    sv = _rel_samples(stl, origin)
    raw = _raw_lines(stl) if stl is not None else {}

    per = {f: {"n": 0, "correct": 0, "accuracy": None} for f in LABELLED_FIELDS}
    logc = {}
    cases, log_cases, notes, skipped = [], [], [], 0
    for e in entries:
        obs = e.get("obs")
        run_t = e.get("run_t")
        if not isinstance(obs, dict) or run_t is None:
            skipped += 1
            continue
        pos, pbasis = bot_position(run_t, ag, sv)
        water = water_label(run_t, sv, raw) if sv else None
        labels = labels_for(run_t, pos, seed_features, portal_state(run_t, atl), water)
        for field, label in labels.items():
            allowed, basis = label[0], label[1]
            observed = obs.get(field)
            if observed is None:
                continue  # model abstained (e.g. player_in_water null)
            ok = observed in allowed
            case = {"video_t": e.get("video_t"), "run_t": run_t, "field": field,
                    "expected": allowed, "observed": observed, "correct": ok,
                    "basis": basis, "position_basis": pbasis,
                    "confidence": obs.get("confidence"), "frame_sha": e.get("frame_sha")}
            if is_log_derived(label):
                lc = logc.setdefault(field, {"n": 0, "consistent": 0, "source": "agent log claim"})
                lc["n"] += 1
                lc["consistent"] += int(ok)
                case["log_derived"] = True
                log_cases.append(case)
                continue
            per[field]["n"] += 1
            per[field]["correct"] += int(ok)
            cases.append(case)
    for f, r in per.items():
        if r["n"]:
            r["accuracy"] = round(r["correct"] / r["n"], 3)
        r["ci95"] = wilson(r["correct"], r["n"])
        r["sufficient"] = r["n"] >= MIN_N
    if skipped:
        notes.append(f"{skipped} perception entries without obs/run_t were skipped")
    if stl is None:
        notes.append("no server log: player_in_water has no ground truth; positions from agent log only")
    validated = [f for f in LABELLED_FIELDS if per[f]["sufficient"]]
    insufficient = [f for f in LABELLED_FIELDS if per[f]["n"] and not per[f]["sufficient"]]
    if insufficient:
        notes.append(f"insufficient ground truth (n < {MIN_N}) for: " + ", ".join(
            f"{f} (n={per[f]['n']})" for f in insufficient) + "; these accuracies must not gate findings")
    if logc:
        notes.append("log_consistency rows compare the model with the agent's own claim; they are not "
                     "ground truth and are not in per_field")
    return {"per_field": per, "cases": cases, "validated_fields": validated,
            "insufficient_fields": insufficient, "min_n": MIN_N,
            "log_consistency": logc, "log_cases": log_cases,
            "unvalidated_fields": [f for f in ALL_FIELDS if f not in validated and f not in insufficient],
            "rules": RULES, "notes": notes, "entries": len(entries)}


def format_table(res: dict) -> str:
    L = ["| field | n | correct | accuracy | 95% CI |", "|---|---:|---:|---:|---|"]
    for f, r in res["per_field"].items():
        acc = "n/a" if r["accuracy"] is None else f"{r['accuracy']:.0%}"
        if r["n"] and not r.get("sufficient", True):
            acc += f" (insufficient, n<{res.get('min_n', MIN_N)})"
        ci = r.get("ci95")
        L.append(f"| {f} | {r['n']} | {r['correct']} | {acc} | {'' if not ci else f'{ci[0]}-{ci[1]}'} |")
    L.append("")
    for f, r in (res.get("log_consistency") or {}).items():
        L.append(f"Consistent with agent-log claim (not ground truth): {f} {r['consistent']}/{r['n']}")
    L.append("Unvalidated (no ground truth): " + ", ".join(res["unvalidated_fields"]))
    for n in res.get("notes", []):
        L.append(f"Note: {n}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m splitcheck.perception_validate",
                                 description="Score perception.json against deterministic ground truth.")
    ap.add_argument("perception")
    ap.add_argument("--run-log", required=True)
    ap.add_argument("--server-log")
    ap.add_argument("--seed-dir")
    ap.add_argument("--json", help="also write the full result (incl. cases) here")
    a = ap.parse_args(argv)
    from .seedfeatures import load_seed_features
    res = validate(a.perception, a.run_log, a.server_log, load_seed_features(a.seed_dir))
    print(format_table(res))
    wrong = [c for c in res["cases"] if not c["correct"]]
    if wrong:
        print(f"\n{len(wrong)} disagreements, e.g.:")
        for c in wrong[:10]:
            print(f"  run_t={c['run_t']} {c['field']}: observed {c['observed']} expected {c['expected']} ({c['basis']})")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
