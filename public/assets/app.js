const fmt=new Intl.NumberFormat('zh-TW',{maximumFractionDigits:2});
const state={};let inst=null;
const tone=v=>v>0?'positive':v<0?'negative':'neutral';
async function load(name){try{const r=await fetch(`./data/${name}.json`,{cache:'no-store'});if(!r.ok)throw new Error(`${r.status}`);state[name]=await r.json();return state[name]}catch(e){state[name]={status:'error',error:String(e)};return state[name]}}
function renderDates(meta){
 const map=meta?.module_dates||{};const names={market:'市場',institutional:'法人',sectors:'族群',capital_flow:'資金',research:'研究池',flow_persistence:'持續度',playbook:'市場劇本'};
 moduleDates.innerHTML=Object.keys(names).map(k=>`<div class="date-item"><span class="muted">${names[k]}</span><strong>${map[k]||'待更新'}</strong></div>`).join('');
}
function renderMarket(m){
 const verdict=m?.verdict||'待更新';marketBadge.textContent=verdict;marketBadge.className='market-badge '+(verdict==='偏多'?'positive':verdict==='偏空'?'negative':'neutral');
 marketStatus.textContent=m?.status||'待更新';marketSummary.textContent=verdict==='待更新'?'目前可核對訊號不足，等待完整資料。':`市場方向初判：${verdict}`;
 marketSignals.innerHTML=(m?.signals||[]).map(x=>`<div class="signal"><span>${x.name}</span><strong class="${tone(x.score)}">${fmt.format(x.value)} ${x.unit||''}</strong></div>`).join('')||'<div class="signal"><span>訊號</span><strong>待更新</strong></div>';
 warnings.innerHTML=(m?.warnings||[]).map(x=>`<div>⚠ ${x}</div>`).join('');
}
function renderCoverage(i){
 const c=i?.coverage||{};coverage.innerHTML=[['上市筆數',c.twse_rows],['上櫃筆數',c.tpex_rows],['合計解析',c.parsed_rows],['全市場覆蓋',c.full_market_coverage?'是':'否']].map(([a,b])=>`<div class="metric"><span class="muted">${a}</span><strong>${b??'待更新'}</strong></div>`).join('');
}
function fallbackFlow(sectors){
 return (sectors?.rankings||[]).map((s,idx)=>({rank:idx+1,sector_name:s.name,flow_score:Math.max(0,Math.min(100,50+(Number(s.average_change_pct)||0)*5+((Number(s.advance_ratio_pct)||50)-50)*.25)),flow_state:'由族群資料即時計算',leaders:s.representatives||[]})).sort((a,b)=>b.flow_score-a.flow_score);
}
function renderFlow(flow,sectors){
 let rows=flow?.rankings||[];if(!rows.length)rows=fallbackFlow(sectors);
 const item=x=>`<div class="flow-row"><div><strong>${x.rank||'-'}. ${x.sector_name||'待更新'}</strong><small>${x.flow_state||''}${(x.leaders||[]).length?'｜'+x.leaders.slice(0,3).map(v=>v.name||v.code).join('、'):''}</small></div><div class="flow-score">${fmt.format(x.flow_score??0)}</div></div>`;
 inflowList.innerHTML=rows.slice(0,5).map(item).join('')||'待更新';outflowList.innerHTML=[...rows].sort((a,b)=>(a.flow_score??0)-(b.flow_score??0)).slice(0,5).map(item).join('')||'待更新';
 flowStatus.textContent=flow?.status==='ok'?'資料已連線':'使用族群回退計算';
}
function fallbackResearch(sectors){
 const arr=[];(sectors?.rankings||[]).slice(0,5).forEach(s=>(s.representatives||[]).slice(0,3).forEach(v=>arr.push({code:v.code,name:v.name,market:v.market,score:Math.min(99,60+(Number(v.change_pct)||0)*4),sectors:[s.name],reasons:[`${s.name} 族群排名前段`,`當日漲跌 ${fmt.format(v.change_pct||0)}%`],risk_flags:(Number(v.change_pct)||0)>=8?['當日漲幅偏大，追價風險提高']:[]})));return arr.sort((a,b)=>b.score-a.score).slice(0,10);
}
function renderResearch(r,sectors){
 const rows=(r?.research_pool||[]).length?r.research_pool:fallbackResearch(sectors);
 researchGrid.innerHTML=rows.map(x=>`<article class="research-card"><div class="card-top"><div><p class="eyebrow">${x.market||''} ${x.code||''}</p><h3>${x.name||x.code||'待更新'}</h3></div><div class="score">${fmt.format(x.score||0)}</div></div><p class="muted">${[...new Set(x.sectors||[])].join('／')}</p><div class="reason-list">${[...new Set(x.reasons||[])].slice(0,3).join('<br>')}</div>${(x.risk_flags||[]).map(v=>`<div class="risk-flag">⚠ ${v}</div>`).join('')}<p><a class="chip link-chip" href="./stock-risk.html?code=${encodeURIComponent(x.code||'')}">建立風險計畫</a></p></article>`).join('')||'<article class="panel">目前無符合門檻標的。</article>';
}
function renderSectors(s){
 sectorGrid.innerHTML=(s?.rankings||[]).slice(0,12).map(x=>`<article class="sector-card"><div class="card-top"><div><p class="eyebrow">#${x.rank||'-'}</p><h3>${x.name}</h3></div><div class="score ${tone(x.average_change_pct)}">${x.average_change_pct==null?'—':fmt.format(x.average_change_pct)+'%'}</div></div><div class="mini-grid"><div class="mini">上漲比例<strong>${x.advance_ratio_pct==null?'—':fmt.format(x.advance_ratio_pct)+'%'}</strong></div><div class="mini">強勢股<strong>${x.strong_stock_count??'—'}</strong></div><div class="mini">站上20MA<strong>${x.above_20ma_ratio_pct==null?'—':fmt.format(x.above_20ma_ratio_pct)+'%'}</strong></div><div class="mini">站上60MA<strong>${x.above_60ma_ratio_pct==null?'—':fmt.format(x.above_60ma_ratio_pct)+'%'}</strong></div></div><p class="muted">${x.classification||''}</p></article>`).join('')||'<article class="panel">族群資料待更新。</article>';
}
function renderPersistence(p){
 const target=document.getElementById('persistenceGrid');if(!target)return;
 const rows=p?.rankings||[];
 target.innerHTML=rows.slice(0,8).map(x=>`<article class="sector-card"><div class="card-top"><div><p class="eyebrow">#${x.rank}</p><h3>${x.sector_name}</h3></div><div class="score">${fmt.format(x.average_score)}</div></div><div class="mini-grid"><div class="mini">有效天數<strong>${x.effective_days}/${p.requested_trading_days||5}</strong></div><div class="mini">持續比例<strong>${fmt.format(x.persistence_ratio_pct)}%</strong></div><div class="mini">最新分數<strong>${fmt.format(x.latest_score)}</strong></div><div class="mini">分數變化<strong class="${tone(x.score_change)}">${x.score_change>0?'+':''}${fmt.format(x.score_change)}</strong></div></div><p class="muted">${x.state}</p>${x.current_leader?`<div class="reason-list">目前領先：${x.current_leader.name||x.current_leader.code}${x.leadership_change?'（龍頭更換）':''}</div>`:''}</article>`).join('')||'<article class="panel">歷史資料累積中。</article>';
}
function renderPlaybook(p){
 const h=document.getElementById('playbookHeadline'),c=document.getElementById('changedList'),rot=document.getElementById('rotationSummary');if(!h)return;
 h.textContent=p?.headline||'市場劇本待更新。';
 c.innerHTML=(p?.what_changed_today||[]).map((x,i)=>`<div class="signal"><span>${i+1}</span><strong>${x}</strong></div>`).join('')||'<div class="signal">尚無足夠變化資料。</div>';
 const r=p?.rotation_summary||{};rot.innerHTML=`<div class="metric"><span class="muted">相對轉弱</span><strong>${(r.from||[]).join('、')||'待更新'}</strong></div><div class="metric"><span class="muted">相對流入</span><strong>${(r.to||[]).join('、')||'待更新'}</strong></div>`;
}
function renderInst(key){
 institutionalTable.innerHTML=(inst?.rankings?.[key]||[]).slice(0,50).map(x=>`<tr><td>${x.rank}</td><td>${x.market}</td><td>${x.code}</td><td>${x.name}</td><td class="${tone(x.net_lots)}">${fmt.format(x.net_lots)}</td></tr>`).join('')||'<tr><td colspan="5">法人資料待更新</td></tr>';
}
(async()=>{
 await Promise.all(['market','institutional','sectors','capital_flow','research','flow_persistence','playbook','meta'].map(load));
 const m=state.market||{},i=state.institutional||{},s=state.sectors||{},f=state.capital_flow||{},r=state.research||{},p=state.flow_persistence||{},pb=state.playbook||{},meta=state.meta||{};
 inst=i;renderMarket(m);renderCoverage(i);renderDates(meta);renderFlow(f,s);renderResearch(r,s);renderSectors(s);renderPersistence(p);renderPlaybook(pb);renderInst('foreign_buy_top50');
 document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');renderInst(b.dataset.tab)});
 updatedAt.textContent=`網站更新：${meta.generated_at||'待更新'}｜最新資料：${meta.latest_available_data_date||meta.data_date||'待更新'}`;
})();
