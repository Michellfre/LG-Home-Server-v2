#!/usr/bin/env python3
import json, subprocess, time, uuid, zipfile, shutil, socket, ipaddress, mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

VERSION="v10.4 Android Sensor Edition"
HOME=Path.home()
BASE=HOME/"Servidor"
WEB=BASE/"Web"
CONFIG=BASE/"Config"
AREAS={
 "files":BASE/"Files","shared":BASE/"Shared","documents":BASE/"Documents","downloads":BASE/"Downloads",
 "media":BASE/"Media","photos":BASE/"Photos","videos":BASE/"Videos","music":BASE/"Music",
 "cameras":BASE/"Cameras","backups":BASE/"Backups","trash":BASE/"Trash","logs":BASE/"Logs"
}
for p in list(AREAS.values())+[WEB,CONFIG]: p.mkdir(parents=True,exist_ok=True)

CAMERAS=CONFIG/"cameras.json"; SETTINGS=CONFIG/"settings.json"; SETUP=CONFIG/"setup.json"
NOTES=CONFIG/"notifications.json"; EVENTS=CONFIG/"events.json"; CACHE=CONFIG/"sensor_cache.json"

def ensure(p,d):
    if not p.exists(): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
ensure(CAMERAS,[]); ensure(NOTES,[]); ensure(EVENTS,[]); ensure(CACHE,{"ts":0}); ensure(SETUP,{"done":False,"step":1})
ensure(SETTINGS,{"project_name":"Open Home Server","device_name":"LG K41S","version":VERSION,"camera_retention_days":30,"auto_delete_when_disk_above":90,"battery_low_level":20,"temperature_alert":40,"backup_hour":"02:00","theme":"dark","notifications":True})

NET_LAST={"time":time.time(),"rx":0,"tx":0}; CPU_LAST={"total":0,"idle":0}; ALERTS={}

def run(cmd,timeout=6):
    try: return subprocess.check_output(cmd,shell=True,text=True,stderr=subprocess.DEVNULL,timeout=timeout).strip()
    except Exception: return ""
def load(p,d):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return d
def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
def safe(n): return Path(n).name
def area(a): return AREAS.get(a,AREAS["files"])

def notify(t,m,l="info"):
    key=t+m+l; now=time.time()
    if ALERTS.get(key,0) and now-ALERTS[key]<300: return
    ALERTS[key]=now
    arr=load(NOTES,[]); arr.insert(0,{"id":uuid.uuid4().hex[:8],"title":t,"message":m,"level":l,"time":time.strftime("%d/%m/%Y %H:%M:%S")}); save(NOTES,arr[:120])
def event(k,msg="",l="info",cam=""):
    arr=load(EVENTS,[]); arr.insert(0,{"id":uuid.uuid4().hex[:8],"kind":k,"camera":cam,"message":msg,"level":l,"date":time.strftime("%Y-%m-%d"),"time":time.strftime("%d/%m/%Y %H:%M:%S")}); save(EVENTS,arr[:600])

def media(p):
    e=p.suffix.lower()
    if e in [".jpg",".jpeg",".png",".gif",".webp",".bmp"]: return "image"
    if e in [".mp4",".webm",".mov",".mkv",".avi",".m4v"]: return "video"
    if e in [".mp3",".wav",".ogg",".m4a",".flac"]: return "audio"
    if e==".pdf": return "pdf"
    if e in [".zip",".rar",".7z",".tar",".gz"]: return "archive"
    if e in [".doc",".docx",".xls",".xlsx",".ppt",".pptx",".txt",".md"]: return "document"
    return "other"
def items(a,q="",sort="name"):
    rows=[]; query=q.lower().strip()
    for p in area(a).iterdir():
        if query and query not in p.name.lower(): continue
        try:
            s=p.stat(); rows.append({"name":p.name,"type":"folder" if p.is_dir() else "file","media":media(p),"size":s.st_size,"modified_ts":s.st_mtime,"modified":time.strftime("%d/%m/%Y %H:%M",time.localtime(s.st_mtime))})
        except Exception: pass
    rows.sort(key=(lambda x:x["modified_ts"]) if sort=="date" else (lambda x:x["size"]) if sort=="size" else (lambda x:(x["type"]!="folder",x["name"].lower())), reverse=sort in ["date","size"])
    return rows

def ip(): return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"
def disk_used():
    try: return int(run(f"df {HOME} | awk 'NR==2 {{print $5}}'").replace("%",""))
    except Exception: return 0
def cpu_pct():
    global CPU_LAST
    try:
        vals=[int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
        idle=vals[3]+(vals[4] if len(vals)>4 else 0); total=sum(vals)
        if not CPU_LAST["total"]: CPU_LAST={"total":total,"idle":idle}; return "calculando..."
        dt=total-CPU_LAST["total"]; di=idle-CPU_LAST["idle"]; CPU_LAST={"total":total,"idle":idle}
        return f"{max(0,min(100,int((1-di/dt)*100)))}%" if dt>0 else "0%"
    except Exception: return "indisponível"
def tj(cmd):
    out=run(cmd,5)
    try: return json.loads(out) if out else {}
    except Exception: return {}
def battery():
    b=tj("termux-battery-status")
    if b: return {"available":True,"percentage":b.get("percentage"),"status":b.get("status"),"plugged":b.get("plugged"),"health":b.get("health"),"temperature":b.get("temperature"),"technology":b.get("technology"),"raw":b}
    try:
        base=Path("/sys/class/power_supply/battery"); cap=int((base/"capacity").read_text().strip())
        temp=None
        if (base/"temp").exists():
            n=int((base/"temp").read_text().strip()); temp=n/10 if n>100 else n
        return {"available":True,"percentage":cap,"status":(base/"status").read_text().strip(),"temperature":temp,"health":"indisponível","raw":{}}
    except Exception: return {"available":False,"message":"Termux:API não respondeu"}
def wifi():
    w=tj("termux-wifi-connectioninfo")
    if w: return {"available":True,"ssid":w.get("ssid") or "sem ssid","ip":w.get("ip"),"rssi":w.get("rssi"),"link_speed_mbps":w.get("link_speed_mbps") or w.get("link_speed"),"raw":w}
    return {"available":False,"ssid":run("ip route | awk '/default/ {print $5; exit}'") or "indisponível","message":"Termux:API Wi-Fi não respondeu"}
def device():
    return {"manufacturer":run("getprop ro.product.manufacturer"),"model":run("getprop ro.product.model"),"android":run("getprop ro.build.version.release"),"sdk":run("getprop ro.build.version.sdk"),"kernel":run("uname -r")}
def thermal():
    for base in ["/sys/class/thermal","/sys/devices/virtual/thermal"]:
        b=Path(base)
        if b.exists():
            for p in b.glob("thermal_zone*/temp"):
                try:
                    n=int(p.read_text().strip()); t=n/1000 if n>1000 else n/10 if n>100 else n
                    if 10<=t<=95: return t
                except Exception: pass
    return None
def sensors(force=False):
    c=load(CACHE,{"ts":0})
    if not force and time.time()-c.get("ts",0)<4 and c.get("battery"): return c
    b=battery(); w=wifi(); t=b.get("temperature") if b.get("temperature") is not None else thermal()
    data={"ts":time.time(),"battery":b,"wifi":w,"device":device(),"temperature":t,"api_package":bool(run("command -v termux-battery-status"))}
    save(CACHE,data); return data
def net():
    global NET_LAST
    raw=run("cat /proc/net/dev | awk '/wlan|eth|rmnet/ {rx+=$2; tx+=$10} END {print rx\",\"tx}'")
    try: rx,tx=[int(x or 0) for x in raw.split(",")]
    except Exception: rx=tx=0
    now=time.time(); el=max(1,now-NET_LAST["time"]); d={"rx":rx,"tx":tx,"download_s":max(0,int((rx-NET_LAST["rx"])/el)),"upload_s":max(0,int((tx-NET_LAST["tx"])/el))}
    NET_LAST={"time":now,"rx":rx,"tx":tx}; return d

def folder_usage():
    out=[]
    for n,p in AREAS.items():
        size=count=0
        for f in p.rglob("*"):
            if f.is_file():
                count+=1
                try: size+=f.stat().st_size
                except Exception: pass
        out.append({"area":n,"size":size,"files":count})
    return sorted(out,key=lambda x:x["size"],reverse=True)
def largest():
    rows=[]
    for n,p in AREAS.items():
        for f in p.rglob("*"):
            if f.is_file():
                try: rows.append({"area":n,"name":f.name,"size":f.stat().st_size,"modified":time.strftime("%d/%m/%Y %H:%M",time.localtime(f.stat().st_mtime))})
                except Exception: pass
    return sorted(rows,key=lambda x:x["size"],reverse=True)[:20]

def status():
    cams=load(CAMERAS,[]); s=sensors(); b=s["battery"]; w=s["wifi"]; cfg=load(SETTINGS,{})
    st={"version":VERSION,"ip":ip(),"nginx":"Ativo" if run("pgrep nginx") else "Parado","api":"Ativa","disk":run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),"used":f"{disk_used()}%","cpu":cpu_pct(),"cpu_load":run("cat /proc/loadavg | awk '{print $1}'"),"mem":run("free -m | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'") or "indisponível","uptime":run("uptime -p") or "indisponível","temperature":f"{s.get('temperature')}°C" if s.get("temperature") is not None else "indisponível","battery":f"{b.get('percentage')}% • {b.get('status','')}" if b.get("percentage") is not None else "indisponível","battery_detail":b,"wifi":w.get("ssid") or "indisponível","wifi_detail":w,"device":s.get("device",{}),"network":net(),"files":len([p for p in AREAS["files"].rglob("*") if p.is_file()]),"camera_files":len([p for p in AREAS["cameras"].rglob("*") if p.is_file()]),"backup_files":len([p for p in AREAS["backups"].rglob("*") if p.is_file()]),"trash_files":len([p for p in AREAS["trash"].rglob("*") if p.is_file()]),"cameras_total":len(cams),"cameras_online":len([c for c in cams if c.get("status")=="online"]),"cameras_recording":len([c for c in cams if c.get("recording") in ["always","motion","schedule"]]),"setup":load(SETUP,{}),"settings":cfg,"updated":run("date '+%d/%m/%Y %H:%M:%S'"),"python":run("python --version")}
    if disk_used()>=int(cfg.get("auto_delete_when_disk_above",90)): notify("Espaço baixo",f"Disco em {st['used']}.","warning")
    if b.get("percentage") is not None and int(b["percentage"])<=int(cfg.get("battery_low_level",20)): notify("Bateria baixa",f"Bateria em {b['percentage']}%.","warning"); event("battery_low",f"Bateria em {b['percentage']}%","warning")
    if s.get("temperature") is not None and float(s["temperature"])>=float(cfg.get("temperature_alert",40)): notify("Temperatura alta",f"{s['temperature']}°C","warning"); event("temperature_high",f"{s['temperature']}°C","warning")
    return st

def parse_upload(ct,body):
    if "boundary=" not in ct: return None,None
    b=ct.split("boundary=",1)[1].strip().strip('"')
    for part in body.split(("--"+b).encode()):
        if b"Content-Disposition" in part and b"\r\n\r\n" in part:
            h,c=part.split(b"\r\n\r\n",1)
            if c.endswith(b"\r\n"): c=c[:-2]
            hs=h.decode("utf-8","ignore"); fn=None
            for piece in hs.split(";"):
                piece=piece.strip()
                if piece.startswith("filename="): fn=piece.split("=",1)[1].strip().strip('"')
            if fn: return safe(fn),c
    return None,None
def send_file(h,p,download=False):
    data=p.read_bytes(); typ=mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    h.send_response(200); h.send_header("Content-Type",typ); h.send_header("Access-Control-Allow-Origin","*")
    if download: h.send_header("Content-Disposition",f'attachment; filename="{p.name}"')
    h.send_header("Content-Length",str(len(data))); h.end_headers(); h.wfile.write(data)
def test_port(host,port):
    try:
        with socket.create_connection((host,port),timeout=.25): return True
    except Exception: return False
def discover():
    me=ip()
    if me=="não encontrado": return []
    res=[]; ports=[554,8554,80,8080,8899,5000,8000,8081]
    for h in ipaddress.ip_network(me+"/24",strict=False).hosts():
        addr=str(h)
        if addr==me: continue
        op=[p for p in ports if test_port(addr,p)]
        if op:
            kind="Possível Yoosee" if 8899 in op else "Possível RTSP/ONVIF" if (554 in op or 8554 in op) else "Possível IP Camera"
            res.append({"ip":addr,"ports":op,"type":kind,"suggested_name":f"Camera {len(res)+1}"})
    notify("Busca de câmeras",f"{len(res)} dispositivo(s) encontrado(s)."); return res
def rtsp(ipaddr,user="",pwd=""):
    auth=f"{user}:{pwd}@" if user or pwd else ""
    return [f"rtsp://{auth}{ipaddr}:554/onvif1",f"rtsp://{auth}{ipaddr}:554/live/ch00_0",f"rtsp://{auth}{ipaddr}:554/11",f"rtsp://{auth}{ipaddr}:8554/live",f"http://{ipaddr}:8080/video"]
def timeline():
    d={}
    for p in AREAS["cameras"].rglob("*"):
        if p.is_file():
            day=time.strftime("%Y-%m-%d",time.localtime(p.stat().st_mtime)); d[day]=d.get(day,0)+1
    return [{"date":k,"count":v,"blocks":min(24,max(1,v))} for k,v in sorted(d.items(),reverse=True)]
def library():
    c={"image":0,"video":0,"audio":0,"pdf":0,"archive":0,"document":0,"other":0}
    for a in ["files","documents","downloads","media","photos","videos","music","cameras"]:
        for p in area(a).rglob("*"):
            if p.is_file(): c[media(p)]=c.get(media(p),0)+1
    return c
def backup(kind="manual"):
    date=run("date '+%Y-%m-%d_%H-%M-%S'"); target=AREAS["backups"]/f"backup_{kind}_{date}.zip"
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
        for base in [AREAS["files"],AREAS["documents"],AREAS["cameras"],CONFIG]:
            for p in base.rglob("*"):
                if p.is_file(): z.write(p,p.relative_to(BASE))
    notify("Backup concluído",target.name,"success"); event("backup",target.name,"success"); return target.name

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): return
    def j(self,d,code=200):
        b=json.dumps(d,ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Methods","GET,POST,DELETE,OPTIONS"); self.send_header("Access-Control-Allow-Headers","Content-Type"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        raw=self.rfile.read(int(self.headers.get("Content-Length","0"))).decode("utf-8","ignore")
        try: return json.loads(raw)
        except Exception: return {}
    def do_OPTIONS(self): self.j({"ok":True})
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/status": return self.j(status())
        if u.path=="/api/android": return self.j(sensors(True))
        if u.path=="/api/system/processes": return self.j({"text":run("ps 2>/dev/null | head -30")})
        if u.path=="/api/system/logs":
            p=AREAS["logs"]/ "api.log"; return self.j({"text":"\n".join(p.read_text(errors="ignore").splitlines()[-100:]) if p.exists() else ""})
        if u.path=="/api/system/folders": return self.j({"items":folder_usage()})
        if u.path=="/api/system/largest": return self.j({"items":largest()})
        if u.path=="/api/system/permissions":
            s=sensors(True); return self.j({"termux_api":bool(run("command -v termux-battery-status")),"battery":s.get("battery"),"wifi":s.get("wifi"),"device":s.get("device"),"hint":"Termux:API funcionando." if s.get("battery",{}).get("available") else "Instale/abra Termux:API e dê permissões."})
        if u.path=="/api/setup": return self.j(load(SETUP,{}))
        if u.path=="/api/settings": return self.j(load(SETTINGS,{}))
        if u.path=="/api/library": return self.j(library())
        if u.path=="/api/timeline": return self.j({"items":timeline()})
        if u.path=="/api/events": return self.j({"items":load(EVENTS,[])})
        if u.path=="/api/notifications": return self.j({"items":load(NOTES,[])})
        if u.path=="/api/cameras": return self.j({"items":load(CAMERAS,[])})
        if u.path=="/api/camera/discover": return self.j({"items":discover()})
        if u.path=="/api/camera/suggest": return self.j({"items":rtsp(q.get("ip",[""])[0],q.get("user",[""])[0],q.get("password",[""])[0])})
        if u.path=="/api/files": return self.j({"area":q.get("area",["files"])[0],"items":items(q.get("area",["files"])[0],q.get("q",[""])[0],q.get("sort",["name"])[0])})
        if u.path in ["/api/view","/api/download"]:
            p=area(q.get("area",["files"])[0])/safe(unquote(q.get("name",[""])[0]))
            if not p.exists() or not p.is_file(): return self.j({"error":"arquivo não encontrado"},404)
            return send_file(self,p,u.path=="/api/download")
        return self.j({"error":"rota não encontrada"},404)
    def do_POST(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/settings":
            cfg=load(SETTINGS,{}); cfg.update(self.body()); save(SETTINGS,cfg); notify("Configurações","Preferências atualizadas.","success"); return self.j({"ok":True})
        if u.path=="/api/setup":
            data=self.body(); st=load(SETUP,{}); st.update(data); save(SETUP,st); cfg=load(SETTINGS,{})
            for k in ["device_name","camera_retention_days","auto_delete_when_disk_above","battery_low_level","temperature_alert","backup_hour"]:
                if k in data: cfg[k]=data[k]
            save(SETTINGS,cfg); return self.j({"ok":True})
        if u.path=="/api/setup/finish": save(SETUP,{"done":True,"step":99,"finished":time.strftime("%d/%m/%Y %H:%M:%S")}); return self.j({"ok":True})
        if u.path=="/api/upload":
            a=q.get("area",["files"])[0]; body=self.rfile.read(int(self.headers.get("Content-Length","0"))); fn,content=parse_upload(self.headers.get("Content-Type",""),body)
            if not fn: fn=f"upload_{uuid.uuid4().hex}.bin"; content=body
            (area(a)/safe(fn)).write_bytes(content); notify("Upload concluído",safe(fn),"success"); return self.j({"ok":True,"file":safe(fn)})
        if u.path=="/api/mkdir": data=self.body(); (area(data.get("area","files"))/safe(data.get("name","Nova pasta"))).mkdir(exist_ok=True); return self.j({"ok":True})
        if u.path=="/api/rename":
            a=q.get("area",["files"])[0]; src=area(a)/safe(unquote(q.get("old",[""])[0])); dst=area(a)/safe(unquote(q.get("new",[""])[0]))
            if not src.exists() or dst.exists(): return self.j({"error":"erro"},400)
            src.rename(dst); return self.j({"ok":True})
        if u.path=="/api/move":
            d=self.body(); src=area(d.get("from","files"))/safe(d.get("name","")); dst=area(d.get("to","files"))/safe(d.get("name",""))
            if not src.exists(): return self.j({"error":"não encontrado"},404)
            shutil.move(str(src),str(dst)); return self.j({"ok":True})
        if u.path=="/api/backup": return self.j({"ok":True,"file":backup(self.body().get("kind","manual"))})
        if u.path=="/api/restore":
            n=safe(unquote(q.get("name",[""])[0])); src=AREAS["trash"]/n
            if not src.exists(): return self.j({"error":"não encontrado"},404)
            clean="_".join(n.split("_")[1:]) if "_" in n else n; src.rename(AREAS["files"]/clean); return self.j({"ok":True})
        if u.path=="/api/camera/add":
            d=self.body(); cams=load(CAMERAS,[]); name=d.get("name") or f"Camera {len(cams)+1}"; ipaddr=d.get("ip","")
            cam={"id":uuid.uuid4().hex[:8],"name":name,"type":d.get("type","rtsp"),"ip":ipaddr,"user":d.get("user",""),"password":d.get("password",""),"rtsp":d.get("rtsp",""),"quality":d.get("quality","media"),"recording":d.get("recording","manual"),"location":d.get("location",""),"status":"online" if ipaddr and any(test_port(ipaddr,p) for p in [554,8554,80,8080,8899]) else "cadastrada"}
            cams.append(cam); save(CAMERAS,cams); notify("Câmera adicionada",name,"success"); event("camera_added","Câmera cadastrada.","success",name); return self.j({"ok":True})
        if u.path=="/api/camera/check":
            cams=load(CAMERAS,[])
            for c in cams:
                ipaddr=c.get("ip"); c["status"]="online" if ipaddr and any(test_port(ipaddr,p) for p in [554,8554,80,8080,8899]) else "offline"
            save(CAMERAS,cams); return self.j({"ok":True,"items":cams})
        if u.path=="/api/camera/delete": cid=self.body().get("id"); save(CAMERAS,[c for c in load(CAMERAS,[]) if c.get("id")!=cid]); return self.j({"ok":True})
        if u.path=="/api/notifications/clear": save(NOTES,[]); return self.j({"ok":True})
        if u.path=="/api/trash/empty":
            for p in AREAS["trash"].iterdir():
                if p.is_file(): p.unlink()
            return self.j({"ok":True})
        return self.j({"error":"rota não encontrada"},404)
    def do_DELETE(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/delete":
            a=q.get("area",["files"])[0]; p=area(a)/safe(unquote(q.get("name",[""])[0]))
            if p.exists() and p.is_file(): p.rename(AREAS["trash"]/f"{uuid.uuid4().hex}_{p.name}"); return self.j({"ok":True})
            return self.j({"error":"não encontrado"},404)
        return self.j({"error":"rota não encontrada"},404)

event("server_start",f"API {VERSION} iniciada.","success")
print(f"Open Home Server API {VERSION} rodando na porta 8090")
HTTPServer(("0.0.0.0",8090),H).serve_forever()
