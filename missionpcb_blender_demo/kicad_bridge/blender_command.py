"""Allowlisted widget commands for a running Blender adapter."""
import json,time,uuid
from pathlib import Path
IPC=Path(__file__).resolve().parent.parent/'blender_widget/ipc'
def run(text):
 statefile=IPC/'state.json'
 if not statefile.exists():raise ValueError('Blender adapter is not running. Run blender_widget/addon.py in the MissionPCB scene.')
 state=json.loads(statefile.read_text())
 if time.time()-state['heartbeat']>4:raise ValueError('Blender is disconnected or busy. Try again after it responds.')
 if state.get('error'):raise ValueError(state['error'])
 aliases={'u1':'MCU','mcu':'MCU','u2':'Sensor','sensor':'Sensor','u3':'RF','radio':'RF','u4':'Regulator','regulator':'Regulator','u5':'Driver','charger':'Driver','j1':'Battery','battery connector':'Battery'}
 t=text.strip().lower();action='inspect';ref=None
 if t in ('full check','check','check the board','inspect the board','inspect','status'):action='check' if t in ('full check','check','check the board') else 'inspect'
 elif t.startswith('focus '):
  ref=aliases.get(t[6:]);action='focus'
  if not ref:raise ValueError('Use focus sensor, regulator, radio, MCU, charger or battery connector.')
 else:return 'Blender supports: Full check, Inspect, Focus sensor, Focus regulator. Live Astra and arbitrary CAD placement are not connected.'
 cmd=dict(id=uuid.uuid4().hex,created=time.time(),action=action,ref=ref)
 if (IPC/'command.json').exists():raise ValueError('Another Blender command is pending')
 tmp=IPC/'command.tmp';tmp.write_text(json.dumps(cmd));tmp.replace(IPC/'command.json')
 reply=IPC/(cmd['id']+'.json')
 for _ in range(100):
  if reply.exists():
   result=json.loads(reply.read_text());reply.unlink()
   if not result['ok']:raise ValueError(result['message'])
   state=result.get('state') or json.loads(statefile.read_text());r=state.get('result') or {};summary=r.get('summary',{})
   if state.get('stale'):return result['message']+'\nResults are stale after scene edits. Run Full check before using previous counts.'
   return result['message']+'\n'+str(summary)+'\n'+ '\n'.join(c['message'] for c in r.get('checks',[]) if c['status'] in ('FAIL','SKIP'))
  time.sleep(.1)
 raise ValueError('Blender has not acknowledged the command. Inspect before retrying.')
