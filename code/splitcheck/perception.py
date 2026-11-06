"""AI perception layer: what is VISIBLE in a footage frame, nothing else.

Design rules (binding):
  * The model is used ONLY for perception (fields in OBS_SCHEMA). Every verdict built on top of
    these observations is a deterministic rule elsewhere (detectors_perception.py).
  * The burned-in overlay is removed before any frame reaches the model: the scene is cropped to
    y 52..662 (drops the top banner and the bottom HUD bar) and the two overlay boxes that sit
    inside that band are filled black: the "server clock" box (top right) and the event callout
    strip (e.g. "FAIL build_portal 3s", bottom left, can span the full width). So the model can
    never read the log's answers off the frame.
  * Every call is cached on disk, keyed by sha256(frame bytes + prompt + model + schema [+ vote]),
    so a rerun replays byte-identical observations with zero backend calls. Each cache entry records
    the model id, prompt, prompt sha, schema sha and UTC timestamp.
  * Output is labelled "perception-assisted".

Alignment (video_t -> run_t)
  The bottom HUD's "t+<N>s" is the VIDEO clock (overlay.py writes t = frame_index / fps), not the
  run clock, and the "server clock" box freezes at the last poller sample (18:46:27Z for agent-01,
  the poller stopped at run t=44.3 s). Neither gives run time directly, so alignment is a
  deterministic offset: run_t = video_t + offset_s. For agent-01 the offset is derived from the
  "FAIL build_portal" callout: overlay.py shows a callout while -0.1 <= video_t - off <= 3.5 and it
  is visible on frames 0..13 and gone on frame 14 at 4.5224 fps (5653/1250), so the event sits at
  video_t in (-0.625, -0.404]; the agent log puts that skill_result at run t=48.045 s, so
  offset_s = 48.045 + 0.51 = 48.56 (+/-0.11 s). The whole clip therefore shows the post-build
  linger at the portal site (run t 48.6 .. ~143). Pass --offset for other clips.
  read_overlay_clock() optionally asks the backend to read the HUD's t+N from a tiny crop of just
  that bar (never sent together with the scene); it is a consistency check that the clip was not
  trimmed (t+N should equal floor(video_t)), cached like every other call.

CLI
  python -m splitcheck.perception <video> --run-log <events.jsonl> --out perception.json
         [--every 2] [--votes 1] [--backend codex|fake] [--offset S] [--model M] [--check-clock]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from collections import Counter

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
DEFAULT_MODEL = "gpt-6-astra"
DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".perception_cache")
LABEL = "perception-assisted"

# ---- overlay geometry (1280x720 overlay.py output) ---------------------------------------
SCENE_Y0, SCENE_Y1 = 52, 662                     # keep rows [52, 662): drops top banner + HUD bar
SCENE_W, SCENE_H = 1280, SCENE_Y1 - SCENE_Y0     # 1280 x 610
# boxes inside the scene band, in CROPPED coordinates (x, y, w, h), filled black
MASKS = [
    (880, 0, 400, 36),      # "server clock HH:MM:SSZ" box (orig y ~50..86, x >= 894)
    (0, 574, 1280, 36),     # event callout strip (orig y ~626..662, width varies with text)
]
HUD_BAR = (0, 666, 220, 40)  # x, y, w, h of the "t+<N>s" start of the bottom HUD bar (orig coords)

# Deterministic alignments for known clips (see module docstring for the derivation).
KNOWN_ALIGNMENTS = {
    "agent-01-chests.mp4": {
        "offset_s": 48.56, "tolerance_s": 0.11,
        "method": "callout 'FAIL build_portal' visible frames 0..13 at 4.5224 fps; overlay shows a "
                  "callout for video_t-off in [-0.1,3.5]; build_portal skill_result at run t=48.045 s",
    },
}

ACTIVITIES = ["walking", "standing", "swimming", "placing_or_mining", "unknown"]

# JSON schema for `codex exec --output-schema` (strict structured output: every property
# required, no extra properties; nullable via a type list).
OBS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "obsidian_frame": {"type": "string", "enum": ["none", "partial", "complete"]},
        "portal_lit": {"type": "boolean"},
        "chest_visible": {"type": "boolean"},
        "village_visible": {"type": "boolean"},
        "lava_visible": {"type": "boolean"},
        "water_visible": {"type": "boolean"},
        "player_visible": {"type": "boolean"},
        "player_in_water": {"type": ["boolean", "null"]},
        "player_activity": {"type": "string", "enum": ACTIVITIES},
        "confidence": {"type": "number"},
    },
    "required": ["obsidian_frame", "portal_lit", "chest_visible", "village_visible", "lava_visible",
                 "water_visible", "player_visible", "player_in_water", "player_activity", "confidence"],
}

CLOCK_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"t_plus_s": {"type": ["number", "null"]}},
    "required": ["t_plus_s"],
}

OBS_PROMPT = """You are looking at ONE frame rendered from a Minecraft Java 1.16 world by prismarine-viewer.
The camera is third-person, looking down at a single player character (the bot) from above and behind.
Some rectangular areas may be solid black; they are masked out, ignore them.
Report ONLY what is visible in this image. Do not guess about anything outside the frame.

Fields:
- obsidian_frame: "complete" if a full rectangular nether-portal frame of obsidian (dark purple-black blocks) is visible;
  "partial" if some obsidian blocks forming part of a frame / ruined portal are visible but the rectangle is incomplete;
  "none" if no obsidian is visible.
- portal_lit: true only if purple swirling nether-portal blocks fill a frame.
- chest_visible: a chest block (brown wooden box with a latch) is visible.
- village_visible: village buildings (houses, paths, bells, farms built by villagers) are visible.
- lava_visible: lava (bright orange liquid) is visible anywhere.
- water_visible: water (blue liquid) is visible anywhere.
- player_visible: the player character (bot) is visible.
- player_in_water: if the player is visible, true when the player is standing or swimming in water, else false; null if the player is not visible.
- player_activity: what the player appears to be doing: walking, standing, swimming, placing_or_mining, or unknown.
- confidence: your overall confidence in these answers, 0.0 to 1.0.

Reply with the JSON object only."""

CLOCK_PROMPT = """This is a small crop of a heads-up text bar. It starts with a time stamp of the form t+<N>s
(for example t+07s). Report N as a number in t_plus_s. If no such stamp is readable, use null.
Reply with the JSON object only."""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_text(s: str) -> str:
    return _sha(s.encode("utf-8"))


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------- video helpers
def probe(video: str) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", video],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st = j["streams"][0]
    num, _, den = st.get("r_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    return {"width": int(st["width"]), "height": int(st["height"]), "fps": fps,
            "duration": float(j.get("format", {}).get("duration") or 0.0)}


def scene_filter(width: int = 1280, height: int = 720) -> str:
    """ffmpeg -vf chain: scale to 1280x720 if needed, crop the scene band, black out overlay boxes."""
    parts = []
    if (width, height) != (1280, 720):
        parts.append("scale=1280:720")
    parts.append(f"crop={SCENE_W}:{SCENE_H}:0:{SCENE_Y0}")
    for x, y, w, h in MASKS:
        parts.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black:t=fill")
    return ",".join(parts)


def _grab(video: str, t: float, vf: str, out_png: str) -> None:
    subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                    "-vf", vf, out_png], check=True, capture_output=True)


def sample_times(last: float, every_s: float, fps: float, dense_times=None,
                 dense_every: float = 0.5, dense_window: float = 10.0) -> list[float]:
    """Deterministic sampling grid: every `every_s` s, plus every `dense_every` s within
    +-`dense_window` s of each time in `dense_times` (adaptive sampling around logged events).
    Times are snapped to the footage's frame grid (1/fps) and de-duplicated."""
    step = 1.0 / max(fps, 1.0)
    snap = lambda t: round(round(t / step) * step, 3)
    times, k = set(), 0
    while k * every_s <= last + 1e-9:
        times.add(snap(k * every_s)); k += 1
    for c in sorted(dense_times or []):
        t = max(0.0, c - dense_window)
        while t <= min(last, c + dense_window) + 1e-9:
            times.add(snap(t)); t += dense_every
    return sorted(t for t in times if 0.0 <= t <= last + 1e-9)


def event_times(run_log: str) -> list[float]:
    """Run times (s) of logged events worth dense sampling: failed actions, build/loot/craft/light
    skill results, milestones (dimension changes, deaths, splits). Pure function of the log."""
    from .timeline import load_timeline
    tl = load_timeline(run_log)
    ts = set()
    for smp in tl.samples:
        a = (smp.action or "")
        if smp.action_failed or any(k in a for k in ("build", "portal", "loot", "craft", "light", "place", "mine")):
            ts.add(round(smp.t, 3))
    for ev in tl.events:
        if ev.get("t") is not None and ev.get("type") != "start":
            ts.add(round(float(ev["t"]), 3))
    return sorted(ts)


def extract_frames(video: str, every_s: float = 2.0, outdir: str | None = None,
                   dense_times=None, dense_every: float = 0.5, dense_window: float = 10.0) -> list[dict]:
    """Overlay-free scene frames every `every_s` seconds (denser around `dense_times`, video clock):
    [{frame_path, video_t}] sorted by video_t."""
    info = probe(video)
    outdir = outdir or tempfile.mkdtemp(prefix="perception-frames-")
    os.makedirs(outdir, exist_ok=True)
    vf = scene_filter(info["width"], info["height"])
    last = max(0.0, info["duration"] - 0.5 / max(info["fps"], 1.0))
    times = sample_times(last, every_s, info["fps"], dense_times, dense_every, dense_window)
    frames = []
    for t in times:
        p = os.path.join(outdir, f"scene_{int(round(t * 1000)):08d}ms.png")
        _grab(video, t, vf, p)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            frames.append({"frame_path": p, "video_t": t})
    return frames


def crop_hud_clock(video: str, video_t: float, out_png: str) -> str:
    """Tiny crop of ONLY the start of the bottom HUD bar (t+<N>s). Never combined with the scene."""
    x, y, w, h = HUD_BAR
    info = probe(video)
    pre = "scale=1280:720," if (info["width"], info["height"]) != (1280, 720) else ""
    _grab(video, video_t, f"{pre}crop={w}:{h}:{x}:{y}", out_png)
    return out_png


# ---------------------------------------------------------------- backends
class CodexBackend:
    """`codex exec` with an image + strict output schema, run from an empty temp dir, read-only."""
    name = "codex"

    def __init__(self, model: str = DEFAULT_MODEL, effort: str | None = "low", timeout_s: int = 240):
        self.model, self.effort, self.timeout_s = model, effort, timeout_s
        self.calls = 0

    def params(self) -> dict:
        """Every model-call parameter besides frame/prompt/model/schema; part of the cache key."""
        return {"backend": self.name, "effort": self.effort, "cli_version": _codex_version()}

    def __call__(self, image_path: str, prompt: str, schema: dict) -> dict:
        self.calls += 1
        work = tempfile.mkdtemp(prefix="perception-cwd-")      # empty cwd: no repo, no AGENTS.md
        side = tempfile.mkdtemp(prefix="perception-io-")       # schema + image copy live elsewhere
        try:
            schema_path = os.path.join(side, "schema.json")
            with open(schema_path, "w") as f:
                json.dump(schema, f)
            img = os.path.join(side, "frame" + os.path.splitext(image_path)[1])
            shutil.copyfile(image_path, img)
            cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--json",
                   "--image", img, "--output-schema", schema_path]
            if self.model:
                cmd += ["-m", self.model]
            if self.effort:
                cmd += ["-c", f'model_reasoning_effort="{self.effort}"']
            cmd.append("-")
            p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=work,
                               timeout=self.timeout_s)
        finally:
            shutil.rmtree(work, ignore_errors=True)
            shutil.rmtree(side, ignore_errors=True)
        messages, tools, usage = [], [], None
        for line in p.stdout.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "turn.completed":
                usage = ev.get("usage")
            item = ev.get("item") or {}
            if ev.get("type") == "item.completed":
                if item.get("type") == "agent_message":
                    messages.append(item.get("text", ""))
                elif item.get("type") != "reasoning":
                    tools.append(item.get("type"))
        if not messages:
            raise RuntimeError(f"codex returned no message (exit {p.returncode}): {p.stderr[-400:]}")
        return {"parsed": _parse_json(messages[0]), "raw": messages[0], "usage": usage,
                "tool_events": tools, "exit_code": p.returncode}


class ClaudeBackend:
    """`claude -p` (Claude Code CLI, subscription login) reading ONE copied frame with the Read tool only,
    from an empty temp dir. The image is the only file in that dir; the JSON schema is in the prompt."""
    name = "claude"

    def __init__(self, model: str = "claude-sonnet-5-5", effort: str | None = None, timeout_s: int = 240):
        self.model, self.effort, self.timeout_s = model, effort, timeout_s
        self.calls = 0

    def params(self) -> dict:
        try:
            v = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            v = "unknown"
        return {"backend": self.name, "effort": self.effort, "cli_version": v}

    def __call__(self, image_path: str, prompt: str, schema: dict) -> dict:
        self.calls += 1
        work = tempfile.mkdtemp(prefix="perception-cwd-")
        try:
            img = os.path.join(work, "frame" + os.path.splitext(image_path)[1])
            shutil.copyfile(image_path, img)
            full = (f"Read the image file at {img} (and nothing else). {prompt}\n"
                    f"Reply with ONLY one JSON object matching this JSON schema, no prose:\n{json.dumps(schema)}")
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            cmd = ["claude", "-p", full, "--allowedTools", "Read", "--model", self.model,
                   "--output-format", "json"]
            p = subprocess.run(cmd, capture_output=True, text=True, cwd=work, env=env, timeout=self.timeout_s)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        try:
            env_out = json.loads(p.stdout)
            text = env_out.get("result", "") if isinstance(env_out, dict) else ""
            usage = env_out.get("usage") if isinstance(env_out, dict) else None
        except json.JSONDecodeError:
            text, usage = p.stdout, None
        if not text:
            raise RuntimeError(f"claude returned no message (exit {p.returncode}): {p.stderr[-400:]}")
        return {"parsed": _parse_json(text), "raw": text, "usage": usage, "tool_events": ["Read(frame)"],
                "exit_code": p.returncode}


class FakeBackend:
    """Deterministic, offline. Observations are a pure function of the image bytes."""
    name = "fake"

    def __init__(self, model: str = "fake-perception-v1"):
        self.model = model
        self.calls = 0

    def params(self) -> dict:
        return {"backend": self.name}

    def __call__(self, image_path: str, prompt: str, schema: dict) -> dict:
        self.calls += 1
        h = _sha(open(image_path, "rb").read())
        bits = [int(c, 16) for c in h[:12]]
        if "t_plus_s" in schema.get("properties", {}):
            parsed = {"t_plus_s": None}
        else:
            parsed = {
                "obsidian_frame": ["none", "partial", "complete"][bits[0] % 3],
                "portal_lit": bits[1] % 5 == 0,
                "chest_visible": bits[2] % 2 == 0,
                "village_visible": bits[3] % 2 == 0,
                "lava_visible": bits[4] % 2 == 0,
                "water_visible": bits[5] % 2 == 0,
                "player_visible": bits[6] % 4 != 0,
                "player_in_water": None if bits[6] % 4 == 0 else bits[7] % 2 == 0,
                "player_activity": ACTIVITIES[bits[8] % len(ACTIVITIES)],
                "confidence": round(0.5 + bits[9] / 32.0, 3),
            }
        return {"parsed": parsed, "raw": json.dumps(parsed), "usage": None, "tool_events": []}


def make_backend(name: str, model: str | None = None, effort: str | None = "low"):
    if name == "fake":
        return FakeBackend(model or "fake-perception-v1")
    if name == "codex":
        return CodexBackend(model or DEFAULT_MODEL, effort=effort)
    if name == "claude":
        return ClaudeBackend(model or "claude-sonnet-5-5", effort=None)
    raise ValueError(f"unknown backend {name!r}")


def _parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    start, end = t.find("{"), t.rfind("}")
    return json.loads(t[start:end + 1])


def normalize_obs(o: dict) -> dict:
    """Coerce to OBS_SCHEMA types; unknown/invalid values become conservative defaults."""
    def b(v):
        return bool(v) if isinstance(v, bool) else False
    of = o.get("obsidian_frame")
    act = o.get("player_activity")
    piw = o.get("player_in_water")
    try:
        conf = min(1.0, max(0.0, float(o.get("confidence"))))
    except (TypeError, ValueError):
        conf = 0.0
    return {
        "obsidian_frame": of if of in ("none", "partial", "complete") else "none",
        "portal_lit": b(o.get("portal_lit")),
        "chest_visible": b(o.get("chest_visible")),
        "village_visible": b(o.get("village_visible")),
        "lava_visible": b(o.get("lava_visible")),
        "water_visible": b(o.get("water_visible")),
        "player_visible": b(o.get("player_visible")),
        "player_in_water": piw if isinstance(piw, bool) else None,
        "player_activity": act if act in ACTIVITIES else "unknown",
        "confidence": round(conf, 3),
    }


# ---------------------------------------------------------------- cache
_KEY_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()


_CODEX_VERSION = None


def _codex_version() -> str:
    """`codex --version` (memoised); "unknown" if the CLI is missing."""
    global _CODEX_VERSION
    if _CODEX_VERSION is None:
        try:
            p = subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=30)
            _CODEX_VERSION = (p.stdout or p.stderr).strip() or "unknown"
        except Exception:
            _CODEX_VERSION = "unknown"
    return _CODEX_VERSION


def backend_params(backend) -> dict:
    fn = getattr(backend, "params", None)
    return fn() if callable(fn) else {"backend": getattr(backend, "name", type(backend).__name__)}


def cache_key(frame_bytes: bytes, prompt: str, model: str, schema: dict, vote: int = 0,
              params: dict | None = None) -> str:
    """sha256 over frame bytes, prompt, model, schema, vote and the backend's call parameters
    (backend name, reasoning effort, CLI version), so different configurations never replay
    each other's observations."""
    h = hashlib.sha256()
    h.update(frame_bytes)
    h.update(b"\0prompt\0" + prompt.encode("utf-8"))
    h.update(b"\0model\0" + model.encode("utf-8"))
    h.update(b"\0schema\0" + _canon(schema).encode("utf-8"))
    if vote:
        h.update(f"\0vote\0{vote}".encode())
    if params is not None:
        h.update(b"\0params\0" + _canon(params).encode("utf-8"))
    return h.hexdigest()


def cached_call(backend, image_path: str, prompt: str, schema: dict, cache_dir: str, vote: int = 0) -> dict:
    """Return {parsed, cache_hit, key, entry}. A cache hit makes no backend call."""
    data = open(image_path, "rb").read()
    key = cache_key(data, prompt, backend.model, schema, vote, backend_params(backend))
    with _LOCKS_GUARD:   # identical frames in one run (static scenes) -> one backend call, not N
        lock = _KEY_LOCKS.setdefault(key, threading.Lock())
    with lock:
        return _cached_call_locked(backend, image_path, prompt, schema, cache_dir, vote, data, key)


def _cached_call_locked(backend, image_path, prompt, schema, cache_dir, vote, data, key):
    path = os.path.join(cache_dir, key[:2], key + ".json")
    if os.path.exists(path):
        with open(path) as f:
            entry = json.load(f)
        return {"parsed": entry["parsed"], "cache_hit": True, "key": key, "entry": entry}
    res = backend(image_path, prompt, schema)
    entry = {
        "key": key, "frame_sha": _sha(data), "model": backend.model, "backend": backend.name,
        "params": backend_params(backend),
        "prompt": prompt, "prompt_sha": _sha_text(prompt), "schema_sha": _sha_text(_canon(schema)),
        "vote": vote, "created_utc": utc_now(), "parsed": res["parsed"], "raw": res.get("raw"),
        "usage": res.get("usage"), "tool_events": res.get("tool_events") or [], "label": LABEL,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w") as f:
        json.dump(entry, f, indent=1, sort_keys=True)
    os.replace(tmp, path)
    return {"parsed": res["parsed"], "cache_hit": False, "key": key, "entry": entry}


def _majority(obs_list: list[dict]) -> dict:
    if len(obs_list) == 1:
        return obs_list[0]
    out = {}
    for k in obs_list[0]:
        if k == "confidence":
            vals = sorted(o[k] for o in obs_list)
            out[k] = vals[len(vals) // 2]
            continue
        cnt = Counter(_canon(o[k]) for o in obs_list)
        top, n = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        out[k] = json.loads(top)
    agree = min(Counter(_canon(o[k]) for o in obs_list).most_common(1)[0][1]
                for k in obs_list[0] if k != "confidence") / len(obs_list)
    out["confidence"] = round(min(out["confidence"], agree), 3)   # disagreement lowers confidence
    return out


# ---------------------------------------------------------------- observe
def observe(frames: list[dict], backend, cache_dir: str = DEFAULT_CACHE, votes: int = 1,
            offset_s: float | None = None, prompt: str = OBS_PROMPT, max_workers: int = 4,
            errors: list | None = None) -> list[dict]:
    """Observe every frame (cached). Output is sorted by video_t, independent of thread order."""
    os.makedirs(cache_dir, exist_ok=True)
    votes = max(1, int(votes))
    jobs = [(i, v) for i in range(len(frames)) for v in range(votes)]
    results: dict = {}

    def run(job):
        i, v = job
        return job, cached_call(backend, frames[i]["frame_path"], prompt, OBS_SCHEMA, cache_dir, vote=v)

    with cf.ThreadPoolExecutor(max_workers=max(1, min(4, max_workers))) as ex:
        futs = [ex.submit(run, j) for j in jobs]
        for fut in futs:
            try:
                job, r = fut.result()
                results[job] = r
            except Exception as e:  # keep going: one failed frame must not sink the run
                if errors is not None:
                    errors.append(repr(e)[:300])
    out = []
    psha = _sha_text(prompt)
    for i, fr in enumerate(frames):
        rs = [results[(i, v)] for v in range(votes) if (i, v) in results]
        if not rs:
            continue
        obs = _majority([normalize_obs(r["parsed"]) for r in rs])
        vt = fr["video_t"]
        out.append({
            "video_t": vt,
            "run_t": round(vt + offset_s, 3) if offset_s is not None else None,
            "frame_path": fr["frame_path"],
            "frame_sha": _sha(open(fr["frame_path"], "rb").read()),
            "obs": obs,
            "votes": len(rs),
            "model": backend.model,
            "prompt_sha": psha,
            "cache_hit": all(r["cache_hit"] for r in rs),
            "cache_keys": [r["key"] for r in rs],
            "created_utc": min(r["entry"].get("created_utc", "") for r in rs),
            "label": LABEL,
        })
    out.sort(key=lambda r: r["video_t"])
    return out


def read_overlay_clock(video: str, video_t: float, backend, cache_dir: str = DEFAULT_CACHE,
                       workdir: str | None = None) -> float | None:
    """Ask the backend to read t+N from a crop of ONLY the HUD bar's start (cached). Returns N."""
    workdir = workdir or tempfile.mkdtemp(prefix="perception-clock-")
    png = crop_hud_clock(video, video_t, os.path.join(workdir, f"hud_{int(video_t * 1000):08d}ms.png"))
    r = cached_call(backend, png, CLOCK_PROMPT, CLOCK_SCHEMA, cache_dir)
    v = r["parsed"].get("t_plus_s")
    return float(v) if isinstance(v, (int, float)) else None


def alignment_for(video: str, offset_s: float | None = None) -> dict:
    if offset_s is not None:
        return {"offset_s": float(offset_s), "method": "explicit --offset"}
    known = KNOWN_ALIGNMENTS.get(os.path.basename(video))
    if known:
        return dict(known)
    return {"offset_s": None, "method": "unknown: pass --offset (run_t left null)"}


def read_run_time(video: str, video_t: float, offset_s: float | None = None) -> float | None:
    """Deterministic run time for a video time (see module docstring for why not OCR)."""
    off = alignment_for(video, offset_s)["offset_s"]
    return None if off is None else round(video_t + off, 3)


def _file_sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_perception(video: str, backend, every_s: float = 2.0, votes: int = 1,
                   cache_dir: str = DEFAULT_CACHE, offset_s: float | None = None,
                   frames_dir: str | None = None, run_log: str | None = None,
                   check_clock: bool = False, adaptive: bool = False,
                   frames_index: str | None = None) -> dict:
    dense = []
    if adaptive and run_log:
        try:
            dense = event_times(run_log)
        except Exception:
            dense = []
    if frames_index:
        # Clean frames + explicit run times from the capture (preferred: no overlay, no offset guess).
        idx = json.load(open(frames_index))
        base = os.path.dirname(os.path.abspath(frames_index))
        allf = sorted(({"frame_path": os.path.join(base, e["file"]), "video_t": round(float(e["run_t"]), 3)}
                       for e in idx if os.path.exists(os.path.join(base, e["file"]))), key=lambda f: f["video_t"])
        want = sample_times(allf[-1]["video_t"] if allf else 0.0, every_s, 1000.0, dense, 0.5, 10.0)
        frames, j = [], 0
        for t in want:  # nearest captured frame to each wanted time, de-duplicated
            best = min(allf, key=lambda f: (abs(f["video_t"] - t), f["video_t"])) if allf else None
            if best and best not in frames:
                frames.append(best)
        frames.sort(key=lambda f: f["video_t"])
        align = {"offset_s": 0.0, "method": f"frames_index {os.path.basename(frames_index)} (run_t per frame)"}
    else:
        align = alignment_for(video, offset_s)
        frames_dir = frames_dir or os.path.join(cache_dir, "frames", _file_sha(video)[:16])
        vdense = [t - align["offset_s"] for t in dense] if align.get("offset_s") is not None else []
        frames = extract_frames(video, every_s, frames_dir, dense_times=vdense)
    calls_before = backend.calls
    errors: list = []
    recs = observe(frames, backend, cache_dir=cache_dir, votes=votes, offset_s=align["offset_s"],
                   errors=errors)
    run_meta = {}
    if run_log:
        try:
            from .timeline import load_timeline
            tl = load_timeline(run_log)
            run_meta = {"run_log": run_log, "run_duration_s": tl.meta.get("duration_s"),
                        "run_id": tl.meta.get("run_id")}
            dur = tl.meta.get("duration_s")
            for r in recs:
                r["after_run_log_end"] = bool(r["run_t"] is not None and dur is not None and r["run_t"] > dur)
        except Exception as e:  # alignment metadata only; observations stand on their own
            run_meta = {"run_log": run_log, "error": repr(e)[:200]}
    clock = None
    if check_clock and frames:
        ts = [frames[0]["video_t"], frames[len(frames) // 2]["video_t"], frames[-1]["video_t"]]
        reads = [{"video_t": t, "t_plus_s": read_overlay_clock(video, t, backend, cache_dir)} for t in ts]
        clock = {"reads": reads, "consistent": all(r["t_plus_s"] is not None and
                                                   abs(r["t_plus_s"] - int(r["video_t"])) <= 1 for r in reads)}
    return {
        "label": LABEL,
        "schema_version": 1,
        "video": os.path.abspath(frames_index) if frames_index else os.path.abspath(video),
        "video_sha": _file_sha(frames_index if frames_index else video),
        "backend": backend.name,
        "model": backend.model,
        "backend_params": backend_params(backend),
        "prompt": OBS_PROMPT,
        "prompt_sha": _sha_text(OBS_PROMPT),
        "obs_schema": OBS_SCHEMA,
        "crop": {"scene_y": [SCENE_Y0, SCENE_Y1], "size": [SCENE_W, SCENE_H], "masks_xywh": MASKS},
        "alignment": align,
        "clock_check": clock,
        "every_s": every_s,
        "sampling": {"adaptive": bool(adaptive), "dense_every_s": 0.5, "dense_window_s": 10.0,
                     "dense_event_run_t": dense},
        "votes": votes,
        "run": run_meta,
        "stats": {"n_frames": len(frames), "n_observed": len(recs),
                  "cache_hits": sum(1 for r in recs if r["cache_hit"]),
                  "backend_calls": backend.calls - calls_before, "errors": errors},
        "frames": recs,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m splitcheck.perception", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--run-log", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--votes", type=int, default=1)
    ap.add_argument("--backend", choices=["codex", "claude", "fake"], default="codex")
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default="low")
    ap.add_argument("--offset", type=float, default=None, help="run_t = video_t + OFFSET")
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE)
    ap.add_argument("--check-clock", action="store_true", help="VLM-read HUD t+N on 3 frames (cached)")
    ap.add_argument("--adaptive", action="store_true",
                    help="also sample every 0.5 s within +-10 s of logged events (needs --run-log)")
    ap.add_argument("--frames-index", default=None,
                    help="frames_index.json [{file, run_t}] of clean frames; replaces video extraction")
    a = ap.parse_args(argv)
    backend = make_backend(a.backend, a.model, a.effort)
    res = run_perception(a.video, backend, every_s=a.every, votes=a.votes, cache_dir=a.cache_dir,
                         offset_s=a.offset, run_log=a.run_log, check_clock=a.check_clock,
                         adaptive=a.adaptive, frames_index=a.frames_index)
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    s = res["stats"]
    print(f"{s['n_observed']}/{s['n_frames']} frames observed  model={res['model']}  "
          f"cache_hits={s['cache_hits']}  backend_calls={s['backend_calls']}  errors={len(s['errors'])}"
          f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
