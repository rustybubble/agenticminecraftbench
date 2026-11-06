import json
import os
import shutil
import subprocess

import pytest

from splitcheck import perception as P

FFMPEG = P.FFMPEG
pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") or os.path.exists(FFMPEG)),
                                reason="ffmpeg not available")


@pytest.fixture(scope="module")
def tiny_video(tmp_path_factory):
    d = tmp_path_factory.mktemp("vid")
    out = str(d / "tiny.mp4")
    # testsrc: bright, and every frame differs (moving counter) so cache keys are distinct
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc=s=1280x720:r=5:d=5", "-pix_fmt", "yuv420p", out],
                   check=True, capture_output=True)
    return out


def _gray_mean(png, x, y, w, h):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", png, "-vf", f"crop={w}:{h}:{x}:{y}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], check=True,
                         capture_output=True).stdout
    return sum(raw) / len(raw)


def test_extract_frames_crops_overlay(tiny_video, tmp_path):
    frames = P.extract_frames(tiny_video, every_s=2.0, outdir=str(tmp_path))
    assert [f["video_t"] for f in frames] == [0.0, 2.0, 4.0]
    for f in frames:
        info = P.probe(f["frame_path"])
        assert (info["width"], info["height"]) == (1280, 610) == (P.SCENE_W, P.SCENE_H)
    png = frames[0]["frame_path"]
    for x, y, w, h in P.MASKS:          # overlay boxes inside the band are blacked out
        assert _gray_mean(png, x, y, w, h) < 20
    assert _gray_mean(png, 100, 200, 400, 200) > 60    # scene itself untouched


def test_hud_crop_is_separate_and_tiny(tiny_video, tmp_path):
    p = P.crop_hud_clock(tiny_video, 1.0, str(tmp_path / "hud.png"))
    info = P.probe(p)
    assert (info["width"], info["height"]) == (P.HUD_BAR[2], P.HUD_BAR[3])
    assert P.HUD_BAR[1] >= P.SCENE_Y1   # never overlaps the scene band sent to the model


def test_cache_replay_zero_calls_and_identical(tiny_video, tmp_path):
    cache = str(tmp_path / "cache")
    b1 = P.FakeBackend()
    r1 = P.run_perception(tiny_video, b1, every_s=1.0, cache_dir=cache, offset_s=10.0)
    assert b1.calls == r1["stats"]["n_frames"] == 5
    assert r1["stats"]["cache_hits"] == 0
    b2 = P.FakeBackend()
    r2 = P.run_perception(tiny_video, b2, every_s=1.0, cache_dir=cache, offset_s=10.0)
    assert b2.calls == 0 and r2["stats"]["backend_calls"] == 0
    assert r2["stats"]["cache_hits"] == 5
    strip = lambda r: [(f["video_t"], f["run_t"], f["frame_sha"], f["obs"], f["cache_keys"]) for f in r["frames"]]
    assert strip(r1) == strip(r2)
    # cache entries carry provenance
    key = r1["frames"][0]["cache_keys"][0]
    entry = json.load(open(os.path.join(cache, key[:2], key + ".json")))
    for k in ("model", "prompt", "prompt_sha", "schema_sha", "created_utc", "frame_sha", "parsed"):
        assert k in entry
    assert entry["label"] == "perception-assisted"


def test_cache_key_depends_on_all_inputs():
    base = P.cache_key(b"img", "p", "m", {"a": 1})
    assert base == P.cache_key(b"img", "p", "m", {"a": 1})
    assert len({base, P.cache_key(b"img2", "p", "m", {"a": 1}), P.cache_key(b"img", "q", "m", {"a": 1}),
                P.cache_key(b"img", "p", "m2", {"a": 1}), P.cache_key(b"img", "p", "m", {"a": 2}),
                P.cache_key(b"img", "p", "m", {"a": 1}, vote=1)}) == 6


def test_cache_key_separates_backends_and_effort(tmp_path):
    # regression: FakeBackend with the codex model id used to replay real codex cache entries
    base = P.cache_key(b"img", "p", "m", {"a": 1})
    k = {P.cache_key(b"img", "p", "m", {"a": 1}, params=pr) for pr in
         ({"backend": "fake"}, {"backend": "codex", "effort": "low", "cli_version": "x"},
          {"backend": "codex", "effort": "high", "cli_version": "x"},
          {"backend": "codex", "effort": "low", "cli_version": "y"})}
    assert len(k) == 4 and base not in k
    assert P.backend_params(P.FakeBackend("gpt-6-astra")) == {"backend": "fake"}
    cb = P.CodexBackend("gpt-6-astra", effort="high")
    P._CODEX_VERSION = "codex-cli test"
    assert P.backend_params(cb) == {"backend": "codex", "effort": "high", "cli_version": "codex-cli test"}


class _SlowReverse(P.FakeBackend):
    """Finishes later frames first, to prove output order does not depend on thread timing."""
    def __call__(self, image_path, prompt, schema):
        import time
        n = int(os.path.basename(image_path).split("_")[1][:8])
        time.sleep(max(0.0, 0.05 - n / 1e6 * 0.01))
        return super().__call__(image_path, prompt, schema)


def test_deterministic_ordering_and_alignment(tiny_video, tmp_path):
    frames = P.extract_frames(tiny_video, every_s=1.0, outdir=str(tmp_path / "f"))
    recs = P.observe(list(reversed(frames)), _SlowReverse(), cache_dir=str(tmp_path / "c"), offset_s=48.56)
    assert [r["video_t"] for r in recs] == sorted(r["video_t"] for r in recs)
    assert [r["run_t"] for r in recs] == [round(t + 48.56, 3) for t in (0, 1, 2, 3, 4)]
    for r in recs:
        assert set(r["obs"]) == set(P.OBS_SCHEMA["required"])
        assert r["label"] == "perception-assisted"


def test_votes_majority_and_vote_keys(tiny_video, tmp_path):
    frames = P.extract_frames(tiny_video, every_s=4.0, outdir=str(tmp_path / "f"))
    b = P.FakeBackend()
    recs = P.observe(frames, b, cache_dir=str(tmp_path / "c"), votes=3)
    assert b.calls == 3 * len(frames)
    assert all(r["votes"] == 3 and len(set(r["cache_keys"])) == 3 for r in recs)


def test_normalize_obs_coerces_bad_values():
    o = P.normalize_obs({"obsidian_frame": "maybe", "confidence": 7, "player_in_water": "yes",
                         "player_activity": "dancing", "portal_lit": 1})
    assert o["obsidian_frame"] == "none" and o["confidence"] == 1.0
    assert o["player_in_water"] is None and o["player_activity"] == "unknown" and o["portal_lit"] is False


def test_known_alignment_agent01():
    assert P.read_run_time("/x/agent-01-chests.mp4", 0.0) == 48.56
    assert P.read_run_time("/x/other.mp4", 3.0) is None
    assert P.read_run_time("/x/other.mp4", 3.0, offset_s=1.5) == 4.5


def test_obs_schema_is_strict():
    s = P.OBS_SCHEMA
    assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])


def test_cli_fake(tiny_video, tmp_path):
    out = tmp_path / "perception.json"
    rc = P.main([tiny_video, "--out", str(out), "--backend", "fake", "--every", "2",
                 "--offset", "5", "--cache-dir", str(tmp_path / "c")])
    assert rc == 0
    j = json.loads(out.read_text())
    assert j["label"] == "perception-assisted" and j["backend"] == "fake"
    assert [f["run_t"] for f in j["frames"]] == [5.0, 7.0, 9.0]
    assert j["crop"]["size"] == [1280, 610]


def test_identical_frames_one_backend_call(tmp_path):
    src = tmp_path / "a.png"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=64x64",
                    "-frames:v", "1", str(src)], check=True, capture_output=True)
    frames = []
    for i in range(6):
        p = tmp_path / f"scene_{i:08d}ms.png"
        shutil.copyfile(src, p)
        frames.append({"frame_path": str(p), "video_t": float(i)})
    b = P.FakeBackend()
    recs = P.observe(frames, b, cache_dir=str(tmp_path / "c"))
    assert b.calls == 1 and len(recs) == 6
