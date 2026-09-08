"""Offline dashboard context for the registered ECG component demonstration.

Values are cached library data and authored placement policies, not a live CAD
snapshot or datasheet extraction. The tests compare policies with layout_adapter.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBRARY_PATH = ROOT / 'missionpcb_review' / 'native-six-parts.json'
if str(ROOT / 'missionpcb_review') not in sys.path:
    sys.path.insert(0, str(ROOT / 'missionpcb_review'))
from board_profile import component_map, support_parts
from layout_adapter import payload_for

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
    mapping = component_map()
    supports = {part['ref']: part for part in support_parts()}
    catalog = {part['id']: part for part in library['parts']}
    # Positions only satisfy the adapter's input contract; no synthetic placement
    # is exposed as a measured or live CAD position.
    payload = payload_for({'parts': [
        {'ref': ref, 'x_mm': 110, 'y_mm': 120, 'rotation_deg': 0} for ref in mapping
    ]})
    layout = payload['layout']
    parts = []
    for ref, (role, part_id) in mapping.items():
        raw = catalog.get(part_id, {})
        support = supports.get(ref)
        approximate = ref in ('U2', 'U4')
        status = 'Approximate package model; exact package verification required' if approximate else 'Cached representative CAD dimensions; exact package verification incomplete'
        if ref == 'J1':
            status = 'Battery connector model only; no battery cell model or battery safety validation'
        if support:
            availability = ('available' if support.get('model_available') is True
                            else 'missing' if support.get('model_available') is False
                            else support.get('model_status', 'unknown'))
            status = ('Generic supporting package; value ' + str(support.get('value', 'TBD'))
                      + '; 3D model ' + str(availability) + '. ' + str(support.get('limitation', '')))
        parts.append({
            'ref': ref, 'role': role, 'part_id': part_id, 'catalog': raw,
            'catalog_status': 'cached' if raw else 'missing',
            'support_manifest': support,
            'approximate': approximate, 'model_status': status,
            'unknown_fields': {field: 'unknown' for field in UNKNOWN_FIELDS},
            'safety_fields': {'isolation_v': None, 'creepage': None,
                              'status': 'Not provided; these isolator-specific fields are not assessed'},
            'provenance': {'source': 'missionpcb_review/native-six-parts.json',
                           'basis': 'Cached representative dimensions and authored clearance proxies',
                           'notes': list(library.get('notes', []))},
        })
    constraints = {
        **{key: layout[key] for key in ('distance_metric', 'board', 'enclosure', 'mission_rules')},
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
        'mission': payload['brief'],
        'mode': f'Cached {len(parts)}-part demonstration context; no live model call or CAD connection',
        'parts': parts,
        'constraints': constraints,
        'limitations': [
            'This context describes the canonical registered MissionPCB demo, not any newly opened KiCad project.',
            'No complete schematic, netlist, routing, or ERC validation is represented here.',
            'U2 and U4 use approximate packages; all cached dimensions still require exact package verification.',
            'Heat radii, keepouts, and separation thresholds are authored placement proxies, not solved temperature or EMI results.',
            'Thermal, electrical, noise, and datasheet citation fields listed as unknown are not populated by this library.',
            'J1 is a connector, not a battery cell; electrodes and patient-contact protection are not fully modeled.',
            'Supporting components use generic package dimensions; TBD values and missing models remain explicit in their manifests.',
            'Placement rule results do not establish clinical safety or fabrication readiness.',
        ],
    }
