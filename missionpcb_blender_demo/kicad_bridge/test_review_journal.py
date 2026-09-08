"""Persistent user review data; tests never touch the demo journal."""
import importlib
import math
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import review_journal as journal
except ImportError:
    journal = None


class ReviewJournalTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(journal, 'review journal implementation is missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.previous_root = journal.STORAGE_ROOT
        journal.STORAGE_ROOT = Path(self.tmp.name)
        self.addCleanup(setattr, journal, 'STORAGE_ROOT', self.previous_root)

    def test_comment_preserves_exact_text_and_audit(self):
        text = '  Keep U2 here. <script>ignored</script>\nSecond line.  '
        comment = journal.add_comment('board-a', 'thermal:U2', text)
        state = journal.get_state('board-a')
        self.assertEqual(state['comments'], [comment])
        self.assertEqual(comment['text'], text)
        self.assertEqual(comment['finding_id'], 'thermal:U2')
        self.assertEqual(state['events'][0]['kind'], 'comment_added')
        self.assertEqual(state['events'][0]['payload']['comment_id'], comment['id'])

    def test_pin_state_changes_retain_history(self):
        first = journal.set_pin('board-a', 'U2', True)
        journal.set_pin('board-a', 'U2', False)
        state = journal.get_state('board-a')
        self.assertEqual(state['pins'], {'U2': False})
        self.assertEqual(first['payload'], {'ref': 'U2', 'pinned': True})
        self.assertEqual(len(state['events']), 2)

    def test_board_isolation_and_disk_persistence(self):
        journal.add_comment('/boards/a.kicad_pcb', 'fit', 'Move capacitor')
        journal.set_pin('/boards/b.kicad_pcb', 'C1', True)
        module = importlib.reload(journal)
        module.STORAGE_ROOT = Path(self.tmp.name)
        self.assertEqual(len(module.get_state('/boards/a.kicad_pcb')['comments']), 1)
        self.assertEqual(module.get_state('/boards/a.kicad_pcb')['pins'], {})
        self.assertEqual(module.get_state('/boards/b.kicad_pcb')['comments'], [])

    def test_event_payload_is_detached(self):
        payload = {'before': {'x': 10}, 'after': {'x': 12}}
        event = journal.append_event('board-a', 'component_moved', payload)
        payload['after']['x'] = 900
        self.assertEqual(event['payload']['after']['x'], 12)
        event['payload']['after']['x'] = 100
        self.assertEqual(journal.get_state('board-a')['events'][0]['payload']['after']['x'], 12)

    def test_invalid_requests_write_nothing(self):
        calls = [
            lambda: journal.add_comment('', 'fit', 'hello'),
            lambda: journal.add_comment('a', '', 'hello'),
            lambda: journal.add_comment('a', 'fit', '  '),
            lambda: journal.add_comment('a', 'fit', 'x' * 10001),
            lambda: journal.set_pin('a', '../U2', True),
            lambda: journal.set_pin('a', 'U2', 1),
            lambda: journal.append_event('a', '', {}),
            lambda: journal.append_event('a', 'change', []),
            lambda: journal.append_event('a', 'change', {'x': math.nan}),
            lambda: journal.append_event('a', 'change', {'x': object()}),
        ]
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()
        self.assertEqual(journal.get_state('a'), {'comments': [], 'pins': {}, 'events': []})

    def test_concurrent_writes_are_not_lost(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            records = list(executor.map(lambda i: journal.add_comment('a', 'fit', str(i)), range(40)))
        state = journal.get_state('a')
        self.assertEqual(len(state['comments']), 40)
        self.assertEqual(len(state['events']), 40)
        self.assertEqual(len({r['id'] for r in records}), 40)

    def test_separate_process_writes_are_not_lost(self):
        script = """import sys
from pathlib import Path
import review_journal as j
j.STORAGE_ROOT = Path(sys.argv[1])
for i in range(12):
    j.append_event('shared', 'check', {'index': i})
"""
        workers = [subprocess.Popen([sys.executable, '-c', script, self.tmp.name],
                                   cwd=Path(journal.__file__).parent)
                   for _ in range(3)]
        for worker in workers:
            self.assertEqual(worker.wait(timeout=15), 0)
        state = journal.get_state('shared')
        self.assertEqual(len(state['events']), 36)
        self.assertEqual(len({event['id'] for event in state['events']}), 36)

    def test_corrupt_storage_is_not_silently_discarded(self):
        journal.add_comment('a', 'fit', 'preserve')
        path = next(Path(self.tmp.name).glob('*.json'))
        path.write_text('{broken')
        with self.assertRaises(ValueError):
            journal.add_comment('a', 'fit', 'new')
        self.assertEqual(path.read_text(), '{broken')


if __name__ == '__main__':
    unittest.main()
