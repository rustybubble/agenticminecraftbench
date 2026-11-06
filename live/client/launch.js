#!/usr/bin/env node
// Direct Minecraft 1.16.5 client launch, used because Prism auto-substitutes the arm64
// ("mmachina") LWJGL 3.3.1 build for 1.16.5 even when the instance pins 3.2.2, and that mix
// crashes the client at chunk tessellation on this Mac ("Tesselating block in world").
// This launcher uses the official 1.16.5 version JSON with x86_64 LWJGL 3.2.2 + Temurin 8,
// the same instance game directory and the same asset store as Prism.
//
//   node live/client/launch.js --server 127.0.0.1 --port 25576 --user thugshakerbob
const fs = require('fs')
const path = require('path')
const os = require('os')
const https = require('https')
const { spawn } = require('child_process')
const { execFileSync } = require('child_process')

const args = {}
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1]

const username = args.user || 'Player'
const server = args.server || '127.0.0.1'
const port = args.port || '25576'
const root = path.join(__dirname, '..', '..')
const cache = path.join(root, 'live', 'client', '.cache')
const nativesDir = path.join(cache, 'natives')
const gameDir = path.join(os.homedir(), 'Library/Application Support/PrismLauncher/instances/1.16.5/minecraft')
const assetsDir = path.join(os.homedir(), 'Library/Application Support/PrismLauncher/assets')
const java = path.join(root, 'live', 'java', 'jdk8u504-b01', 'Contents', 'Home', 'bin', 'java')

const VERSION_URL = 'https://piston-meta.mojang.com/v1/packages/fba9f7833e858a1257d810d21a3a9e3c967f9077/1.16.5.json'

const download = (url, file) => new Promise((resolve, reject) => {
  if (fs.existsSync(file) && fs.statSync(file).size > 0) return resolve(file)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  const tmp = file + '.part'
  const out = fs.createWriteStream(tmp)
  https.get(url, res => {
    if (res.statusCode === 301 || res.statusCode === 302) {
      res.resume(); return download(res.headers.location, file).then(resolve, reject)
    }
    if (res.statusCode !== 200) { res.resume(); return reject(new Error(`${res.statusCode} ${url}`)) }
    res.pipe(out)
    out.on('finish', () => { out.close(() => { fs.renameSync(tmp, file); resolve(file) }) })
  }).on('error', reject)
})

// The Prism account file holds the MSA profile + token. Vanilla only needs a non-empty session
// to enable the Multiplayer button; our server is offline-mode so nothing verifies the token.
function readAccount (username, usePrism) {
  if (!usePrism) return { uuid: '00000000000000000000000000000000', token: '0', userType: 'legacy' }
  const file = path.join(os.homedir(), 'Library/Application Support/PrismLauncher/accounts.json')
  const data = JSON.parse(fs.readFileSync(file, 'utf8'))
  const acc = (data.accounts || []).find(a => a.profile && a.profile.name === username) || data.accounts?.[0]
  if (!acc || !acc.profile) throw new Error('no Prism account found')
  return { uuid: acc.profile.id, token: acc.msa?.token || '0', userType: 'msa' }
}

async function main () {
  const versionFile = path.join(cache, '1.16.5.json')
  if (!fs.existsSync(versionFile)) {
    await download(VERSION_URL, versionFile)
  }
  const v = JSON.parse(fs.readFileSync(versionFile, 'utf8'))
  const libs = []
  const natives = []
  for (const lib of v.libraries) {
    const rules = lib.rules || []
    const allowed = rules.length === 0 || rules.some(r => r.action === 'allow' && (!r.os || r.os.name === 'osx'))
    if (!allowed) continue
    if (lib.downloads?.artifact?.path) {
      const f = path.join(cache, 'libs', lib.downloads.artifact.path)
      await download(lib.downloads.artifact.url, f)
      libs.push(f)
    }
    const nat = lib.downloads?.classifiers?.['natives-macos']
    if (nat) {
      const f = path.join(cache, 'libs', nat.path)
      await download(nat.url, f)
      natives.push(f)
    }
  }
  fs.mkdirSync(nativesDir, { recursive: true })
  for (const n of natives) {
    try { execFileSync('unzip', ['-o', '-q', n, '-d', nativesDir]) } catch {}
  }
  const clientJar = path.join(cache, '1.16.5-client.jar')
  await download(v.downloads.client.url, clientJar)
  libs.push(clientJar)

  const account = readAccount(username, args.auth === 'prism')
  const cp = libs.join(':')
  const jvm = [
    '-XstartOnFirstThread', '-Xms1G', '-Xmx3G',
    `-Djava.library.path=${nativesDir}`,
    '-Dorg.lwjgl.util.Debug=false',
    '-cp', cp, 'net.minecraft.client.main.Main',
    '--username', username,
    '--version', '1.16.5',
    '--gameDir', gameDir,
    '--assetsDir', assetsDir,
    '--assetIndex', v.assetIndex.id,
    '--uuid', account.uuid,
    '--accessToken', account.token,
    '--userType', account.userType,
    '--server', server,
    '--port', port
  ]
  fs.mkdirSync(gameDir, { recursive: true })
  console.log(`launching MC 1.16.5 as ${username} -> ${server}:${port}`)
  const log = fs.openSync('/tmp/mcclient.log', 'a')
  const child = spawn(java, jvm, { cwd: gameDir, stdio: ['ignore', log, log], detached: true })
  child.unref()
  fs.writeFileSync('/tmp/mcclient.pid', String(child.pid))
  console.log(`pid ${child.pid}, log /tmp/mcclient.log`)
}

main().catch(e => { console.error(e); process.exit(1) })
