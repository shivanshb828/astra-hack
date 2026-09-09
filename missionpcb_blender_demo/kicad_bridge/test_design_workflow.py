import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import design_workflow as w
class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.patches=[patch.object(w.brief_store,'current',return_value={'text':w.brief_store.CANONICAL_BRIEF.read_text(),'revision':'fixture-brief','source':'test','filename':'test.md'}),patch.object(w.review_journal,'STORAGE_ROOT',Path(self.tmp.name)),patch.object(w.bridge,'connect',return_value=object()),patch.object(w.bridge,'snapshot',return_value={'board':str(w.bridge.TARGET),'revision':'r1','parts':[dict(ref='U1',x_mm=110,y_mm=110,rotation_deg=0)]}),patch.object(w,'evaluate',side_effect=lambda s:{'checks':[dict(id='x',status='FAIL' if s['parts'][0]['x_mm']==110 else 'PASS',margin_mm=-1 if s['parts'][0]['x_mm']==110 else 1)],'summary':{}}),patch.object(w.mission_constraints,'revision',return_value='c1')]
  for p in self.patches:p.start();self.addCleanup(p.stop)
 def proposal(self):return w.propose(dict(base_revision='r1',moves=[dict(ref='U1',x_mm=111,y_mm=110,rotation_deg=0)],rationale='Reduce interference'))['payload']
 def test_preview_does_not_apply(self):
  with patch.object(w.bridge,'apply') as apply:
   p=self.proposal();self.assertEqual(p['tradeoffs']['fixed'],['x']);apply.assert_not_called()
 def test_reject_keeps_history(self):
  p=self.proposal()
  with patch.object(w.bridge,'apply') as apply:w.decide(dict(proposal_id=p['proposal_id'],decision='reject',note='Prefer current routing'));apply.assert_not_called()
  self.assertEqual(w.events()[-1]['payload']['decision'],'reject')
 def test_stale_and_pinned_refused(self):
  p=self.proposal()
  with patch.object(w.mission_constraints,'revision',return_value='changed'),self.assertRaises(ValueError):w.decide(dict(proposal_id=p['proposal_id'],decision='accept',note='Reviewed'))
  w.review_journal.set_pin(str(w.bridge.TARGET),'U1',True)
  with self.assertRaises(ValueError):self.proposal()
 def test_apply_error_never_marked_accepted(self):
  p=self.proposal()
  with patch.object(w.bridge,'apply',side_effect=RuntimeError('uncertain')),self.assertRaises(RuntimeError):w.decide(dict(proposal_id=p['proposal_id'],decision='accept',note='Reviewed'))
  self.assertEqual(w.events()[-1]['kind'],'proposal_apply_error')
  with self.assertRaises(ValueError):w.decide(dict(proposal_id=p['proposal_id'],decision='accept',note='retry'))
 def test_capture_and_report(self):
  w.capture();self.assertEqual(w.events()[0]['kind'],'design_snapshot')
  text=w.report_markdown(dict(brief='Test brief',wearable_checks=[],events=w.events()))
  self.assertIn('Initial design',text);self.assertIn('No automatic copper routing',text)
 def test_budget_revision_guard(self):
  rev=w.input_revision();w.save_inputs(dict(base_revision=rev,inputs={'max_mass_g':10}))
  with self.assertRaises(ValueError):w.save_inputs(dict(base_revision=rev,inputs={}))

 def test_accept_calls_native_apply_once_and_schedules_checks(self):
  from unittest.mock import MagicMock
  p=self.proposal();current=w.bridge.snapshot(None);board=MagicMock()
  result={'before':current,'after':current,'applied':True}
  with patch.object(w.bridge,'connect',return_value=board),patch.object(w.bridge,'apply',return_value=result) as apply,patch.object(w,'capture'),patch.object(w,'start_checks') as checks,patch('native_flags.apply_findings'),patch('widget_command.record_review'),patch('widget_command.open_native_3d'):
   w.decide(dict(proposal_id=p['proposal_id'],decision='accept',note='Trade-offs reviewed'))
   apply.assert_called_once();board.save.assert_called_once();checks.assert_called_once()
   with self.assertRaises(ValueError):w.decide(dict(proposal_id=p['proposal_id'],decision='accept',note='Duplicate'))
 def test_finding_acceptance_keeps_failure(self):
  result=w.decide_finding(dict(base_revision='r1',constraint_revision='c1',finding_id='x',decision='accept_tradeoff',note='Explicit engineering decision'))
  self.assertEqual(result['payload']['technical_status'],'FAIL')
