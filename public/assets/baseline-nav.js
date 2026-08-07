document.addEventListener("DOMContentLoaded",()=>{
 const nav=document.querySelector(".quick-nav"); if(!nav)return;
 const wanted=[["./morning.html","晨報"],["./market.html","Market"],["./institution.html","Institution"],["./sector.html","Sector"],["#research","Research"],["./decision.html","Decision"],["./development.html","Development"]];
 wanted.reverse().forEach(([href,label])=>{if(!nav.querySelector(`a[href="${href}"]`)){const a=document.createElement("a");a.href=href;a.textContent=label;nav.insertBefore(a,nav.firstChild)}});
});