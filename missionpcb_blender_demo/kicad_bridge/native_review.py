"""Review current exact-target KiCad placement; no CAD writes."""
import json,time,urllib.request,subprocess,sys
from pathlib import Path
import bridge
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT/'missionpcb_review') not in sys.path:
 sys.path.insert(0,str(ROOT/'missionpcb_review'))
from board_profile import CORE_MAP,component_map
MAP=component_map()
def run():
 board=bridge.connect();before=bridge.snapshot(board)
 from layout_adapter import payload_for
 payload=payload_for(before)
 req=urllib.request.Request('http://127.0.0.1:8769/review',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
 result=json.load(urllib.request.urlopen(req,timeout=15))
 if bridge.snapshot(board)['revision']!=before['revision']:raise ValueError('Board changed during review; run again')
 result['native_board_revision']=before['revision'];result['source']='live KiCad footprint positions; fixed demo outline/enclosure and cached package dimensions'
 result['limitations'].append('No schematic/netlist completeness, patient/battery coverage, or exact package verification. Native DRC below is on saved disk board, not unsaved edits.')
 folder=bridge.TARGET.parent/'verification';folder.mkdir(exist_ok=True)
 drc=folder/'widget-drc.json'
 proc=subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(drc),str(bridge.TARGET)],capture_output=True,text=True,timeout=15)
 native=json.loads(drc.read_text()) if proc.returncode==0 and drc.exists() else {'error':proc.stderr}
 result['saved_board_drc']=native
 (folder/'live-review.json').write_text(json.dumps(result,indent=2))
 summary=result['result']['summary'];lines=['LIVE KICAD PLACEMENT REVIEW',f"{summary.get('PASS',0)} passed · {summary.get('FAIL',0)} failed · {summary.get('SKIP',0)} skipped"]
 lines += [','.join(c['kicad_refs'])+': '+c.get('message','') for c in result['findings']]
 lines += ['SAVED BOARD DRC (not unsaved edits): '+str(len(native.get('violations',[])))+' violations' if 'error' not in native else 'Saved-board DRC unavailable']
 lines += [c.get('description','') for c in native.get('violations',[])]
 lines += ['Coverage incomplete: no circuit/ERC validation. Approximate U2/U4 packages. Placement rules use cached dimensions and authored proxies.']
 return '\n'.join(lines)
if __name__=='__main__':print(run())
