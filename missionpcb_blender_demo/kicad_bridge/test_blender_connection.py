"""Regression checks for stale Blender sessions and reconnecting safely."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import blender_handoff as pipeline

class BlenderConnectionTests(unittest.TestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
  self.root=Path(temp.name)
  for key in ('IPC','SESSIONS'):
   p=patch.object(pipeline,key,self.root);p.start();self.addCleanup(p.stop)
 def state(self,**updates):
  value=dict(heartbeat=pipeline.time.time(),assembly_api=1,session='current',assembly={'findings':[{'status':'PASS'}]})
  value.update(updates);(self.root/'state.json').write_text(json.dumps(value));return value
 def test_disconnected_state_drops_stale_checks(self):
  self.state(heartbeat=pipeline.time.time()-60)
  result=pipeline.state();self.assertFalse(result['connected']);self.assertNotIn('assembly',result)
 def test_adapter_error_drops_stale_checks(self):
  self.state(error='Wrong scene')
  result=pipeline.state();self.assertFalse(result['connected']);self.assertEqual(result['error'],'Wrong scene');self.assertNotIn('assembly',result)
 def test_changed_scene_rejected_before_queue(self):
  self.state()
  with self.assertRaisesRegex(ValueError,'scene changed'):pipeline.dispatch('assembly_check',expected_session='previous')
  self.assertFalse((self.root/'command.json').exists())
 def test_command_bound_to_observed_session(self):
  self.state()
  def respond(_):
   command=json.loads((self.root/'command.json').read_text());self.assertEqual(command['session'],'current')
   (self.root/(command['id']+'.json')).write_text(json.dumps({'ok':True,'message':'checked'}))
  with patch.object(pipeline.time,'sleep',side_effect=respond):self.assertTrue(pipeline.dispatch('assembly_check')['ok'])
 def test_reopen_connected_session_does_not_spawn_duplicate(self):
  self.state()
  with patch.object(pipeline.subprocess,'Popen') as spawn,patch.object(pipeline.subprocess,'run'):
   self.assertTrue(pipeline.open_session()['ok']);spawn.assert_not_called()
 def test_reopen_uses_newest_saved_assembly_and_waits_for_its_adapter(self):
  folder=self.root/'session';folder.mkdir();saved=folder/'assembly.blend';saved.write_bytes(b'fixture')
  process=Mock(pid=123);process.poll.return_value=None
  def connected(_):self.state(pid=123)
  with patch.object(pipeline.subprocess,'Popen',return_value=process) as spawn,patch.object(pipeline.subprocess,'run'),patch.object(pipeline.time,'sleep',side_effect=connected):
   self.assertTrue(pipeline.open_session()['ok'])
  self.assertEqual(spawn.call_args.args[0],[pipeline.BLENDER,str(saved),'--python',str(pipeline.PIPELINE/'addon.py')])
 def test_no_saved_assembly_has_actionable_error(self):
  with self.assertRaisesRegex(ValueError,'Confirm a KiCad board'):pipeline.open_session()

if __name__=='__main__':unittest.main()
