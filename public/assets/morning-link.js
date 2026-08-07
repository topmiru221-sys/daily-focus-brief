document.addEventListener("DOMContentLoaded",()=>{
  const n=document.querySelector(".quick-nav");
  if(n && !n.querySelector('a[href="./morning.html"]')){
    const a=document.createElement("a");
    a.href="./morning.html";
    a.textContent="晨報";
    n.insertBefore(a,n.firstChild);
  }
});