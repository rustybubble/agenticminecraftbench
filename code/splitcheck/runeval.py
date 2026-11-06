"""Deterministic run evaluator: how was this Minecraft 1.16.5 speedrun actually played?

Input: a game log (rmalde/minecraft-agent events.jsonl, or the human RCON poller log),
the seed features of seed 8398967436125155523, optional pro splits and an optional route
sheet (what a human was told). Output: a report with splits, findings and a score.

No LLM anywhere. Same input -> same output (findings sorted with a total order, floats
rounded, JSON written with sort_keys). Every number in the score is traceable to findings.

CLI: python -m splitcheck.runeval <log> [--pro ../splits/pro_splits.json]
         [--route-sheet x.json] [--seed-dir DIR] [--out report.json] [--md report.md]
"""
from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import sys
from pathlib import Path

from .logeval import SPLIT_ORDER, _canon, compare_splits

CATEGORIES = ("micro", "decision", "safety", "claim")
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
MILESTONES = [s for s in SPLIT_ORDER if s != "start"]  # nether_entry ... game_won


# ---------------------------------------------------------------- helpers
def _r(x, nd=3):
    return None if x is None else round(float(x), nd)


def _as_dict(f) -> dict:
    if dataclasses.is_dataclass(f) and not isinstance(f, type):
        d = dataclasses.asdict(f)
    elif isinstance(f, dict):
        d = dict(f)
    else:
        raise TypeError(f"finding is neither dataclass nor dict: {type(f).__name__}")
    d.setdefault("lines", [])
    d.setdefault("evidence", {})
    for k in ("t_start", "t_end", "cost_s"):
        d[k] = _r(d.get(k) or 0.0)
    if d["t_end"] < d["t_start"]:
        d["t_end"] = d["t_start"]
    d["cost_s"] = max(0.0, d["cost_s"])
    d["lines"] = sorted({int(n) for n in d["lines"] if n is not None})
    return json.loads(json.dumps(d, sort_keys=True, default=str))  # plain JSON-able, stable


def _finding_key(f: dict):
    return (-f["cost_s"], SEVERITY_RANK.get(f.get("severity"), 9), f["t_start"],
            str(f.get("code")), f["lines"][:1] or [0], str(f.get("message")))


def _load_json(p):
    if p is None:
        return None
    p = Path(p)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _registries():
    """REGISTRY from detectors (+ SEED_REGISTRY if any module provides it). Sorted by code."""
    regs = {}
    from . import detectors  # noqa: required by the contract
    regs.update(getattr(detectors, "REGISTRY", {}) or {})
    seed_reg = getattr(detectors, "SEED_REGISTRY", None)
    if seed_reg is None:
        try:
            from . import detectors_seed  # optional module
            seed_reg = getattr(detectors_seed, "SEED_REGISTRY", None)
        except ImportError:
            seed_reg = None
    for k, v in (seed_reg or {}).items():
        regs.setdefault(k, v)
    return dict(sorted(regs.items()))


# ---------------------------------------------------------------- score math
def attribute_waste(findings: list[dict], total_time_s: float | None = None) -> dict:
    """Attribute wasted seconds with no double counting.

    Each finding with cost_s > 0 claims the interval [t_start, t_start + cost_s] (its cost
    anchored where the waste began). When given total_time_s, an interval running past the end
    slides back to end at total_time_s (so late findings such as a final death still count). The union of
    all claimed intervals is the attributed waste. Where intervals overlap, each elementary
    segment is credited to exactly one finding: higher severity first, then larger cost_s,
    then earlier t_start, then code. So per-category totals sum exactly to the union, and each
    finding gets an `attributed_s` (its unique share).
    """
    iv = []
    for i, f in enumerate(findings):
        c = float(f.get("cost_s") or 0.0)
        if c <= 0:
            continue
        a = float(f.get("t_start") or 0.0)
        b = a + c
        if total_time_s is not None:  # keep the cost inside the run: slide back from the end
            b = max(0.0, min(b, total_time_s))
            a = max(0.0, min(a, b - c))
        if b > a:
            iv.append((a, b, i))
    prio = {i: (SEVERITY_RANK.get(findings[i].get("severity"), 9), -float(findings[i]["cost_s"]),
                float(findings[i].get("t_start") or 0.0), str(findings[i].get("code")), i)
            for _, _, i in iv}
    cuts = sorted({x for a, b, _ in iv for x in (a, b)})
    per_finding = {i: 0.0 for _, _, i in iv}
    for lo, hi in zip(cuts, cuts[1:]):
        cover = [i for a, b, i in iv if a <= lo and b >= hi]
        if cover:
            per_finding[min(cover, key=lambda i: prio[i])] += hi - lo
    by_cat = {c: 0.0 for c in CATEGORIES}
    for i, s in per_finding.items():
        cat = findings[i].get("category")
        by_cat[cat] = by_cat.get(cat, 0.0) + s
    # merged intervals (for display / audit)
    merged = []
    for a, b, _ in sorted(iv):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    raw_sum = sum(float(f.get("cost_s") or 0.0) for f in findings)
    return {"total_s": _r(sum(per_finding.values())),
            "by_category": {k: _r(v) for k, v in sorted(by_cat.items())},
            "per_finding": {i: _r(s) for i, s in per_finding.items()},
            "merged_intervals": [[_r(a), _r(b)] for a, b in merged],
            "raw_cost_sum_s": _r(raw_sum),
            "overlap_removed_s": _r(raw_sum - sum(per_finding.values()))}


# ---------------------------------------------------------------- timeline bits
def _total_time(tl) -> float:
    meta = getattr(tl, "meta", {}) or {}
    for k in ("total_time_s", "duration_s"):
        if isinstance(meta.get(k), (int, float)):
            return float(meta[k])
    ts = [s.t for s in tl.samples if s.t is not None] + \
         [e.get("t") for e in tl.events if isinstance(e.get("t"), (int, float))]
    return float(max(ts)) if ts else 0.0


def _splits(tl) -> list[dict]:
    out, seen = [], set()
    for e in sorted(tl.events, key=lambda e: (e.get("t") if e.get("t") is not None else 1e18,
                                              e.get("line") or 0)):
        name = _canon(e.get("type", ""))
        if name not in SPLIT_ORDER or name in seen:
            continue
        seen.add(name)
        out.append({"split": name, "time_s": _r(e.get("t")), "line": e.get("line"),
                    "event_type": e.get("type")})
    if "start" not in seen:
        out.insert(0, {"split": "start", "time_s": 0.0, "line": None, "event_type": None})
    return out


def _load_tl(log_path, route_sheet):
    from .timeline import load_timeline
    try:
        params = inspect.signature(load_timeline).parameters
    except (TypeError, ValueError):
        params = {}
    if "route_sheet" in params:
        tl = load_timeline(log_path, route_sheet=route_sheet)
    else:
        tl = load_timeline(log_path)
    if route_sheet and tl.source == "human_poller" and not tl.knowledge:
        rs = _load_json(route_sheet)
        if isinstance(rs, dict):
            tl.knowledge = rs.get("knowledge", rs)
    return tl


# ---------------------------------------------------------------- evaluate
CONTAINED_MICRO = ("oscillation", "overshoot_waypoint", "idle")


def _credit_contained(findings: list[dict]) -> None:
    """A path_efficiency leg's extra distance is caused by the dithering inside it. Subtract the
    cost of oscillation/overshoot/idle findings lying inside the leg (clipped to the overlap) from
    the leg's cost so the same seconds are not charged twice (their cost intervals are anchored at
    different times, so the interval merge alone cannot see the overlap)."""
    micro = [f for f in findings if f.get("code") in CONTAINED_MICRO and f["cost_s"] > 0]
    for f in findings:
        if f.get("code") != "path_efficiency" or f["cost_s"] <= 0:
            continue
        a, b = f["t_start"], f["t_end"]
        credit = sum(min(m["cost_s"], max(0.0, min(b, m["t_end"]) - max(a, m["t_start"])))
                     for m in micro)
        if credit > 0:
            f["evidence"]["cost_before_contained_credit_s"] = f["cost_s"]
            f["evidence"]["contained_micro_credit_s"] = _r(credit)
            f["cost_s"] = _r(max(0.0, f["cost_s"] - credit))


def _seed_match(tl, seed):
    """True/False when both the log and the seed features name a seed, else None (unknown)."""
    import re
    m = re.search(r"-?\d+", str((getattr(tl, "meta", {}) or {}).get("seed") or ""))
    want = (seed or {}).get("seed")
    if not m or want is None:
        return None
    return m.group(0) == str(want).strip()


def evaluate_run(log_path, seed_dir=None, pro_splits=None, route_sheet=None, registry=None) -> dict:
    tl = _load_tl(log_path, route_sheet)
    seed, seed_err = {}, None
    try:
        from .seedfeatures import load_seed_features
        seed = load_seed_features(seed_dir) or {}
    except Exception as ex:  # seed features are optional context
        seed_err = f"{type(ex).__name__}: {ex}"
    seed_match = _seed_match(tl, seed)
    if seed_match is False:  # features of seed 8398967436125155523 do not exist in another world
        seed_err = (f"seed mismatch: log seed {tl.meta.get('seed')!r} != seed features "
                    f"{seed.get('seed')!r}; seed features not applied")
        seed = {}
    pro = _load_json(pro_splits)
    if isinstance(pro, dict):
        pro = pro.get("splits", [])
    total = _r(_total_time(tl))
    splits = _splits(tl)
    ctx = {"seed": seed, "knowledge": tl.knowledge, "pro_splits": pro, "total_time_s": total,
           "splits": splits,
           "difficulty": (tl.meta or {}).get("difficulty") or (seed or {}).get("difficulty")}

    reg = registry if registry is not None else _registries()
    findings, ran, errors = [], [], {}
    for code in sorted(reg):
        try:
            got = reg[code](tl, ctx) or []
            findings.extend(_as_dict(f) for f in got)
            ran.append(code)
        except Exception as ex:  # one broken detector must not sink the report
            errors[code] = f"{type(ex).__name__}: {ex}"
    _credit_contained(findings)
    findings.sort(key=_finding_key)

    att = attribute_waste(findings, total)
    for i, f in enumerate(findings):
        f["attributed_s"] = att["per_finding"].get(i, 0.0)
    waste = att["total_s"]
    eff = _r((total - waste) / total, 4) if total else None

    reached = {s["split"] for s in splits}
    milestones = {m: (m in reached) for m in MILESTONES}
    comparison = compare_splits(splits, pro) if pro is not None else []
    ratios = [r["ratio"] for r in comparison if r.get("ratio") is not None]
    by_cat_count = {c: sum(1 for f in findings if f.get("category") == c) for c in CATEGORIES}

    score = {
        "total_time_s": total,
        "attributed_waste_s": waste,
        "waste_by_category_s": att["by_category"],
        "efficiency": eff,
        "efficiency_formula": "(total_time_s - attributed_waste_s) / total_time_s",
        "raw_cost_sum_s": att["raw_cost_sum_s"],
        "overlap_removed_s": att["overlap_removed_s"],
        "milestones_reached": sum(milestones.values()),
        "milestones_total": len(milestones),
        "milestone_completion": _r(sum(milestones.values()) / len(milestones), 4),
        "split_ratio_vs_pro_last": ratios[-1] if ratios else None,
        "split_ratio_vs_pro_mean": _r(sum(ratios) / len(ratios), 4) if ratios else None,
    }
    summary = {
        "log": str(log_path), "source": tl.source, "total_time_s": total,
        "findings": len(findings), "findings_by_category": by_cat_count,
        "findings_by_severity": {s: sum(1 for f in findings if f.get("severity") == s)
                                 for s in SEVERITY_RANK},
        "milestones": milestones, "efficiency": eff, "attributed_waste_s": waste,
    }
    coverage = {
        "source": tl.source, "samples": len(tl.samples), "events": len(tl.events),
        "knowledge_features": sorted(tl.knowledge.keys()) if isinstance(tl.knowledge, dict) else [],
        "seed_features": sorted(k for k in seed.keys()) if isinstance(seed, dict) else [],
        "seed_error": seed_err, "seed_match": seed_match, "seed_dir": str(seed_dir) if seed_dir else None,
        "pro_splits": str(pro_splits) if pro is not None else None,
        "route_sheet": str(route_sheet) if route_sheet else None,
        "detectors_run": ran, "detector_errors": dict(sorted(errors.items())),
        "merged_waste_intervals": att["merged_intervals"],
        "meta": json.loads(json.dumps(getattr(tl, "meta", {}) or {}, sort_keys=True, default=str)),
    }
    return {"summary": summary, "score": score, "splits": splits, "comparison": comparison,
            "findings": findings, "waste_by_category": att["by_category"], "coverage": coverage}


# ---------------------------------------------------------------- markdown
def _fmt(x, unit=""):
    return "-" if x is None else f"{x}{unit}"


def to_markdown(rep: dict) -> str:
    s, sc = rep["summary"], rep["score"]
    L = [f"# Run evaluation: `{s['log']}`", "",
         f"Source: **{s['source']}**. Deterministic (no LLM); every number below comes from the "
         "findings list.", "", "| Metric | Value |", "|---|---|",
         f"| Total time | {_fmt(sc['total_time_s'], ' s')} |",
         f"| Attributed waste (overlaps merged) | {_fmt(sc['attributed_waste_s'], ' s')} |"]
    for c in CATEGORIES:
        L.append(f"| &nbsp;&nbsp;{c} | {_fmt(sc['waste_by_category_s'].get(c), ' s')} |")
    L += [f"| Overlap removed | {_fmt(sc['overlap_removed_s'], ' s')} |",
          f"| Efficiency | {_fmt(sc['efficiency'])} |",
          f"| Milestones | {sc['milestones_reached']}/{sc['milestones_total']} |",
          f"| Mean split ratio vs pro | {_fmt(sc['split_ratio_vs_pro_mean'])} |", ""]
    L += ["## Splits", "", "| Split | Time (s) | Log line | Pro (s) | Delta (s) | Ratio |",
          "|---|---|---|---|---|---|"]
    comp = {r["split"]: r for r in rep["comparison"]}
    for sp in rep["splits"]:
        r = comp.get(sp["split"], {})
        L.append(f"| {sp['split']} | {_fmt(sp['time_s'])} | {_fmt(sp['line'])} | "
                 f"{_fmt(r.get('pro_time_s'))} | {_fmt(r.get('delta_s'))} | {_fmt(r.get('ratio'))} |")
    for m, ok in s["milestones"].items():
        if not ok:
            r = comp.get(m, {})
            L.append(f"| {m} | not reached | - | {_fmt(r.get('pro_time_s'))} | - | - |")
    L += ["", f"## Findings ({len(rep['findings'])}, sorted by cost)", ""]
    if not rep["findings"]:
        L.append("No findings.")
    for n, f in enumerate(rep["findings"], 1):
        lines = ", ".join(map(str, f["lines"][:12])) + (" ..." if len(f["lines"]) > 12 else "")
        L.append(f"{n}. **{f.get('code')}** ({f.get('category')}, {f.get('severity')}): "
                 f"cost {f['cost_s']} s, attributed {f['attributed_s']} s, "
                 f"t={f['t_start']}-{f['t_end']} s, lines [{lines}]")
        L.append(f"   {f.get('message')}")
        if f.get("evidence"):
            ev = json.dumps(f["evidence"], sort_keys=True)
            L.append(f"   evidence: `{ev[:400]}{'...' if len(ev) > 400 else ''}`")
    cov = rep["coverage"]
    L += ["", "## Coverage", "",
          f"- samples {cov['samples']}, events {cov['events']}",
          f"- detectors run: {', '.join(cov['detectors_run']) or 'none'}",
          f"- detector errors: {json.dumps(cov['detector_errors']) if cov['detector_errors'] else 'none'}",
          f"- disclosed knowledge: {', '.join(cov['knowledge_features']) or 'none'}",
          f"- seed features: {', '.join(cov['seed_features']) or 'none'}"
          + (f" (error: {cov['seed_error']})" if cov['seed_error'] else "")]
    return "\n".join(L) + "\n"


def to_json(rep: dict) -> str:
    return json.dumps(rep, indent=2, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m splitcheck.runeval")
    ap.add_argument("log")
    ap.add_argument("--pro", default=None, help="splits/pro_splits.json")
    ap.add_argument("--route-sheet", default=None, help="JSON of what a human runner was told")
    ap.add_argument("--seed-dir", default=None, help="seed feature dir (default: data/seed_<seed>)")
    ap.add_argument("--out", default=None, help="write JSON report")
    ap.add_argument("--md", default=None, help="write markdown report")
    a = ap.parse_args(argv)
    if not Path(a.log).exists():
        print(f"log not found: {a.log}", file=sys.stderr)
        return 2
    rep = evaluate_run(a.log, seed_dir=a.seed_dir, pro_splits=a.pro, route_sheet=a.route_sheet)
    for path, text in ((a.out, to_json(rep)), (a.md, to_markdown(rep))):
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(text, encoding="utf-8")
    sc = rep["score"]
    print(f"{rep['summary']['source']}: total {sc['total_time_s']} s, waste "
          f"{sc['attributed_waste_s']} s {json.dumps(sc['waste_by_category_s'])}, efficiency "
          f"{sc['efficiency']}, milestones {sc['milestones_reached']}/{sc['milestones_total']}, "
          f"findings {rep['summary']['findings']}")
    for f in rep["findings"][:10]:
        print(f"  [{f.get('code')}] {f['cost_s']} s lines {f['lines'][:6]}: {f.get('message')}")
    for p in (a.out, a.md):
        if p:
            print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
