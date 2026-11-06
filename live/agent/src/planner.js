// Strategic planner (DeepSeek v4 Pro, effort=high). Called rarely: split changes, repeated
// failures, danger, or a 30s cadence. It gets the compact observation, the route state, and
// calculator output; it answers with ONE skill from the registry (with a fallback).
const config = require('./config')
const { chat } = require('./llm')
const { REGISTRY } = require('./skills')

const SYSTEM = `You are the strategic layer of an elite Minecraft Java 1.16.1 RSG (random seed glitchless) speedrun bot. You are not a chatbot and you do not narrate. You pick the single next action that a 6:40-caliber human runner would take.

HARD ROUTE RULES (violating these is the failure mode we are measuring):
- Reset judgment: a spawn with no trees, no structure and no lava pool within ~80 blocks is a reset, not a project. With a live run already in progress, do not reset; salvage.
- Minimal toolkit: 4-8 logs, planks/sticks, wooden pickaxe, then stone pickaxe. Do not craft spare tools, armor, or a full stone set. No farms. No potato detours.
- Iron: 3 iron is a bucket (or a pickaxe if the portal plan needs one). Kill animals you pass; do not hunt.
- Nether entry: water on a lava pool makes obsidian in place. Mining obsidian needs a diamond pickaxe, so either you already have that plan, or you finish a ruined portal with obsidian from chests. Never dig obsidian with an iron pickaxe.
- Nether is 8:1. Never walk long distances in the overworld; travel in the Nether toward target/8 and portal out near the target.
- Pearls: bastion chests first; bartering is supplementary. One gold armor piece before looting near piglins, and never open a chest or break a gold block in their line of sight.
- Blaze rods: 12 eyes need 12 powder = 6 rods. Take 7 for buffer. Eyes break 20% of throws, so do not over-farm and do not throw eyes one at a time.
- Stronghold: throw 2 eyes from different spots, triangulate, then travel. Ring 1 is 1280-2816 blocks from origin.
- End: beds one-cycle the dragon. Fill only empty portal frames.
- Risk: lava, falls and the void cost the whole run. A pro does not take a 10% death for a 5s gain.
- If state contains a "goal", the goal outranks the route: finish exactly that goal, then stop. Do not advance to the next split to look productive.
- When the goal (or the whole run) is complete, return {"done":true} with a one-line why. If the goal is impossible with the current inventory and no reachable resources, return {"done":true,"why":"blocked: ..."}.

You receive:
1. state: compact observation (inventory, nearby blocks/entities, danger, route split, timer).
2. calculators: deterministic math (portal target, eye count, barter EV, triangulation). Trust these numbers; never compute them yourself.
3. last: the previous skill and its result.
4. available skills: the ONLY actions you may choose.

Reply with exactly one JSON object:
{"split":"<id>","skill":{"name":"<registry name>","args":{...}},"fallback":{"name":"<registry name>","args":{...}},"why":"<=200 chars, concrete","risk":"low|medium|high","memory":"<=120 chars worth keeping","done":false}

Rules for the reply:
- "skill.name" must be one of the registry names. Args must match. Omit args you do not need.
- Prefer continuing the current split over jumping ahead. Only change split when the state proves it.
- If the state shows danger (lava<=3, low hp, hostiles close), the skill must be eat/flee/attack before progress.
- If the last skill failed twice, change approach instead of retrying the same call.
- No prose outside the JSON. No markdown.`

function skillsBlock () {
  return Object.entries(REGISTRY)
    .map(([name, v]) => `- ${name}(${Object.entries(v.args).map(([k, t]) => `${k}:${t}`).join(', ')}): ${v.desc}`)
    .join('\n')
}

function validate (plan) {
  if (!plan || typeof plan !== 'object') return { ok: false, error: 'not an object' }
  const pick = p => {
    if (!p || typeof p !== 'object') return null
    const name = p.name || p.skill
    if (!REGISTRY[name]) return null
    const args = (p.args && typeof p.args === 'object') ? p.args : {}
    return { name, args }
  }
  const skill = pick(plan.skill)
  if (!skill) return { ok: false, error: `unknown skill: ${JSON.stringify(plan.skill)}` }
  return {
    ok: true,
    plan: {
      split: typeof plan.split === 'string' ? plan.split : null,
      skill,
      fallback: pick(plan.fallback),
      done: plan.done === true,
      why: String(plan.why || '').slice(0, 240),
      risk: ['low', 'medium', 'high'].includes(plan.risk) ? plan.risk : 'medium',
      memory: String(plan.memory || '').slice(0, 140)
    }
  }
}

async function plan ({ state, compact, route, calculators, last, memory = [] }) {
  const user = [
    `state:\n${compact}`,
    `route: ${JSON.stringify(route)}`,
    calculators ? `calculators: ${JSON.stringify(calculators)}` : null,
    last ? `last: ${JSON.stringify(last)}` : 'last: none',
    memory.length ? `memory: ${memory.slice(-6).join(' | ')}` : null,
    `available skills:\n${skillsBlock()}`
  ].filter(Boolean).join('\n\n')

  const t0 = Date.now()
  const res = await chat({
    provider: config.models.planner.provider,
    model: config.models.planner.model,
    effort: config.models.planner.effort,
    maxTokens: config.models.planner.maxTokens,
    temperature: 0.15,
    system: SYSTEM,
    messages: [{ role: 'user', content: user }],
    purpose: 'planner'
  })
  const v = validate(res.json)
  if (!v.ok) {
    const retry = await chat({
      provider: config.models.planner.provider,
      model: config.models.planner.model,
      effort: 'low',
      maxTokens: 500,
      temperature: 0,
      system: SYSTEM,
      messages: [
        { role: 'user', content: user },
        { role: 'assistant', content: JSON.stringify(res.json || {}) },
        { role: 'user', content: `Invalid: ${v.error}. Reply again with a valid JSON object using only registry skill names.` }
      ],
      purpose: 'planner_retry'
    })
    const v2 = validate(retry.json)
    if (!v2.ok) throw new Error(`planner invalid twice: ${v2.error}`)
    return { ...v2.plan, ms: Date.now() - t0, model: res.model, usage: res.usage }
  }
  return { ...v.plan, ms: Date.now() - t0, model: res.model, usage: res.usage }
}

module.exports = { plan, SYSTEM, skillsBlock, validate }
