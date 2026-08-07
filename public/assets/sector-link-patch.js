(async()=>{
  try{
    const r=await fetch('./data/sectors.json',{cache:'no-store'});
    const data=await r.json();
    const idByName=new Map((data.rankings||[]).map(x=>[x.name,x.id]));
    const grid=document.getElementById('sectorGrid');
    if(!grid)return;
    const apply=()=>{
      grid.querySelectorAll('.sector-card').forEach(card=>{
        if(card.querySelector('.sector-center-link'))return;
        const name=card.querySelector('h3')?.textContent?.trim();
        const id=idByName.get(name);
        if(!id)return;
        const p=document.createElement('p');
        p.innerHTML=`<a class="chip link-chip sector-center-link" href="./sector.html?id=${encodeURIComponent(id)}">查看概念股與風險</a>`;
        card.appendChild(p);
      });
    };
    new MutationObserver(apply).observe(grid,{childList:true,subtree:true});
    apply();
  }catch(e){console.warn('sector link patch failed',e)}
})();
