#!/usr/bin/env python3
import json, subprocess, time, uuid, zipfile, shutil, socket, mimetypes, os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

VERSION = "Open Home OS v11.0 Core"
HOME = Path.home()
BASE = HOME / "OpenHomeOS"
WEB = BASE / "Web"
CONFIG = BASE / "Config"
DATA = BASE / "Data"
LOGS = BASE / "Logs"

AREAS = {
    "files": DATA / "Files",
    "shared": DATA / "Shared",
    "documents": DATA / "Documents",
    "downloads": DATA / "Downloads",
    "media": DATA / "Media",
    "photos": DATA / "Photos",
    "videos": DATA / "Videos",
    "music": DATA / "Music",
    "cameras": DATA / "Cameras",
    "snapshots": DATA / "Snapshots",
    "streams": DATA / "Streams",
    "backups": DATA / "Backups",
    "trash": DATA / "Trash",
    "ai": DATA / "AI",
    "iot": DATA / "IoT",
}
for p in [WEB, CONFIG, DATA, LOGS] + list(AREAS.values()):
    p.mkdir(parents=True, exist_ok=True)

SETTINGS = CONFIG / "settings.json"
MODULES = CONFIG / "modules.json"
CAMERAS = CONFIG / "cameras.json"
JARVIS = CONFIG / "jarvis.json"
EVENTS = CONFIG / "events.json"
NOTES = CONFIG / "notifications.json"
CACHE = CONFIG / "sensor_cache.json"

def ensure(path, default):
    if not path.exists():
        path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")

ensure(SETTINGS, {
    "system_name": "Open Home OS",
    "device_name": "LG K41S",
    "version": VERSION,
    "theme": "dark",
    "jarvis_enabled": True,
    "jarvis_voice": True,
    "tv_mode": False,
    "battery_low_level": 20,
    "temperature_alert": 40,
    "auto_delete_when_disk_above": 90,
    "backup_hour": "02:00"
})
ensure(MODULES, [
    {"id":"dashboard","name":"Dashboard Inteligente","icon":"🏠","enabled":True,"status":"online"},
    {"id":"jarvis","name":"Jarvis IA","icon":"🤖","enabled":True,"status":"online"},
    {"id":"nvr","name":"NVR Profissional","icon":"📹","enabled":True,"status":"base"},
    {"id":"nas","name":"File Server / NAS","icon":"📁","enabled":True,"status":"online"},
    {"id":"tv","name":"TV Mode","icon":"📺","enabled":True,"status":"online"},
    {"id":"ai","name":"Central IA","icon":"🧠","enabled":True,"status":"base"},
    {"id":"iot","name":"IoT / MQTT / ESP32","icon":"📡","enabled":True,"status":"base"},
    {"id":"security","name":"Segurança","icon":"🔒","enabled":True,"status":"base"},
    {"id":"media","name":"Multimídia","icon":"🎵","enabled":True,"status":"base"},
    {"id":"backup","name":"Backup","icon":"☁️","enabled":True,"status":"online"},
    {"id":"system","name":"Sistema","icon":"⚙️","enabled":True,"status":"online"},
    {"id":"logs","name":"Logs","icon":"📜","enabled":True,"status":"online"}
])
ensure(CAMERAS, [])
ensure(JARVIS, {"history": [], "last_command": "", "last_reply": "", "name": "Jarvis"})
ensure(EVENTS, [])
ensure(NOTES, [])
ensure(CACHE, {"ts": 0})

NET_LAST = {"time": time.time(), "rx": 0, "tx": 0}
CPU_LAST = {"total": 0, "idle": 0}

def run(cmd, timeout=6):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()
    except Exception:
        return ""

def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def event(kind, message="", level="info", module="core"):
    items = load(EVENTS, [])
    items.insert(0, {
        "id": uuid.uuid4().hex[:8],
        "kind": kind,
        "module": module,
        "message": message,
        "level": level,
        "time": time.strftime("%d/%m/%Y %H:%M:%S")
    })
    save(EVENTS, items[:1000])

def notify(title, message, level="info"):
    items = load(NOTES, [])
    items.insert(0, {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "message": message,
        "level": level,
        "time": time.strftime("%d/%m/%Y %H:%M:%S")
    })
    save(NOTES, items[:300])

def ip_addr():
    return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"

def disk_used():
    try:
        return int(run(f"df {HOME} | awk 'NR==2 {{print $5}}'").replace("%",""))
    except Exception:
        return 0

def cpu_pct():
    global CPU_LAST
    try:
        vals = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        if not CPU_LAST["total"]:
            CPU_LAST = {"total": total, "idle": idle}
            return "calculando..."
        dt = total - CPU_LAST["total"]
        di = idle - CPU_LAST["idle"]
        CPU_LAST = {"total": total, "idle": idle}
        return f"{max(0, min(100, int((1 - di / dt) * 100)))}%" if dt > 0 else "0%"
    except Exception:
        return "indisponível"

def termux_json(cmd):
    out = run(cmd, 5)
    try:
        return json.loads(out) if out else {}
    except Exception:
        return {}

def battery():
    b = termux_json("termux-battery-status")
    if b:
        return {"available": True, **b}
    return {"available": False, "message": "Termux:API não respondeu"}

def wifi():
    w = termux_json("termux-wifi-connectioninfo")
    if w:
        return {"available": True, **w}
    return {"available": False, "ssid": "indisponível"}

def thermal():
    for base in ["/sys/class/thermal", "/sys/devices/virtual/thermal"]:
        b = Path(base)
        if b.exists():
            for p in b.glob("thermal_zone*/temp"):
                try:
                    n = int(p.read_text().strip())
                    t = n / 1000 if n > 1000 else n / 10 if n > 100 else n
                    if 10 <= t <= 95:
                        return t
                except Exception:
                    pass
    return None

def sensors(force=False):
    cache = load(CACHE, {"ts": 0})
    if not force and time.time() - cache.get("ts", 0) < 4 and cache.get("battery"):
        return cache
    b = battery()
    w = wifi()
    temp = b.get("temperature") if b.get("temperature") is not None else thermal()
    data = {
        "ts": time.time(),
        "battery": b,
        "wifi": w,
        "temperature": temp,
        "device": {
            "manufacturer": run("getprop ro.product.manufacturer"),
            "model": run("getprop ro.product.model"),
            "android": run("getprop ro.build.version.release"),
            "sdk": run("getprop ro.build.version.sdk"),
            "kernel": run("uname -r")
        },
        "termux_api": bool(run("command -v termux-battery-status")),
        "ffmpeg": bool(run("command -v ffmpeg")),
        "python": run("python --version")
    }
    save(CACHE, data)
    return data

def net_speed():
    global NET_LAST
    raw = run("cat /proc/net/dev | awk '/wlan|eth|rmnet/ {rx+=$2; tx+=$10} END {print rx\",\"tx}'")
    try:
        rx, tx = [int(x or 0) for x in raw.split(",")]
    except Exception:
        rx = tx = 0
    now = time.time()
    elapsed = max(1, now - NET_LAST["time"])
    data = {
        "download_s": max(0, int((rx - NET_LAST["rx"]) / elapsed)),
        "upload_s": max(0, int((tx - NET_LAST["tx"]) / elapsed)),
        "rx": rx,
        "tx": tx
    }
    NET_LAST = {"time": now, "rx": rx, "tx": tx}
    return data

def camera_counts():
    cams = load(CAMERAS, [])
    return {
        "registered": len(cams),
        "online": len([c for c in cams if c.get("verified") and c.get("status") == "online"]),
        "pending": len([c for c in cams if not c.get("verified")]),
        "offline": len([c for c in cams if c.get("status") == "offline"]),
        "recording": len([c for c in cams if c.get("recording") in ["always","motion","schedule"] and c.get("verified")])
    }

def status():
    s = sensors()
    cfg = load(SETTINGS, {})
    b = s.get("battery", {})
    w = s.get("wifi", {})
    cc = camera_counts()
    return {
        "version": VERSION,
        "ip": ip_addr(),
        "nginx": "Ativo" if run("pgrep nginx") else "Parado",
        "api": "Ativa",
        "disk": run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),
        "used": f"{disk_used()}%",
        "cpu": cpu_pct(),
        "load": run("cat /proc/loadavg | awk '{print $1}'"),
        "mem": run("free -m | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'") or "indisponível",
        "uptime": run("uptime -p") or "indisponível",
        "battery": f"{b.get('percentage')}% • {b.get('status','')}" if b.get("percentage") is not None else "indisponível",
        "battery_detail": b,
        "temperature": f"{s.get('temperature')}°C" if s.get("temperature") is not None else "indisponível",
        "wifi": w.get("ssid") or "indisponível",
        "wifi_detail": w,
        "network": net_speed(),
        "device": s.get("device", {}),
        "modules": load(MODULES, []),
        "cameras": cc,
        "snapshots": len([p for p in AREAS["snapshots"].rglob("*") if p.is_file()]),
        "files": len([p for p in AREAS["files"].rglob("*") if p.is_file()]),
        "backups": len([p for p in AREAS["backups"].rglob("*") if p.is_file()]),
        "settings": cfg,
        "updated": run("date '+%d/%m/%Y %H:%M:%S'"),
    }

def media_type(p):
    ext = p.suffix.lower()
    if ext in [".jpg",".jpeg",".png",".gif",".webp",".bmp"]:
        return "image"
    if ext in [".mp4",".webm",".mov",".mkv",".avi",".m4v",".ts"]:
        return "video"
    if ext in [".mp3",".wav",".ogg",".m4a",".flac"]:
        return "audio"
    if ext == ".pdf":
        return "pdf"
    if ext in [".zip",".rar",".7z",".tar",".gz"]:
        return "archive"
    if ext in [".doc",".docx",".xls",".xlsx",".ppt",".pptx",".txt",".md"]:
        return "document"
    return "other"

def list_files(area="files", q="", sort="name"):
    root = AREAS.get(area, AREAS["files"])
    rows = []
    query = q.lower().strip()
    for p in root.iterdir():
        if query and query not in p.name.lower():
            continue
        try:
            st = p.stat()
            rows.append({
                "name": p.name,
                "type": "folder" if p.is_dir() else "file",
                "media": media_type(p),
                "size": st.st_size,
                "modified_ts": st.st_mtime,
                "modified": time.strftime("%d/%m/%Y %H:%M", time.localtime(st.st_mtime))
            })
        except Exception:
            pass
    rows.sort(key=(lambda x: x["modified_ts"]) if sort == "date" else (lambda x: x["size"]) if sort == "size" else (lambda x: (x["type"] != "folder", x["name"].lower())), reverse=sort in ["date","size"])
    return rows

def parse_upload(content_type, body):
    if "boundary=" not in content_type:
        return None, None
    boundary = content_type.split("boundary=",1)[1].strip().strip('"')
    for part in body.split(("--" + boundary).encode()):
        if b"Content-Disposition" in part and b"\r\n\r\n" in part:
            headers, content = part.split(b"\r\n\r\n", 1)
            if content.endswith(b"\r\n"):
                content = content[:-2]
            hs = headers.decode("utf-8", "ignore")
            filename = None
            for piece in hs.split(";"):
                piece = piece.strip()
                if piece.startswith("filename="):
                    filename = piece.split("=",1)[1].strip().strip('"')
            if filename:
                return Path(filename).name, content
    return None, None

def create_backup(kind="manual"):
    ts = run("date '+%Y-%m-%d_%H-%M-%S'")
    target = AREAS["backups"] / f"openhomeos_backup_{kind}_{ts}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for base in [CONFIG, AREAS["files"], AREAS["documents"], AREAS["cameras"], AREAS["snapshots"]]:
            for p in base.rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(BASE))
    event("backup", target.name, "success", "backup")
    notify("Backup concluído", target.name, "success")
    return target.name

def jarvis_command(command):
    text = (command or "").lower().strip()
    st = status()
    reply = "Comando não reconhecido. Tente: Jarvis status, Jarvis modo TV, Jarvis câmeras, Jarvis backup."
    action = "none"
    if "status" in text or "servidor" in text:
        reply = f"Open Home OS online. IP {st['ip']}. Disco {st['disk']}. Bateria {st['battery']}. Câmeras online: {st['cameras']['online']}."
        action = "speak"
    elif "tv" in text or "espelhar" in text:
        cfg = load(SETTINGS, {})
        cfg["tv_mode"] = True
        save(SETTINGS, cfg)
        reply = "Modo TV ativado."
        action = "open_tv"
    elif "dashboard" in text or "painel" in text:
        reply = "Abrindo dashboard inteligente."
        action = "open_dashboard"
    elif "camera" in text or "câmera" in text:
        c = st["cameras"]
        reply = f"{c['registered']} câmeras cadastradas. {c['online']} online, {c['pending']} pendentes e {c['offline']} offline."
        action = "open_nvr"
    elif "backup" in text:
        f = create_backup("jarvis")
        reply = f"Backup criado: {f}."
        action = "backup"
    elif "bateria" in text:
        reply = f"Bateria em {st['battery']}."
        action = "speak"
    elif "temperatura" in text:
        reply = f"Temperatura do servidor: {st['temperature']}."
        action = "speak"
    j = load(JARVIS, {"history":[]})
    j["last_command"] = command
    j["last_reply"] = reply
    j.setdefault("history", []).insert(0, {"command": command, "reply": reply, "action": action, "time": time.strftime("%d/%m/%Y %H:%M:%S")})
    j["history"] = j["history"][:100]
    save(JARVIS, j)
    return {"ok": True, "reply": reply, "action": action, "status": st}

def send_file(handler, path, download=False):
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
    handler.send_header("Access-Control-Allow-Origin", "*")
    if download:
        handler.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8", "ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.json({"ok": True})

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/status":
            return self.json(status())
        if u.path == "/api/modules":
            return self.json({"items": load(MODULES, [])})
        if u.path == "/api/events":
            return self.json({"items": load(EVENTS, [])})
        if u.path == "/api/notifications":
            return self.json({"items": load(NOTES, [])})
        if u.path == "/api/jarvis":
            return self.json(load(JARVIS, {}))
        if u.path == "/api/cameras":
            return self.json({"items": load(CAMERAS, [])})
        if u.path == "/api/files":
            return self.json({"items": list_files(q.get("area", ["files"])[0], q.get("q", [""])[0], q.get("sort", ["name"])[0])})
        if u.path == "/api/system/diagnostic":
            return self.json({
                "status": status(),
                "processes": run("ps 2>/dev/null | head -40"),
                "api_log": "\n".join((LOGS / "api.log").read_text(errors="ignore").splitlines()[-80:]) if (LOGS / "api.log").exists() else "",
                "ffmpeg": run("ffmpeg -version | head -1") if run("command -v ffmpeg") else "não instalado",
                "termux_api": bool(run("command -v termux-battery-status"))
            })
        if u.path in ["/api/view", "/api/download"]:
            a = q.get("area", ["files"])[0]
            n = Path(unquote(q.get("name", [""])[0])).name
            p = AREAS.get(a, AREAS["files"]) / n
            if not p.exists() or not p.is_file():
                return self.json({"error": "arquivo não encontrado"}, 404)
            return send_file(self, p, u.path == "/api/download")
        return self.json({"error": "rota não encontrada"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/jarvis/command":
            return self.json(jarvis_command(self.body().get("command", "")))
        if u.path == "/api/settings":
            cfg = load(SETTINGS, {})
            cfg.update(self.body())
            save(SETTINGS, cfg)
            return self.json({"ok": True, "settings": cfg})
        if u.path == "/api/modules":
            save(MODULES, self.body().get("items", load(MODULES, [])))
            return self.json({"ok": True})
        if u.path == "/api/backup":
            return self.json({"ok": True, "file": create_backup(self.body().get("kind", "manual"))})
        if u.path == "/api/upload":
            area = q.get("area", ["files"])[0]
            raw = self.rfile.read(int(self.headers.get("Content-Length","0")))
            fn, content = parse_upload(self.headers.get("Content-Type",""), raw)
            if not fn:
                fn = f"upload_{uuid.uuid4().hex}.bin"
                content = raw
            (AREAS.get(area, AREAS["files"]) / fn).write_bytes(content)
            return self.json({"ok": True, "file": fn})
        if u.path == "/api/camera/add":
            cam = self.body()
            cam.setdefault("id", uuid.uuid4().hex[:8])
            cam.setdefault("verified", False)
            cam.setdefault("status", "pending")
            cams = load(CAMERAS, [])
            cams.append(cam)
            save(CAMERAS, cams)
            return self.json({"ok": True, "camera": cam})
        if u.path == "/api/camera/delete":
            cid = self.body().get("id")
            save(CAMERAS, [c for c in load(CAMERAS, []) if c.get("id") != cid])
            return self.json({"ok": True})
        if u.path == "/api/notifications/clear":
            save(NOTES, [])
            return self.json({"ok": True})
        return self.json({"error": "rota não encontrada"}, 404)

    def do_DELETE(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/delete":
            a = q.get("area", ["files"])[0]
            n = Path(unquote(q.get("name", [""])[0])).name
            p = AREAS.get(a, AREAS["files"]) / n
            if p.exists() and p.is_file():
                p.rename(AREAS["trash"] / f"{uuid.uuid4().hex}_{p.name}")
                return self.json({"ok": True})
            return self.json({"error": "não encontrado"}, 404)
        return self.json({"error": "rota não encontrada"}, 404)

event("server_start", f"{VERSION} iniciado", "success", "core")
print(f"{VERSION} API rodando na porta 8090")
HTTPServer(("0.0.0.0", 8090), H).serve_forever()
