// A/B the decision layer on the same states: current classifier (NVIDIA), DeepSeek Flash, OpenAI.
// Measures latency, JSON validity and whether the chosen skill is allowed for the split.
const { chat } = require('../src/llm')
const { ALLOWED_BY_SPLIT } = require('../src/router')
const { REGISTRY } = require('../src/skills')

const SYSTEM = `You are the reflex-policy classifier for a Minecraft 1.16.1 speedrun bot. You do not plan a route. Given a compact state and the current split, output the single best immediate action from the allowed list.
Bias: 1) survive (lava<=3 -> move; hp<=8 -> eat/flee), 2) finish the current split with the fewest resources, 3) pick up drops you just made. No spare tools, no armor, no food you do not need.
Reply with exactly one JSON object: {"skill":{"name":"<allowed>","args":{...}},"why":"<=80 chars","urgency":"low|normal|high"}`

const blocks = split => (ALLOWED_BY_SPLIT[split] || []).map(n =>
  `- ${n}(${Object.entries(REGISTRY[n].args).map(([k, t]) => `${k}:${t}`).join(', ')}): ${REGISTRY[n].desc}`).join('\n')

const CASES = [
  { split: 'wood', state: `dim=overworld pos=-211,72,226 hp=20 food=20 held=none\ninv[0]: empty\nnear: logs@2.8 counts: oak_log:24 stone:110\nhostiles: none; danger: clear` },
  { split: 'stone', state: `dim=overworld pos=-211,72,226 hp=18 food=17 held=wooden_pickaxe\ninv[4]: oak_logx2, stickx4, wooden_pickaxex1\nnear: stone@3 counts: stone:80\nhostiles: zombie@5; danger: clear` },
  { split: 'portal', state: `dim=overworld pos=-281,65,261 hp=14 food=12 held=bucket\ninv[6]: iron_ingotx3, bucketx1, flint_and_steelx1\nnear: lava@40 water@6 obsidian@2\nhostiles: none; danger: clear` },
  { split: 'pearls', state: `dim=the_nether pos=-120,40,90 hp=20 food=18 held=gold_ingot\ninv[8]: gold_ingotx12, iron_swordx1, breadx3\nnear: goldBlock@8 chest@6\nhostiles: piglin@4; danger: clear` },
  { split: 'rods', state: `dim=the_nether pos=-60,50,140 hp=20 food=16 held=iron_sword\ninv[7]: iron_swordx1, breadx2, obsidianx3\nnear: blazeSpawner@4\nhostiles: blaze@5, blaze@9; danger: clear` },
  { split: 'stronghold', state: `dim=the_nether pos=-130,41,100 hp=20 food=14 held=ender_eye\ninv[9]: ender_eyex2, obsidianx10, flint_and_steelx1\nnear: netherrack@1\nhostiles: none; danger: clear` }
]

const BACKENDS = [
  { name: 'nvidia-bolt (current)', provider: 'nvidia', model: 'nvidia/nemotron-3.5-bolt-e4b', maxTokens: 160, effort: undefined },
  { name: 'deepseek-flash', provider: 'deepseek', model: 'deepseek-flash', maxTokens: 500, effort: 'low' },
  { name: 'openai-gpt-5.4-mini', provider: 'openai', model: 'gpt-5.4-mini', maxTokens: 400, effort: 'low' }
]

;(async () => {
  const rows = []
  for (const c of CASES) {
    const allowed = ALLOWED_BY_SPLIT[c.split] || []
    for (const b of BACKENDS) {
      const t0 = Date.now()
      let out = { ok: false, err: null, skill: null, ms: 0, allowed: null }
      try {
        const res = await chat({
          provider: b.provider, model: b.model, effort: b.effort, maxTokens: b.maxTokens,
          temperature: 0.1, system: SYSTEM,
          messages: [{ role: 'user', content: `state:\n${c.state}\nsplit: ${c.split}\nallowed:\n${blocks(c.split)}` }],
          purpose: 'bench-decisions'
        })
        const p = res.json && (res.json.skill || res.json)
        const name = p && (p.name || p.skill)
        out = { ok: !!name, skill: name, ms: Date.now() - t0, allowed: allowed.includes(name), err: null }
      } catch (e) {
        out = { ok: false, err: String(e.message).slice(0, 60), skill: null, ms: Date.now() - t0, allowed: null }
      }
      rows.push({ split: c.split, backend: b.name, ...out })
      console.log(`${c.split.padEnd(11)} ${b.name.padEnd(24)} ${String(out.ms).padStart(5)}ms ${out.ok ? out.skill : 'ERR'}${out.allowed === false ? '  (NOT ALLOWED)' : ''}`)
    }
  }
  const summary = {}
  for (const r of rows) {
    const s = summary[r.backend] || (summary[r.backend] = { n: 0, ok: 0, allowed: 0, ms: 0 })
    s.n++; if (r.ok) s.ok++; if (r.allowed) s.allowed++; s.ms += r.ms
  }
  for (const [k, v] of Object.entries(summary)) console.log(`\n${k}: ${v.ok}/${v.n} parsed, ${v.allowed}/${v.n} allowed-skill, avg ${Math.round(v.ms / v.n)}ms`)
  require('fs').writeFileSync('/tmp/bench-decisions.json', JSON.stringify(rows, null, 1))
})().catch(e => { console.error(e); process.exit(1) })
