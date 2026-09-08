"""Actual KiCad -> complete package -> engine -> annotated package -> live comments."""
import argparse,json,sys,tempfile,uuid,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'missionpcb_blender_demo/kicad_bridge')]
import bridge,packages
from layout_adapter import payload_for
from constraint_engine import load_layout,load_parts,validate
from kipy.board_types import BoardText,BoardLayer
from kipy.geometry import Vector2
PREFIX='MissionPCB review: '

def submit(revision):
 board=bridge.connect();before=bridge.snapshot(board)
 payload=payload_for(before)
 bindings=[]
 for f in board.get_footprints():
  ref=f.reference_field.text.value
  placement=next(p for p in payload['layout']['placements'] if payload['kicad_refs'][p['ref']]==ref)
  bindings.append({'kicad_ref':ref,'uuid':f.id.value,'catalog_id':placement['part_id'],'engine_ref':placement['ref'],'models':[m.filename for m in f.definition.models]})
 if bridge.snapshot(board)['revision']!=before['revision']:raise ValueError('Board changed during snapshot')
 board.save()
 metadata={'payload':payload,'bindings':bindings,'native_snapshot':before,'source_board_sha256':packages.sha(bridge.TARGET.read_bytes()),'coordinates':{'unit':'mm','kicad_to_board_local':'x_local=x_kicad-100; y_local=138-y_kicad','enclosure_origin_mm':[9,6,2]},'assumptions':['Fixed demo enclosure and cached package dimensions; U2/U4 approximate.','No complete schematic, routing or patient/battery validation.']}
 return packages.prepare(revision,metadata)

def review(outbound):
 # Only review locally prepared, immutable submissions.
 with zipfile.ZipFile(outbound) as z:data={n:z.read(n) for n in z.namelist()}
 manifest=json.loads(data['manifest.json']);revision=manifest['revision']
 for name,digest in manifest['files'].items():
  if packages.sha(data[name])!=digest:raise ValueError('Submission hash mismatch')
 meta=json.loads(data['engineering.json']);payload=meta['payload']
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp)/'layout.json';path.write_text(json.dumps(payload['layout']))
  partpath=Path(tmp)/'parts.json';partpath.write_bytes(data['parts.json'])
  layout,w=load_layout(path);parts,pw=load_parts(partpath)
  result=validate(layout,parts,w+pw).to_dict()
 findings=[c for c in result['checks'] if c['status']!='PASS']
 annotations=[]
 positions={p['ref']:p for p in meta['native_snapshot']['parts']}
 for n,c in enumerate(findings):
  refs=[payload['kicad_refs'][r] for r in c.get('subjects',[]) if r in payload['kicad_refs']]
  c['kicad_refs']=refs
  # Compact numbered marker at each affected component; complete comments beside board.
  for ref in refs:
   pos=positions[ref];annotations.append({'text':PREFIX+f"[{n+1}] {c['status']} {ref}",'x':pos['x_mm'],'y':pos['y_mm']-3-n*.6})
  annotations.append({'text':PREFIX+f"[{n+1}] {c['status']} {','.join(refs) or 'Coverage'}: "+c.get('message','')[:220],'x':140,'y':145+n*3})
 reviewed={'revision':revision,'source_board_sha256':meta['source_board_sha256'],'findings':findings,'summary':result['summary'],'annotations':annotations,'limitations':meta['assumptions']+['Distance proxies do not establish temperatures or medical compliance.']}
 data['findings.json']=json.dumps(reviewed,indent=2).encode()
 source=data[manifest['board']].decode();idx=source.rfind(')')
 drawings='\n'.join('(gr_text '+json.dumps(a['text'])+f' (at {a["x"]} {a["y"]}) (layer "Cmts.User") (uuid "{uuid.uuid4()}") (effects (font (size 0.7 0.7) (thickness 0.1))))' for a in annotations)
 data[manifest['board']]=(source[:idx]+drawings+'\n'+source[idx:]).encode()
 output=Path(outbound).with_name(Path(outbound).stem+'-return.zip')
 if output.exists():raise ValueError('Return archive exists')
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for name,value in data.items():z.writestr(name,value)
 return output

def apply(archive):
 staged=packages.receive(archive)
 result=json.loads((staged.parents[1]/'findings.json').read_text())
 board=bridge.connect();before=bridge.snapshot(board)
 # Full live-document hash catches unsaved edits too, not just footprint positions.
 with tempfile.TemporaryDirectory() as tmp:
  live=Path(tmp)/'MissionPCB.kicad_pcb';board.save_as(str(live),include_project=False)
  if packages.sha(live.read_bytes())!=result['source_board_sha256']:raise ValueError('Live board changed since submission; review staged but not applied')
 annotations=result.get('annotations',[])
 if len(annotations)>100:raise ValueError('Too many annotations')
 changes=[]
 for a in annotations:
  if not isinstance(a['text'],str) or not a['text'].startswith(PREFIX) or len(a['text'])>500:raise ValueError('Invalid review text')
  if not all(isinstance(a[k],(float,int)) and -1000<a[k]<1000 for k in ('x','y')):raise ValueError('Invalid annotation coordinates')
  item=BoardText();item.value=a['text'];item.position=Vector2.from_xy_mm(a['x'],a['y']);item.layer=BoardLayer.BL_Cmts_User
  item.attributes.size=Vector2.from_xy_mm(.7,.7);item.attributes.stroke_width=100000
  changes.append(item)
 old=[t for t in board.get_text() if isinstance(t,BoardText) and t.value.startswith(PREFIX)]
 tx=board.begin_commit()
 try:
  if old:board.remove_items(old)
  created=board.create_items(changes) if changes else []
  if len(created)!=len(changes):raise ValueError('Incomplete annotation creation')
 except Exception:board.drop_commit(tx);raise
 board.push_commit(tx,'MissionPCB: import reviewed findings')
 if bridge.snapshot(board)['revision']!=before['revision']:raise RuntimeError('Unexpected placement change; inspect Undo')
 found=[t for t in board.get_text() if isinstance(t,BoardText) and t.value.startswith(PREFIX)]
 if len(found)!=len(changes):raise RuntimeError('Annotation readback failed')
 board.save()
 return {'reviewed_board':str(staged),'annotations_applied':len(found),'summary':result['summary'],'undo':'One KiCad Undo removes this import; save afterward to persist undo.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['submit','review','apply','cycle']);p.add_argument('value');a=p.parse_args()
 if a.action=='cycle':print(json.dumps(apply(review(submit(a.value))),indent=2))
 else:print(globals()[a.action](a.value))
