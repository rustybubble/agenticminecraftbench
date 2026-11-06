import json, os, subprocess
from splitcheck import perception as P


def test_sample_times_dense_and_snapped():
    t = P.sample_times(20.0, 2.0, 4.0, dense_times=[5.0], dense_every=0.5, dense_window=1.0)
    assert t == sorted(set(t))
    assert {4.0, 4.5, 5.0, 5.5, 6.0}.issubset(set(t))
    assert 2.0 in t and 20.0 in t and 7.0 not in t or 8.0 in t
    assert all(abs(x * 4 - round(x * 4)) < 1e-6 for x in t)  # on the 4 fps frame grid


def test_sample_times_deterministic_and_clipped():
    a = P.sample_times(10.0, 2.0, 4.5, dense_times=[0.2, 9.9])
    assert a == P.sample_times(10.0, 2.0, 4.5, dense_times=[9.9, 0.2])
    assert min(a) >= 0.0 and max(a) <= 10.0


def test_frames_index_mode(tmp_path):
    fd = tmp_path / "frames"; fd.mkdir()
    idx = []
    for i in range(12):
        f = fd / f"f{i:03d}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x{(i*20)%256:02x}2040:s=64x48",
                        "-frames:v", "1", str(f)], check=True)
        idx.append({"file": f"frames/{f.name}", "run_t": i * 1.0})
    ip = tmp_path / "frames_index.json"; ip.write_text(json.dumps(idx))
    be = P.make_backend("fake")
    res = P.run_perception("unused.mp4", be, every_s=4.0, cache_dir=str(tmp_path / "cache"), frames_index=str(ip))
    ts = [r["run_t"] for r in res["frames"]]
    assert ts == [0.0, 4.0, 8.0]
    assert res["alignment"]["offset_s"] == 0.0 and "frames_index" in res["alignment"]["method"]
