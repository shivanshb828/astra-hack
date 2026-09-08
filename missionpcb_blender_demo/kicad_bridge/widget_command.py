"""Offline commands for the native floating panel; no model call."""
import json,re,sys,datetime,zipfile
import review_journal
from pathlib import Path
import bridge

def parse(text):
 command=text.strip().lower().rstrip('.!?')
 command=re.sub(r'^please\s+', '',command)
 command=re.sub(r'^move the ', 'move ',command)
 if command in ('hi','hello','hey','help','what can you do'):
  return ('help',)
 if command in ('inspect','status','','inspect the board','show the board','show me the board','what is on the board','show component positions','check the board'):
  return ('inspect',)
 if command in ('improve','improve the layout','optimize the layout','apply the improved layout','apply the cached placement','improve the board'):
  return ('improve',)
 if command in ('reset','reset the board','restore the initial layout','go back to the original layout','reset the layout'):
  return ('reset',)
 aliases={'mcu':'U1','sensor':'U2','ecg front end':'U2','radio':'U3','regulator':'U4','charger':'U5','battery connector':'J1'}
 match=re.fullmatch(r'move ([ucrlj][1-9][0-9]*|mcu|sensor|ecg front end|radio|regulator|charger|battery connector) (?:to )?(-?\d+(?:\.\d+)?)\s*(?:,\s*|\s+)(-?\d+(?:\.\d+)?)(?: mm)?',command)
 if match:
  ref,x,y=match.groups();return ('move',aliases.get(ref,ref.upper()),float(x),float(y))
 match=re.fullmatch(r'move ([ucrlj][1-9][0-9]*|mcu|sensor|ecg front end|radio|regulator|charger|battery connector) (\d+(?:\.\d+)?)\s*mm (left|right|up|down)',command)
 if match:
  ref,distance,direction=match.groups();return ('relative',aliases.get(ref,ref.upper()),float(distance),direction)
 return ('unknown',)

def run(text):
 if text.strip().lower() in ('open kicad 3d viewer','render in kicad'):
  from kipy import KiCad
  for socket in sorted(Path('/tmp/kicad').glob('api*.sock')):
   try:
    client=KiCad(socket_path='ipc://'+str(socket),client_name='MissionPCB native viewer',timeout_ms=1500)
    board=client.get_board()
   except Exception:continue
   if bridge.board_path(board)!=bridge.TARGET:continue
   result=client.run_action('common.Control.show3DViewer')
   if result.status!=1:raise ValueError('KiCad did not accept the native viewer action: '+str(result))
   __import__('subprocess').run(['open','-b','org.kicad.pcbnew'],check=True)
   return 'Opened KiCad’s native 3D Viewer for the active board.'
  raise ValueError('Open the active MissionPCB board with the KiCad API enabled.')
 if text.strip().lower()=='show flagged areas':
  import native_review,native_flags
  native_review.run()
  report=json.loads((bridge.TARGET.parent/'verification/live-review.json').read_text())
  return native_flags.apply_findings(report)

 if text.strip().lower() in ('find best of 10','search layouts','generate 10 layouts'):
  import layout_search
  return layout_search.start()
 if text.strip().lower()=='apply best layout':
  import layout_search
  return layout_search.apply_winner()

 if text.strip().lower() in ('show review markers','hide review markers'):
  from kipy.board_types import BoardLayer
  board=bridge.connect();layers=set(board.get_visible_layers());layer=BoardLayer.BL_Cmts_User
  if text.strip().lower().startswith('show'):layers.add(layer)
  else:layers.discard(layer)
  board.set_visible_layers(list(layers))
  visible=layer in board.get_visible_layers()
  return 'Review markers '+('visible' if visible else 'hidden')+' in the PCB Editor. Geometry unchanged.'
 if re.fullmatch(r"select (?:[UCRLJ][1-9][0-9]*)(?:,(?:[UCRLJ][1-9][0-9]*))*",text.strip(),re.I):
  refs=text.strip().upper().split(' ',1)[1].split(',')
  board=bridge.connect();fps={f.reference_field.text.value:f for f in board.get_footprints()}
  if any(r not in fps for r in refs):raise ValueError('Unknown component')
  board.clear_selection();board.add_to_selection([fps[r] for r in refs])
  selected={getattr(f,'reference_field',None).text.value for f in board.get_selection() if getattr(f,'reference_field',None)}
  if not set(refs)<=selected:raise ValueError('Selection was not confirmed')
  return 'Selected '+', '.join(refs)+' in MissionPCB. No geometry changed.'
 if text.lower().startswith("blender:"):
  import blender_command
  return blender_command.run(text.split(":",1)[1].strip())
 if text.strip().lower() in ("full check","review board","check the board"):
  import native_review
  response=native_review.run()
  report=json.loads((bridge.TARGET.parent/'verification/live-review.json').read_text())
  record_review(report['findings'],report['result']['summary'],report['native_board_revision'],annotated=False,checks=report['result']['checks'])
  return response
 if text.strip().lower() in ("review cycle","flag board","flag and comment","review and annotate board"):
  sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'missionpcb_review'))
  import roundtrip
  revision='widget-'+str(__import__('time').time_ns())
  archive=roundtrip.review(roundtrip.submit(revision))
  outcome=roundtrip.apply(archive)
  with zipfile.ZipFile(archive) as package:
   report=json.loads(package.read('findings.json'))
  try:record_review(report['findings'],report['summary'],bridge.snapshot(bridge.connect())['revision'],annotated=True,revision=revision,checks=report.get('checks',[]))
  except Exception as exc:raise RuntimeError('Native review annotations were applied and saved, but the transcript could not be saved. Inspect the board before retrying: '+str(exc)) from exc
  return 'ENGINE REVIEW → NATIVE KICAD FLAGS\n'+str(outcome['summary'])+'\n'+str(outcome['annotations_applied'])+' review labels/comments applied on Cmts.User.\nBoard saved. One Undo reverses annotations. Component positions preserved.\nRevision: '+revision+'\nCoverage incomplete; geometry policies only.'
 intent=parse(text)
 if intent[0] in ('help','unknown'):
  prefix="Hi! I can inspect and move components in your open MissionPCB board." if intent[0]=='help' else "I couldn't map that to a supported action, so I haven't changed the board."
  return prefix+'\n\nTry: “Full check”, “Flag and comment”, “Improve the layout”, “Move the regulator 2 mm right”, or “Reset the layout”. Comments and pins are available in the expanded dashboard.\n\nLocal command understanding is active. Live Astra chat is not connected.'
 state=bridge.snapshot(bridge.connect())
 command=intent[0]
 if command in ('inspect','status',''):
  return 'Connected to MissionPCB · %d parts\n'%len(state['parts'])+'\n'.join('%s  (%.1f, %.1f) mm'%(p['ref'],p['x_mm'],p['y_mm']) for p in state['parts'])
 if command in ('improve','reset'):
  key='MissionPCB' if command=='improve' else 'Naive'
  data=json.loads((bridge.TARGET.parent/'cache/results.json').read_text())['results'][key]
  mapping={'MCU':'U1','Sensor':'U2','RF':'U3','Regulator':'U4','Driver':'U5','Battery':'J1'}
  moves=[{'ref':mapping[p['ref']],'x_mm':100+p['board_xy_mm'][0],'y_mm':138-p['board_xy_mm'][1],'rotation_deg':90 if p['ref']=='RF' else 0} for p in data['component_positions']]
  from board_profile import expand_moves
  moves=expand_moves(moves,{p['ref'] for p in state['parts']})
 else:
  ref=intent[1]
  old=next((p for p in state['parts'] if p['ref']==ref),None)
  if old is None:raise ValueError('Unknown component reference')
  if command=='relative':
   distance,direction=intent[2:]
   x=old['x_mm']+({'left':-distance,'right':distance}.get(direction,0))
   y=old['y_mm']+({'up':-distance,'down':distance}.get(direction,0))
  else:x,y=intent[2:]
  moves=[{'ref':ref,'x_mm':x,'y_mm':y,'rotation_deg':old['rotation_deg']}]
 pins=review_journal.get_state(state['board'])['pins']
 old_positions={p['ref']:p for p in state['parts']}
 blocked=[m['ref'] for m in moves if pins.get(m['ref']) and any(m[k]!=old_positions[m['ref']][k] for k in ('x_mm','y_mm','rotation_deg'))]
 if blocked:raise ValueError('Pinned components would move: '+', '.join(blocked)+'. Unpin them in the dashboard before applying.')
 result=bridge.apply({'board':state['board'],'base_revision':state['revision'],'moves':moves})
 try:review_journal.append_event(state['board'],'design_change',{'command':text,'before':result['before'],'after':result['after'],'moves':moves,'source':'cached placement' if command in ('improve','reset') else 'user command','review_required':True})
 except Exception as exc:raise RuntimeError('The native component move succeeded, but the transcript could not be saved. Inspect KiCad before retrying; one Undo reverses the move. '+str(exc)) from exc
 return 'Applied and verified %d component moves in KiCad.\nOne Undo reverses the change. Not saved to disk.\nThis checks placement commands, not circuit correctness.'%len(moves)

def record_review(findings,summary,native_revision,annotated=False,revision=None,checks=None):
 """Persist review snapshots and stable finding transitions for the dashboard."""
 previous=[e['payload'] for e in review_journal.get_state(str(bridge.TARGET))['events'] if e['kind']=='engine_review']
 old={c['id'] for c in previous[-1]['findings'] if c['status']=='FAIL'} if previous else set()
 current={c['id'] for c in findings if c['status']=='FAIL'}
 ever={c['id'] for p in previous for c in p['findings'] if c['status']=='FAIL'}
 payload={'findings':findings,'summary':summary,'native_board_revision':native_revision,'annotated':annotated,'revision':revision,'source':'local compute engine; cached part data and authored policies','new_failures':sorted(current-old-ever),'reopened':sorted((current-old)&ever),'resolved':sorted(old-current)}
 from mission_constraints import revision as constraint_revision
 payload['constraint_revision']=constraint_revision();payload['checks']=checks or findings
 return review_journal.append_event(str(bridge.TARGET),'engine_review',payload)

def log_event(command, status, message):
 path=Path(__file__).with_name('activity.jsonl')
 with path.open('a') as file:
  file.write(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':command,'status':status,'message':message})+'\n')

if __name__=='__main__':
 command=sys.argv[1] if len(sys.argv)>1 else 'inspect'
 log_event(command,'running','Reading the MissionPCB board')
 try:
  response=run(command)
  log_event(command,'complete',response)
  print(response)
 except Exception as e:
  response='Could not apply: '+str(e)
  log_event(command,'error',response)
  print(response);sys.exit(1)
