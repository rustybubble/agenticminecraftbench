const { chat } = require('../src/llm')
const { SYSTEM, skillsBlock } = require('../src/planner')
const compact = `dim=overworld pos=-211.7,72,226.5 t=9871(day) hp=20 food=20 held=wooden_pickaxe
inv[10]: oak_logx4, oak_planksx3, wooden_pickaxex1, crafting_tablex1
near: logs@2.8 craftTable@0.6 counts: dirt:337 stone:110
hostiles: none; danger: clear
goal: craft a wooden pickaxe`
const user = `state:\n${compact}\n\nroute: {"split":"stone","targetS":60,"elapsedS":45}\n\navailable skills:\n${skillsBlock()}`
;(async()=>{
 for (const [model, effort, maxTokens] of [
   ['deepseek-flash','low',500],['deepseek-flash','low',900]
 ]) {
   const t0=Date.now()
   try{
     const r = await chat({provider:'deepseek',model,effort,maxTokens,temperature:0.1,system:SYSTEM,messages:[{role:'user',content:user}],purpose:'bench'})
     console.log(model,effort,maxTokens,'->',Date.now()-t0,'ms','json?',!!r.json, 'skill', r.json&&r.json.skill&&r.json.skill.name, 'usage', r.usage&&r.usage.completion_tokens)
   }catch(e){console.log(model,'ERR',String(e.message).slice(0,120), Date.now()-t0)}
 }
})()
