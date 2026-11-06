# Provenance: seed 8398967436125155523 (Java 1.16.5)

All JSON files here are verbatim copies from https://github.com/rmalde/minecraft-agent
at commit `78b40ed59514e5e2abde33a05ce398ecb2c39e05`, directory `optimization/nether/`.
They are read-only Mineflayer surveys (`optimization/nether/survey.mjs`: findBlocks for chests,
beds, obsidian, crying obsidian, portals, end portal frames, gravel within 100 blocks) and the
route config the agent used. Loaded by `code/splitcheck/seedfeatures.py`.

| file | source path | used for | sha256 |
|---|---|---|---|
| config.json | optimization/nether/config.json | village, supply chests, entry/exit portal, active End portal, nether route, beds, kit | c8f339d27f5dcec2e9892a30addd2cfff56a51bb90a41d3b8df38256198b7cdf |
| portal-loot.json | optimization/nether/portal-loot.json | contents of chests (-284,66,262), (-290,68,253) | 3a2cf18943600540a7245fade6d8349500e66b31d76be3abeeefab11976d456a |
| chest-survey.json | optimization/nether/chest-survey.json | contents of village chests incl. (-228,71,240) | 01bec0d32562b254fa5d6bf3a8cf2b4ab0a3ef856e4df8556c4355525d7236fe |
| portal-survey.json | optimization/nether/portal-survey.json | existing entry-frame obsidian, crying obsidian | 4b8d3d0a0bd7744cafe8da9b86c365654d9494f947bf17b2027af9b2d32063a6 |
| spawn-survey.json | optimization/nether/spawn-survey.json | approximate spawn position | 53dc140df14f7ac3a3a842cd54be3f025d94e6246eb9b898b3cf8b7759f2253b |
| stronghold-survey.json | optimization/nether/stronghold-survey.json | End portal blocks/frames (12 frames, all eyes), stronghold chest positions | 4ce3745005e9d50237512bf08a8f8881a27e379afb9bb857933006d636927ea7 |
| entry-link.json | optimization/nether/entry-link.json | nether-side portal linked to the entry portal | 21db436345bc05b0381a20c48b38d9e0af7098095ee91ce2edcfa4899c6e1e00 |
| exit-link.json | optimization/nether/exit-link.json | overworld-side portal after the nether exit (near stronghold) | a6826433b9cd725337ac7fac5099369c67420d5cfeb4e5522c17756a483a8d66 |
| nether-exit-survey.json | optimization/nether/nether-exit-survey.json | copied for completeness (nether terrain below exit) | 90d5d4ab77c455613902d84e5ee699190d58dbebd8fe3ceb9b9f2f52211e6fd6 |
| exit-terrain.json | optimization/nether/exit-terrain.json | copied for completeness (surface heights near exit) | d620b10f6cee63756d637089e2cca16439817328db7b6c8b852bc519f2c45405 |

Facts taken from prose rather than JSON (cited in feature `source` fields):
- `optimization/nether/REVIEW.md` line 7: three supply chests, 21 obsidian total, iron pickaxe, iron, flint; eight beds; active End portal at (-1130,34,856).
- `optimization/nether/REVIEW.md` line 9: entry frame has 3 essential existing obsidian, 7 to place (config.json `entryNote` says "nine new obsidian", an older plan; both are recorded); exit uses 10 obsidian + 4 ordinary corners.

Not copied: `optimization/seed-map.json` and `optimization/seed-route.json` describe a different
seed (`-4530634556500121041`, a boat/water route) and do not apply here.

Not available: no lava or water survey exists for this seed; `lava_pools` and `water` are empty lists.
`spawn` is the bot position at the spawn survey, flagged `approximate`.
