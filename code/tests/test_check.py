import csv
import json
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

try:
    from splitcheck import answers as _answers  # noqa: F401
    from splitcheck import sim as _sim  # noqa: F401
    HAVE_DEPS = True
except ImportError:  # other builders' modules not present yet
    HAVE_DEPS = False

from splitcheck import check

needs_deps = pytest.mark.skipif(not HAVE_DEPS, reason="splitcheck.answers / splitcheck.sim not importable yet")


@pytest.fixture
def root(tmp_path):
    dst = tmp_path / "repo"
    shutil.copytree(FIXTURES, dst)
    return dst


def _rows(root):
    with open(root / "runs" / "results.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_import_has_no_hard_dependency():
    # check.py must import even when answers/sim are missing (lazy imports)
    assert callable(check.main) and callable(check.self_test) and callable(check.check_task)


@needs_deps
def test_self_test_passes_on_fixtures(root):
    cases = check.self_test(root)
    failed = [c for c in cases if not c["pass"]]
    assert cases and not failed, failed
    kinds = {(c["task_id"], c["case"]) for c in cases}
    for tid in ("FX1_eyes_needed", "FX2_nether_exit_coords", "FX3_nether_entry_plan"):
        assert (tid, "alternate") in kinds and (tid, "broken") in kinds


@needs_deps
def test_self_test_cli_exit_codes(root, capsys):
    assert check.main(["--root", str(root), "--self-test"]) == 0
    assert "FAIL" not in capsys.readouterr().out
    # corrupt one broken case: expected OK for a wrong answer -> must FAIL and exit non-zero
    p = root / "reference" / "FX1_eyes_needed.json"
    ref = json.loads(p.read_text())
    ref["broken"][0]["expected_verdict"] = "OK"
    p.write_text(json.dumps(ref))
    assert check.main(["--root", str(root), "--self-test"]) == 1
    assert "FAIL" in capsys.readouterr().out


@needs_deps
def test_main_writes_csv_and_outputs(root):
    assert check.main(["--root", str(root)]) == 0
    rows = _rows(root)
    assert list(rows[0].keys()) == check.CSV_COLUMNS
    by = {r["task_id"]: r for r in rows}
    assert set(by) == {"FX1_eyes_needed", "FX2_nether_exit_coords", "FX3_nether_entry_plan"}
    assert by["FX1_eyes_needed"]["verdict"] == "OK"
    assert by["FX2_nether_exit_coords"]["verdict"] == "WRONG"
    assert by["FX2_nether_exit_coords"]["miss_category"] == "no_nether_shortcut"
    assert by["FX2_nether_exit_coords"]["techniques_missed"] == "nether_travel_8to1"
    assert by["FX3_nether_entry_plan"]["verdict"] == "OK"  # prose + fenced JSON parsed
    assert by["FX3_nether_entry_plan"]["time_s"] and by["FX3_nether_entry_plan"]["pro_time_s"]
    for r in rows:
        assert r["reason"]
        out = json.loads((root / "runs" / "checker_output" / f"{r['task_id']}.json").read_text())
        assert out["attempts"][0]["verdict"] == r["verdict"]


@needs_deps
def test_deterministic(root):
    check.main(["--root", str(root)])
    a = (root / "runs" / "results.csv").read_text()
    check.main(["--root", str(root)])
    assert (root / "runs" / "results.csv").read_text() == a


@needs_deps
def test_check_task_unparseable_is_wrong(root):
    task = json.loads((root / "tasks" / "FX1_eyes_needed.json").read_text())
    ref = json.loads((root / "reference" / "FX1_eyes_needed.json").read_text())
    r = check.check_task(task, ref, "I think nine eyes.")
    assert r["verdict"] == "WRONG" and r["reason"]
    assert r["miss_category"] == "ignores_information"


@needs_deps
def test_plan_illegal_reports_techniques_missed(root):
    task = json.loads((root / "tasks" / "FX3_nether_entry_plan.json").read_text())
    ref = json.loads((root / "reference" / "FX3_nether_entry_plan.json").read_text())
    raw = json.dumps({"actions": [{"action": "travel", "to": "portal_site"}, {"action": "enter_portal"}]})
    r = check.check_task(task, ref, raw)
    assert r["verdict"] == "ILLEGAL" and r["reason"]
    assert r["miss_category"] == "brute_force_over_trick"


def test_missing_dirs_do_not_crash(tmp_path, capsys):
    rc = check.main(["--root", str(tmp_path)])
    out = capsys.readouterr()
    if not HAVE_DEPS:
        assert rc == 2 and "could not be imported" in out.err
    else:
        assert rc == 0
        assert "missing directory" in out.out
        assert _rows(tmp_path) == []
