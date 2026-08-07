
const DFB = {
  stamp: ()=>Date.now(),
  async load(name){
    try{
      const r=await fetch(`./data/${name}.json?v=${Date.now()}`,{cache:'no-store'});
      if(!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    }catch(e){ return {status:"missing", error:e.message}; }
  },
  dateOf(x){ return x?.data_date||x?.run_date||x?.latest_available_data_date||"待更新"; },
  genOf(x){ return x?.generated_at||"待更新"; },
  state(x){
    if(!x || x.status==="missing" || x.status==="error") return ["🟡","待接／尚無資料"];
    if(x.status==="ok") return ["🟢","已更新"];
    return ["🟡",x.status||"部分資料"];
  },
  fmt(v,d=2){ return v==null||Number.isNaN(Number(v))?"—":Number(v).toLocaleString("zh-TW",{maximumFractionDigits:d}); }
};
