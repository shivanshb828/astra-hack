"""Loopback-only viewer server. Serves cached assets and a narrowly scoped command API."""
from http.server import HTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import json,math,secrets,time,uuid
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parent;PUBLIC=ROOT/'public';IPC=ROOT/'bridge';PORT=8765
TOKEN=secrets.token_urlsafe(32)
ORIGINS={f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'}
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(PUBLIC),**k)
    def log_message(self,*args):pass
    def reply(self,code,data):
        body=json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def host_ok(self):return self.headers.get('Host') in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'}
    def do_GET(self):
        if not self.host_ok():return self.reply(403,{'error':'Invalid host'})
        path=urlsplit(self.path).path
        if path=='/api/session':return self.reply(200,{'token':TOKEN})
        if path=='/api/state':
            try:data=json.loads((IPC/'state.json').read_text());data['connected']=time.time()-data['heartbeat']<3;return self.reply(200,data)
            except (FileNotFoundError,ValueError):return self.reply(200,{'connected':False})
        if path.startswith('/api/'):return self.reply(404,{'error':'Unknown endpoint'})
        return super().do_GET()
    def list_directory(self,path):return self.reply(404,{'error':'Not found'})
    def do_POST(self):
        if not self.host_ok() or self.headers.get('Origin') not in ORIGINS or self.headers.get('Authorization')!='Bearer '+TOKEN:return self.reply(403,{'error':'Request not authorized'})
        if self.path!='/api/command':return self.reply(404,{'error':'Unknown endpoint'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<2048:raise ValueError('Invalid request size')
            data=json.loads(self.rfile.read(length));current=json.loads((IPC/'state.json').read_text())
            if time.time()-current['heartbeat']>3 or current.get('error'):return self.reply(409,{'error':'Blender is disconnected or needs attention'})
            if data.get('base_signature')!=current['signature']:return self.reply(409,{'error':'Stale scene; refresh and retry'})
            action=data.get('action')
            if action not in ('move','reset','validate'):raise ValueError('Unsupported action')
            if action=='move':
                if data.get('ref') not in {'MCU','Sensor','RF','Regulator','Driver','Battery'}:raise ValueError('Unknown component')
                if any(isinstance(data.get(k),bool) or not isinstance(data.get(k),(int,float)) or not math.isfinite(data[k]) or abs(data[k])>100 for k in ('x','y')):raise ValueError('Invalid coordinates')
            if (IPC/'command.json').exists():return self.reply(409,{'error':'A command is already pending'})
            command={k:data[k] for k in ('action','ref','x','y','base_signature') if k in data};command.update(id=str(uuid.uuid4()),created=time.time())
            temp=IPC/'command.tmp';temp.write_text(json.dumps(command,allow_nan=False));temp.replace(IPC/'command.json')
            return self.reply(202,{'id':command['id']})
        except (ValueError,KeyError,FileNotFoundError):return self.reply(400,{'error':'Invalid request'})
if __name__=='__main__':
    IPC.mkdir(exist_ok=True);print(f'MissionPCB viewer: http://127.0.0.1:{PORT}',flush=True)
    HTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
