# Generic decision tasks: supplementary, not part of the headline result

These 14 tasks are generic random-seed (RSG) situations for Java 1.16.5 (T07 is 1.16.1 on purpose). They cover splits that the seed `8398967436125155523` route skips (bastion, fortress, triangulation, portal room) and general Nether-entry and dragon play.

- `tasks/` holds what the AI sees and `reference/` holds the answers. The format is in `SCHEMA.md`, sections 1–7.
- Their answers come from the Minecraft wiki and game data, not from a pro run. So they have no pro time, and they do not feed the efficiency result.
- T01 (plains reset) is still `verified: false`; see `UNVERIFIED.md`.
- They are built by `python tools/build_tasks.py` and checked by `python tools/validate_refs.py`.
