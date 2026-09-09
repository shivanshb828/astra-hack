"""Saved-board electrical evidence and a verified, immutable schematic handoff.

No operation edits the PCB, assigns nets, routes copper, or marks electrical signoff.
The HTTP caller must authenticate attachment requests before calling this module.
"""
import copy
import hashlib
import json
import os
import re
import subprocess
import threading
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent
STORAGE_ROOT = ROOT / 'runtime' / 'circuits'
KICAD_PYTHON = Path('/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3')
CLI = Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
MAX_SCHEMATIC_BYTES = 8 * 1024 * 1024
MAX_NETLIST_BYTES = 40 * 1024 * 1024
_LOCK = threading.RLock()
_BOARD_CACHE = {}
_NETLIST_CACHE = {}


def clear_cache():
    with _LOCK:
        _BOARD_CACHE.clear()
        _NETLIST_CACHE.clear()


def _target(target=None):
    if target is None:
        import bridge
        target = bridge.TARGET
    return Path(target).resolve()


def _folder(target):
    return STORAGE_ROOT / hashlib.sha256(str(target).encode()).hexdigest()[:24]


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _immutable(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError('Stored source integrity check failed')
    return path


def _run(command, timeout=45):
    try:
        result = subprocess.run([str(item) for item in command], capture_output=True,
                                text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('KiCad could not inspect this saved design: ' + str(error)) from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-1500:]
        raise ValueError('KiCad could not inspect this saved design: ' + detail)
    return result.stdout


def _probe_board(path):
    return json.loads(_run([KICAD_PYTHON, ROOT / 'saved_circuit_snapshot.py', path]))


def _run_netlist(path):
    output = path.parent / ('netlist-' + uuid.uuid4().hex + '.xml')
    try:
        _run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '--output', output, path])
        if not output.is_file() or output.stat().st_size > MAX_NETLIST_BYTES:
            raise ValueError('KiCad netlist is missing or exceeds the supported size')
        return output.read_bytes()
    finally:
        output.unlink(missing_ok=True)


def _validate_schematic(filename, data):
    if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,159}\.kicad_sch', filename):
        raise ValueError('Use a simple filename ending in .kicad_sch; paths are not accepted')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SCHEMATIC_BYTES:
        raise ValueError('Schematic must contain 1 byte to 8 MiB')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError('Schematic must be a UTF-8 KiCad document') from error
    if '\x00' in text:
        raise ValueError('Schematic contains invalid null bytes')
    # Tokenize strings separately: text in a label must not look like a real sheet.
    tokens = re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()"]+|"', text)
    depth, first, awaiting_symbol = 0, None, False
    for match in tokens:
        token = match.group()
        if token == '"':
            raise ValueError('Malformed schematic string')
        if token == '(':
            depth += 1
            awaiting_symbol = True
        elif token == ')':
            depth -= 1
            if depth < 0 or awaiting_symbol:
                raise ValueError('Malformed schematic structure')
        elif awaiting_symbol:
            if token.startswith('"'):
                raise ValueError('Malformed schematic structure')
            if first is None:
                first = token
            if token == 'sheet':
                raise ValueError('Hierarchical schematics require the complete sheet package; attach a flat .kicad_sch for now')
            awaiting_symbol = False
        elif depth == 0:
            raise ValueError('Unexpected data outside the schematic')
    if first != 'kicad_sch' or depth != 0 or awaiting_symbol:
        raise ValueError('Expected a complete KiCad .kicad_sch document')


def _net_name(value):
    # KiCad creates names for deliberately or accidentally disconnected pins.
    # Such names are not proof of a functional connection.
    # KiCad CTX_NETNAME stores a literal slash as {slash}; XML exports decode it.
    # https://gitlab.com/kicad/code/kicad/-/blob/10.0/common/string_utils.cpp
    return '' if not value or value.startswith('unconnected-(') else value.replace('{slash}', '/')


def parse_netlist(data):
    if len(data) > MAX_NETLIST_BYTES or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unsupported XML netlist declarations or size')
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise ValueError('KiCad returned an invalid XML netlist') from error
    if root.tag != 'export' or root.find('components') is None or root.find('nets') is None:
        raise ValueError('Expected a KiCad XML netlist with components and nets')
    refs = [component.get('ref', '') for component in root.findall('./components/comp')]
    if any(not ref for ref in refs) or len(refs) != len(set(refs)):
        raise ValueError('Schematic contains empty or duplicate component references')
    pins, no_connect = {}, set()
    for net in root.findall('./nets/net'):
        name = _net_name(net.get('name', ''))
        for node in net.findall('node'):
            ref, pin = node.get('ref', ''), node.get('pin', '')
            if ref not in refs or not pin:
                raise ValueError('Schematic net refers to an unknown component or pin')
            key = (ref, pin)
            if key in pins and pins[key] != name:
                raise ValueError('Schematic pin belongs to more than one net')
            pins[key] = name
            if 'no_connect' in node.get('pintype', '').split('+'):
                no_connect.add(key)
    # Include pins omitted from <nets> so a disconnected pin cannot disappear
    # from the comparison when the exporter supplies the library pin inventory.
    libraries = {(part.get('lib'), part.get('part')):
                 [(pin.get('num'), pin.get('type', '')) for pin in part.findall('./pins/pin') if pin.get('num')]
                 for part in root.findall('./libparts/libpart')}
    for component in root.findall('./components/comp'):
        source = component.find('libsource')
        if source is not None:
            for pin, pin_type in libraries.get((source.get('lib'), source.get('part')), []):
                pins.setdefault((component.get('ref'), pin), '')
                if pin_type == 'no_connect':
                    no_connect.add((component.get('ref'), pin))
    return {'refs': sorted(refs), 'pins': pins, 'no_connect': no_connect}


def _schematic_evidence(path):
    data = path.read_bytes()
    settings = path.with_suffix('.kicad_pro')
    key = (str(STORAGE_ROOT), _digest(data), _digest(settings.read_bytes()) if settings.exists() else None)
    if key not in _NETLIST_CACHE:
        parsed = parse_netlist(_run_netlist(path))
        if len(_NETLIST_CACHE) >= 16:
            _NETLIST_CACHE.pop(next(iter(_NETLIST_CACHE)))
        _NETLIST_CACHE[key] = parsed
    return copy.deepcopy(_NETLIST_CACHE[key])


def _source(target):
    folder = _folder(target)
    active = folder / 'active.json'
    if active.exists():
        metadata = json.loads(active.read_text())
        digest = metadata.get('sha256', '')
        if not re.fullmatch('[a-f0-9]{64}', digest):
            raise ValueError('Invalid stored schematic identity')
        path = folder / 'schematics' / digest / 'source.kicad_sch'
        data = path.read_bytes()
        if _digest(data) != digest:
            raise ValueError('Stored schematic changed after attachment')
        return path, dict(filename=metadata['filename'], sha256=digest, source='attached',
                          erc_scope='Attached schematic with KiCad default ERC settings; no project settings uploaded')
    path = target.with_suffix('.kicad_sch')
    if not path.exists():
        return None, {'status': 'missing', 'source': None}
    if path.stat().st_size > MAX_SCHEMATIC_BYTES:
        raise ValueError('Existing schematic exceeds the supported 8 MiB size')
    data = path.read_bytes()
    _validate_schematic(path.name, data)
    digest = _digest(data)
    settings_path = target.with_suffix('.kicad_pro')
    settings = None
    if settings_path.exists():
        if settings_path.stat().st_size > MAX_SCHEMATIC_BYTES:
            raise ValueError('Project settings exceed the supported 8 MiB size')
        settings = settings_path.read_bytes()
    settings_digest = _digest(settings) if settings is not None else 'default-settings'
    immutable = _immutable(folder / 'schematics' / digest / settings_digest / 'source.kicad_sch', data)
    if settings is not None:
        _immutable(immutable.with_suffix('.kicad_pro'), settings)
    return immutable, dict(filename=path.name, sha256=digest, source='project',
                           project_settings_sha256=settings_digest if settings is not None else None,
                           erc_scope='Saved schematic and project ERC settings snapshot' if settings is not None else
                           'Saved schematic snapshot with KiCad default ERC settings')


def get_erc_source(target=None):
    """Return an immutable flat schematic Path, or None if none is available.

    Invalid/hierarchical source raises ValueError so callers must report a blocked
    ERC, rather than run a partial root sheet or report a false pass.
    """
    with _LOCK:
        return _source(_target(target))[0]


def _electrical_pins(snapshot):
    pins, conflicts = {}, []
    for pad in snapshot['pads']:
        if not pad.get('electrical', True) or not pad.get('pin'):
            continue
        key, name = (pad['ref'], pad['pin']), _net_name(pad.get('net', ''))
        if key in pins and pins[key] != name:
            conflicts.append({'ref': key[0], 'pin': key[1]})
        pins[key] = name
    return pins, conflicts


def _comparison(snapshot, schematic):
    board_pins, conflicts = _electrical_pins(snapshot)
    electrical_refs = {ref for ref, _ in board_pins}
    ignored_refs = {item['ref'] for item in snapshot['footprints']
                    if item.get('board_only') and item['ref'] not in electrical_refs}
    board_refs = [item['ref'] for item in snapshot['footprints'] if item['ref'] not in ignored_refs]
    source_pins = schematic['pins']
    mismatch = [{'ref': ref, 'pin': pin, 'board_net': board_pins[(ref, pin)],
                 'schematic_net': source_pins[(ref, pin)]}
                for ref, pin in sorted(board_pins.keys() & source_pins.keys())
                if board_pins[(ref, pin)] != source_pins[(ref, pin)]]
    result = {'board_only_refs': sorted(set(board_refs) - set(schematic['refs'])),
              'schematic_only_refs': sorted(set(schematic['refs']) - set(board_refs)),
              'duplicate_board_refs': sorted(ref for ref, count in Counter(board_refs).items() if count > 1),
              'board_only_pins': [{'ref': ref, 'pin': pin} for ref, pin in sorted(board_pins.keys() - source_pins.keys())],
              'schematic_only_pins': [{'ref': ref, 'pin': pin} for ref, pin in sorted(source_pins.keys() - board_pins.keys())],
              'pin_net_mismatches': mismatch, 'conflicting_board_pins': conflicts,
              'no_connect_net_conflicts': [{'ref': ref, 'pin': pin} for ref, pin in sorted(schematic.get('no_connect', set()))
                                          if source_pins.get((ref, pin)) or board_pins.get((ref, pin))]}
    result['matched'] = not any(result.values())
    result['ignored_mechanical_refs'] = sorted(ignored_refs)
    return result


def _coverage(snapshot):
    pins, _ = _electrical_pins(snapshot)
    groups = defaultdict(set)
    for pin, net in pins.items():
        if net:
            groups[net].add(pin)
    connected = sum(len(nodes) for nodes in groups.values() if len(nodes) >= 2)
    return {'footprints': len(snapshot['footprints']), 'pads': len(snapshot['pads']),
            'electrical_pins': len(pins), 'assigned_pads': sum(bool(net) for net in pins.values()),
            'unassigned_pads': sum(not net for net in pins.values()),
            'no_connect_pads': 0, 'unresolved_pads': sum(not net for net in pins.values()),
            'connected_pads': connected, 'named_nets': len(set(groups) | {_net_name(net) for net in snapshot.get('nets', []) if _net_name(net)}),
            'connected_nets': sum(len(nodes) >= 2 for nodes in groups.values()),
            'tracks': snapshot['tracks'], 'vias': snapshot['vias'], 'zones': snapshot['zones'],
            'filled_zones': snapshot.get('filled_zones', 0),
            'unconnected': snapshot.get('unconnected')}


def view(target=None):
    """Read saved design evidence, caching native probes by exact saved SHA-256."""
    target = _target(target)
    state = {'board': str(target), 'scope': 'Saved PCB on disk; unsaved editor changes are not included',
             'saved_board_sha256': None, 'status': 'unavailable', 'coverage': None,
             'readiness': {'placement_available': False, 'connectivity_verified': False,
                           'has_copper': False, 'routing_available': False, 'electrical_signoff': False},
             'schematic': {'status': 'missing'}, 'blockers': [], 'pin_net_mapping': [],
             'routing': {'status': 'unavailable', 'automatic': False,
                         'reason': 'No automatic copper router is connected to this workflow'},
             'notes': ['Zero unrouted connections does not prove connectivity when nets are missing.',
                       'Assigned pins and copper do not prove electrical correctness; ERC and DRC are separate checks.']}
    with _LOCK:
        try:
            data = target.read_bytes()
            digest = _digest(data)
            state['saved_board_sha256'] = digest
            key = (str(target), digest)
            if key not in _BOARD_CACHE:
                path = _immutable(_folder(target) / 'boards' / (digest + '.kicad_pcb'), data)
                snapshot = _probe_board(path)
                if len(_BOARD_CACHE) >= 16:
                    _BOARD_CACHE.pop(next(iter(_BOARD_CACHE)))
                _BOARD_CACHE[key] = snapshot
            snapshot = copy.deepcopy(_BOARD_CACHE[key])
            coverage = state['coverage'] = _coverage(snapshot)
            state['readiness']['placement_available'] = bool(coverage['footprints'])
            state['readiness']['has_copper'] = bool(coverage['tracks'] or coverage['vias'] or coverage['filled_zones'])
            pins, _ = _electrical_pins(snapshot)
            state['pin_net_mapping'] = [{'ref': ref, 'pin': pin, 'net': net}
                                        for (ref, pin), net in sorted(pins.items())]
            state['status'] = 'blocked'
        except (OSError, ValueError, KeyError, TypeError) as error:
            state['blockers'].append('Saved board inspection unavailable: ' + str(error))
            return state
        try:
            path, metadata = _source(target)
            state['schematic'] = metadata
            if path is None:
                state['blockers'].append('Attach the electrical schematic to verify reference and pin-to-net assignments')
            else:
                evidence = _schematic_evidence(path)
                comparison = _comparison(snapshot, evidence)
                coverage['no_connect_pads'] = sum(key in pins and not pins[key] and not evidence['pins'][key]
                                                   for key in evidence.get('no_connect', set()))
                coverage['unresolved_pads'] = coverage['unassigned_pads'] - coverage['no_connect_pads']
                state['schematic'].update(status='matched' if comparison['matched'] else 'mismatch', comparison=comparison)
                if not comparison['matched']:
                    state['blockers'].append('Schematic and PCB references or pin-to-net assignments differ; update the PCB from the schematic in KiCad')
                elif coverage['connected_nets'] and not coverage['unresolved_pads']:
                    state['readiness']['connectivity_verified'] = True
        except (OSError, ValueError, KeyError, TypeError) as error:
            state['schematic'] = {'status': 'unavailable', 'error': str(error)}
            state['blockers'].append('Schematic verification unavailable: ' + str(error))
        if not coverage['named_nets']:
            state['blockers'].append('PCB has no electrical nets; component placement is not a connected circuit')
        elif not coverage['connected_nets']:
            state['blockers'].append('No net connects two or more component pins; named nets alone are not a connected circuit')
        if coverage['unresolved_pads']:
            state['blockers'].append(str(coverage['unresolved_pads']) + ' electrical pins have no functional net assignment; resolve wiring or provide explicit no-connect evidence')
        if not state['readiness']['has_copper']:
            state['blockers'].append('No copper tracks, vias, or filled zones are present')
        elif coverage['unconnected']:
            state['blockers'].append(str(coverage['unconnected']) + ' required copper connections remain unrouted')
        if state['readiness']['connectivity_verified']:
            state['status'] = ('partially_routed' if coverage['unconnected'] else 'routed_unverified') if state['readiness']['has_copper'] else 'ready_for_routing'
        state['blockers'].append(state['routing']['reason'])
        return state


def attach_schematic(filename, data, target=None, expected_board_sha256=None):
    """Attach a flat schematic after valid netlist export; never change PCB nets.

    A mismatching schematic is retained as evidence with mismatch details. A
    malformed schematic or failed KiCad export never replaces a prior attachment.
    """
    _validate_schematic(filename, data)
    target = _target(target)
    with _LOCK:
        saved_digest = _digest(target.read_bytes())
        if expected_board_sha256 is not None and expected_board_sha256 != saved_digest:
            raise ValueError('Saved PCB changed; refresh electrical readiness before attaching the schematic')
        folder = _folder(target)
        digest = _digest(data)
        source = _immutable(folder / 'schematics' / digest / 'source.kicad_sch', data)
        _schematic_evidence(source)
        if _digest(target.read_bytes()) != saved_digest:
            raise ValueError('Saved PCB changed during schematic verification; refresh and retry attachment')
        temporary = folder / ('active-' + uuid.uuid4().hex + '.json')
        temporary.write_text(json.dumps({'filename': filename, 'sha256': digest,
                                         'attached_board_sha256': saved_digest}))
        os.replace(temporary, folder / 'active.json')
        return view(target)
