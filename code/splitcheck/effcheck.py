"""Efficiency check (SCHEMA.md section 8, v4 headline): agent timeline vs pro segments.

Compares an agent run's milestone brackets with a pro baseline, segment by segment, and
attaches waste entries. Segments, bracket math, the verdict thresholds and every waste
rule come from baseline/rules.json at runtime; nothing is hardcoded here. Output matches
baseline/reference_check.py (B's reference implementation) for every fixtures/*.json.

No LLM, stdlib only, deterministic.

CLI: python -m splitcheck.effcheck <timeline.json> [--baseline path] [--rules path] [--out file]

Inputs accepted for `timeline`:
  * checker-facing shape: {"milestones": {"M_start": {"low", "high"} | number, ...}, "facts": {...}}
  * raw montage shape (agent_runs/published_montage/timeline.json): {"milestones": [{"id", "after_s",
    "by_s"}, ...]}; ids are mapped to M_* names (see MONTAGE_IDS) and after_s/by_s -> low/high.
  * optional timeline["waste_extra"] = [{segment, tag, seconds, evidence}, ...] (e.g. RunEval findings
    from v4export) appended to that segment's waste; never changes verdicts.

Differences from reference_check.py (none of them reachable by the fixtures):
  * facts.model_latency_s = null is treated as "not given" (rules.json: "when ... is given");
    the reference emits an idle_wait entry with seconds null.
  * a milestone that is missing from the timeline gives a segment with null numbers and verdict
    "NOT_REACHED" (excluded from the median) instead of a crash.
  * total is computed with the same bracket math against the first segment's start milestone and
    rounded to 3 decimals (identical when M_start is 0, as in every fixture).
  * the remaining rules.json waste rules (longer_path, failed_or_retried_action, unnecessary_risk)
    are applied when their facts are present; the reference ignores them.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES = REPO_ROOT / "baseline" / "rules.json"
DEFAULT_BASELINE = "baseline/pro_2m49_segments.json"
WHOLE_RUN = "whole_run"
NOT_REACHED = "NOT_REACHED"

# raw montage milestone ids -> SCHEMA section 8 names (matched on the part after "M<n>_")
MONTAGE_IDS = {
    "start": "M_start",
    "enter_nether": "M_portal_in",
    "exit_nether": "M_portal_out",
    "enter_end": "M_end_in",
    "complete_exit": "M_finish",
    "complete": "M_finish",
    "finish": "M_finish",
}


# ---------------------------------------------------------------- loading
def _resolve(path) -> Path:
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    return REPO_ROOT / p


def load_rules(path=None) -> dict:
    with open(_resolve(path) if path else DEFAULT_RULES, encoding="utf-8") as f:
        return json.load(f)


def load_baseline(path) -> dict:
    with open(_resolve(path), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- helpers
def _r(x):
    return None if x is None else round(x, 3)


def _bracket(m):
    """Milestone -> (low, high) floats, or None when absent."""
    if m is None:
        return None
    if isinstance(m, bool):
        return None
    if isinstance(m, (int, float)):
        return float(m), float(m)
    if isinstance(m, dict):
        lo = m.get("low", m.get("after_s"))
        hi = m.get("high", m.get("by_s"))
        if lo is None and hi is None:
            return None
        if lo is None:
            lo = hi
        if hi is None:
            hi = lo
        return float(lo), float(hi)
    return None


def normalize_milestones(milestones) -> dict:
    """Return {M_name: {"low", "high"}} from either the checker shape or the raw montage list."""
    if isinstance(milestones, dict):
        return milestones
    out = {}
    for m in milestones or []:
        mid = str(m.get("id", ""))
        if mid in MONTAGE_IDS.values():
            name = mid
        else:
            key = re.sub(r"^M\d+_", "", mid)
            name = MONTAGE_IDS.get(key)
        if name and name not in out:  # first occurrence wins
            b = _bracket(m)
            if b is not None:
                out[name] = {"low": b[0], "high": b[1]}
    return out


def _rule(rules, tag):
    for w in rules.get("waste_rules", []):
        if w.get("tag") == tag:
            return w
    return None


def _num(rule, keys, text_field, pattern):
    """A numeric parameter of a waste rule: explicit key if present, else parsed from its prose."""
    for k in keys:
        if isinstance(rule.get(k), (int, float)):
            return float(rule[k])
    m = re.search(pattern, str(rule.get(text_field, "")))
    return float(m.group(1)) if m else None


def _seg_facts(facts, seg):
    sf = facts.get(seg)
    if not isinstance(sf, dict):
        sf = (facts.get("segments") or {}).get(seg)
    return sf if isinstance(sf, dict) else {}


def _target(rule, default, by):
    s = (rule or {}).get("segment", default)
    return s if s in by else default


# ---------------------------------------------------------------- check
def check(timeline: dict, baseline: dict = None, rules: dict = None) -> dict:
    rules = rules if rules is not None else load_rules()
    if baseline is None:
        baseline = load_baseline(timeline.get("baseline", DEFAULT_BASELINE))
    v = rules["verdict"]
    pro_m = baseline["milestones_s"]
    ms = normalize_milestones(timeline.get("milestones", {}))

    rows = []
    for seg in rules["segments"]:
        f, t = _bracket(ms.get(seg["from"])), _bracket(ms.get(seg["to"]))
        pf, pt = pro_m.get(seg["from"]), pro_m.get(seg["to"])
        pro = None if pf is None or pt is None else pt - pf
        if f is None or t is None:
            lo = hi = None
        else:
            lo, hi = max(0.0, t[0] - f[1]), max(0.0, t[1] - f[0])
        ok = lo is not None and pro
        rows.append({"segment": seg["segment"], "agent_s_low": _r(lo), "agent_s_high": _r(hi), "pro_s": _r(pro),
                     "ratio_low": _r(lo / pro) if ok else None, "ratio_high": _r(hi / pro) if ok else None,
                     "waste": []})

    mids = [(r["ratio_low"] + r["ratio_high"]) / 2 for r in rows if r["ratio_low"] is not None]
    med = statistics.median(mids) if mids else None
    for r in rows:
        if r["ratio_low"] is None:
            r["verdict"] = NOT_REACHED
        elif (r["ratio_low"] > v["flag_k_times_median"] * max(med, 1.0)
              and r["agent_s_low"] - r["pro_s"] >= v["flag_min_excess_s"]):
            r["verdict"] = "FLAG"
        elif r["ratio_low"] > v["ok_max_ratio"]:
            r["verdict"] = "SLOW"
        else:
            r["verdict"] = "OK"

    by = {r["segment"]: r for r in rows}
    whole = []
    facts = timeline.get("facts") or {}
    extra = [w for w in (timeline.get("waste_extra") or []) if isinstance(w, dict)]
    extra_tags = {(w.get("segment"), w.get("tag")) for w in extra}

    # missed_shortcut: overworld arrival far from the End portal
    rule = _rule(rules, "missed_shortcut")
    a, e = facts.get("overworld_arrival_xyz"), facts.get("end_portal_xyz")
    if rule and a and e:
        limit = _num(rule, ("max_blocks", "threshold_blocks"), "when", r"more than\s+(\d+(?:\.\d+)?)\s+blocks")
        r = by.get(_target(rule, "exit_to_end_portal", by))
        if limit is not None and r is not None:
            d = math.dist([a["x"], a["y"], a["z"]], [e["x"], e["y"], e["z"]])
            if d > limit:
                secs = None if r["agent_s_low"] is None else round(max(0.0, r["agent_s_low"] - (r["pro_s"] or 0.0)), 3)
                r["waste"].append({"tag": "missed_shortcut", "seconds": secs,
                                   "evidence": "overworld arrival {:.1f} blocks from the End portal".format(d)})

    # extra_items: beds collected but not used on the dragon
    rule = _rule(rules, "extra_items")
    if rule and facts.get("beds_collected") is not None and facts.get("beds_used") is not None:
        per = rule.get("seconds_per_extra_bed")
        pro_left = (baseline.get("items") or {}).get("beds_leftover", 0)
        n = (facts["beds_collected"] - facts["beds_used"]) - pro_left
        r = by.get(_target(rule, "spawn_to_nether", by))
        if n > 0 and per is not None and r is not None:
            r["waste"].append({"tag": "extra_items", "seconds": round(n * per, 3),
                               "evidence": "{} beds collected, {} used".format(facts["beds_collected"], facts["beds_used"])})

    # longer_path / failed_or_retried_action: per-segment facts
    rule = _rule(rules, "longer_path")
    if rule:
        ratio = _num(rule, ("max_ratio",), "when", r">\s*(\d+(?:\.\d+)?)")
        per_block = _num(rule, ("seconds_per_block",), "seconds", r"\*\s*(\d+(?:\.\d+)?)")
        for r in rows:
            sf = _seg_facts(facts, r["segment"])
            p, s = sf.get("path_blocks"), sf.get("straight_blocks")
            if (ratio is None or per_block is None or not p or not s
                    or (r["segment"], "longer_path") in extra_tags):
                continue
            if p / s > ratio:
                r["waste"].append({"tag": "longer_path", "seconds": round((p - s) * per_block, 3),
                                   "evidence": "path {:.1f} blocks vs straight {:.1f} blocks ({:.2f}x)".format(p, s, p / s)})
    rule = _rule(rules, "failed_or_retried_action")
    if rule:
        for r in rows:
            sf = _seg_facts(facts, r["segment"])
            n = sf.get("failed_actions")
            if n and n > 0 and (r["segment"], "failed_or_retried_action") not in extra_tags:
                secs = sf.get("failed_actions_s")
                r["waste"].append({"tag": "failed_or_retried_action", "seconds": _r(secs),
                                   "evidence": "{} failed actions{}".format(n, "" if secs is not None else " (time unknown)")})

    # whole-run entries: model latency, deaths
    rule = _rule(rules, "idle_wait")
    if rule and facts.get("model_latency_s") is not None:
        whole.append({"tag": "idle_wait", "seconds": facts["model_latency_s"], "evidence": "model latency total"})
    rule = _rule(rules, "unnecessary_risk")
    if rule and facts.get("deaths") and not any(t == "unnecessary_risk" for _, t in extra_tags):
        whole.append({"tag": "unnecessary_risk", "seconds": _r(facts.get("death_recovery_s")),
                      "evidence": "{} death(s)".format(facts["deaths"])})

    # waste_extra: appended in input order, verdicts untouched
    for w in extra:
        entry = {"tag": w.get("tag"), "seconds": w.get("seconds"), "evidence": w.get("evidence")}
        target = by.get(w.get("segment"))
        (target["waste"] if target is not None else whole).append(entry)

    if whole:
        rows.append({"segment": WHOLE_RUN, "waste": whole})

    # total
    first, last = rules["segments"][0]["from"], rules["segments"][-1]["to"]
    f, t = _bracket(ms.get(first)), _bracket(ms.get(last))
    tot_pro = None if pro_m.get(first) is None or pro_m.get(last) is None else pro_m[last] - pro_m[first]
    if f is None or t is None:
        tl = th = None
    else:
        tl, th = max(0.0, t[0] - f[1]), max(0.0, t[1] - f[0])
    tok = tl is not None and tot_pro
    total = {"agent_s_low": _r(tl), "agent_s_high": _r(th), "pro_s": _r(tot_pro),
             "ratio_low": _r(tl / tot_pro) if tok else None, "ratio_high": _r(th / tot_pro) if tok else None}
    out = {"run_median_ratio": _r(med), "total": total, "segments": rows}
    flags = _finish_flags(timeline, ms, last)
    if flags:  # only for runs without a real finish; finished runs keep the exact SCHEMA shape
        out["flags"] = flags
    return out


def _finish_flags(timeline, ms, last):
    """Hard flags for a run whose last milestone is missing or only a proxy (e.g. dragon_killed)."""
    flags = []
    m = ms.get(last)
    if isinstance(m, dict) and m.get("proxy"):
        flags.append("{}: proxy finish ({}); end segment and total use it".format(last, m.get("note") or m.get("evidence")))
    elif (_bracket(m) is None and timeline.get("finish_flag")) or (isinstance(m, dict) and m.get("reached") is False):
        note = m.get("note") if isinstance(m, dict) else None
        flags.append("{}: not reached ({}); total not scored".format(last, note or "unfinished run"))
    return flags


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m splitcheck.effcheck", description=__doc__.splitlines()[0])
    ap.add_argument("timeline")
    ap.add_argument("--baseline", default=None, help="pro segments JSON (default: timeline['baseline'] or the 2:49 run)")
    ap.add_argument("--rules", default=None, help="rules JSON (default: baseline/rules.json)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    with open(a.timeline, encoding="utf-8") as f:
        tl = json.load(f)
    baseline = load_baseline(a.baseline or tl.get("baseline") or DEFAULT_BASELINE)
    text = json.dumps(check(tl, baseline, load_rules(a.rules)), indent=1) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
