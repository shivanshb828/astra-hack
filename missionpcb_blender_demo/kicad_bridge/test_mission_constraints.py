import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import mission_constraints as mc
import brief_store
from board_profile import CORE_MAP
from layout_adapter import payload_for
class MissionConstraintsTests(unittest.TestCase):
 def setUp(self):
  brief=patch.object(brief_store,"current",return_value={"text":mc.BRIEF.read_text(),"revision":"fixture","source":"fixture"});brief.start();self.addCleanup(brief.stop)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  p=patch.object(mc,'OVERRIDES',Path(self.tmp.name)/'limits.json');p.start();self.addCleanup(p.stop)
  self.state={'parts':[{'ref':r,'x_mm':120,'y_mm':120,'rotation_deg':0} for r in CORE_MAP]}
 def test_edited_limit_enters_engine_and_invalidates_review(self):
  old=mc.revision();self.state['review']={'constraint_revision':old,'checks':[{'id':'mission.afe_MCU','status':'PASS','measured_mm':22}]}
  self.assertEqual(mc.view(self.state)['rows'][0]['status'],'PASS')
  mc.update('afe_MCU',25,old)
  self.assertEqual(next(r for r in payload_for(self.state)['layout']['mission_rules'] if r['id']=='afe_MCU')['distance_mm'],25)
  self.assertEqual(mc.view(self.state)['rows'][0]['status'],'STALE')
  with self.assertRaisesRegex(ValueError,'refresh'):mc.update('afe_MCU',20,old)
 def test_unknown_coverage_does_not_become_pass(self):
  self.state['review']={'constraint_revision':mc.revision(),'checks':[]}
  rows=mc.view(self.state)['rows']
  self.assertEqual(next(r for r in rows if r['id']=='runtime')['status'],'NOT EVALUATED')
  self.assertEqual(next(r for r in rows if r['id']=='support_C1')['status'],'NOT PRESENT')
 def test_invalid_limits_rejected(self):
  for value in (True,0,-1,101,float('nan'),'18'):
   with self.assertRaises(ValueError):mc.update('afe_MCU',value,mc.revision())
if __name__=='__main__':unittest.main()
