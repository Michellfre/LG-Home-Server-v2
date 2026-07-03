#!/usr/bin/env python3
import json, subprocess, uuid, time, zipfile, socket, ipaddress, os, shutil, mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HOME = Path.home()
BASE = HOME / "Servidor"
WEB = BASE / "Web"
CONFIG = BASE / "Config"

AREAS = {
    "files": BASE / "Files",
    "shared": BASE / "Shared",
    "documents": BASE / "Documents",
    "downloads": BASE / "Downloads",
    "media": BASE / "Media",
    "photos": BASE / "Photos",
    "videos": BASE / "Videos",
    "music": BASE / "Music",
    "cameras": BASE / "Cameras",
    "backups": BASE / "Backups",
    "trash": BASE / "Trash",
    "logs": BASE / "Logs"
}

for p in list(AREAS.values()) + [WEB, CONFIG]:
    p.mkdir(parents=True, exist_ok=True)

CAMERAS = CONFIG / "cameras.json"
SETTINGS = CONFIG / "settings.json"
SETUP = CONFIG / "setup.json"
NOTES = CONFIG / "notifications.json"
EVENTS = CONFIG / "events.json"
USERS = CONFIG / "users.json"

def ensure(path, data):
    if not path.exists():
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

ensure(CAMERAS, [])
ensure(NOTES, [])
ensure(EVENTS, [])
ensure(USERS, [{"user": "admin", "role": "Administrador", "enabled": True}])
ensure(SETUP, {"done": False, "step": 1})
ensure(SETTINGS, {
    "project_name": "Open Home Server",
    "device_name": "Android Server",
    "storage_path": str(BASE),
    "camera_retention_days": 30,
    "auto_delete_when_disk_above": 90,
    "backup_hour": "02:00",
    "backup_daily": True,
    "backup_weekly": False,
    "backup_google_drive": False,
    "backup_usb": False,
    "theme": "dark",
    "notifications": True,
    "web_port": 8080,
    "api_port": 8090,
    "remote_access": False,
    "motion_detection": False,
    "library_auto_sort": True
})

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def notify(title, message, level="info"):
    arr = load(NOTES, [])
    arr.insert(0, {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "message": message,
        "level": level,
        "time": time.strftime("%d/%m/%Y %H:%M:%S")
    })
    save(NOTES, arr[:100])

def add_event(kind, camera="", message="", level="info"):
    arr = load(EVENTS, [])
    arr.insert(0, {
        "id": uuid.uuid4().hex[:8],
        "kind": kind,
        "camera": camera,
        "message": message,
        "level": level,
        "time": time.strftime("%d/%m/%Y %H:%M:%S"),
        "date": time.strftime("%Y-%m-%d")
    })
    save(EVENTS, arr[:500])

def safe(name):
    return Path(name).name

def area_dir(area):
    return AREAS.get(area, AREAS["files"])

def media_type(path):
    ext = path.suffix.lower()
    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]: return "image"
    if ext in [".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"]: return "video"
    if ext in [".mp3", ".wav", ".ogg", ".m4a", ".flac"]: return "audio"
    if ext == ".pdf": return "pdf"
    if ext in [".zip", ".rar", ".7z", ".tar", ".gz"]: return "archive"
    if ext in [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md"]: return "document"
    return "other"

def list_items(area, query="", sort="name"):
    folder = area_dir(area)
    rows = []
    q = query.lower().strip()
    for p in folder.iterdir():
        if q and q not in p.name.lower():
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

    if sort == "date":
        rows.sort(key=lambda x: x["modified_ts"], reverse=True)
    elif sort == "size":
        rows.sort(key=lambda x: x["size"], reverse=True)
    else:
        rows.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))
    return rows

def local_ip():
    return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"

def disk_used_int():
    val = run(f"df {HOME} | awk 'NR==2 {{print $5}}'").replace("%", "")
    try:
        return int(val)
    except Exception:
        return 0

def get_cpu():
    loadavg = run("cat /proc/loadavg 2>/dev/null | awk '{print $1}'")
    return loadavg or "indisponível"

def get_temp():
    for p in ["/sys/class/thermal/thermal_zone0/temp", "/sys/class/power_supply/battery/temp"]:
        try:
            val = Path(p).read_text().strip()
            if val:
                n = int(val)
                if n > 1000:
                    return f"{n/1000:.1f}°C"
                return f"{n/10:.1f}°C"
        except Exception:
            pass
    return "indisponível"

def get_battery():
    base = Path("/sys/class/power_supply/battery")
    try:
        cap = (base / "capacity").read_text().strip()
        status = (base / "status").read_text().strip()
        return f"{cap}% • {status}"
    except Exception:
        return "indisponível"

def get_wifi():
    ssid = run("termux-wifi-connectioninfo 2>/dev/null | grep -o '\"ssid\": *\"[^\"]*\"' | head -1 | cut -d '\"' -f4")
    if ssid:
        return ssid
    return run("ip route 2>/dev/null | awk '/default/ {print $5; exit}'") or "indisponível"

def get_net():
    rx = run("cat /proc/net/dev 2>/dev/null | awk '/wlan|eth/ {rx+=$2; tx+=$10} END {print rx\",\"tx}'")
    if not rx:
        return {"rx": 0, "tx": 0}
    try:
        a, b = rx.split(",")
        return {"rx": int(a or 0), "tx": int(b or 0)}
    except Exception:
        return {"rx": 0, "tx": 0}

def status():
    cams = load(CAMERAS, [])
    st = {
        "ip": local_ip(),
        "nginx": "Ativo" if run("pgrep nginx") else "Parado",
        "api": "Ativa",
        "disk": run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),
        "used": f"{disk_used_int()}%",
        "cpu": get_cpu(),
        "mem": run("free -m 2>/dev/null | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'") or "indisponível",
        "uptime": run("uptime -p 2>/dev/null") or "indisponível",
        "temperature": get_temp(),
        "battery": get_battery(),
        "wifi": get_wifi(),
        "network": get_net(),
        "files": len([p for p in AREAS["files"].rglob("*") if p.is_file()]),
        "camera_files": len([p for p in AREAS["cameras"].rglob("*") if p.is_file()]),
        "backup_files": len([p for p in AREAS["backups"].rglob("*") if p.is_file()]),
        "trash_files": len([p for p in AREAS["trash"].rglob("*") if p.is_file()]),
        "cameras_total": len(cams),
        "cameras_online": len([c for c in cams if c.get("status") == "online"]),
        "cameras_recording": len([c for c in cams if c.get("recording") in ["always", "motion", "schedule"]]),
        "setup": load(SETUP, {}),
        "settings": load(SETTINGS, {}),
        "updated": run("date '+%d/%m/%Y %H:%M:%S'"),
        "python": run("python --version")
    }
    threshold = int(st["settings"].get("auto_delete_when_disk_above", 90))
    if disk_used_int() >= threshold:
        notify("Espaço baixo", f"Disco em {st['used']}. Considere limpar gravações.", "warning")
    return st

def parse_upload(ct, body):
    if "boundary=" not in ct:
        return None, None
    boundary = ct.split("boundary=", 1)[1].strip().strip('"')
    for part in body.split(("--" + boundary).encode()):
        if b"Content-Disposition" not in part or b"\r\n\r\n" not in part:
            continue
        h, c = part.split(b"\r\n\r\n", 1)
        if c.endswith(b"\r\n"): c = c[:-2]
        if c.endswith(b"--"): c = c[:-2]
        hs = h.decode("utf-8", "ignore")
        filename = None
        for piece in hs.split(";"):
            piece = piece.strip()
            if piece.startswith("filename="):
                filename = piece.split("=", 1)[1].strip().strip('"')
        if filename:
            return safe(filename), c
    return None, None

def send_file(handler, p, download=False):
    data = p.read_bytes()
    ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Access-Control-Allow-Origin", "*")
    if download:
        handler.send_header("Content-Disposition", f'attachment; filename="{p.name}"')
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

def test_port(host, port, timeout=0.25):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def discover_devices():
    me = local_ip()
    if me == "não encontrado":
        return []
    net = ipaddress.ip_network(me + "/24", strict=False)
    results = []
    ports = [554, 8554, 80, 8080, 8899, 5000, 8000, 8081]
    for h in list(net.hosts()):
        ip = str(h)
        if ip == me:
            continue
        open_ports = [p for p in ports if test_port(ip, p)]
        if open_ports:
            kind = "Dispositivo"
            if 8899 in open_ports:
                kind = "Possível Yoosee"
            elif 554 in open_ports or 8554 in open_ports:
                kind = "Possível RTSP/ONVIF"
            elif 8080 in open_ports or 8081 in open_ports:
                kind = "Possível IP Camera/ESP32-CAM"
            results.append({"ip": ip, "ports": open_ports, "type": kind, "suggested_name": f"Camera {len(results)+1}"})
    notify("Busca de câmeras", f"{len(results)} dispositivo(s) encontrado(s).")
    return results

def rtsp_suggestions(ip, user="", password=""):
    auth = f"{user}:{password}@" if user or password else ""
    return [
        f"rtsp://{auth}{ip}:554/onvif1",
        f"rtsp://{auth}{ip}:554/onvif2",
        f"rtsp://{auth}{ip}:554/live/ch00_0",
        f"rtsp://{auth}{ip}:554/live/ch00_1",
        f"rtsp://{auth}{ip}:554/11",
        f"rtsp://{auth}{ip}:554/12",
        f"rtsp://{auth}{ip}:8554/live",
        f"http://{ip}:8080/video",
        f"http://{ip}:8081/stream"
    ]

def timeline():
    counts = {}
    for p in AREAS["cameras"].rglob("*"):
        if p.is_file():
            day = time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime))
            counts[day] = counts.get(day, 0) + 1
    out = []
    for day, count in sorted(counts.items(), reverse=True):
        blocks = min(24, max(1, count))
        out.append({"date": day, "count": count, "blocks": blocks})
    return out

def library_stats():
    counts = {"image":0, "video":0, "audio":0, "pdf":0, "archive":0, "document":0, "other":0}
    for a in ["files", "documents", "downloads", "media", "photos", "videos", "music", "cameras"]:
        for p in area_dir(a).rglob("*"):
            if p.is_file():
                t = media_type(p)
                counts[t] = counts.get(t, 0) + 1
    return counts

def cleanup_old(days):
    limit = time.time() - (int(days) * 86400)
    removed = 0
    for p in AREAS["cameras"].rglob("*"):
        if p.is_file() and p.stat().st_mtime < limit:
            target = AREAS["trash"] / f"{uuid.uuid4().hex}_{p.name}"
            p.rename(target)
            removed += 1
    if removed:
        notify("Limpeza concluída", f"{removed} gravação(ões) movidas para a lixeira.", "warning")
    return removed

def make_backup(kind="manual"):
    date = run("date '+%Y-%m-%d_%H-%M-%S'")
    target = AREAS["backups"] / f"backup_{kind}_{date}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for base in [AREAS["files"], AREAS["documents"], AREAS["cameras"], CONFIG]:
            for p in base.rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(BASE))
    notify("Backup concluído", target.name, "success")
    return target.name

class H(BaseHTTPRequestHandler):
    def log_message(self, *args): return

    def json(self, data, code=200):
        b = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body_json(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8", "ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self): self.json({"ok": True})

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path == "/api/status": return self.json(status())
        if u.path == "/api/setup": return self.json(load(SETUP, {}))
        if u.path == "/api/settings": return self.json(load(SETTINGS, {}))
        if u.path == "/api/library": return self.json(library_stats())
        if u.path == "/api/timeline": return self.json({"items": timeline()})
        if u.path == "/api/events": return self.json({"items": load(EVENTS, [])})
        if u.path == "/api/notifications": return self.json({"items": load(NOTES, [])})
        if u.path == "/api/users": return self.json({"items": load(USERS, [])})
        if u.path == "/api/cameras": return self.json({"items": load(CAMERAS, [])})
        if u.path == "/api/camera/discover": return self.json({"items": discover_devices()})
        if u.path == "/api/camera/suggest":
            return self.json({"items": rtsp_suggestions(q.get("ip", [""])[0], q.get("user", [""])[0], q.get("password", [""])[0])})
        if u.path == "/api/files":
            return self.json({"area": q.get("area", ["files"])[0], "items": list_items(q.get("area", ["files"])[0], q.get("q", [""])[0], q.get("sort", ["name"])[0])})
        if u.path in ["/api/view", "/api/download"]:
            p = area_dir(q.get("area", ["files"])[0]) / safe(unquote(q.get("name", [""])[0]))
            if not p.exists() or not p.is_file():
                return self.json({"error": "arquivo não encontrado"}, 404)
            return send_file(self, p, u.path == "/api/download")
        return self.json({"error": "rota não encontrada"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path == "/api/setup":
            data = self.body_json()
            setup = load(SETUP, {})
            setup.update(data)
            save(SETUP, setup)
            cfg = load(SETTINGS, {})
            for k in ["device_name", "storage_path", "camera_retention_days", "auto_delete_when_disk_above", "backup_hour"]:
                if k in data:
                    cfg[k] = data[k]
            save(SETTINGS, cfg)
            notify("Assistente", "Configuração salva.", "success")
            return self.json({"ok": True})
        if u.path == "/api/setup/finish":
            save(SETUP, {"done": True, "step": 99, "finished": time.strftime("%d/%m/%Y %H:%M:%S")})
            notify("Assistente concluído", "Sistema pronto para uso.", "success")
            return self.json({"ok": True})
        if u.path == "/api/upload":
            a = q.get("area", ["files"])[0]
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            fn, content = parse_upload(self.headers.get("Content-Type", ""), body)
            if not fn:
                fn = f"upload_{uuid.uuid4().hex}.bin"
                content = body
            (area_dir(a) / safe(fn)).write_bytes(content)
            return self.json({"ok": True, "file": safe(fn)})
        if u.path == "/api/mkdir":
            data = self.body_json()
            (area_dir(data.get("area", "files")) / safe(data.get("name", "Nova pasta"))).mkdir(exist_ok=True)
            return self.json({"ok": True})
        if u.path == "/api/rename":
            a = q.get("area", ["files"])[0]
            old = safe(unquote(q.get("old", [""])[0]))
            new = safe(unquote(q.get("new", [""])[0]))
            src = area_dir(a) / old
            dst = area_dir(a) / new
            if not src.exists() or dst.exists():
                return self.json({"error": "erro ao renomear"}, 400)
            src.rename(dst)
            return self.json({"ok": True})
        if u.path == "/api/move":
            data = self.body_json()
            src = area_dir(data.get("from", "files")) / safe(data.get("name", ""))
            dst = area_dir(data.get("to", "files")) / safe(data.get("name", ""))
            if not src.exists():
                return self.json({"error": "arquivo não encontrado"}, 404)
            shutil.move(str(src), str(dst))
            return self.json({"ok": True})
        if u.path == "/api/copy":
            data = self.body_json()
            src = area_dir(data.get("from", "files")) / safe(data.get("name", ""))
            dst = area_dir(data.get("to", "files")) / safe(data.get("name", ""))
            if not src.exists() or not src.is_file():
                return self.json({"error": "arquivo não encontrado"}, 404)
            shutil.copy2(src, dst)
            return self.json({"ok": True})
        if u.path == "/api/backup":
            data = self.body_json()
            return self.json({"ok": True, "file": make_backup(data.get("kind", "manual"))})
        if u.path == "/api/restore":
            n = safe(unquote(q.get("name", [""])[0]))
            src = AREAS["trash"] / n
            if not src.exists():
                return self.json({"error": "não encontrado"}, 404)
            clean = "_".join(n.split("_")[1:]) if "_" in n else n
            src.rename(AREAS["files"] / clean)
            return self.json({"ok": True})
        if u.path == "/api/settings":
            data = self.body_json()
            cfg = load(SETTINGS, {})
            cfg.update(data)
            save(SETTINGS, cfg)
            notify("Configurações", "Preferências atualizadas.", "success")
            return self.json({"ok": True})
        if u.path == "/api/cleanup":
            days = load(SETTINGS, {}).get("camera_retention_days", 30)
            return self.json({"ok": True, "removed": cleanup_old(days)})
        if u.path == "/api/camera/add":
            data = self.body_json()
            cams = load(CAMERAS, [])
            name = data.get("name") or f"Camera {len(cams)+1}"
            ip = data.get("ip", "")
            folder = AREAS["cameras"] / safe(name.replace(" ", "_"))
            folder.mkdir(exist_ok=True)
            cam = {
                "id": uuid.uuid4().hex[:8],
                "name": name,
                "type": data.get("type", "rtsp"),
                "brand": data.get("brand", data.get("type", "IP Camera")),
                "ip": ip,
                "user": data.get("user", ""),
                "password": data.get("password", ""),
                "rtsp": data.get("rtsp", ""),
                "quality": data.get("quality", "media"),
                "resolution": data.get("resolution", "Auto"),
                "recording": data.get("recording", "manual"),
                "location": data.get("location", ""),
                "folder": str(folder),
                "status": "online" if ip and any(test_port(ip, p) for p in [554, 8554, 80, 8080, 8899]) else "cadastrada",
                "snapshot": ""
            }
            cams.append(cam)
            save(CAMERAS, cams)
            notify("Câmera adicionada", name, "success")
            add_event("camera_added", name, "Câmera cadastrada.", "success")
            return self.json({"ok": True, "camera": cam})
        if u.path == "/api/camera/add_many":
            data = self.body_json()
            cams = load(CAMERAS, [])
            added = 0
            for item in data.get("items", []):
                name = item.get("name") or item.get("suggested_name") or f"Camera {len(cams)+1}"
                ip = item.get("ip", "")
                if not ip:
                    continue
                folder = AREAS["cameras"] / safe(name.replace(" ", "_"))
                folder.mkdir(exist_ok=True)
                cams.append({
                    "id": uuid.uuid4().hex[:8],
                    "name": name,
                    "type": item.get("type", "ipcam"),
                    "brand": item.get("type", "IP Camera"),
                    "ip": ip,
                    "user": "",
                    "password": "",
                    "rtsp": rtsp_suggestions(ip)[0] if ("RTSP" in item.get("type","")) else "",
                    "quality": "media",
                    "resolution": "Auto",
                    "recording": "manual",
                    "location": "",
                    "folder": str(folder),
                    "status": "online",
                    "snapshot": ""
                })
                added += 1
            save(CAMERAS, cams)
            notify("Câmeras adicionadas", f"{added} câmera(s) adicionada(s).", "success")
            return self.json({"ok": True, "added": added})
        if u.path == "/api/camera/check":
            cams = load(CAMERAS, [])
            for c in cams:
                ip = c.get("ip")
                old = c.get("status")
                c["status"] = "online" if ip and any(test_port(ip, p) for p in [554, 8554, 80, 8080, 8899]) else "offline"
                if old != c["status"]:
                    add_event("camera_status", c.get("name", ""), f"Status mudou para {c['status']}", "warning" if c["status"] == "offline" else "success")
            save(CAMERAS, cams)
            return self.json({"ok": True, "items": cams})
        if u.path == "/api/camera/delete":
            cid = self.body_json().get("id")
            save(CAMERAS, [c for c in load(CAMERAS, []) if c.get("id") != cid])
            return self.json({"ok": True})
        if u.path == "/api/notifications/clear":
            save(NOTES, [])
            return self.json({"ok": True})
        if u.path == "/api/trash/empty":
            for p in AREAS["trash"].iterdir():
                if p.is_file():
                    p.unlink()
            return self.json({"ok": True})
        return self.json({"error": "rota não encontrada"}, 404)

    def do_DELETE(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/delete":
            a = q.get("area", ["files"])[0]
            n = safe(unquote(q.get("name", [""])[0]))
            p = area_dir(a) / n
            if p.exists() and p.is_file():
                p.rename(AREAS["trash"] / f"{uuid.uuid4().hex}_{p.name}")
                return self.json({"ok": True})
            return self.json({"error": "arquivo não encontrado"}, 404)
        return self.json({"error": "rota não encontrada"}, 404)

print("Open Home Server API v10.2 Enterprise LTS rodando na porta 8090")
HTTPServer(("0.0.0.0", 8090), H).serve_forever()
