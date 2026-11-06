// Minimal Source RCON client (no dependencies). Used by the telemetry logger to read
// server-authoritative player state, so a run's evidence does not depend on the agent's claims.
//
// Vanilla splits a long command reply (e.g. a 36-slot Inventory) across several RCON packets,
// so a reply is collected until no new packet arrives for FLUSH_MS. Resolving on the first
// packet desynchronizes the queue and silently truncates inventory.
const net = require('net')
const FLUSH_MS = 8

class Rcon {
  constructor ({ host = '127.0.0.1', port = 25575, password = 'splitcheck-live', timeoutMs = 8000 } = {}) {
    Object.assign(this, { host, port, password, timeoutMs })
    this.id = 0
    this.buf = Buffer.alloc(0)
    this.current = null
  }

  connect () {
    return new Promise((resolve, reject) => {
      this.sock = net.connect(this.port, this.host)
      this.sock.once('connect', async () => {
        try {
          const res = await this.send(3, this.password)
          if (res.id === -1) return reject(new Error('rcon auth failed'))
          resolve(this)
        } catch (e) { reject(e) }
      })
      this.sock.once('error', reject)
      this.sock.on('data', d => {
        this.buf = Buffer.concat([this.buf, d])
        while (this.buf.length >= 4) {
          const len = this.buf.readInt32LE(0)
          if (this.buf.length < 4 + len) break
          const id = this.buf.readInt32LE(4)
          const type = this.buf.readInt32LE(8)
          const body = this.buf.subarray(12, 4 + len - 2).toString('utf8')
          this.buf = this.buf.subarray(4 + len)
          if (this.current) {
            this.current.id = id
            this.current.type = type
            this.current.chunks.push(body)
            const joined = this.current.chunks.join('')
            // /data get replies are one complete value; flush as soon as it looks whole.
            if (/[}\]]\s*$|^Found no elements|data:\s*-?[\d.]+f?\s*$|"[^"]*"\s*$/.test(joined)) {
              this.flush()
            } else {
              clearTimeout(this.current.flushTimer)
              this.current.flushTimer = setTimeout(() => this.flush(), FLUSH_MS)
            }
          }
        }
      })
    })
  }

  flush () {
    const c = this.current
    if (!c) return
    this.current = null
    clearTimeout(c.timer)
    clearTimeout(c.flushTimer)
    c.resolve({ id: c.id, type: c.type, body: c.chunks.join('') })
  }

  send (type, body) {
    return new Promise((resolve, reject) => {
      const id = ++this.id
      const b = Buffer.from(body, 'utf8')
      const pkt = Buffer.alloc(14 + b.length)
      pkt.writeInt32LE(10 + b.length, 0)
      pkt.writeInt32LE(id, 4)
      pkt.writeInt32LE(type, 8)
      b.copy(pkt, 12)
      this.current = {
        id, chunks: [], resolve, reject,
        timer: setTimeout(() => { this.current = null; reject(new Error(`rcon timeout: ${body}`)) }, this.timeoutMs)
      }
      this.sock.write(pkt)
    })
  }

  async cmd (command) {
    const r = await this.send(2, command)
    return r.body
  }

  close () { try { this.sock.end() } catch {} }
}

// --- parsers for vanilla /data get output ---------------------------------
function parsePos (s) {
  const m = s.match(/\[(-?[\d.]+)d?,\s*(-?[\d.]+)d?,\s*(-?[\d.]+)d?\]/)
  return m ? { x: +m[1], y: +m[2], z: +m[3] } : null
}
function parseNumber (s) {
  const m = s.match(/(?:data:|-?\d)\s*(-?\d+(?:\.\d+)?)/)
  if (m) return Number(m[1])
  const n = s.match(/(-?\d+(?:\.\d+)?)/)
  return n ? Number(n[1]) : null
}
function parseDimension (s) {
  const m = s.match(/"minecraft:([a-z_]+)"/)
  return m ? m[1] : null
}
function parseInventory (s) {
  const items = {}
  const re = /id:\s*"minecraft:([a-z0-9_]+)",\s*Count:\s*(\d+)b/g
  let m
  while ((m = re.exec(s))) items[m[1]] = (items[m[1]] || 0) + Number(m[2])
  return { items, truncated: !/\]\s*$/.test(s.trim()) }
}

module.exports = { Rcon, parsePos, parseNumber, parseDimension, parseInventory }
