const API_PORT=8090;
const apiBase=()=>location.protocol+"//"+location.hostname+":"+API_PORT;
function showPage(id){
 document.querySelectorAll(".page").forEach(p=>p.classList.remove("active-page"));
 document.getElementById(id).classList.add("active-page");
 document.querySelectorAll(".sidebar a").forEach(a=>a.classList.remove("active"));
 const map={dashboard:0,files:1,cameras:2,backups:3,status:4};
 document.querySelectorAll(".sidebar a")[map[id]].classList.add("active");
 document.getElementById("page-title").textContent={dashboard:"Dashboard",files:"Arquivos",cameras:"Câmeras",backups:"Backups",status:"Sistema"}[id];
 if(id==="files") loadFiles("files","file-list");
 if(id==="cameras") loadFiles("cameras","camera-list");
 if(id==="backups") loadFiles("backups","backup-list");
}
async function loadStatus(){
 try{
  let d=await (await fetch(apiBase()+"/api/status?"+Date.now())).json();
  ["ip","nginx","api","disk","used","camera_files","updated","python"].forEach(id=>{let e=document.getElementById(id); if(e)e.textContent=d[id]||"..."});
  let fc=document.getElementById("files_count"); if(fc) fc.textContent=d.files||"0";
  let bc=document.getElementById("backup_files"); if(bc) bc.textContent=d.backup_files||"0";
  let raw=document.getElementById("raw-status"); if(raw) raw.textContent=JSON.stringify(d,null,2);
  let bar=document.getElementById("disk-bar"); if(bar) bar.style.width=(parseInt((d.used||"0").replace("%",""))||0)+"%";
 }catch(e){console.log(e)}
}
async function loadFiles(area,id){
 let el=document.getElementById(id); el.innerHTML="Carregando...";
 try{
  let d=await (await fetch(apiBase()+"/api/files?area="+area+"&"+Date.now())).json();
  if(!d.items.length){el.innerHTML="<p>Nenhum arquivo.</p>";return;}
  el.innerHTML=d.items.map(i=>fileRow(area,i)).join("");
 }catch(e){el.innerHTML="<p>API parada. Rode: bash scripts/start_api.sh</p>"}
}
function fileRow(area,i){
 let icon=i.type==="folder"?"📁":i.media==="image"?"🖼️":i.media==="video"?"🎥":i.media==="pdf"?"📕":"📄";
 let view=(i.media==="image"||i.media==="video"||i.media==="pdf")?`<button onclick="previewFile('${area}','${i.name}','${i.media}')">Ver</button>`:"";
 return `<div class="file-item"><div><strong>${icon} ${i.name}</strong><small>${formatSize(i.size)}</small></div><span>${view}<button onclick="downloadFile('${area}','${i.name}')">Baixar</button><button onclick="renameFile('${area}','${i.name}')">Renomear</button><button class="danger" onclick="deleteFile('${area}','${i.name}')">Excluir</button></span></div>`;
}
async function uploadFile(area,inputId){
 let input=document.getElementById(inputId); if(!input.files.length) return alert("Escolha um arquivo");
 for(const file of input.files){let form=new FormData(); form.append("file",file); await fetch(apiBase()+"/api/upload?area="+area,{method:"POST",body:form});}
 input.value=""; loadFiles(area, area==="files"?"file-list":"camera-list"); loadStatus();
}
function downloadFile(area,name){window.open(apiBase()+"/api/download?area="+area+"&name="+encodeURIComponent(name));}
function previewFile(area,name,media){
 const url=apiBase()+"/api/view?area="+area+"&name="+encodeURIComponent(name); let html="";
 if(media==="image") html=`<img src="${url}" class="preview-media">`;
 else if(media==="video") html=`<video src="${url}" controls class="preview-media"></video>`;
 else html=`<iframe src="${url}" class="preview-frame"></iframe>`;
 document.getElementById("modal-body").innerHTML=html; document.getElementById("modal-title").textContent=name; document.getElementById("modal").classList.add("show");
}
function closeModal(){document.getElementById("modal").classList.remove("show");}
async function renameFile(area,name){let novo=prompt("Novo nome:",name); if(!novo||novo===name)return; await fetch(apiBase()+"/api/rename?area="+area+"&old="+encodeURIComponent(name)+"&new="+encodeURIComponent(novo),{method:"POST"}); loadFiles(area,area==="files"?"file-list":area==="cameras"?"camera-list":"backup-list");}
async function deleteFile(area,name){if(!confirm("Mover para lixeira: "+name+"?"))return; await fetch(apiBase()+"/api/delete?area="+area+"&name="+encodeURIComponent(name),{method:"DELETE"}); loadFiles(area,area==="files"?"file-list":area==="cameras"?"camera-list":"backup-list"); loadStatus();}
async function createBackup(){await fetch(apiBase()+"/api/backup",{method:"POST"}); loadFiles("backups","backup-list"); loadStatus(); alert("Backup criado.");}
function formatSize(b){if(b<1024)return b+" B"; if(b<1048576)return(b/1024).toFixed(1)+" KB"; if(b<1073741824)return(b/1048576).toFixed(1)+" MB"; return(b/1073741824).toFixed(1)+" GB";}
loadStatus(); setInterval(loadStatus,30000);
