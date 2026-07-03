#!/usr/bin/env python3
import json, subprocess, uuid, time, zipfile, socket, ipaddress
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HOME=Path.home()
BASE=HOME/"Servidor"
WEB=BASE/"Web"
CONFIG=BASE/"Config"
AREAS={
 "files":BASE/"Files","documents":BASE/"Documents","downloads":BASE/"Downloads","media":BASE/"Media",
 "cameras":BASE/"Cameras","backups":BASE/"Backups","trash":BASE/"Trash","logs":BASE/"Logs"
}
for p in list(AREAS.values())+[WEB,CONFIG]: p.mkdir(parents=True, exist_ok=True)
CAMERAS=CONFIG/"cameras.json"; SETTINGS=CONFIG/"settings.json"; SETUP=CONFIG/"setup.json"; NOTES=CONFIG/"notifications.json"

def ensure(path,data):
    if not path.exists(): path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
ensure(CAMERAS,[])
ensure(NOTES,[])
ensure(SETUP,{"done":False,"step":1})
ensure(SETTINGS,{"project_name":"Open Home Server","device_name":"K41S","storage_path":str(BASE),"camera_retention_days":30,"auto_delete_when_disk_above":90,"backup_hour":"02:00","theme":"dark"})

def run(cmd):
    try: return subprocess.check_output(cmd,shell=True,text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return ""
def load(p,d):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return d
def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
def note(title,msg,level="info"):
    arr=load(NOTES,[]); arr.insert(0,{"id":uuid.uuid4().hex[:8],"title":title,"message":msg,"level":level,"time":time.strftime("%d/%m/%Y %H:%M:%S")}); save(NOTES,arr[:80])
def safe(n): return Path(n).name
def area(a): return AREAS.get(a,AREAS["files"])
def ip():
    return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"
def mtype(p):
    e=p.suffix.lower()
    if e in [".jpg",".jpeg",".png",".gif",".webp"]: return "image"
    if e in [".mp4",".webm",".mov",".mkv",".avi"]: return "video"
    if e in [".mp3",".wav",".ogg",".m4a"]: return "audio"
    if e==".pdf": return "pdf"
    if e in [".zip",".rar",".7z",".tar",".gz"]: return "archive"
    return "other"
def items(a,q="",sort="name"):
    rows=[]; query=q.lower().strip()
    for p in area(a).iterdir():
        if query and query not in p.name.lower(): continue
        try:
            st=p.stat(); rows.append({"name":p.name,"type":"folder" if p.is_dir() else "file","media":mtype(p),"size":st.st_size,"modified_ts":st.st_mtime,"modified":time.strftime("%d/%m/%Y %H:%M",time.localtime(st.st_mtime))})
        except Exception: pass
    rows.sort(key=(lambda x:x["size"]) if sort=="size" else (lambda x:x["modified_ts"]) if sort=="date" else (lambda x:(x["type"]!="folder",x["name"].lower())), reverse=(sort in ["date","size"]))
    return rows
def status():
    cams=load(CAMERAS,[])
    return {"ip":ip(),"nginx":"Ativo" if run("pgrep nginx") else "Parado","api":"Ativa","disk":run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),"used":run(f"df {HOME} | awk 'NR==2 {{print $5}}'"),"mem":run("free -m 2>/dev/null | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'") or "indisponível","uptime":run("uptime -p 2>/dev/null") or "indisponível","files":len([p for p in AREAS["files"].rglob("*") if p.is_file()]),"camera_files":len([p for p in AREAS["cameras"].rglob("*") if p.is_file()]),"backup_files":len([p for p in AREAS["backups"].rglob("*") if p.is_file()]),"trash_files":len([p for p in AREAS["trash"].rglob("*") if p.is_file()]),"cameras_total":len(cams),"cameras_online":len([c for c in cams if c.get("status")=="online"]),"setup":load(SETUP,{}),"settings":load(SETTINGS,{}),"updated":run("date '+%d/%m/%Y %H:%M:%S'"),"python":run("python --version")}
def parse_upload(ct,body):
    if "boundary=" not in ct: return None,None
    b=ct.split("boundary=",1)[1].strip().strip('"')
    for part in body.split(("--"+b).encode()):
        if b"Content-Disposition" not in part or b"\r\n\r\n" not in part: continue
        h,c=part.split(b"\r\n\r\n",1)
        if c.endswith(b"\r\n"): c=c[:-2]
        if c.endswith(b"--"): c=c[:-2]
        hs=h.decode("utf-8","ignore"); fn=None
        for piece in hs.split(";"):
            piece=piece.strip()
            if piece.startswith("filename="): fn=piece.split("=",1)[1].strip().strip('"')
        if fn: return safe(fn),c
    return None,None
def send(handler,p,download=False):
    data=p.read_bytes(); t="application/octet-stream"; e=p.suffix.lower()
    if e in [".jpg",".jpeg"]: t="image/jpeg"
    elif e==".png": t="image/png"
    elif e==".webp": t="image/webp"
    elif e==".gif": t="image/gif"
    elif e==".mp4": t="video/mp4"
    elif e==".webm": t="video/webm"
    elif e==".pdf": t="application/pdf"
    elif e==".mp3": t="audio/mpeg"
    handler.send_response(200); handler.send_header("Content-Type",t); handler.send_header("Access-Control-Allow-Origin","*")
    if download: handler.send_header("Content-Disposition",f'attachment; filename="{p.name}"')
    handler.send_header("Content-Length",str(len(data))); handler.end_headers(); handler.wfile.write(data)
def port(host,prt,timeout=.28):
    try:
        with socket.create_connection((host,prt),timeout=timeout): return True
    except Exception: return False
def discover():
    me=ip()
    if me=="não encontrado": return []
    net=ipaddress.ip_network(me+"/24",strict=False); out=[]
    for h in list(net.hosts()):
        s=str(h)
        if s==me: continue
        ports=[p for p in [554,8554,80,8080,8899,5000,8000] if port(s,p)]
        if ports:
            kind="Dispositivo"
            if 8899 in ports: kind="Possível Yoosee"
            elif 554 in ports or 8554 in ports: kind="Possível RTSP/ONVIF"
            out.append({"ip":s,"ports":ports,"type":kind})
    note("Busca de câmeras",f"{len(out)} dispositivo(s) encontrado(s).")
    return out
def rtsp(ipaddr,user="",pwd=""):
    auth=f"{user}:{pwd}@" if user or pwd else ""
    return [f"rtsp://{auth}{ipaddr}:554/onvif1",f"rtsp://{auth}{ipaddr}:554/onvif2",f"rtsp://{auth}{ipaddr}:554/live/ch00_0",f"rtsp://{auth}{ipaddr}:554/live/ch00_1",f"rtsp://{auth}{ipaddr}:554/11",f"rtsp://{auth}{ipaddr}:554/12",f"rtsp://{auth}{ipaddr}:8554/live"]
def library():
    c={"image":0,"video":0,"audio":0,"pdf":0,"archive":0,"other":0}
    for a in ["files","documents","downloads","media","cameras"]:
        for p in area(a).rglob("*"):
            if p.is_file(): c[mtype(p)]=c.get(mtype(p),0)+1
    return c
def timeline():
    d={}
    for p in AREAS["cameras"].rglob("*"):
        if p.is_file():
            day=time.strftime("%Y-%m-%d",time.localtime(p.stat().st_mtime)); d[day]=d.get(day,0)+1
    return [{"date":k,"count":v} for k,v in sorted(d.items(),reverse=True)]

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
        if u.path=="/api/setup": return self.j(load(SETUP,{}))
        if u.path=="/api/settings": return self.j(load(SETTINGS,{}))
        if u.path=="/api/library": return self.j(library())
        if u.path=="/api/timeline": return self.j({"items":timeline()})
        if u.path=="/api/notifications": return self.j({"items":load(NOTES,[])})
        if u.path=="/api/cameras": return self.j({"items":load(CAMERAS,[])})
        if u.path=="/api/camera/discover": return self.j({"items":discover()})
        if u.path=="/api/camera/suggest": return self.j({"items":rtsp(q.get("ip",[""])[0],q.get("user",[""])[0],q.get("password",[""])[0])})
        if u.path=="/api/files": return self.j({"area":q.get("area",["files"])[0],"items":items(q.get("area",["files"])[0],q.get("q",[""])[0],q.get("sort",["name"])[0])})
        if u.path in ["/api/view","/api/download"]:
            p=area(q.get("area",["files"])[0])/safe(unquote(q.get("name",[""])[0]))
            if not p.exists() or not p.is_file(): return self.j({"error":"arquivo não encontrado"},404)
            return send(self,p,u.path=="/api/download")
        self.j({"error":"rota não encontrada"},404)
    def do_POST(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/setup":
            data=self.body(); s=load(SETUP,{}); s.update(data); save(SETUP,s); cfg=load(SETTINGS,{})
            for k in ["device_name","storage_path","camera_retention_days","auto_delete_when_disk_above"]: 
                if k in data: cfg[k]=data[k]
            save(SETTINGS,cfg); note("Assistente","Configuração inicial salva.","success"); return self.j({"ok":True})
        if u.path=="/api/setup/finish":
            save(SETUP,{"done":True,"step":99,"finished":time.strftime("%d/%m/%Y %H:%M:%S")}); note("Assistente concluído","Sistema pronto para uso.","success"); return self.j({"ok":True})
        if u.path=="/api/upload":
            a=q.get("area",["files"])[0]; body=self.rfile.read(int(self.headers.get("Content-Length","0"))); fn,content=parse_upload(self.headers.get("Content-Type",""),body)
            if not fn: fn=f"upload_{uuid.uuid4().hex}.bin"; content=body
            (area(a)/safe(fn)).write_bytes(content); return self.j({"ok":True,"file":safe(fn)})
        if u.path=="/api/mkdir":
            data=self.body(); (area(data.get("area","files"))/safe(data.get("name","Nova pasta"))).mkdir(exist_ok=True); return self.j({"ok":True})
        if u.path=="/api/rename":
            a=q.get("area",["files"])[0]; old=safe(unquote(q.get("old",[""])[0])); new=safe(unquote(q.get("new",[""])[0])); src=area(a)/old; dst=area(a)/new
            if not src.exists() or dst.exists(): return self.j({"error":"erro ao renomear"},400)
            src.rename(dst); return self.j({"ok":True})
        if u.path=="/api/backup":
            date=run("date '+%Y-%m-%d_%H-%M-%S'"); target=AREAS["backups"]/f"backup_{date}.zip"
            with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
                for base in [AREAS["files"],AREAS["cameras"],CONFIG]:
                    for p in base.rglob("*"):
                        if p.is_file(): z.write(p,p.relative_to(BASE))
            note("Backup concluído",target.name,"success"); return self.j({"ok":True,"file":target.name})
        if u.path=="/api/camera/add":
            data=self.body(); cams=load(CAMERAS,[]); name=data.get("name") or f"Camera {len(cams)+1}"; ipaddr=data.get("ip",""); (AREAS["cameras"]/safe(name.replace(" ","_"))).mkdir(exist_ok=True)
            cam={"id":uuid.uuid4().hex[:8],"name":name,"type":data.get("type","rtsp"),"ip":ipaddr,"user":data.get("user",""),"password":data.get("password",""),"rtsp":data.get("rtsp",""),"quality":data.get("quality","media"),"recording":data.get("recording","manual"),"status":"online" if ipaddr and any(port(ipaddr,p) for p in [554,8554,80,8899]) else "cadastrada"}
            cams.append(cam); save(CAMERAS,cams); note("Câmera adicionada",name,"success"); return self.j({"ok":True,"camera":cam})
        if u.path=="/api/camera/check":
            cams=load(CAMERAS,[])
            for c in cams:
                ipaddr=c.get("ip"); c["status"]="online" if ipaddr and any(port(ipaddr,p) for p in [554,8554,80,8899]) else "offline"
            save(CAMERAS,cams); return self.j({"ok":True,"items":cams})
        if u.path=="/api/camera/delete":
            camid=self.body().get("id"); save(CAMERAS,[c for c in load(CAMERAS,[]) if c.get("id")!=camid]); return self.j({"ok":True})
        if u.path=="/api/settings":
            data=self.body(); cfg=load(SETTINGS,{}); cfg.update(data); save(SETTINGS,cfg); return self.j({"ok":True})
        if u.path=="/api/notifications/clear": save(NOTES,[]); return self.j({"ok":True})
        self.j({"error":"rota não encontrada"},404)
    def do_DELETE(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/delete":
            a=q.get("area",["files"])[0]; n=safe(unquote(q.get("name",[""])[0])); p=area(a)/n
            if p.exists() and p.is_file(): p.rename(AREAS["trash"]/f"{uuid.uuid4().hex}_{p.name}"); return self.j({"ok":True})
            return self.j({"error":"arquivo não encontrado"},404)
        self.j({"error":"rota não encontrada"},404)

print("Open Home Server API v10.1 rodando na porta 8090")
HTTPServer(("0.0.0.0",8090),H).serve_forever()
