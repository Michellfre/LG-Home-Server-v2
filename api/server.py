#!/usr/bin/env python3
import json, subprocess, time, uuid, zipfile, shutil, socket, ipaddress, mimetypes, re
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs,unquote
VERSION='v10.7 Jarvis + TV Mode'; HOME=Path.home(); BASE=HOME/'Servidor'; WEB=BASE/'Web'; CFG=BASE/'Config'
AREAS={k:BASE/v for k,v in {'files':'Files','documents':'Documents','downloads':'Downloads','media':'Media','photos':'Photos','videos':'Videos','music':'Music','cameras':'Cameras','backups':'Backups','trash':'Trash','logs':'Logs','snapshots':'Snapshots','streams':'Streams','shared':'Shared'}.items()}
for p in [*AREAS.values(),WEB,CFG]: p.mkdir(parents=True,exist_ok=True)
P=lambda n: CFG/n
CAM,NOT,EV,CACHE,DISC,JAR,SET,SETUP=[P(x) for x in 'cameras.json notifications.json events.json sensor_cache.json discovery.json jarvis.json settings.json setup.json'.split()]
def ensure(p,d):
    if not p.exists(): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
ensure(CAM,[]); ensure(NOT,[]); ensure(EV,[]); ensure(CACHE,{'ts':0}); ensure(DISC,[]); ensure(JAR,{'history':[],'tv_mode':False,'name':'Jarvis'}); ensure(SETUP,{'done':False,'step':1})
ensure(SET,{'device_name':'LG K41S','version':VERSION,'camera_retention_days':30,'auto_delete_when_disk_above':90,'battery_low_level':20,'temperature_alert':40,'backup_hour':'02:00','jarvis_enabled':True,'jarvis_voice':True})
NET={'time':time.time(),'rx':0,'tx':0}; CPU={'total':0,'idle':0}
def run(c,t=6):
    try: return subprocess.check_output(c,shell=True,text=True,stderr=subprocess.DEVNULL,timeout=t).strip()
    except Exception: return ''
def load(p,d):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return d
def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def safe(n): return Path(n).name
def note(t,m,l='info'):
    a=load(NOT,[]); a.insert(0,{'id':uuid.uuid4().hex[:8],'title':t,'message':m,'level':l,'time':time.strftime('%d/%m/%Y %H:%M:%S')}); save(NOT,a[:120])
def event(k,m='',l='info',cam=''):
    a=load(EV,[]); a.insert(0,{'id':uuid.uuid4().hex[:8],'kind':k,'message':m,'level':l,'camera':cam,'time':time.strftime('%d/%m/%Y %H:%M:%S'),'date':time.strftime('%Y-%m-%d')}); save(EV,a[:500])
def ip(): return run("ip -o -4 addr show | awk '!/127.0.0.1/ {split($4,a,\"/\"); print a[1]; exit}'") or 'não encontrado'
def tj(c):
    o=run(c,5)
    try: return json.loads(o) if o else {}
    except Exception: return {}
def battery():
    b=tj('termux-battery-status')
    return {'available':bool(b),'percentage':b.get('percentage'),'status':b.get('status'),'temperature':b.get('temperature'),'raw':b} if b else {'available':False,'message':'Termux:API não respondeu'}
def wifi():
    w=tj('termux-wifi-connectioninfo')
    return {'available':bool(w),'ssid':w.get('ssid') or 'indisponível','ip':w.get('ip'),'rssi':w.get('rssi'),'link_speed_mbps':w.get('link_speed_mbps') or w.get('link_speed'),'raw':w} if w else {'available':False,'ssid':'indisponível'}
def cpu():
    global CPU
    try:
        v=[int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:]]; idle=v[3]+(v[4] if len(v)>4 else 0); total=sum(v)
        if not CPU['total']: CPU={'total':total,'idle':idle}; return 'calculando...'
        dt=total-CPU['total']; di=idle-CPU['idle']; CPU={'total':total,'idle':idle}; return f'{int((1-di/dt)*100)}%' if dt>0 else '0%'
    except Exception: return 'indisponível'
def net():
    global NET
    raw=run("cat /proc/net/dev | awk '/wlan|eth|rmnet/ {rx+=$2; tx+=$10} END {print rx\",\"tx}'")
    try: rx,tx=[int(x or 0) for x in raw.split(',')]
    except Exception: rx=tx=0
    now=time.time(); el=max(1,now-NET['time']); d={'download_s':max(0,int((rx-NET['rx'])/el)),'upload_s':max(0,int((tx-NET['tx'])/el))}; NET={'time':now,'rx':rx,'tx':tx}; return d
def disk_used():
    try: return int(run(f"df {HOME} | awk 'NR==2 {{print $5}}'").replace('%',''))
    except Exception: return 0
def counts():
    c=load(CAM,[]); return {'registered':len(c),'online':len([x for x in c if x.get('verified') and x.get('status')=='online']),'pending':len([x for x in c if not x.get('verified')]),'offline':len([x for x in c if x.get('status')=='offline']),'recording':len([x for x in c if x.get('verified') and x.get('recording') in ['always','motion','schedule']])}
def status():
    b=battery(); w=wifi(); cc=counts()
    temp=b.get('temperature')
    return {'version':VERSION,'ip':ip(),'nginx':'Ativo' if run('pgrep nginx') else 'Parado','api':'Ativa','disk':run(f"df -h {HOME} | awk 'NR==2 {{print $4 \" livre de \" $2}}'"),'used':f'{disk_used()}%','cpu':cpu(),'cpu_load':run("cat /proc/loadavg | awk '{print $1}'"),'mem':run("free -m | awk '/Mem:/ {print $3\" MB usado de \"$2\" MB\"}'"),'uptime':run('uptime -p'),'battery':f"{b.get('percentage')}% • {b.get('status','')}" if b.get('percentage') is not None else 'indisponível','battery_detail':b,'temperature':f'{temp}°C' if temp is not None else 'indisponível','wifi':w.get('ssid'),'wifi_detail':w,'network':net(),'cameras_registered':cc['registered'],'cameras_online':cc['online'],'cameras_pending':cc['pending'],'cameras_offline':cc['offline'],'cameras_recording':cc['recording'],'snapshot_files':len([p for p in AREAS['snapshots'].rglob('*') if p.is_file()]),'setup':load(SETUP,{}),'settings':load(SET,{}),'jarvis':load(JAR,{}),'updated':run("date '+%d/%m/%Y %H:%M:%S'"),'python':run('python --version')}
def test_port(h,p,to=.3):
    try:
        with socket.create_connection((h,p),timeout=to): return True
    except Exception: return False
def rtsp(addr,user='',pwd=''):
    auth=f'{user}:{pwd}@' if user or pwd else ''
    return [f'rtsp://{auth}{addr}:554/onvif1',f'rtsp://{auth}{addr}:554/onvif2',f'rtsp://{auth}{addr}:554/live/ch00_0',f'rtsp://{auth}{addr}:554/live/ch00_1',f'rtsp://{auth}{addr}:554/11',f'rtsp://{auth}{addr}:8554/live',f'http://{addr}:8080/video']
def probe(url):
    if not url: return {'ok':False,'message':'URL vazia'}
    if url.startswith('rtsp://'):
        if not run('command -v ffprobe || command -v ffmpeg'): return {'ok':False,'message':'ffmpeg/ffprobe não instalado'}
        out=run(f'ffprobe -v error -rtsp_transport tcp -i "{url}" -show_entries stream=codec_name,width,height,r_frame_rate -of json',8)
        if out:
            try:
                info=json.loads(out); s=(info.get('streams') or [{}])[0]; return {'ok':True,'message':'RTSP funcionando','codec':s.get('codec_name'),'width':s.get('width'),'height':s.get('height'),'fps':s.get('r_frame_rate')}
            except Exception: return {'ok':True,'message':'RTSP respondeu'}
        return {'ok':False,'message':'RTSP não respondeu'}
    m=re.match(r'https?://([^/:]+)(?::(\d+))?',url); return {'ok':bool(m and test_port(m.group(1),int(m.group(2) or 80),.7)),'message':'HTTP testado'}
def snap(url,label='camera'):
    target=AREAS['snapshots']/f"{safe(label).replace(' ','_')}_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    if not run('command -v ffmpeg'): return {'ok':False,'message':'ffmpeg não instalado'}
    run(f'ffmpeg -y -rtsp_transport tcp -i "{url}" -frames:v 1 "{target}"',12) if url.startswith('rtsp://') else run(f'ffmpeg -y -i "{url}" -frames:v 1 "{target}"',10)
    return {'ok':target.exists() and target.stat().st_size>0,'file':target.name if target.exists() else '', 'message':'snapshot'}
def verify(cam):
    ports=[p for p in [554,8554,80,8080,8081,8899] if cam.get('ip') and test_port(cam['ip'],p)]
    pr=probe(cam.get('rtsp','')); sn=snap(cam.get('rtsp',''),cam.get('name','camera')) if pr.get('ok') else {'ok':False,'message':'snapshot ignorado'}
    score=(30 if ports else 0)+(40 if pr.get('ok') else 0)+(20 if sn.get('ok') else 0)+(10 if cam.get('user') or cam.get('password') else 0)
    return {'id':cam.get('id'),'name':cam.get('name'),'ip':cam.get('ip'),'ports':ports,'online':bool(ports),'rtsp':pr,'snapshot':sn,'score':score,'verified':bool(ports and pr.get('ok') and sn.get('ok'))}
def discover():
    me=ip(); res=[]; ports=[554,8554,80,8080,8081,8899]
    if me=='não encontrado': return []
    for h in ipaddress.ip_network(me+'/24',strict=False).hosts():
        a=str(h)
        if a==me: continue
        op=[p for p in ports if test_port(a,p)]
        if op:
            score=88 if 8899 in op else 78 if 554 in op or 8554 in op else 45
            typ='Yoosee provável' if 8899 in op else 'RTSP/ONVIF provável' if 554 in op or 8554 in op else 'Dispositivo web'
            res.append({'id':uuid.uuid4().hex[:8],'ip':a,'ports':op,'type':typ,'brand':'IP Camera' if score>50 else 'Desconhecida','score':score,'suggested_name':f'Camera {len(res)+1}','rtsp_suggestions':rtsp(a),'snapshot':'','configured':False})
    save(DISC,res); note('Busca de câmeras',f'{len(res)} dispositivo(s) encontrado(s).'); return res
def med(p):
    e=p.suffix.lower();
    return 'image' if e in ['.jpg','.jpeg','.png','.webp','.gif'] else 'video' if e in ['.mp4','.webm','.mov','.mkv','.ts'] else 'audio' if e in ['.mp3','.wav','.ogg'] else 'pdf' if e=='.pdf' else 'document'
def list_files(a,q='',sort='name'):
    rows=[]; query=q.lower().strip(); base=AREAS.get(a,AREAS['files'])
    for p in base.iterdir():
        if query and query not in p.name.lower(): continue
        s=p.stat(); rows.append({'name':p.name,'type':'folder' if p.is_dir() else 'file','media':med(p),'size':s.st_size,'modified_ts':s.st_mtime,'modified':time.strftime('%d/%m/%Y %H:%M',time.localtime(s.st_mtime))})
    rows.sort(key=lambda x:x['modified_ts'] if sort=='date' else x['size'] if sort=='size' else x['name'].lower(), reverse=sort in ['date','size']); return rows
def backup(kind='manual'):
    f=AREAS['backups']/f"backup_{kind}_{time.strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED) as z:
        for base in [AREAS['files'],AREAS['documents'],AREAS['cameras'],CFG]:
            for p in base.rglob('*'):
                if p.is_file(): z.write(p,p.relative_to(BASE))
    note('Backup concluído',f.name,'success'); return f.name
def jarvis(cmd):
    text=(cmd or '').lower(); st=status(); reply='Não entendi. Tente: Jarvis, status do servidor; Jarvis, modo TV; Jarvis, mostrar câmeras.'; action='none'
    if 'dashboard' in text: reply='Abrindo dashboard.'; action='open_dashboard'
    elif 'modo tv' in text or 'espelhar' in text or ' tv' in text: j=load(JAR,{}); j['tv_mode']=True; save(JAR,j); reply='Modo TV ativado.'; action='open_tv'
    elif 'câmera' in text or 'camera' in text: c=counts(); reply=f"Existem {c['registered']} câmeras cadastradas. {c['online']} online e {c['pending']} aguardando configuração."; action='open_cameras'
    elif 'verificar' in text and ('câmera' in text or 'camera' in text): reply='Verificando câmeras.'; action='verify_cameras'
    elif 'bateria' in text: reply=f"A bateria está em {st['battery']}."; action='speak'
    elif 'temperatura' in text: reply=f"A temperatura está em {st['temperature']}."; action='speak'
    elif 'disco' in text or 'espaço' in text or 'armazenamento' in text: reply=f"O disco está com {st['disk']} e uso de {st['used']}."; action='speak'
    elif 'backup' in text: f=backup('jarvis'); reply=f'Backup criado: {f}.'; action='backup'
    elif 'status' in text or 'servidor' in text: reply=f"Servidor online. IP {st['ip']}. Nginx {st['nginx']}. API {st['api']}. Disco {st['disk']}."; action='speak'
    j=load(JAR,{'history':[]}); j.setdefault('history',[]).insert(0,{'command':cmd,'reply':reply,'action':action,'time':time.strftime('%d/%m/%Y %H:%M:%S')}); j['history']=j['history'][:80]; save(JAR,j); return {'ok':True,'reply':reply,'action':action,'status':st}
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): return
    def j(self,d,code=200):
        b=json.dumps(d,ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Methods','GET,POST,DELETE,OPTIONS'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        try: return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode())
        except Exception: return {}
    def do_OPTIONS(self): self.j({'ok':True})
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=='/api/status': return self.j(status())
        if u.path=='/api/jarvis': return self.j(load(JAR,{}))
        if u.path=='/api/cameras': return self.j({'items':load(CAM,[])})
        if u.path=='/api/camera/discover': return self.j({'items':discover()})
        if u.path=='/api/camera/discovery': return self.j({'items':load(DISC,[])})
        if u.path=='/api/camera/suggest': return self.j({'items':rtsp(q.get('ip',[''])[0],q.get('user',[''])[0],q.get('password',[''])[0])})
        if u.path=='/api/camera/probe': return self.j(probe(q.get('url',[''])[0]))
        if u.path=='/api/settings': return self.j(load(SET,{}))
        if u.path=='/api/setup': return self.j(load(SETUP,{}))
        if u.path=='/api/notifications': return self.j({'items':load(NOT,[])})
        if u.path=='/api/events': return self.j({'items':load(EV,[])})
        if u.path=='/api/library': return self.j({'image':len(list(AREAS['snapshots'].glob('*.jpg'))),'video':0,'audio':0,'pdf':0,'document':0,'archive':0})
        if u.path=='/api/files': return self.j({'area':q.get('area',['files'])[0],'items':list_files(q.get('area',['files'])[0],q.get('q',[''])[0],q.get('sort',['name'])[0])})
        if u.path=='/api/system/permissions': return self.j({'termux_api':bool(run('command -v termux-battery-status')),'ffmpeg':bool(run('command -v ffmpeg')),'ffprobe':bool(run('command -v ffprobe')),'hint':'Verificação concluída'})
        if u.path=='/api/system/logs': p=AREAS['logs']/ 'api.log'; return self.j({'text':'\n'.join(p.read_text(errors='ignore').splitlines()[-120:]) if p.exists() else ''})
        if u.path=='/api/system/processes': return self.j({'text':run('ps 2>/dev/null | head -30')})
        if u.path=='/api/system/folders': return self.j({'items':[]})
        if u.path=='/api/system/largest': return self.j({'items':[]})
        if u.path in ['/api/view','/api/download']:
            p=AREAS.get(q.get('area',['files'])[0],AREAS['files'])/safe(unquote(q.get('name',[''])[0]))
            if not p.exists(): return self.j({'error':'arquivo não encontrado'},404)
            data=p.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(str(p))[0] or 'application/octet-stream'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(data); return
        self.j({'error':'rota não encontrada'},404)
    def do_POST(self):
        u=urlparse(self.path); d=self.body()
        if u.path=='/api/jarvis/command': return self.j(jarvis(d.get('command','')))
        if u.path=='/api/jarvis/tv': j=load(JAR,{}); j['tv_mode']=bool(d.get('enabled')); save(JAR,j); return self.j({'ok':True,'jarvis':j})
        if u.path=='/api/settings': s=load(SET,{}); s.update(d); save(SET,s); return self.j({'ok':True})
        if u.path=='/api/setup': st=load(SETUP,{}); st.update(d); save(SETUP,st); return self.j({'ok':True})
        if u.path=='/api/setup/finish': save(SETUP,{'done':True,'step':99,'finished':time.strftime('%d/%m/%Y %H:%M:%S')}); return self.j({'ok':True})
        if u.path=='/api/backup': return self.j({'ok':True,'file':backup(d.get('kind','manual'))})
        if u.path in ['/api/camera/add','/api/camera/quickadd']:
            addr=d.get('ip',''); chosen=d.get('rtsp') or (rtsp(addr,d.get('user',''),d.get('password',''))[0] if addr else '')
            cam={'id':uuid.uuid4().hex[:8],'name':d.get('name') or f'Camera {addr}','type':d.get('type','auto'),'brand':d.get('brand','IP Camera'),'ip':addr,'user':d.get('user',''),'password':d.get('password',''),'rtsp':chosen,'quality':d.get('quality','media'),'recording':d.get('recording','manual'),'location':d.get('location',''),'favorite':False,'status':'pending','verified':False,'snapshot':''}
            if u.path.endswith('quickadd'):
                r=verify(cam); cam['last_report']=r; cam['verified']=r['verified']; cam['status']='online' if r['verified'] else 'pending'; cam['snapshot']=r.get('snapshot',{}).get('file','') if r.get('snapshot',{}).get('ok') else ''
            cams=load(CAM,[]); cams.append(cam); save(CAM,cams); return self.j({'ok':True,'camera':cam})
        if u.path=='/api/camera/verify':
            cams=load(CAM,[]); ids=d.get('ids') or [c['id'] for c in cams]; reps=[]
            for c in cams:
                if c['id'] in ids:
                    r=verify(c); reps.append(r); c['last_report']=r; c['verified']=r['verified']; c['status']='online' if r['verified'] else 'pending'; c['snapshot']=r.get('snapshot',{}).get('file','') if r.get('snapshot',{}).get('ok') else c.get('snapshot','')
            save(CAM,cams); return self.j({'ok':True,'reports':reps})
        if u.path=='/api/camera/snapshot':
            cams=load(CAM,[]); c=next((x for x in cams if x['id']==d.get('id')),None)
            if not c: return self.j({'ok':False},404)
            r=snap(c.get('rtsp',''),c.get('name','camera'))
            if r.get('ok'): c['snapshot']=r['file']; c['verified']=True; c['status']='online'; save(CAM,cams)
            return self.j(r)
        if u.path=='/api/camera/favorite':
            cams=load(CAM,[])
            for c in cams:
                if c['id']==d.get('id'): c['favorite']=not c.get('favorite',False)
            save(CAM,cams); return self.j({'ok':True})
        if u.path=='/api/camera/delete': save(CAM,[c for c in load(CAM,[]) if c.get('id')!=d.get('id')]); return self.j({'ok':True})
        if u.path=='/api/camera/check': return self.j({'ok':True,'items':load(CAM,[])})
        if u.path=='/api/notifications/clear': save(NOT,[]); return self.j({'ok':True})
        self.j({'error':'rota não encontrada'},404)
    def do_DELETE(self): self.j({'ok':True})
event('server_start',f'API {VERSION} iniciada.','success'); print(f'Open Home Server API {VERSION} rodando na porta 8090'); HTTPServer(('0.0.0.0',8090),H).serve_forever()
