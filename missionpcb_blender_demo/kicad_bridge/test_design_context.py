import ast
import json
import sys
import unittest
from pathlib import Path

try:
    import design_context
except ImportError:
    design_context = None

ROOT = Path(__file__).resolve().parents[2]


class DesignContextTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(design_context, 'offline design context implementation missing')

    def test_all_catalog_data_is_preserved_exactly(self):
        source = json.loads((ROOT / 'missionpcb_review/native-six-parts.json').read_text())
        context = design_context.get_context()
        self.assertEqual([p['catalog'] for p in context['parts']], source['parts'])
        self.assertEqual([p['ref'] for p in context['parts']], ['U1', 'U2', 'U3', 'U4', 'U5', 'J1'])
        json.dumps(context, allow_nan=False)
        native_tree = ast.parse((ROOT / 'missionpcb_blender_demo/kicad_bridge/native_review.py').read_text())
        mapping = next(ast.literal_eval(node.value) for node in native_tree.body
                       if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                       and target.id == 'MAP' for target in node.targets))
        self.assertEqual({p['ref']: (p['role'], p['part_id']) for p in context['parts']}, mapping)

    def test_unknown_fields_do_not_become_claimed_properties(self):
        context = design_context.get_context()
        for part in context['parts']:
            self.assertIn('thermal.theta_ja', part['unknown_fields'])
            self.assertIn('electrical.v_in_range', part['unknown_fields'])
            self.assertIn('sensitivity.input_referred_noise', part['unknown_fields'])
            self.assertIn('notes.datasheet_citations', part['unknown_fields'])
            self.assertEqual(part['unknown_fields']['thermal.theta_ja'], 'unknown')
        self.assertEqual([p['ref'] for p in context['parts'] if p['approximate']], ['U2', 'U4'])
        self.assertIn('connector', context['parts'][-1]['model_status'])

    def test_constraints_match_current_layout_adapter(self):
        tree = ast.parse((ROOT / 'missionpcb_review/layout_adapter.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'payload_for')
        import time
        namespace = {'MAP': {}, 'time': time}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'layout_adapter.py', 'exec'), namespace)
        source = namespace['payload_for']({'parts': []})
        context = design_context.get_context()
        self.assertEqual(context['mission'], source['brief'])
        self.assertEqual(context['constraints']['board'], source['layout']['board'])
        self.assertEqual(context['constraints']['enclosure'], source['layout']['enclosure'])
        self.assertEqual(context['constraints']['mission_rules'], source['layout']['mission_rules'])
        self.assertIn('authored', context['constraints']['provenance']['basis'].lower())

    def test_no_native_connection_needed_and_results_detached(self):
        before = set(sys.modules)
        first = design_context.get_context()
        first['parts'][0]['catalog']['name'] = 'changed'
        second = design_context.get_context()
        self.assertNotEqual(second['parts'][0]['catalog']['name'], 'changed')
        self.assertNotIn('kipy', set(sys.modules) - before)
        self.assertNotIn('bridge', set(sys.modules) - before)
        self.assertIn('cached', second['mode'].lower())
        self.assertTrue(any('netlist' in item for item in second['limitations']))


if __name__ == '__main__':
    unittest.main()
