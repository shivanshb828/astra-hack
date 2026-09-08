"""Read-only local dashboard; never mutates a board."""
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json
import bridge
import widget_command
import secrets
TOKEN=(Path(__file__).resolve().parent/'.widget-token').read_text()
ROOT=Path(__file__).resolve().parent
class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  if self.path!='/command' or self.headers.get('Host') not in ('127.0.0.1:8768','localhost:8768') or not secrets.compare_digest(self.headers.get('X-Widget-Token',''),TOKEN):
   self.send_error(403);return
  size=int(self.headers.get('Content-Length','0'))
  if not 0<size<=1000:self.send_error(400);return
  command=self.rfile.read(size).decode()
  widget_command.log_event(command,'running','Reading the MissionPCB board')
  try:
   message=widget_command.run(command)
   widget_command.log_event(command,'complete',message)
  except Exception as e:
   message='Could not apply: '+str(e)
   widget_command.log_event(command,'error',message)
  self.send_response(200);self.send_header('Content-Type','text/plain');self.end_headers();self.wfile.write(message.encode())
 def do_GET(self):
  if self.headers.get('Host') not in ('127.0.0.1:8768','localhost:8768'):
   self.send_error(403);return
  if self.path=='/state':
   try:state={'connected':True,**bridge.snapshot(bridge.connect())}
   except Exception as e:state={'connected':False,'error':str(e)}
   log=ROOT/'activity.jsonl'
   state['events']=[json.loads(s) for s in log.read_text().splitlines()[-60:]] if log.exists() else []
   body=json.dumps(state).encode();mime='application/json'
  elif self.path=='/':body=(ROOT/'dashboard.html').read_bytes();mime='text/html'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',8768),Handler).serve_forever()
