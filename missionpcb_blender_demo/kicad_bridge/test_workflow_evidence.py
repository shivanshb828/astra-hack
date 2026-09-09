import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import brief_targets,brief_store,design_workflow as w
import test_design_workflow as baseline
class BriefTargetsTests(unittest.TestCase):
 def test_canonical14days_and_no_interior_as_external(self):
  data=brief_targets.extract(brief_store.CANONICAL_BRIEF.read_text());self.assertEqual(data['candidates'][0]['value'],336);self.assertEqual(len(data['candidates']),1)
 def test_ambiguous_runtime_is_not_automatically_chosen(self):
  data=brief_targets.extract('Wear for 7 days, possible 14 days.');self.assertFalse(data['candidates']);self.assertEqual(data['ambiguous'][0]['field'],'required_runtime_hours')
class WorkflowEvidenceTests(unittest.TestCase):
 setUp=baseline.WorkflowTests.setUp
 proposal=baseline.WorkflowTests.proposal
 def test_capture_failure_after_apply_is_explicit_not_retryable(self):
  p=self.proposal();current=w.bridge.snapshot(None);board=MagicMock()
  with patch.object(w.bridge,'connect',return_value=board),patch.object(w.bridge,'apply',return_value={'after':current}) as apply,patch.object(w,'capture',side_effect=RuntimeError('snapshot unavailable')),patch.object(w,'start_checks'),patch('native_flags.apply_findings'),patch('widget_command.record_review'),patch('widget_command.open_native_3d'):
   result=w.decide(dict(proposal_id=p['proposal_id'],decision='accept',note='Reviewed'))
   self.assertTrue(result['placement_applied']);self.assertIn('snapshot',result['warnings'][0]);board.save.assert_called_once()
   with self.assertRaises(ValueError):w.decide(dict(proposal_id=p['proposal_id'],decision='accept',note='Retry'))
   apply.assert_called_once()
 def test_annotation_error_still_saves_and_checks(self):
  p=self.proposal();current=w.bridge.snapshot(None);board=MagicMock()
  with patch.object(w.bridge,'connect',return_value=board),patch.object(w.bridge,'apply',return_value={'after':current}),patch.object(w,'capture'),patch.object(w,'start_checks') as checks,patch('native_flags.apply_findings',side_effect=RuntimeError('marker failure')),patch('widget_command.record_review'),patch('widget_command.open_native_3d'):
   result=w.decide(dict(proposal_id=p['proposal_id'],decision='accept',note='Reviewed'))
   board.save.assert_called_once();checks.assert_called_once();self.assertIn('markers',result['warnings'][0])
 def test_housing_requires_current_profile_and_observed_session(self):
  with patch('blender_handoff.dispatch') as dispatch:
   with self.assertRaisesRegex(ValueError,'connection'):w.generate_housing({'profile_revision':'fake'})
   with self.assertRaisesRegex(ValueError,'Review'):w.generate_housing({'profile_revision':'fake','expected_session':'scene1'})
   dispatch.assert_not_called()
 def test_brief_target_adoption_checks_both_revisions(self):
  targets=w.brief_targets()
  with self.assertRaises(ValueError):w.adopt_brief_targets(dict(brief_revision='stale',input_revision=targets['input_revision'],fields=['required_runtime_hours']))
  w.adopt_brief_targets(dict(brief_revision=targets['brief_revision'],input_revision=targets['input_revision'],fields=['required_runtime_hours']))
  self.assertEqual(w.inputs()['required_runtime_hours'],336)
 def test_comments_visible_in_full_journal(self):
  w.capture();w.add_comment({'finding_id':'x','text':'Check coupling on assembled device'})
  data=w.view();self.assertEqual(data['journal']['comments'][0]['text'],'Check coupling on assembled device');self.assertTrue(any(e['kind']=='comment_added' for e in data['events']))
if __name__=='__main__':unittest.main()

class VerificationRegressionTests(unittest.TestCase):
 def test_drc_includes_unconnected_and_schematic_parity(self):
  counts=w.drc_counts({'violations':[],'unconnected_items':[{'a':1}],'schematic_parity':[{'b':2}]})
  self.assertEqual(sum(counts.values()),2)
 def test_validation_fingerprint_includes_rules_and_schematic(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[Path(d)/name for name in ['board','project','rules','schematic','erc_project']]
   for p in paths:p.write_text('original')
   first=w.validation_fingerprint(*paths)
   for p in paths:
    p.write_text('changed');self.assertNotEqual(first,w.validation_fingerprint(*paths));p.write_text('original')
 def test_changed_brief_does_not_claim_ecg_requirements(self):
  import mission_constraints as m
  brief={'text':'Build an EEG device worn on the head with a strap for 8 hours.','revision':'eeg','source':'engineer'}
  with patch.object(brief_store,'current',return_value=brief):
   data=m.view({'parts':[]})
   self.assertFalse(any('14 days' in r['requirement'] for r in data['rows']))
   self.assertFalse(any('Ag/AgCl' in r['brief_quote'] for r in data['rows']))
   self.assertTrue(any(r['id']=='brief.mount' and 'head' in r['requirement'] for r in data['rows']))
   self.assertTrue(w.inputs_stale())
