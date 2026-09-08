"""Deterministic engine scenarios; never edits the native board."""
import unittest,sys,json,tempfile,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'missionpcb_blender_demo/kicad_bridge'),str(ROOT/'missionpcb_review')]
from constraint_engine import load_parts,load_layout,validate
from layout_adapter import payload_for
class Scenarios(unittest.TestCase):
 def test_geometric_failures(self):
  source=json.loads((ROOT/'missionpcb_blender_demo/component_pass/engine_validation_results.json').read_text())['results']['MissionPCB']['component_positions']
  refs={'MCU':'U1','Sensor':'U2','RF':'U3','Regulator':'U4','Driver':'U5','Battery':'J1'}
  before={'parts':[dict(ref=refs[p['ref']],x_mm=100+p['board_xy_mm'][0],y_mm=138-p['board_xy_mm'][1],rotation_deg=90 if p['ref']=='RF' else 0) for p in source]}
  baseline=payload_for(before)['layout'];parts,_=load_parts(ROOT/'missionpcb_review/native-six-parts.json')
  scenarios={
   'overlap':lambda l:l['placements'][1].update(pos_mm=l['placements'][0]['pos_mm']),
   'outside_board':lambda l:l['placements'][0].update(pos_mm=[-3,8]),
   'height':lambda l:l['board'].update(max_component_height_mm=.3),
   'wall':lambda l:l['enclosure'].update(wall_keepout_mm=15),
   'antenna':lambda l:next(p for p in l['placements'] if p['ref']=='MCU').update(pos_mm=[1,29]),
  }
  with tempfile.TemporaryDirectory() as tmp:
   def check(layout):
    p=Path(tmp)/'layout.json';p.write_text(json.dumps(layout));obj,w=load_layout(p);return validate(obj,parts,w).to_dict()
   base=check(baseline);basefailed={c['id'] for c in base['checks'] if c['status']=='FAIL'}
   for name,mutate in scenarios.items():
    with self.subTest(name=name):
     l=copy.deepcopy(baseline);mutate(l);r=check(l);failed={c['id'] for c in r['checks'] if c['status']=='FAIL'}
     self.assertTrue(failed-basefailed,(name,r['summary']))
if __name__=='__main__':unittest.main()
