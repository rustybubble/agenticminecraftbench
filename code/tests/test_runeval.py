import json
from pathlib import Path

import pytest

from splitcheck import runeval
from splitcheck.runeval import attribute_waste, evaluate_run

FIX = Path(__file__).parent / "fixtures"


def _log():
    runs = sorted((FIX / "runs").glob("*.jsonl"))
    return runs[0] if runs else FIX / "events" / "wasteful_run.jsonl"


def F(code, cat, sev, a, cost, b=None):
    return {"code": code, "category": cat, "severity": sev, "t_start": a,
            "t_end": a + cost if b is None else b, "cost_s": cost, "lines": [1],
            "message": code, "evidence": {}}


def test_overlap_merged_no_double_count():
    fs = [F("a", "micro", "low", 10, 20),        # [10,30]
          F("b", "decision", "high", 20, 20),    # [20,40] overlaps a by 10
          F("c", "safety", "medium", 100, 5)]    # [100,105] disjoint
    att = attribute_waste(fs)
    assert att["total_s"] == 35.0                # union 10..40 + 100..105, not 45
    assert att["raw_cost_sum_s"] == 45.0 and att["overlap_removed_s"] == 10.0
    # overlap 20..30 goes to the high-severity finding
    assert att["by_category"] == {"claim": 0.0, "decision": 20.0, "micro": 10.0, "safety": 5.0}
    assert sum(att["by_category"].values()) == att["total_s"]
    assert att["merged_intervals"] == [[10.0, 40.0], [100.0, 105.0]]


def test_clipped_to_run_and_zero_cost_ignored():
    att = attribute_waste([F("a", "micro", "low", 90, 50), F("z", "claim", "high", 5, 0)], 100.0)
    assert att["total_s"] == 50.0 and att["merged_intervals"] == [[50.0, 100.0]]
    assert att["by_category"]["claim"] == 0.0
    assert attribute_waste([F("a", "micro", "low", 0, 500)], 100.0)["total_s"] == 100.0


def test_contained_interval_identical_costs():
    att = attribute_waste([F("a", "micro", "medium", 0, 10), F("b", "micro", "medium", 0, 10)])
    assert att["total_s"] == 10.0


def _fake_registry():
    def d1(tl, ctx):
        return [F("loop", "micro", "medium", 5.0, 30.0)]

    def d2(tl, ctx):
        return [F("bad_route", "decision", "high", 20.0, 40.0)]

    def boom(tl, ctx):
        raise ValueError("broken")
    return {"loop": d1, "bad_route": d2, "boom": boom}


def test_score_traceable_to_findings():
    rep = evaluate_run(_log(), registry=_fake_registry())
    sc = rep["score"]
    assert sc["attributed_waste_s"] == round(sum(f["attributed_s"] for f in rep["findings"]), 3)
    assert sc["attributed_waste_s"] == round(sum(sc["waste_by_category_s"].values()), 3)
    assert sc["efficiency"] == round((sc["total_time_s"] - sc["attributed_waste_s"]) / sc["total_time_s"], 4)
    assert rep["findings"][0]["code"] == "bad_route"           # sorted by cost
    assert rep["coverage"]["detector_errors"] == {"boom": "ValueError: broken"}
    assert sc["milestones_total"] == 5


def test_deterministic_output():
    a = runeval.to_json(evaluate_run(_log()))
    b = runeval.to_json(evaluate_run(_log()))
    assert a == b
    assert runeval.to_markdown(json.loads(a)) == runeval.to_markdown(json.loads(b))


def test_cli_writes_files(tmp_path, capsys):
    pro = tmp_path / "pro.json"
    pro.write_text(json.dumps([{"split": "nether_entry", "time_s": 60, "verified": True}]))
    out, md = tmp_path / "r.json", tmp_path / "r.md"
    assert runeval.main([str(_log()), "--pro", str(pro), "--out", str(out), "--md", str(md)]) == 0
    rep = json.loads(out.read_text())
    assert {"summary", "score", "splits", "comparison", "findings", "waste_by_category",
            "coverage"} <= set(rep)
    assert any(r["split"] == "nether_entry" and r["ratio"] for r in rep["comparison"])
    text = md.read_text()
    assert "Attributed waste" in text and "## Findings" in text


def test_cli_missing_log(tmp_path):
    assert runeval.main([str(tmp_path / "nope.jsonl")]) == 2
