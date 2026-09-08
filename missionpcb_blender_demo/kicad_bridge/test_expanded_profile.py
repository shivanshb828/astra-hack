"""Expanded cached layout checks using the real local compute engine."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
import board_profile,bridge,widget_command
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'missionpcb_review')]
from layout_adapter import payload_for
from constraint_engine import load_layout,load_parts,validate
class ExpandedProfile(unittest.TestCase):
 def state(self,key):
  data=json.loads((ROOT/'missionpcb_kicad/cache/results.json').read_text())['results'][key]
  refs={role:ref for ref,(role,_) in board_profile.CORE_MAP.items()}
  moves=[dict(ref=refs[p['ref']],x_mm=100+p['board_xy_mm'][0],y_mm=138-p['board_xy_mm'][1],rotation_deg=90 if p['ref']=='RF' else 0) for p in data['component_positions']]
  return {'parts':board_profile.expand_moves(moves,set(board_profile.component_map()))}
 def evaluate(self,state):
  payload=payload_for(state)
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'layout.json';p.write_text(json.dumps(payload['layout']));layout,w=load_layout(p)
   parts,_=load_parts(ROOT/'missionpcb_review/native-six-parts.json');return validate(layout,parts,w).to_dict()
 def test_expanded_baseline_and_improvement(self):
  baseline=self.state('Naive');improved=self.state('MissionPCB')
  self.assertEqual(len(improved['parts']),18)
  self.assertGreaterEqual(self.evaluate(baseline)['summary']['FAIL'],7)
  report=self.evaluate(improved)
  self.assertEqual(report['summary']['FAIL'],0,[c['message'] for c in report['checks'] if c['status']=='FAIL'])
  self.assertGreater(report['summary']['PASS'],60)
 def test_decoupling_distance_is_actually_checked(self):
  state=self.state('MissionPCB');next(p for p in state['parts'] if p['ref']=='C1')['x_mm']=103
  report=self.evaluate(state)
  self.assertTrue(any(c['id']=='mission.support_C1' and c['status']=='FAIL' for c in report['checks']))
 def test_support_commands_and_full_move_validation(self):
  self.assertEqual(widget_command.parse('Move C1 2 mm right'),('relative','C1',2.,'right'))
  state=self.state('MissionPCB');state.update(board=str(bridge.TARGET),revision='test')
  self.assertEqual(len(bridge.validate({'board':str(bridge.TARGET),'base_revision':'test','moves':state['parts']},state)),18)
if __name__=='__main__':unittest.main()
