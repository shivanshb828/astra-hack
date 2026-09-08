"""Isolated adapter contract tests; never contacts Blender or the live IPC folder."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ipc = Path(self.tmp.name)
        self.client = load_module('widget_client_test', ROOT.parent / 'kicad_bridge/blender_command.py')
        self.client.IPC = self.ipc
        self.bpy = types.SimpleNamespace(
            data=types.SimpleNamespace(filepath='/unrelated/Other.blend'),
            context=types.SimpleNamespace(scene={'use_upstream_engine': True}),
        )
        with patch.dict(sys.modules, {'bpy': self.bpy}):
            self.addon = load_module('widget_addon_test', ROOT / 'addon.py')
        self.addon.IPC = self.ipc

    def state(self, **updates):
        state = {'heartbeat': self.client.time.time(), 'stale': False, 'result': {}}
        state.update(updates)
        (self.ipc / 'state.json').write_text(json.dumps(state))

    def test_missing_adapter_rejected_without_queue(self):
        with self.assertRaisesRegex(ValueError, 'not running'):
            self.client.run('inspect')
        self.assertFalse((self.ipc / 'command.json').exists())

    def test_disconnected_heartbeat_rejected_without_queue(self):
        self.state(heartbeat=self.client.time.time() - 60)
        with self.assertRaisesRegex(ValueError, 'disconnected|busy'):
            self.client.run('check')
        self.assertFalse((self.ipc / 'command.json').exists())

    def test_scene_error_propagated_without_queue(self):
        self.state(error='Open the canonical MissionPCB scene first')
        with self.assertRaisesRegex(ValueError, 'canonical'):
            self.client.run('check')
        self.assertFalse((self.ipc / 'command.json').exists())

    def test_unknown_command_never_queued(self):
        self.state()
        message = self.client.run('execute arbitrary python')
        self.assertIn('supports', message)
        self.assertFalse((self.ipc / 'command.json').exists())

    def test_unknown_focus_never_queued(self):
        self.state()
        with self.assertRaisesRegex(ValueError, 'focus'):
            self.client.run('focus unrelated')
        self.assertFalse((self.ipc / 'command.json').exists())

    def test_pending_command_preserved(self):
        self.state()
        pending = self.ipc / 'command.json'
        pending.write_text('{"existing": true}')
        with self.assertRaisesRegex(ValueError, 'pending'):
            self.client.run('check')
        self.assertEqual(pending.read_text(), '{"existing": true}')

    def test_wrong_scene_rejected_before_runtime_access(self):
        with self.assertRaisesRegex(ValueError, 'canonical'):
            self.addon.execute({'action': 'check'})

    def test_missing_engine_rejected(self):
        self.bpy.data.filepath = str(self.addon.TARGET)
        self.bpy.context.scene = {}
        with self.assertRaisesRegex(ValueError, 'engine'):
            self.addon.guard()

    def test_unknown_addon_action_rejected(self):
        self.bpy.data.filepath = str(self.addon.TARGET)
        with patch.object(self.addon, 'runtime', return_value=object()):
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                self.addon.execute({'action': 'arbitrary'})

    def test_expired_command_not_executed(self):
        command = {'id': 'a' * 32, 'created': self.client.time.time() - 60, 'action': 'check'}
        (self.ipc / 'command.json').write_text(json.dumps(command))
        with patch.object(self.addon, 'execute') as execute:
            self.assertEqual(self.addon.tick(), .75)
            execute.assert_not_called()
        reply = json.loads((self.ipc / (command['id'] + '.json')).read_text())
        self.assertFalse(reply['ok'])
        self.assertIn('Expired', reply['message'])
        self.assertFalse((self.ipc / 'command.json').exists())

    def test_malformed_queue_does_not_stop_timer(self):
        (self.ipc / 'command.json').write_text('{broken')
        self.assertEqual(self.addon.tick(), .75)
        self.assertFalse((self.ipc / 'command.json').exists())
        self.assertTrue((self.ipc / 'last_error.json').exists())

    def test_invalid_id_cannot_escape_ipc(self):
        command = {'id': '../escape', 'created': self.client.time.time(), 'action': 'check'}
        (self.ipc / 'command.json').write_text(json.dumps(command))
        with patch.object(self.addon, 'execute') as execute:
            self.assertEqual(self.addon.tick(), .75)
            execute.assert_not_called()
        self.assertTrue((self.ipc / 'last_error.json').exists())

    def test_invalid_timestamps_rejected(self):
        for created in (True, float('nan'), float('inf'), self.client.time.time() + 60, 'now'):
            with self.subTest(created=created):
                command = {'id': 'b' * 32, 'created': created, 'action': 'check'}
                (self.ipc / 'command.json').write_text(json.dumps(command))
                with patch.object(self.addon, 'execute') as execute:
                    self.assertEqual(self.addon.tick(), .75)
                    execute.assert_not_called()
                self.assertFalse(json.loads((self.ipc / ('b' * 32 + '.json')).read_text())['ok'])

    def command_reply(self, state):
        command = json.loads((self.ipc / 'command.json').read_text())
        (self.ipc / (command['id'] + '.json')).write_text(json.dumps({
            'ok': True, 'message': 'Inspected.', 'state': state,
        }))

    def test_stale_scene_counts_are_not_reported(self):
        self.state()
        with patch.object(self.client.time, 'sleep', side_effect=lambda _: self.command_reply({
            'stale': True, 'result': {'summary': {'pass': 999}},
        })):
            message = self.client.run('inspect')
        self.assertIn('stale', message)
        self.assertNotIn('999', message)

    def test_ack_snapshot_wins_over_old_state_file(self):
        self.state(result={'summary': {'pass': 999}})
        with patch.object(self.client.time, 'sleep', side_effect=lambda _: self.command_reply({
            'stale': False, 'result': {'summary': {'pass': 26}},
        })):
            message = self.client.run('inspect')
        self.assertIn('26', message)
        self.assertNotIn('999', message)

    def test_success_ack_contains_completed_snapshot(self):
        command = {'id': 'c' * 32, 'created': self.client.time.time(), 'action': 'inspect'}
        (self.ipc / 'command.json').write_text(json.dumps(command))
        current = {'heartbeat': self.client.time.time(), 'stale': False, 'result': {'summary': {'pass': 26}}}
        with patch.object(self.addon, 'execute', return_value='Inspected.'), patch.object(self.addon, 'snapshot', return_value=current):
            self.assertEqual(self.addon.tick(), .75)
        reply = json.loads((self.ipc / (command['id'] + '.json')).read_text())
        self.assertTrue(reply['ok'])
        self.assertEqual(reply['state'], current)


if __name__ == '__main__':
    unittest.main()
