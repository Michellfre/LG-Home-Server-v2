#!/usr/bin/env python3
import json, subprocess, time, uuid, zipfile, hmac, hashlib, urllib.request, socket, ipaddress, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

VERSION="Open Home OS v13.5 RTSP Camera Setup"
BUILD="000340"

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


RTSP_COMMON_PATHS=[
    "/stream1","/stream2","/live/ch00_0","/live/ch00_1","/live/ch0",
    "/cam/realmonitor?channel=1&subtype=0","/cam/realmonitor?channel=1&subtype=1",
    "/h264","/11","/12","/onvif1","/videoMain","/videoSub",
    "/Streaming/Channels/101","/Streaming/Channels/102"
]

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

def ffprobe_rtsp(url,timeout=7):
    cmd=["ffprobe","-v","error","-rtsp_transport","tcp","-show_entries",
         "stream=codec_name,width,height,r_frame_rate","-of","json",url]
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        if p.returncode==0:
            data=json.loads(p.stdout or "{}")
            streams=data.get("streams",[])
            video=next((x for x in streams if x.get("width") or x.get("codec_name")),streams[0] if streams else {})
            return {"ok":True,"stream":video,"message":"Stream RTSP validado."}
        err=(p.stderr or "Falha ao abrir o stream.").strip()[-500:]
        return {"ok":False,"message":err}
    except FileNotFoundError:
        return {"ok":False,"message":"ffprobe não instalado. Execute: pkg install ffmpeg"}
    except subprocess.TimeoutExpired:
        return {"ok":False,"message":"Tempo esgotado ao testar o stream."}
    except Exception as e:
        return {"ok":False,"message":str(e)}

def test_rtsp_config(d):
    ip=str(d.get("ip","")).strip()
    if not ip:
        return {"ok":False,"message":"IP obrigatório."}
    port=int(d.get("port") or 554)
    user=str(d.get("username",""))
    password=str(d.get("password",""))
    manual=str(d.get("path","")).strip()
    paths=[manual] if manual else RTSP_COMMON_PATHS
    attempts=[]
    for path in paths:
        url=rtsp_url(ip,port,path,user,password)
        result=ffprobe_rtsp(url)
        attempts.append({"path":path,"ok":result.get("ok",False),"message":result.get("message","")})
        if result.get("ok"):
            return {"ok":True,"path":path,"stream":result.get("stream",{}),
                    "safe_url":rtsp_url(ip,port,path,user,"***" if password else ""),
                    "attempts":attempts}
    return {"ok":False,"message":"Nenhum caminho RTSP respondeu com as credenciais fornecidas.","attempts":attempts}

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
    def do_OPTIONS(self): self.js({"ok":True})
    def do_GET(self):
        u=urlparse(self.path)
        routes={"/api/status":lambda:status(),"/api/house":lambda:house(),"/api/connect/devices":lambda:{"items":load(DEVICES,[]),"summary":connect_summary()},"/api/connect/rooms":lambda:{"items":connect_summary().get("rooms",[]),"names":load(ROOMS,[])},"/api/connect/network":lambda:load(NETWORK,{}),"/api/discovery":lambda:load(NETWORK,{}),"/api/discovery/state":lambda:load(DISCOVERY_STATE,{}),"/api/connect/tuya/config":lambda:load(TUYA_CFG,{}),"/api/connect/tuya/cache":lambda:load(TUYA_CACHE,{}),"/api/jarvis":lambda:load(JARVIS,{}),"/api/cameras":lambda:{"items":[{**x,"password":"***" if x.get("password") else ""} for x in load(CAMERAS,[])]},"/api/events":lambda:{"items":load(EVENTS,[])},"/api/notifications":lambda:{"items":load(NOTES,[])},"/api/system/diagnostic":lambda:{"status":status(),"house":house(),"network":load(NETWORK,{}),"discovery_state":load(DISCOVERY_STATE,{}),"tuya":load(TUYA_CFG,{}),"df":run("df -h"),"ip_neigh":run("ip neigh show"),"log":(LOGS/"api.log").read_text(errors="ignore")[-8000:] if (LOGS/"api.log").exists() else ""}}
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
HTTPServer(("0.0.0.0",8090),H).serve_forever()
