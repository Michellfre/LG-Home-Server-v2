const API_PORT = 8090;
const apiBase = () => location.protocol + "//" + location.hostname + ":" + API_PORT;
let lastNetworkDevices = [];
let discoveryTimer = null;

function el(id){ return document.getElementById(id); }
function setText(id, value){ const e = el(id); if(e) e.textContent = value ?? ""; }
function setHTML(id, value){ const e = el(id); if(e) e.innerHTML = value ?? ""; }
function toast(t){ const e=el("toast"); if(!e) return; e.textContent=t; e.style.display="block"; setTimeout(()=>e.style.display="none",3000); }
function speak(t){ try{ speechSynthesis.cancel(); const u=new SpeechSynthesisUtterance(t); u.lang="pt-BR"; speechSynthesis.speak(u); }catch(e){} }
function pct(v){ return parseInt(String(v||"0").replace("%",""))||0; }
function setBar(id,v){ const e=el(id); if(e){ e.style.width=Math.max(0,Math.min(100,v))+"%"; e.className=v>85?"bad":v>65?"warn":""; } }
function icon(t){ return t==="door"?"🚪":t==="temperature_humidity"?"🌡️":t==="motion"?"🏃":t==="light"?"💡":t==="plug"?"🔌":t==="switch"?"🔘":t==="camera"?"📹":t==="mqtt"?"📡":t==="printer"?"🖨️":t==="chromecast"?"📺":t==="pc_nas"?"💻":t==="home_assistant"?"🏠":t==="open_home_os"?"🟢":t==="esp32"?"🧩":t==="raspberry"?"🍓":"📡"; }

async function safeJson(url,opt={}){
  const r = await fetch(url,opt);
  if(!r.ok) throw new Error(await r.text());
  return await r.json();
}

function showPage(id){
  document.querySelectorAll(".page").forEach(p=>p.classList.remove("active-page"));
  const page = el(id); if(page) page.classList.add("active-page");
  document.querySelectorAll(".sidebar a").forEach(a=>a.classList.remove("active"));
  const order={dashboard:0,connect:1,rooms:2,setup:3,jarvis:4,network:5,cameras:6,tv:7,system:8};
  if(order[id]!=null && document.querySelectorAll(".sidebar a")[order[id]]) document.querySelectorAll(".sidebar a")[order[id]].classList.add("active");
  setText("page-title",{dashboard:"Dashboard Inteligente",connect:"Open Home Connect",rooms:"Ambientes",setup:"Assistente de Instalação",jarvis:"Jarvis",network:"Open Home Discovery Engine",cameras:"Camera Manager",tv:"TV Mode",system:"Sistema",notifications:"Notificações"}[id]||"Open Home OS");
  if(id==="connect") loadDevices();
  if(id==="rooms") loadRooms();
  if(id==="setup") loadTuyaConfig();
  if(id==="jarvis") loadJarvis();
  if(id==="network") loadNetwork();
  if(id==="cameras") loadCameraManager();
  if(id==="system") diag();
  if(id==="notifications") loadNotifications();
  loadStatus();
}

async function loadStatus(){
  try{
    const d = await safeJson(apiBase()+"/api/status?"+Date.now());
    const h = await safeJson(apiBase()+"/api/house?"+Date.now());
    setText("ip", d.ip);
    setText("disk", d.disk);
    setText("sdcard", d.sdcard);
    setText("sd-extra", d.storage?.sdcard?.mount || d.storage?.sdcard?.message || "");
    setText("health", d.health+"%");
    setText("health-label", d.health>=90?"saúde excelente":d.health>=75?"atenção leve":"atenção");
    setText("house-message", h.message);
    setText("env-temp", d.connect.avg_temperature!==null?d.connect.avg_temperature+"°C":"sem dados");
    setText("env-hum", d.connect.avg_humidity!==null?d.connect.avg_humidity+"%":"sem dados");
    setText("wifi", d.wifi);
    setText("dev-total", d.connect.total);
    setText("dev-online", d.connect.online);
    setText("open-doors", d.connect.open_doors);
    setText("discovered", (d.network&&d.network.count)||0);
    setBar("disk-bar", pct(d.used));
    renderDeviceCards(d.connect.devices||[]);
    if(el("tv-clock")){
      setText("tv-clock", new Date().toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"}));
      setText("tv-health", d.health+"%");
      setText("tv-devs", d.connect.online+"/"+d.connect.total);
      setText("tv-env", d.connect.avg_temperature!==null?d.connect.avg_temperature+"°C":"sem dados");
      setText("tv-hum", d.connect.avg_humidity!==null?d.connect.avg_humidity+"%":"sem dados");
      setText("tv-doors", d.connect.open_doors);
      setText("tv-sd", d.sdcard);
    }
    loadEvents();
    loadNotifyCount();
  }catch(e){ console.log(e); }
}

function renderDeviceCards(items){
  setHTML("device-cards", items.length ? items.slice(0,12).map(d=>`<div class="module"><h3>${icon(d.type)} ${d.name}</h3><p>${d.online?"Online":"Offline"}</p><small>${d.ip?("IP "+d.ip+" • "):""}${d.room||""} ${d.temperature!==""?("• "+d.temperature+"°C"):""} ${d.humidity!==""?("• "+d.humidity+"%"):""} ${d.battery!==""?("• Bat "+d.battery+"%"):""}</small></div>`).join("") : "<p>Nenhum dispositivo cadastrado.</p>");
}

async function loadNotifyCount(){
  try{ const d=await safeJson(apiBase()+"/api/notifications?"+Date.now()); setText("notify-count",(d.items||[]).length); }catch(e){}
}

async function loadEvents(){
  try{
    const d=await safeJson(apiBase()+"/api/events?"+Date.now());
    setHTML("events",(d.items||[]).slice(0,8).map(e=>`<div class="note"><div><b>${e.kind}</b><br><small>${e.time} • ${e.module} • ${e.message}</small></div><span>${e.level}</span></div>`).join("")||"<p>Sem eventos.</p>");
  }catch(e){}
}

async function loadDevices(){
  const d=await safeJson(apiBase()+"/api/connect/devices?"+Date.now());
  setHTML("device-list",(d.items||[]).map(x=>`<div class="module"><h3>${icon(x.type)} ${x.name}</h3><p>${x.online?"Online":"Offline"}</p><small>${x.source||"manual"} • ${x.room||""}<br>${x.ip?("IP "+x.ip+"<br>"):""}Temp ${x.temperature||"--"}°C • Umid ${x.humidity||"--"}% • Bat ${x.battery||"--"}%</small><br><button onclick="editDevice('${x.id}','${x.temperature||""}','${x.humidity||""}','${x.battery||""}')">Atualizar</button><button class="danger" onclick="deleteDevice('${x.id}')">Excluir</button></div>`).join("")||"<p>Nenhum dispositivo.</p>");
}

async function addDevice(){
  const data={name:el("dev-name")?.value,room:el("dev-room")?.value,type:el("dev-type")?.value,temperature:el("dev-temp")?.value,humidity:el("dev-hum")?.value,battery:el("dev-bat")?.value};
  await fetch(apiBase()+"/api/connect/device/add",{method:"POST",body:JSON.stringify(data)});
  loadDevices(); loadStatus(); toast("Dispositivo adicionado");
}

async function editDevice(id,t,h,b){
  const nt=prompt("Temperatura:",t); if(nt===null) return;
  const nh=prompt("Umidade:",h); if(nh===null) return;
  const nb=prompt("Bateria:",b);
  await fetch(apiBase()+"/api/connect/device/update",{method:"POST",body:JSON.stringify({id,temperature:nt,humidity:nh,battery:nb})});
  loadDevices(); loadStatus();
}

async function deleteDevice(id){
  if(!confirm("Excluir dispositivo?")) return;
  await fetch(apiBase()+"/api/connect/device/delete",{method:"POST",body:JSON.stringify({id})});
  loadDevices(); loadStatus();
}

async function loadRooms(){
  const d=await safeJson(apiBase()+"/api/connect/rooms?"+Date.now());
  setHTML("rooms-list",(d.items||[]).map(r=>`<div class="module"><h3>🏘️ ${r.name}</h3><p>${r.online}/${r.devices} online</p><small>Temp ${r.avg_temperature??"--"}°C • Umid ${r.avg_humidity??"--"}% • Portas abertas ${r.doors_open}</small></div>`).join("")||"<p>Nenhum ambiente com dispositivos.</p>");
}

async function loadTuyaConfig(){
  const c=await safeJson(apiBase()+"/api/connect/tuya/config");
  if(el("tuya-client")) el("tuya-client").value=c.client_id||"";
  if(el("tuya-secret")) el("tuya-secret").value=c.client_secret||"";
  if(el("tuya-dc")) el("tuya-dc").value=c.data_center||"https://openapi.tuyaus.com";
  if(el("tuya-asset")) el("tuya-asset").value=c.asset_id||"";
  setText("setup-result",JSON.stringify({enabled:c.enabled,last_sync:c.last_sync,data_center:c.data_center},null,2));
}

function tuyaPayload(){
  return {enabled:true,client_id:el("tuya-client")?.value,client_secret:el("tuya-secret")?.value,data_center:el("tuya-dc")?.value,asset_id:el("tuya-asset")?.value};
}

async function saveTuya(){
  const r=await safeJson(apiBase()+"/api/connect/tuya/config",{method:"POST",body:JSON.stringify(tuyaPayload())});
  setText("setup-result",JSON.stringify(r,null,2)); toast("Configuração salva");
}
async function testTuya(){
  const r=await safeJson(apiBase()+"/api/connect/tuya/test",{method:"POST",body:JSON.stringify(tuyaPayload())});
  setText("setup-result",JSON.stringify(r,null,2)); toast(r.message);
}
async function syncTuya(){
  const r=await safeJson(apiBase()+"/api/connect/tuya/sync",{method:"POST",body:"{}"});
  setText("setup-result",JSON.stringify(r,null,2)); loadStatus(); loadDevices(); toast(r.ok?`Sincronizado: ${r.count} dispositivos`:"Falha na sincronização");
}

async function startDiscovery(){
  try{
    setHTML("network-list","<p>Busca iniciada...</p>");
    setText("discovery-message","Iniciando descoberta...");
    const bar=el("discovery-progress"); if(bar) bar.style.width="3%";
    await safeJson(apiBase()+"/api/discovery/start",{method:"POST",body:JSON.stringify({limit:254})});
    toast("Discovery iniciado");
    if(discoveryTimer) clearInterval(discoveryTimer);
    discoveryTimer=setInterval(loadDiscoveryState,900);
    loadDiscoveryState();
  }catch(e){ toast("Erro ao iniciar: "+e.message); }
}

async function loadDiscoveryState(){
  try{
    const s=await safeJson(apiBase()+"/api/discovery/state?"+Date.now());
    const bar=el("discovery-progress"); if(bar) bar.style.width=(s.progress||0)+"%";
    setText("discovery-message",s.message||"Aguardando...");
    lastNetworkDevices=s.devices||[];
    renderDiscoverySummary(s);
    renderNetwork(lastNetworkDevices);
    if(!s.running && discoveryTimer){
      clearInterval(discoveryTimer);
      discoveryTimer=null;
      loadStatus();
      toast("Discovery concluído");
    }
  }catch(e){ console.log(e); }
}

async function loadNetwork(){
  try{
    const d=await safeJson(apiBase()+"/api/discovery?"+Date.now());
    lastNetworkDevices=d.devices||[];
    const bar=el("discovery-progress"); if(bar) bar.style.width=(d.progress||100)+"%";
    setText("discovery-message",d.last_scan?`Última busca: ${d.last_scan}`:"Nenhuma busca ainda.");
    renderDiscoverySummary(d);
    renderNetwork(lastNetworkDevices);
  }catch(e){ toast("Erro ao atualizar: "+e.message); }
}

function renderDiscoverySummary(d){
  const sum=d.summary||{};
  setHTML("network-summary",`<div>Rede<b>${d.network||"--"}</b></div><div>Gateway<b>${d.gateway||"--"}</b></div><div>Encontrados<b>${d.count||0}</b></div><div>Câmeras<b>${sum.camera||0}</b></div><div>PC/NAS<b>${sum.pc_nas||0}</b></div><div>Web<b>${sum.web_device||0}</b></div><div>Impressoras<b>${sum.printer||0}</b></div>`);
}

function filteredNetwork(items){
  const f=el("discovery-filter")?.value||"";
  const q=(el("discovery-search")?.value||"").toLowerCase();
  return (items||[]).filter(x=>(!f||x.type===f)&&(!q||JSON.stringify(x).toLowerCase().includes(q)));
}

function renderNetwork(items){
  const filtered=filteredNetwork(items||[]);
  setHTML("network-list",filtered.length?filtered.map((x,i)=>{
    const isCamera=x.type==="camera"||(x.ports||[]).includes(554);
    const webPort=(x.ports||[]).find(p=>[80,81,443,8080,8090,8123].includes(p));
    const primary=isCamera
      ? `<button class="ok" onclick="openCameraSetup(${i})">📹 Configurar câmera</button><button class="ghost" onclick="analyzeCamera(${i})">Diagnosticar</button>`
      : `<button class="ok" onclick="importDiscovered(${i})">Adicionar ao Open Home</button>`;
    const webButton=webPort?`<button class="ghost" onclick="openDevice('${x.ip}',${webPort})">Abrir interface Web</button>`:"";
    return `<div class="module"><h3>${icon(x.type)} ${x.name}</h3><p>${x.ip}</p><span class="device-type">${x.type}</span><br><small>${x.vendor||"Fabricante não identificado"}<br>Confiança ${x.confidence||0}%<br>Portas: ${(x.ports||[]).join(", ")||"--"}<br>Serviços: ${(x.services||[]).join(", ")||"--"}</small><br>${primary}${webButton}</div>`;
  }).join(""):"<p>Nenhum dispositivo encontrado para esse filtro.</p>");
}

function openDevice(ip,port){
  const scheme=port==443?"https":"http";
  window.open(`${scheme}://${ip}:${port}`,"_blank");
}

async function importDiscovered(index){
  const filtered=filteredNetwork(lastNetworkDevices||[]);
  const dev=filtered[index];
  if(!dev) return;
  const room=prompt("Ambiente para este dispositivo:",dev.room||"Rede")||"Rede";
  const r=await safeJson(apiBase()+"/api/discovery/device/import",{method:"POST",body:JSON.stringify({device:dev,room})});
  toast(r.ok?"Adicionado ao Open Home Connect":"Falha ao adicionar");
  loadStatus();
}

async function loadJarvis(){
  const d=await safeJson(apiBase()+"/api/jarvis");
  setHTML("jarvis-history",(d.history||[]).map(h=>`<div class="note"><div><b>${h.command}</b><br><small>${h.time} • ${h.reply}</small></div><span>${h.action}</span></div>`).join("")||"<p>Sem histórico.</p>");
}

async function sendJarvis(){
  const cmd=el("jarvis-input")?.value||"";
  const r=await safeJson(apiBase()+"/api/jarvis/command",{method:"POST",body:JSON.stringify({command:cmd})});
  setText("jarvis-reply",r.reply);
  speak(r.reply);
  if(el("jarvis-input")) el("jarvis-input").value="";
  loadJarvis();
  if(r.action==="open_connect") showPage("connect");
  if(r.action==="open_dashboard") showPage("dashboard");
  if(r.action==="open_setup") showPage("setup");
  if(r.action==="open_network") showPage("network");
}
function quick(t){ if(el("jarvis-input")) el("jarvis-input").value=t; sendJarvis(); }
function startVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){ alert("Reconhecimento de voz não suportado."); return; }
  const rec=new SR(); rec.lang="pt-BR";
  rec.onresult=e=>{ if(el("jarvis-input")) el("jarvis-input").value=e.results[0][0].transcript; sendJarvis(); };
  rec.start(); toast("Jarvis ouvindo...");
}

async function createBackup(){
  const r=await safeJson(apiBase()+"/api/backup",{method:"POST",body:"{}"});
  toast("Backup criado: "+r.file); loadStatus();
}
async function diag(){
  const d=await safeJson(apiBase()+"/api/system/diagnostic?"+Date.now());
  setText("diagnostic",JSON.stringify(d,null,2));
}
async function loadNotifications(){
  const d=await safeJson(apiBase()+"/api/notifications?"+Date.now());
  setHTML("notifications-list",(d.items||[]).map(n=>`<div class="note"><div><b>${n.title}</b><br><small>${n.time} • ${n.message}</small></div><span>${n.level}</span></div>`).join("")||"<p>Sem notificações.</p>");
}
async function clearNotifications(){
  await fetch(apiBase()+"/api/notifications/clear",{method:"POST"});
  loadNotifications(); loadNotifyCount();
}

function currentFilteredNetwork(){
  return filteredNetwork(lastNetworkDevices||[]);
}
function openCameraSetup(index){
  const dev=currentFilteredNetwork()[index];
  if(!dev) return;

  const modal=el("camera-modal");
  if(!modal){
    toast("Janela de configuração não encontrada.");
    return;
  }

  el("cam-name").value=dev.name==="Câmera RTSP"?`Câmera ${dev.ip}`:dev.name;
  el("cam-room").value="Garagem";
  el("cam-ip").value=dev.ip||"";
  el("cam-port").value=554;
  if(el("cam-preset")) el("cam-preset").value="yoosee";
  el("cam-user").value="admin";
  el("cam-password").value="";
  el("cam-path").value="";

  setText("camera-device-info",`${dev.ip} • Portas ${(dev.ports||[]).join(", ")} • ${dev.vendor||"fabricante não identificado"}`);
  setText("camera-test-result","Aguardando teste...");

  modal.classList.remove("hidden");
  modal.style.display="flex";
  modal.setAttribute("aria-hidden","false");
  document.body.classList.add("modal-open");

  window.setTimeout(()=>{
    const first=el("cam-name");
    if(first) first.focus();
  },50);
}

function closeCameraModal(event){
  if(event){
    event.preventDefault();
    event.stopPropagation();
  }
  const modal=el("camera-modal");
  if(!modal) return;

  modal.classList.add("hidden");
  modal.style.display="none";
  modal.setAttribute("aria-hidden","true");
  document.body.classList.remove("modal-open");
}
function cameraPayload(){
  return {
    name:el("cam-name")?.value||"",
    room:el("cam-room")?.value||"Sem ambiente",
    ip:el("cam-ip")?.value||"",
    port:Number(el("cam-port")?.value||554),
    preset:el("cam-preset")?.value||"auto",
    username:el("cam-user")?.value||"",
    password:el("cam-password")?.value||"",
    path:el("cam-path")?.value||""
  };
}
async function probeCameraONVIF(){
  setText("camera-test-result","Procurando serviço ONVIF...");
  try{
    const payload=cameraPayload();
    payload.onvif_ports=[80,5000,8000,8080,8899];
    const r=await safeJson(apiBase()+"/api/cameras/onvif/probe",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });
    setText("camera-test-result",JSON.stringify(r,null,2));
    toast(r.ok?"Serviço ONVIF localizado":"ONVIF não confirmado");
  }catch(e){
    setText("camera-test-result","Erro ONVIF: "+e.message);
  }
}

async function testCameraRTSP(){
  setText("camera-test-result","Testando RTSP. Aguarde...");
  try{
    const r=await safeJson(apiBase()+"/api/cameras/rtsp/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(cameraPayload())});
    setText("camera-test-result",JSON.stringify(r,null,2));
    toast(r.ok?"Vídeo RTSP validado":(r.error_code==="unauthorized"?"Usuário ou senha RTSP recusados":"Stream não validado"));
  }catch(e){
    setText("camera-test-result","Erro: "+e.message);
  }
}
async function saveCameraRTSP(){
  setText("camera-test-result","Testando e adicionando...");
  try{
    const r=await safeJson(apiBase()+"/api/cameras/rtsp/add",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(cameraPayload())});
    setText("camera-test-result",JSON.stringify(r,null,2));
    if(r.ok){
      toast("Câmera adicionada com sucesso");
      setTimeout(()=>{closeCameraModal();showPage("connect");},900);
    }else toast(r.message||"Não foi possível adicionar");
  }catch(e){
    setText("camera-test-result","Erro: "+e.message);
  }
}


function installCameraModalHandlers(){
  const modal=el("camera-modal");
  const closeButton=el("camera-modal-close");
  if(!modal) return;

  modal.setAttribute("aria-hidden", modal.classList.contains("hidden") ? "true" : "false");

  if(closeButton){
    closeButton.addEventListener("click",closeCameraModal);
    closeButton.addEventListener("touchend",closeCameraModal,{passive:false});
  }

  modal.addEventListener("click",(event)=>{
    if(event.target===modal) closeCameraModal(event);
  });

  document.addEventListener("keydown",(event)=>{
    if(event.key==="Escape" && !modal.classList.contains("hidden")){
      closeCameraModal(event);
    }
  });
}

if(document.readyState==="loading"){
  document.addEventListener("DOMContentLoaded",installCameraModalHandlers);
}else{
  installCameraModalHandlers();
}


async function analyzeCamera(index){
  const dev=currentFilteredNetwork()[index];
  if(!dev) return;
  const r=await safeJson(apiBase()+"/api/cameras/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device:dev})});
  alert(JSON.stringify(r.capabilities,null,2));
}

async function loadCameraManager(){
  const cams=await safeJson(apiBase()+"/api/cameras?"+Date.now());
  const profiles=await safeJson(apiBase()+"/api/camera-profiles?"+Date.now());
  setHTML("camera-manager-list",(cams.items||[]).map(c=>`<div class="module"><h3>📹 ${c.name||c.ip}</h3><p>${c.status||"desconhecido"}</p><small>IP ${c.ip||"--"}:${c.port||554}<br>${c.room||"Sem ambiente"}<br>Caminho ${c.path||"--"}</small><br><button class="danger" onclick="deleteCamera('${c.id}')">Excluir</button></div>`).join("")||"<p>Nenhuma câmera adicionada.</p>");
  setHTML("camera-profile-list",(profiles.profiles||[]).map(p=>`<div class="module"><h3>${p.name}</h3><p>${(p.rtsp_paths||[]).length} caminhos RTSP</p><small>Portas: ${(p.ports||[]).join(", ")}<br>${p.notes||""}</small></div>`).join(""));
}

async function deleteCamera(id){
  if(!confirm("Excluir esta câmera?")) return;
  await safeJson(apiBase()+"/api/cameras/delete",{method:"POST",body:JSON.stringify({id})});
  loadCameraManager(); loadStatus();
}

loadStatus();
setInterval(loadStatus,5000);
loadDiscoveryState();
