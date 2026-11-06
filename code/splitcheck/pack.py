"""Results pack: deterministically regenerate every headline result into one folder.

CLI: python -m splitcheck.pack --root .. --out ../runs/results_pack [--no-determinism-check]

Writes <out>/RESULTS.md plus the JSON it is built from:
  efficiency/published_montage.json, efficiency/fixtures.json   (splitcheck.effcheck)
  runs/<run>.json                                                (splitcheck.evaluate summary)
  decision/<suite>.json, decision/self_test_<suite>.json          (splitcheck.check)
  determinism.json                                               (two packs into temp dirs, filecmp)
Full evaluate outputs go to <root>/runs/<run>-eval (or <eval-root>/<run>-eval).

Stdlib only, no LLM calls, no timestamps in the outputs.
"""
from __future__ import annotations

import argparse
import contextlib
import filecmp
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from . import check as checkmod
from . import effcheck
from . import evaluate as evalmod

CLAIM_CODES = ("self_report_contradiction", "inventory_loss_without_effect", "agent_server_mismatch")


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _f(x, nd=3):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}".rstrip("0").rstrip(".") if nd else str(x)
    return str(x)


def _cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _strip(obj, keys=("flags",)):
    """Comparison copy of an effcheck result without keys a fixture's expected never carries."""
    return {k: v for k, v in obj.items() if k not in keys}


# ---------------------------------------------------------------- (a) efficiency
def efficiency_section(root: Path, out: Path) -> list:
    md = ["## 1. Efficiency check (splitcheck.effcheck)", ""]
    rules = effcheck.load_rules(str(root / "baseline" / "rules.json"))
    cwd = os.getcwd()
    os.chdir(root)  # effcheck resolves timeline['baseline'] relative to the repo root
    try:
        tl_path = root / "agent_runs" / "published_montage" / "timeline.json"
        tl = json.loads(tl_path.read_text(encoding="utf-8"))
        res = effcheck.check(tl, effcheck.load_baseline(tl.get("baseline") or effcheck.DEFAULT_BASELINE), rules)
        _write(out / "efficiency" / "published_montage.json", _dump(res))
        t = res["total"]
        md += ["### Published montage (agent_runs/published_montage/timeline.json)", "",
               f"Total: agent {_f(t['agent_s_low'])}-{_f(t['agent_s_high'])} s vs pro {_f(t['pro_s'])} s; "
               f"**ratio {_f(t['ratio_low'])}-{_f(t['ratio_high'])}**; run median segment ratio "
               f"{_f(res.get('run_median_ratio'))}.", "",
               "| segment | agent s (low-high) | pro s | ratio (low-high) | verdict | waste |",
               "|---|---|---|---|---|---|"]
        for s in res["segments"]:
            waste = "; ".join(f"{w['tag']} {_f(w.get('seconds'))}s" for w in s.get("waste", [])) or "-"
            if s["segment"] == effcheck.WHOLE_RUN:
                md.append(f"| whole_run | - | - | - | - | {_cell(waste)} |")
                continue
            md.append(f"| {s['segment']} | {_f(s['agent_s_low'])}-{_f(s['agent_s_high'])} | {_f(s['pro_s'])} | "
                      f"{_f(s['ratio_low'])}-{_f(s['ratio_high'])} | **{s['verdict']}** | {_cell(waste)} |")
        for fl in res.get("flags", []):
            md.append(f"\nFlag: {fl}")
        md.append("")

        fx = []
        for p in sorted((root / "fixtures").glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            got = effcheck.check(d, effcheck.load_baseline(d.get("baseline") or effcheck.DEFAULT_BASELINE), rules)
            exp = d.get("expected")
            ok = exp is not None and _strip(got) == _strip(exp)
            verdicts = ", ".join(f"{s['segment']}={s['verdict']}" for s in got["segments"] if "verdict" in s)
            fx.append({"fixture": p.name, "pass": ok, "has_expected": exp is not None,
                       "total_ratio": [got["total"]["ratio_low"], got["total"]["ratio_high"]],
                       "verdicts": verdicts, "got": got})
    finally:
        os.chdir(cwd)
    _write(out / "efficiency" / "fixtures.json", _dump(fx))
    npass = sum(x["pass"] for x in fx)
    md += [f"### Fixtures: {npass}/{len(fx)} PASS against their `expected`", "",
           "| fixture | result | total ratio | verdicts |", "|---|---|---|---|"]
    for x in fx:
        r = x["total_ratio"]
        md.append(f"| {x['fixture']} | {'PASS' if x['pass'] else 'FAIL'} | {_f(r[0])}-{_f(r[1])} | {x['verdicts']} |")
    md.append("")
    return md


# ---------------------------------------------------------------- (b) agent runs
def runs_section(root: Path, out: Path, eval_root: Path) -> list:
    md = ["## 2. Live agent runs (splitcheck.evaluate)", ""]
    # agent_runs/<run>/{events,server_events}.jsonl (handoff layout) and the live lab's
    # runs/live/demo-*/{events,server}.jsonl (telemetry.js server logs). Test/dev folders are skipped.
    logs = {p.parent.name: p for p in (root / "agent_runs").glob("*/events.jsonl")}
    for p in sorted((root / "runs" / "live").glob("*/events.jsonl")):
        if p.parent.name.startswith(("demo-", "live-", "foot-")) and p.parent.name not in logs:
            logs[p.parent.name] = p
    runs = sorted(logs)
    if not runs:
        return md + ["No agent_runs/<run>/events.jsonl found.", ""]
    md += ["Note: agent-06 (agent_runs) and demo-01 (runs/live) are the same run; demo-01 has the full "
           "server telemetry.", ""]
    for run in runs:
        log = logs[run]
        srv = log.parent / "server_events.jsonl"
        if not srv.exists():
            srv = log.parent / "server.jsonl"
        perc = root / "runs" / "perception" / f"{run}_perception.json"
        with contextlib.redirect_stdout(io.StringIO()):
            res = evalmod.evaluate(str(log), run_id=run, outdir=str(eval_root / f"{run}-eval"),
                                   server_log=str(srv) if srv.exists() else None,
                                   perception=str(perc) if perc.exists() else None)
        rep, eff = res["runeval"], res["efficiency"]
        summ = rep.get("summary", {})
        ms = summ.get("milestones", {}) or {}
        findings = rep.get("findings", [])
        xfind = (rep.get("server_crosscheck") or {}).get("findings", []) or []
        claims = [f for f in findings + xfind if f.get("code") in CLAIM_CODES]
        waste = sorted((f for f in findings if f.get("category") != "claim" and (f.get("cost_s") or 0) > 0),
                       key=lambda f: (-(f.get("cost_s") or 0), f.get("t_start") or 0, f.get("code")))
        prog = rep.get("progress") or {}
        perc_b = rep.get("perception") or {}
        reached = [k for k, v in ms.items() if v]
        failed = prog.get("failed_at")
        outcome = ("finished" if ms.get("game_won") else
                   f"did not finish; failed at step `{failed['step']}` (line {failed.get('line')}: {failed.get('note')})"
                   if failed else "did not finish")
        summary = {"run": run, "outcome": outcome, "ok": res["ok"], "milestones": ms,
                   "milestones_reached": reached, "score": rep.get("score"), "summary": summ,
                   "claims": claims, "top_waste": waste[:5], "progress": prog,
                   "server_coverage": (rep.get("server_crosscheck") or {}).get("coverage"),
                   "perception_validation": perc_b.get("validation"),
                   "efficiency_verdicts": {s["segment"]: s.get("verdict") for s in eff.get("segments", [])
                                           if "verdict" in s},
                   "inputs": {"server_log": srv.exists(), "perception": perc.exists()}}
        _write(out / "runs" / f"{run}.json", _dump(summary))
        sc = rep.get("score") or {}
        md += [f"### {run}", "",
               f"- Outcome: **{outcome}**",
               f"- Milestones reached: {len(reached)}/{len(ms)}"
               + (f" ({', '.join(reached)})" if reached else "") ,
               f"- Total time {_f(summ.get('total_time_s'))} s; attributed waste {_f(sc.get('attributed_waste_s'))} s; "
               f"efficiency {_f(sc.get('efficiency'), 4)}; findings {summ.get('findings')} "
               f"{json.dumps(summ.get('findings_by_category', {}), sort_keys=True)}",
               f"- Inputs: server log {'yes' if srv.exists() else 'no'}, perception {'yes' if perc.exists() else 'no'}; "
               f"full outputs in runs/{run}-eval/", ""]
        md += ["**Claims findings**", ""]
        for code in CLAIM_CODES:
            hits = [f for f in claims if f.get("code") == code]
            md.append(f"- `{code}`: {len(hits)}")
            for f in hits:
                md.append(f"  - {_cell(f.get('message'))}")
        cov = summary["server_coverage"] or {}
        for n in cov.get("notes", []):
            md.append(f"- server coverage: {n}")
        md += ["", "**Top waste findings**", ""]
        md += [f"{i}. `{f['code']}` ({f.get('category')}, {_f(f.get('cost_s'))} s): {_cell(f.get('message'))}"
               for i, f in enumerate(waste[:5], 1)] or ["- none with cost > 0"]
        if prog.get("steps"):
            md += ["", "**Progress before failure (agent vs pro, seconds from start)**", "",
                   "| step | reached | agent t | pro t | delta | note |", "|---|---|---|---|---|---|"]
            for s in prog["steps"]:
                pro = f"{_f(s.get('pro_lo'))}-{_f(s.get('pro_hi'))}" if s.get("pro_lo") != s.get("pro_hi") \
                    else _f(s.get("pro_lo"))
                dl = f"{_f(s.get('delta_lo'))}..{_f(s.get('delta_hi'))}" if s.get("delta_lo") is not None else "-"
                md.append(f"| {s['step']} | {'yes' if s.get('reached') else 'no'} | {_f(s.get('agent_t'))} | {pro} | "
                          f"{dl} | {_cell(s.get('note') or '')} |")
        val = perc_b.get("validation") or {}
        if val.get("per_field"):
            md += ["", f"**Perception validation** (model {perc_b.get('model')}, {perc_b.get('frames')} frames, "
                       f"{perc_b.get('frames_after_server_log')} after the server log ends)", "",
                   "| field | n | correct | accuracy |", "|---|---|---|---|"]
            for k, v in sorted(val["per_field"].items()):
                md.append(f"| {k} | {v.get('n')} | {v.get('correct')} | {_f(v.get('accuracy'))} |")
            if val.get("unvalidated_fields"):
                md.append(f"\nUnvalidated fields: {', '.join(val['unvalidated_fields'])}")
            pf = [f for f in perc_b.get("findings", [])]
            if pf:
                md.append("\nPerception findings: " + ", ".join(sorted({f.get('code', '?') for f in pf})))
        md.append("")
    return md


# ---------------------------------------------------------------- (c) decision tasks
def _suite_root(tmp: Path, root: Path, tasks: Path, ref: Path) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    for name, src in (("tasks", tasks), ("reference", ref), ("attempts", root / "attempts"),
                      ("splits", root / "splits")):
        os.symlink(src, tmp / name)
    return tmp


def decision_section(root: Path, out: Path) -> list:
    md = ["## 3. Decision tasks (splitcheck.check)", ""]
    costs_path = root / "splits" / "time_costs.json"
    suites = [("seed", root / "tasks", root / "reference"),
              ("generic", root / "extras" / "generic_tasks" / "tasks", root / "extras" / "generic_tasks" / "reference")]
    attempts, _ = checkmod._load_attempts(root / "attempts")
    contam = {(a["_file"], a["_index"]): a.get("contaminated") for a in attempts}
    attempted = {a["task_id"] for a in attempts}
    all_results, st_rows, task_ids = [], [], set()
    with tempfile.TemporaryDirectory() as td:
        for name, tdir, rdir in suites:
            sroot = _suite_root(Path(td) / name, root, tdir, rdir)
            costs = checkmod._load_costs(sroot, costs_path)
            results, problems = checkmod.run_attempts(sroot, costs)
            for r in results:
                r["suite"] = name
            cases = checkmod.self_test(sroot, costs)
            npass = sum(c["pass"] for c in cases)
            st_rows.append((name, npass, len(cases)))
            _write(out / "decision" / f"{name}.json",
                   _dump({"suite": name, "results": results,
                          "problems": [p for p in problems if "no tasks or reference" not in p
                                       and "no tasks file" not in p and "no reference file" not in p]}))
            _write(out / "decision" / f"self_test_{name}.json",
                   _dump({"suite": name, "passed": npass, "total": len(cases), "cases": cases}))
            all_results += results
            task_ids |= {p.stem for p in tdir.glob("*.json")}
    by_model: dict = {}
    for r in all_results:
        m = r.get("model") or "?"
        by_model.setdefault(m, {}).setdefault(r["verdict"], 0)
        by_model[m][r["verdict"]] += 1
    verdicts = sorted({r["verdict"] for r in all_results})
    md += [f"{len(all_results)} attempts checked across {len(task_ids)} tasks "
           f"({sum(1 for s in suites for _ in s[1].glob('*.json'))} task files: seed {len(list(suites[0][1].glob('*.json')))}, "
           f"generic {len(list(suites[1][1].glob('*.json')))}).", "",
           "| model | " + " | ".join(verdicts) + " | total |", "|---|" + "---|" * (len(verdicts) + 1)]
    for m, c in sorted(by_model.items()):
        md.append(f"| {m} | " + " | ".join(str(c.get(v, 0)) for v in verdicts) + f" | {sum(c.values())} |")
    md += ["", "| task | suite | verdict | reason |", "|---|---|---|---|"]
    for r in sorted(all_results, key=lambda r: (r["task_id"], r["suite"])):
        md.append(f"| {r['task_id']} | {r['suite']} | {r['verdict']} | {_cell((r.get('reason') or '')[:160])} |")
    missing = sorted(task_ids - attempted)
    md += ["", f"Tasks without an attempt: {', '.join(missing) if missing else 'none'}"]
    bad = sorted(f"{f}[{i}]" for (f, i), c in contam.items() if c)
    md += [f"Contaminated attempts: {', '.join(bad) if bad else 'none'} "
           f"({len(bad)} of {len(contam)} flagged `contaminated: true`)", ""]
    catches = [r for r in sorted(all_results, key=lambda r: (r["task_id"], r["suite"])) if r["verdict"] != "OK"][:3]
    md += ["**Example catches**", ""]
    md += [f"- {r['task_id']} ({r.get('model')}): **{r['verdict']}** -- {_cell(r.get('reason'))}"
           + (f" [miss: {r.get('miss_category')}]" if r.get("miss_category") else "") for r in catches] \
        or ["- none (every attempt OK)"]
    md += ["", "**Self-tests** (reference + alternates must be OK, broken answers must hit their expected verdict)", ""]
    md += [f"- {n}: {p}/{t} cases pass" for n, p, t in st_rows]
    md.append("")
    _write(out / "decision" / "summary.json",
           _dump({"by_model": by_model, "tasks_without_attempt": missing, "contaminated": bad,
                  "self_test": {n: {"passed": p, "total": t} for n, p, t in st_rows}}))
    return md


# ---------------------------------------------------------------- pack
REPRO = """## 4. Reproduce

```
cd code
python -m pytest -q
python -m splitcheck.pack --root .. --out ../runs/results_pack
# individual pieces:
python -m splitcheck.effcheck ../agent_runs/published_montage/timeline.json
python -m splitcheck.evaluate ../agent_runs/agent-01/events.jsonl --run-id agent-01 --outdir ../runs/agent-01-eval \\
    --server-log ../agent_runs/agent-01/server_events.jsonl --perception ../runs/perception/agent-01_perception.json
python -m splitcheck.check --root ..            # seed tasks (tasks/ + reference/)
python -m splitcheck.check --root .. --self-test
# generic tasks: a root whose tasks/ and reference/ are extras/generic_tasks/{tasks,reference}
python -m splitcheck.check --root <generic_root> --costs ../splits/time_costs.json [--self-test]
cd .. && bash make_submission.sh
```
"""


def build(root: Path, out: Path, eval_root: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    md = ["# Results pack", "",
          "Regenerated by `python -m splitcheck.pack`; deterministic, stdlib only, no LLM calls "
          "(perception results are read from the cached runs/perception/*.json).", ""]
    md += efficiency_section(root, out)
    md += runs_section(root, out, eval_root)
    md += decision_section(root, out)
    md += [REPRO]
    _write(out / "RESULTS.md", "\n".join(md))


def _all_files(d: Path) -> list:
    return sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file())


def determinism_check(root: Path) -> dict:
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        for t in (a, b):
            build(root, Path(t) / "pack", Path(t) / "pack" / "_eval")
        fa, fb = _all_files(Path(a)), _all_files(Path(b))
        common = sorted(set(fa) & set(fb))
        _, mismatch, errors = filecmp.cmpfiles(a, b, common, shallow=False)
        return {"files": len(common), "identical": not mismatch and not errors and fa == fb,
                "mismatched": sorted(mismatch), "errors": sorted(errors),
                "only_in_one": sorted(set(fa) ^ set(fb))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m splitcheck.pack", description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="..")
    ap.add_argument("--out", default=None, help="default <root>/runs/results_pack")
    ap.add_argument("--eval-root", default=None, help="where <run>-eval folders go (default <root>/runs)")
    ap.add_argument("--no-determinism-check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    out = Path(a.out).resolve() if a.out else root / "runs" / "results_pack"
    eval_root = Path(a.eval_root).resolve() if a.eval_root else root / "runs"
    build(root, out, eval_root)
    if not a.no_determinism_check:
        det = determinism_check(root)
        _write(out / "determinism.json", _dump(det))
        line = (f"Determinism: two packs built into separate temp dirs; {det['files']} files compared with "
                f"filecmp (shallow=False): **{'all byte-identical' if det['identical'] else 'DIFFERENCES'}**")
        if not det["identical"]:
            line += f"; mismatched {det['mismatched']}, errors {det['errors']}, only in one {det['only_in_one']}"
        with open(out / "RESULTS.md", "a", encoding="utf-8", newline="\n") as f:
            f.write("\n" + line + "\n")
        print(line)
    print(f"wrote {out / 'RESULTS.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
