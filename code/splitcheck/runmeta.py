"""Run facts from a RUN_NOTES.md, and which rules.json fairness notes apply to this run.

    facts = parse_run_notes(path)            # {} if the file is missing
    notes = fairness_applicability(rules["fairness"], facts, reached={"nether_entered", ...})

RUN_NOTES.md is free text written by the operator; we read its "- **Label:** value" bullets
(continuation lines are joined) and the "# RUN <id> — <kind>, ..." title. Deterministic, stdlib only.
A fairness note is marked "does not apply to this run: <why>" only when a parsed fact contradicts it;
a note we have no fact for is left as is.
"""
from __future__ import annotations

import re
from pathlib import Path

_BULLET = re.compile(r"^\s*[-*]\s+\*\*(.+?)\*\*\s*(.*)$")


def _clean(s: str) -> str:
    s = s.replace("**", "")
    return " ".join(s.split()).strip()


def parse_bullets(text: str) -> dict:
    """{label (no trailing ':' / '?'): value} for '- **Label:** value' bullets; label keeps '?' info."""
    out, cur = {}, None
    for raw in text.splitlines():
        m = _BULLET.match(raw)
        if m:
            label = m.group(1).strip()
            val = m.group(2)
            if label.endswith(":"):
                label = label[:-1]
            elif val.startswith(":"):
                val = val[1:]
            cur = label.strip()
            out[cur] = val.strip()
            continue
        if cur and raw.startswith((" ", "\t")) and raw.strip() and not re.match(r"\s*([-*]\s|#|\|)", raw):
            out[cur] += " " + raw.strip()
            continue
        cur = None
    return {k: _clean(v) for k, v in out.items()}


def _get(b: dict, *names):
    for want in names:
        for k, v in b.items():
            if k.lower().rstrip("?").strip() == want.lower():
                return v
    return None


def _difficulty(text: str | None):
    if not text:
        return None
    m = re.search(r"difficulty\s*[:=]?\s*(peaceful|easy|normal|hard)", text, re.I)
    return m.group(1).lower() if m else None


def parse_run_notes(path) -> dict:
    """Run facts: run_id, agent, live, planner_model, difficulty, first_attempt, interventions,
    interventions_none, outcome, outcome_short, source. Missing file -> {}."""
    p = Path(path) if path else None
    if not p or not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    b = parse_bullets(text)
    title = next((ln[1:].strip() for ln in text.splitlines() if ln.startswith("# ")), "")
    facts: dict = {"source": str(p), "title": _clean(title)}
    rid = _get(b, "RUN_ID", "run id", "run")
    if not rid:
        m = re.match(r"RUN\s+(\S+)", title)
        rid = m.group(1) if m else None
    facts["run_id"] = rid.strip("` ") if rid else None
    kind = None
    m = re.search(r"\s(?:—|–|-)\s+([^,]+)", title)
    if m:
        kind = m.group(1).strip()
    facts["agent"] = kind
    facts["live"] = bool(kind and "live" in kind.lower())
    pm = _get(b, "Planner model", "planner", "model")
    facts["planner_model_text"] = pm
    if pm:
        m = re.search(r"`([^`]+)`", pm)
        facts["planner_model"] = m.group(1) if m else pm.split("·")[0].strip()
    else:
        facts["planner_model"] = None
    # raw (uncleaned) server bullet keeps backticks; difficulty is in it or a Difficulty bullet
    dbul = _get(b, "Difficulty")
    facts["difficulty"] = (_difficulty("difficulty " + dbul) if dbul else None) \
        or _difficulty(_get(b, "Server")) or _difficulty(text)
    fa = _get(b, "First attempt", "first attempt?")
    facts["first_attempt"] = fa
    facts["first_attempt_world"] = bool(fa and re.search(r"yes for this world|^yes", fa, re.I))
    iv = _get(b, "Interventions during the run", "Interventions")
    facts["interventions"] = iv
    facts["interventions_none"] = bool(iv and re.match(r"none\b", iv, re.I))
    oc = _get(b, "Outcome")
    facts["outcome"] = oc
    facts["outcome_short"] = (oc.split(". ")[0].rstrip(".") + ".") if oc else None
    return facts


def fairness_applicability(fairness: dict, facts: dict, reached=None) -> dict:
    """{note key: reason it does not apply} for notes contradicted by the run facts.
    reached: set of milestone names this run reached (e.g. from the agent timeline), or None."""
    out = {}
    if not facts:
        return out
    diff = facts.get("difficulty")
    live = facts.get("live")
    rid = facts.get("run_id") or "this run"
    for k, v in (fairness or {}).items():
        s = str(v)
        low = s.lower()
        why = None
        if k == "difficulty" or "peaceful" in low:
            m = re.search(r"agent on (peaceful|easy|normal|hard)", low)
            said = m.group(1) if m else None
            if said and diff and said != diff:
                why = (f"the rules say the agent played on {said.capitalize()}, but {rid} was on "
                       f"{diff.capitalize()} (RUN_NOTES)")
        if why is None and k == "rng" and reached is not None and "end_entered" not in reached \
                and ("dragon" in low or "end segment" in low):
            why = f"{rid} never reached the End, so dragon RNG plays no part"
        if why is None and live and ("montage" in low or "published" in low or "rmalde" in low):
            if k == "brackets" or "cuts" in low:
                why = (f"{rid} is a live run with a continuous timestamped event log, not the published "
                       "montage; its milestones are exact log times, not brackets")
            elif k == "practice":
                why = (f"the agent half: {rid} is a live run, not the author's best published run"
                       + (f"; first attempt: {facts['first_attempt']}" if facts.get("first_attempt") else ""))
            elif k == "route_supplied":
                why = (f"the note describes the published rmalde/minecraft-agent config; {rid} is a live agent "
                       "whose route is fixed in its own route_start event (the point that the route is "
                       "supplied, not chosen by the LLM, still holds)")
            else:
                why = f"the note describes the published montage run; {rid} is a live run"
        if why:
            out[k] = why
    return out


def this_run_lines(facts: dict) -> list:
    """Markdown '## This run' section."""
    if not facts:
        return []
    rows = [("Run", facts.get("run_id")), ("Agent", facts.get("agent")),
            ("Planner model", facts.get("planner_model_text") or facts.get("planner_model")),
            ("Difficulty", facts.get("difficulty")), ("First attempt", facts.get("first_attempt")),
            ("Interventions", facts.get("interventions")), ("Outcome", facts.get("outcome"))]
    src = facts.get("source") or "RUN_NOTES.md"
    if Path(src).is_absolute():
        try:
            src = Path(src).relative_to(Path(__file__).resolve().parents[2]).as_posix()
        except ValueError:
            pass
    L = ["## This run", "", f"From `{src}` (operator notes, not checked against the log except where "
         "another section says so).", ""]
    L += [f"- **{k}:** {v}" for k, v in rows if v]
    return L + [""]
