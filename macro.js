const LEVEL={critical:"重大",high:"高",medium:"中"};
async function loadMacroEvents(){try{const r=await fetch("./data/macro_events.json?ts="+Date.now());return await r.json()}catch(e){return {events:[]}}}
function macroFmt(ms){if(ms<=0)return"已公布";const d=Math.floor(ms/864e5),h=Math.floor(ms%864e5/36e5),m=Math.floor(ms%36e5/6e4);return d?`${d} 天 ${h} 小時後`:h?`${h} 小時 ${m} 分後`:`${m} 分鐘後`;}
function eventRisk(ms,l){if(ms<=864e5&&l==="critical")return"🔴 24H 重大事件風險";if(ms<=1728e5&&(l==="critical"||l==="high"))return"🟠 48H 事件風險";return"🟢 無近端重大事件";}
async function renderMacro(){
  const d=await loadMacroEvents(),now=Date.now(),a=(d.events||[]).filter(e=>new Date(e.date)>now).sort((x,y)=>new Date(x.date)-new Date(y.date)),n=a[0],box=document.querySelector("#events");
  if(box)box.innerHTML=a.map(e=>{const t=new Date(e.date);return `<div class="event ${e.level}"><div class="event-date">${t.toLocaleDateString("zh-TW",{month:"2-digit",day:"2-digit"})}<br><span class="tag">${t.toLocaleTimeString("zh-TW",{hour:"2-digit",minute:"2-digit"})}</span></div><div><div class="event-title">${e.title}</div><div class="impact">${LEVEL[e.level]}｜${e.source}｜可能影響：${e.impact}</div></div><div class="countdown">${macroFmt(t-now)}</div></div>`}).join("");
  const title=document.querySelector("#nextTitle"),countdown=document.querySelector("#nextCountdown"),impact=document.querySelector("#nextImpact");
  if(n&&title&&countdown&&impact){const ms=new Date(n.date)-now;title.textContent=n.title;countdown.textContent=macroFmt(ms);impact.textContent=`${eventRisk(ms,n.level)}｜可能影響：${n.impact}`;}
  const updated=document.querySelector("#updated");if(updated)updated.textContent="事件資料："+d.generated_at;
}
renderMacro();setInterval(renderMacro,60000);
