#!/usr/bin/env python3
import json, subprocess, time, uuid, zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

VERSION="Open Home OS v12.0 Smart Home Core"
BUILD="000145"
HOME=Path.home()
BASE=HOME/"OpenHomeOS"; WEB=BASE/"Web"; CONFIG=BASE/"Config"; DATA=BASE/"Data"; LOGS=BASE/"Logs"
AREAS={k:DATA/v for k,v in {"files":"Files","cameras":"Cameras","snapshots":"Snapshots","backups":"Backups","trash":"Trash","iot":"IoT","stats":"Stats"}.items()}
for p in [WEB,CONFIG,DATA,LOGS,*AREAS.values()]: p.mkdir(parents=True,exist_ok=True)
SETTINGS=CONFIG/"settings.json"; CAMERAS=CONFIG/"cameras.json"; TUYA=CONFIG/"tuya_sensors.json"; EVENTS=CONFIG/"events.json"; NOTES=CONFIG/"notifications.json"; JARVIS=CONFIG/"jarvis.json"
def ensure(p,d):
    if not p.exists(): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
ensure(SETTINGS,{"system_name":"Open Home OS","version":VERSION,"build":BUILD,"temperature_alert":30,"humidity_alert":80,"backup_hour":"02:00"})
ensure(CAMERAS,[]); ensure(TUYA,[]); ensure(EVENTS,[]); ensure(NOTES,[]); ensure(JARVIS,{"history":[]})
CPU={"total":0,"idle":0}; NET={"time":time.time(),"rx":0,"tx":0}
def run(c,t=6):
    try: return subprocess.check_output(c,shell=True,text=True,stderr=subprocess.DEVNULL,timeout=t).strip()
    except Exception: return ""
def load(p,d):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return d
def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
def ev(k,msg,level="info",mod="core"):
    a=load(EVENTS,[]); a.insert(0,{"id":uuid.uuid4().hex[:8],"kind":k,"module":mod,"message":msg,"level":level,"time":time.strftime("%d/%m/%Y %H:%M:%S")}); save(EVENTS,a[:1000])
def note(t,m,l="info"):
    a=load(NOTES,[]); a.insert(0,{"id":uuid.uuid4().hex[:8],"title":t,"message":m,"level":l,"time":time.strftime("%d/%m/%Y %H:%M:%S")}); save(NOTES,a[:300])
def ip(): return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"
def df_line(line):
    p=line.split()
    return {"filesystem":p[0],"size":p[1],"used":p[2],"available":p[3],"percent":p[4],"mount":" ".join(p[5:])} if len(p)>=6 else {}
def storage():
    internal=df_line(run(f"df -h {HOME} | awk 'NR==2'"))
    c=[]
    for line in run("df -h | grep -E '/storage|/mnt/media_rw|/sdcard' | grep -v emulated",5).splitlines():
        x=df_line(line)
        if x: c.append(x)
    return {"internal":internal,"sdcard":c[0] if c else {"available":False,"message":"SD Card não detectado"},"candidates":c}
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
    b=tj("termux-battery-status")
    return {"available":True,**b} if b else {"available":False}
def wifi():
    w=tj("termux-wifi-connectioninfo")
    return {"available":True,**w} if w else {"available":False,"ssid":"indisponível"}
def thermal():
    b=battery()
    if b.get("temperature") is not None: return b.get("temperature")
    return None
def num(v):
    try: return float(str(v).replace(",","."))
    except Exception: return None
def tuya_summary():
    items=load(TUYA,[])
    online=[x for x in items if x.get("status","manual")!="offline"]
    ts=[num(x.get("temperature")) for x in online]; ts=[x for x in ts if x is not None]
    hs=[num(x.get("humidity")) for x in online]; hs=[x for x in hs if x is not None]
    return {"total":len(items),"online":len(online),"avg_temperature":round(sum(ts)/len(ts),1) if ts else None,"avg_humidity":round(sum(hs)/len(hs),1) if hs else None,"rooms":online,"items":items}
def cam_counts():
    cams=load(CAMERAS,[])
    return {"registered":len(cams),"online":len([c for c in cams if c.get("verified") and c.get("status")=="online"]),"pending":len([c for c in cams if not c.get("verified")]),"offline":len([c for c in cams if c.get("status")=="offline"])}
def status():
    b=battery(); w=wifi(); stg=storage(); sd=stg["sdcard"]; tu=tuya_summary(); cams=cam_counts(); temp=thermal()
    d={"version":VERSION,"build":BUILD,"ip":ip(),"nginx":"Ativo" if run("pgrep nginx") else "Parado","api":"Ativa","disk":run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),"used":run(f"df {HOME} | awk 'NR==2 {{print $5}}'"),"storage":stg,"sdcard":f"{sd.get('available')} livre de {sd.get('size')}" if sd.get("available") else "não detectado","cpu":cpu(),"load":run("cat /proc/loadavg | awk '{print $1}'"),"mem":run("free -m | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'"),"uptime":run("uptime -p"),"battery":f"{b.get('percentage')}% • {b.get('status','')}" if b.get("percentage") is not None else "indisponível","battery_detail":b,"temperature":f"{temp}°C" if temp is not None else "indisponível","wifi":w.get("ssid") or "indisponível","wifi_detail":w,"tuya":tu,"cameras":cams,"backups":len(list(AREAS["backups"].glob("*"))),"updated":time.strftime("%d/%m/%Y %H:%M:%S")}
    score=100
    try:
        if int(str(d["used"]).replace("%",""))>85: score-=25
    except Exception: pass
    if d["sdcard"]=="não detectado": score-=10
    if tu["total"]==0: score-=10
    if cams["pending"]>0: score-=10
    d["health"]=max(0,score)
    return d
def house():
    st=status(); tu=st["tuya"]; cams=st["cameras"]; probs=[]
    if st["sdcard"]=="não detectado": probs.append("SD Card não detectado")
    if tu["total"]==0: probs.append("nenhum sensor Tuya cadastrado")
    if cams["pending"]: probs.append(f"{cams['pending']} câmera(s) pendente(s)")
    return {"temperature":tu["avg_temperature"],"humidity":tu["avg_humidity"],"cameras":cams,"storage":{"internal":st["disk"],"sdcard":st["sdcard"]},"health":st["health"],"problems":probs,"message":"Tudo normal." if not probs else "; ".join(probs)}
def backup():
    target=AREAS["backups"]/f"backup_v12_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
        for base in [CONFIG,AREAS["files"],AREAS["cameras"],AREAS["snapshots"],AREAS["iot"]]:
            for p in base.rglob("*"):
                if p.is_file(): z.write(p,p.relative_to(BASE))
    ev("backup",target.name,"success","backup"); return target.name
def jarvis(cmd):
    t=(cmd or "").lower(); st=status(); hs=house(); reply="Não entendi. Tente: como está a casa, SD Card, sensores Tuya, backup."; action="none"
    if "casa" in t:
        reply=f"A casa está com {hs['temperature'] or 'sem temperatura'} graus e umidade de {hs['humidity'] or 'sem dados'} por cento. {hs['message']}."; action="open_dashboard"
    elif "sd" in t or "cartão" in t or "cartao" in t:
        reply=f"SD Card: {st['sdcard']}."; action="speak"
    elif "tuya" in t or "ambiente" in t or "umidade" in t:
        reply=f"Sensores Tuya: {st['tuya']['online']} online de {st['tuya']['total']}. Média ambiente: {st['tuya']['avg_temperature'] or 'sem temperatura'} graus e umidade {st['tuya']['avg_humidity'] or 'sem dados'} por cento."; action="open_iot"
    elif "backup" in t:
        f=backup(); reply=f"Backup criado: {f}."; action="backup"
    elif "status" in t:
        reply=f"Open Home OS online. Saúde {st['health']} por cento. Interno {st['disk']}. SD Card {st['sdcard']}."; action="speak"
    j=load(JARVIS,{"history":[]}); j.setdefault("history",[]).insert(0,{"command":cmd,"reply":reply,"action":action,"time":time.strftime("%d/%m/%Y %H:%M:%S")}); j["history"]=j["history"][:100]; save(JARVIS,j)
    return {"ok":True,"reply":reply,"action":action,"status":st,"house":hs}
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): return
    def js(self,d,c=200):
        b=json.dumps(d,ensure_ascii=False).encode(); self.send_response(c); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Methods","GET,POST,DELETE,OPTIONS"); self.send_header("Access-Control-Allow-Headers","Content-Type"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))).decode("utf-8","ignore"))
        except Exception: return {}
    def do_OPTIONS(self): self.js({"ok":True})
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/status": return self.js(status())
        if u.path=="/api/house": return self.js(house())
        if u.path=="/api/tuya": return self.js({"items":load(TUYA,[]),"summary":tuya_summary()})
        if u.path=="/api/jarvis": return self.js(load(JARVIS,{}))
        if u.path=="/api/cameras": return self.js({"items":load(CAMERAS,[])})
        if u.path=="/api/events": return self.js({"items":load(EVENTS,[])})
        if u.path=="/api/notifications": return self.js({"items":load(NOTES,[])})
        if u.path=="/api/system/diagnostic": return self.js({"status":status(),"house":house(),"df":run("df -h"),"log":(LOGS/"api.log").read_text(errors="ignore")[-4000:] if (LOGS/"api.log").exists() else ""})
        self.js({"error":"rota não encontrada"},404)
    def do_POST(self):
        u=urlparse(self.path); d=self.body()
        if u.path=="/api/jarvis/command": return self.js(jarvis(d.get("command","")))
        if u.path=="/api/tuya/add":
            d.setdefault("id",uuid.uuid4().hex[:8]); d.setdefault("name","Sensor Tuya"); d.setdefault("room","Ambiente"); d.setdefault("status","manual"); d["updated"]=time.strftime("%d/%m/%Y %H:%M:%S")
            a=load(TUYA,[]); a.append(d); save(TUYA,a); ev("sensor_tuya",f"{d.get('name')} adicionado","success","iot"); return self.js({"ok":True})
        if u.path=="/api/tuya/update":
            a=load(TUYA,[])
            for x in a:
                if x.get("id")==d.get("id"): x.update(d); x["updated"]=time.strftime("%d/%m/%Y %H:%M:%S")
            save(TUYA,a); return self.js({"ok":True})
        if u.path=="/api/tuya/delete":
            save(TUYA,[x for x in load(TUYA,[]) if x.get("id")!=d.get("id")]); return self.js({"ok":True})
        if u.path=="/api/camera/add":
            d.setdefault("id",uuid.uuid4().hex[:8]); d.setdefault("verified",False); d.setdefault("status","pending"); a=load(CAMERAS,[]); a.append(d); save(CAMERAS,a); return self.js({"ok":True})
        if u.path=="/api/camera/delete":
            save(CAMERAS,[x for x in load(CAMERAS,[]) if x.get("id")!=d.get("id")]); return self.js({"ok":True})
        if u.path=="/api/backup": return self.js({"ok":True,"file":backup()})
        if u.path=="/api/notifications/clear": save(NOTES,[]); return self.js({"ok":True})
        self.js({"error":"rota não encontrada"},404)
ev("server_start",VERSION,"success","core")
print(f"{VERSION} API rodando na porta 8090")
HTTPServer(("0.0.0.0",8090),H).serve_forever()
