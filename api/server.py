#!/usr/bin/env python3
import json, subprocess, time, uuid, zipfile, hmac, hashlib, urllib.request, socket, ipaddress, threading, urllib.parse, base64, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

VERSION="Open Home OS v14.8 Recordings Library"
BUILD="001480"

HOME=Path.home()
BASE=HOME/"OpenHomeOS"
WEB=BASE/"Web"
CONFIG=BASE/"Config"
DATA=BASE/"Data"
LOGS=BASE/"Logs"

AREAS={k:DATA/v for k,v in {
"files":"Files","cameras":"Cameras","snapshots":"Snapshots","backups":"Backups",
"iot":"IoT","connect":"Connect","network":"Network","discovery":"Discovery"
}.items()}

for p in [WEB,CONFIG,DATA,LOGS,*AREAS.values()]:
    p.mkdir(parents=True,exist_ok=True)

SETTINGS=CONFIG/"settings.json"; CAMERAS=CONFIG/"cameras.json"; EVENTS=CONFIG/"events.json"; NOTES=CONFIG/"notifications.json"; JARVIS=CONFIG/"jarvis.json"
DEVICES=CONFIG/"devices.json"; ROOMS=CONFIG/"rooms.json"; TUYA_CFG=CONFIG/"tuya_cloud.json"; TUYA_CACHE=CONFIG/"tuya_cache.json"; NETWORK=CONFIG/"network_devices.json"; DISCOVERY_STATE=CONFIG/"discovery_state.json"
CAMERA_PROFILES=Path(__file__).resolve().parent.parent/"config"/"camera_profiles.json"
CAMERA_LEARNED=CONFIG/"camera_learned.json"
CAMERA_RECORDING_CONFIG=CONFIG/"camera_recording.json"
RECORDINGS=BASE/"recordings"
RECORDINGS.mkdir(parents=True,exist_ok=True)

def ensure(p,d):
    if not p.exists():
        p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")

ensure(SETTINGS,{"system_name":"Open Home OS","version":VERSION,"build":BUILD,"scan_limit":254})
ensure(CAMERAS,[]); ensure(EVENTS,[]); ensure(NOTES,[]); ensure(JARVIS,{"history":[]}); ensure(DEVICES,[])
ensure(ROOMS,["Sala","Quarto","Cozinha","Garagem","Oficina","Jardim"])
ensure(TUYA_CFG,{"enabled":False,"client_id":"","client_secret":"","data_center":"https://openapi.tuyaus.com","asset_id":"","last_sync":"","token":"","token_expire":0})
ensure(TUYA_CACHE,{"last_sync":"","devices":[]})
ensure(NETWORK,{"last_scan":"","devices":[],"summary":{},"count":0})
ensure(DISCOVERY_STATE,{"running":False,"progress":0,"message":"Aguardando busca.","last_scan":"","devices":[],"summary":{},"count":0})

CPU={"total":0,"idle":0}
SCAN_LOCK=threading.Lock()

def run(c,t=8):
    try: return subprocess.check_output(c,shell=True,text=True,stderr=subprocess.DEVNULL,timeout=t).strip()
    except Exception: return ""

def load(p,d):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return d

def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
def now(): return time.strftime("%d/%m/%Y %H:%M:%S")

def ev(k,msg,level="info",mod="core"):
    a=load(EVENTS,[])
    a.insert(0,{"id":uuid.uuid4().hex[:8],"kind":k,"module":mod,"message":msg,"level":level,"time":now()})
    save(EVENTS,a[:2000])

def local_ip():
    return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or "não encontrado"

def gateway():
    return run("ip route | awk '/default/ {print $3; exit}'") or ""

def df_line(line):
    p=line.split()
    return {"filesystem":p[0],"size":p[1],"used":p[2],"available":p[3],"percent":p[4],"mount":" ".join(p[5:])} if len(p)>=6 else {}

def storage():
    internal=df_line(run(f"df -h {HOME} | awk 'NR==2'"))
    cards=[df_line(x) for x in run("df -h | grep -E '/storage|/mnt/media_rw|/sdcard' | grep -v emulated",5).splitlines()]
    cards=[x for x in cards if x]
    return {"internal":internal,"sdcard":cards[0] if cards else {"available":False,"message":"SD Card não detectado"},"candidates":cards}

def cpu():
    global CPU
    try:
        vals=[int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
        idle=vals[3]+(vals[4] if len(vals)>4 else 0); total=sum(vals)
        if not CPU["total"]:
            CPU={"total":total,"idle":idle}; return "calculando..."
        dt=total-CPU["total"]; di=idle-CPU["idle"]; CPU={"total":total,"idle":idle}
        return f"{max(0,min(100,int((1-di/dt)*100)))}%" if dt else "0%"
    except Exception:
        return "indisponível"

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
    return b.get("temperature") if b.get("temperature") is not None else None

def num(v):
    try: return float(str(v).replace(",","."))
    except Exception: return None

def mac_vendor(mac):
    if not mac: return ""
    prefix=mac.upper().replace(":","")[:6]
    vendors={
        "001A11":"Google","F4F5D8":"Google","D8C4E9":"Google","A4CF12":"Espressif","24D7EB":"Espressif","30AEA4":"Espressif",
        "84F3EB":"Tuya/SmartLife","B827EB":"Raspberry Pi","DCA632":"Raspberry Pi","E45F01":"Raspberry Pi","F0D5BF":"Intelbras",
        "001422":"Dell","001B63":"Apple","3C5A37":"Samsung","F45C89":"Samsung","7C2EDD":"Samsung","BC1485":"Samsung",
        "28E31F":"Xiaomi","50EC50":"Xiaomi","A0A3B3":"Sony","E8F2E2":"LG","CC2D83":"LG","ACDCE5":"LG","18B430":"Nest",
        "44D9E7":"Ubiquiti","60E327":"TP-Link","50C7BF":"TP-Link","C0C9E3":"TP-Link","D8B6B7":"Tuya/SmartLife",
        "7CF666":"Tuya/SmartLife","10D561":"Tuya/SmartLife","70A2B3":"Tuya/SmartLife","FCF5C4":"Amazon","F0272D":"Amazon","74C246":"Amazon"
    }
    return vendors.get(prefix,"")

def arp_table():
    txt=run("ip neigh show",5); out={}
    for line in txt.splitlines():
        parts=line.split()
        if not parts: continue
        ip=parts[0]; mac=""
        if "lladdr" in parts:
            try: mac=parts[parts.index("lladdr")+1]
            except Exception: pass
        state=parts[-1] if parts else ""
        out[ip]={"mac":mac,"state":state,"vendor":mac_vendor(mac)}
    return out

PORTS={21:"FTP",22:"SSH",23:"Telnet",53:"DNS",80:"HTTP",81:"HTTP",443:"HTTPS",445:"SMB",554:"RTSP",8000:"HTTP-alt",8008:"Chromecast",8009:"Chromecast",8080:"HTTP-alt",8081:"HTTP-alt",8090:"OpenHomeAPI",1883:"MQTT",5000:"NAS/UPnP",5001:"NAS",8123:"HomeAssistant",9100:"Printer"}
FAST_PORTS=[80,443,554,8080,8090,1883,8123,445,9100,8008,8009,5000,5001,22]

def ping_host(addr):
    return bool(run(f"ping -c 1 -W 1 {addr}",2))

def port_open(addr,port,timeout=.18):
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.settimeout(timeout)
    try: ok=s.connect_ex((addr,port))==0
    except Exception: ok=False
    try: s.close()
    except Exception: pass
    return ok

def grab_http(addr,port):
    scheme="https" if port==443 else "http"; url=f"{scheme}://{addr}:{port}/"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"OpenHomeDiscovery/13.4"})
        with urllib.request.urlopen(req,timeout=1.4) as r:
            data=r.read(900).decode("utf-8","ignore").lower(); hdr=str(r.headers).lower(); title=""
            if "<title>" in data and "</title>" in data:
                title=data.split("<title>",1)[1].split("</title>",1)[0].strip()[:80]
            return {"ok":True,"title":title,"headers":hdr[:600],"sample":data[:300]}
    except Exception:
        return {"ok":False}

def classify(addr,ports,arp=None,http_info=None):
    arp=arp or {}; vendor=(arp.get("vendor") or "").lower()
    title=" ".join([(x.get("title") or "") for x in (http_info or {}).values()]).lower()
    headers=" ".join([(x.get("headers") or "") for x in (http_info or {}).values()]).lower()
    text=title+" "+headers+" "+vendor; kind="device"; score=40; name=""
    if 8090 in ports: kind="open_home_os"; score=95; name="Open Home OS"
    elif 8123 in ports or "home assistant" in text: kind="home_assistant"; score=95; name="Home Assistant"
    elif 1883 in ports: kind="mqtt"; score=90; name="Broker MQTT"
    elif 554 in ports: kind="camera"; score=88; name="Câmera RTSP"
    elif 8008 in ports or 8009 in ports or "chromecast" in text or "google" in text: kind="chromecast"; score=82; name="Chromecast/Google"
    elif 9100 in ports: kind="printer"; score=85; name="Impressora"
    elif 445 in ports: kind="pc_nas"; score=75; name="PC/NAS"
    elif 80 in ports or 443 in ports or 8080 in ports: kind="web_device"; score=65; name="Dispositivo Web"
    if "raspberry" in text: kind="raspberry"; score=max(score,85); name="Raspberry Pi"
    if "samsung" in text: kind="tv_samsung" if kind in ["web_device","device"] else kind; name=name or "Samsung"
    if "lg" in text: kind="tv_lg" if kind in ["web_device","device"] else kind; name=name or "LG"
    if "tuya" in text or "smartlife" in text: kind="tuya_local"; score=max(score,75); name=name or "Tuya/SmartLife"
    if "espressif" in text or "esp" in text: kind="esp32"; score=max(score,78); name=name or "ESP32/ESP8266"
    return kind,score,name

def scan_ip(addr,arp=None,deep=False):
    ports=FAST_PORTS if not deep else list(PORTS.keys()); open_ports=[]
    for port in ports:
        if port_open(addr,port): open_ports.append(port)
    alive=bool(open_ports) or ping_host(addr)
    if not alive: return None
    http_info={}
    for p in open_ports:
        if p in [80,81,443,8000,8008,8080,8081,8123,8090,5000,5001]:
            hi=grab_http(addr,p)
            if hi.get("ok"): http_info[str(p)]=hi
    try: dns=socket.gethostbyaddr(addr)[0]
    except Exception: dns=""
    arp=arp or {}; kind,score,smart_name=classify(addr,open_ports,arp,http_info); name=dns or smart_name or addr
    return {"id":"net_"+addr.replace(".","_"),"source":"discovery","name":name,"ip":addr,"mac":arp.get("mac",""),"vendor":arp.get("vendor",""),"type":kind,"online":True,"confidence":score,"ports":open_ports,"services":[PORTS.get(p,str(p)) for p in open_ports],"http":http_info,"updated":now()}

def discovery_candidates(limit=254):
    ipaddr=local_ip()
    try: net=ipaddress.ip_network(ipaddr+"/24",strict=False)
    except Exception: return None,[]
    candidates=[str(x) for x in list(net.hosts())[:int(limit or 254)]]
    arp=arp_table()
    for a in arp.keys():
        if a not in candidates: candidates.append(a)
    return net,candidates

def merge_devices(items):
    cur=load(DEVICES,[]); by={x.get("id"):x for x in cur}
    for item in items:
        old=by.get(item["id"],{}); old.update(item); by[item["id"]]=old
    out=list(by.values()); save(DEVICES,out); return out

def discovery_scan(limit=None,deep=False):
    with SCAN_LOCK:
        state=load(DISCOVERY_STATE,{})
        state.update({"running":True,"progress":2,"message":"Iniciando descoberta...","devices":[],"summary":{},"count":0})
        save(DISCOVERY_STATE,state)
        net,candidates=discovery_candidates(limit or int(load(SETTINGS,{}).get("scan_limit",254)))
        if not net:
            state.update({"running":False,"progress":100,"message":"Rede não detectada."}); save(DISCOVERY_STATE,state)
            return {"ok":False,"message":"Rede não detectada","devices":[]}
        arp=arp_table(); results=[]; lock=threading.Lock(); total=max(1,len(candidates)); completed=0
        def sort_results(items):
            def ipkey(x):
                try: return tuple(int(p) for p in x["ip"].split("."))
                except Exception: return (999,999,999,999)
            return sorted(items,key=ipkey)
        def worker(a):
            nonlocal completed
            r=scan_ip(a,arp.get(a,{}),deep=deep)
            with lock:
                completed+=1
                if r:
                    results.append(r)
                    partial=load(DISCOVERY_STATE,{})
                    partial["devices"]=sort_results(results); partial["count"]=len(results); partial["message"]=f"Encontrado: {r['name']} ({r['ip']})"; save(DISCOVERY_STATE,partial)
                if completed % 8 == 0 or completed==total:
                    partial=load(DISCOVERY_STATE,{}); partial["progress"]=min(98,int((completed/total)*100)); partial["message"]=f"Verificando rede... {completed}/{total}"; save(DISCOVERY_STATE,partial)
        threads=[]
        for a in candidates:
            th=threading.Thread(target=worker,args=(a,),daemon=True); th.start(); threads.append(th)
            while threading.active_count()>42: time.sleep(.03)
        for th in threads: th.join(timeout=.65)
        by={x["ip"]:x for x in results}; results=sort_results(list(by.values()))
        summary={}
        for d in results: summary[d["type"]]=summary.get(d["type"],0)+1
        payload={"ok":True,"last_scan":now(),"network":str(net),"gateway":gateway(),"devices":results,"summary":summary,"count":len(results),"running":False,"progress":100,"message":f"Busca concluída: {len(results)} dispositivos encontrados."}
        save(NETWORK,{k:v for k,v in payload.items() if k!="ok"}); save(DISCOVERY_STATE,payload)
        merge_devices([{"id":d["id"],"source":"discovery","name":d["name"],"room":"Rede","type":d["type"],"online":True,"ip":d["ip"],"mac":d.get("mac",""),"vendor":d.get("vendor",""),"ports":d.get("ports",[]),"services":d.get("services",[]),"confidence":d.get("confidence",0),"updated":now()} for d in results])
        ev("discovery_scan",f"{len(results)} dispositivos encontrados na rede","success","discovery")
        return payload

def discovery_start(limit=None,deep=False):
    state=load(DISCOVERY_STATE,{})
    if state.get("running"): return {"ok":True,"running":True,"message":"Busca já está em andamento."}
    th=threading.Thread(target=discovery_scan,args=(limit,deep),daemon=True); th.start()
    return {"ok":True,"running":True,"message":"Busca iniciada."}

def connect_summary():
    devs=load(DEVICES,[]); online=[d for d in devs if d.get("online",True)]
    doors=[d for d in devs if d.get("type")=="door"]; opened=[d for d in doors if d.get("open") in [True,"open","opened",1]]
    ts=[num(d.get("temperature")) for d in online]; ts=[x for x in ts if x is not None]
    hs=[num(d.get("humidity")) for d in online]; hs=[x for x in hs if x is not None]
    rooms={}
    for d in devs:
        r=d.get("room") or "Sem ambiente"; rooms.setdefault(r,{"name":r,"devices":0,"online":0,"temps":[],"hums":[],"doors_open":0})
        rooms[r]["devices"]+=1
        if d.get("online",True): rooms[r]["online"]+=1
        if num(d.get("temperature")) is not None: rooms[r]["temps"].append(num(d.get("temperature")))
        if num(d.get("humidity")) is not None: rooms[r]["hums"].append(num(d.get("humidity")))
        if d.get("type")=="door" and d.get("open") in [True,"open","opened",1]: rooms[r]["doors_open"]+=1
    room_list=[]
    for r in rooms.values():
        room_list.append({"name":r["name"],"devices":r["devices"],"online":r["online"],"doors_open":r["doors_open"],"avg_temperature":round(sum(r["temps"])/len(r["temps"]),1) if r["temps"] else None,"avg_humidity":round(sum(r["hums"])/len(r["hums"]),1) if r["hums"] else None})
    return {"total":len(devs),"online":len(online),"offline":len(devs)-len(online),"doors":len(doors),"open_doors":len(opened),"avg_temperature":round(sum(ts)/len(ts),1) if ts else None,"avg_humidity":round(sum(hs)/len(hs),1) if hs else None,"rooms":room_list,"devices":devs}

def tuya_host(): return load(TUYA_CFG,{}).get("data_center","https://openapi.tuyaus.com").rstrip("/")
def tuya_sign(cid,sec,t,method,path,body="",token=""):
    return hmac.new(sec.encode(),(cid+(token or "")+t+f"{method}\n{hashlib.sha256(body.encode()).hexdigest()}\n\n{path}").encode(),hashlib.sha256).hexdigest().upper()
def tuya_request(method,path,body_obj=None,token=None):
    cfg=load(TUYA_CFG,{}); cid=cfg.get("client_id",""); sec=cfg.get("client_secret","")
    if not cid or not sec: return {"success":False,"msg":"Client ID/Secret não configurados"}
    body=json.dumps(body_obj or {},separators=(",",":"),ensure_ascii=False) if body_obj is not None else ""
    t=str(int(time.time()*1000)); tok=token or cfg.get("token","")
    headers={"client_id":cid,"sign":tuya_sign(cid,sec,t,method,path,body,tok),"t":t,"sign_method":"HMAC-SHA256","Content-Type":"application/json"}
    if tok: headers["access_token"]=tok
    try:
        with urllib.request.urlopen(urllib.request.Request(tuya_host()+path,data=body.encode() if body else None,headers=headers,method=method),timeout=14) as r:
            return json.loads(r.read().decode())
    except Exception as e: return {"success":False,"msg":str(e)}
def tuya_token():
    cfg=load(TUYA_CFG,{})
    if cfg.get("token") and time.time()<cfg.get("token_expire",0)-60: return cfg.get("token")
    res=tuya_request("GET","/v1.0/token?grant_type=1")
    if res.get("success") and res.get("result"):
        cfg["token"]=res["result"].get("access_token",""); cfg["token_expire"]=time.time()+int(res["result"].get("expire_time",7200)); save(TUYA_CFG,cfg); return cfg["token"]
    return ""
def normalize_tuya(d):
    name=d.get("name") or d.get("device_name") or "Dispositivo Tuya"; did=d.get("id") or d.get("device_id") or uuid.uuid4().hex[:8]
    cat=(d.get("category") or d.get("product_category") or "").lower(); dtype="device"
    for k,v in {"mcs":"door","doorcontact":"door","pir":"motion","motion":"motion","wsdcg":"temperature_humidity","temp":"temperature_humidity","humidity":"temperature_humidity","cz":"plug","kg":"switch","light":"light","dj":"light","ipc":"camera","camera":"camera"}.items():
        if k in cat or k in name.lower(): dtype=v; break
    sm={str(s.get("code")):s.get("value") for s in (d.get("status",[]) or [])}
    temp=sm.get("va_temperature") or sm.get("temp_current") or sm.get("temperature") or sm.get("temp")
    hum=sm.get("va_humidity") or sm.get("humidity_value") or sm.get("humidity")
    bat=sm.get("battery_percentage") or sm.get("battery_state") or sm.get("battery")
    if isinstance(temp,(int,float)) and temp>100: temp=round(temp/10,1)
    if isinstance(hum,(int,float)) and hum>1000: hum=round(hum/10,1)
    return {"id":did,"source":"tuya","name":name,"room":d.get("room","Sem ambiente"),"type":dtype,"online":bool(d.get("online",True)),"category":cat,"temperature":temp if temp is not None else "","humidity":hum if hum is not None else "","battery":bat if bat is not None else "","open":sm.get("doorcontact_state"),"raw":d,"updated":now()}
def tuya_sync():
    cfg=load(TUYA_CFG,{})
    if not cfg.get("enabled"): return {"ok":False,"message":"Tuya Cloud desativada"}
    token=tuya_token()
    if not token: return {"ok":False,"message":"Falha ao obter token Tuya"}
    devices=[]; asset=cfg.get("asset_id","").strip(); last={}
    for path in ([f"/v1.0/iot-03/assets/{asset}/devices"] if asset else [])+["/v1.0/users/devices"]:
        last=tuya_request("GET",path,token=token)
        if last.get("success"):
            r=last.get("result",{}); devices=(r.get("devices") or r.get("list") or []) if isinstance(r,dict) else r if isinstance(r,list) else []
            if devices: break
    norm=[normalize_tuya(x) for x in devices]; merge_devices(norm); save(TUYA_CACHE,{"last_sync":now(),"devices":norm,"raw":last})
    cfg["last_sync"]=now(); save(TUYA_CFG,cfg); ev("tuya_sync",f"{len(norm)} dispositivos sincronizados","success","connect")
    return {"ok":True,"count":len(norm),"devices":norm,"raw":last}



def camera_profiles():
    return load(CAMERA_PROFILES, {"version":"14.0","profiles":[]})

def identify_camera_profile(device):
    vendor=(device.get("vendor") or "").lower()
    mac=(device.get("mac") or "").upper()
    ports=set(device.get("ports") or [])
    best=None; score_best=0
    for p in camera_profiles().get("profiles",[]):
        score=0
        for prefix in p.get("mac_prefixes",[]):
            if mac.startswith(prefix.upper()): score+=80
        for name in p.get("vendors",[]):
            if name.lower() in vendor: score+=60
        score+=len(ports.intersection(set(p.get("ports",[]))))*5
        if score>score_best:
            best=p; score_best=score
    return {"profile":best,"confidence":min(100,score_best)}

def camera_capabilities(device):
    ports=set(device.get("ports") or [])
    result=identify_camera_profile(device)
    profile=result.get("profile")
    return {
        "profile":profile,
        "profile_confidence":result.get("confidence",0),
        "rtsp_detected":bool(ports.intersection({554,8554})),
        "web_detected":bool(ports.intersection({80,81,443,8080,8000})),
        "onvif_possible":bool(profile and ports.intersection(set(profile.get("onvif_ports",[])))),
        "firmware_mode":"dafang_hacks_possible" if profile and profile.get("id")=="xiaomi_xiaofang" and ports.intersection({22,554,8554}) else ("original_limited" if profile and profile.get("id")=="xiaomi_xiaofang" else "unknown")
    }

RTSP_COMMON_PATHS=[
    "/onvif1","/onvif2",
    "/live/ch00_0","/live/ch00_1","/live/ch0",
    "/stream1","/stream2",
    "/h264/ch1/main/av_stream","/h264/ch1/sub/av_stream",
    "/h264Preview_01_main","/h264Preview_01_sub",
    "/cam/realmonitor?channel=1&subtype=0","/cam/realmonitor?channel=1&subtype=1",
    "/Streaming/Channels/101","/Streaming/Channels/102",
    "/11","/12","/videoMain","/videoSub","/h264"
]

RTSP_PRESETS={
    "auto":RTSP_COMMON_PATHS,
    "yoosee":[
        "/onvif1","/onvif2",
        "/live/ch00_0","/live/ch00_1",
        "/stream1","/stream2",
        "/h264/ch1/main/av_stream","/h264/ch1/sub/av_stream",
        "/11","/12"
    ],
    "hikvision":["/Streaming/Channels/101","/Streaming/Channels/102","/h264/ch1/main/av_stream"],
    "dahua":["/cam/realmonitor?channel=1&subtype=0","/cam/realmonitor?channel=1&subtype=1"],
    "generic":["/stream1","/stream2","/onvif1","/11","/12"]
}

def rtsp_url(ip,port,path,user="",password=""):
    path=(path or "/stream1").strip()
    if not path.startswith("/"):
        path="/"+path
    auth=""
    if user:
        auth=urllib.parse.quote(str(user),safe="")+"@"
        if password:
            auth=urllib.parse.quote(str(user),safe="")+":"+urllib.parse.quote(str(password),safe="")+"@"
    return f"rtsp://{auth}{ip}:{int(port or 554)}{path}"


def parse_rtsp_response(raw):
    text=raw.decode("utf-8","ignore") if isinstance(raw,(bytes,bytearray)) else str(raw or "")
    lines=text.replace("\r\n","\n").split("\n")
    status_line=lines[0].strip() if lines else ""
    headers={}
    body=""
    body_started=False
    body_lines=[]
    for line in lines[1:]:
        if body_started:
            body_lines.append(line)
            continue
        if line=="":
            body_started=True
            continue
        if ":" in line:
            k,v=line.split(":",1)
            headers[k.strip().lower()]=v.strip()
    body="\n".join(body_lines)
    code=None
    m=re.search(r"RTSP/\d\.\d\s+(\d+)",status_line)
    if m:
        code=int(m.group(1))
    return {"status_line":status_line,"status":code,"headers":headers,"body":body[:2000]}

def rtsp_raw_request(ip,port,path,method="OPTIONS",username="",password="",timeout=4,authorization=""):
    path=(path or "/").strip()
    if not path.startswith("/"):
        path="/"+path
    uri=f"rtsp://{ip}:{int(port or 554)}{path}"
    cseq=int(time.time()*1000)%100000
    headers=[
        f"{method} {uri} RTSP/1.0",
        f"CSeq: {cseq}",
        "User-Agent: OpenHomeOS/14.2",
        "Accept: application/sdp"
    ]
    if authorization:
        headers.append(f"Authorization: {authorization}")
    elif username:
        token=base64.b64encode(f"{username}:{password}".encode()).decode()
        headers.append(f"Authorization: Basic {token}")
    request="\r\n".join(headers)+"\r\n\r\n"
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.settimeout(timeout)
    started=time.time()
    try:
        sock.connect((ip,int(port or 554)))
        sock.sendall(request.encode())
        chunks=[]
        total=0
        while total<65536:
            try:
                chunk=sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            total+=len(chunk)
            if b"\r\n\r\n" in b"".join(chunks) and total>1024:
                break
        parsed=parse_rtsp_response(b"".join(chunks))
        parsed.update({"ok":True,"method":method,"path":path,"uri":uri,"elapsed_ms":round((time.time()-started)*1000)})
        return parsed
    except Exception as e:
        return {"ok":False,"method":method,"path":path,"uri":uri,"error":str(e),"elapsed_ms":round((time.time()-started)*1000)}
    finally:
        try: sock.close()
        except Exception: pass

def rtsp_server_diagnostics(d):
    ip=str(d.get("ip","")).strip()
    if not ip:
        return {"ok":False,"message":"IP obrigatório."}
    port=int(d.get("port") or 554)
    user=str(d.get("username",""))
    password=str(d.get("password",""))
    preset=str(d.get("preset","auto") or "auto").lower()
    manual=str(d.get("path","")).strip()
    paths=[manual] if manual else RTSP_PRESETS.get(preset,RTSP_COMMON_PATHS)
    paths=list(dict.fromkeys(["/"]+paths[:12]))

    results=[]
    server_name=""
    public_methods=[]
    auth_scheme=""
    auth_required=False
    credentials_accepted=False
    sdp_detected=False

    for path in paths:
        for method in ["OPTIONS","DESCRIBE"]:
            r=rtsp_raw_request(ip,port,path,method,user,password,timeout=4)
            results.append(r)
            if not r.get("ok"):
                continue
            headers=r.get("headers",{})
            if headers.get("server") and not server_name:
                server_name=headers.get("server")
            if headers.get("public"):
                public_methods=[x.strip() for x in headers.get("public","").split(",") if x.strip()]
            www=headers.get("www-authenticate","")
            if www:
                auth_required=True
                auth_scheme=www.split(" ",1)[0]
            status=r.get("status")
            if status in [200,201]:
                credentials_accepted=True
            if "application/sdp" in headers.get("content-type","").lower() or "m=video" in (r.get("body") or ""):
                sdp_detected=True
                return {
                    "ok":True,
                    "rtsp_server":True,
                    "server":server_name,
                    "public_methods":public_methods,
                    "auth_required":auth_required,
                    "auth_scheme":auth_scheme,
                    "credentials_accepted":credentials_accepted,
                    "sdp_detected":True,
                    "working_path":path,
                    "message":"Servidor RTSP respondeu e forneceu descrição SDP.",
                    "results":results
                }

    any_response=any(x.get("ok") and x.get("status") for x in results)
    statuses=[x.get("status") for x in results if x.get("status")]
    if 401 in statuses:
        message="Servidor RTSP localizado, mas as credenciais foram recusadas."
        code="unauthorized"
    elif 461 in statuses:
        message="Servidor RTSP localizado, mas recusou o transporte solicitado."
        code="unsupported_transport"
    elif any_response:
        message="Servidor RTSP respondeu, porém nenhum caminho forneceu vídeo SDP."
        code="no_sdp"
    else:
        message="Não foi possível obter resposta RTSP válida."
        code="no_response"

    return {
        "ok":False,
        "error_code":code,
        "rtsp_server":any_response,
        "server":server_name,
        "public_methods":public_methods,
        "auth_required":auth_required,
        "auth_scheme":auth_scheme,
        "credentials_accepted":credentials_accepted,
        "sdp_detected":sdp_detected,
        "message":message,
        "results":results
    }


def xiaomi_xiaofang_probe(device):
    ip=str(device.get("ip") or "").strip()
    mac=(device.get("mac") or "").upper()
    ports=sorted(set(device.get("ports") or []))

    identified=mac.startswith("34:CE:00")
    if not ports and ip:
        ports=scan_ports(ip,[22,80,81,443,554,8554,8080,8000,8899])

    firmware_mode="original_limited"
    rtsp=False
    onvif=False
    web=False
    ssh=False

    if 22 in ports:
        ssh=True
    if 80 in ports or 8080 in ports or 443 in ports:
        web=True
    if 554 in ports or 8554 in ports:
        rtsp=True
    if 8899 in ports or 8000 in ports:
        onvif=True

    if ssh or rtsp or onvif:
        firmware_mode="modified_or_dafang"

    compatibility=30
    if identified:
        compatibility+=25
    if rtsp:
        compatibility+=25
    if onvif:
        compatibility+=10
    if web:
        compatibility+=5
    if ssh:
        compatibility+=5
    compatibility=min(100,compatibility)

    recommendations=[]
    if firmware_mode=="original_limited":
        recommendations.append("Firmware original Xiaomi provável: RTSP e ONVIF normalmente não ficam expostos.")
        recommendations.append("A câmera continua utilizável pelo aplicativo Mi Home, mas a integração local pode ser limitada.")
    else:
        recommendations.append("Firmware modificado ou Dafang Hacks provável: serviços locais foram detectados.")
        if rtsp:
            recommendations.append("RTSP detectado; execute o teste de vídeo.")
        if onvif:
            recommendations.append("ONVIF pode estar disponível.")
        if ssh:
            recommendations.append("SSH detectado, indicando firmware modificado.")

    return {
        "identified":identified,
        "manufacturer":"Xiaomi",
        "model":"Xiao Fang Smart Camera",
        "mac":mac,
        "ip":ip,
        "ports":ports,
        "firmware_mode":firmware_mode,
        "capabilities":{
            "rtsp":rtsp,
            "onvif":onvif,
            "web":web,
            "ssh":ssh,
            "mi_home":True,
            "snapshot":"unknown",
            "audio":"likely",
            "motion_detection":"likely"
        },
        "compatibility":compatibility,
        "recommendations":recommendations
    }

def camera_full_diagnostic(d):
    device=d.get("device",d)
    caps=camera_capabilities(device)
    ip=str(device.get("ip") or d.get("ip") or "").strip()
    ports=sorted(set(device.get("ports") or []))
    if not ports and ip:
        ports=scan_ports(ip,[22,80,81,443,554,8554,5000,8000,8080,8899])
    payload={
        "ip":ip,
        "port":d.get("port",554),
        "preset":d.get("preset","auto"),
        "username":d.get("username",""),
        "password":d.get("password",""),
        "path":d.get("path","")
    }
    rtsp=rtsp_server_diagnostics(payload) if (554 in ports or not ports) else {"ok":False,"skipped":True,"message":"Porta 554 não detectada."}
    onvif=onvif_probe({**payload,"onvif_ports":[80,5000,8000,8080,8899]})
    recommendation=[]
    if caps.get("profile") and caps["profile"].get("id")=="xiaomi_xiaofang" and caps.get("firmware_mode")=="original_limited":
        recommendation.append("Firmware original Xiaomi detectado: RTSP/ONVIF podem não estar disponíveis.")
    if rtsp.get("error_code")=="unauthorized":
        recommendation.append("Revise o usuário e a senha NVR/RTSP configurados no aplicativo da câmera.")
    if rtsp.get("error_code")=="unsupported_transport":
        recommendation.append("O servidor RTSP respondeu, mas usa comportamento incompatível com os transportes testados.")
    if rtsp.get("error_code")=="no_sdp":
        recommendation.append("A porta RTSP existe, porém o caminho de vídeo ainda não foi identificado.")
    if not onvif.get("ok"):
        recommendation.append("ONVIF não foi confirmado.")
    if rtsp.get("ok"):
        recommendation.append("RTSP pronto para configuração.")
    xiaomi=None
    profile=(caps.get("profile") or {}).get("id")
    mac=(device.get("mac") or "").upper()
    if profile=="xiaomi_xiaofang" or mac.startswith("34:CE:00"):
        xiaomi=xiaomi_xiaofang_probe({**device,"ports":ports})
        recommendation.extend(xiaomi.get("recommendations",[]))

    return {
        "ok":True,
        "device":device,
        "ports":ports,
        "capabilities":caps,
        "rtsp":rtsp,
        "onvif":onvif,
        "xiaomi":xiaomi,
        "recommendations":list(dict.fromkeys(recommendation))
    }

def ffprobe_rtsp(url,timeout=7,transport="tcp"):
    cmd=["ffprobe","-v","error"]
    if transport in ["tcp","udp"]:
        cmd += ["-rtsp_transport",transport]
    cmd += [
        "-analyzeduration","3000000",
        "-probesize","3000000",
        "-show_entries","stream=index,codec_type,codec_name,width,height,r_frame_rate",
        "-of","json",url
    ]
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        if p.returncode==0:
            data=json.loads(p.stdout or "{}")
            streams=data.get("streams",[])
            video=next((x for x in streams if x.get("codec_type")=="video"), streams[0] if streams else {})
            if streams:
                return {
                    "ok":True,
                    "transport":transport,
                    "stream":video,
                    "streams":streams,
                    "message":"Stream RTSP validado."
                }
            return {"ok":False,"transport":transport,"message":"Conexão aceita, mas nenhum stream de mídia foi identificado."}
        err=(p.stderr or "Falha ao abrir o stream.").strip()[-700:]
        return {"ok":False,"transport":transport,"message":err}
    except FileNotFoundError:
        return {"ok":False,"transport":transport,"message":"ffprobe não instalado. Execute: pkg install ffmpeg"}
    except subprocess.TimeoutExpired:
        return {"ok":False,"transport":transport,"message":"Tempo esgotado ao testar o stream."}
    except Exception as e:
        return {"ok":False,"transport":transport,"message":str(e)}

def classify_rtsp_error(message):
    text=(message or "").lower()
    if "401" in text or "unauthorized" in text:
        return "unauthorized"
    if "nonmatching transport" in text or "461 unsupported transport" in text:
        return "transport"
    if "404" in text or "not found" in text:
        return "path_not_found"
    if "connection refused" in text:
        return "connection_refused"
    if "timed out" in text or "tempo esgotado" in text:
        return "timeout"
    if "invalid data found" in text:
        return "invalid_stream"
    return "unknown"


def learned_camera_key(ip,port,preset):
    return f"{str(ip).strip()}:{int(port or 554)}:{str(preset or 'auto').lower()}"

def learned_camera_profiles():
    return load(CAMERA_LEARNED,{})

def save_learned_camera(ip,port,preset,path,transport,stream=None):
    data=learned_camera_profiles()
    key=learned_camera_key(ip,port,preset)
    data[key]={
        "ip":str(ip),
        "port":int(port or 554),
        "preset":str(preset or "auto").lower(),
        "path":path,
        "transport":transport or "auto",
        "stream":stream or {},
        "updated":time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save(CAMERA_LEARNED,data)
    return data[key]

def get_learned_camera(ip,port,preset):
    return learned_camera_profiles().get(learned_camera_key(ip,port,preset))

def sanitize_rtsp_text(text,username="",password=""):
    value=str(text or "")
    if password:
        value=value.replace(password,"***")
    if username:
        value=value.replace(f"{username}:***@", "***:***@")
        value=value.replace(f"{username}:", "***:")
    value=re.sub(r"rtsp://[^/@\s:]+:[^/@\s]+@", "rtsp://***:***@", value)
    return value

def camera_snapshot(camera):
    ip=str(camera.get("ip","")).strip()
    port=int(camera.get("port") or 554)
    path=str(camera.get("path","")).strip()
    user=str(camera.get("username",""))
    password=str(camera.get("password",""))
    transport=str(camera.get("transport","udp") or "udp")
    if not ip or not path:
        return {"ok":False,"message":"Câmera sem IP ou caminho RTSP."}

    url=rtsp_url(ip,port,path,user,password)
    cmd=["ffmpeg","-hide_banner","-loglevel","error"]
    if transport in ["tcp","udp"]:
        cmd += ["-rtsp_transport",transport]
    cmd += [
        "-analyzeduration","3000000",
        "-probesize","3000000",
        "-i",url,
        "-an","-sn","-dn",
        "-frames:v","1",
        "-q:v","5",
        "-f","image2pipe",
        "-vcodec","mjpeg",
        "-"
    ]
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=12)
        if p.returncode==0 and p.stdout:
            return {
                "ok":True,
                "mime":"image/jpeg",
                "data":base64.b64encode(p.stdout).decode(),
                "updated":time.strftime("%Y-%m-%d %H:%M:%S")
            }
        return {"ok":False,"message":sanitize_rtsp_text((p.stderr or b"Falha ao capturar imagem.").decode("utf-8","ignore"),user,password)[-500:]}
    except FileNotFoundError:
        return {"ok":False,"message":"ffmpeg não instalado. Execute: pkg install ffmpeg"}
    except subprocess.TimeoutExpired:
        return {"ok":False,"message":"Tempo esgotado ao capturar snapshot."}
    except Exception as e:
        return {"ok":False,"message":sanitize_rtsp_text(str(e),user,password)}

def test_rtsp_config(d):
    ip=str(d.get("ip","")).strip()
    if not ip:
        return {"ok":False,"message":"IP obrigatório."}

    port=int(d.get("port") or 554)
    user=str(d.get("username",""))
    password=str(d.get("password",""))
    manual=str(d.get("path","")).strip()
    preset=str(d.get("preset","auto") or "auto").lower()
    deep=bool(d.get("deep",False))

    learned=get_learned_camera(ip,port,preset)
    base_paths=[manual] if manual else RTSP_PRESETS.get(preset,RTSP_COMMON_PATHS)
    paths=list(dict.fromkeys(base_paths))

    if learned and learned.get("path") and not manual:
        paths=[learned["path"]]+[x for x in paths if x!=learned["path"]]

    if deep:
        deep_paths=[
            "/live/0/MAIN","/live/0/SUB","/live/1/MAIN","/live/1/SUB",
            "/live/main","/live/sub","/main","/sub","/media/video1","/media/video2",
            "/video1","/video2","/av0_0","/av0_1","/ch0_0.h264","/ch0_1.h264",
            "/user=admin_password=_channel=1_stream=0.sdp",
            "/user=admin_password=_channel=1_stream=1.sdp",
            "/axis-media/media.amp","/mpeg4","/0","/1"
        ]
        paths=list(dict.fromkeys(paths+deep_paths))

    transports=["tcp","udp","auto"]
    if learned and learned.get("transport"):
        t=learned["transport"]
        transports=[t]+[x for x in transports if x!=t]

    attempts=[]
    counters={}
    started=time.time()

    for path in paths:
        url=rtsp_url(ip,port,path,user,password)
        for transport in transports:
            result=ffprobe_rtsp(url,timeout=8,transport=transport)
            msg=sanitize_rtsp_text(result.get("message",""),user,password)
            kind=classify_rtsp_error(msg)
            counters[kind]=counters.get(kind,0)+1

            attempts.append({
                "path":path,
                "transport":transport,
                "ok":result.get("ok",False),
                "error_type":kind,
                "message":msg
            })

            if result.get("ok"):
                elapsed=round(time.time()-started,1)
                learned_entry=save_learned_camera(
                    ip,port,preset,path,transport,result.get("stream",{})
                )
                return {
                    "ok":True,
                    "preset":preset,
                    "deep":deep,
                    "learned":True,
                    "learned_profile":learned_entry,
                    "path":path,
                    "transport":transport,
                    "stream":result.get("stream",{}),
                    "streams":result.get("streams",[]),
                    "safe_url":rtsp_url(ip,port,path,"***","***" if password else ""),
                    "attempts_count":len(attempts),
                    "elapsed_seconds":elapsed,
                    "attempts":attempts
                }

    if counters.get("unauthorized",0):
        message="A câmera respondeu, mas recusou o usuário ou a senha RTSP."
        error_code="unauthorized"
    elif counters.get("transport",0):
        message="A câmera respondeu, mas não aceitou os transportes RTSP testados."
        error_code="transport"
    elif counters.get("connection_refused",0)==len(attempts) and attempts:
        message="A porta RTSP recusou todas as conexões."
        error_code="connection"
    elif counters.get("timeout",0)==len(attempts) and attempts:
        message="A câmera não respondeu dentro do tempo esperado."
        error_code="timeout"
    else:
        message="Nenhum caminho RTSP conhecido retornou vídeo válido."
        error_code="path_not_found"

    return {
        "ok":False,
        "error_code":error_code,
        "preset":preset,
        "deep":deep,
        "learned_profile":learned,
        "message":message,
        "attempts_count":len(attempts),
        "elapsed_seconds":round(time.time()-started,1),
        "summary":counters,
        "attempts":attempts
    }

def onvif_probe(d):
    """Checks common ONVIF service endpoints without guessing credentials."""
    ip=str(d.get("ip","")).strip()
    if not ip:
        return {"ok":False,"message":"IP obrigatório."}

    ports=[]
    for value in d.get("onvif_ports",[80,5000,8000,8080,8899]):
        try:
            value=int(value)
            if value not in ports:
                ports.append(value)
        except Exception:
            pass

    endpoints=[
        "/onvif/device_service",
        "/onvif/Device_service",
        "/onvif/services",
        "/device_service"
    ]
    results=[]

    for port in ports:
        for endpoint in endpoints:
            scheme="https" if port==443 else "http"
            url=f"{scheme}://{ip}:{port}{endpoint}"
            try:
                req=urllib.request.Request(
                    url,
                    headers={
                        "User-Agent":"OpenHomeOS/13.6",
                        "Content-Type":"application/soap+xml; charset=utf-8"
                    },
                    method="GET"
                )
                with urllib.request.urlopen(req,timeout=2.2) as resp:
                    code=getattr(resp,"status",200)
                    sample=resp.read(700).decode("utf-8","ignore")
                    results.append({"url":url,"status":code,"sample":sample[:250]})
                    if code in [200,401,405]:
                        return {
                            "ok":True,
                            "url":url,
                            "status":code,
                            "auth_required":code==401,
                            "message":"Serviço ONVIF localizado."
                        }
            except urllib.error.HTTPError as e:
                results.append({"url":url,"status":e.code})
                if e.code in [401,405]:
                    return {
                        "ok":True,
                        "url":url,
                        "status":e.code,
                        "auth_required":e.code==401,
                        "message":"Serviço ONVIF localizado; autenticação pode ser necessária."
                    }
            except Exception as e:
                results.append({"url":url,"error":str(e)[:160]})

    return {
        "ok":False,
        "message":"Serviço ONVIF não confirmado nas portas comuns.",
        "results":results
    }

def add_rtsp_camera(d):
    tested=test_rtsp_config(d)
    if not tested.get("ok"):
        return tested
    cams=load(CAMERAS,[])
    ip=str(d.get("ip","")).strip()
    cid="cam_"+ip.replace(".","_")+"_"+str(int(d.get("port") or 554))
    cam={
        "id":cid,
        "name":str(d.get("name") or f"Câmera {ip}"),
        "room":str(d.get("room") or "Sem ambiente"),
        "type":"rtsp",
        "ip":ip,
        "port":int(d.get("port") or 554),
        "username":str(d.get("username","")),
        "password":str(d.get("password","")),
        "path":tested.get("path"),
        "transport":tested.get("transport","tcp"),
        "codec":(tested.get("stream") or {}).get("codec_name"),
        "width":(tested.get("stream") or {}).get("width"),
        "height":(tested.get("stream") or {}).get("height"),
        "last_test":time.strftime("%Y-%m-%d %H:%M:%S"),
        "verified":True,
        "status":"online",
        "stream":tested.get("stream",{}),
        "updated":now()
    }
    by={x.get("id"):x for x in cams}
    by[cid]=cam
    save(CAMERAS,list(by.values()))
    merge_devices([{
        "id":cid,"source":"camera","name":cam["name"],"room":cam["room"],
        "type":"camera","online":True,"ip":ip,"ports":[cam["port"]],
        "services":["RTSP"],"verified":True,"updated":now()
    }])
    ev("camera_add",f"{cam['name']} configurada e validada","success","camera")
    public=dict(cam)
    public["password"]="***" if cam["password"] else ""
    return {"ok":True,"camera":public,"message":"Câmera adicionada e validada."}

def cam_counts():
    cams=load(CAMERAS,[])
    return {"registered":len(cams),"online":len([c for c in cams if c.get("verified") and c.get("status")=="online"]),"pending":len([c for c in cams if not c.get("verified")]),"offline":len([c for c in cams if c.get("status")=="offline"])}
def health_score(st):
    score=100
    try:
        if int(str(st.get("used","0")).replace("%",""))>85: score-=20
    except Exception: pass
    if st.get("sdcard")=="não detectado": score-=8
    if st["connect"]["total"]==0: score-=15
    if st["connect"]["offline"]>0: score-=min(20,st["connect"]["offline"]*5)
    if st["connect"]["open_doors"]>0: score-=min(15,st["connect"]["open_doors"]*5)
    if st.get("nginx")!="Ativo": score-=15
    return max(0,min(100,score))
def status():
    b=battery(); w=wifi(); stg=storage(); sd=stg["sdcard"]; con=connect_summary(); temp=thermal(); net=load(NETWORK,{})
    d={"version":VERSION,"build":BUILD,"ip":local_ip(),"gateway":gateway(),"nginx":"Ativo" if run("pgrep nginx") else "Parado","api":"Ativa","disk":run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),"used":run(f"df {HOME} | awk 'NR==2 {{print $5}}'"),"storage":stg,"sdcard":f"{sd.get('available')} livre de {sd.get('size')}" if sd.get("available") else "não detectado","cpu":cpu(),"mem":run("free -m | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'"),"uptime":run("uptime -p"),"battery":f"{b.get('percentage')}% • {b.get('status','')}" if b.get("percentage") is not None else "indisponível","temperature":f"{temp}°C" if temp is not None else "indisponível","wifi":w.get("ssid") or "indisponível","wifi_detail":w,"connect":con,"cameras":cam_counts(),"network":net,"discovery_state":load(DISCOVERY_STATE,{}),"backups":len(list(AREAS["backups"].glob("*"))),"tuya_cloud":load(TUYA_CFG,{}),"updated":now()}
    d["health"]=health_score(d); return d
def house():
    st=status(); con=st["connect"]; probs=[]
    if st["sdcard"]=="não detectado": probs.append("SD Card não detectado")
    if con["total"]==0: probs.append("nenhum dispositivo smart home cadastrado")
    if con["offline"]: probs.append(f"{con['offline']} dispositivo(s) offline")
    if con["open_doors"]: probs.append(f"{con['open_doors']} porta(s)/janela(s) aberta(s)")
    return {"temperature":con["avg_temperature"],"humidity":con["avg_humidity"],"connect":con,"health":st["health"],"problems":probs,"message":"Saúde excelente." if not probs else "; ".join(probs)}
def backup():
    target=AREAS["backups"]/f"backup_v13_4_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
        for base in [CONFIG,AREAS["files"],AREAS["cameras"],AREAS["snapshots"],AREAS["iot"],AREAS["connect"],AREAS["network"]]:
            for p in base.rglob("*"):
                if p.is_file(): z.write(p,p.relative_to(BASE))
    ev("backup",target.name,"success","backup"); return target.name
def jarvis(cmd):
    t=(cmd or "").lower(); st=status(); hs=house(); reply="Não entendi. Tente: como está a casa, portas abertas, descobrir rede, sincronizar Tuya."; action="none"
    if "casa" in t:
        reply=f"Sua casa está com saúde de {st['health']} por cento. {st['connect']['online']} dispositivos online. Temperatura média {hs['temperature'] or 'sem dados'} graus. {hs['message']}."; action="open_dashboard"
    elif "porta" in t or "janela" in t:
        opens=[d for d in st["connect"]["devices"] if d.get("type")=="door" and d.get("open") in [True,"open","opened",1]]
        reply="Todas as portas e janelas estão fechadas." if not opens else "Abertas: "+", ".join([x.get("name","Sensor") for x in opens]); action="open_connect"
    elif "tuya" in t and ("sincron" in t or "buscar" in t):
        r=tuya_sync(); reply=f"Sincronização Tuya concluída. {r.get('count',0)} dispositivos encontrados." if r.get("ok") else "Não consegui sincronizar Tuya: "+r.get("message","erro"); action="open_setup"
    elif "rede" in t or "procurar" in t or "scan" in t or "descobrir" in t:
        r=discovery_start(); reply="Iniciei a descoberta da rede. Abra a tela Discovery para acompanhar em tempo real." if r.get("ok") else r.get("message","Falha na busca"); action="open_network"
    elif "sensor" in t or "dispositivo" in t:
        c=st["connect"]; reply=f"Open Home Connect tem {c['total']} dispositivos, {c['online']} online e {c['offline']} offline."; action="open_connect"
    elif "backup" in t:
        f=backup(); reply=f"Backup criado: {f}."
    j=load(JARVIS,{"history":[]}); j.setdefault("history",[]).insert(0,{"command":cmd,"reply":reply,"action":action,"time":now()}); j["history"]=j["history"][:100]; save(JARVIS,j); ev("jarvis",cmd,"info","jarvis")
    return {"ok":True,"reply":reply,"action":action}



RECORDING_PROCESSES={}
RECORDING_LOCK=threading.Lock()

def recording_config():
    return load(CAMERA_RECORDING_CONFIG,{
        "segment_seconds":300,
        "retention_days":7,
        "max_storage_gb":20,
        "format":"mp4",
        "copy_video":True,
        "recording_root":str(RECORDINGS)
    })

def save_recording_config(data):
    cfg=recording_config()
    allowed=["segment_seconds","retention_days","max_storage_gb","format","copy_video","recording_root"]
    for k in allowed:
        if k in data:
            cfg[k]=data[k]
    cfg["segment_seconds"]=max(30,min(3600,int(cfg.get("segment_seconds",300))))
    cfg["retention_days"]=max(1,min(365,int(cfg.get("retention_days",7))))
    cfg["max_storage_gb"]=max(1,min(500,int(cfg.get("max_storage_gb",20))))
    cfg["format"]="mp4"
    try:
        cfg["recording_root"]=str(normalize_recording_root(cfg.get("recording_root")))
    except Exception as e:
        return {"error":str(e),"config":cfg}
    save(CAMERA_RECORDING_CONFIG,cfg)
    return cfg


def normalize_recording_root(value):
    raw=str(value or "").strip()
    if not raw:
        return RECORDINGS

    path=Path(raw).expanduser()
    if not path.is_absolute():
        path=(BASE/path).resolve()
    else:
        path=path.resolve()

    path.mkdir(parents=True,exist_ok=True)

    test_file=path/".openhome_write_test"
    try:
        test_file.write_text("ok",encoding="utf-8")
        test_file.unlink(missing_ok=True)
    except Exception as e:
        raise PermissionError(f"Sem permissão para gravar em {path}: {e}")

    return path

def recording_root():
    cfg=recording_config()
    try:
        return normalize_recording_root(cfg.get("recording_root"))
    except Exception:
        return RECORDINGS

def storage_locations():
    items=[
        {"id":"internal","name":"Armazenamento interno do projeto","path":str(RECORDINGS)}
    ]

    candidates=[
        Path("/storage"),
        Path("/sdcard"),
        Path("/mnt/media_rw"),
        Path.home()/ "storage"
    ]

    seen={str(RECORDINGS.resolve())}
    for base in candidates:
        try:
            if not base.exists():
                continue
            if base.is_dir():
                entries=[base] + [p for p in base.iterdir() if p.is_dir()]
                for p in entries:
                    try:
                        rp=str(p.resolve())
                        if rp in seen:
                            continue
                        seen.add(rp)
                        items.append({
                            "id":"detected",
                            "name":p.name or rp,
                            "path":rp
                        })
                    except Exception:
                        pass
        except Exception:
            pass

    return {"ok":True,"items":items,"current":str(recording_root())}

def test_recording_path(path_value):
    try:
        path=normalize_recording_root(path_value)
        stat=shutil.disk_usage(path)
        return {
            "ok":True,
            "path":str(path),
            "free_gb":round(stat.free/1024/1024/1024,2),
            "total_gb":round(stat.total/1024/1024/1024,2)
        }
    except Exception as e:
        return {"ok":False,"message":str(e)}

def recording_dir(camera):
    safe=re.sub(r"[^A-Za-z0-9_.-]+","_",str(camera.get("name") or camera.get("ip") or camera.get("id")))
    folder=recording_root()/safe
    folder.mkdir(parents=True,exist_ok=True)
    return folder

def recording_command(camera,cfg):
    ip=str(camera.get("ip","")).strip()
    port=int(camera.get("port") or 554)
    path=str(camera.get("path","")).strip()
    user=str(camera.get("username",""))
    password=str(camera.get("password",""))
    transport=str(camera.get("transport","udp") or "udp").lower()
    if not ip or not path:
        return None,None

    url=rtsp_url(ip,port,path,user,password)
    folder=recording_dir(camera)
    pattern=str(folder/"%Y-%m-%d_%H-%M-%S.mp4")

    cmd=["ffmpeg","-hide_banner","-loglevel","warning"]
    if transport in ["tcp","udp"]:
        cmd += ["-rtsp_transport",transport]
    cmd += [
        "-i",url,
        "-map","0:v:0",
        "-an",
        "-c:v","copy" if cfg.get("copy_video",True) else "libx264",
        "-f","segment",
        "-segment_time",str(int(cfg.get("segment_seconds",300))),
        "-reset_timestamps","1",
        "-strftime","1",
        pattern
    ]
    return cmd,folder

def start_recording(camera_id):
    camera=find_camera(camera_id)
    if not camera:
        return {"ok":False,"message":"Câmera não encontrada."}

    with RECORDING_LOCK:
        current=RECORDING_PROCESSES.get(str(camera_id))
        if current and current.get("process") and current["process"].poll() is None:
            return {"ok":True,"message":"Gravação já está ativa.","status":recording_status(camera_id)}

        cfg=recording_config()
        cmd,folder=recording_command(camera,cfg)
        if not cmd:
            return {"ok":False,"message":"Configuração RTSP incompleta."}

        log_path=folder/"recording.log"
        log=open(log_path,"ab",buffering=0)
        try:
            proc=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=log)
        except FileNotFoundError:
            log.close()
            return {"ok":False,"message":"FFmpeg não instalado. Execute: pkg install ffmpeg"}
        except Exception as e:
            log.close()
            return {"ok":False,"message":str(e)}

        RECORDING_PROCESSES[str(camera_id)]={
            "process":proc,
            "log":log,
            "started":time.strftime("%Y-%m-%d %H:%M:%S"),
            "folder":str(folder),
            "pid":proc.pid
        }
        return {"ok":True,"message":"Gravação iniciada.","status":recording_status(camera_id)}

def stop_recording(camera_id):
    with RECORDING_LOCK:
        item=RECORDING_PROCESSES.get(str(camera_id))
        if not item:
            return {"ok":True,"message":"Gravação já estava parada."}
        proc=item.get("process")
        try:
            if proc and proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except Exception: proc.kill()
        finally:
            try: item.get("log").close()
            except Exception: pass
            RECORDING_PROCESSES.pop(str(camera_id),None)
        return {"ok":True,"message":"Gravação interrompida."}

def recording_status(camera_id=None):
    with RECORDING_LOCK:
        ids=[str(camera_id)] if camera_id is not None else list(RECORDING_PROCESSES.keys())
        items=[]
        for cid in ids:
            item=RECORDING_PROCESSES.get(cid)
            if not item:
                if camera_id is not None:
                    return {"camera_id":cid,"recording":False}
                continue
            proc=item.get("process")
            active=bool(proc and proc.poll() is None)
            if not active:
                try: item.get("log").close()
                except Exception: pass
                RECORDING_PROCESSES.pop(cid,None)
                if camera_id is not None:
                    return {"camera_id":cid,"recording":False}
                continue
            items.append({
                "camera_id":cid,
                "recording":True,
                "started":item.get("started"),
                "folder":item.get("folder"),
                "pid":item.get("pid")
            })
        if camera_id is not None:
            return items[0] if items else {"camera_id":str(camera_id),"recording":False}
        return {"items":items}

def recordings_list(camera_id):
    camera=find_camera(camera_id)
    if not camera:
        return {"ok":False,"message":"Câmera não encontrada.","items":[]}
    folder=recording_dir(camera)
    items=[]
    for p in sorted(folder.glob("*.mp4"),key=lambda x:x.stat().st_mtime,reverse=True):
        st=p.stat()
        items.append({
            "name":p.name,
            "size_mb":round(st.st_size/1024/1024,2),
            "modified":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(st.st_mtime)),
            "path":str(p)
        })
    return {"ok":True,"items":items[:200],"folder":str(folder)}

def cleanup_recordings():
    cfg=recording_config()
    cutoff=time.time()-int(cfg.get("retention_days",7))*86400
    files=[]
    for p in recording_root().rglob("*.mp4"):
        try:
            st=p.stat()
            if st.st_mtime<cutoff:
                p.unlink()
            else:
                files.append((p,st))
        except Exception:
            pass

    max_bytes=int(cfg.get("max_storage_gb",20))*1024*1024*1024
    total=sum(st.st_size for _,st in files)
    if total>max_bytes:
        for p,st in sorted(files,key=lambda x:x[1].st_mtime):
            if total<=max_bytes: break
            try:
                p.unlink()
                total-=st.st_size
            except Exception:
                pass
    return {"ok":True,"used_gb":round(total/1024/1024/1024,2)}


def allowed_browser_roots():
    roots=[
        Path.home(),
        BASE,
        Path("/storage"),
        Path("/sdcard"),
        Path("/mnt/media_rw")
    ]
    out=[]
    seen=set()
    for p in roots:
        try:
            rp=p.expanduser().resolve()
            if rp.exists() and rp.is_dir() and str(rp) not in seen:
                seen.add(str(rp))
                out.append(rp)
        except Exception:
            pass
    return out

def path_is_allowed(path):
    try:
        rp=Path(path).expanduser().resolve()
        for root in allowed_browser_roots():
            try:
                rp.relative_to(root)
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False

def browse_folders(path_value=""):
    roots=allowed_browser_roots()
    if not path_value:
        return {
            "ok":True,
            "mode":"roots",
            "current":"",
            "parent":"",
            "items":[{"name":p.name or str(p),"path":str(p),"type":"folder"} for p in roots]
        }

    try:
        current=Path(path_value).expanduser().resolve()
    except Exception:
        return {"ok":False,"message":"Caminho inválido."}

    if not path_is_allowed(current):
        return {"ok":False,"message":"Acesso fora das pastas permitidas."}
    if not current.exists() or not current.is_dir():
        return {"ok":False,"message":"Pasta não encontrada."}

    items=[]
    try:
        for p in sorted(current.iterdir(),key=lambda x:x.name.lower()):
            if p.is_dir():
                try:
                    rp=p.resolve()
                    if path_is_allowed(rp):
                        items.append({"name":p.name,"path":str(rp),"type":"folder"})
                except Exception:
                    pass
    except Exception as e:
        return {"ok":False,"message":str(e)}

    parent=str(current.parent) if path_is_allowed(current.parent) and current.parent!=current else ""
    try:
        usage=shutil.disk_usage(current)
        free_gb=round(usage.free/1024/1024/1024,2)
        total_gb=round(usage.total/1024/1024/1024,2)
    except Exception:
        free_gb=total_gb=None

    return {
        "ok":True,
        "mode":"folder",
        "current":str(current),
        "parent":parent,
        "items":items,
        "free_gb":free_gb,
        "total_gb":total_gb
    }

def all_recordings():
    root=recording_root()
    items=[]
    cameras=load(CAMERAS,[])
    camera_by_folder={}
    for cam in cameras:
        try:
            camera_by_folder[str(recording_dir(cam).resolve())]=cam
        except Exception:
            pass

    for p in root.rglob("*.mp4"):
        try:
            st=p.stat()
            parent=str(p.parent.resolve())
            cam=camera_by_folder.get(parent,{})
            items.append({
                "id":hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:16],
                "name":p.name,
                "camera_id":cam.get("id",""),
                "camera_name":cam.get("name") or p.parent.name,
                "room":cam.get("room",""),
                "size_mb":round(st.st_size/1024/1024,2),
                "modified":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(st.st_mtime)),
                "timestamp":st.st_mtime,
                "path":str(p.resolve())
            })
        except Exception:
            pass
    return sorted(items,key=lambda x:x["timestamp"],reverse=True)

def recording_by_id(recording_id):
    for item in all_recordings():
        if item.get("id")==recording_id:
            return item
    return None

def delete_recording(recording_id):
    item=recording_by_id(recording_id)
    if not item:
        return {"ok":False,"message":"Gravação não encontrada."}
    path=Path(item["path"])
    if not path_is_allowed(path):
        return {"ok":False,"message":"Arquivo fora da área permitida."}
    try:
        path.unlink()
        return {"ok":True,"message":"Gravação excluída."}
    except Exception as e:
        return {"ok":False,"message":str(e)}

LIVE_CLIENTS={}
LIVE_LOCK=threading.Lock()

def find_camera(camera_id):
    return next((x for x in load(CAMERAS,[]) if str(x.get("id"))==str(camera_id)),None)

def camera_mjpeg_command(camera,fps=6,width=640):
    ip=str(camera.get("ip","")).strip()
    port=int(camera.get("port") or 554)
    path=str(camera.get("path","")).strip()
    user=str(camera.get("username",""))
    password=str(camera.get("password",""))
    transport=str(camera.get("transport","udp") or "udp").lower()
    if not ip or not path:
        return None

    url=rtsp_url(ip,port,path,user,password)
    cmd=["ffmpeg","-hide_banner","-loglevel","error"]
    if transport in ["tcp","udp"]:
        cmd += ["-rtsp_transport",transport]
    cmd += [
        "-i",url,
        "-an","-sn","-dn",
        "-vf",f"fps={max(1,min(12,int(fps)))},scale={int(width)}:-2",
        "-q:v","6",
        "-f","mjpeg",
        "pipe:1"
    ]
    return cmd

def iter_jpeg_frames(stream):
    buffer=b""
    while True:
        chunk=stream.read(8192)
        if not chunk:
            break
        buffer+=chunk
        while True:
            start=buffer.find(b"\xff\xd8")
            end=buffer.find(b"\xff\xd9",start+2) if start>=0 else -1
            if start<0 or end<0:
                if len(buffer)>4_000_000:
                    buffer=buffer[-1_000_000:]
                break
            frame=buffer[start:end+2]
            buffer=buffer[end+2:]
            yield frame

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): return
    def js(self,d,c=200):
        b=json.dumps(d,ensure_ascii=False).encode(); self.send_response(c)
        self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,DELETE,OPTIONS"); self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))).decode("utf-8","ignore"))
        except Exception: return {}
    def mjpeg(self,camera_id,fps=6,width=640):
        camera=find_camera(camera_id)
        if not camera:
            return self.js({"ok":False,"message":"Câmera não encontrada."},404)

        cmd=camera_mjpeg_command(camera,fps,width)
        if not cmd:
            return self.js({"ok":False,"message":"Configuração RTSP incompleta."},400)

        process=None
        try:
            process=subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            self.send_response(200)
            self.send_header("Content-Type","multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma","no-cache")
            self.send_header("Connection","close")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()

            with LIVE_LOCK:
                LIVE_CLIENTS[camera_id]=LIVE_CLIENTS.get(camera_id,0)+1

            for frame in iter_jpeg_frames(process.stdout):
                try:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError):
                    break
        except FileNotFoundError:
            if not self.wfile.closed:
                try: self.js({"ok":False,"message":"ffmpeg não instalado."},500)
                except Exception: pass
        except Exception:
            pass
        finally:
            with LIVE_LOCK:
                if camera_id in LIVE_CLIENTS:
                    LIVE_CLIENTS[camera_id]=max(0,LIVE_CLIENTS[camera_id]-1)
                    if LIVE_CLIENTS[camera_id]==0:
                        LIVE_CLIENTS.pop(camera_id,None)
            if process:
                try: process.terminate()
                except Exception: pass
                try: process.wait(timeout=2)
                except Exception:
                    try: process.kill()
                    except Exception: pass
    def serve_recording(self,recording_id):
        item=recording_by_id(recording_id)
        if not item:
            return self.js({"ok":False,"message":"Gravação não encontrada."},404)

        path=Path(item["path"])
        if not path.exists() or not path.is_file() or not path_is_allowed(path):
            return self.js({"ok":False,"message":"Arquivo indisponível."},404)

        size=path.stat().st_size
        range_header=self.headers.get("Range","")
        start=0
        end=size-1
        status=200

        if range_header.startswith("bytes="):
            try:
                spec=range_header.split("=",1)[1]
                a,b=spec.split("-",1)
                if a.strip():
                    start=int(a)
                if b.strip():
                    end=int(b)
                status=206
            except Exception:
                start=0; end=size-1; status=200

        start=max(0,min(start,size-1))
        end=max(start,min(end,size-1))
        length=end-start+1

        self.send_response(status)
        self.send_header("Content-Type","video/mp4")
        self.send_header("Accept-Ranges","bytes")
        self.send_header("Content-Length",str(length))
        self.send_header("Cache-Control","no-store")
        self.send_header("Access-Control-Allow-Origin","*")
        if status==206:
            self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
        self.end_headers()

        with path.open("rb") as f:
            f.seek(start)
            remaining=length
            while remaining>0:
                chunk=f.read(min(1024*1024,remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining-=len(chunk)

    def do_OPTIONS(self): self.js({"ok":True})
    def do_GET(self):
        u=urlparse(self.path)
        q=urllib.parse.parse_qs(u.query)
        if u.path=="/api/cameras/live.mjpeg":
            camera_id=(q.get("id") or [""])[0]
            try: fps=int((q.get("fps") or ["6"])[0])
            except Exception: fps=6
            try: width=int((q.get("width") or ["640"])[0])
            except Exception: width=640
            return self.mjpeg(camera_id,fps,width)
        if u.path=="/api/cameras/live/status":
            return self.js({"ok":True,"clients":LIVE_CLIENTS})
        if u.path=="/api/cameras/recordings":
            camera_id=(q.get("id") or [""])[0]
            return self.js(recordings_list(camera_id))
        if u.path=="/api/recordings":
            return self.js({"ok":True,"items":all_recordings(),"root":str(recording_root())})
        if u.path=="/api/recordings/play":
            recording_id=(q.get("id") or [""])[0]
            return self.serve_recording(recording_id)
        if u.path=="/api/storage/browse":
            path=(q.get("path") or [""])[0]
            return self.js(browse_folders(path))

        routes={"/api/status":lambda:status(),"/api/house":lambda:house(),"/api/connect/devices":lambda:{"items":load(DEVICES,[]),"summary":connect_summary()},"/api/connect/rooms":lambda:{"items":connect_summary().get("rooms",[]),"names":load(ROOMS,[])},"/api/connect/network":lambda:load(NETWORK,{}),"/api/discovery":lambda:load(NETWORK,{}),"/api/discovery/state":lambda:load(DISCOVERY_STATE,{}),"/api/connect/tuya/config":lambda:load(TUYA_CFG,{}),"/api/connect/tuya/cache":lambda:load(TUYA_CACHE,{}),"/api/jarvis":lambda:load(JARVIS,{}),"/api/cameras":lambda:{"items":[{**x,"password":"***" if x.get("password") else ""} for x in load(CAMERAS,[])]},"/api/camera-profiles":lambda:camera_profiles(),"/api/cameras/learned":lambda:{"items":list(learned_camera_profiles().values())},"/api/cameras/recording/config":lambda:recording_config(),"/api/cameras/recording/status":lambda:recording_status(),"/api/cameras/recording/storage-locations":lambda:storage_locations(),"/api/events":lambda:{"items":load(EVENTS,[])},"/api/notifications":lambda:{"items":load(NOTES,[])},"/api/system/diagnostic":lambda:{"status":status(),"house":house(),"network":load(NETWORK,{}),"discovery_state":load(DISCOVERY_STATE,{}),"tuya":load(TUYA_CFG,{}),"df":run("df -h"),"ip_neigh":run("ip neigh show"),"log":(LOGS/"api.log").read_text(errors="ignore")[-8000:] if (LOGS/"api.log").exists() else ""}}
        if u.path in routes: return self.js(routes[u.path]())
        self.js({"error":"rota não encontrada"},404)
    def do_POST(self):
        u=urlparse(self.path); d=self.body()
        if u.path=="/api/jarvis/command": return self.js(jarvis(d.get("command","")))
        if u.path in ["/api/connect/network/scan","/api/discovery/scan"]: return self.js(discovery_scan(d.get("limit"),d.get("deep",False)))
        if u.path=="/api/discovery/start": return self.js(discovery_start(d.get("limit"),d.get("deep",False)))
        if u.path=="/api/connect/device/add":
            d.setdefault("id",uuid.uuid4().hex[:8]); d.setdefault("source","manual"); d.setdefault("online",True); d["updated"]=now()
            a=load(DEVICES,[]); a.append(d); save(DEVICES,a); ev("device_add",f"{d.get('name','Dispositivo')} adicionado","success","connect"); return self.js({"ok":True})
        if u.path=="/api/connect/device/update":
            a=load(DEVICES,[])
            for x in a:
                if x.get("id")==d.get("id"): x.update(d); x["updated"]=now()
            save(DEVICES,a); return self.js({"ok":True})
        if u.path=="/api/connect/device/delete":
            save(DEVICES,[x for x in load(DEVICES,[]) if x.get("id")!=d.get("id")]); return self.js({"ok":True})
        if u.path=="/api/discovery/device/import":
            dev=d.get("device",{})
            if not dev.get("id"): return self.js({"ok":False,"message":"Dispositivo inválido"},400)
            item={"id":dev.get("id"),"source":"discovery","name":dev.get("name") or dev.get("ip"),"room":d.get("room") or dev.get("room") or "Rede","type":dev.get("type","device"),"online":True,"ip":dev.get("ip",""),"mac":dev.get("mac",""),"vendor":dev.get("vendor",""),"ports":dev.get("ports",[]),"services":dev.get("services",[]),"confidence":dev.get("confidence",0),"updated":now()}
            merge_devices([item]); ev("device_import",f"{item['name']} importado para Open Home Connect","success","discovery"); return self.js({"ok":True,"device":item})
        if u.path=="/api/connect/tuya/config":
            cfg=load(TUYA_CFG,{}); cfg.update(d); cfg["enabled"]=bool(d.get("enabled",cfg.get("enabled",False))); save(TUYA_CFG,cfg); ev("tuya_config","Configuração Tuya salva","success","connect"); return self.js({"ok":True,"config":cfg})
        if u.path=="/api/connect/tuya/test":
            cfg=load(TUYA_CFG,{}); cfg.update(d); save(TUYA_CFG,cfg); token=tuya_token(); return self.js({"ok":bool(token),"message":"Conectado à Tuya Cloud" if token else "Falha ao conectar à Tuya Cloud"})
        if u.path=="/api/connect/tuya/sync": return self.js(tuya_sync())
        if u.path=="/api/cameras/rtsp/test":
            return self.js(test_rtsp_config(d))
        if u.path=="/api/cameras/rtsp/add":
            return self.js(add_rtsp_camera(d))
        if u.path=="/api/cameras/onvif/probe":
            return self.js(onvif_probe(d))
        if u.path=="/api/cameras/analyze":
            dev=d.get("device",d)
            return self.js({"ok":True,"device":dev,"capabilities":camera_capabilities(dev)})
        if u.path=="/api/cameras/rtsp/diagnose":
            return self.js(rtsp_server_diagnostics(d))
        if u.path=="/api/cameras/full-diagnostic":
            return self.js(camera_full_diagnostic(d))
        if u.path=="/api/cameras/xiaomi/xiaofang":
            dev=d.get("device",d)
            return self.js({"ok":True,"xiaomi":xiaomi_xiaofang_probe(dev)})
        if u.path=="/api/cameras/snapshot":
            camera_id=str(d.get("id",""))
            camera=next((x for x in load(CAMERAS,[]) if str(x.get("id"))==camera_id),None)
            if not camera:
                return self.js({"ok":False,"message":"Câmera não encontrada."})
            return self.js(camera_snapshot(camera))
        if u.path=="/api/cameras/recording/start":
            return self.js(start_recording(str(d.get("id",""))))
        if u.path=="/api/cameras/recording/stop":
            return self.js(stop_recording(str(d.get("id",""))))
        if u.path=="/api/cameras/recording/config":
            saved=save_recording_config(d)
            if isinstance(saved,dict) and saved.get("error"):
                return self.js({"ok":False,"message":saved.get("error"),"config":saved.get("config")},400)
            return self.js({"ok":True,"config":saved})
        if u.path=="/api/cameras/recording/test-path":
            return self.js(test_recording_path(d.get("path","")))
        if u.path=="/api/cameras/recording/cleanup":
            return self.js(cleanup_recordings())
        if u.path=="/api/recordings/delete":
            return self.js(delete_recording(str(d.get("id",""))))




        if u.path=="/api/cameras/delete":
            cid=d.get("id")
            save(CAMERAS,[x for x in load(CAMERAS,[]) if x.get("id")!=cid])
            save(DEVICES,[x for x in load(DEVICES,[]) if x.get("id")!=cid])
            ev("camera_delete",f"Câmera {cid} excluída","info","camera")
            return self.js({"ok":True})
        if u.path=="/api/backup": return self.js({"ok":True,"file":backup()})
        if u.path=="/api/notifications/clear": save(NOTES,[]); return self.js({"ok":True})
        self.js({"error":"rota não encontrada"},404)

ev("server_start",VERSION,"success","core")
print(f"{VERSION} API rodando na porta 8090")
ThreadingHTTPServer(("0.0.0.0",8090),H).serve_forever()
