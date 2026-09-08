"""Build the offline placement demo using KiCad's bundled Python runtime."""
from pathlib import Path
import json, shutil, hashlib, re
import pcbnew as p
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
PARTS=REPO/'missionpcb_blender_demo/parts'
LIB=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
SOURCE=REPO/'missionpcb_blender_demo/component_pass/engine_validation_results.json'
DATA=json.loads(SOURCE.read_text())
SPECS={
'MCU':('Package_DFN_QFN','Texas_RGE0024H_VQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm','U1','Package matches RGE0024H'),
'Sensor':('Package_DFN_QFN','QFN-32-1EP_4x4mm_P0.4mm_EP2.65x2.65mm','U2','APPROXIMATE: exposed pad 2.65 versus 2.8 mm'),
'RF':('RF_Module','Raytac_MDBT42Q','U3','Manufacturer family outline'),
'Regulator':('Package_DFN_QFN','Texas_DSQ0010A_WSON-10-1EP_2x2mm_P0.4mm_EP0.9x1.5mm','U4','APPROXIMATE: wrong pin count and body; placement demo only'),
'Driver':('Package_TO_SOT_SMD','SOT-23-5','U5','Generic SOT23-5 package; height not verified'),
'Battery':('Connector_JST','JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical','J1','JST family package; connector only')}
def vec(x,y): return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
manifest=[]
for role,(lib,name,ref,note) in SPECS.items():
 probe=PARTS/'converted_models'/((name if role!='RF' else 'mdbt42q')+'.kicad_pcb')
 model=Path(re.search(r'\(model "([^"]+)"',probe.read_text()).group(1))
 target=ROOT/'models'/model.name
 shutil.copy2(model,target)
 manifest.append(dict(role=role,reference=ref,footprint=lib+':'+name,model=str(target.relative_to(ROOT)),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),limitation=note))
for layout in ('Naive','MissionPCB'):
 board=p.BOARD()
 for a,b in [((100,100),(172,100)),((172,100),(172,138)),((172,138),(100,138)),((100,138),(100,100))]:
  s=p.PCB_SHAPE(); s.SetShape(p.SHAPE_T_SEGMENT); s.SetStart(vec(*a)); s.SetEnd(vec(*b)); s.SetLayer(p.Edge_Cuts); s.SetWidth(p.FromMM(.05)); board.Add(s)
 for position in DATA['results'][layout]['component_positions']:
  role=position['ref']; lib,name,ref,note=SPECS[role]
  fp=p.FootprintLoad(str(LIB/(lib+'.pretty')),name)
  assert fp is not None,name
  fp.SetReference(ref); fp.SetValue(position['part_name']+(' [APPROX]' if 'APPROXIMATE' in note else ''))
  x,y=position['board_xy_mm']; fp.SetPosition(vec(100+x,138-y))
  fp.SetOrientationDegrees(-position['rotation_deg'])
  fp.Models().clear()
  model=p.FP_3DMODEL(); model.m_Filename='${KIPRJMOD}/../models/'+next(m['model'].split('/')[-1] for m in manifest if m['role']==role)
  if role=='RF':
   model.m_Rotation.x=-90; model.m_Rotation.z=0
   fp.SetOrientationDegrees(90-position['rotation_deg'])
  fp.Models().push_back(model)
  board.Add(fp)
 text=p.PCB_TEXT(board); text.SetText('MissionPCB | ECG placement demo'); text.SetPosition(vec(136,103)); text.SetTextSize(vec(1,1)); text.SetLayer(p.F_SilkS); board.Add(text)
 text=p.PCB_TEXT(board); text.SetText('CACHED / UNROUTED'); text.SetPosition(vec(136,136)); text.SetTextSize(vec(.8,.8)); text.SetLayer(p.F_SilkS); board.Add(text)
 path=ROOT/'cache'/(layout+'.kicad_pcb'); p.SaveBoard(str(path),board)
 # Cache boards are copied to the canonical project before opening; models resolve there.
 check=p.LoadBoard(str(path)); assert len(list(check.GetFootprints()))==6
 assert len(list(check.GetTracks()))==0
(ROOT/'cache/results.json').write_text(json.dumps(DATA,indent=2))
(ROOT/'cache/models.json').write_text(json.dumps(manifest,indent=2))
print('Built and reopened both cached boards: 6 footprints each, no routed tracks. Canonical board not overwritten.')
