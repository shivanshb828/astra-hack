"""Known ECG demo references and supporting-component placement policies."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CORE_MAP={'U1':('MCU','msp430fr2433'),'U2':('Sensor','ads1292r'),'U3':('RF','mdbt42q'),'U4':('Regulator','tps62740'),'U5':('Driver','mcp73831'),'J1':('Battery','bm02b_srss')}
def support_parts():
 path=ROOT/'missionpcb_kicad/expanded-support-parts.json'
 return json.loads(path.read_text())['parts'] if path.exists() else []
def component_map():
 return {**CORE_MAP,**{p['ref']:(p['engine_ref'],p['part_id']) for p in support_parts()}}
def expand_moves(core_moves,known_refs):
 """Keep each added support group with its anchor in cached placement changes."""
 moves=list(core_moves);anchors={p['ref']:p for p in core_moves}
 for part in support_parts():
  if part['ref'] not in known_refs:continue
  anchor=anchors[part['anchor_ref']];dx,dy=part['offset_mm']
  moves.append({'ref':part['ref'],'x_mm':anchor['x_mm']+dx,'y_mm':anchor['y_mm']+dy,'rotation_deg':0})
 return moves
