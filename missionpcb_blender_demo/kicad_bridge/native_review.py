"""Review current exact-target KiCad placement; no CAD writes."""
import json,time,urllib.request,subprocess
from pathlib import Path
import bridge
ROOT=Path(__file__).resolve().parents[2]
MAP={'U1':('MCU','msp430fr2433'),'U2':('Sensor','ads1292r'),'U3':('RF','mdbt42q'),'U4':('Regulator','tps62740'),'U5':('Driver','mcp73831'),'J1':('Battery','bm02b_srss')}
def run():
 board=bridge.connect();before=bridge.snapshot(board)
 if set(p['ref'] for p in before['parts'])!=set(MAP):raise ValueError('Expected the six known MissionPCB components')
 placements=[dict(ref=MAP[p['ref']][0],part_id=MAP[p['ref']][1],pos_mm=[round(p['x_mm']-100,6),round(138-p['y_mm'],6)],rotation_deg=(-(p['rotation_deg']-(90 if p['ref']=='U3' else 0)))%360) for p in before['parts']]
 payload=dict(design_id='missionpcb-native-six',revision=time.time_ns(),part_library='native-six',brief='ECG chest patch. Review current six-component placement against authored demo spacing policies.',kicad_refs={v[0]:k for k,v in MAP.items()},layout=dict(name='Live MissionPCB KiCad placement',distance_metric='center',enclosure=dict(interior_mm=dict(length=90,width=50,height=10),wall_keepout_mm=0),board=dict(id='MissionPCB',size_mm=dict(length=72,width=38,thickness=1.6),origin_mm=[9,6,2],edge_margin_mm=1,max_component_height_mm=6.4,min_component_gap_mm=.5),placements=placements,mission_rules=[dict(id='afe_'+ref,type='min_separation',between=['Sensor',ref],distance_mm=dist,metric='center',rationale='Authored demo policy, not solved physics.') for ref,dist in [('MCU',18),('RF',20),('Regulator',20)]]))
 req=urllib.request.Request('http://127.0.0.1:8769/review',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
 result=json.load(urllib.request.urlopen(req,timeout=15))
 if bridge.snapshot(board)['revision']!=before['revision']:raise ValueError('Board changed during review; run again')
 result['native_board_revision']=before['revision'];result['source']='live KiCad footprint positions; fixed demo outline/enclosure and cached package dimensions'
 result['limitations'].append('No schematic/netlist completeness, patient/battery coverage, or exact package verification. Native DRC below is on saved disk board, not unsaved edits.')
 folder=ROOT/'missionpcb_kicad/verification';folder.mkdir(exist_ok=True)
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
