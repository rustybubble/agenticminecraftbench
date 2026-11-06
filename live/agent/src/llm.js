// Minimal OpenAI-compatible chat client for the two decision layers.
// - deepseek: planner + classifier (cheap, ~1.3s at effort=low)
// - nvidia:   free-tier classifier fallback (bolt-e4b ~0.5s)
// Every call is timed and appended to logs/llm.jsonl so latency/cost is evidence, not vibes.
const fs = require('fs')
const path = require('path')
const config = require('./config')

const PROVIDERS = {
  deepseek: {
    base: 'https://api.deepseek.com/v1',
    key: () => process.env.DEEPSEEK_API_KEY,
    supportsEffort: true
  },
  nvidia: {
    base: 'https://integrate.api.nvidia.com/v1',
    key: () => process.env.NVIDIA_API_KEY,
    supportsEffort: false
  },
  openai: {
    base: 'https://api.openai.com/v1',
    key: () => process.env.YC_OPENAI_API_KEY || process.env.OPENAI_API_KEY,
    supportsEffort: false,
    effortParam: 'reasoning_effort'
  },
  anthropic: {
    base: 'https://api.anthropic.com/v1',
    key: () => process.env.YC_ANTHROPIC_API_KEY || process.env.ANTHROPIC_API_KEY,
    anthropic: true
  }
}

function logCall (rec) {
  try {
    fs.mkdirSync(config.paths.logs, { recursive: true })
    fs.appendFileSync(path.join(config.paths.logs, 'llm.jsonl'), JSON.stringify(rec) + '\n')
  } catch {}
}

// Models answer with prose or fenced JSON even when asked for JSON; recover the first object.
function extractJson (text) {
  if (!text) return null
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/)
  const candidates = []
  if (fenced) candidates.push(fenced[1])
  candidates.push(text)
  for (const c of candidates) {
    const start = c.indexOf('{')
    if (start === -1) continue
    let depth = 0, inStr = false, esc = false
    for (let i = start; i < c.length; i++) {
      const ch = c[i]
      if (inStr) {
        if (esc) esc = false
        else if (ch === '\\') esc = true
        else if (ch === '"') inStr = false
        continue
      }
      if (ch === '"') inStr = true
      else if (ch === '{') depth++
      else if (ch === '}') {
        depth--
        if (depth === 0) {
          try { return JSON.parse(c.slice(start, i + 1)) } catch { break }
        }
      }
    }
  }
  return null
}

const sleep = ms => new Promise(r => setTimeout(r, ms))

async function chat ({
  provider, model, system, messages = [], temperature = 0.2,
  maxTokens = 800, effort, json = true, purpose = 'unknown', timeoutMs = 45000
}) {
  const p = PROVIDERS[provider]
  if (!p) throw new Error(`unknown provider ${provider}`)
  const key = p.key()
  if (!key) throw new Error(`missing API key for ${provider} (set ${provider === 'deepseek' ? 'DEEPSEEK_API_KEY' : 'NVIDIA_API_KEY'})`)

  const body = {
    model,
    messages: [
      ...(system ? [{ role: 'system', content: system }] : []),
      ...messages
    ],
    temperature,
    max_tokens: maxTokens
  }
  if (p.supportsEffort && effort) body.effort = effort
  if (p.effortParam && effort) body[p.effortParam] = effort
  if (json && !p.anthropic) body.response_format = { type: 'json_object' }
  if (p.anthropic) {
    body.system = system || undefined
    body.messages = messages
    body.max_tokens = maxTokens
    delete body.temperature // claude-haiku-5-5 rejects it
  }
  if (provider === 'openai') {
    body.max_completion_tokens = maxTokens
    delete body.max_tokens
    if (body.reasoning_effort) delete body.temperature // gpt-5.x only accepts the default
  }

  let lastErr
  for (let attempt = 0; attempt < 3; attempt++) {
    const t0 = Date.now()
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), timeoutMs)
      const headers = p.anthropic
        ? { 'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01' }
        : { 'content-type': 'application/json', authorization: `Bearer ${key}` }
      const res = await fetch(p.anthropic ? `${p.base}/messages` : `${p.base}/chat/completions`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: ctrl.signal
      })
      clearTimeout(timer)
      const text = await res.text()
      const ms = Date.now() - t0
      if (!res.ok) {
        lastErr = new Error(`${provider} ${res.status}: ${text.slice(0, 300)}`)
        if (res.status === 429 || res.status >= 500) { await sleep(600 * (attempt + 1)); continue }
        throw lastErr
      }
      let data
      try { data = JSON.parse(text) } catch { throw new Error(`${provider} non-JSON envelope: ${text.slice(0, 200)}`) }
      const msg = data.choices?.[0]?.message || {}
      const content = p.anthropic
        ? (data.content || []).map(c => c.text || '').join('')
        : (msg.content || '')
      const parsed = json ? extractJson(content) : null
      const rec = {
        ts: new Date().toISOString(), purpose, provider, model, ms,
        usage: data.usage || null,
        ok: !!(content && (!json || parsed)),
        jsonOk: json ? !!parsed : null,
        contentPreview: String(content).slice(0, 400)
      }
      logCall(rec)
      if (json && !parsed) {
        lastErr = new Error(`${provider} returned no parsable JSON: ${content.slice(0, 200)}`)
        await sleep(300)
        continue
      }
      const usage = p.anthropic
        ? { prompt_tokens: data.usage?.input_tokens, completion_tokens: data.usage?.output_tokens, total_tokens: (data.usage?.input_tokens || 0) + (data.usage?.output_tokens || 0) }
        : (data.usage || null)
      return { text: content, json: parsed, ms, usage, model, provider }
    } catch (err) {
      lastErr = err
      logCall({ ts: new Date().toISOString(), purpose, provider, model, ok: false, error: String(err.message).slice(0, 300) })
      await sleep(500 * (attempt + 1))
    }
  }
  throw lastErr
}

module.exports = { chat, extractJson, PROVIDERS }
