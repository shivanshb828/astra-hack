"""Authenticated mutations and local downloadable engineering artifacts."""
import json,secrets
from urllib.parse import unquote
from pathlib import Path
import design_workflow as workflow
ROOT=Path(__file__).resolve().parent
ASSETS=ROOT.parent/'wearable-cad'
CACHE=ROOT.parent/'detailed-cache'
CACHE_FILES={'missionpcb_detailed_assembly.blend','board.png','assembly.png','chest.png','exploded.png','cache-manifest.json','state.json'}
FILES={'wearable-assembly.blend','wearable-assembly.png','assembly-verification.json','ecg-chest-enclosure.blend','ecg-chest-enclosure.glb','enclosure-base.stl','enclosure-lid.stl','human-chest-reference.blend','human-chest-reference.glb','human-chest-reference.obj','manifest.json'}
def reply(h,code,value):
 body=json.dumps(value).encode();h.send_response(code);h.send_header('Content-Type','application/json');h.send_header('Cache-Control','no-store');h.end_headers();h.wfile.write(body)
def post(h,token):
 if h.headers.get('Host') not in ('127.0.0.1:8768','localhost:8768') or not secrets.compare_digest(h.headers.get('X-Widget-Token',''),token):return reply(h,403,{'error':'Unauthorized'})
 try:
  size=int(h.headers.get('Content-Length','0'))
  if h.path=='/workflow/schematic':
   import circuit_readiness
   if not 0<size<=circuit_readiness.MAX_SCHEMATIC_BYTES:raise ValueError('Choose a schematic up to 8 MiB.')
   result=circuit_readiness.attach_schematic(unquote(h.headers.get('X-Filename','')),h.rfile.read(size),expected_board_sha256=h.headers.get('X-Board-Revision'))
   workflow.append('schematic_attached',{'saved_board_sha256':result['saved_board_sha256'],'schematic':result['schematic']})
   return reply(h,200,result)
  if not 0<size<=16000:raise ValueError('Request must be 1–16000 bytes')
  p=json.loads(h.rfile.read(size));route=h.path
  if route=='/workflow/capture':result=workflow.capture('Initial design' if not workflow.events() else 'Current design snapshot')
  elif route=='/workflow/proposals':result=workflow.propose(p)
  elif route=='/workflow/decisions':result=workflow.decide(p)
  elif route=='/workflow/finding-decisions':result=workflow.decide_finding(p)
  elif route=='/workflow/comments':result=workflow.add_comment(p)
  elif route=='/workflow/focus':result=workflow.focus_finding(p)
  elif route=='/workflow/adopt-targets':result=workflow.adopt_brief_targets(p)
  elif route=='/workflow/profile':result=workflow.save_profile(p)
  elif route=='/workflow/generate-housing':result=workflow.generate_housing(p)
  elif route=='/workflow/inputs':result=workflow.save_inputs(p)
  elif route=='/workflow/checks':result=workflow.start_checks()
  elif route=='/workflow/import-asset':
   import blender_handoff
   name=p['name']
   if name not in ('ecg-chest-enclosure.glb','human-chest-reference.glb'):raise ValueError('Unknown asset')
   result=blender_handoff.upload(name,(ASSETS/name).read_bytes(),'m','body' if name.startswith('human') else 'product')
  else:return reply(h,404,{'error':'Unknown workflow action'})
  return reply(h,200,result)
 except (ValueError,KeyError,TypeError) as e:return reply(h,409 if any(w in str(e).lower() for w in ('changed','stale','already')) else 400,{'error':str(e)})
 except Exception as e:return reply(h,500,{'error':str(e)})
def get(h,token):
 try:
  name=None
  if h.path=='/workflow':body=(ROOT/'workflow.html').read_text().replace('__LOCAL_TOKEN__',json.dumps(token)).encode();mime='text/html'
  elif h.path=='/workflow/ui.js':body=(ROOT/'workflow-ui.js').read_bytes();mime='text/javascript'
  elif h.path=='/workflow/ui.css':body=(ROOT/'workflow-ui.css').read_bytes();mime='text/css'
  elif h.path=='/workflow/profile':return reply(h,200,workflow.profile_state())
  elif h.path=='/workflow/assembly-preview':body=((CACHE/'chest.png') if (CACHE/'cache-manifest.json').exists() else (ASSETS/'wearable-assembly.png')).read_bytes();mime='image/png'
  elif h.path=='/workflow/cache-state':
   manifest=CACHE/'cache-manifest.json'
   return reply(h,200,{'available':manifest.exists(),'manifest':json.loads(manifest.read_text()) if manifest.exists() else None})
  elif h.path.startswith('/workflow/cache/'):
   filename=h.path.rsplit('/',1)[1]
   if filename not in CACHE_FILES or not (CACHE/'cache-manifest.json').exists():return reply(h,404,{'error':'Detailed assembly cache is not ready.'})
   body=(CACHE/filename).read_bytes();mime='image/png' if filename.endswith('.png') else 'application/octet-stream'
   if not filename.endswith('.png'):name=filename
  elif h.path=='/workflow/state':return reply(h,200,workflow.view())
  elif h.path=='/workflow/summary':return reply(h,200,workflow.summary())
  elif h.path in ('/workflow/report.json','/workflow/report.md'):
   state=workflow.view();name='missionpcb-design-report.'+h.path.rsplit('.',1)[1]
   body=(json.dumps(state,indent=2) if name.endswith('json') else workflow.report_markdown(state)).encode();mime='application/json' if name.endswith('json') else 'text/markdown'
  elif h.path.startswith('/workflow/assets/'):
   name=h.path.rsplit('/',1)[1]
   if name not in FILES:return reply(h,404,{'error':'Unknown asset'})
   body=(ASSETS/name).read_bytes();mime='application/octet-stream'
  else:return reply(h,404,{'error':'Not found'})
  h.send_response(200);h.send_header('Content-Type',mime);h.send_header('Cache-Control','no-store')
  if name:h.send_header('Content-Disposition','attachment; filename="'+name+'"')
  h.end_headers();h.wfile.write(body)
 except Exception as e:return reply(h,500,{'error':str(e)})
