"""Answer parsing, tolerance checks (SCHEMA.md section 3) and geometry helpers.

Deterministic, standard library only, no LLM calls.
"""
from __future__ import annotations

import json
import math
import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 1.16.2+ Nether portal search radius (blocks) when looking for an existing
# portal at the destination. 1.16.0/1.16.1 used 128 on both sides.
PORTAL_SEARCH_RADIUS = {
    "overworld": 128,
    "the_nether": 16,
    "source": "minecraft.wiki/w/Nether_portal (Java 1.16.2 changelog: nether-side search radius 128 -> 16); not re-checked against 1.16.5 decompiled code",
    "verified": False,
}

# Valid Y range used when clamping a portal link target (1.16.5 build limits:
# overworld 0..255, nether logical height 128 with bedrock roof). Conservative
# values that keep a 3-tall portal inside the range.
PORTAL_Y_RANGE = {
    "overworld": (1, 253),
    "the_nether": (1, 124),
    "source": "estimate from 1.16.5 world height (256) and nether logical height (128)",
    "verified": False,
}

# Stronghold rings for Java 1.9+ (distance from 0,0 in blocks).
STRONGHOLD_RINGS = [
    (1, 1280, 2816),
    (2, 4352, 5888),
    (3, 7424, 8960),
    (4, 10496, 12032),
    (5, 13568, 15104),
    (6, 16640, 18176),
    (7, 19712, 21248),
    (8, 22784, 24320),
]

# Typical angular error of a reading of an eye of ender's direction (degrees).
DEFAULT_YAW_ERROR_DEG = 0.5  # estimate, verified=False

_NETHER = "the_nether"
_OVERWORLD = "overworld"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def horizontal_distance(x1, z1, x2, z2) -> float:
    return math.hypot(float(x2) - float(x1), float(z2) - float(z1))


def overworld_to_nether(x, z):
    return (x / 8, z / 8)


def nether_to_overworld(x, z):
    return (x * 8, z * 8)


def portal_link_target(x, y, z, from_dim):
    """Where a portal at (x, y, z) in from_dim looks for/creates its partner (1.16.5).

    X and Z are divided by 8 (overworld -> nether) or multiplied by 8
    (nether -> overworld). Y is not scaled, only clamped to the destination's
    valid range (PORTAL_Y_RANGE). The game then searches for an existing portal
    within PORTAL_SEARCH_RADIUS[dest] of this point before building a new one.
    Returns {"x", "y", "z", "dimension", "search_radius"}.
    """
    if from_dim == _OVERWORLD:
        dest = _NETHER
        tx, tz = overworld_to_nether(x, z)
    elif from_dim == _NETHER:
        dest = _OVERWORLD
        tx, tz = nether_to_overworld(x, z)
    else:
        raise ValueError(f"portal linking only between overworld and the_nether, got {from_dim!r}")
    lo, hi = PORTAL_Y_RANGE[dest]
    ty = min(max(y, lo), hi)
    return {"x": tx, "y": ty, "z": tz, "dimension": dest,
            "search_radius": PORTAL_SEARCH_RADIUS[dest]}


def yaw_direction(yaw):
    """Unit (dx, dz) for a Minecraft yaw in degrees: 0 = +Z (south), 90 = -X (west)."""
    r = math.radians(yaw)
    return (-math.sin(r), math.cos(r))


def _angle_between_deg(yaw1, yaw2) -> float:
    """Angle between the two lines (0..90 degrees; direction ignored)."""
    d = abs((yaw1 - yaw2) % 180.0)
    return min(d, 180.0 - d)


def triangulate(x1, z1, yaw1, x2, z2, yaw2):
    """Intersection of the line from (x1, z1) along yaw1 and from (x2, z2) along yaw2.

    Returns (x, z), or None when the lines are nearly parallel (< 1 degree apart) or
    when the intersection lies behind either thrower (an eye only flies forward).
    """
    if _angle_between_deg(yaw1, yaw2) < 1.0:
        return None
    dx1, dz1 = yaw_direction(yaw1)
    dx2, dz2 = yaw_direction(yaw2)
    # Solve P1 + t*d1 = P2 + s*d2 for t (Cramer's rule).
    det = dx1 * (-dz2) - dz1 * (-dx2)
    if abs(det) < 1e-12:
        return None
    bx, bz = x2 - x1, z2 - z1
    t = (bx * (-dz2) - bz * (-dx2)) / det
    u = (dx1 * bz - dz1 * bx) / det
    if t < 0 or u < 0:
        return None
    return (x1 + t * dx1, z1 + t * dz1)


def triangulation_error_radius(x1, z1, yaw1, x2, z2, yaw2, yaw_error_deg=DEFAULT_YAW_ERROR_DEG):
    """Rough uncertainty radius (blocks) of triangulate(...).

    Formula: each ray's lateral error at the intersection is d_i * tan(e), where
    d_i is the thrower-to-intersection distance and e the yaw reading error.
    Two rays crossing at angle theta turn a lateral error w into a positional
    error of about w / sin(theta), so
        radius = max(d1, d2) * tan(e) / sin(theta).
    Returns None for nearly parallel rays. e defaults to an estimate (0.5 deg,
    verified=False).
    """
    p = triangulate(x1, z1, yaw1, x2, z2, yaw2)
    if p is None:
        return None
    theta = math.radians(_angle_between_deg(yaw1, yaw2))
    d = max(horizontal_distance(x1, z1, *p), horizontal_distance(x2, z2, *p))
    return d * math.tan(math.radians(yaw_error_deg)) / math.sin(theta)


def ring_of(x, z):
    """Stronghold ring number (1.9+ table) for a point, or None if between rings."""
    r = math.hypot(x, z)
    for ring, lo, hi in STRONGHOLD_RINGS:
        if lo <= r <= hi:
            return ring
    return None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def _objects(text: str, offset: int = 0):
    """All top-level JSON objects in text, as (obj, start, end) in order."""
    dec = json.JSONDecoder()
    out = []
    i = text.find("{")
    while i != -1:
        try:
            obj, end = dec.raw_decode(text, i)
            if isinstance(obj, dict):
                out.append((obj, offset + i, offset + end))
                i = text.find("{", end)
                continue
        except json.JSONDecodeError:
            pass
        i = text.find("{", i + 1)
    return out


def _first_object(text: str):
    objs = _objects(text)
    return objs[0][0] if objs else None


def answer_candidates(text):
    """Every JSON object in the reply: fenced blocks first (in order), then the whole text."""
    if text is None:
        return []
    text = str(text)
    out = []
    for m in _FENCE_RE.finditer(text):
        for obj, a, b in _objects(m.group(1), m.start(1)):
            out.append({"obj": obj, "span": [a, b], "fenced": True})
    seen = {tuple(c["span"]) for c in out}
    for obj, a, b in _objects(text):
        if not any(sa <= a and b <= sb for sa, sb in seen):
            out.append({"obj": obj, "span": [a, b], "fenced": False})
    out.sort(key=lambda c: c["span"][0])
    return out


def required_keys_for(task, ref=None):
    """Keys an answer object must have to count as the model's answer."""
    atype = (task or {}).get("answer_type")
    if atype == "plan":
        return ["actions"]
    if atype == "coordinates":
        return ["x", "z"]
    if atype == "choice":
        return ["choice"]
    if atype == "number" and ref and isinstance(ref.get("answer"), dict):
        return [k for k in ref["answer"] if k != "reasoning"]
    return []


def select_answer(text, task=None, ref=None):
    """Pick the scored object from a reply: the LAST object that has the answer_type's keys and
    is not the answer_schema example echoed back. Falls back to the first object.

    Returns (obj | None, info) where info cites which object/span was used.
    """
    if isinstance(text, dict):
        return text, {"selected": "dict passed directly"}
    cands = answer_candidates(text)
    if not cands:
        return None, {"selected": None, "candidates": 0}
    keys = required_keys_for(task, ref)
    schema_obj = None
    schema = (task or {}).get("answer_schema")
    if isinstance(schema, str):
        schema_obj = _first_object(schema)
    elif isinstance(schema, dict):
        schema_obj = schema
    ok = [i for i, c in enumerate(cands)
          if all(k in c["obj"] for k in keys) and not (schema_obj is not None and c["obj"] == schema_obj)]
    if ok:
        idx, why = ok[-1], f"last of {len(ok)} object(s) with keys {keys} that is not the answer_schema echo"
    else:
        idx, why = 0, f"no object had keys {keys}; used the first object"
    c = cands[idx]
    return c["obj"], {"selected": why, "candidate_index": idx, "candidates": len(cands),
                      "span": c["span"], "fenced": c["fenced"]}


def parse_json_answer(text):
    """Extract the first valid JSON object from a raw model reply, or None.

    Fenced code blocks are tried first (in order), then the whole text. The checker uses
    select_answer() (last object matching the answer type) instead; this keeps the contract.
    """
    if text is None:
        return None
    if isinstance(text, dict):
        return text
    text = str(text)
    for block in _FENCE_RE.findall(text):
        obj = _first_object(block)
        if obj is not None:
            return obj
    return _first_object(text)


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def _norm_str(v):
    return v.strip().lower() if isinstance(v, str) else v


def _result(verdict, reason, **details):
    return {"verdict": verdict, "reason": reason, "details": details}


def _field_tol(tol: dict, name: str):
    fields = tol.get("fields") or {}
    if name in fields and isinstance(fields[name], dict):
        return fields[name].get("abs", 0)
    return None


def _compare_field(name, got, want, abs_tol):
    """Return (ok, reason) for one field."""
    if isinstance(want, bool) or not isinstance(want, (int, float)):
        if isinstance(want, str):
            ok = isinstance(got, str) and _norm_str(got) == _norm_str(want)
        else:
            ok = got == want
        return ok, f"field '{name}': got {got!r}, expected {want!r}" + ("" if ok else " (must match exactly)")
    g = _num(got)
    if g is None:
        return False, f"field '{name}': got {got!r}, expected a number ({want})"
    tol = float(abs_tol or 0)
    diff = abs(g - float(want))
    ok = diff <= tol + 1e-9
    return ok, f"field '{name}': got {got}, expected {want} ±{abs_tol or 0} (off by {diff:g})"


def _check_fields(answer, ref_answer, tol, skip=(), global_abs=None):
    notes, bad = [], []
    for name, want in ref_answer.items():
        if name in skip or name == "reasoning":
            continue
        if name not in answer:
            bad.append(f"field '{name}' missing from answer")
            continue
        abs_tol = _field_tol(tol, name)
        if abs_tol is None:
            abs_tol = global_abs
        ok, why = _compare_field(name, answer[name], want, abs_tol)
        (notes if ok else bad).append(why)
    return bad, notes


def _check_number(ref_answer, answer, tol):
    bad, notes = _check_fields(answer, ref_answer, tol, global_abs=tol.get("abs"))
    if bad:
        return _result("WRONG", "; ".join(bad), checked=notes, failed=bad)
    return _result("OK", "all fields within tolerance: " + "; ".join(notes), checked=notes)


def _check_coordinates(ref_answer, answer, tol):
    want_dim = ref_answer.get("dimension")
    got_dim = answer.get("dimension")
    if want_dim is not None and _norm_str(got_dim) != _norm_str(want_dim):
        return _result("WRONG", f"field 'dimension': got {got_dim!r}, expected {want_dim!r}",
                       got_dimension=got_dim, expected_dimension=want_dim)
    gx, gz = _num(answer.get("x")), _num(answer.get("z"))
    if gx is None or gz is None:
        return _result("WRONG", f"answer needs numeric 'x' and 'z' (got x={answer.get('x')!r}, z={answer.get('z')!r})")
    rx, rz = float(ref_answer["x"]), float(ref_answer["z"])
    blocks = float(tol.get("blocks", 0))
    dist = horizontal_distance(gx, gz, rx, rz)
    details = {"horizontal_distance": round(dist, 3), "tolerance_blocks": blocks,
               "got": {"x": gx, "z": gz}, "expected": {"x": rx, "z": rz}}
    if dist > blocks + 1e-9:
        return _result("WRONG", f"({gx:g}, {gz:g}) is {dist:.1f} blocks from reference ({rx:g}, {rz:g}); tolerance {blocks:g}", **details)
    if "y_blocks" in tol and "y" in ref_answer and ref_answer["y"] is not None:
        gy = _num(answer.get("y"))
        ry = float(ref_answer["y"])
        yt = float(tol["y_blocks"])
        details.update(got_y=gy, expected_y=ry, tolerance_y_blocks=yt)
        if gy is None:
            return _result("WRONG", f"field 'y' missing or not a number (y is scored, expected {ry:g} ±{yt:g})", **details)
        if abs(gy - ry) > yt + 1e-9:
            return _result("WRONG", f"y={gy:g} is {abs(gy-ry):g} from reference y={ry:g}; tolerance {yt:g}", **details)
    return _result("OK", f"({gx:g}, {gz:g}) is {dist:.1f} blocks from reference ({rx:g}, {rz:g}); within {blocks:g}", **details)


def _check_choice(ref_answer, answer, tol):
    accepted = tol.get("choices") or [ref_answer.get("choice")]
    got = answer.get("choice")
    if _norm_str(got) not in [_norm_str(c) for c in accepted]:
        return _result("WRONG", f"field 'choice': got {got!r}, accepted {accepted!r}", accepted=accepted, got=got)
    bad, notes = _check_fields(answer, ref_answer, tol, skip=("choice",))
    if bad:
        return _result("WRONG", f"choice {got!r} accepted but " + "; ".join(bad), accepted=accepted, failed=bad)
    extra = ("; " + "; ".join(notes)) if notes else ""
    return _result("OK", f"choice {got!r} is in accepted {accepted!r}{extra}", accepted=accepted, checked=notes)


def _check_plan(task, ref, answer, tol, costs):
    actions = answer.get("actions")
    if not isinstance(actions, list):
        return _result("WRONG", "plan answer has no 'actions' list")
    from . import sim  # lazy: sim may not exist yet
    res = sim.simulate(task, answer, costs)
    pro = ref.get("pro_time_s")
    secs = float(tol.get("seconds", 0))
    details = {"time_s": res.time_s, "pro_time_s": pro, "tolerance_seconds": secs,
               "failed_step": res.failed_step, "techniques_used": list(res.techniques_used),
               "steps": res.steps}
    if pro is None and isinstance(ref.get("answer"), dict) and ref.get("answer") is not answer:
        rres = sim.simulate(task, ref["answer"], costs)
        if rres.legal:
            pro = rres.time_s
            details["pro_time_s"] = pro
            details["pro_time_source"] = "reference.answer priced with the time-cost table (pro_time_s null, SCHEMA v2)"
    if not res.legal:
        step = res.failed_step
        act = None
        if step is not None and 0 <= step < len(actions) and isinstance(actions[step], dict):
            act = actions[step].get("action")
        reason = str(res.reason or "")
        if not reason.startswith(f"step {step} "):
            reason = f"step {step} ({act}): {reason}"
        return _result("ILLEGAL", reason, **details)
    goal = plan_goal(task, ref)
    details["goal"] = goal
    unmet = goal_unmet(goal, res.final_state)
    if unmet:
        return _result("WRONG", f"legal plan ({len(actions)} steps) does not reach the task goal: {unmet}", **details)
    if pro is None:
        return _result("OK", f"legal plan, {res.time_s:.1f}s (no pro_time_s to compare)", **details)
    limit = float(pro) + secs
    if res.time_s > limit + 1e-9:
        return _result("SLOW", f"legal plan takes {res.time_s:.1f}s, more than pro {float(pro):.1f}s + {secs:g}s tolerance (+{res.time_s - float(pro):.1f}s)", **details)
    return _result("OK", f"legal plan takes {res.time_s:.1f}s, within pro {float(pro):.1f}s + {secs:g}s", **details)


# Default goal per split when neither reference nor task gives "goal".
SPLIT_GOALS = {
    "nether_entry": {"dimension": "the_nether"},
    "portal_room": {"end_portal_active": True},
}


def plan_goal(task, ref):
    """Goal predicates for a plan: ref['goal'] > task['goal'] > SPLIT_GOALS[task['split']]."""
    for src in (ref or {}, task or {}):
        g = src.get("goal")
        if isinstance(g, dict):
            return g
    return SPLIT_GOALS.get((task or {}).get("split"))


def goal_unmet(goal, final):
    """Human-readable reason the final state misses the goal, or None if it is met.

    Supported predicates: dimension, inventory {item: min}, reset (bool),
    end_portal_active (bool), dragon_killed (bool).
    """
    if not goal:
        return None
    final = final or {}
    if final.get("reset") and not goal.get("reset"):
        return "plan resets the world, but this task's goal is not a reset"
    if goal.get("reset"):
        return None if final.get("reset") else "goal is a reset but the plan does not reset"
    bad = []
    if goal.get("dimension") and final.get("dimension") != goal["dimension"]:
        bad.append(f"final dimension {final.get('dimension')!r}, goal {goal['dimension']!r}")
    inv = final.get("inventory") or {}
    for item, n in (goal.get("inventory") or {}).items():
        if inv.get(item, 0) < n:
            bad.append(f"final inventory has {inv.get(item, 0)} {item}, goal needs {n}")
    if goal.get("end_portal_active"):
        frames = final.get("end_portal_frames") or {}
        if not any(v >= 12 for v in frames.values()) and final.get("dimension") != "the_end":
            bad.append("no End portal activated")
    beds_needed = goal.get("dragon_beds")
    beds_ok = isinstance(beds_needed, (int, float)) and final.get("beds_exploded_in_end", 0) >= beds_needed
    if goal.get("dragon_killed") and not (final.get("dragon_killed") or beds_ok):
        bad.append("ender dragon not killed")
    return "; ".join(bad) or None


def check_answer(task, ref, answer, costs=None):
    """Score one parsed answer against a reference. See SCHEMA.md section 3."""
    if not isinstance(answer, dict):
        return _result("WRONG", "reply did not contain a parseable JSON object")
    atype = task.get("answer_type")
    ref_answer = ref.get("answer")
    tol = ref.get("tolerance") or {}
    if atype == "plan":
        return _check_plan(task, ref, answer, tol, costs)
    if not isinstance(ref_answer, dict):
        return _result("WRONG", f"reference answer for {ref.get('id')} is not an object (checker data error)")
    if atype == "number":
        return _check_number(ref_answer, answer, tol)
    if atype == "coordinates":
        return _check_coordinates(ref_answer, answer, tol)
    if atype == "choice":
        return _check_choice(ref_answer, answer, tol)
    return _result("WRONG", f"unknown answer_type {atype!r} in task {task.get('id')}")
