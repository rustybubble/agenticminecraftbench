import json
from pathlib import Path

import pytest

from splitcheck import logeval

FX = Path(__file__).parent / "fixtures" / "events"


@pytest.fixture(scope="module")
def clean():
    return logeval.evaluate(FX / "clean_run.jsonl")


@pytest.fixture(scope="module")
def waste():
    return logeval.evaluate(FX / "wasteful_run.jsonl")


@pytest.fixture(scope="module")
def claim():
    return logeval.evaluate(FX / "false_claim_run.jsonl")


def lines(findings, key="line"):
    return [f[key] for f in findings]


def test_clean_run_splits(clean):
    s = {x["split"]: x for x in clean["splits"]}
    assert s["start"]["time_s"] == 0.0 and s["start"]["line"] == 1
    assert s["nether_entry"]["line"] == 17 and s["nether_entry"]["time_s"] == 34.7
    assert s["nether_exit"]["line"] == 28
    assert s["end_entry"]["line"] == 35 and "the_end" in s["end_entry"]["reason"]
    assert s["dragon_kill"]["line"] == 38
    assert s["game_won"]["line"] == 39 and s["game_won"]["time_s"] == 296.7
    assert "death" not in s
    assert clean["coverage"]["missing_types"] == []


def test_clean_run_is_silent(clean):
    w = clean["waste"]
    for k in ("failed_actions", "no_progress", "waits", "loops", "place_recover", "unused_items",
              "overshoot", "deaths"):
        assert w[k] == [], k
    assert clean["claims"] == []


def test_failed_actions(waste):
    f = waste["waste"]["failed_actions"]
    assert lines(f) == [20, 24, 28]
    assert f[0]["time_s"] == 25.0 and "line 20" in f[0]["reason"]
    assert waste["waste"]["totals"]["failed_s"] == 31.0


def test_waits_and_no_progress(waste):
    assert lines(waste["waste"]["waits"]) == [22]
    assert lines(waste["waste"]["no_progress"]) == [22, 26]


def test_loop(waste):
    (lp,) = waste["waste"]["loops"]
    assert lp["key"] == "collect_drop" and lp["count"] == 3 and lp["end_line"] == 28


def test_place_then_recover(waste):
    (pr,) = waste["waste"]["place_recover"]
    assert pr["item"] == "crafting_table" and pr["line"] == 14 and pr["recover_line"] == 18
    assert pr["crafts_between"] == 1


def test_unused_items(waste):
    u = {x["item"]: x for x in waste["waste"]["unused_items"]}
    assert set(u) == {"cooked_beef", "leather", "iron_chestplate"}
    assert u["cooked_beef"]["line"] == 6 and "Peaceful" in u["cooked_beef"]["reason"]
    assert u["iron_chestplate"]["line"] == 8


def test_overshoot(waste):
    (o,) = waste["waste"]["overshoot"]
    assert o["reached_line"] == 31 and o["line"] == 32 and o["min_distance"] <= 3


def test_death(waste):
    (d,) = waste["waste"]["deaths"]
    assert d["line"] == 42 and d["dimension"] == "the_nether" and d["position"]["x"] == 41.2
    assert any(s["split"] == "death" and s["line"] == 42 for s in waste["splits"])


def test_latency_separate(waste):
    lat = waste["waste"]["latency"]
    assert lat["decisions"] == 18 and lat["jev_api_s"] == 7.2 and lat["planner_api_s"] == 2.0


def test_false_claims(claim):
    c = claim["claims"]
    assert all(x["label"] == "claim_contradicted" for x in c)
    eyes = [x for x in c if x.get("item") == "ender_eye"]
    assert len(eyes) == 1 and eyes[0]["line"] == 5 and eyes[0]["evidence_line"] == 4  # state before the plan
    assert eyes[0]["claimed"] == 12 and eyes[0]["actual"] == 9
    assert any("nether" in x["claim"] for x in c)
    assert len(c) == 2


def test_compare_splits(tmp_path):
    pro = [{"split": "nether_entry", "time_s": 17.35, "verified": True, "run": "x"},
           {"split": "dragon_kill", "time_s": 174.5, "verified": True}]
    p = tmp_path / "pro.json"
    p.write_text(json.dumps(pro))
    rep = logeval.evaluate(FX / "clean_run.jsonl", p)
    c = {r["split"]: r for r in rep["comparison"]}
    assert c["nether_entry"]["delta_s"] == 17.35 and c["nether_entry"]["ratio"] == 2.0
    assert c["dragon_kill"]["delta_s"] == round(291.7 - 174.5, 3)
    assert c["game_won"]["pro_time_s"] is None


def test_deterministic_and_cli(tmp_path, capsys):
    a = logeval.evaluate(FX / "wasteful_run.jsonl")
    b = logeval.evaluate(FX / "wasteful_run.jsonl")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    out = tmp_path / "r.json"
    assert logeval.main([str(FX / "wasteful_run.jsonl"), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["waste"]["totals"]["deaths"] == 1
    assert "place_recover" in capsys.readouterr().out


def test_bad_lines_do_not_crash(tmp_path):
    p = tmp_path / "e.jsonl"
    p.write_text('{"time":"2026-11-06T12:00:00Z","type":"start"}\nnot json\n\n'
                 '{"time":"2026-11-06T12:00:05Z","type":"nether_entered","position":{"x":1,"y":2,"z":3}}\n')
    rep = logeval.evaluate(p)
    assert rep["coverage"]["parse_errors"] == [2]
    assert [s["line"] for s in rep["splits"]] == [1, 4]
