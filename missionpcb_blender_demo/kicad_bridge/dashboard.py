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
  if self.path not in ('/command','/comment','/pin') or self.headers.get('Host') not in ('127.0.0.1:8768','localhost:8768') or not secrets.compare_digest(self.headers.get('X-Widget-Token',''),TOKEN):
   self.send_error(403);return
  try:size=int(self.headers.get('Content-Length','0'))
  except ValueError:self.send_error(400);return
  if not 0<size<=6000:self.send_error(400);return
  command=self.rfile.read(size).decode()
  if self.path in ('/comment','/pin'):
   try:
    import review_journal
    payload=json.loads(command)
    if self.path=='/comment':
     if not isinstance(payload.get('text'),str) or not 0<len(payload['text'].strip())<=2000:raise ValueError('Comment must be1–2000characters')
     finding_id=payload.get('finding_id')
     if not isinstance(finding_id,str) or not 0<len(finding_id)<=300:raise ValueError('Invalid finding ID')
     review_journal.add_comment(str(bridge.TARGET),finding_id,payload['text'])
    else:
     if payload.get('ref') not in ('U1','U2','U3','U4','U5','J1') or not isinstance(payload.get('pinned'),bool):raise ValueError('Invalid pin')
     review_journal.set_pin(str(bridge.TARGET),payload['ref'],payload['pinned'])
    self.send_response(200);self.end_headers();self.wfile.write(b'Saved');return
   except Exception as e:
    self.send_response(400);self.end_headers();self.wfile.write(str(e).encode());return
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
   try:
    board=bridge.connect();state={'connected':True,**bridge.snapshot(board)}
    from kipy.board_types import BoardLayer
    state['review_visible']=BoardLayer.BL_Cmts_User in board.get_visible_layers()
    state['selected_refs']=[f.reference_field.text.value for f in board.get_selection() if hasattr(f,'reference_field')]
   except Exception as e:state={'connected':False,'error':str(e)}
   log=ROOT/'activity.jsonl'
   state['events']=[json.loads(s) for s in log.read_text().splitlines()] if log.exists() else []
   try:
    import review_journal
    state['journal']=review_journal.get_state(str(bridge.TARGET))
   except Exception as e:
    state['journal']={'comments':[],'pins':{},'events':[]};state['journal_error']=str(e)
   reviews=sorted((ROOT.parents[1]/'missionpcb_review/exchange').glob('*-reviewed/findings.json'),key=lambda p:p.stat().st_mtime,reverse=True)
   if reviews:
    latest=reviews[0];review=json.loads(latest.read_text());meta=json.loads((latest.parent/'engineering.json').read_text())
    state['review']=review;state['review_stale']=state.get('revision')!=meta['native_snapshot']['revision']
   review_events=[e for e in state['journal']['events'] if e.get('kind')=='engine_review']
   if review_events:
    event=review_events[-1];payload=event['payload']
    from datetime import datetime
    newer=not reviews or datetime.fromisoformat(event['timestamp']).timestamp()>=reviews[0].stat().st_mtime
    if newer:
     state['review']=payload;state['review_stale']=state.get('revision')!=payload.get('native_board_revision')
   body=json.dumps(state).encode();mime='application/json'
  elif self.path=='/context':
   import design_context
   body=json.dumps(design_context.get_context()).encode();mime='application/json'
  elif self.path=='/design':body=(ROOT/'design-dashboard.html').read_text().replace('__LOCAL_TOKEN__',json.dumps(TOKEN)).encode();mime='text/html'
  elif self.path=='/ui-vendor/motion.js':body=(ROOT/'ui-vendor/motion.js').read_bytes();mime='text/javascript'
  elif self.path=='/classic':body=(ROOT/'dashboard.html').read_text().replace('__LOCAL_TOKEN__',json.dumps(TOKEN)).encode();mime='text/html'
  elif self.path=='/':body=(ROOT/'design-dashboard.html').read_text().replace('__LOCAL_TOKEN__',json.dumps(TOKEN)).encode();mime='text/html'
  else:self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',8768),Handler).serve_forever()
