#!/usr/bin/env python3
import json, os, shutil, subprocess, cgi
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HOME = Path.home()
BASE = HOME / "Servidor"
AREAS = {
    "files": BASE / "Files",
    "cameras": BASE / "Cameras",
    "backups": BASE / "Backups",
    "logs": BASE / "Logs"
}
WEB = BASE / "Web"
for p in list(AREAS.values()) + [WEB]:
    p.mkdir(parents=True, exist_ok=True)

def run(cmd):
    try: return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return ""

def area_dir(area):
    return AREAS.get(area, AREAS["files"])

def safe_name(name):
    return Path(name).name

def list_items(area):
    folder = area_dir(area)
    items = []
    for p in sorted(folder.iterdir(), key=lambda x:(not x.is_dir(), x.name.lower())):
        st = p.stat()
        items.append({"name":p.name,"type":"folder" if p.is_dir() else "file","size":st.st_size})
    return items

def status():
    ip = run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"
    return {
        "ip": ip,
        "nginx": "Ativo" if run("pgrep nginx") else "Parado",
        "api": "Ativa",
        "disk": run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),
        "used": run(f"df {HOME} | awk 'NR==2 {{print $5}}'"),
        "files": len(list(AREAS["files"].rglob("*"))),
        "camera_files": len(list(AREAS["cameras"].rglob("*"))),
        "backup_files": len(list(AREAS["backups"].rglob("*"))),
        "updated": run("date '+%d/%m/%Y %H:%M:%S'")
    }

class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, code=200):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_json({"ok":True})

    def do_GET(self):
        parsed=urlparse(self.path)
        qs=parse_qs(parsed.query)
        if parsed.path=="/api/status":
            self.send_json(status()); return
        if parsed.path=="/api/files":
            area=qs.get("area",["files"])[0]
            self.send_json({"area":area,"items":list_items(area)}); return
        if parsed.path=="/api/download":
            area=qs.get("area",["files"])[0]
            name=safe_name(unquote(qs.get("name",[""])[0]))
            path=area_dir(area)/name
            if not path.exists() or not path.is_file():
                self.send_json({"error":"arquivo não encontrado"},404); return
            data=path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type","application/octet-stream")
            self.send_header("Content-Disposition",f'attachment; filename="{name}"')
            self.send_header("Access-Control-Allow-Origin","*")
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data); return
        self.send_json({"error":"rota não encontrada"},404)

    def do_POST(self):
        parsed=urlparse(self.path)
        qs=parse_qs(parsed.query)
        if parsed.path=="/api/upload":
            area=qs.get("area",["files"])[0]
            form=cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD":"POST"})
            if "file" not in form:
                self.send_json({"error":"nenhum arquivo enviado"},400); return
            item=form["file"]
            name=safe_name(item.filename)
            target=area_dir(area)/name
            with open(target,"wb") as f:
                shutil.copyfileobj(item.file,f)
            self.send_json({"ok":True,"file":name}); return
        self.send_json({"error":"rota não encontrada"},404)

    def do_DELETE(self):
        parsed=urlparse(self.path)
        qs=parse_qs(parsed.query)
        if parsed.path=="/api/delete":
            area=qs.get("area",["files"])[0]
            name=safe_name(unquote(qs.get("name",[""])[0]))
            path=area_dir(area)/name
            if path.exists() and path.is_file():
                path.unlink()
                self.send_json({"ok":True}); return
            self.send_json({"error":"arquivo não encontrado"},404); return
        self.send_json({"error":"rota não encontrada"},404)

HTTPServer(("0.0.0.0",8090),Handler).serve_forever()
