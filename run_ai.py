#!/usr/bin/env python3
"""Run ONE AI model on every SplitCheck task: fresh conversation per task, first answer kept.

Follows the event rules (opening slides): same AI for every task; a new conversation per task;
save the first answer unchanged with model, date and exact prompt; never show the AI our answers
or our checker.

Backends
  codex   (default) Runs `codex exec` once per task in a brand-new EMPTY temp directory outside the
          repo, read-only sandbox, JSON event stream. Any tool use (shell commands, file reads, web)
          is recorded and the attempt is flagged `contaminated: true`. It is still kept: first answer only.
  manual  Prints the prompt (and copies it to the clipboard on macOS). You paste it into a NEW chat in
          the model's own app, then paste the reply back and end with a line containing only END.

Usage (from the repo root):
  python3 run_ai.py --dry-run                         # show what would run, write nothing
  python3 run_ai.py --model gpt-6-astra --effort high # run every task that has no attempt yet
  python3 run_ai.py --only T04_nether_entry_seed_chests
  python3 run_ai.py --backend manual --model "<exact model name shown in the app>"
Existing attempts/<task_id>.json files are NEVER overwritten (first-attempt rule).
"""
import argparse, concurrent.futures as cf, datetime, glob, json, os, platform, shutil, subprocess, sys, tempfile

PREAMBLE = ("Answer from your own knowledge only. Do not run commands, read files, or browse the web. "
            "Reply with the JSON object the question asks for.\n\n")

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def codex_version():
    try:
        return subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as e:
        return f"unknown ({e})"

def run_codex(prompt, model, effort, timeout_s):
    work = tempfile.mkdtemp(prefix="splitcheck-ai-")  # empty dir: no repo files, no AGENTS.md
    cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--json"]
    if model:
        cmd += ["-m", model]
    if effort:
        cmd += ["-c", f'model_reasoning_effort="{effort}"']
    cmd.append("-")
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=work, timeout=timeout_s)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    events, messages, tools, thread_id, usage = [], [], [], None, None
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(ev)
        if ev.get("type") == "thread.started":
            thread_id = ev.get("thread_id")
        if ev.get("type") == "turn.completed":
            usage = ev.get("usage")
        item = ev.get("item") or {}
        if ev.get("type") == "item.completed":
            if item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
            elif item.get("type") not in ("reasoning",):
                tools.append({"type": item.get("type"), "detail": {k: v for k, v in item.items() if k != "id"}})
    return {
        "raw_response": messages[0] if messages else "",       # FIRST answer only
        "later_messages": messages[1:],
        "tool_events": tools,
        "contaminated": bool(tools),
        "thread_id": thread_id,
        "usage": usage,
        "exit_code": p.returncode,
        "stderr_tail": p.stderr[-800:],
    }

def run_manual(prompt):
    if platform.system() == "Darwin":
        try:
            subprocess.run(["pbcopy"], input=prompt, text=True, check=True)
            print("(prompt copied to clipboard)")
        except Exception:
            pass
    print("=" * 70 + "\nOPEN A NEW CHAT, paste this prompt, then paste the FIRST reply below and end with END\n" + "=" * 70)
    print(prompt)
    print("=" * 70 + "\nPaste reply, then a line with only END:")
    lines = []
    for line in sys.stdin:
        if line.strip() == "END":
            break
        lines.append(line)
    return {"raw_response": "".join(lines).strip(), "tool_events": [], "contaminated": None,
            "note": "manual: pasted from the model's own chat app"}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--backend", choices=["codex", "manual"], default="codex")
    ap.add_argument("--model", default="gpt-6-astra", help="record + request this exact model id")
    ap.add_argument("--effort", default=None, help="codex reasoning effort (e.g. low/medium/high/xhigh); recorded")
    ap.add_argument("--only", nargs="*", help="task ids to run (default: all without an attempt)")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    tasks = sorted(glob.glob(os.path.join(a.root, "tasks", "*.json")))
    out_dir = os.path.join(a.root, "attempts")
    os.makedirs(out_dir, exist_ok=True)
    todo = []
    for path in tasks:
        t = json.load(open(path))
        tid = t["id"]
        if a.only and tid not in a.only:
            continue
        dest = os.path.join(out_dir, f"{tid}.json")
        if os.path.exists(dest):
            print(f"SKIP {tid}: attempt already exists (first-attempt rule, never overwritten)")
            continue
        todo.append((tid, t, dest))
    print(f"{len(todo)} task(s) to run with backend={a.backend} model={a.model} effort={a.effort or 'default'}")
    if a.dry_run or not todo:
        for tid, _, _ in todo:
            print("  would run", tid)
        return

    cli = codex_version() if a.backend == "codex" else None

    def one(item):
        tid, t, dest = item
        prompt = PREAMBLE + t["prompt"]
        started = utc_now()
        res = run_codex(prompt, a.model, a.effort, a.timeout) if a.backend == "codex" else run_manual(prompt)
        rec = {"task_id": tid, "model": a.model, "reasoning_effort": a.effort, "backend": a.backend,
               "backend_version": cli, "date": started, "finished": utc_now(),
               "prompt": prompt, **res}
        if os.path.exists(dest):  # race guard: never overwrite
            return tid, "SKIPPED (appeared during run)"
        with open(dest, "w") as f:
            json.dump(rec, f, indent=2)
        flag = " CONTAMINATED (tool use recorded)" if res.get("contaminated") else ""
        return tid, f"saved{flag}" + ("" if res.get("raw_response") else " EMPTY RESPONSE")

    if a.backend == "manual":
        for item in todo:
            print(*one(item))
    else:
        with cf.ThreadPoolExecutor(max_workers=max(1, a.parallel)) as ex:
            for tid, status in ex.map(one, todo):
                print(f"{tid}: {status}")
    print("Next: cd code && python -m splitcheck.check --root ..")

if __name__ == "__main__":
    main()
