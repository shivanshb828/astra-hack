"""Authenticated local brief intake; file bytes never leave this machine."""
import json,secrets
from urllib.parse import unquote
import brief_store
from assembly_http import reply

def post(handler,token):
 if handler.headers.get('Host') not in ('127.0.0.1:8768','localhost:8768') or not secrets.compare_digest(handler.headers.get('X-Widget-Token',''),token):return reply(handler,403,{'error':'Unauthorized'})
 try:
  size=int(handler.headers.get('Content-Length','0'))
  if not 0<size<=brief_store.MAX_BYTES:raise ValueError('Choose a brief up to 5 MB.')
  data=handler.rfile.read(size)
  if handler.path=='/brief/upload':
   # Extract for review first. The Save brief action adopts the edited text.
   name=unquote(handler.headers.get('X-Filename','brief.txt'))
   result={'text':brief_store.extract(name,data),'filename':name}
  elif handler.path=='/brief/save':
   payload=json.loads(data);result=brief_store.save(payload['text'],payload.get('filename','Project brief'),payload['base_revision'])
  else:raise ValueError('Unknown brief action.')
  return reply(handler,200,result)
 except Exception as exc:return reply(handler,400,{'error':str(exc)})
