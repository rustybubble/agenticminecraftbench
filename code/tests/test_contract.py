"""Contract tests: the shared code contract between herobrine builders.

Checks that every module/function/dataclass field named in the SHARED CODE
CONTRACT exists with the agreed signature, and that every action in
SCHEMA.md section 4 is handled by the simulator's dispatch.

Run: cd code && python -m pytest -q
"""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
import re
from pathlib import Path

import pytest

CODE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CODE_DIR.parent
SCHEMA_PATH = REPO_ROOT / "SCHEMA.md"
TEMPLATE_PATH = CODE_DIR / "splitcheck" / "time_costs_template.json"


def _mod(name):
    return importlib.import_module(f"splitcheck.{name}")


def _params(fn):
    return list(inspect.signature(fn).parameters.values())


def _assert_sig(fn, expected):
    """expected: list of (name, required: bool). Extra trailing optional params are allowed."""
    params = _params(fn)
    names = [p.name for p in params]
    assert len(params) >= len(expected), f"{fn.__qualname__}{inspect.signature(fn)}: expected params {expected}"
    for (want_name, want_required), p in zip(expected, params):
        assert p.name == want_name, f"{fn.__qualname__}: param {p.name!r} should be {want_name!r} (got {names})"
        has_default = p.default is not inspect.Parameter.empty
        if want_required:
            assert not has_default, f"{fn.__qualname__}: {p.name!r} should be required"
        else:
            assert has_default, f"{fn.__qualname__}: {p.name!r} should have a default"
    for p in params[len(expected):]:
        assert p.default is not inspect.Parameter.empty or p.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ), f"{fn.__qualname__}: unexpected extra required param {p.name!r}"


# ---------------------------------------------------------------- package

def test_package_importable():
    assert (CODE_DIR / "splitcheck" / "__init__.py").exists()
    for m in ("sim", "answers", "check", "logeval"):
        _mod(m)


# ---------------------------------------------------------------- sim.py

def test_sim_load_costs():
    sim = _mod("sim")
    _assert_sig(sim.load_costs, [("path", False)])
    assert _params(sim.load_costs)[0].default is None


def test_sim_simulate_signature():
    sim = _mod("sim")
    _assert_sig(sim.simulate, [("task", True), ("plan", True), ("costs", False)])
    assert _params(sim.simulate)[2].default is None


def test_sim_result_dataclass():
    sim = _mod("sim")
    assert dataclasses.is_dataclass(sim.SimResult)
    fields = {f.name for f in dataclasses.fields(sim.SimResult)}
    for name in ("legal", "reason", "failed_step", "time_s", "steps", "final_state", "techniques_used"):
        assert name in fields, f"SimResult missing field {name!r} (has {sorted(fields)})"


def test_sim_default_costs_are_estimates():
    sim = _mod("sim")
    assert isinstance(sim.DEFAULT_COSTS, dict) and sim.DEFAULT_COSTS
    # DEFAULT_COSTS may be flat {key: entry} or SCHEMA-shaped {"actions": {...}}
    entries = sim.DEFAULT_COSTS.get("actions", sim.DEFAULT_COSTS)
    for key, entry in entries.items():
        assert isinstance(entry, dict), key
        assert entry.get("source") == "estimate", f"default cost {key!r} source should be 'estimate'"
        assert entry.get("verified") is False, f"default cost {key!r} must be verified=false"


def test_sim_load_costs_without_file_returns_defaults(tmp_path):
    sim = _mod("sim")
    costs = sim.load_costs(tmp_path / "does_not_exist.json")
    assert isinstance(costs, dict) and costs


def schema_actions():
    """Parse the action names from the SCHEMA.md section 4 table."""
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    m = re.search(r"^## 4\..*?$(.*?)^## 5\.", text, re.S | re.M)
    assert m, "SCHEMA.md section 4 not found"
    actions = re.findall(r"^\|\s*`([a-z_]+)`\s*\|", m.group(1), re.M)
    assert actions, "no actions parsed from SCHEMA.md section 4"
    return actions


def test_schema_action_table_parsed():
    acts = schema_actions()
    for a in ("mine", "craft", "travel", "build_portal", "enter_portal", "reset"):
        assert a in acts


@pytest.mark.parametrize("action", schema_actions())
def test_sim_dispatch_handles_action(action):
    sim = _mod("sim")
    src = inspect.getsource(sim)
    quoted = re.search(r"""(['"])%s\1""" % re.escape(action), src)
    assert quoted, f"SCHEMA §4 action {action!r} does not appear as a string literal in sim.py dispatch"


def test_sim_unknown_action_is_illegal_not_crash():
    sim = _mod("sim")
    task = {"id": "contract", "state": {"dimension": "overworld", "position": {"x": 0, "y": 64, "z": 0},
                                        "inventory": {}, "known_locations": {}, "world": {}, "elapsed_s": 0}}
    res = sim.simulate(task, {"actions": [{"action": "teleport_to_dragon"}]})
    assert res.legal is False
    assert res.failed_step == 0
    assert res.reason


def test_sim_deterministic():
    sim = _mod("sim")
    task = {"id": "contract", "state": {"dimension": "overworld", "position": {"x": 0, "y": 64, "z": 0},
                                        "inventory": {}, "known_locations": {"p": {"x": 100, "y": 64, "z": 0, "dimension": "overworld"}},
                                        "world": {}, "elapsed_s": 0}}
    plan = {"actions": [{"action": "travel", "to": "p"}]}
    a, b = sim.simulate(task, plan), sim.simulate(task, plan)
    assert a.legal and a.time_s == b.time_s and a.time_s > 0


def test_time_costs_template_covers_sim_defaults():
    sim = _mod("sim")
    tmpl = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert "actions" in tmpl
    entries = sim.DEFAULT_COSTS.get("actions", sim.DEFAULT_COSTS)
    missing = sorted(set(entries) - set(tmpl["actions"]))
    assert not missing, f"time_costs_template.json lacks sim cost keys: {missing}"


def test_time_costs_template_shape():
    tmpl = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    for key, e in tmpl["actions"].items():
        assert isinstance(e["seconds"], (int, float)), key
        assert e["per"] in ("action", "block", "item", "100_blocks"), key
        assert e["source"] == "estimate" and e["verified"] is False, key


# ---------------------------------------------------------------- answers.py

def test_answers_functions():
    ans = _mod("answers")
    _assert_sig(ans.parse_json_answer, [("text", True)])
    _assert_sig(ans.check_answer, [("task", True), ("ref", True), ("answer", True), ("costs", False)])
    _assert_sig(ans.overworld_to_nether, [("x", True), ("z", True)])
    _assert_sig(ans.nether_to_overworld, [("x", True), ("z", True)])
    _assert_sig(ans.triangulate, [("x1", True), ("z1", True), ("yaw1", True),
                                  ("x2", True), ("z2", True), ("yaw2", True)])
    _assert_sig(ans.ring_of, [("x", True), ("z", True)])
    assert callable(ans.horizontal_distance)


def test_answers_behaviour_smoke():
    ans = _mod("answers")
    assert ans.parse_json_answer('Sure!\n```json\n{"x": 1, "z": 2}\n```') == {"x": 1, "z": 2}
    assert ans.parse_json_answer("no json here") is None
    assert ans.overworld_to_nether(800, -160) == pytest.approx((100, -20))
    assert ans.nether_to_overworld(100, -20) == pytest.approx((800, -160))
    assert ans.ring_of(0, 2000) == 1
    assert ans.ring_of(0, 100) is None
    # Two throws: from (0,0) facing yaw -45 (towards +X,+Z) and from (100,0) facing yaw 45 (towards -X,+Z)
    pt = ans.triangulate(0, 0, -45, 100, 0, 45)
    assert pt is not None and pt[0] == pytest.approx(50, abs=1e-6) and pt[1] == pytest.approx(50, abs=1e-6)
    assert ans.triangulate(0, 0, 0, 10, 0, 0) is None  # parallel throws
    r = ans.check_answer({"answer_type": "number"}, {"answer": {"n": 1}, "tolerance": {"abs": 0}}, None)
    assert r["verdict"] == "WRONG" and r["reason"] and "details" in r


# ---------------------------------------------------------------- check.py

def test_check_functions():
    chk = _mod("check")
    _assert_sig(chk.check_task, [("task", True), ("ref", True), ("raw_response", True), ("costs", False)])
    _assert_sig(chk.self_test, [("root", True)])
    assert callable(chk.main)


def test_check_empty_root_does_not_crash(tmp_path):
    chk = _mod("check")
    out = chk.self_test(tmp_path)
    assert isinstance(out, list)


# ---------------------------------------------------------------- logeval.py

def test_logeval_functions():
    le = _mod("logeval")
    _assert_sig(le.load_events, [("path", True)])
    _assert_sig(le.extract_splits, [("events", True)])
    _assert_sig(le.detect_waste, [("events", True)])
    _assert_sig(le.compare_splits, [("splits", True), ("pro_splits", True)])
    _assert_sig(le.evaluate, [("events_path", True), ("pro_splits_path", False), ("survey_dir", False)])
    assert callable(getattr(le, "main", None)), "logeval needs a main() for the CLI"
