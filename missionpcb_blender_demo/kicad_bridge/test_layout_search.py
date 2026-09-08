import unittest
from layout_search import rank_report,choose_best,to_native_moves
class RankingTests(unittest.TestCase):
 def test_hard_failures_beat_small_movement(self):
  good={'checks':[{'id':'mission.a','status':'PASS'}]}
  bad={'checks':[{'id':'mission.a','status':'FAIL','severity':'blocker','margin_mm':-1}]}
  self.assertLess(rank_report(good,100),rank_report(bad,0))
 def test_larger_violation_loses_tie(self):
  def r(m):return {'checks':[{'id':'mission.a','status':'FAIL','severity':'blocker','margin_mm':m}]}
  self.assertLess(rank_report(r(-1),10),rank_report(r(-5),0))
 def test_winner_is_deterministic(self):
  candidates=[{'id':2,'rank':[0,0,0,0,10]},{'id':1,'rank':[0,0,0,0,10]}]
  self.assertEqual(choose_best(candidates)['id'],1)
 def test_native_conversion_preserves_rf_alignment(self):
  placements=[{'ref':'RF','x_mm':10,'y_mm':20,'rotation_deg':90}]
  self.assertEqual(to_native_moves(placements,{'RF':'U3'}),[{'ref':'U3','x_mm':110,'y_mm':118,'rotation_deg':0}])
if __name__=='__main__':unittest.main()

class SearchIntegrationTests(unittest.TestCase):
 def test_ten_real_validated_candidates_keep_pins(self):
  import layout_search,board_profile,json
  data=json.loads((layout_search.ROOT/'missionpcb_kicad/cache/results.json').read_text())['results']['Naive']
  refs={role:ref for ref,(role,_) in board_profile.CORE_MAP.items()}
  moves=[dict(ref=refs[p['ref']],x_mm=100+p['board_xy_mm'][0],y_mm=138-p['board_xy_mm'][1],rotation_deg=90 if p['ref']=='RF' else 0) for p in data['component_positions']]
  rows=layout_search.generate({'parts':moves},{p['ref']:True for p in moves})
  self.assertEqual(len(rows),10)
  for row in rows:
   self.assertTrue(row['checks']);self.assertEqual(row['movement_mm'],0)
   self.assertEqual({p['ref']:(p['x_mm'],p['y_mm'],p['rotation_deg']) for p in row['moves']},{p['ref']:(p['x_mm'],p['y_mm'],p['rotation_deg']) for p in moves})

class ApplyGuards(unittest.TestCase):
 def test_stale_board_rejected_before_native_write(self):
  from unittest.mock import patch
  import layout_search as s
  job={'status':'complete','board_revision':'old','constraint_revision':'rules','pins':{}}
  with patch.object(s,'status',return_value=job),patch.object(s.bridge,'connect'),patch.object(s.bridge,'snapshot',return_value={'revision':'new'}),patch.object(s.bridge,'apply') as apply:
   with self.assertRaisesRegex(ValueError,'changed'):s.apply_winner()
   apply.assert_not_called()
 def test_changed_pins_rejected_before_native_write(self):
  from unittest.mock import patch
  import layout_search as s
  job={'status':'complete','board_revision':'same','constraint_revision':'rules','pins':{}}
  with patch.object(s,'status',return_value=job),patch.object(s.bridge,'connect'),patch.object(s.bridge,'snapshot',return_value={'revision':'same','board':'test'}),patch.object(s.mission_constraints,'revision',return_value='rules'),patch.object(s.review_journal,'get_state',return_value={'pins':{'U1':True}}),patch.object(s.bridge,'apply') as apply:
   with self.assertRaisesRegex(ValueError,'pins changed'):s.apply_winner()
   apply.assert_not_called()

class SearchRecoveryTests(unittest.TestCase):
 def test_completed_result_survives_new_python_process(self):
  import json,subprocess,sys,tempfile
  from pathlib import Path
  import layout_search as s
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'search.json'
   job={'status':'complete','before':{'board':str(s.bridge.TARGET)},'winner':{'id':4},'completed':10}
   path.write_text(json.dumps(job))
   code="import json,sys; from pathlib import Path; import layout_search as s; s.JOB_FILE=Path(sys.argv[1]); print(json.dumps(s.status()))"
   result=subprocess.check_output([sys.executable,'-c',code,str(path)],cwd=Path(s.__file__).parent,text=True)
   self.assertEqual(json.loads(result),job)
 def test_interrupted_worker_is_reported_without_losing_candidates(self):
  import json,tempfile
  from pathlib import Path
  from unittest.mock import patch
  import layout_search as s
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'search.json'
   path.write_text(json.dumps({'status':'running','pid':123,'before':{'board':str(s.bridge.TARGET)},'candidates':[{'id':1}]}))
   with patch.object(s,'JOB_FILE',path),patch.object(s,'process_running',return_value=False):result=s.status()
   self.assertEqual(result['status'],'failed');self.assertEqual(result['candidates'],[{'id':1}])


class BackgroundSearchTests(unittest.TestCase):
 def setUp(self):
  from unittest.mock import patch
  import layout_search as s
  self.s=s;s._pending_key=None
  self.before={'board':'test','revision':'a','parts':[]}
  self.patches=[patch.object(s.review_journal,'get_state',return_value={'pins':{}}),patch.object(s.mission_constraints,'revision',return_value='rules'),patch.object(s,'status',return_value=None),patch.object(s,'start')]
  self.journal,self.rules,self.status,self.start=[p.start() for p in self.patches]
  for p in self.patches:self.addCleanup(p.stop)
 def test_edits_are_debounced_and_only_compute_starts(self):
  s=self.s;s.ensure_background(self.before,now=0);s.ensure_background(self.before,now=1)
  self.start.assert_not_called()
  s.ensure_background(self.before,now=2)
  self.start.assert_called_once_with(before=self.before,pins={},constraint_revision='rules')
 def test_completed_or_failed_input_is_not_repeated(self):
  s=self.s
  for status in ('complete','failed','applied'):
   self.status.return_value={'status':status,'before':self.before,'pins':{},'constraint_revision':'rules'}
   s.ensure_background(self.before,now=0);s.ensure_background(self.before,now=3)
  self.start.assert_not_called()
 def test_new_pins_schedule_a_fresh_suggestion(self):
  s=self.s;self.status.return_value={'status':'complete','before':self.before,'pins':{},'constraint_revision':'rules'}
  s.ensure_background(self.before,now=0);self.journal.return_value={'pins':{'U1':True}}
  s.ensure_background(self.before,now=2);s.ensure_background(self.before,now=4)
  self.start.assert_called_once_with(before=self.before,pins={'U1':True},constraint_revision='rules')
 def test_busy_worker_and_disconnected_board_never_start_search(self):
  s=self.s;self.status.return_value={'status':'running'}
  s.ensure_background(self.before,now=0);s.ensure_background(self.before,now=3)
  s.ensure_background({'connected':False},now=5)
  self.start.assert_not_called()
