#!/usr/bin/env bash
# Build ../agenticminecraftbench_submission.zip: tests, results pack, then zip of
# git-tracked + untracked-not-ignored files (new modules not yet committed) + runs/ outputs + code/.perception_cache (if present).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ZIP="$(cd "$ROOT/.." && pwd)/herobrine_submission.zip"
cd "$ROOT/code"
echo "== pytest"
# tests/fixtures/runs/ is gitignored in this repo, so the fixture-output suite (EXPECTED.md vs disk)
# cannot run from a fresh clone; skip exactly those two modules and run everything else.
python3 -m pytest -q --ignore=tests/test_fixture_runs.py --ignore=tests/test_v4export.py --ignore=tests/test_v4_fixer.py \
  || { echo "tests failed; aborting" >&2; exit 1; }
echo "== results pack"
python3 -m splitcheck.pack --root .. --out ../runs/results_pack
cd "$ROOT"
echo "== zip"
python3 - "$ROOT" "$ZIP" <<'PY'
import os, subprocess, sys, zipfile
root, zpath = sys.argv[1], sys.argv[2]
LIMIT = 50 * 1024 * 1024
SKIP = {"node_modules", "__pycache__", ".pytest_cache", ".git", "frames", "frames-clean", "clipframes", "demo-01_frames", "clip-portal", "clip-resources"}  # frames: re-extracted deterministically from the mp4
files = set(subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root, check=True,
                           capture_output=True, text=True).stdout.split("\0")) - {""}
for extra in ("runs", "code/.perception_cache"):
    for dp, dns, fns in os.walk(os.path.join(root, extra)):
        dns[:] = [d for d in dns if d not in SKIP]
        files |= {os.path.relpath(os.path.join(dp, f), root) for f in fns}
excluded, kept, total = [], [], 0
for rel in sorted(files):
    p = os.path.join(root, rel)
    if any(part in SKIP for part in rel.split(os.sep)):
        excluded.append((rel, "excluded dir")); continue
    if not os.path.isfile(p):
        excluded.append((rel, "missing on disk")); continue
    sz = os.path.getsize(p)
    if sz > LIMIT:
        excluded.append((rel, f"{sz/1048576:.1f} MB > 50 MB")); continue
    kept.append(rel); total += sz
if os.path.exists(zpath):
    os.remove(zpath)
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for rel in kept:
        z.write(os.path.join(root, rel), os.path.join("agenticminecraftbench", rel))
print(f"excluded {len(excluded)} file(s):")
for rel, why in excluded:
    print(f"  {rel}  ({why})")
print(f"included {len(kept)} files, {total/1048576:.1f} MB uncompressed")
print(f"zip: {zpath}  ({os.path.getsize(zpath)/1048576:.1f} MB)")
PY
