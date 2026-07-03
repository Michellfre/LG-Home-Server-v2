#!/usr/bin/env python3
import json, subprocess, time, uuid, zipfile, mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

VERSION="Open Home OS v11.1 Tuya + SD"
HOME=Path.home()
BASE=HOME/"OpenHomeOS"; WEB=BASE/"Web"; CONFIG=BASE/"Config"; DATA=BASE/"Data"; LOGS=BASE/"Logs"
AREAS={k:DATA/v for k,v in {
"files":"Files","documents":"Documents","downloads":"Downloads","media":"Media","photos":"Photos","videos":"Videos","music":"Music",
"cameras":"Cameras","snapshots":"Snapshots","backups":"Backups","trash":"Trash","iot":"IoT"}.items()}
for p in [WEB,CONFIG,DATA,LOGS,*AREAS.values()]: p.mkdir(parents=True,exist_ok=True)
def ensure(p,d):
    if not p.exists(): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
SETTINGS=CONFIG/"settings.json"; CAMERAS=CONFIG/"cameras.json"; TUYA=CONFIG/"tuya_sensors.json"; EVENTS=CONFIG/"events.json"; NOTES=CONFIG/"notifications.json"; JARVIS=CONFIG/"jarvis.json"
ensure(SETTINGS,{"system_name":"Open Home OS","version":VERSION,"device_name":"LG K41S","humidity_alert":80,"temperature_alert":40})
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
    a=load(EVENTS,[]); a.insert(0,{"id":uuid.uuid4().hex[:8],"kind":k,"module":mod,"message":msg,"level":level,"time":time.strftime("%d/%m/%Y %H:%M:%S")}); save(EVENTS,a[:500])
def note(t,m,l="info"):
    a=load(NOTES,[]); a.insert(0,{"id":uuid.uuid4().hex[:8],"title":t,"message":m,"level":l,"time":time.strftime("%d/%m/%Y %H:%M:%S")}); save(NOTES,a[:200])
def ip(): return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"
def df_line(line):
    p=line.split()
    if len(p)>=6: return {"filesystem":p[0],"size":p[1],"used":p[2],"available":p[3],"percent":p[4],"mount":" ".join(p[5:])}
    return None
def storage():
    internal=df_line(run(f"df -h {HOME} | awk 'NR==2'")) or {}
    candidates=[]
    out=run("df -h | grep -E '/storage|/mnt/media_rw|/sdcard' | grep -v emulated",5)
    for line in out.splitlines():
        x=df_line(line)
        if x and x["mount"] not in [c["mount"] for c in candidates]: candidates.append(x)
    sd=candidates[0] if candidates else None
    return {"internal":internal,"sdcard":sd or {"available":False,"message":"SD Card não detectado"},"candidates":candidates}
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
def net():
    global NET
    raw=run("cat /proc/net/dev | awk '/wlan|eth|rmnet/ {rx+=$2; tx+=$10} END {print rx\",\"tx}'")
    try: rx,tx=[int(x or 0) for x in raw.split(",")]
    except Exception: rx=tx=0
    now=time.time(); e=max(1,now-NET["time"]); out={"download_s":max(0,int((rx-NET["rx"])/e)),"upload_s":max(0,int((tx-NET["tx"])/e))}
    NET={"time":now,"rx":rx,"tx":tx}; return out
def tuya_summary():
    items=load(TUYA,[])
    online=[x for x in items if x.get("status","manual")!="offline"]
    def num(v):
        try: return float(str(v).replace(",","."))
        except Exception: return None
    ts=[num(x.get("temperature")) for x in online]; ts=[x for x in ts if x is not None]
    hs=[num(x.get("humidity")) for x in online]; hs=[x for x in hs if x is not None]
    return {"total":len(items),"online":len(online),"avg_temperature":round(sum(ts)/len(ts),1) if ts else None,"avg_humidity":round(sum(hs)/len(hs),1) if hs else None,"items":items}
def cam_counts():
    cams=load(CAMERAS,[])
    return {"registered":len(cams),"online":len([c for c in cams if c.get("verified") and c.get("status")=="online"]),"pending":len([c for c in cams if not c.get("verified")])}
def status():
    b=battery(); w=wifi(); st=storage(); sd=st["sdcard"]; tu=tuya_summary()
    return {"version":VERSION,"ip":ip(),"nginx":"Ativo" if run("pgrep nginx") else "Parado","api":"Ativa",
    "disk":run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),"used":run(f"df {HOME} | awk 'NR==2 {{print $5}}'"),
    "storage":st,"sdcard":f"{sd.get('available')} livre de {sd.get('size')}" if sd.get("available") else "não detectado",
    "cpu":cpu(),"load":run("cat /proc/loadavg | awk '{print $1}'"),"mem":run("free -m | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'"),
    "battery":f"{b.get('percentage')}% • {b.get('status','')}" if b.get("percentage") is not None else "indisponível","battery_detail":b,
    "temperature":f"{thermal()}°C" if thermal() is not None else "indisponível","wifi":w.get("ssid") or "indisponível","wifi_detail":w,
    "network":net(),"tuya":tu,"cameras":cam_counts(),"files":len(list(AREAS["files"].rglob("*"))),"backups":len(list(AREAS["backups"].glob("*"))),
    "updated":time.strftime("%d/%m/%Y %H:%M:%S")}
def media(p):
    e=p.suffix.lower()
    if e in [".jpg",".jpeg",".png",".webp"]: return "image"
    if e in [".mp4",".mkv",".avi",".webm"]: return "video"
    if e in [".mp3",".wav",".ogg"]: return "audio"
    if e==".pdf": return "pdf"
    return "file"
def list_files(a="files",q=""):
    root=AREAS.get(a,AREAS["files"]); out=[]
    for p in root.iterdir():
        if q and q.lower() not in p.name.lower(): continue
        s=p.stat(); out.append({"name":p.name,"size":s.st_size,"modified":time.strftime("%d/%m/%Y %H:%M",time.localtime(s.st_mtime)),"media":media(p),"type":"folder" if p.is_dir() else "file"})
    return sorted(out,key=lambda x:x["name"].lower())
def backup():
    target=AREAS["backups"]/f"backup_v11_1_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
        for base in [CONFIG,AREAS["files"],AREAS["cameras"],AREAS["snapshots"]]:
            for p in base.rglob("*"):
                if p.is_file(): z.write(p,p.relative_to(BASE))
    ev("backup",target.name,"success","backup"); return target.name
def jarvis(cmd):
    t=(cmd or "").lower(); st=status(); reply="Não entendi. Tente: sensores Tuya, SD Card, status."
    action="none"
    if "tuya" in t or "ambiente" in t or "umidade" in t:
        tu=st["tuya"]; reply=f"Sensores Tuya: {tu['online']} online de {tu['total']}. Ambiente: {tu['avg_temperature'] or 'sem temperatura'} graus e umidade {tu['avg_humidity'] or 'sem dados'} por cento."; action="open_iot"
    elif "sd" in t or "cartão" in t or "cartao" in t:
        reply=f"SD Card: {st['sdcard']}."; action="speak"
    elif "status" in t:
        reply=f"Open Home OS online. IP {st['ip']}. SD Card {st['sdcard']}. Bateria {st['battery']}."; action="speak"
    j=load(JARVIS,{"history":[]}); j.setdefault("history",[]).insert(0,{"command":cmd,"reply":reply,"action":action,"time":time.strftime("%d/%m/%Y %H:%M:%S")}); j["history"]=j["history"][:100]; save(JARVIS,j)
    return {"ok":True,"reply":reply,"action":action,"status":st}
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
        if u.path=="/api/tuya": return self.js({"items":load(TUYA,[]),"summary":tuya_summary()})
        if u.path=="/api/storage": return self.js(storage())
        if u.path=="/api/jarvis": return self.js(load(JARVIS,{}))
        if u.path=="/api/cameras": return self.js({"items":load(CAMERAS,[])})
        if u.path=="/api/events": return self.js({"items":load(EVENTS,[])})
        if u.path=="/api/notifications": return self.js({"items":load(NOTES,[])})
        if u.path=="/api/files": return self.js({"items":list_files(q.get("area",["files"])[0],q.get("q",[""])[0])})
        if u.path=="/api/system/diagnostic": return self.js({"status":status(),"storage":storage(),"tuya":tuya_summary(),"df":run("df -h"),"log":(LOGS/"api.log").read_text(errors="ignore")[-4000:] if (LOGS/"api.log").exists() else ""})
        if u.path in ["/api/view","/api/download"]:
            p=AREAS.get(q.get("area",["files"])[0],AREAS["files"])/Path(unquote(q.get("name",[""])[0])).name
            if not p.exists(): return self.js({"error":"não encontrado"},404)
            data=p.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(str(p))[0] or "application/octet-stream"); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        self.js({"error":"rota não encontrada"},404)
    def do_POST(self):
        u=urlparse(self.path)
        if u.path=="/api/jarvis/command": return self.js(jarvis(self.body().get("command","")))
        if u.path=="/api/tuya/add":
            d=self.body(); d.setdefault("id",uuid.uuid4().hex[:8]); d.setdefault("name","Sensor Tuya"); d.setdefault("room","Ambiente"); d.setdefault("status","manual"); d["updated"]=time.strftime("%d/%m/%Y %H:%M:%S")
            a=load(TUYA,[]); a.append(d); save(TUYA,a); ev("tuya_add",d.get("name","Sensor"),"success","iot"); return self.js({"ok":True,"sensor":d})
        if u.path=="/api/tuya/update":
            d=self.body(); a=load(TUYA,[])
            for x in a:
                if x.get("id")==d.get("id"): x.update(d); x["updated"]=time.strftime("%d/%m/%Y %H:%M:%S")
            save(TUYA,a); return self.js({"ok":True})
        if u.path=="/api/tuya/delete":
            sid=self.body().get("id"); save(TUYA,[x for x in load(TUYA,[]) if x.get("id")!=sid]); return self.js({"ok":True})
        if u.path=="/api/backup": return self.js({"ok":True,"file":backup()})
        if u.path=="/api/camera/add":
            d=self.body(); d.setdefault("id",uuid.uuid4().hex[:8]); d.setdefault("verified",False); d.setdefault("status","pending"); a=load(CAMERAS,[]); a.append(d); save(CAMERAS,a); return self.js({"ok":True})
        if u.path=="/api/camera/delete":
            sid=self.body().get("id"); save(CAMERAS,[x for x in load(CAMERAS,[]) if x.get("id")!=sid]); return self.js({"ok":True})
        self.js({"error":"rota não encontrada"},404)
ev("server_start",VERSION,"success","core")
print(f"{VERSION} API rodando na porta 8090")
HTTPServer(("0.0.0.0",8090),H).serve_forever()
