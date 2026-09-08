"""Visible non-copper review regions in KiCad, tracked by generated UUID only."""
import json
from pathlib import Path
import bridge
from board_profile import component_map
from kipy.board_types import BoardRectangle,BoardText,BoardLayer
from kipy.geometry import Vector2
ROOT=Path(__file__).resolve().parent
REGISTRY=ROOT/'runtime/native-region-flags.json'

def apply_findings(report):
 board=bridge.connect();before=bridge.snapshot(board)
 if report.get('native_board_revision')!=before['revision']:raise ValueError('Review is stale; run Full check again.')
 rows={p['ref']:p for p in before['parts']};mapped=component_map();library=json.loads((ROOT.parents[1]/'missionpcb_review/native-six-parts.json').read_text());parts={p['id']:p for p in library['parts']}
 status={}
 for f in report['findings']:
  if f['status']=='PASS':continue
  for ref in f.get('kicad_refs',[]):
   if status.get(ref)!='FAIL':status[ref]=f['status']
 generated=[]
 for ref,kind in status.items():
  if ref not in rows:continue
  pos=rows[ref];dims=parts[mapped[ref][1]]['dimensions_mm'];w,h=dims['length']+3,dims['width']+3
  if int(pos['rotation_deg'])%180:w,h=h,w
  layer=BoardLayer.BL_User_1 if kind=='FAIL' else BoardLayer.BL_User_2
  r=BoardRectangle();r.layer=layer;r.top_left=Vector2.from_xy_mm(pos['x_mm']-w/2,pos['y_mm']-h/2);r.bottom_right=Vector2.from_xy_mm(pos['x_mm']+w/2,pos['y_mm']+h/2);r.attributes.stroke.width=1000000;generated.append(r)
  text=BoardText();text.value=ref+' '+('ERROR' if kind=='FAIL' else 'WATCH');text.layer=layer;text.position=Vector2.from_xy_mm(pos['x_mm'],pos['y_mm']-h/2-1.5);text.attributes.size=Vector2.from_xy_mm(1.1,1.1);generated.append(text)
 registry=json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}
 oldids=set(registry.get('ids',[])) if registry.get('board')==str(bridge.TARGET) else set()
 old=[o for o in [*board.get_shapes(),*board.get_text()] if o.id.value in oldids]
 if bridge.snapshot(board)['revision']!=before['revision']:raise ValueError('Board changed while preparing flags.')
 tx=board.begin_commit()
 try:
  if old:board.remove_items(old)
  created=board.create_items(generated) if generated else []
  if len(created)!=len(generated):raise ValueError('Incomplete native flag creation')
 except Exception:board.drop_commit(tx);raise
 board.push_commit(tx,'MissionPCB: update visible review areas')
 layers={BoardLayer.BL_User_1,BoardLayer.BL_User_2}
 enabled=set(board.get_enabled_layers())
 if not layers<=enabled:board.set_enabled_layers(board.get_copper_layer_count(),list(enabled|layers))
 board.set_visible_layers(list(set(board.get_visible_layers())|layers))
 REGISTRY.parent.mkdir(exist_ok=True,parents=True);REGISTRY.write_text(json.dumps({'board':str(bridge.TARGET),'ids':[o.id.value for o in created]}))
 return 'Highlighted '+str(len(status))+' component areas on User.1 (errors) and User.2 (watch).'
