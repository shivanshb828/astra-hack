import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "missionpcb_review"))

import design_context
from board_profile import component_map, support_parts
from layout_adapter import payload_for

ROOT = Path(__file__).resolve().parents[2]


def fixture(mapping):
    return {'parts': [{'ref': ref, 'x_mm': 110, 'y_mm': 120, 'rotation_deg': 0}
                      for ref in mapping]}


class DesignContextTests(unittest.TestCase):
    def test_all_catalog_data_and_dynamic_mapping_preserved(self):
        source = json.loads((ROOT / 'missionpcb_review/native-six-parts.json').read_text())
        by_id = {part['id']: part for part in source['parts']}
        context = design_context.get_context()
        self.assertEqual({p['ref']: (p['role'], p['part_id']) for p in context['parts']}, component_map())
        for part in context['parts']:
            self.assertEqual(part['catalog'], by_id.get(part['part_id'], {}))
        json.dumps(context, allow_nan=False)

    def test_unknown_fields_and_approximate_status(self):
        context = design_context.get_context()
        for part in context['parts']:
            self.assertEqual(part['unknown_fields']['thermal.theta_ja'], 'unknown')
            self.assertIn('electrical.v_in_range', part['unknown_fields'])
            self.assertIn('sensitivity.input_referred_noise', part['unknown_fields'])
            self.assertIn('notes.datasheet_citations', part['unknown_fields'])
        parts = {part['ref']: part for part in context['parts']}
        self.assertTrue(parts['U2']['approximate'])
        self.assertTrue(parts['U4']['approximate'])
        self.assertIn('connector', parts['J1']['model_status'])

    def test_constraints_match_current_layout_adapter(self):
        source = payload_for(fixture(component_map()))
        context = design_context.get_context()
        self.assertEqual(context['mission'], source['brief'])
        for field in ('board', 'enclosure', 'mission_rules', 'distance_metric'):
            self.assertEqual(context['constraints'][field], source['layout'][field])
        self.assertIn('authored', context['constraints']['provenance']['basis'].lower())
        for support in support_parts():
            self.assertIn('support_' + support['ref'], [rule['id'] for rule in context['constraints']['mission_rules']])

    def test_support_manifest_and_missing_catalog_are_explicit(self):
        mapping = {**component_map(), 'L99': ('L99', 'pending_inductor')}
        support = {'ref': 'L99', 'engine_ref': 'L99', 'part_id': 'pending_inductor',
                   'anchor_ref': 'U4', 'offset_mm': [2, 0], 'model_status': 'missing', 'value': 'TBD'}
        with patch.object(design_context, 'component_map', return_value=mapping), \
             patch.object(design_context, 'support_parts', return_value=[support]), \
             patch('layout_adapter.component_map', return_value=mapping), \
             patch('layout_adapter.support_parts', return_value=[support]):
            part = next(p for p in design_context.get_context()['parts'] if p['ref'] == 'L99')
        self.assertEqual(part['support_manifest'], support)
        self.assertEqual(part['catalog'], {})
        self.assertEqual(part['catalog_status'], 'missing')
        self.assertIn('TBD', part['model_status'])
        self.assertIn('missing', part['model_status'])

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
