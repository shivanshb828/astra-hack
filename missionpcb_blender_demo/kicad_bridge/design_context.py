"""Offline dashboard context for the existing six-component demonstration.

Values are cached library data and authored placement policies, not a live CAD
snapshot or datasheet extraction. The tests compare policies with layout_adapter.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBRARY_PATH = ROOT / 'missionpcb_review' / 'native-six-parts.json'
PART_REFS = {
    'msp430fr2433': ('U1', 'MCU'),
    'ads1292r': ('U2', 'Sensor'),
    'mdbt42q': ('U3', 'RF'),
    'tps62740': ('U4', 'Regulator'),
    'mcp73831': ('U5', 'Driver'),
    'bm02b_srss': ('J1', 'Battery'),
}
UNKNOWN_FIELDS = (
    'mechanical.package', 'mechanical.thermal_pad',
    'thermal.theta_ja', 'thermal.copper_condition', 'thermal.t_op_range',
    'thermal.t_j_max', 'thermal.dissipation_model',
    'electrical.v_in_range', 'electrical.i_typ', 'electrical.i_max',
    'electrical.i_quiescent', 'electrical.operating_conditions',
    'emi.switching_freq', 'emi.is_switching',
    'sensitivity.input_referred_noise', 'sensitivity.susceptibility_notes',
    'notes.datasheet_citations',
)


def get_context():
    """Return fresh JSON data for parts, authored constraints, and coverage limits."""
    library = json.loads(LIBRARY_PATH.read_text(encoding='utf-8'))
    parts = []
    for raw in library['parts']:
        ref, role = PART_REFS[raw['id']]
        approximate = ref in ('U2', 'U4')
        status = 'Approximate package model; exact package verification required' if approximate else 'Cached representative CAD dimensions; exact package verification incomplete'
        if ref == 'J1':
            status = 'Battery connector model only; no battery cell model or battery safety validation'
        parts.append({
            'ref': ref, 'role': role, 'part_id': raw['id'], 'catalog': raw,
            'approximate': approximate, 'model_status': status,
            'unknown_fields': {field: 'unknown' for field in UNKNOWN_FIELDS},
            'safety_fields': {'isolation_v': None, 'creepage': None,
                              'status': 'Not provided; these isolator-specific fields are not assessed'},
            'provenance': {'source': 'missionpcb_review/native-six-parts.json',
                           'basis': 'Cached representative dimensions and authored clearance proxies',
                           'notes': list(library.get('notes', []))},
        })
    constraints = {
        'distance_metric': 'center',
        'board': {'id': 'MissionPCB', 'size_mm': {'length': 72, 'width': 38, 'thickness': 1.6},
                  'origin_mm': [9, 6, 2], 'edge_margin_mm': 1,
                  'max_component_height_mm': 6.4, 'min_component_gap_mm': 0.5},
        'enclosure': {'interior_mm': {'length': 90, 'width': 50, 'height': 10}, 'wall_keepout_mm': 0},
        'mission_rules': [
            {'id': 'afe_' + role, 'type': 'min_separation', 'between': ['Sensor', role],
             'distance_mm': distance, 'metric': 'center',
             'rationale': 'Authored demo policy, not solved physics.'}
            for role, distance in [('MCU', 18), ('RF', 20), ('Regulator', 20)]
        ],
        'part_proxies': [
            {'ref': part['ref'], 'part_id': part['part_id'],
             'heat_zone_radius_mm': part['catalog'].get('heat_zone_radius_mm'),
             'keepout': part['catalog'].get('keepout'),
             'basis': 'Authored demo clearance proxy, not a datasheet-derived system result'}
            for part in parts
            if part['catalog'].get('heat_zone_radius_mm') is not None or part['catalog'].get('keepout') is not None
        ],
        'provenance': {'source': 'missionpcb_review/layout_adapter.py:payload_for',
                       'part_source': 'missionpcb_review/native-six-parts.json',
                       'basis': 'Fixed authored demonstration policies; no solved thermal or EMI model',
                       'geometry_source': 'Fixed demo board and enclosure, not measured from the active board'},
    }
    return {
        'mission': 'ECG chest patch. Review current six-component placement against authored demo spacing policies.',
        'mode': 'Cached six-part demonstration context; no live model call or CAD connection',
        'parts': parts,
        'constraints': constraints,
        'limitations': [
            'This context describes the canonical six-part MissionPCB demo, not any newly opened KiCad project.',
            'No complete schematic, netlist, routing, or ERC validation is represented here.',
            'U2 and U4 use approximate packages; all cached dimensions still require exact package verification.',
            'Heat radii, keepouts, and separation thresholds are authored placement proxies, not solved temperature or EMI results.',
            'Thermal, electrical, noise, and datasheet citation fields listed as unknown are not populated by this library.',
            'J1 is a connector, not a battery cell; electrodes and patient-contact protection are not fully modeled.',
            'Placement rule results do not establish clinical safety or fabrication readiness.',
        ],
    }
