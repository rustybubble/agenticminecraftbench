# SplitCheck file formats

Owner: B. Person A codes the checker against this file. Any change after the first publish goes in the **Changelog** at the bottom.

All files are UTF-8 JSON. Item, block and mob ids are Minecraft ids **without** the `minecraft:` prefix (`obsidian`, `flint_and_steel`, `ender_eye`, `blaze_rod`, `piglin`, `ender_dragon`). Coordinates are block coordinates as shown on the F3 screen.

## 1. `tasks/<id>.json` (what the AI sees)

Never put the answer, the trap, or a hint at the trap in a task file.

```json
{
  "id": "T03_nether_exit_coords",
  "split": "reset | nether_entry | bastion | fortress | blind_travel | triangulation | portal_room | dragon | full_route",
  "version": "1.16.5",
  "seed": "8398967436125155523",
  "difficulty": "peaceful | easy",
  "prompt": "Exact text sent to the AI: situation + question + required output format",
  "state": {
    "dimension": "overworld | the_nether | the_end",
    "position": {"x": 0, "y": 0, "z": 0},
    "inventory": {"item_id": 1},
    "known_locations": {"name": {"x": 0, "y": 0, "z": 0, "dimension": "overworld"}},
    "world": {},
    "elapsed_s": 0
  },
  "answer_type": "plan | number | coordinates | choice",
  "answer_schema": "Exact JSON shape the AI must reply with (also copied verbatim into the prompt)"
}
```

Field notes:

- `seed`: a string, or `null` for generic random-seed (RSG) tasks.
- `state.world` (optional): facts the AI is told about the world that the checker needs for legality, for example chest contents or what an existing portal frame looks like. Shape:
  ```json
  {
    "chests":     {"<location name>": {"item_id": 3}},
    "structures": {"<location name>": {"type": "ruined_portal | village | bastion | fortress | stronghold | end_portal", "notes": "free text"}},
    "facts":      ["free-text facts stated to the AI, e.g. 'the End portal is already active'"]
  }
  ```
  Every `<location name>` used here must also appear in `known_locations`.
- `state.position` may be `null` when position does not matter (for example reset decisions).
- `elapsed_s`: in-game time (IGT) already used when the task starts.
- `answer_schema`: a string holding the exact JSON shape, copied into the prompt so the AI sees the same text.

## 2. Answer shapes (what the AI replies with)

The AI must reply with one JSON object. Extra keys are ignored. A `"reasoning"` string key is always allowed and never scored.

| `answer_type` | Shape | Example |
|---|---|---|
| `number` | object of named numbers | `{"eyes_needed": 9, "eyes_to_carry": 11}` |
| `coordinates` | `x`, `z`, optional `y`, `dimension` | `{"x": -141, "y": 107, "z": 107, "dimension": "the_nether"}` |
| `choice` | `choice` = one option id from the prompt; may carry extra named fields defined by the task | `{"choice": "reset"}` |
| `plan` | ordered list of actions from the vocabulary in section 4 | `{"actions": [{"action": "loot_chest", "at": "chest_1"}, ...]}` |

## 3. `reference/<id>.json` (never shown to the AI)

```json
{
  "id": "T03_nether_exit_coords",
  "answer": "the correct answer, in the task's answer shape",
  "tolerance": {"blocks": 16},
  "pro_time_s": null,
  "why": "Step-by-step reason this is right, the way a pro runner would explain it",
  "trap": "The plausible wrong answer and why it is wrong",
  "techniques": [
    {"tag": "nether_travel_8to1", "description": "...", "est_time_saved_s": 0, "verified": true, "source": "url or repo:path:line"}
  ],
  "miss_category": "one of the 8 taxonomy tags in section 6",
  "sources": ["..."],
  "verified": true,
  "alternates": [{"answer": "a different VALID answer", "why_valid": "..."}],
  "broken":     [{"answer": "a WRONG answer", "expected_verdict": "ILLEGAL | SLOW | WRONG", "why_wrong": "..."}]
}
```

`tolerance` keys (use whichever apply):

| Key | Applies to | Meaning |
|---|---|---|
| `{"abs": n}` | `number` (all fields) | each field must be within ±n of the reference |
| `{"fields": {"name": {"abs": n}}}` | `number`, `choice` extras | per-field tolerance; a field not listed must match exactly |
| `{"blocks": n}` | `coordinates` | horizontal (x, z) Euclidean distance ≤ n; `dimension` must match |
| `{"y_blocks": n}` | `coordinates` | if present, `y` must also be within ±n; if absent, `y` is not scored |
| `{"seconds": n}` | `plan` | a legal plan priced within n seconds of `pro_time_s` is `OK`; slower is `SLOW` |
| `{"choices": ["a", "b"]}` | `choice` | the set of accepted choices (defaults to `[answer.choice]`) |

- `pro_time_s`: for `plan` tasks, the time of the reference plan priced with `splits/time_costs.json`, or a measured pro time from `splits/pro_splits.json`. `null` for other answer types.
- `alternates` and `broken`: every task has at least one of each. A runs them through the checker: every alternate must come back `OK`, and every broken answer must come back with its `expected_verdict`.
- `verified`: `true` only if every fact the answer depends on was confirmed from a source in `sources`. Otherwise `false`, and the item is listed in `UNVERIFIED.md`.
- Each technique has its own `verified` and `source`. `est_time_saved_s` may be `null` when no sourced estimate exists.

### Verdicts

| Verdict | Meaning |
|---|---|
| `OK` | Legal, and within tolerance (or within `seconds` of the pro time). |
| `SLOW` | Legal, but more than `tolerance.seconds` slower than `pro_time_s`. Only for `plan`. |
| `ILLEGAL` | The plan breaks a game rule or uses something it does not have (for example lighting a portal without flint and steel or a fire charge). Only for `plan`. |
| `WRONG` | A `number`, `coordinates` or `choice` answer outside tolerance, or a reply that does not parse against `answer_schema`. |

## 4. Plan action vocabulary

A plan is `{"actions": [ ... ]}`. Each action is an object with `"action"` plus the parameters below. Parameters not listed are ignored. A implements what each action does to the state (inventory, position, dimension, time) and its preconditions; the "intended meaning" column is the contract.

| Action | Parameters | Intended meaning and preconditions |
|---|---|---|
| `mine` | `block` (id), `count` (int) | Break `count` blocks of `block` and pick up the drops. Obsidian needs a `diamond_pickaxe` in inventory. Uses the 1.16 drop rules (for example `gravel` may drop `flint`). |
| `craft` | `item` (id), `count` (int) | Craft `count` of `item`. Ingredients must be in inventory. Items needing a crafting table need `crafting_table` in inventory or placed. |
| `smelt` | `item` (id, the output), `count` (int), `fuel` (id) | Smelt into `count` of `item`. Needs a furnace and the input and fuel. |
| `loot_chest` | `at` (a `known_locations` name) | Move all contents of that chest (from `state.world.chests`) into inventory. Must be at or travel to `at`. Each chest can be looted once. |
| `travel` | `to` (a `known_locations` name, or `{"x","y","z"}`), `dimension` (optional; defaults to current) | Walk or sprint to the target in the current dimension. Travel to a different dimension is illegal: change dimension with `enter_portal`. Time is priced by distance. |
| `build_portal` | `method`: `bucket_lava` \| `chest_obsidian` \| `mine_obsidian` \| `complete_ruined` | Build a Nether portal frame at the current position. `chest_obsidian` needs enough `obsidian` in inventory (10 for a cornerless frame, minus existing frame blocks when completing a ruined portal). `bucket_lava` needs `water_bucket` + `bucket` (or `lava_bucket`) and a lava source. `mine_obsidian` needs a `diamond_pickaxe`. `complete_ruined` needs a ruined portal at the current location plus enough obsidian for the missing blocks. |
| `light_portal` | `with`: `flint_and_steel` \| `fire_charge` | Light a built frame. Needs that item in inventory. |
| `enter_portal` | none | Go through a lit Nether portal or an active End portal at the current position. Switches dimension. Nether coordinates are overworld ÷ 8 in X and Z. |
| `barter` | `gold_ingots` (int) | Give gold ingots to piglins. Needs gold armor equipped for piglins to stay neutral. Yield is drawn from the barter table for the task's version. |
| `kill` | `mob` (id), `count` (int) | Kill `count` of `mob`. Some mobs do not spawn on Peaceful. |
| `throw_eye` | `at` (`{"x","y","z"}`, the throw position) | Throw one `ender_eye` from `at`. The eye may break. |
| `place_eyes` | `count` (int) | Place `count` eyes into empty frames of the End portal at the current position. |
| `bed_explode` | `count` (int) | Place and use `count` beds. Beds explode in `the_nether` and `the_end`. Used to damage the ender dragon. |
| `reset` | none | Abandon this world and start a new one. Ends the plan. |

## 5. `splits/` files

`splits/pro_splits.json`: one entry per split of the human baseline run.

```json
[
  {"split": "nether_entry", "time_s": 0, "run": "https://www.speedrun.com/mc/runs/yoex3d0z", "vod_timestamp": "mm:ss", "verified": true, "notes": "how the split boundary was defined"}
]
```

`time_s` is the cumulative in-game time at the end of the split. `vod_timestamp` is where that moment appears in the video.

`splits/time_costs.json`: seconds per action at pro pace.

```json
{
  "actions": {
    "<action or technique key>": {"seconds": 0, "per": "action | block | item | 100_blocks", "source": "url or repo:path:line", "verified": true, "notes": ""}
  }
}
```

## 6. Miss taxonomy tags (use exactly these)

| Tag | Meaning |
|---|---|
| `no_reset_judgment` | Keeps a hopeless seed or resets a good one |
| `brute_force_over_trick` | Uses a slow general method where a known trick exists (e.g. mining obsidian instead of using chest obsidian or a lava bucket portal) |
| `no_nether_shortcut` | Travels in the overworld instead of the Nether, or gets the 8:1 scaling wrong |
| `ignores_information` | Ignores facts given in the prompt (chest contents, an already-active portal, eye throws) |
| `resource_miscount` | Wrong count of items (eyes, rods, obsidian, beds) |
| `mob_rule_unaware` | Breaks a mob behaviour rule (piglin aggression, dragon perching, Peaceful spawning) |
| `detour_overprep` | Gathers things the route does not need (armor or food on Peaceful, extra tools) |
| `unnecessary_risk` | Takes a risk that a pro avoids (e.g. standing in dragon breath, opening chests next to piglins) |

## 7. Rules the simulator should use (v2)

- **Random drops** are simulated at their expected rate, rounded down, cumulative over the plan: gravel gives flint at 10%, so 10 gravel mined = 1 flint ([wiki: Gravel](https://minecraft.wiki/w/Gravel)).
- **Beds**: `mine{block: "white_bed" | "yellow_bed" | ..., count, at}` picks up that many bed items. Bed items are counted together for `bed_explode`.
- **Dragon kill**: a plan kills the dragon when the total `bed_explode` count in `the_end` reaches `splits/time_costs.json` → `rules.dragon_beds_required`. Melee or bow kills use `kill{mob: "ender_dragon"}` and are priced by the `kill_ender_dragon_melee` entry.
- **Finish**: a `full_route` plan finishes with `enter_portal` in `the_end` after the dragon is dead (the exit portal).
- **Portal linking**: entering a Nether portal at overworld (x, z) arrives in the Nether near (x/8, z/8), and the reverse. Y is not scaled. When the reference has a known arrival point (for example `state.known_locations` entries called `nether_arrival`), use it.

## Changelog

- v1 (initial publish): formats above.
- v2 (12:55):
  - Tasks may carry `"options": [...]` for `choice` tasks: the list of valid option ids. Answers outside it are `WRONG`.
  - `mine` and `loot_chest` take an optional `at` (a `known_locations` name). If given, the simulator first travels there.
  - `state.world.structures[*].type` adds `lava_pool` and `gravel_patch`. `build_portal{method: "bucket_lava"}` needs a `water_bucket` in inventory and the player at a `lava_pool` location. It does not need an empty `bucket`.
  - `state.position` and `state.elapsed_s` may be `null` for tasks where they do not matter.
  - `reference.pro_time_s` may be `null` for a `plan` task: then the checker prices `reference.answer` with `splits/time_costs.json` and uses that as the pro time. `reference.pro_time_note` explains any human upper bound.
  - New optional reference keys, informational only: `pro_time_note`, `verified_note`.
  - Section 7 added (drop rates, beds, dragon kill, finish, portal linking).
