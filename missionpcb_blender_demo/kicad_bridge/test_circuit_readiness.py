"""Electrical readiness is backed by saved KiCad data, never placement geometry."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import circuit_readiness as circuit

SCHEMATIC = b'(kicad_sch (version 20250114) (generator eeschema))'
NETLIST = b'''<?xml version="1.0"?><export><components>
<comp ref="U1"/><comp ref="R1"/></components><nets>
<net code="1" name="/SIGNAL"><node ref="U1" pin="1"/><node ref="R1" pin="1"/></net>
<net code="2" name="GND"><node ref="U1" pin="2"/><node ref="R1" pin="2"/></net>
</nets></export>'''


def board_snapshot():
    return {'footprints': [{'ref': 'U1', 'value': 'IC'}, {'ref': 'R1', 'value': '10k'}],
            'pads': [{'ref': ref, 'pin': pin, 'net': net, 'electrical': True}
                     for ref in ('U1', 'R1') for pin, net in (('1', '/SIGNAL'), ('2', 'GND'))],
            'tracks': 0, 'vias': 0, 'zones': 0, 'unconnected': 2}


class CircuitReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.board = self.root / 'Board.kicad_pcb'
        self.board.write_text('(kicad_pcb)')
        self.snapshot = board_snapshot()
        for mocked in (patch.object(circuit, 'STORAGE_ROOT', self.root / 'runtime'),
                       patch.object(circuit, '_probe_board', side_effect=lambda path: copy.deepcopy(self.snapshot)),
                       patch.object(circuit, '_run_netlist', return_value=NETLIST)):
            mocked.start()
            self.addCleanup(mocked.stop)
        circuit.clear_cache()

    def test_missing_schematic_and_zero_nets_cannot_pass(self):
        for pad in self.snapshot['pads']:
            pad['net'] = ''
        self.snapshot['unconnected'] = 0
        state = circuit.view(self.board)
        self.assertEqual(state['coverage']['named_nets'], 0)
        self.assertEqual(state['coverage']['unassigned_pads'], 4)
        self.assertFalse(state['readiness']['connectivity_verified'])
        self.assertEqual(state['schematic']['status'], 'missing')
        self.assertEqual(state['status'], 'blocked')
        self.assertTrue(any('no electrical nets' in item.lower() for item in state['blockers']))

    def test_matching_schematic_verifies_connectivity_but_not_routing(self):
        state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        self.assertEqual(state['schematic']['status'], 'matched')
        self.assertTrue(state['readiness']['connectivity_verified'])
        self.assertFalse(state['readiness']['routing_available'])
        self.assertFalse(state['readiness']['electrical_signoff'])
        self.assertEqual(state['coverage']['connected_pads'], 4)
        self.assertEqual(state['coverage']['unconnected'], 2)

    def test_swapped_pin_nets_and_missing_references_block_matching(self):
        self.snapshot['pads'][0]['net'] = 'GND'
        self.snapshot['footprints'].append({'ref': 'J1', 'value': 'Connector'})
        state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        comparison = state['schematic']['comparison']
        self.assertEqual(state['schematic']['status'], 'mismatch')
        self.assertEqual(comparison['board_only_refs'], ['J1'])
        self.assertEqual(comparison['pin_net_mismatches'][0]['ref'], 'U1')
        self.assertFalse(state['readiness']['connectivity_verified'])

    def test_duplicate_reference_and_unassigned_pin_are_not_ignored(self):
        self.snapshot['footprints'].append({'ref': 'U1', 'value': 'Duplicate'})
        self.snapshot['pads'].append({'ref': 'U1', 'pin': '3', 'net': '', 'electrical': True})
        state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        self.assertEqual(state['schematic']['status'], 'mismatch')
        self.assertEqual(state['schematic']['comparison']['duplicate_board_refs'], ['U1'])
        self.assertTrue(state['schematic']['comparison']['board_only_pins'])

    def test_explicit_mechanical_board_only_parts_do_not_block_electrical_match(self):
        self.snapshot['footprints'].append({'ref': 'MH1', 'value': 'Mount', 'board_only': True})
        self.snapshot['pads'].append({'ref': 'MH1', 'pin': '', 'net': '', 'electrical': False})
        state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        self.assertEqual(state['schematic']['status'], 'matched')
        self.assertEqual(state['schematic']['comparison']['ignored_mechanical_refs'], ['MH1'])

    def test_kicad_escaped_slash_net_names_match_exported_netlist(self):
        for pad in self.snapshot['pads']:
            if pad['net'] == '/SIGNAL':
                pad['net'] = '/DATA{slash}CLK'
        with patch.object(circuit, '_run_netlist', return_value=NETLIST.replace(b'/SIGNAL', b'/DATA/CLK')):
            state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        self.assertEqual(state['schematic']['status'], 'matched')

    def test_erc_project_settings_snapshot_does_not_follow_later_changes(self):
        self.board.with_suffix('.kicad_sch').write_bytes(SCHEMATIC)
        settings = self.board.with_suffix('.kicad_pro')
        settings.write_text('{"erc":{"rule_severities":{"pin_to_pin":"error"}}}')
        original = circuit.get_erc_source(self.board)
        original_settings = original.with_suffix('.kicad_pro').read_bytes()
        settings.write_text('{}')
        updated = circuit.get_erc_source(self.board)
        self.assertNotEqual(original, updated)
        self.assertEqual(original.with_suffix('.kicad_pro').read_bytes(), original_settings)

    def test_explicit_no_connect_evidence_distinguishes_unused_from_unwired_pins(self):
        self.snapshot['pads'].append({'ref': 'U1', 'pin': '3', 'net': 'unconnected-(U1-Pad3)', 'electrical': True})
        xml = NETLIST.replace(b'</nets>', b'<net name="unconnected-(U1-Pad3)"><node ref="U1" pin="3" pintype="input+no_connect"/></net></nets>')
        with patch.object(circuit, '_run_netlist', return_value=xml):
            state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        self.assertTrue(state['readiness']['connectivity_verified'])
        self.assertEqual(state['coverage']['no_connect_pads'], 1)
        self.assertEqual(state['coverage']['unresolved_pads'], 0)

    def test_no_connect_pin_on_functional_net_remains_a_conflict(self):
        xml = NETLIST.replace(b'<node ref="U1" pin="1"/>', b'<node ref="U1" pin="1" pintype="no_connect"/>')
        with patch.object(circuit, '_run_netlist', return_value=xml):
            state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        self.assertFalse(state['readiness']['connectivity_verified'])
        self.assertEqual(state['schematic']['comparison']['no_connect_net_conflicts'], [{'ref': 'U1', 'pin': '1'}])

    def test_upload_rejects_paths_hierarchy_size_and_invalid_document(self):
        cases = [('../Board.kicad_sch', SCHEMATIC), ('Board.txt', SCHEMATIC),
                 ('Board.kicad_sch', b'(kicad_sch (sheet (property "Sheetfile" "other.kicad_sch")))'),
                 ('Board.kicad_sch', b'(kicad_sch'), ('Board.kicad_sch', b'(kicad_pcb)'),
                 ('Board.kicad_sch', b'x' * (circuit.MAX_SCHEMATIC_BYTES + 1))]
        for name, content in cases:
            with self.subTest(name=name, content=content[:30]), self.assertRaises(ValueError):
                circuit.attach_schematic(name, content, self.board)
        self.assertIsNone(circuit.get_erc_source(self.board))

    def test_erc_source_is_immutable_copy_and_board_scoped(self):
        source = self.board.with_suffix('.kicad_sch')
        source.write_bytes(SCHEMATIC)
        immutable = circuit.get_erc_source(self.board)
        self.assertNotEqual(immutable, source)
        source.write_bytes(SCHEMATIC.replace(b'eeschema', b'changed'))
        self.assertEqual(immutable.read_bytes(), SCHEMATIC)
        other = self.root / 'Other.kicad_pcb'
        other.write_bytes(b'(kicad_pcb)')
        self.assertIsNone(circuit.get_erc_source(other))

    def test_changed_board_rechecks_attachment_and_stale_upload_is_rejected(self):
        state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        digest = state['saved_board_sha256']
        self.board.write_text('(kicad_pcb (changed))')
        self.snapshot['pads'][0]['net'] = ''
        self.assertEqual(circuit.view(self.board)['schematic']['status'], 'mismatch')
        with self.assertRaisesRegex(ValueError, 'changed'):
            circuit.attach_schematic('Next.kicad_sch', SCHEMATIC, self.board, expected_board_sha256=digest)

    def test_failed_export_preserves_previous_attachment(self):
        circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        previous = circuit.get_erc_source(self.board)
        with patch.object(circuit, '_run_netlist', side_effect=ValueError('Invalid schematic')):
            with self.assertRaises(ValueError):
                circuit.attach_schematic('Next.kicad_sch', SCHEMATIC + b'\n', self.board)
        self.assertEqual(circuit.get_erc_source(self.board), previous)

    def test_missing_board_is_unavailable_without_false_counts(self):
        self.board.unlink()
        state = circuit.view(self.board)
        self.assertEqual(state['status'], 'unavailable')
        self.assertIsNone(state['coverage'])

    def test_filled_copper_zone_counts_but_empty_zone_does_not(self):
        self.snapshot.update(zones=1, filled_zones=1, unconnected=0)
        state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        self.assertTrue(state['readiness']['has_copper'])
        self.assertFalse(state['readiness']['electrical_signoff'])
        self.snapshot['filled_zones'] = 0
        self.board.write_text('(kicad_pcb (unfilled))')
        self.assertFalse(circuit.view(self.board)['readiness']['has_copper'])

    def test_named_nets_without_pin_connections_are_not_a_circuit(self):
        self.snapshot.update(nets=['GND'], footprints=[], pads=[])
        with patch.object(circuit, '_run_netlist', return_value=b'<export><components/><nets/></export>'):
            state = circuit.attach_schematic('Board.kicad_sch', SCHEMATIC, self.board)
        self.assertEqual(state['coverage']['named_nets'], 1)
        self.assertFalse(state['readiness']['connectivity_verified'])
        self.assertEqual(state['status'], 'blocked')

    def test_xml_entities_and_unknown_nodes_are_rejected(self):
        with self.assertRaises(ValueError):
            circuit.parse_netlist(b'<!DOCTYPE x [<!ENTITY x "bad">]><export/>')
        with self.assertRaises(ValueError):
            circuit.parse_netlist(b'<export><components/><nets><net name="GND"><node ref="X" pin="1"/></net></nets></export>')


if __name__ == '__main__':
    unittest.main()
