"""Local widget assembly routes; upload bytes never leave this machine."""
import json,secrets
from pathlib import Path
from urllib.parse import unquote
import blender_handoff as pipeline
ROOT=Path(__file__).resolve().parent
ACTIONS={'assembly_view','assembly_comment','assembly_flag_motion','assembly_region','assembly_place','assembly_edit','assembly_focus','assembly_check','assembly_body','assembly_sample','assembly_save','assembly_fit_chest','assembly_select_body'}
def reply(handler,status,value):
 body=json.dumps(value).encode();handler.send_response(status);handler.send_header('Content-Type','application/json');handler.send_header('Cache-Control','no-store');handler.end_headers();handler.wfile.write(body)
def post(handler,token):
 if handler.headers.get('Host') not in ('127.0.0.1:8768','localhost:8768') or not secrets.compare_digest(handler.headers.get('X-Widget-Token',''),token):return reply(handler,403,{'error':'Unauthorized'})
 try:
  size=int(handler.headers.get('Content-Length','0'))
  limit=100*1024*1024 if handler.path=='/assembly/upload' else 16000
  if not 0<size<=limit:raise ValueError('Request is empty or too large.')
  data=handler.rfile.read(size)
  if handler.path=='/assembly/upload':result=pipeline.upload(unquote(handler.headers.get('X-Filename','')),data,handler.headers.get('X-Units','mm'),handler.headers.get('X-Role','product'),expected_session=handler.headers.get('X-Blender-Session'))
  else:
   payload=json.loads(data)
   if handler.path=='/assembly/open':result=pipeline.open_session()
   elif handler.path=='/assembly/confirm':result=pipeline.confirm(payload['revision'],expected_session=payload.get('expected_session'))
   elif handler.path=='/assembly/push-preview':result=pipeline.push_preview(payload['id'])
   elif handler.path=='/assembly/action':
    action=payload.pop('action')
    if action not in ACTIONS:raise ValueError('Unsupported action.')
    result=pipeline.dispatch(action,**payload)
   else:raise ValueError('Unknown route.')
  return reply(handler,200,result)
 except Exception as exc:return reply(handler,400,{'error':str(exc)})
