#!/usr/bin/env python3
import json, subprocess, time, uuid, zipfile, hmac, hashlib, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

VERSION="Open Home OS v13.0 Open Home Connect"
BUILD="000160"
HOME=Path.home()
BASE=HOME/"OpenHomeOS"; WEB=BASE/"Web"; CONFIG=BASE/"Config"; DATA=BASE/"Data"; LOGS=BASE/"Logs"
AREAS={k:DATA/v for k,v in {"files":"Files","cameras":"Cameras","snapshots":"Snapshots","backups":"Backups","trash":"Trash","iot":"IoT","connect":"Connect"}.items()}
for p in [WEB,CONFIG,DATA,LOGS,*AREAS.values()]: p.mkdir(parents=True,exist_ok=True)
SETTINGS=CONFIG/"settings.json"; CAMERAS=CONFIG/"cameras.json"; EVENTS=CONFIG/"events.json"; NOTES=CONFIG/"notifications.json"; JARVIS=CONFIG/"jarvis.json"
DEVICES=CONFIG/"devices.json"; TUYA_CFG=CONFIG/"tuya_cloud.json"; TUYA_CACHE=CONFIG/"tuya_cache.json"

def ensure(p,d):
    if not p.exists(): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
ensure(SETTINGS,{"system_name":"Open Home OS","version":VERSION,"build":BUILD})
ensure(CAMERAS,[]); ensure(EVENTS,[]); ensure(NOTES,[]); ensure(JARVIS,{"history":[]}); ensure(DEVICES,[])
ensure(TUYA_CFG,{"enabled":False,"client_id":"","client_secret":"","data_center":"https://openapi.tuyaus.com","asset_id":"","last_sync":"","token":"","token_expire":0})
ensure(TUYA_CACHE,{"last_sync":"","devices":[]})
CPU={"total":0,"idle":0}

def run(c,t=6):
    try: return subprocess.check_output(c,shell=True,text=True,stderr=subprocess.DEVNULL,timeout=t).strip()
    except Exception: return ""
def load(p,d):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return d
def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
def now(): return time.strftime("%d/%m/%Y %H:%M:%S")
def ev(k,msg,level="info",mod="core"):
    a=load(EVENTS,[]); a.insert(0,{"id":uuid.uuid4().hex[:8],"kind":k,"module":mod,"message":msg,"level":level,"time":now()}); save(EVENTS,a[:1200])
def ip(): return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"
def df_line(line):
    p=line.split()
    return {"filesystem":p[0],"size":p[1],"used":p[2],"available":p[3],"percent":p[4],"mount":" ".join(p[5:])} if len(p)>=6 else {}
def storage():
    internal=df_line(run(f"df -h {HOME} | awk 'NR==2'"))
    cards=[]
    for line in run("df -h | grep -E '/storage|/mnt/media_rw|/sdcard' | grep -v emulated",5).splitlines():
        x=df_line(line)
        if x: cards.append(x)
    return {"internal":internal,"sdcard":cards[0] if cards else {"available":False,"message":"SD Card não detectado"},"candidates":cards}
def cpu():
    global CPU
    try:
        vals=[int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
        idle=vals[3]+(vals[4] if len(vals)>4 else 0); total=sum(vals)
        if not CPU["total"]: CPU={"total":total,"idle":idle}; return "calculando..."
        dt=total-CPU["total"]; di=idle-CPU["idle"]; CPU={"total":total,"idle":idle}
        return f"{max(0,min(100,int((1-di/dt)*100)))}%" if dt else "0%"
    except Exception: return "indisponível"
def tj(cmd):
    o=run(cmd,5)
    try: return json.loads(o) if o else {}
    except Exception: return {}
def battery():
    b=tj("termux-battery-status"); return {"available":True,**b} if b else {"available":False}
def wifi():
    w=tj("termux-wifi-connectioninfo"); return {"available":True,**w} if w else {"available":False,"ssid":"indisponível"}
def thermal():
    b=battery()
    return b.get("temperature") if b.get("temperature") is not None else None
def num(v):
    try: return float(str(v).replace(",","."))
    except Exception: return None

TYPE_MAP={"mcs":"door","doorcontact":"door","pir":"motion","motion":"motion","wsdcg":"temperature_humidity","temp":"temperature_humidity","humidity":"temperature_humidity","cz":"plug","kg":"switch","light":"light","dj":"light","ipc":"camera","camera":"camera"}
def normalize_tuya(d):
    name=d.get("name") or d.get("device_name") or "Dispositivo Tuya"
    did=d.get("id") or d.get("device_id") or uuid.uuid4().hex[:8]
    cat=(d.get("category") or d.get("product_category") or "").lower()
    dtype="device"
    for k,v in TYPE_MAP.items():
        if k in cat or k in name.lower(): dtype=v; break
    sm={}
    for s in d.get("status",[]) or []:
        sm[str(s.get("code"))]=s.get("value")
    temp=sm.get("va_temperature") or sm.get("temp_current") or sm.get("temperature") or sm.get("temp")
    hum=sm.get("va_humidity") or sm.get("humidity_value") or sm.get("humidity")
    bat=sm.get("battery_percentage") or sm.get("battery_state") or sm.get("battery")
    opened=sm.get("doorcontact_state")
    if isinstance(temp,(int,float)) and temp>100: temp=round(temp/10,1)
    if isinstance(hum,(int,float)) and hum>1000: hum=round(hum/10,1)
    return {"id":did,"source":"tuya","name":name,"room":d.get("room","Sem ambiente"),"type":dtype,"online":bool(d.get("online",True)),"category":cat,"temperature":temp if temp is not None else "","humidity":hum if hum is not None else "","battery":bat if bat is not None else "","open":opened,"raw":d,"updated":now()}

def merge_devices(items):
    cur=load(DEVICES,[]); by={x.get("id"):x for x in cur}
    for item in items:
        old=by.get(item["id"],{}); old.update(item); by[item["id"]]=old
    out=list(by.values()); save(DEVICES,out); return out
def connect_summary():
    devs=load(DEVICES,[]); online=[d for d in devs if d.get("online",True)]
    doors=[d for d in devs if d.get("type")=="door"]; opened=[d for d in doors if d.get("open") in [True,"open","opened",1]]
    ts=[num(d.get("temperature")) for d in online]; ts=[x for x in ts if x is not None]
    hs=[num(d.get("humidity")) for d in online]; hs=[x for x in hs if x is not None]
    return {"total":len(devs),"online":len(online),"offline":len(devs)-len(online),"doors":len(doors),"open_doors":len(opened),"avg_temperature":round(sum(ts)/len(ts),1) if ts else None,"avg_humidity":round(sum(hs)/len(hs),1) if hs else None,"devices":devs}

def tuya_host(): return load(TUYA_CFG,{}).get("data_center","https://openapi.tuyaus.com").rstrip("/")
def tuya_sign(cid,sec,t,method,path,body="",token=""):
    content_hash=hashlib.sha256(body.encode()).hexdigest()
    string_to_sign=f"{method}\n{content_hash}\n\n{path}"
    return hmac.new(sec.encode(),(cid+(token or "")+t+string_to_sign).encode(),hashlib.sha256).hexdigest().upper()
def tuya_request(method,path,body_obj=None,token=None):
    cfg=load(TUYA_CFG,{}); cid=cfg.get("client_id",""); sec=cfg.get("client_secret","")
    if not cid or not sec: return {"success":False,"msg":"Client ID/Secret não configurados"}
    body=json.dumps(body_obj or {},separators=(",",":"),ensure_ascii=False) if body_obj is not None else ""
    t=str(int(time.time()*1000)); tok=token or cfg.get("token","")
    headers={"client_id":cid,"sign":tuya_sign(cid,sec,t,method,path,body,tok),"t":t,"sign_method":"HMAC-SHA256","Content-Type":"application/json"}
    if tok: headers["access_token"]=tok
    req=urllib.request.Request(tuya_host()+path,data=body.encode() if body else None,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=12) as r: return json.loads(r.read().decode())
    except Exception as e: return {"success":False,"msg":str(e)}
def tuya_token():
    cfg=load(TUYA_CFG,{})
    if cfg.get("token") and time.time()<cfg.get("token_expire",0)-60: return cfg.get("token")
    res=tuya_request("GET","/v1.0/token?grant_type=1")
    if res.get("success") and res.get("result"):
        cfg["token"]=res["result"].get("access_token",""); cfg["token_expire"]=time.time()+int(res["result"].get("expire_time",7200)); save(TUYA_CFG,cfg); return cfg["token"]
    return ""
def tuya_sync():
    cfg=load(TUYA_CFG,{})
    if not cfg.get("enabled"): return {"ok":False,"message":"Tuya Cloud desativada"}
    token=tuya_token()
    if not token: return {"ok":False,"message":"Falha ao obter token Tuya"}
    devices=[]; asset=cfg.get("asset_id","").strip()
    paths=([f"/v1.0/iot-03/assets/{asset}/devices"] if asset else [])+["/v1.0/users/devices"]
    last={}
    for path in paths:
        last=tuya_request("GET",path,token=token)
        if last.get("success"):
            r=last.get("result",{})
            devices=(r.get("devices") or r.get("list") or []) if isinstance(r,dict) else r if isinstance(r,list) else []
            if devices: break
    norm=[normalize_tuya(x) for x in devices]
    merge_devices(norm)
    save(TUYA_CACHE,{"last_sync":now(),"devices":norm,"raw":last})
    cfg["last_sync"]=now(); save(TUYA_CFG,cfg)
    ev("tuya_sync",f"{len(norm)} dispositivos sincronizados","success","connect")
    return {"ok":True,"count":len(norm),"devices":norm,"raw":last}

def cam_counts():
    cams=load(CAMERAS,[])
    return {"registered":len(cams),"online":len([c for c in cams if c.get("verified") and c.get("status")=="online"]),"pending":len([c for c in cams if not c.get("verified")]),"offline":len([c for c in cams if c.get("status")=="offline"])}
def status():
    b=battery(); w=wifi(); stg=storage(); sd=stg["sdcard"]; con=connect_summary(); cams=cam_counts(); temp=thermal()
    d={"version":VERSION,"build":BUILD,"ip":ip(),"nginx":"Ativo" if run("pgrep nginx") else "Parado","api":"Ativa","disk":run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),"used":run(f"df {HOME} | awk 'NR==2 {{print $5}}'"),"storage":stg,"sdcard":f"{sd.get('available')} livre de {sd.get('size')}" if sd.get("available") else "não detectado","cpu":cpu(),"mem":run("free -m | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'"),"uptime":run("uptime -p"),"battery":f"{b.get('percentage')}% • {b.get('status','')}" if b.get("percentage") is not None else "indisponível","temperature":f"{temp}°C" if temp is not None else "indisponível","wifi":w.get("ssid") or "indisponível","wifi_detail":w,"connect":con,"cameras":cams,"backups":len(list(AREAS["backups"].glob("*"))),"tuya_cloud":load(TUYA_CFG,{}),"updated":now()}
    score=100
    try:
        if int(str(d["used"]).replace("%",""))>85: score-=25
    except Exception: pass
    if d["sdcard"]=="não detectado": score-=10
    if con["total"]==0: score-=15
    if con["offline"]>0: score-=10
    d["health"]=max(0,score); return d
def house():
    st=status(); con=st["connect"]; probs=[]
    if st["sdcard"]=="não detectado": probs.append("SD Card não detectado")
    if con["total"]==0: probs.append("nenhum dispositivo smart home cadastrado")
    if con["offline"]: probs.append(f"{con['offline']} dispositivo(s) offline")
    if con["open_doors"]: probs.append(f"{con['open_doors']} porta(s)/janela(s) aberta(s)")
    return {"temperature":con["avg_temperature"],"humidity":con["avg_humidity"],"connect":con,"storage":{"internal":st["disk"],"sdcard":st["sdcard"]},"health":st["health"],"problems":probs,"message":"Tudo normal." if not probs else "; ".join(probs)}
def backup():
    target=AREAS["backups"]/f"backup_v13_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
        for base in [CONFIG,AREAS["files"],AREAS["cameras"],AREAS["snapshots"],AREAS["iot"],AREAS["connect"]]:
            for p in base.rglob("*"):
                if p.is_file(): z.write(p,p.relative_to(BASE))
    ev("backup",target.name,"success","backup"); return target.name
def jarvis(cmd):
    t=(cmd or "").lower(); st=status(); hs=house(); reply="Não entendi. Tente: como está a casa, portas abertas, sincronizar Tuya, sensores."; action="none"
    if "casa" in t:
        reply=f"A casa está com {hs['temperature'] or 'sem temperatura'} graus e umidade {hs['humidity'] or 'sem dados'} por cento. {hs['message']}."; action="open_dashboard"
    elif "porta" in t or "janela" in t:
        opens=[d for d in st["connect"]["devices"] if d.get("type")=="door" and d.get("open") in [True,"open","opened",1]]
        reply="Nenhuma porta ou janela aberta." if not opens else "Abertas: "+", ".join([x.get("name","Sensor") for x in opens]); action="open_connect"
    elif "tuya" in t and ("sincron" in t or "buscar" in t):
        r=tuya_sync(); reply=f"Sincronização Tuya concluída. {r.get('count',0)} dispositivos encontrados." if r.get("ok") else "Não consegui sincronizar Tuya: "+r.get("message","erro"); action="open_connect"
    elif "sensor" in t or "dispositivo" in t:
        c=st["connect"]; reply=f"Open Home Connect tem {c['total']} dispositivos, {c['online']} online e {c['offline']} offline."; action="open_connect"
    elif "sd" in t:
        reply=f"SD Card: {st['sdcard']}."
    elif "backup" in t:
        f=backup(); reply=f"Backup criado: {f}."
    j=load(JARVIS,{"history":[]}); j.setdefault("history",[]).insert(0,{"command":cmd,"reply":reply,"action":action,"time":now()}); j["history"]=j["history"][:100]; save(JARVIS,j)
    return {"ok":True,"reply":reply,"action":action}

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): return
    def js(self,d,c=200):
        b=json.dumps(d,ensure_ascii=False).encode(); self.send_response(c); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Methods","GET,POST,DELETE,OPTIONS"); self.send_header("Access-Control-Allow-Headers","Content-Type"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))).decode("utf-8","ignore"))
        except Exception: return {}
    def do_OPTIONS(self): self.js({"ok":True})
    def do_GET(self):
        u=urlparse(self.path)
        if u.path=="/api/status": return self.js(status())
        if u.path=="/api/house": return self.js(house())
        if u.path=="/api/connect/devices": return self.js({"items":load(DEVICES,[]),"summary":connect_summary()})
        if u.path=="/api/connect/tuya/config": return self.js(load(TUYA_CFG,{}))
        if u.path=="/api/connect/tuya/cache": return self.js(load(TUYA_CACHE,{}))
        if u.path=="/api/jarvis": return self.js(load(JARVIS,{}))
        if u.path=="/api/cameras": return self.js({"items":load(CAMERAS,[])})
        if u.path=="/api/events": return self.js({"items":load(EVENTS,[])})
        if u.path=="/api/notifications": return self.js({"items":load(NOTES,[])})
        if u.path=="/api/system/diagnostic": return self.js({"status":status(),"house":house(),"tuya":load(TUYA_CFG,{}),"df":run("df -h"),"log":(LOGS/"api.log").read_text(errors="ignore")[-5000:] if (LOGS/"api.log").exists() else ""})
        self.js({"error":"rota não encontrada"},404)
    def do_POST(self):
        u=urlparse(self.path); d=self.body()
        if u.path=="/api/jarvis/command": return self.js(jarvis(d.get("command","")))
        if u.path=="/api/connect/device/add":
            d.setdefault("id",uuid.uuid4().hex[:8]); d.setdefault("source","manual"); d.setdefault("online",True); d["updated"]=now(); a=load(DEVICES,[]); a.append(d); save(DEVICES,a); ev("device_add",f"{d.get('name','Dispositivo')} adicionado","success","connect"); return self.js({"ok":True})
        if u.path=="/api/connect/device/update":
            a=load(DEVICES,[])
            for x in a:
                if x.get("id")==d.get("id"): x.update(d); x["updated"]=now()
            save(DEVICES,a); return self.js({"ok":True})
        if u.path=="/api/connect/device/delete":
            save(DEVICES,[x for x in load(DEVICES,[]) if x.get("id")!=d.get("id")]); return self.js({"ok":True})
        if u.path=="/api/connect/tuya/config":
            cfg=load(TUYA_CFG,{}); cfg.update(d); cfg["enabled"]=bool(d.get("enabled",cfg.get("enabled",False))); save(TUYA_CFG,cfg); ev("tuya_config","Configuração Tuya salva","success","connect"); return self.js({"ok":True,"config":cfg})
        if u.path=="/api/connect/tuya/test":
            cfg=load(TUYA_CFG,{}); cfg.update(d); save(TUYA_CFG,cfg); token=tuya_token(); return self.js({"ok":bool(token),"message":"Conectado à Tuya Cloud" if token else "Falha ao conectar à Tuya Cloud"})
        if u.path=="/api/connect/tuya/sync": return self.js(tuya_sync())
        if u.path=="/api/backup": return self.js({"ok":True,"file":backup()})
        if u.path=="/api/notifications/clear": save(NOTES,[]); return self.js({"ok":True})
        self.js({"error":"rota não encontrada"},404)

ev("server_start",VERSION,"success","core")
print(f"{VERSION} API rodando na porta 8090")
HTTPServer(("0.0.0.0",8090),H).serve_forever()
