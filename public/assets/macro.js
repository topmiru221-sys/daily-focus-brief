const EVENTS=[
{date:"2026-08-20T20:30:00+08:00",title:"美國初領失業救濟金",level:"medium",impact:"美元／美債殖利率／成長股"},
{date:"2026-08-21T22:00:00+08:00",title:"美國既有房屋銷售",level:"medium",impact:"景氣敏感／利率預期"},
{date:"2026-08-27T20:30:00+08:00",title:"美國 GDP 修正值",level:"high",impact:"美元／美債／全球風險資產"},
{date:"2026-08-28T20:30:00+08:00",title:"美國 PCE / 核心 PCE",level:"critical",impact:"Fed 利率路徑／科技成長股"},
{date:"2026-09-04T20:30:00+08:00",title:"美國非農就業報告",level:"critical",impact:"美元／美債／全球股市"},
{date:"2026-09-16T00:00:00+08:00",title:"台指期月結算窗口",level:"high",impact:"台股現貨／期貨／大型權值股"},
{date:"2026-09-17T02:00:00+08:00",title:"FOMC 利率決策（時間待官方最終確認）",level:"critical",impact:"全球流動性／科技股／美元"},
{date:"2026-09-17T14:00:00+08:00",title:"台灣央行理監事會（日期待官方確認）",level:"high",impact:"台幣／金融／房市敏感族群"}
];
function fmt(ms){if(ms<=0)return"已公布";const d=Math.floor(ms/864e5),h=Math.floor(ms%864e5/36e5);return d?`${d} 天 ${h} 小時後`:`${h} 小時內`;}
function render(){const now=Date.now(), future=EVENTS.filter(e=>new Date(e.date).getTime()>=now-864e5).sort((a,b)=>new Date(a.date)-new Date(b.date));const box=document.querySelector("#events");
box.innerHTML=future.map(e=>{const t=new Date(e.date);return `<div class="event ${e.level}"><div class="event-date">${t.toLocaleDateString("zh-TW",{month:"2-digit",day:"2-digit"})}<br><span class="tag">${t.toLocaleTimeString("zh-TW",{hour:"2-digit",minute:"2-digit"})}</span></div><div><div class="event-title">${e.title}</div><div class="impact">可能影響：${e.impact}</div></div><div class="countdown">${fmt(t-Date.now())}</div></div>`}).join("");
const n=future[0];if(n){document.querySelector("#nextTitle").textContent=n.title;document.querySelector("#nextCountdown").textContent=fmt(new Date(n.date)-Date.now());document.querySelector("#nextImpact").textContent="可能影響："+n.impact}}
render();setInterval(render,60000);