"""Exercise review lifecycle and pinned move guards without changing KiCad."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import bridge
import review_journal
import widget_command

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.storage=patch.object(review_journal,'STORAGE_ROOT',Path(self.tmp.name));self.storage.start()
  self.addCleanup(self.tmp.cleanup);self.addCleanup(self.storage.stop)
  self.flags=patch.object(widget_command,'refresh_native_flags_after_move',return_value='Native flags refreshed.');self.flags_mock=self.flags.start();self.addCleanup(self.flags.stop)
 def test_resolved_and_reopened_finding_retains_comment(self):
  finding={'id':'heat-U2-U5','status':'FAIL','kicad_refs':['U2','U5'],'message':'Separation below authored policy'}
  widget_command.record_review([finding],{'FAIL':1},'a')
  review_journal.add_comment(str(bridge.TARGET),finding['id'],'Keep electrode access clear')
  widget_command.record_review([],{'FAIL':0},'b')
  event=widget_command.record_review([finding],{'FAIL':1},'c')
  self.assertEqual(event['payload']['reopened'],[finding['id']])
  state=review_journal.get_state(str(bridge.TARGET))
  reviews=[e for e in state['events'] if e['kind']=='engine_review']
  self.assertEqual(reviews[1]['payload']['resolved'],[finding['id']])
  self.assertEqual(state['comments'][0]['text'],'Keep electrode access clear')
 def test_pin_blocks_native_move_and_unpin_records_before_after(self):
  before={'board':str(bridge.TARGET),'revision':'a','parts':[{'ref':'U1','x_mm':136,'y_mm':129,'rotation_deg':0}]}
  after=copy.deepcopy(before);after['revision']='b';after['parts'][0]['x_mm']=138
  with patch.object(bridge,'connect'),patch.object(bridge,'snapshot',return_value=before),patch.object(bridge,'apply',return_value={'before':before,'after':after}) as apply:
   review_journal.set_pin(str(bridge.TARGET),'U1',True)
   with self.assertRaisesRegex(ValueError,'Pinned'):widget_command.run('Move U1 2 mm right')
   apply.assert_not_called()
   review_journal.set_pin(str(bridge.TARGET),'U1',False)
   self.assertIn('Applied and verified',widget_command.run('Move U1 2 mm right'))
   event=review_journal.get_state(str(bridge.TARGET))['events'][-1]
   self.assertEqual(event['kind'],'design_change');self.assertEqual(event['payload']['before'],before)
   self.assertEqual(event['payload']['after'],after)
   self.flags_mock.assert_called_once()
 def test_journal_failure_after_move_reports_actual_native_outcome(self):
  before={'board':str(bridge.TARGET),'revision':'a','parts':[{'ref':'U1','x_mm':136,'y_mm':129,'rotation_deg':0}]}
  with patch.object(bridge,'connect'),patch.object(bridge,'snapshot',return_value=before),patch.object(bridge,'apply',return_value={'before':before,'after':before}) as apply,patch.object(review_journal,'append_event',side_effect=OSError('disk full')):
   with self.assertRaisesRegex(RuntimeError,'native component move succeeded'):
    widget_command.run('Move U1 2 mm right')
   apply.assert_called_once()
if __name__=='__main__':unittest.main()
