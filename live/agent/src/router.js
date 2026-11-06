// Action classifier (fast, high-frequency). This is the layer rmalde/minecraft-agent fills with
// the JEV action model: given a small state, pick the next short-horizon action. We use a cheap
// low-effort model because it is called every few seconds and must not dominate latency.
const config = require('./config')
const { chat } = require('./llm')
const { REGISTRY } = require('./skills')

const SYSTEM = `You are the reflex-policy classifier for a Minecraft 1.16.1 speedrun bot. You do not plan a route. Given a compact state and the current split, output the single best immediate action from the allowed list.

Bias (in order):
1. Survive: lava within 3 -> move away; hp<=8 -> eat/flee; hostiles <=6 blocks with no weapon -> flee.
2. Finish the current split with the fewest resources: wood->pickaxe->stone->iron->portal.
3. Pick up drops you just made (items within 6 blocks).
Use ensure_pickaxe / ensure_axe / ensure_sword for tools (they make planks and sticks first). Do not craft spares, armor, or food you do not need. Do not start a new objective while the split's core action is available.

Reply with exactly one JSON object:
{"skill":{"name":"<allowed>","args":{...}},"why":"<=80 chars","urgency":"low|normal|high"}`

const ALLOWED_BY_SPLIT = {
  spawn: ['collect_wood', 'goto', 'ensure_pickaxe'],
  wood: ['collect_wood', 'craft', 'ensure_pickaxe', 'ensure_axe', 'goto', 'eat', 'flee'],
  stone: ['dig_staircase', 'mine_blocks', 'craft', 'ensure_pickaxe', 'ensure_sword', 'goto', 'eat', 'flee'],
  iron: ['mine_blocks', 'dig_staircase', 'smelt', 'craft', 'attack', 'eat', 'flee', 'goto'],
  portal: ['water_on_lava', 'light_portal', 'enter_portal', 'take_from_chest', 'mine_blocks', 'goto', 'eat', 'flee', 'attack'],
  pearls: ['take_from_chest', 'barter', 'attack', 'flee', 'goto', 'eat'],
  rods: ['attack', 'goto', 'take_from_chest', 'eat', 'flee'],
  stronghold: ['throw_eye', 'goto', 'enter_portal', 'craft', 'eat', 'flee'],
  end: ['goto', 'throw_eye', 'eat', 'attack', 'flee'],
  dragon: ['goto', 'attack', 'eat', 'flee']
}

function allowedBlock (split) {
  const names = ALLOWED_BY_SPLIT[split] || ALLOWED_BY_SPLIT.wood
  return names.map(n => {
    const r = REGISTRY[n]
    return r ? `- ${n}(${Object.entries(r.args).map(([k, t]) => `${k}:${t}`).join(', ')}): ${r.desc}` : null
  }).filter(Boolean).join('\n')
}

function normalize (json, allowed) {
  if (!json) return null
  // models sometimes answer {"skill":"mine_blocks"} instead of {"skill":{"name":...}}
  if (typeof json.skill === 'string') json = { ...json, skill: { name: json.skill, args: json.args || {} } }
  const p = json.skill || json.action || json
  const name = p && (p.name || p.skill)
  if (!name || !REGISTRY[name]) return null
  if (allowed && !allowed.includes(name)) return null
  return {
    name,
    args: (p.args && typeof p.args === 'object') ? p.args : {},
    why: String(json.why || '').slice(0, 100),
    urgency: ['low', 'normal', 'high'].includes(json.urgency) ? json.urgency : 'normal'
  }
}

async function classify ({ compact, split, last }) {
  const allowed = ALLOWED_BY_SPLIT[split] || ALLOWED_BY_SPLIT.wood
  const user = [
    `state:\n${compact}`,
    `split: ${split}`,
    last ? `last: ${JSON.stringify(last)}` : null,
    `allowed:\n${allowedBlock(split)}`
  ].filter(Boolean).join('\n\n')
  const t0 = Date.now()
  let res
  try {
    res = await chat({
      provider: config.models.classifier.provider,
      model: config.models.classifier.model,
      effort: config.models.classifier.effort,
      maxTokens: config.models.classifier.maxTokens,
      temperature: 0.1,
      system: SYSTEM,
      messages: [{ role: 'user', content: user }],
      purpose: 'classifier'
    })
  } catch (err) {
    // free-tier hiccup -> same contract on the DeepSeek fallback, still cheap
    res = await chat({
      provider: 'deepseek',
      model: process.env.CLASSIFIER_FALLBACK_MODEL || 'deepseek-flash',
      effort: 'low',
      maxTokens: 500,
      temperature: 0.1,
      system: SYSTEM,
      messages: [{ role: 'user', content: user }],
      purpose: 'classifier_fallback'
    })
  }
  const action = normalize(res.json, allowed) || normalize(res.json, null)
  if (!action) throw new Error(`classifier returned no usable action: ${JSON.stringify(res.json)}`)
  return { ...action, ms: Date.now() - t0, model: res.model, provider: res.provider }
}

module.exports = { classify, normalize, ALLOWED_BY_SPLIT }
