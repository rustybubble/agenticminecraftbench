const { chat } = require('../src/llm')
const { ALLOWED_BY_SPLIT } = require('../src/router')
const { REGISTRY } = require('../src/skills')
const SYSTEM = `You are the reflex-policy classifier for a Minecraft 1.16.1 speedrun bot. Output the single best immediate action from the allowed list. Reply with exactly one JSON object: {"skill":{"name":"<allowed>","args":{...}},"why":"<=80 chars","urgency":"low|normal|high"}`
const blocks = s => (ALLOWED_BY_SPLIT[s]||[]).map(n=>`- ${n}(${Object.entries(REGISTRY[n].args).map(([k,t])=>`${k}:${t}`).join(', ')}): ${REGISTRY[n].desc}`).join('\n')
const cases = [
 {split:'wood', compact:`dim=overworld pos=-211,72,226 hp=20 food=20 held=none\ninv[0]: empty\nnear: logs@2.8 counts: oak_log:24 stone:110\nhostiles: none; danger: clear`},
 {split:'stone', compact:`dim=overworld pos=-211,72,226 hp=20 food=20 held=wooden_pickaxe\ninv[4]: oak_logx2, stickx4, wooden_pickaxex1\nnear: stone@3 counts: stone:80\nhostiles: zombie@5; danger: clear`},
 {split:'portal', compact:`dim=overworld pos=-285,67,259 hp=14 food=12 held=bucket\ninv[6]: iron_ingotx3, bucketx1, flint_and_steelx1\nnear: lava@40 water@6 obsidian@2 counts: obsidian:3\nhostiles: none; danger: clear`}
]
;(async()=>{
 for (const [provider,model,maxTokens] of [['nvidia','nvidia/nemotron-3.5-bolt-e4b',160],['deepseek','deepseek-flash',500]]) {
  for (const c of cases) {
   const t0=Date.now()
   try{
     const r = await chat({provider,model,effort:'low',maxTokens,temperature:0.1,system:SYSTEM,
       messages:[{role:'user',content:`state:\n${c.compact}\nsplit: ${c.split}\nallowed:\n${blocks(c.split)}`}],purpose:'bench-clf'})
     console.log(model,c.split,'->',Date.now()-t0,'ms',JSON.stringify(r.json))
   }catch(e){console.log(model,c.split,'ERR',String(e.message).slice(0,100),Date.now()-t0)}
  }
 }
})()
