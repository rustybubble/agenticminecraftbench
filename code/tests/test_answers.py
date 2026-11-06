import importlib.util
import math

import pytest

from splitcheck import answers as A


def T(atype):
    return {"id": "t", "answer_type": atype, "state": {}}


# --- parse_json_answer ---------------------------------------------------

def test_parse_plain():
    assert A.parse_json_answer('{"x": 1}') == {"x": 1}


def test_parse_fenced_with_prose():
    txt = 'Sure! Here is my answer:\n```json\n{"choice": "reset", "reasoning": "bad"}\n```\nGood luck.'
    assert A.parse_json_answer(txt) == {"choice": "reset", "reasoning": "bad"}


def test_parse_prose_around_object_and_braces_noise():
    txt = 'I think {not json} then {"eyes_needed": 9, "nested": {"a": 1}} done'
    assert A.parse_json_answer(txt) == {"eyes_needed": 9, "nested": {"a": 1}}


def test_parse_none():
    assert A.parse_json_answer("no json here") is None
    assert A.parse_json_answer("") is None
    assert A.parse_json_answer(None) is None


def test_unparseable_is_wrong():
    r = A.check_answer(T("number"), {"answer": {"n": 1}}, None)
    assert r["verdict"] == "WRONG"


# --- number --------------------------------------------------------------

def test_number_abs_boundary():
    ref = {"answer": {"eyes": 9, "carry": 11}, "tolerance": {"abs": 1}}
    assert A.check_answer(T("number"), ref, {"eyes": 10, "carry": 10})["verdict"] == "OK"
    assert A.check_answer(T("number"), ref, {"eyes": 11, "carry": 11})["verdict"] == "WRONG"


def test_number_fields_unlisted_exact():
    ref = {"answer": {"eyes": 9, "carry": 11}, "tolerance": {"fields": {"carry": {"abs": 2}}}}
    assert A.check_answer(T("number"), ref, {"eyes": 9, "carry": 13, "reasoning": "x", "extra": 5})["verdict"] == "OK"
    r = A.check_answer(T("number"), ref, {"eyes": 10, "carry": 11})
    assert r["verdict"] == "WRONG" and "eyes" in r["reason"]


def test_number_missing_field_and_string_number():
    ref = {"answer": {"obsidian": 10}, "tolerance": {}}
    assert A.check_answer(T("number"), ref, {})["verdict"] == "WRONG"
    assert A.check_answer(T("number"), ref, {"obsidian": "10"})["verdict"] == "OK"
    assert A.check_answer(T("number"), ref, {"obsidian": True})["verdict"] == "WRONG"


# --- coordinates ---------------------------------------------------------

def test_coords_boundary_and_dimension():
    ref = {"answer": {"x": 0, "z": 0, "dimension": "the_nether"}, "tolerance": {"blocks": 5}}
    assert A.check_answer(T("coordinates"), ref, {"x": 3, "z": 4, "dimension": "the_nether"})["verdict"] == "OK"
    assert A.check_answer(T("coordinates"), ref, {"x": 3, "z": 4.01, "dimension": "the_nether"})["verdict"] == "WRONG"
    r = A.check_answer(T("coordinates"), ref, {"x": 0, "z": 0, "dimension": "overworld"})
    assert r["verdict"] == "WRONG" and "dimension" in r["reason"]


def test_coords_y_scoring():
    ref = {"answer": {"x": 0, "y": 64, "z": 0, "dimension": "overworld"}, "tolerance": {"blocks": 5}}
    assert A.check_answer(T("coordinates"), ref, {"x": 0, "y": 200, "z": 0, "dimension": "overworld"})["verdict"] == "OK"
    ref["tolerance"]["y_blocks"] = 3
    assert A.check_answer(T("coordinates"), ref, {"x": 0, "y": 67, "z": 0, "dimension": "overworld"})["verdict"] == "OK"
    assert A.check_answer(T("coordinates"), ref, {"x": 0, "y": 68, "z": 0, "dimension": "overworld"})["verdict"] == "WRONG"
    assert A.check_answer(T("coordinates"), ref, {"x": 0, "z": 0, "dimension": "overworld"})["verdict"] == "WRONG"


# --- choice --------------------------------------------------------------

def test_choice_default_and_set():
    ref = {"answer": {"choice": "reset"}, "tolerance": {}}
    assert A.check_answer(T("choice"), ref, {"choice": "reset", "reasoning": "?"})["verdict"] == "OK"
    assert A.check_answer(T("choice"), ref, {"choice": "keep"})["verdict"] == "WRONG"
    ref["tolerance"] = {"choices": ["reset", "keep"]}
    assert A.check_answer(T("choice"), ref, {"choice": "keep"})["verdict"] == "OK"


def test_choice_extras():
    ref = {"answer": {"choice": "no", "rods": 0}, "tolerance": {"fields": {"rods": {"abs": 1}}}}
    assert A.check_answer(T("choice"), ref, {"choice": "no", "rods": 1})["verdict"] == "OK"
    assert A.check_answer(T("choice"), ref, {"choice": "no", "rods": 2})["verdict"] == "WRONG"
    assert A.check_answer(T("choice"), ref, {"choice": "no"})["verdict"] == "WRONG"


# --- geometry ------------------------------------------------------------

def test_yaw_convention():
    dx, dz = A.yaw_direction(0)
    assert abs(dx) < 1e-9 and abs(dz - 1) < 1e-9          # +Z
    dx, dz = A.yaw_direction(90)
    assert abs(dx + 1) < 1e-9 and abs(dz) < 1e-9           # -X
    dx, dz = A.yaw_direction(-90)
    assert abs(dx - 1) < 1e-9 and abs(dz) < 1e-9           # +X


def _yaw_towards(x, z, tx, tz):
    # inverse of direction (-sin, cos)
    return math.degrees(math.atan2(-(tx - x), tz - z))


def test_triangulate_known_point():
    target = (1500.0, -900.0)
    p1, p2 = (0.0, 0.0), (300.0, 200.0)
    y1 = _yaw_towards(*p1, *target)
    y2 = _yaw_towards(*p2, *target)
    x, z = A.triangulate(p1[0], p1[1], y1, p2[0], p2[1], y2)
    assert abs(x - target[0]) < 1e-6 and abs(z - target[1]) < 1e-6
    r = A.triangulation_error_radius(p1[0], p1[1], y1, p2[0], p2[1], y2)
    assert r is not None and r > 0
    assert A.ring_of(x, z) == 1


def test_triangulate_simple_axes():
    # From (0,0) facing +X (yaw -90); from (10,-10) facing +Z (yaw 0) -> (10, 0)
    x, z = A.triangulate(0, 0, -90, 10, -10, 0)
    assert abs(x - 10) < 1e-9 and abs(z) < 1e-9


def test_triangulate_parallel():
    assert A.triangulate(0, 0, 10, 100, 0, 10.5) is None
    assert A.triangulate(0, 0, 10, 100, 0, 190.2) is None
    assert A.triangulation_error_radius(0, 0, 10, 100, 0, 10.5) is None


def test_ring_of():
    assert A.ring_of(1280, 0) == 1
    assert A.ring_of(0, 2816) == 1
    assert A.ring_of(3000, 0) is None
    assert A.ring_of(5000, 0) == 2
    assert A.ring_of(100, 100) is None


def test_nether_conversion():
    assert A.overworld_to_nether(-1130, 856) == (-141.25, 107.0)
    assert A.nether_to_overworld(-141.25, 107) == (-1130, 856)
    assert A.horizontal_distance(0, 0, 3, 4) == 5


def test_portal_link_target():
    t = A.portal_link_target(-1130, 34, 856, "overworld")
    assert t["dimension"] == "the_nether"
    assert (t["x"], t["y"], t["z"]) == (-141.25, 34, 107.0)
    assert t["search_radius"] == 16
    t = A.portal_link_target(-1130, 200, 856, "overworld")
    assert t["y"] <= 128
    t = A.portal_link_target(10, 70, -5, "the_nether")
    assert (t["x"], t["y"], t["z"], t["dimension"], t["search_radius"]) == (80, 70, -40, "overworld", 128)
    assert A.PORTAL_SEARCH_RADIUS["verified"] is False


# --- plan delegation -----------------------------------------------------

def _sim_available():
    return importlib.util.find_spec("splitcheck.sim") is not None


def test_plan_without_actions_is_wrong():
    assert A.check_answer(T("plan"), {"pro_time_s": 10}, {"foo": 1})["verdict"] == "WRONG"


def test_plan_delegation_with_fake_sim(monkeypatch):
    import sys, types
    from dataclasses import dataclass, field

    @dataclass
    class R:
        legal: bool
        reason: str = None
        failed_step: int = None
        time_s: float = 0.0
        steps: list = field(default_factory=list)
        final_state: dict = field(default_factory=dict)
        techniques_used: list = field(default_factory=list)

    fake = types.ModuleType("splitcheck.sim")
    outcome = {}
    fake.simulate = lambda task, plan, costs=None: outcome["r"]
    import splitcheck
    monkeypatch.setitem(sys.modules, "splitcheck.sim", fake)
    monkeypatch.setattr(splitcheck, "sim", fake, raising=False)

    ref = {"pro_time_s": 100, "tolerance": {"seconds": 10}}
    plan = {"actions": [{"action": "mine"}, {"action": "light_portal", "with": "flint_and_steel"}]}
    outcome["r"] = R(legal=True, time_s=110)
    r = A.check_answer(T("plan"), ref, plan)
    assert r["verdict"] == "OK" and r["details"]["time_s"] == 110 and r["details"]["pro_time_s"] == 100
    outcome["r"] = R(legal=True, time_s=110.5)
    assert A.check_answer(T("plan"), ref, plan)["verdict"] == "SLOW"
    outcome["r"] = R(legal=False, reason="no flint_and_steel", failed_step=1, time_s=5)
    r = A.check_answer(T("plan"), ref, plan)
    assert r["verdict"] == "ILLEGAL" and "step 1" in r["reason"] and "flint_and_steel" in r["reason"]


@pytest.mark.skipif(not _sim_available(), reason="sim.py not written yet")
def test_plan_with_real_sim_runs():
    task = {"id": "t", "answer_type": "plan", "state": {
        "dimension": "overworld", "position": {"x": 0, "y": 64, "z": 0}, "inventory": {},
        "known_locations": {}, "world": {}, "elapsed_s": 0}}
    r = A.check_answer(task, {"pro_time_s": None, "tolerance": {}},
                       {"actions": [{"action": "light_portal", "with": "flint_and_steel"}]})
    assert r["verdict"] == "ILLEGAL"
