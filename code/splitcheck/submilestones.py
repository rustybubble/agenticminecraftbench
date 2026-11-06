"""Sub-milestone scoring for partial runs: how far did the agent get, and how fast vs the pro?

    steps = derive_steps(tl)            # tl = splitcheck.timeline.Timeline
    rows  = compare_to_pro(steps)       # adds pro_t / delta
    md    = progress_lines(rows, fail)  # "## Progress before failure"

Steps: chest_1/2/3 looted, flint_and_steel crafted, portal_build_attempted, portal_built,
portal_lit, nether_entered. Agent times are seconds since the first timed log line (spawn).

Pro times come from baseline/pro_2m49_playbook.md (Segment 1, Q1.1 "Order (seen)"), as video
timestamps minus M_start = 0:22.0 (pause menu closes). They are written out below with the exact
playbook wording so a reader can check them; load_pro_steps() re-reads the playbook and keeps a
step only if its cited timestamp is still in the file, so an edited playbook drops the pro time
instead of silently using a stale one. Deterministic, stdlib only.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_MD = ROOT / "baseline" / "pro_2m49_playbook.md"
PRO_M_START_VIDEO_S = 22.0  # playbook "M_start | 0:22.0"

STEPS = ("chest_1", "chest_2", "chest_3", "flint_and_steel", "portal_build_attempted",
         "portal_built", "portal_lit", "nether_entered")

# pro chest identity -> (video lo, video hi, cited text in the playbook)
PRO_CHESTS = {
    "village": ("0:51", "0:55", "Village supply chest at about 0:51–0:55: iron pickaxe, 6 obsidian"),
    "flint": ("1:11", "1:13", "Ruined-portal chest with flint and 4 obsidian at about 1:11–1:13"),
    "obsidian": ("1:16", "1:16", "the chest with 11 obsidian and iron at about 1:16"),
}
PRO_STEPS = {
    "flint_and_steel": ("1:22", "1:23", "Flint and steel crafted in the 2×2 inventory grid at about 1:22–1:23"),
    "portal_build_attempted": ("1:17", "1:17", "Frame built at 1:17–1:25"),
    "portal_built": ("1:25", "1:25", "Frame built at 1:17–1:25"),
    "portal_lit": ("1:25", "1:26", "portal lit at about 1:25–1:26"),
    "nether_entered": ("1:28.7", "1:28.7", "M_portal_in | 1:28.7"),
}


def _vs(ts: str) -> float:
    m, s = ts.split(":")
    return int(m) * 60 + float(s)


def load_pro_steps(path=PLAYBOOK_MD) -> dict:
    """{key: {"lo", "hi", "source"}} relative to the pro's M_start; keys are PRO_STEPS keys and
    'chest:<identity>'. Empty if the playbook is missing."""
    p = Path(path)
    if not p.exists():
        return {}
    text = " ".join(p.read_text(encoding="utf-8").split())
    out = {}
    items = [(k, v) for k, v in PRO_STEPS.items()] + [(f"chest:{k}", v) for k, v in PRO_CHESTS.items()]
    for key, (lo, hi, cite) in items:
        if cite not in text:
            continue
        out[key] = {"lo": round(_vs(lo) - PRO_M_START_VIDEO_S, 3), "hi": round(_vs(hi) - PRO_M_START_VIDEO_S, 3),
                    "source": f"{p.name}: \"{cite}\" (video time minus M_start 0:22.0)"}
    return out


def _chest_identity(inv_got: dict) -> str:
    if inv_got.get("iron_pickaxe"):
        return "village"
    if inv_got.get("flint"):
        return "flint"
    return "obsidian"


def derive_steps(tl) -> dict:
    """{step: {"t", "t_lo"?, "line", "note", "reached"}} from a Timeline. Unreachable steps are absent."""
    live = (tl.meta or {}).get("live_agent") or {}
    steps: dict = {}
    by_line = {s.line: s for s in tl.samples}
    route_steps = {}
    # chests: live_agent loot_chest results, in log order
    if live:
        lines = sorted(by_line)
        loots = [r for r in live.get("skill_results") or [] if r["skill"] == "loot_chest" and r["ok"]]
        for i, r in enumerate(loots[:3], 1):
            prev = max((ln for ln in lines if ln < r["line"]), default=None)
            before = by_line[prev].inv if prev is not None else {}
            after = by_line[r["line"]].inv
            got = {k: after.get(k, 0) - before.get(k, 0) for k in after if after.get(k, 0) > before.get(k, 0)}
            steps[f"chest_{i}"] = {"t": r["t"], "line": r["line"], "reached": True,
                                   "identity": _chest_identity(got),
                                   "note": ", ".join(f"{k} {n}" for k, n in sorted(got.items())
                                                     if k in ("obsidian", "iron_pickaxe", "flint", "iron_ingot"))}
        for st in live.get("skill_starts") or []:
            route_steps.setdefault(st["skill"], st)
    # flint_and_steel: first sample holding one; lower bound is the flint pickup
    fs = next((s for s in tl.samples if s.inv.get("flint_and_steel")), None)
    if fs is not None:
        flint = next((s for s in tl.samples if s.inv.get("flint")), None)
        rec = {"t": fs.t, "line": fs.line, "reached": True,
               "note": f"first seen in inventory at line {fs.line} (no craft event in the log)"}
        if flint is not None and flint.t < fs.t:
            rec["t_lo"] = flint.t
            rec["note"] += f"; crafted after the flint pickup at t={flint.t} (line {flint.line})"
        steps["flint_and_steel"] = rec
    # portal build
    builds = [r for r in live.get("skill_results") or [] if r["skill"] in ("build_portal", "build_portal_frame")]
    if "build_portal" in route_steps or builds:
        st = route_steps.get("build_portal") or route_steps.get("build_portal_frame")
        if st:
            steps["portal_build_attempted"] = {"t": st["t"], "line": st["line"], "reached": True,
                                               "note": "build_portal skill started"}
        ok = next((r for r in builds if r["ok"]), None)
        if ok:
            steps["portal_built"] = {"t": ok["t"], "line": ok["line"], "reached": True, "note": "build_portal ok"}
        elif builds:
            b = builds[0]
            steps["portal_built"] = {"t": b["t"], "line": b["line"], "reached": False,
                                     "note": f"build_portal failed: {b.get('error')}"
                                             + (f", placed {b['placed']}" if b.get("placed") is not None else "")}
    for r in live.get("skill_results") or []:
        if r["skill"] in ("light_portal", "ignite_portal") and "portal_lit" not in steps:
            steps["portal_lit"] = {"t": r["t"], "line": r["line"], "reached": r["ok"],
                                   "note": f"{r['skill']} {'ok' if r['ok'] else 'failed: ' + str(r.get('error'))}"}
    for ev in tl.events:
        if ev["type"] in ("portal_lit", "nether_entered") and ev["type"] not in steps:
            steps[ev["type"]] = {"t": ev["t"], "line": ev["line"], "reached": True, "note": ev["type"]}
    if steps.get("nether_entered", {}).get("reached") and "portal_lit" not in steps:
        ne = steps["nether_entered"]
        steps["portal_lit"] = {"t": ne["t"], "line": ne["line"], "reached": True,
                               "note": "implied by nether entry (no lit event)"}
    return steps


def compare_to_pro(steps: dict, pro=None) -> list:
    """Rows for every step in STEPS order: step, agent_t, agent_t_lo, pro_lo, pro_hi, delta_lo/hi, note."""
    pro = load_pro_steps() if pro is None else pro
    rows = []
    for name in STEPS:
        s = steps.get(name)
        if name.startswith("chest_") and s:
            pkey = f"chest:{s.get('identity')}"
        else:
            pkey = name
        p = pro.get(pkey)
        row = {"step": name, "agent_t": s["t"] if s and s.get("reached") else None,
               "agent_t_lo": s.get("t_lo") if s and s.get("reached") else None,
               "line": s.get("line") if s else None, "reached": bool(s and s.get("reached")),
               "note": (s or {}).get("note", "not reached" if steps else "not derivable from this log"),
               "pro_lo": p["lo"] if p else None, "pro_hi": p["hi"] if p else None,
               "pro_source": p["source"] if p else None}
        if name.startswith("chest_") and s:
            row["note"] = f"{s.get('identity')} chest" + (f" ({s['note']})" if s.get("note") else "")
        if row["agent_t"] is not None and p:
            row["delta_lo"] = round(row["agent_t"] - p["hi"], 3)
            row["delta_hi"] = round(row["agent_t"] - p["lo"], 3)
        rows.append(row)
    return rows


def failure_point(steps: dict, rows=None):
    """First step that was attempted but not reached, else the first step after the last reached one."""
    for name in STEPS:
        s = steps.get(name)
        if s and not s.get("reached"):
            return {"step": name, "line": s.get("line"), "note": s.get("note")}
    reached = [n for n in STEPS if steps.get(n, {}).get("reached")]
    if not reached or reached[-1] == STEPS[-1]:
        return None
    nxt = STEPS[STEPS.index(reached[-1]) + 1]
    last = steps[reached[-1]]
    return {"step": nxt, "line": last.get("line"), "note": f"never attempted after {reached[-1]}"}


def _n(x):
    if x is None:
        return "-"
    return f"{round(x, 3)}"


def progress_lines(rows: list, fail) -> list:
    L = ["## Progress before failure" if fail else "## Progress by step", "",
         "Agent t = seconds since the first log line (spawn). Pro t = seconds since the pro's M_start in "
         "the 2:49 VOD (baseline/pro_2m49_playbook.md, Segment 1 order). Chests are matched to the pro's "
         "by contents (iron pickaxe = village chest, flint = ruined-portal chest, else the obsidian chest), "
         "not by order. Delta = agent - pro (range when the pro time is a range). The pro also collects "
         "beds on the way, so a negative delta is not the same work done faster. Report only: no verdict "
         "uses this table.", "",
         "| Step | Agent t s | Pro t s | Delta s | Line | Note |", "|---|---|---|---|---|---|"]
    for r in rows:
        at = _n(r["agent_t"])
        if r.get("agent_t_lo") is not None:
            at = f"{_n(r['agent_t_lo'])}-{at}"
        if r["agent_t"] is None:
            at = "not reached"
        pt = "no pro time for this step" if r["pro_lo"] is None else (
            _n(r["pro_lo"]) if r["pro_lo"] == r["pro_hi"] else f"{_n(r['pro_lo'])}-{_n(r['pro_hi'])}")
        if "delta_lo" in r:
            d = r["delta_lo"] if r["delta_lo"] == r["delta_hi"] else None
            dt = (f"+{_n(d)}" if d is not None and d >= 0 else _n(d)) if d is not None else \
                f"{_n(r['delta_lo'])} to {_n(r['delta_hi'])}"
        else:
            dt = "-"
        note = str(r.get("note") or "").replace("|", "\\|")
        L.append(f"| {r['step']} | {at} | {pt} | {dt} | {r['line'] if r['line'] is not None else '-'} | {note} |")
    L.append("")
    if fail:
        L.append(f"run failed at: {fail['step']} (line {fail['line']})" + (f": {fail['note']}" if fail.get("note") else ""))
    else:
        L.append("run reached every step in this table.")
    return L + [""]


def progress_section(tl, pro=None) -> tuple:
    """(markdown lines, data dict) for a Timeline."""
    steps = derive_steps(tl)
    rows = compare_to_pro(steps, pro)
    fail = failure_point(steps)
    return progress_lines(rows, fail), {"steps": rows, "failed_at": fail}
