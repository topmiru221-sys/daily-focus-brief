const fmt=new Intl.NumberFormat("zh-TW",{maximumFractionDigits:2});
async function getJson(path){const r=await fetch(path,{cache:"no-store"});if(!r.ok)throw new Error(`${path}: ${r.status}`);return r.json()}
function tone(v){return v>0?"positive":v<0?"negative":"neutral"}
function renderMarket(m){
 const b=document.getElementById("marketBadge"),s=document.getElementById("marketStatus"),q=document.getElementById("marketSummary"),g=document.getElementById("marketSignals");
 const v=m?.verdict||"待更新";b.textContent=v;s.textContent=m?.status||"待更新";b.className="market-badge "+(v==="偏多"?"positive":v==="偏空"?"negative":"neutral");
 q.textContent=v==="待更新"?"目前可核對訊號不足，維持待更新。":`市場方向初判為「${v}」，信心層級：${m.confidence||"待確認"}。`;
 g.innerHTML="";for(const x of m?.signals||[]){const d=document.createElement("div");d.className="signal";d.innerHTML=`<span>${x.name}</span><strong class="${tone(x.score)}">${fmt.format(x.value)} ${x.unit||""}</strong>`;g.appendChild(d)}
 document.getElementById("warnings").innerHTML=(m?.warnings||[]).map(x=>`<div>⚠ ${x}</div>`).join("")
}
function renderCoverage(i){const c=i?.coverage||{};document.getElementById("coverage").innerHTML=`
<div class="metric"><span class="muted">上市筆數</span><strong>${c.twse_rows??"待更新"}</strong></div>
<div class="metric"><span class="muted">上櫃筆數</span><strong>${c.tpex_rows??"待更新"}</strong></div>
<div class="metric"><span class="muted">合計解析</span><strong>${c.parsed_rows??"待更新"}</strong></div>
<div class="metric"><span class="muted">全市場覆蓋</span><strong>${c.full_market_coverage?"是":"否"}</strong></div>`}
function renderSectors(s){const root=document.getElementById("sectorGrid");root.innerHTML="";
 for(const x of (s?.rankings||[]).slice(0,9)){const c=document.createElement("article");c.className="sector-card";const reps=(x.representatives||[]).map(r=>`${r.name||r.code} ${fmt.format(r.change_pct)}%`).join("、");
 c.innerHTML=`<div class="sector-top"><div><div class="eyebrow">#${x.rank||"-"}</div><h3>${x.name}</h3></div><div class="sector-change ${tone(x.average_change_pct)}">${x.average_change_pct==null?"待更新":fmt.format(x.average_change_pct)+"%"}</div></div>
 <div class="sector-meta"><div class="mini">上漲比例<strong>${x.advance_ratio_pct==null?"待更新":fmt.format(x.advance_ratio_pct)+"%"}</strong></div><div class="mini">強勢股數<strong>${x.strong_stock_count??"待更新"}</strong></div><div class="mini">站上20MA<strong>${x.above_20ma_ratio_pct==null?"待更新":fmt.format(x.above_20ma_ratio_pct)+"%"}</strong></div><div class="mini">站上60MA<strong>${x.above_60ma_ratio_pct==null?"待更新":fmt.format(x.above_60ma_ratio_pct)+"%"}</strong></div></div><div class="pill">${x.classification||"待更新"}</div><p class="rep-list">${reps||"代表股待更新"}</p>`;root.appendChild(c)}}
let institutionalData=null;
function renderInstitutional(k){const rows=institutionalData?.rankings?.[k]||[];document.getElementById("institutionalTable").innerHTML=rows.slice(0,50).map(r=>`<tr><td>${r.rank}</td><td>${r.market}</td><td>${r.code}</td><td>${r.name}</td><td class="${tone(r.net_lots)}">${fmt.format(r.net_lots)}</td></tr>`).join("")}
async function init(){try{const [m,i,s,meta]=await Promise.all([getJson("./data/market.json"),getJson("./data/institutional.json"),getJson("./data/sectors.json"),getJson("./data/meta.json")]);institutionalData=i;renderMarket(m);renderCoverage(i);renderSectors(s);renderInstitutional("foreign_buy_top50");document.getElementById("updatedAt").textContent=`資料日期：${meta.data_date||"待更新"}｜網站更新：${meta.generated_at||"待更新"}`;document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");renderInstitutional(b.dataset.tab)}))}catch(e){document.getElementById("updatedAt").textContent=`載入失敗：${e.message}`}}
init();