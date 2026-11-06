"""Fixture runs: each synthetic log must produce its documented finding codes and none of its
forbidden ones (tests/fixtures/runs/EXPECTED.md is the single source of truth)."""
import json
import re
from pathlib import Path

import pytest

RUNS = Path(__file__).parent / "fixtures" / "runs"

try:
    from splitcheck.runeval import evaluate_run
except ImportError as ex:  # runeval is built in parallel; skip until it lands
    evaluate_run = None
    _IMPORT_ERR = ex


def _parse_expected():
    spec, cur = {}, None
    for raw in (RUNS / "EXPECTED.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(\S+\.jsonl)\s*$", raw)
        if m:
            cur = spec.setdefault(m.group(1), {"must": [], "must_not": [], "route_sheet": None,
                                               "min_efficiency": None})
            continue
        m = re.match(r"^-\s+(must|must_not|route_sheet|min_efficiency):\s*(.*)$", raw)
        if cur is None or not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key in ("must", "must_not"):
            cur[key] = [tuple(a.strip() for a in v.split("|")) for v in val.split(",") if v.strip()]
        elif key == "route_sheet":
            cur[key] = val or None
        else:
            cur[key] = float(val) if val else None
    return spec


SPEC = _parse_expected()
FIXTURES = sorted(SPEC)


def test_every_fixture_documented_and_present():
    on_disk = {p.name for p in RUNS.glob("*.jsonl")}
    assert set(SPEC) == on_disk, f"EXPECTED.md vs disk mismatch: {set(SPEC) ^ on_disk}"
    required = {"agent_clean.jsonl", "agent_peaceful_food_tools.jsonl", "agent_crafting_table_recover.jsonl",
                "agent_mining_in_water_lost_drop.jsonl", "agent_completed_waypoint_overshoot.jsonl",
                "agent_long_approach_timeouts.jsonl", "agent_breath_cloud_death.jsonl",
                "agent_mined_obsidian_ignoring_chests.jsonl", "human_poller_clean.jsonl",
                "human_poller_water_mining_detour.jsonl"}
    assert required <= on_disk


def test_fixtures_are_valid_jsonl_and_formats():
    for name in FIXTURES:
        lines = (RUNS / name).read_text(encoding="utf-8").splitlines()
        evs = [json.loads(l) for l in lines]
        assert evs[0]["type"] == "start" and all("time" in e and "type" in e for e in evs), name
        if name.startswith("agent_"):
            decs = [e for e in evs if e["type"] == "decision"]
            assert decs and all(isinstance(d["request"]["state"], str) for d in decs), name
            st = json.loads(decs[0]["request"]["state"])
            assert {"position", "dimension", "inventory", "knownSeed", "stage", "difficulty"} <= set(st), name
            assert st["knownSeed"]["seed"] == "8398967436125155523"
        else:
            ps = [e for e in evs if e["type"] == "position_sample"]
            assert ps and all({"food", "feet_block", "head_block", "selected_item"} <= set(p) for p in ps), name
            assert evs[0].get("source") == "rcon_poller"


def _codes(rep):
    return {f["code"] for f in rep["findings"]}


def _run(name):
    if evaluate_run is None:
        pytest.skip(f"splitcheck.runeval not importable yet: {_IMPORT_ERR}")
    sheet = SPEC[name]["route_sheet"]
    return evaluate_run(str(RUNS / name), route_sheet=str(RUNS / sheet) if sheet else None)


@pytest.mark.parametrize("name", FIXTURES)
def test_expected_codes_present(name):
    rep = _run(name)
    got = _codes(rep)
    missing = [" | ".join(g) for g in SPEC[name]["must"] if not set(g) & got]
    assert not missing, f"{name}: missing expected codes {missing}; got {sorted(got)}"


@pytest.mark.parametrize("name", FIXTURES)
def test_forbidden_codes_absent(name):
    rep = _run(name)
    bad = sorted({c for g in SPEC[name]["must_not"] for c in g} & _codes(rep))
    detail = [f"{f['code']} lines {f['lines'][:4]}: {f['message'][:160]}" for f in rep["findings"]
              if f["code"] in bad]
    assert not bad, f"{name}: false positives {bad}:\n  " + "\n  ".join(detail)


@pytest.mark.parametrize("name", [n for n in FIXTURES if SPEC[n]["min_efficiency"] is not None])
def test_clean_efficiency(name):
    rep = _run(name)
    eff = rep["score"]["efficiency"]
    assert eff >= SPEC[name]["min_efficiency"], f"{name}: efficiency {eff} < {SPEC[name]['min_efficiency']}"


@pytest.mark.parametrize("name", FIXTURES)
def test_findings_cite_evidence_and_are_deterministic(name):
    rep = _run(name)
    n_lines = len((RUNS / name).read_text(encoding="utf-8").splitlines())
    for f in rep["findings"]:
        assert f["lines"] and all(1 <= l <= n_lines for l in f["lines"]), f
        assert f["cost_s"] >= 0 and f["t_end"] >= f["t_start"], f
        assert f["category"] in ("micro", "decision", "safety", "claim"), f
        assert f["severity"] in ("high", "medium", "low"), f
    again = _run(name)
    assert json.dumps(rep, sort_keys=True, default=str) == json.dumps(again, sort_keys=True, default=str)
