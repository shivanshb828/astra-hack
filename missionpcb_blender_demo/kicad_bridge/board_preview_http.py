import json,re
from pathlib import Path
import blender_handoff as pipeline
ROOT=Path(__file__).resolve().parent
VENDOR=ROOT.parents[1]/'missionpcb_kicad/demo/vendor'
def get(handler,token):
 try:
  path=handler.path.split('?')[0]
  if path=='/board-preview':body=(ROOT/'board-preview.html').read_text().replace('__LOCAL_TOKEN__',json.dumps(token)).encode();mime='text/html'
  elif path=='/board-preview/state':body=json.dumps(pipeline.preview()).encode();mime='application/json'
  elif path.startswith('/board-preview/vendor/'):
   name=path.rsplit('/',1)[-1]
   if name not in ('three.module.js','three.core.js','GLTFLoader.js','OrbitControls.js','BufferGeometryUtils.js','SkeletonUtils.js'):raise ValueError('Unknown asset')
   body=(VENDOR/name).read_bytes();mime='text/javascript'
  elif re.fullmatch(r'/board-preview/[0-9a-f]{24}/board.glb',path):body=(pipeline.SESSIONS/path.split('/')[2]/'board.glb').read_bytes();mime='model/gltf-binary'
  else:handler.send_error(404);return
  handler.send_response(200);handler.send_header('Content-Type',mime);handler.send_header('Cache-Control','no-store');handler.end_headers();handler.wfile.write(body)
 except Exception as exc:
  import assembly_http
  assembly_http.reply(handler,400,{'error':str(exc)})
