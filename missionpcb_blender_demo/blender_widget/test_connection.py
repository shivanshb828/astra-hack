"""Adapter ownership and scene identity regression tests, without live IPC."""
import json
import types,unittest
from unittest.mock import Mock,patch
import test_adapter

class ConnectionTests(unittest.TestCase):
 def setUp(self):
  test_adapter.AdapterTests.setUp(self)
  class Scene(dict):
   def as_pointer(self):return 10
  self.bpy.context.scene=Scene(missionpcb_assembly=True)
  self.bpy.app=types.SimpleNamespace(driver_namespace={},timers=Mock(),handlers=types.SimpleNamespace(load_post=[],persistent=lambda f:f))
  self.bpy.app.timers.is_registered.return_value=False
 def test_timer_survives_file_load(self):
  with patch.object(self.addon,'snapshot',return_value={}):self.addon.start()
  self.assertTrue(self.bpy.app.timers.register.call_args.kwargs['persistent'])
 def test_same_file_reload_rotates_session_even_if_scene_pointer_reused(self):
  old=self.addon.connection()['session'];self.addon.file_loaded(None)
  self.assertNotEqual(self.addon.connection()['session'],old)
 def test_file_change_rejects_old_scene_command(self):
  old=self.addon.connection()['session']
  self.addon.OWNER='owner';(self.ipc/'owner').write_text('owner')
  self.bpy.data.filepath='/another.blend'
  command=dict(id='e'*32,action='assembly_check',session=old,created=self.addon.time.time())
  (self.ipc/'command.json').write_text(json.dumps(command))
  with patch.object(self.addon,'execute') as execute,patch.object(self.addon,'snapshot',return_value={}):
   self.assertEqual(self.addon.tick(),.75);execute.assert_not_called()
  reply=json.loads((self.ipc/('e'*32+'.json')).read_text());self.assertFalse(reply['ok']);self.assertIn('scene changed',reply['message'])
 def test_new_adapter_retires_old_without_consuming_queue(self):
  self.addon.OWNER='old';(self.ipc/'owner').write_text('new')
  pending=self.ipc/'command.json';pending.write_text('{}')
  self.assertIsNone(self.addon.tick());self.assertTrue(pending.exists())
