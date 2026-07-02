#!/usr/bin/env python3
import json, subprocess, uuid, time, zipfile, socket, ipaddress, os, shutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HOME = Path.home()
BASE = HOME / "Servidor"
AREAS = {
    "files": BASE / "Files",
    "cameras": BASE / "Cameras",
    "backups": BASE / "Backups",
    "logs": BASE / "Logs",
    "trash": BASE / "Trash",
    "media": BASE / "Media",
    "downloads": BASE / "Downloads",
    "documents": BASE / "Documents",
}
WEB = BASE / "Web"
CONFIG = BASE / "Config"
CAMERA_FILE = CONFIG / "cameras.json"
SETTINGS_FILE = CONFIG / "settings.json"
NOTIFY_FILE = CONFIG / "notifications.json"

for p in list(AREAS.values()) + [WEB, CONFIG]:
    p.mkdir(parents=True, exist_ok=True)

if not CAMERA_FILE.exists():
    CAMERA_FILE.write_text("[]", encoding="utf-8")

if not NOTIFY_FILE.exists():
    NOTIFY_FILE.write_text("[]", encoding="utf-8")

if not SETTINGS_FILE.exists():
    SETTINGS_FILE.write_text(json.dumps({
        "camera_retention_days": 30,
        "auto_delete_when_disk_above": 90,
        "backup_hour": "02:00",
        "theme": "dark",
        "notifications": True
    }, ensure_ascii=False, indent=2), encoding="utf-8")

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

def jload(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def jsave(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def notify(title, message, level="info"):
    items = jload(NOTIFY_FILE, [])
    items.insert(0, {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "message": message,
        "level": level,
        "time": time.strftime("%d/%m/%Y %H:%M:%S")
    })
    jsave(NOTIFY_FILE, items[:50])

def safe(n):
    return Path(n).name

def area_dir(a):
    return AREAS.get(a, AREAS["files"])

def media_type(p):
    ext = p.suffix.lower()
    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]: return "image"
    if ext in [".mp4", ".webm", ".mov", ".mkv", ".avi"]: return "video"
    if ext == ".pdf": return "pdf"
    if ext in [".mp3", ".wav", ".ogg", ".m4a"]: return "audio"
    if ext in [".zip",".rar",".7z",".tar",".gz"]: return "archive"
    return "other"

def list_items(area, query="", sort="name"):
    folder = area_dir(area)
    q = query.lower().strip()
    rows = []
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

def folder_size(path):
    total = 0
    for p in Path(path).rglob("*"):
        if p.is_file():
            try: total += p.stat().st_size
            except Exception: pass
    return total

def local_ip():
    ip = run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'")
    return ip or "não encontrado"

def status():
    ip = local_ip()
    mem = run("free -m 2>/dev/null | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'")
    uptime = run("uptime -p 2>/dev/null") or "indisponível"
    cams = jload(CAMERA_FILE, [])
    online = len([c for c in cams if c.get("status") == "online"])
    used_percent = run(f"df {HOME} | awk 'NR==2 {{print $5}}'")
    return {
        "ip": ip,
        "nginx": "Ativo" if run("pgrep nginx") else "Parado",
        "api": "Ativa",
        "disk": run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),
        "used": used_percent,
        "mem": mem or "indisponível",
        "uptime": uptime,
        "files": len([p for p in AREAS["files"].rglob("*") if p.is_file()]),
        "camera_files": len([p for p in AREAS["cameras"].rglob("*") if p.is_file()]),
        "backup_files": len([p for p in AREAS["backups"].rglob("*") if p.is_file()]),
        "trash_files": len([p for p in AREAS["trash"].rglob("*") if p.is_file()]),
        "media_files": len([p for p in AREAS["media"].rglob("*") if p.is_file()]),
        "cameras_total": len(cams),
        "cameras_online": online,
        "settings": jload(SETTINGS_FILE, {}),
        "updated": run("date '+%d/%m/%Y %H:%M:%S'"),
        "python": run("python --version")
    }

def parse_multipart(ct, body):
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
        fn = None
        for piece in hs.split(";"):
            piece = piece.strip()
            if piece.startswith("filename="):
                fn = piece.split("=", 1)[1].strip().strip('"')
        if fn:
            return safe(fn), c
    return None, None

def send_file(handler, path, download=False):
    data = path.read_bytes()
    ext = path.suffix.lower()
    ctype = "application/octet-stream"
    if ext in [".jpg",".jpeg"]: ctype = "image/jpeg"
    elif ext == ".png": ctype = "image/png"
    elif ext == ".webp": ctype = "image/webp"
    elif ext == ".gif": ctype = "image/gif"
    elif ext == ".mp4": ctype = "video/mp4"
    elif ext == ".webm": ctype = "video/webm"
    elif ext == ".pdf": ctype = "application/pdf"
    elif ext == ".mp3": ctype = "audio/mpeg"
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Access-Control-Allow-Origin", "*")
    if download:
        handler.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

def test_port(ip, port, timeout=0.3):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def scan_network():
    ip = local_ip()
    if ip == "não encontrado":
        return []
    net = ipaddress.ip_network(ip + "/24", strict=False)
    ports = [554, 8554, 80, 8080, 8899, 5000, 8000]
    results = []
    for host in list(net.hosts()):
        h = str(host)
        if h == ip:
            continue
        open_ports = [port for port in ports if test_port(h, port)]
        if open_ports:
            kind = "Dispositivo"
            if 554 in open_ports or 8554 in open_ports: kind = "Possível RTSP"
            if 8899 in open_ports: kind = "Possível Yoosee"
            results.append({"ip": h, "ports": open_ports, "type": kind})
    notify("Descoberta concluída", f"{len(results)} dispositivo(s) encontrado(s).")
    return results

def rtsp_candidates(ip, user="", password=""):
    auth = f"{user}:{password}@" if user or password else ""
    return [
        f"rtsp://{auth}{ip}:554/onvif1",
        f"rtsp://{auth}{ip}:554/onvif2",
        f"rtsp://{auth}{ip}:554/live/ch00_0",
        f"rtsp://{auth}{ip}:554/live/ch00_1",
        f"rtsp://{auth}{ip}:554/user={user}&password={password}&channel=1&stream=0.sdp",
        f"rtsp://{auth}{ip}:554/11",
        f"rtsp://{auth}{ip}:554/12",
        f"rtsp://{auth}{ip}:8554/live"
    ]

def timeline():
    out = {}
    for p in AREAS["cameras"].rglob("*"):
        if p.is_file():
            day = time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime))
            out.setdefault(day, 0)
            out[day] += 1
    return [{"date": k, "count": v} for k, v in sorted(out.items(), reverse=True)]

def cleanup_old_cameras(days):
    limit = time.time() - (int(days) * 86400)
    removed = 0
    for p in AREAS["cameras"].rglob("*"):
        if p.is_file() and p.stat().st_mtime < limit:
            p.rename(AREAS["trash"] / f"{uuid.uuid4().hex}_{p.name}")
            removed += 1
    if removed:
        notify("Limpeza concluída", f"{removed} gravação(ões) movidas para lixeira.", "warning")
    return removed

def library_stats():
    counts = {"image":0, "video":0, "audio":0, "pdf":0, "archive":0, "other":0}
    for area in ["files","cameras","media","documents","downloads"]:
        for p in area_dir(area).rglob("*"):
            if p.is_file():
                counts[media_type(p)] = counts.get(media_type(p),0) + 1
    return counts

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): return

    def j(self, d, code=200):
        b = json.dumps(d, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", "ignore")
        try: return json.loads(raw)
        except Exception: return {}

    def do_OPTIONS(self): self.j({"ok": True})

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/api/status": self.j(status()); return
        if u.path == "/api/settings": self.j(jload(SETTINGS_FILE, {})); return
        if u.path == "/api/timeline": self.j({"items": timeline()}); return
        if u.path == "/api/library": self.j(library_stats()); return
        if u.path == "/api/notifications": self.j({"items": jload(NOTIFY_FILE, [])}); return

        if u.path == "/api/files":
            a = q.get("area", ["files"])[0]
            query = q.get("q", [""])[0]
            sort = q.get("sort", ["name"])[0]
            self.j({"area": a, "items": list_items(a, query, sort)}); return

        if u.path in ["/api/download", "/api/view"]:
            a = q.get("area", ["files"])[0]
            n = safe(unquote(q.get("name", [""])[0]))
            p = area_dir(a) / n
            if not p.exists() or not p.is_file():
                self.j({"error": "arquivo não encontrado"}, 404); return
            send_file(self, p, u.path == "/api/download"); return

        if u.path == "/api/cameras": self.j({"items": jload(CAMERA_FILE, [])}); return
        if u.path == "/api/camera/discover": self.j({"items": scan_network()}); return

        if u.path == "/api/camera/suggest":
            ip = q.get("ip", [""])[0]
            user = q.get("user", [""])[0]
            password = q.get("password", [""])[0]
            self.j({"items": rtsp_candidates(ip, user, password)}); return

        self.j({"error": "rota não encontrada"}, 404)

    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query)

        if u.path == "/api/upload":
            a = q.get("area", ["files"])[0]
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            fn, content = parse_multipart(self.headers.get("Content-Type", ""), body)
            if not fn:
                fn = f"upload_{uuid.uuid4().hex}.bin"; content = body
            (area_dir(a) / safe(fn)).write_bytes(content)
            notify("Upload recebido", f"{safe(fn)} enviado para {a}.")
            self.j({"ok": True, "file": safe(fn)}); return

        if u.path == "/api/mkdir":
            data = self.body_json()
            a = data.get("area", "files")
            name = safe(data.get("name", "Nova pasta"))
            (area_dir(a) / name).mkdir(exist_ok=True)
            self.j({"ok": True}); return

        if u.path == "/api/rename":
            a = q.get("area", ["files"])[0]
            old = safe(unquote(q.get("old", [""])[0]))
            new = safe(unquote(q.get("new", [""])[0]))
            src = area_dir(a) / old; dst = area_dir(a) / new
            if not src.exists() or dst.exists():
                self.j({"error": "erro ao renomear"}, 400); return
            src.rename(dst); self.j({"ok": True}); return

        if u.path == "/api/backup":
            date = run("date '+%Y-%m-%d_%H-%M-%S'")
            target = AREAS["backups"] / f"backup_{date}.zip"
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
                for base in [AREAS["files"], AREAS["cameras"], CONFIG]:
                    for p in base.rglob("*"):
                        if p.is_file(): z.write(p, p.relative_to(BASE))
            notify("Backup concluído", target.name, "success")
            self.j({"ok": True, "file": target.name}); return

        if u.path == "/api/restore":
            n = safe(unquote(q.get("name", [""])[0]))
            src = AREAS["trash"] / n
            if not src.exists(): self.j({"error": "não encontrado"}, 404); return
            clean = "_".join(n.split("_")[1:]) if "_" in n else n
            src.rename(AREAS["files"] / clean)
            self.j({"ok": True}); return

        if u.path == "/api/settings":
            data = self.body_json()
            settings = jload(SETTINGS_FILE, {})
            settings.update(data)
            jsave(SETTINGS_FILE, settings)
            notify("Configurações salvas", "Preferências atualizadas.", "success")
            self.j({"ok": True, "settings": settings}); return

        if u.path == "/api/cleanup":
            days = jload(SETTINGS_FILE, {}).get("camera_retention_days", 30)
            removed = cleanup_old_cameras(days)
            self.j({"ok": True, "removed": removed}); return

        if u.path == "/api/camera/add":
            data = self.body_json()
            cams = jload(CAMERA_FILE, [])
            cam_id = uuid.uuid4().hex[:8]
            name = data.get("name") or f"Camera {len(cams)+1}"
            folder = AREAS["cameras"] / safe(name.replace(" ", "_"))
            folder.mkdir(parents=True, exist_ok=True)
            cam = {
                "id": cam_id,
                "name": name,
                "type": data.get("type", "rtsp"),
                "ip": data.get("ip", ""),
                "user": data.get("user", ""),
                "password": data.get("password", ""),
                "rtsp": data.get("rtsp", ""),
                "quality": data.get("quality", "media"),
                "retention": data.get("retention", "30"),
                "recording": data.get("recording", "manual"),
                "folder": str(folder),
                "status": "online" if data.get("ip") and (test_port(data.get("ip"), 554) or test_port(data.get("ip"), 8554) or test_port(data.get("ip"), 80)) else "cadastrada"
            }
            cams.append(cam); jsave(CAMERA_FILE, cams)
            notify("Câmera adicionada", name, "success")
            self.j({"ok": True, "camera": cam}); return

        if u.path == "/api/camera/delete":
            data = self.body_json()
            cam_id = data.get("id")
            cams = [c for c in jload(CAMERA_FILE, []) if c.get("id") != cam_id]
            jsave(CAMERA_FILE, cams)
            self.j({"ok": True}); return

        if u.path == "/api/camera/check":
            cams = jload(CAMERA_FILE, [])
            for c in cams:
                ip = c.get("ip")
                c["status"] = "online" if ip and (test_port(ip, 554) or test_port(ip, 8554) or test_port(ip, 80)) else "offline"
            jsave(CAMERA_FILE, cams)
            self.j({"ok": True, "items": cams}); return

        if u.path == "/api/notifications/clear":
            jsave(NOTIFY_FILE, [])
            self.j({"ok": True}); return

        self.j({"error": "rota não encontrada"}, 404)

    def do_DELETE(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/api/delete":
            a = q.get("area", ["files"])[0]
            n = safe(unquote(q.get("name", [""])[0]))
            p = area_dir(a) / n
            if p.exists() and p.is_file():
                p.rename(AREAS["trash"] / f"{uuid.uuid4().hex}_{p.name}")
                self.j({"ok": True}); return
            self.j({"error": "arquivo não encontrado"}, 404); return
        self.j({"error": "rota não encontrada"}, 404)

print("LG Home Server API v9 rodando na porta 8090")
HTTPServer(("0.0.0.0", 8090), H).serve_forever()
