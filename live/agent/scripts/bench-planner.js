const { chat } = require('../src/llm')
const { SYSTEM, skillsBlock } = require('../src/planner')
const compact = `dim=overworld pos=-211.7,72,226.5 t=9871(day) hp=20 food=20 held=wooden_pickaxe
inv[10]: oak_logx4, oak_planksx3, wooden_pickaxex1, crafting_tablex1
near: logs@2.8 craftTable@0.6 counts: dirt:337 stone:110
hostiles: none; danger: clear
goal: craft a stone pickaxe`
const user = `state:\n${compact}\n\nroute: {"split":"stone","targetS":60,"elapsedS":45}\n\navailable skills:\n${skillsBlock()}`
const cases = [
  ['deepseek','deepseek-flash','low',1200],
  ['anthropic','claude-haiku-5-5',undefined,700],
  ['openai','gpt-5.4-mini','low',700]
]
;(async()=>{
 for (const [provider,model,effort,maxTokens] of cases) {
   const t0=Date.now()
   try{
     const r = await chat({provider,model,effort,maxTokens,temperature:0.1,system:SYSTEM,messages:[{role:'user',content:user}],purpose:'bench-planner'})
     console.log(provider,model,'->',Date.now()-t0,'ms','json',!!r.json,'skill',r.json&&r.json.skill&&r.json.skill.name,'tok',r.usage&&r.usage.completion_tokens)
   }catch(e){console.log(provider,model,'ERR',String(e.message).slice(0,160),Date.now()-t0)}
 }
})()
