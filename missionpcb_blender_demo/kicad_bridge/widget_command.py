"""Offline commands for the native floating panel; no model call."""
import json,re,sys,datetime
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
 match=re.fullmatch(r'move (u[1-5]|j1|mcu|sensor|ecg front end|radio|regulator|charger|battery connector) (?:to )?(-?\d+(?:\.\d+)?)\s*(?:,\s*|\s+)(-?\d+(?:\.\d+)?)(?: mm)?',command)
 if match:
  ref,x,y=match.groups();return ('move',aliases.get(ref,ref.upper()),float(x),float(y))
 match=re.fullmatch(r'move (u[1-5]|j1|mcu|sensor|ecg front end|radio|regulator|charger|battery connector) (\d+(?:\.\d+)?)\s*mm (left|right|up|down)',command)
 if match:
  ref,distance,direction=match.groups();return ('relative',aliases.get(ref,ref.upper()),float(distance),direction)
 return ('unknown',)

def run(text):
 if text.lower().startswith("blender:"):
  import blender_command
  return blender_command.run(text.split(":",1)[1].strip())
 if text.strip().lower() in ("full check","review board","check the board"):
  import native_review
  return native_review.run()
 intent=parse(text)
 if intent[0] in ('help','unknown'):
  prefix="Hi! I can inspect and move components in your open MissionPCB board." if intent[0]=='help' else "I couldn't map that to a supported action, so I haven't changed the board."
  return prefix+'\n\nTry: “Inspect the board”, “Improve the layout”, “Move the regulator 2 mm right”, or “Reset the layout”.\n\nLocal command understanding is active. Live Astra chat is not connected.'
 state=bridge.snapshot(bridge.connect())
 command=intent[0]
 if command in ('inspect','status',''):
  return 'Connected to MissionPCB · %d parts\n'%len(state['parts'])+'\n'.join('%s  (%.1f, %.1f) mm'%(p['ref'],p['x_mm'],p['y_mm']) for p in state['parts'])
 if command in ('improve','reset'):
  key='MissionPCB' if command=='improve' else 'Naive'
  data=json.loads((bridge.TARGET.parent/'cache/results.json').read_text())['results'][key]
  mapping={'MCU':'U1','Sensor':'U2','RF':'U3','Regulator':'U4','Driver':'U5','Battery':'J1'}
  moves=[{'ref':mapping[p['ref']],'x_mm':100+p['board_xy_mm'][0],'y_mm':138-p['board_xy_mm'][1],'rotation_deg':90 if p['ref']=='RF' else 0} for p in data['component_positions']]
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
 result=bridge.apply({'board':state['board'],'base_revision':state['revision'],'moves':moves})
 return 'Applied and verified %d component moves in KiCad.\nOne Undo reverses the change. Not saved to disk.\nThis checks placement commands, not circuit correctness.'%len(moves)
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
