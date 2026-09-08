"""Small JSON interface for an agent to inspect and move MissionPCB footprints."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from kipy import KiCad
from kipy.geometry import Vector2, Angle

_ROOT = Path(__file__).resolve().parents[2]
_ACTIVE = Path(__file__).resolve().parent/'runtime/active-project.json'
_PROJECT = Path(json.loads(_ACTIVE.read_text())['project']) if _ACTIVE.exists() else _ROOT/'missionpcb_kicad'
TARGET = (_PROJECT/'MissionPCB.kicad_pcb').resolve()

def board_path(board):
    doc = board.document
    return (Path(doc.project.path) / doc.board_filename).resolve()

def connect(return_client=False):
    matches = []
    for socket in sorted(Path('/tmp/kicad').glob('api*.sock')):
        try:
            client = KiCad(socket_path='ipc://' + str(socket), client_name='MissionPCB agent bridge', timeout_ms=1500)
            board = client.get_board()
            if board_path(board) == TARGET:
                matches.append((client,board))
        except Exception:
            continue
    if len(matches) != 1:
        raise ValueError('Open exactly one MissionPCB board in KiCad with its API server enabled. Other projects are never selected.')
    return matches[0] if return_client else matches[0][1]

def snapshot(board):
    if board_path(board) != TARGET:
        raise ValueError('Wrong board; refusing access')
    parts = []
    for fp in board.get_footprints():
        parts.append({'ref': fp.reference_field.text.value,
                      'value': fp.value_field.text.value,
                      'x_mm': round(fp.position.x / 1e6, 6),
                      'y_mm': round(fp.position.y / 1e6, 6),
                      'rotation_deg': round(fp.orientation.degrees, 6)})
    parts.sort(key=lambda p:p['ref'])
    state = {'board': str(TARGET), 'coordinates': 'KiCad absolute XY millimeters; Y increases downwards', 'parts': parts}
    state['revision'] = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    return state

def validate(proposal, before):
    if set(proposal) != {'board', 'base_revision', 'moves'}:
        raise ValueError('Expected board, base_revision and moves only')
    if proposal['board'] != str(TARGET):
        raise ValueError('Proposal targets another board')
    if proposal['base_revision'] != before['revision']:
        raise ValueError('Stale proposal: inspect again before applying')
    moves = proposal['moves']
    if not isinstance(moves, list) or not 1 <= len(moves) <= len(before['parts']):
        raise ValueError('Expected 1 to the current component count in moves')
    known = {p['ref'] for p in before['parts']}
    seen = set()
    for move in moves:
        if set(move) != {'ref', 'x_mm', 'y_mm', 'rotation_deg'}:
            raise ValueError('Move must contain ref, x_mm, y_mm, rotation_deg only')
        ref = move['ref']
        if ref not in known or ref in seen:
            raise ValueError('Unknown or duplicate reference')
        seen.add(ref)
        for field in ('x_mm', 'y_mm', 'rotation_deg'):
            value = move[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Coordinates and rotations must be finite numbers')
        if not (100 <= move['x_mm'] <= 172 and 100 <= move['y_mm'] <= 138):
            raise ValueError('Footprint center is outside the demo board')
        if move['rotation_deg'] % 90 != 0:
            raise ValueError('Demo supports orthogonal rotations only')
    return moves

def apply(proposal):
    board = connect()
    before = snapshot(board)
    moves = validate(proposal, before)
    footprints = {f.reference_field.text.value:f for f in board.get_footprints()}
    if len(footprints) != len(before['parts']):
        raise ValueError('Duplicate references on board')
    changes=[]
    for move in moves:
        f=footprints[move['ref']]
        f.position=Vector2.from_xy_mm(move['x_mm'],move['y_mm'])
        # kipy 0.8's orientation setter drops non-geometric children (3D models).
        models = list(f.definition.models)
        f.orientation=Angle.from_degrees(move['rotation_deg'])
        retained = {id(item) for item in f.definition.items}
        for item in models:
            if id(item) not in retained:
                f.definition.add_item(item)
        changes.append(f)
    if snapshot(board)['revision'] != before['revision']:
        raise ValueError('Board changed while preparing proposal')
    transaction=board.begin_commit()
    try:
        updated=board.update_items(changes)
        if len(updated)!=len(changes):
            raise ValueError('KiCad returned an incomplete update')
    except Exception:
        board.drop_commit(transaction)
        raise
    # Do not retry an uncertain commit automatically.
    board.push_commit(transaction, 'MissionPCB: apply agent placement proposal')
    after=snapshot(board)
    by_ref={p['ref']:p for p in after['parts']}
    for move in moves:
        actual=by_ref[move['ref']]
        if any(abs(actual[k]-move[k])>0.00001 for k in ('x_mm','y_mm')) or abs((actual['rotation_deg']-move['rotation_deg']+180)%360-180)>0.00001:
            raise RuntimeError('Post-commit verification failed; inspect KiCad and use Undo. Do not retry blindly.')
    return {'applied':True,'saved_to_disk':False,'undo':'One Undo in KiCad restores this proposal','before':before,'after':after}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['inspect','apply'])
    parser.add_argument('proposal',nargs='?')
    args=parser.parse_args()
    try:
        result=snapshot(connect()) if args.action=='inspect' else apply(json.loads(Path(args.proposal).read_text()))
        print(json.dumps(result,indent=2))
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc)}))
        raise SystemExit(1)
if __name__=='__main__': main()
