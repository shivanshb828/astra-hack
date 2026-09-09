"""Confirmed-board handoff and authenticated assembly commands, using file IPC."""
import hashlib,json,subprocess,time,uuid,fcntl
from pathlib import Path
import bridge
from detailed_export import OPTIONS, VERSION, inspect_export
ROOT=Path(__file__).resolve().parent
PIPELINE=ROOT.parent/'blender_widget'
IPC=PIPELINE/'ipc'
SESSIONS=ROOT/'runtime'/'blender-sessions'
CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
BLENDER='/Applications/Blender.app/Contents/MacOS/Blender'

def state():
 try:
  value=json.loads((IPC/'state.json').read_text())
  value['connected']=0<=time.time()-value.get('heartbeat',0)<5 and not value.get('error')
  if not value['connected']:
   return {'connected':False,'file':value.get('file'),'error':value.get('error') or 'Blender connection lost. Reopen the saved assembly to reconnect.'}
  assembly=value.get('assembly',{})
  if assembly.get('source_board'):
   assembly['active_pcb_file']=str(bridge.TARGET)
   assembly['different_project']=Path(assembly['source_board']).resolve()!=bridge.TARGET.resolve()
  if assembly.get('source_board') and assembly.get('source_hash'):
   try:assembly['saved_source_changed']=hashlib.sha256(Path(assembly['source_board']).read_bytes()).hexdigest()!=assembly['source_hash']
   except OSError:assembly['saved_source_unavailable']=True
  return value
 except (OSError,ValueError):return {'connected':False}

def open_session():
 """Reopen a saved assembly with its adapter, preserving other Blender windows."""
 SESSIONS.mkdir(parents=True,exist_ok=True)
 with (SESSIONS/'open.lock').open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('Blender is already opening. Wait for it to connect.')
  current=state()
  if current.get('connected') and current.get('assembly'):
   subprocess.run(['open','-a','Blender'],check=True)
   return {'ok':True,'message':'Blender assembly is connected.','state':current}
  saved=sorted(SESSIONS.glob('*/assembly.blend'),key=lambda p:p.stat().st_mtime,reverse=True)
  # The user may save or rename the assembly outside generated session folders.
  # This pointer is published by the native adapter, never supplied by a request.
  try:
   remembered=Path(json.loads((IPC/'assembly-project.json').read_text())['file'])
   if remembered.is_file() and remembered.suffix.lower()=='.blend':saved.insert(0,remembered)
  except (OSError,ValueError,KeyError):pass
  if not saved:raise ValueError('No saved assembly yet. Confirm a KiCad board for Blender first.')
  path=saved[0]
  with (SESSIONS/'open.log').open('a') as log:
   process=subprocess.Popen([BLENDER,str(path),'--python',str(PIPELINE/'addon.py')],stdout=log,stderr=log,start_new_session=True)
  deadline=time.monotonic()+45
  while time.monotonic()<deadline:
   current=state()
   if current.get('connected') and current.get('pid')==process.pid:
    subprocess.run(['open','-a','Blender'],check=True)
    return {'ok':True,'message':'Saved assembly opened in Blender.','state':current}
   if process.poll() is not None:raise ValueError('Blender could not open the assembly. See runtime/blender-sessions/open.log.')
   time.sleep(.25)
  raise ValueError('Blender is still opening. The widget will reconnect when its adapter is ready.')

def dispatch(action,expected_session=None,**payload):
 current=state()
 if not current['connected']:raise ValueError('Blender adapter is offline. Open the MissionPCB scene and start its adapter.')
 if current.get('assembly_api')!=1:raise ValueError('Restart the Blender adapter to enable assembly tools.')
 if expected_session is not None and expected_session!=current.get('session'):raise ValueError('Blender file or scene changed. Refresh the widget and retry.')
 identifier=uuid.uuid4().hex
 pending=IPC/'command.json'
 if pending.exists():raise ValueError('Blender is processing another request.')
 command={**payload,'id':identifier,'created':time.time(),'action':action,'session':current.get('session')}
 # Exclusive creation prevents two senders from replacing a pending request.
 with pending.open('x') as f:json.dump(command,f,allow_nan=False)
 reply=IPC/(identifier+'.json')
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  if reply.exists():
   result=json.loads(reply.read_text());reply.unlink()
   if not result['ok']:raise ValueError(result['message'])
   return result
  time.sleep(.1)
 raise TimeoutError('Blender has not acknowledged this request. Inspect the scene before retrying.')

def confirm(expected_revision,expected_session=None):
 board=bridge.connect();snapshot=bridge.snapshot(board)
 if not snapshot['parts']:raise ValueError('The active KiCad project has no components. Open the source PCB or build the new board before importing it.')
 if snapshot['revision']!=expected_revision:raise ValueError('Board changed since preview. Refresh before confirming.')
 current=state()
 if not current.get('connected'):raise ValueError('Open Blender before updating the board.')
 if expected_session is not None and expected_session!=current.get('session'):raise ValueError('Blender file or scene changed. Refresh the widget and retry.')
 target_session=current.get('session')
 folder=SESSIONS/uuid.uuid4().hex;folder.mkdir(parents=True)
 # Confirmation authorizes saving this exact board. Export is verified against the same revision.
 board.save()
 if bridge.snapshot(board)['revision']!=expected_revision:raise ValueError('Board changed while saving; confirm again.')
 original=bridge.TARGET.read_bytes();digest=hashlib.sha256(original).hexdigest()
 glb=folder/'board.glb'
 proc=subprocess.run([CLI,'pcb','export','glb','--force',*OPTIONS,'-o',str(glb),str(bridge.TARGET)],capture_output=True,text=True,timeout=60)
 (folder/'export.log').write_text(proc.stdout+'\n'+proc.stderr)
 if proc.returncode or not glb.exists() or glb.stat().st_size<20:raise ValueError('KiCad GLB export failed; see '+str(folder/'export.log'))
 if hashlib.sha256(bridge.TARGET.read_bytes()).hexdigest()!=digest or bridge.snapshot(board)['revision']!=expected_revision:raise ValueError('Board changed during export; exported file was not imported.')
 (folder/'source.kicad_pcb').write_bytes(original)
 coverage=inspect_export(glb,[p['ref'] for p in snapshot['parts']])
 import brief_store
 brief=brief_store.current()
 manifest={'model_coverage':coverage,'id':folder.name,'source_board':str(bridge.TARGET),'source_hash':digest,'revision':expected_revision,'parts':snapshot['parts'],'glb':str(glb),'mission':brief['text'],'brief_revision':brief['revision'],'confirmed_at':time.time()}
 report=bridge.TARGET.parent/'verification/live-review.json'
 if report.exists():
  review=json.loads(report.read_text())
  if review.get('native_board_revision')==expected_revision:manifest['native_findings']=review.get('findings',[])
 path=folder/'manifest.json';path.write_text(json.dumps(manifest,indent=2))
 result=dispatch('assembly_handoff',manifest=str(path),expected_session=target_session)
 (ROOT/'runtime'/'active-stage.json').write_text(json.dumps({'stage':'Blender','session':folder.name}))
 subprocess.run(['open','-a','Blender'],check=True)
 return result

def upload(filename,data,units,role,expected_session=None):
 ext=Path(filename).suffix.lower()
 if ext not in ('.glb','.stl','.obj','.ply','.blend'):raise ValueError('Use GLB, STL, OBJ, PLY or Blender files. Export STEP as a mesh first.')
 if units not in ('mm','m'):raise ValueError('Choose millimeters or meters.')
 if role not in ('product','body'):raise ValueError('Invalid asset role.')
 if not data or len(data)>100*1024*1024:raise ValueError('File must be between 1 byte and 100 MB.')
 folder=SESSIONS/'uploads';folder.mkdir(parents=True,exist_ok=True)
 path=folder/(uuid.uuid4().hex+ext);path.write_bytes(data)
 return dispatch('assembly_import',path=str(path),label=Path(filename).name,units=units,role=role,expected_session=expected_session)

def preview():
 """Render the exact saved board; explicitly separate from unsaved live edits."""
 import sys,tempfile
 for folder in (ROOT.parents[1]/'src',ROOT.parents[1]/'missionpcb_review'):
  if str(folder) not in sys.path:sys.path.insert(0,str(folder))
 from layout_adapter import payload_for
 from constraint_engine import load_layout,load_parts,validate
 import mission_constraints
 digest=hashlib.sha256(bridge.TARGET.read_bytes()).hexdigest()
 key=hashlib.sha256((digest+mission_constraints.revision()+VERSION).encode()).hexdigest()[:24]
 folder=SESSIONS/key;folder.mkdir(parents=True,exist_ok=True)
 manifest_path=folder/'manifest.json'
 if manifest_path.exists():return json.loads(manifest_path.read_text())
 py='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3'
 output=subprocess.run([py,str(ROOT/'saved_board_snapshot.py'),str(bridge.TARGET)],check=True,capture_output=True,text=True,timeout=20)
 snapshot=json.loads(output.stdout);payload=payload_for(snapshot)
 with tempfile.TemporaryDirectory() as directory:
  path=Path(directory)/'layout.json';path.write_text(json.dumps(payload['layout']));layout,warnings=load_layout(path)
 parts,notes=load_parts(ROOT.parents[1]/'missionpcb_review/native-six-parts.json');report=validate(layout,parts,warnings+notes).to_dict()
 findings=[]
 for finding in report['checks']:
  if finding['status']=='PASS':continue
  finding['kicad_refs']=[payload['kicad_refs'][ref] for ref in finding.get('subjects',[]) if ref in payload['kicad_refs']];findings.append(finding)
 glb=folder/'board.glb'
 result=subprocess.run([CLI,'pcb','export','glb','--force',*OPTIONS,'-o',str(glb),str(bridge.TARGET)],capture_output=True,text=True,timeout=60)
 if result.returncode or not glb.exists():raise ValueError('Saved-board render export failed: '+result.stderr[-500:])
 if hashlib.sha256(bridge.TARGET.read_bytes()).hexdigest()!=digest:raise ValueError('Saved board changed during export. Refresh preview.')
 coverage=inspect_export(glb,[p['ref'] for p in snapshot['parts']])
 data={'model_coverage':coverage,'id':key,'source_board':str(bridge.TARGET),'source_hash':digest,'revision':digest,'parts':snapshot['parts'],'glb':str(glb),'native_findings':findings,'summary':report['summary'],'mission':__import__('brief_store').current()['text'],'brief_revision':__import__('brief_store').current()['revision'],'source':'saved KiCad board; unsaved changes are not included','constraints_revision':mission_constraints.revision()}
 manifest_path.write_text(json.dumps(data,indent=2));return data

def push_preview(identifier):
 import re
 if not re.fullmatch(r'[0-9a-f]{24}',identifier):raise ValueError('Invalid preview ID.')
 path=SESSIONS/identifier/'manifest.json';data=json.loads(path.read_text())
 import mission_constraints
 if data.get('constraints_revision')!=mission_constraints.revision():raise ValueError('Mission constraints changed. Refresh the render before continuing.')
 if hashlib.sha256(bridge.TARGET.read_bytes()).hexdigest()!=data['source_hash']:raise ValueError('The saved board changed. Refresh the render before continuing.')
 result=dispatch('assembly_handoff',manifest=str(path));subprocess.run(['open','-a','Blender'],check=True);return result
