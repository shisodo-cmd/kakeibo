const KEY="simple-kakeibo-v1";
let items=JSON.parse(localStorage.getItem(KEY)||"[]");
let viewMonth=new Date(); viewMonth.setDate(1);
let analysisMode="category";
const $=id=>document.getElementById(id);
const yen=n=>"¥"+Number(n||0).toLocaleString("ja-JP");
const ym=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
const itemYM=x=>x.date.slice(0,7);
function save(){localStorage.setItem(KEY,JSON.stringify(items));render()}
function current(){return items.filter(x=>itemYM(x)===ym(viewMonth))}
function group(arr,key){return arr.reduce((a,x)=>{a[x[key]]=(a[x[key]]||0)+Number(x.amount);return a},{})}
function monthText(){return `${viewMonth.getFullYear()}年${viewMonth.getMonth()+1}月`}
function row(x){
 const d=document.createElement("div");d.className="row";
 d.innerHTML=`<div><b>${esc(x.merchant)}</b><div class="meta">${x.date} · ${esc(x.category)} · ${esc(x.payment)}</div></div><div class="amount">${yen(x.amount)}</div><div class="meta">${esc(x.memo||"")}</div><button class="delete">削除</button>`;
 d.querySelector(".delete").onclick=()=>{if(confirm("この支出を削除しますか？")){items=items.filter(i=>i.id!==x.id);save()}};
 return d
}
function esc(s){const d=document.createElement("div");d.textContent=s;return d.innerHTML}
function render(){
 $("monthLabel").textContent=monthText();
 const arr=current(), total=arr.reduce((s,x)=>s+Number(x.amount),0);
 $("monthTotal").textContent=yen(total);
 const prev=new Date(viewMonth);prev.setMonth(prev.getMonth()-1);
 const pt=items.filter(x=>itemYM(x)===ym(prev)).reduce((s,x)=>s+Number(x.amount),0);
 $("monthCompare").textContent=pt?`先月比 ${total>=pt?"+":""}${Math.round((total-pt)/pt*100)}%`:"先月との比較 —";
 const gs=Object.entries(group(arr,"category")).sort((a,b)=>b[1]-a[1]);
 $("categorySummary").innerHTML="";
 gs.slice(0,6).forEach(([k,v])=>{const d=document.createElement("div");d.className="row";d.innerHTML=`<div><b>${esc(k)}</b></div><div class="amount">${yen(v)}</div>`;$("categorySummary").append(d)});
 if(!gs.length)$("categorySummary").innerHTML='<div class="empty">まだ支出がありません</div>';
 const recent=[...arr].sort((a,b)=>b.date.localeCompare(a.date)||b.id-a.id).slice(0,5);
 $("recentList").innerHTML="";recent.forEach(x=>$("recentList").append(row(x)));
 if(!recent.length)$("recentList").innerHTML='<div class="empty">入力タブから支出を登録できます</div>';
 renderHistory();renderAnalysis()
}
function renderHistory(){
 const q=$("search").value.toLowerCase(),c=$("filterCategory").value,p=$("filterPayment").value;
 const arr=[...items].filter(x=>(!q||(x.merchant+" "+x.memo).toLowerCase().includes(q))&&(!c||x.category===c)&&(!p||x.payment===p)).sort((a,b)=>b.date.localeCompare(a.date)||b.id-a.id);
 $("historyList").innerHTML="";arr.forEach(x=>$("historyList").append(row(x)));
 if(!arr.length)$("historyList").innerHTML='<div class="empty">該当する支出はありません</div>'
}
function renderAnalysis(){
 const arr=current(),total=arr.reduce((s,x)=>s+Number(x.amount),0);$("analysisTotal").textContent=`合計 ${yen(total)}`;
 const data=Object.entries(group(arr,analysisMode)).sort((a,b)=>b[1]-a[1]);$("analysisBars").innerHTML="";
 data.forEach(([k,v])=>{const d=document.createElement("div");d.className="barLine";d.innerHTML=`<span>${esc(k)}</span><div class="track"><div class="fill" style="width:${total?v/total*100:0}%"></div></div><b>${yen(v)}</b>`;$("analysisBars").append(d)});
 if(!data.length)$("analysisBars").innerHTML='<div class="empty">分析するデータがありません</div>'
}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll("nav button,.page").forEach(e=>e.classList.remove("active"));b.classList.add("active");$(b.dataset.page).classList.add("active");$("pageTitle").textContent={home:"ホーム",input:"支出入力",history:"履歴",analysis:"分析"}[b.dataset.page]});
$("expenseForm").onsubmit=e=>{e.preventDefault();items.push({id:Date.now(),date:$("date").value,amount:Number($("amount").value),merchant:$("merchant").value.trim(),category:$("category").value,payment:$("payment").value,memo:$("memo").value.trim()});save();e.target.reset();$("date").value=new Date().toISOString().slice(0,10);document.querySelector('nav button[data-page="home"]').click()};
$("monthBtn").onclick=e=>{const r=e.currentTarget.getBoundingClientRect();viewMonth.setMonth(viewMonth.getMonth()+(e.clientX>r.left+r.width/2?1:-1));render()};
["search","filterCategory","filterPayment"].forEach(id=>$(id).oninput=renderHistory);
document.querySelectorAll(".analysisTab").forEach(b=>b.onclick=()=>{document.querySelectorAll(".analysisTab").forEach(x=>x.classList.remove("active"));b.classList.add("active");analysisMode=b.dataset.mode;renderAnalysis()});
["食費","日用品","交通","外食","教育","医療","娯楽","住居","その他"].forEach(v=>$("filterCategory").add(new Option(v,v)));
["クレジットカード","現金","電子マネー","口座振替","その他"].forEach(v=>$("filterPayment").add(new Option(v,v)));
$("date").value=new Date().toISOString().slice(0,10);render();