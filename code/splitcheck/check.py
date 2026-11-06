"""SplitCheck Layer A checker: CLI + library.

Usage:
    cd code && python -m splitcheck.check --root <repo> [--self-test] [--costs <time_costs.json>]

Reads <root>/tasks/*.json, <root>/reference/*.json, <root>/attempts/*.json.
Writes <root>/runs/results.csv and <root>/runs/checker_output/<task_id>.json.
Deterministic, standard library only, no LLM calls.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

CSV_COLUMNS = ["task_id", "model", "verdict", "reason", "miss_category",
               "techniques_missed", "time_s", "pro_time_s"]


class DependencyMissing(RuntimeError):
    pass


def _mods():
    """Import answers/sim lazily so a missing module gives a clear error."""
    try:
        from . import answers  # noqa: WPS433
    except ImportError as e:
        raise DependencyMissing(
            f"splitcheck.answers could not be imported ({e}). "
            "check.py needs code/splitcheck/answers.py (parse_json_answer, check_answer).") from e
    try:
        from . import sim  # noqa: WPS433
    except ImportError as e:
        raise DependencyMissing(
            f"splitcheck.sim could not be imported ({e}). "
            "check.py needs code/splitcheck/sim.py (load_costs, simulate).") from e
    return answers, sim


# ---------------------------------------------------------------- library

def _techniques_used(task, answer, result, costs):
    details = result.get("details") or {}
    used = details.get("techniques_used")
    if used is None and task.get("answer_type") == "plan" and isinstance(answer, dict) \
            and isinstance(answer.get("actions"), list):
        try:
            _, sim = _mods()
            used = sim.simulate(task, answer, costs).techniques_used
        except Exception:  # sim failure is already reflected in the verdict
            used = None
    return list(used or [])


def _check_parsed(task, ref, answer, costs=None):
    answers, _ = _mods()
    result = dict(answers.check_answer(task, ref, answer, costs))
    result.setdefault("details", {})
    result["task_id"] = task.get("id")
    result["answer_type"] = task.get("answer_type")
    result["parsed_answer"] = answer
    details = result["details"] or {}
    result["time_s"] = details.get("time_s")
    result["pro_time_s"] = details.get("pro_time_s", ref.get("pro_time_s"))
    if result.get("verdict") != "OK":
        used = set(_techniques_used(task, answer, result, costs))
        tags = [t.get("tag") for t in ref.get("techniques", []) if isinstance(t, dict) and t.get("tag")]
        result["miss_category"] = ref.get("miss_category")
        result["techniques_missed"] = [t for t in tags if t not in used]
    else:
        result["miss_category"] = None
        result["techniques_missed"] = []
    return result


def check_task(task: dict, ref: dict, raw_response: str, costs: dict | None = None) -> dict:
    """Parse a raw model reply and check it. Adds miss_category / techniques_missed when not OK."""
    answers, _ = _mods()
    parsed, sel = answers.select_answer(raw_response if isinstance(raw_response, str) else "", task, ref)
    result = _check_parsed(task, ref, parsed, costs)
    result["details"]["answer_selection"] = sel
    if parsed is None:
        result["verdict"] = "WRONG"
        if not result.get("reason"):
            result["reason"] = "reply contained no parseable JSON object"
    return result


def _load_json_dir(d: Path):
    """Return ({id: obj}, [errors]) for every *.json in d (sorted, deterministic)."""
    out, errors = {}, []
    if not d.is_dir():
        return out, [f"missing directory: {d}"]
    for p in sorted(d.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"{p.name}: unreadable JSON ({e})")
            continue
        key = obj.get("id", p.stem) if isinstance(obj, dict) else p.stem
        out[key] = obj
    return out, errors


def _load_costs(root: Path, costs_path=None):
    _, sim = _mods()
    if costs_path:
        return sim.load_costs(str(costs_path))
    p = root / "splits" / "time_costs.json"
    return sim.load_costs(str(p) if p.is_file() else None)


def self_test(root, costs: dict | None = None) -> list[dict]:
    """Every reference answer and alternate must be OK; every broken must hit expected_verdict."""
    root = Path(root)
    tasks, _ = _load_json_dir(root / "tasks")
    refs, _ = _load_json_dir(root / "reference")
    if costs is None:
        costs = _load_costs(root)
    cases = []
    for rid in sorted(refs):
        ref = refs[rid]
        task = tasks.get(rid)
        if task is None:
            cases.append({"task_id": rid, "case": "reference", "index": None, "expected": "OK",
                          "got": None, "pass": False, "reason": f"no tasks/{rid}.json for this reference"})
            continue
        todo = [("reference", None, ref.get("answer"), "OK")]
        todo += [("alternate", i, a.get("answer"), "OK") for i, a in enumerate(ref.get("alternates", []))]
        todo += [("broken", i, b.get("answer"), b.get("expected_verdict"))
                 for i, b in enumerate(ref.get("broken", []))]
        if not ref.get("alternates"):
            cases.append({"task_id": rid, "case": "alternate", "index": None, "expected": "OK", "got": None,
                          "pass": False, "reason": "SCHEMA §3 requires >=1 alternate"})
        if not ref.get("broken"):
            cases.append({"task_id": rid, "case": "broken", "index": None, "expected": "ILLEGAL|SLOW|WRONG",
                          "got": None, "pass": False, "reason": "SCHEMA §3 requires >=1 broken answer"})
        for case, idx, answer, expected in todo:
            try:
                r = _check_parsed(task, ref, answer, costs)
                got, reason = r.get("verdict"), r.get("reason")
            except DependencyMissing:
                raise
            except Exception as e:  # a checker crash is a failed case, not a crashed self-test
                got, reason = "ERROR", f"checker raised {type(e).__name__}: {e}"
            cases.append({"task_id": rid, "case": case, "index": idx, "expected": expected,
                          "got": got, "pass": got == expected, "reason": reason})
    return cases


def _load_attempts(d: Path):
    attempts, errors = [], []
    if not d.is_dir():
        return attempts, [f"missing directory: {d}"]
    for p in sorted(d.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"{p.name}: unreadable JSON ({e})")
            continue
        for i, a in enumerate(obj if isinstance(obj, list) else [obj]):
            if isinstance(a, dict) and a.get("task_id"):
                attempts.append(dict(a, _file=p.name, _index=i))
            else:
                errors.append(f"{p.name}[{i}]: not an attempt object with task_id")
    return attempts, errors


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def run_attempts(root, costs: dict | None = None) -> tuple[list[dict], list[str]]:
    """Check every attempt; write runs/results.csv and runs/checker_output/<task_id>.json."""
    root = Path(root)
    tasks, terr = _load_json_dir(root / "tasks")
    refs, rerr = _load_json_dir(root / "reference")
    attempts, aerr = _load_attempts(root / "attempts")
    problems = terr + rerr + aerr
    if costs is None:
        costs = _load_costs(root)
    results = []
    for a in attempts:
        tid = a["task_id"]
        base = {"task_id": tid, "model": a.get("model", ""), "date": a.get("date"),
                "attempt_file": a["_file"], "prompt": a.get("prompt"), "raw_response": a.get("raw_response")}
        if tid not in tasks or tid not in refs:
            missing = [n for n, s in (("tasks", tasks), ("reference", refs)) if tid not in s]
            problems.append(f"attempt {a['_file']}: no {' or '.join(missing)} file for task {tid}; skipped")
            continue
        try:
            r = check_task(tasks[tid], refs[tid], a.get("raw_response") or "", costs)
        except DependencyMissing:
            raise
        except Exception as e:  # one bad reply must not abort the batch
            r = {"task_id": tid, "verdict": "WRONG", "reason": f"checker error on this reply: {type(e).__name__}: {e}",
                 "details": {"error": repr(e)}, "miss_category": refs[tid].get("miss_category"),
                 "techniques_missed": [], "time_s": None, "pro_time_s": refs[tid].get("pro_time_s")}
        results.append(dict(base, **r))

    out_dir = root / "runs" / "checker_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(root / "runs" / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for r in results:
            w.writerow([r["task_id"], r.get("model", ""), r.get("verdict", ""), r.get("reason", "") or "",
                        r.get("miss_category") or "", ";".join(r.get("techniques_missed") or []),
                        _fmt(r.get("time_s")), _fmt(r.get("pro_time_s"))])
    by_task: dict[str, list] = {}
    for r in results:
        by_task.setdefault(r["task_id"], []).append(r)
    for tid, rs in sorted(by_task.items()):
        (out_dir / f"{tid}.json").write_text(
            json.dumps({"task_id": tid, "attempts": rs}, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8")
    return results, problems


# ---------------------------------------------------------------- CLI

def _print_self_test(cases):
    for c in cases:
        idx = "" if c["index"] is None else f"[{c['index']}]"
        status = "PASS" if c["pass"] else "FAIL"
        print(f"{status}  {c['task_id']} {c['case']}{idx}: expected {c['expected']}, got {c['got']}"
              f" -- {c['reason']}")
    n_fail = sum(not c["pass"] for c in cases)
    print(f"\nself-test: {len(cases) - n_fail}/{len(cases)} cases passed")
    return n_fail


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m splitcheck.check", description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.getcwd(), help="repo root holding tasks/, reference/, attempts/")
    ap.add_argument("--self-test", action="store_true", help="check reference/alternate/broken answers only")
    ap.add_argument("--costs", default=None, help="time_costs.json (default: <root>/splits/time_costs.json)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        costs = _load_costs(root, args.costs)
        if args.self_test:
            cases = self_test(root, costs)
            if not cases:
                print(f"self-test: no reference files found in {root / 'reference'}")
                return 1
            return 1 if _print_self_test(cases) else 0
        results, problems = run_attempts(root, costs)
    except DependencyMissing as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"note: {p}")
    if not results:
        print(f"no attempts checked (looked in {root / 'attempts'})")
    else:
        counts: dict[str, int] = {}
        for r in results:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
            extra = ""
            if r["verdict"] != "OK":
                extra = f" [miss: {r.get('miss_category') or '-'}"
                if r.get("techniques_missed"):
                    extra += f"; techniques missed: {', '.join(r['techniques_missed'])}"
                extra += "]"
            t = ""
            if r.get("time_s") is not None:
                t = f" time {_fmt(r['time_s'])}s vs pro {_fmt(r.get('pro_time_s'))}s"
            print(f"{r['verdict']:<8} {r['task_id']}  ({r.get('model') or '?'}){t}: {r.get('reason')}{extra}")
        print("\nsummary: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
              + f" (of {len(results)})")
    print(f"wrote {root / 'runs' / 'results.csv'} and {root / 'runs' / 'checker_output'}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
