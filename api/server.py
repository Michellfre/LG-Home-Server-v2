#!/usr/bin/env python3
import json, subprocess, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HOME=Path.home()
BASE=HOME/"Servidor"
AREAS={"files":BASE/"Files","cameras":BASE/"Cameras","backups":BASE/"Backups","logs":BASE/"Logs"}
WEB=BASE/"Web"; TRASH=BASE/"Trash"
for p in list(AREAS.values())+[WEB,TRASH]: p.mkdir(parents=True, exist_ok=True)

def run(cmd):
    try: return subprocess.check_output(cmd,shell=True,text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return ""
def area_dir(a): return AREAS.get(a,AREAS["files"])
def safe(n): return Path(n).name
def fsize(path):
    total=0
    for p in Path(path).rglob("*"):
        if p.is_file():
            try: total+=p.stat().st_size
            except Exception: pass
    return total
def items(area):
    out=[]
    for p in sorted(area_dir(area).iterdir(), key=lambda x:(not x.is_dir(), x.name.lower())):
        st=p.stat(); ext=p.suffix.lower(); media="other"
        if ext in [".jpg",".jpeg",".png",".gif",".webp"]: media="image"
        elif ext in [".mp4",".webm",".mov",".mkv",".avi"]: media="video"
        elif ext==".pdf": media="pdf"
        out.append({"name":p.name,"type":"folder" if p.is_dir() else "file","media":media,"size":st.st_size})
    return out
def status():
    ip=run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"
    return {"ip":ip,"nginx":"Ativo" if run("pgrep nginx") else "Parado","api":"Ativa",
    "disk":run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),
    "used":run(f"df {HOME} | awk 'NR==2 {{print $5}}'"),
    "files":len([p for p in AREAS["files"].rglob("*") if p.is_file()]),
    "camera_files":len([p for p in AREAS["cameras"].rglob("*") if p.is_file()]),
    "backup_files":len([p for p in AREAS["backups"].rglob("*") if p.is_file()]),
    "files_size":fsize(AREAS["files"]),"cameras_size":fsize(AREAS["cameras"]),"backups_size":fsize(AREAS["backups"]),
    "updated":run("date '+%d/%m/%Y %H:%M:%S'"),"python":run("python --version")}
def parse_multipart(ct, body):
    if "boundary=" not in ct: return None,None
    boundary=ct.split("boundary=",1)[1].strip().strip('"')
    for part in body.split(("--"+boundary).encode()):
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
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): return
    def j(self,d,code=200):
        b=json.dumps(d,ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Methods","GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type"); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self): self.j({"ok":True})
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/status": self.j(status()); return
        if u.path=="/api/files": 
            a=q.get("area",["files"])[0]; self.j({"area":a,"items":items(a)}); return
        if u.path in ["/api/download","/api/view"]:
            a=q.get("area",["files"])[0]; n=safe(unquote(q.get("name",[""])[0])); p=area_dir(a)/n
            if not p.exists() or not p.is_file(): self.j({"error":"arquivo não encontrado"},404); return
            data=p.read_bytes(); ext=p.suffix.lower()
            ctype="application/octet-stream"
            if ext in [".jpg",".jpeg"]: ctype="image/jpeg"
            elif ext==".png": ctype="image/png"
            elif ext==".webp": ctype="image/webp"
            elif ext==".gif": ctype="image/gif"
            elif ext==".mp4": ctype="video/mp4"
            elif ext==".webm": ctype="video/webm"
            elif ext==".pdf": ctype="application/pdf"
            self.send_response(200); self.send_header("Content-Type",ctype); self.send_header("Access-Control-Allow-Origin","*")
            if u.path=="/api/download": self.send_header("Content-Disposition",f'attachment; filename="{n}"')
            self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        self.j({"error":"rota não encontrada"},404)
    def do_POST(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/upload":
            a=q.get("area",["files"])[0]; body=self.rfile.read(int(self.headers.get("Content-Length","0")))
            fn,content=parse_multipart(self.headers.get("Content-Type",""),body)
            if not fn: fn=f"upload_{uuid.uuid4().hex}.bin"; content=body
            (area_dir(a)/safe(fn)).write_bytes(content); self.j({"ok":True,"file":safe(fn)}); return
        if u.path=="/api/rename":
            a=q.get("area",["files"])[0]; old=safe(unquote(q.get("old",[""])[0])); new=safe(unquote(q.get("new",[""])[0]))
            src=area_dir(a)/old; dst=area_dir(a)/new
            if not src.exists() or dst.exists(): self.j({"error":"erro ao renomear"},400); return
            src.rename(dst); self.j({"ok":True}); return
        if u.path=="/api/backup":
            out=run("bash scripts/backup.sh"); self.j({"ok":True,"output":out}); return
        self.j({"error":"rota não encontrada"},404)
    def do_DELETE(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/api/delete":
            a=q.get("area",["files"])[0]; n=safe(unquote(q.get("name",[""])[0])); p=area_dir(a)/n
            if p.exists() and p.is_file():
                p.rename(TRASH/f"{uuid.uuid4().hex}_{p.name}"); self.j({"ok":True}); return
            self.j({"error":"arquivo não encontrado"},404); return
        self.j({"error":"rota não encontrada"},404)
print("LG Home Server API v6 rodando na porta 8090")
HTTPServer(("0.0.0.0",8090),H).serve_forever()
