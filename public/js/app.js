const API_PORT=8090;
const apiBase=()=>location.protocol+"//"+location.hostname+":"+API_PORT;

function showPage(id){
 document.querySelectorAll(".page").forEach(p=>p.classList.remove("active-page"));
 document.getElementById(id).classList.add("active-page");
 document.querySelectorAll(".sidebar a").forEach(a=>a.classList.remove("active"));
 const map={dashboard:0,files:1,cameras:2,backups:3,status:4};
 document.querySelectorAll(".sidebar a")[map[id]].classList.add("active");
 document.getElementById("page-title").textContent={dashboard:"Dashboard",files:"Arquivos",cameras:"Câmeras",backups:"Backups",status:"Status"}[id];
 if(id==="files") loadFiles("files","file-list");
 if(id==="cameras") loadFiles("cameras","camera-list");
 if(id==="backups") loadFiles("backups","backup-list");
}

async function loadStatus(){
 try{
  let r=await fetch(apiBase()+"/api/status?"+Date.now());
  let d=await r.json();
  ["ip","nginx","api","disk","used","camera_files","updated"].forEach(id=>{let e=document.getElementById(id); if(e)e.textContent=d[id]||"..."});
  let fc=document.getElementById("files_count"); if(fc) fc.textContent=d.files||"0";
  let raw=document.getElementById("raw-status"); if(raw) raw.textContent=JSON.stringify(d,null,2);
 }catch(e){console.log(e)}
}

async function loadFiles(area,id){
 let el=document.getElementById(id); el.innerHTML="Carregando...";
 try{
  let r=await fetch(apiBase()+"/api/files?area="+area+"&"+Date.now());
  let d=await r.json();
  if(!d.items.length){el.innerHTML="<p>Nenhum arquivo.</p>";return;}
  el.innerHTML=d.items.map(i=>`<div class="file-item"><strong>${i.type==="folder"?"📁":"📄"} ${i.name}</strong><span>${formatSize(i.size)}</span><span><button onclick="downloadFile('${area}','${i.name}')">Baixar</button><button onclick="deleteFile('${area}','${i.name}')">Excluir</button></span></div>`).join("");
 }catch(e){el.innerHTML="<p>API parada. Rode: bash scripts/start_api.sh</p>"}
}

async function uploadFile(area,inputId){
 let input=document.getElementById(inputId);
 if(!input.files.length) return alert("Escolha um arquivo");
 let form=new FormData(); form.append("file",input.files[0]);
 await fetch(apiBase()+"/api/upload?area="+area,{method:"POST",body:form});
 input.value="";
 loadFiles(area, area==="files"?"file-list":"camera-list");
 loadStatus();
}

function downloadFile(area,name){ window.open(apiBase()+"/api/download?area="+area+"&name="+encodeURIComponent(name)); }

async function deleteFile(area,name){
 if(!confirm("Excluir "+name+"?")) return;
 await fetch(apiBase()+"/api/delete?area="+area+"&name="+encodeURIComponent(name),{method:"DELETE"});
 loadFiles(area, area==="files"?"file-list":area==="cameras"?"camera-list":"backup-list");
 loadStatus();
}

function formatSize(b){if(b<1024)return b+" B"; if(b<1048576)return(b/1024).toFixed(1)+" KB"; if(b<1073741824)return(b/1048576).toFixed(1)+" MB"; return(b/1073741824).toFixed(1)+" GB";}
loadStatus(); setInterval(loadStatus,30000);
