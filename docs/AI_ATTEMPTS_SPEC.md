# Spec: running the AI on the tasks (the "AI attempts" deliverable)

Owner: whoever runs it (Person C, or A if C is busy). Deadline: **attempts frozen by 2:45 PM**. Results go into WRITEUP.md by 3:15.

## Rules we must follow (from the opening slides)
1. **One AI for every task.** Pick it once and don't switch.
2. **A new conversation for each task.**
3. **Keep the first answer.** Never rerun a task to get a better answer, never edit the answer.
4. **Record model, date and exact prompt** with every answer.
5. **Never show the AI our answers or our checker.**

## Decisions (make them before starting, write them in WRITEUP.md)
| Decision | Default | Why |
|---|---|---|
| Model | `gpt-6-astra` via the Codex CLI (already logged in on Anshul's laptop) | It's the same planner model the rmalde agent used, so the chatbot results and the agent-run results talk about the same model. Free/web plans are also fine by the rules. |
| Reasoning effort | `high`, recorded in every attempt | State it in the write-up. Don't change it mid-run. |
| Prompt | exactly `tasks/<id>.json` → `prompt`, plus one fixed preamble line (below) | The preamble is recorded inside each attempt's `prompt` field. |

Preamble (identical for every task): *"Answer from your own knowledge only. Do not run commands, read files, or browse the web. Reply with the JSON object the question asks for."*

## How to run (scripted, recommended)
```bash
cd ~/agenticgamebech
git pull                                   # get Person B's final tasks first: tasks must be FINAL before running
python3 run_ai.py --dry-run                # lists the tasks it will run
python3 run_ai.py --model gpt-6-astra --effort high --parallel 4
```
* Each task runs in a **fresh, empty temp folder outside the repo** (the model cannot see `reference/` or `code/`), in a read-only sandbox, as a separate `codex exec` session = a new conversation.
* `run_ai.py` **never overwrites** an existing `attempts/<id>.json`. That is how the first-attempt rule is enforced.
* If the model uses any tool anyway (shell command, file read, web search), the attempt is saved with `"contaminated": true` and the tool events listed. Keep it (first answer). Report how many were contaminated in the write-up.
* Takes about 1–3 minutes per task. With `--parallel 4`, 21 tasks take about 10–15 minutes.

## Manual alternative (if Codex is out of usage)
`python3 run_ai.py --backend manual --model "<exact model name as the app shows it>"`. It prints and copies each prompt. Open a **new chat** in the app, paste, copy the **first** reply back, end with `END`.

## What each attempt file contains (`attempts/<task_id>.json`)
`task_id, model, reasoning_effort, backend, backend_version, date (UTC start), finished, prompt (exact text sent), raw_response (first answer, unedited), later_messages, tool_events, contaminated, thread_id, usage, exit_code`. The checker reads `task_id, model, date, prompt, raw_response`.

## After the run
```bash
cd code && python -m splitcheck.check --root ..     # writes runs/results.csv + runs/checker_output/
python -m splitcheck.check --root ..                # run again: results.csv must be byte-identical (shasum)
```
Then commit `attempts/` and `runs/` together **once**, and don't touch attempts again.

## Done when
- [ ] Every task in `tasks/` has exactly one attempt, all from the same model and effort.
- [ ] `runs/results.csv` exists, and two checker runs give the same hash.
- [ ] Contaminated and empty attempts are counted and named in WRITEUP.md (not deleted).
- [ ] WRITEUP.md filled in: model, date, effort, verdict counts (OK/SLOW/ILLEGAL/WRONG), the top misses by taxonomy tag, 2–3 quoted catches with the checker's reason.

## Don't
- Don't run before Person B has frozen the tasks: a changed task after its attempt makes that attempt invalid.
- Don't delete or rerun an attempt because the answer was bad. Bad answers are the result.
- Don't paste tasks into a chat that already has history.
