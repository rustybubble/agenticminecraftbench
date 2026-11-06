// Central config. Secrets are read from ~/.pi/agent/secrets.env when not already in env;
// nothing is written back to disk. Never log key material.
const fs = require('fs')
const path = require('path')
const os = require('os')

function loadSecrets () {
  const f = path.join(os.homedir(), '.pi/agent/secrets.env')
  if (!fs.existsSync(f)) return
  for (const line of fs.readFileSync(f, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/)
    if (!m) continue
    if (!process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '')
  }
}
loadSecrets()

const num = (v, d) => (v === undefined || v === '' ? d : Number(v))

const config = {
  mc: {
    host: process.env.MC_HOST || '127.0.0.1',
    port: num(process.env.MC_PORT, 25576),
    username: process.env.MC_USER || 'SplitAgent',
    version: process.env.MC_VERSION || '1.16.5',
    auth: 'offline'
  },
  models: {
    // Strategic planner: judgment, route branching, risk. DeepSeek 4.1 Flash (no v4-pro:
    // slower, pricier and no better on this task). Claude/GPT can be swapped in via env.
    planner: {
      provider: process.env.PLANNER_PROVIDER || 'deepseek',
      model: process.env.PLANNER_MODEL || 'deepseek-flash',
      effort: process.env.PLANNER_EFFORT || 'low',
      maxTokens: num(process.env.PLANNER_MAX_TOKENS, 1200)
    },
    // Action classifier: short-horizon "what should I do right now", high frequency.
    // GPU-free free tier: NVIDIA NIM, ~0.7s for this prompt. DeepSeek Flash is the fallback.
    classifier: {
      provider: process.env.CLASSIFIER_PROVIDER || 'nvidia',
      model: process.env.CLASSIFIER_MODEL || 'nvidia/nemotron-3.5-bolt-e4b',
      effort: process.env.CLASSIFIER_EFFORT || undefined,
      maxTokens: num(process.env.CLASSIFIER_MAX_TOKENS, 160)
    }
  },
  loop: {
    tickMs: num(process.env.TICK_MS, 1000),
    plannerEveryMs: num(process.env.PLANNER_EVERY_MS, 25000),
    minPlanGapMs: num(process.env.MIN_PLAN_GAP_MS, 6000),
    reflexMs: num(process.env.REFLEX_MS, 250),
    skillTimeoutMs: num(process.env.SKILL_TIMEOUT_MS, 120000),
    maxIdleSkills: num(process.env.MAX_IDLE_SKILLS, 40)
  },
  paths: {
    root: path.join(__dirname, '..'),
    // run artifacts live in the repo's runs/live/<id>/ so events.jsonl (agent claims) and
    // server.jsonl (server truth) sit side by side for the Layer B evaluator.
    runs: path.join(__dirname, '..', '..', '..', 'runs', 'live'),
    logs: path.join(__dirname, '..', 'logs')
  },
  // Seed survey values for 8398967436125155523 (rmalde/minecraft-agent optimization/nether/*survey.json).
  // Used only when the world actually uses that seed; otherwise the planner must discover.
  seed: process.env.MC_SEED || '8398967436125155523',
  survey: {
    village: { x: -225, y: 71, z: 255 },
    entryPortal: { x: -285, y: 67, z: 259 },
    netherExit: { x: -141, y: 40, z: 104 },
    endPortal: { x: -1130, y: 34, z: 856 },
    chests: { obsidian: 21, ironPickaxe: true, flint: true }
  }
}

module.exports = config
