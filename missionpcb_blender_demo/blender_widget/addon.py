"""MissionPCB widget adapter. Execute inside the existing Blender scene."""
import bpy,json,time,math,re,os,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
IPC=ROOT/'ipc';IPC.mkdir(exist_ok=True)
import sys,importlib
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
_assembly=None
OWNER=None
SESSION=None
SCENE=None
def connection():
 global SESSION,SCENE
 identity=(bpy.data.filepath,bpy.context.scene.as_pointer())
 if SCENE!=identity:
  SCENE=identity;SESSION=uuid.uuid4().hex
 return dict(instance=OWNER,session=SESSION,pid=os.getpid())
def assembly_module():
 global _assembly
 if _assembly is None:
  _assembly=importlib.import_module("assembly");importlib.reload(_assembly)
 return _assembly
def assembly_active():return bool(bpy.context.scene.get("missionpcb_assembly"))
TARGET=ROOT.parent/'component_pass/missionpcb_three_cad_components.blend'
def atomic(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,allow_nan=False));tmp.replace(path)
def runtime():return bpy.data.texts['runtime.py'].as_module()
def guard():
 if Path(bpy.data.filepath).resolve()!=TARGET.resolve():raise ValueError('Open the canonical MissionPCB scene first')
 if not bpy.context.scene.get('use_upstream_engine'):raise ValueError('MissionPCB engine is not installed')
def parts():return {o['component_id']:o for o in bpy.context.scene.objects if o.get('role')=='component' and o.get('layout_id')=='MissionPCB'}
def snapshot():
 if assembly_active():
  assembly=assembly_module()
  if assembly.signature()!=bpy.context.scene.get('assembly_signature'):assembly.check()
  return dict(heartbeat=time.time(),file=bpy.data.filepath,assembly_api=1,assembly=assembly.snapshot(),**connection())
 guard();r=runtime();payload=json.loads(bpy.context.scene.get('engine_results_json','{}'))
 return dict(heartbeat=time.time(),file=bpy.data.filepath,assembly_api=1,signature=r.signature(),stale=r.signature()!=bpy.context.scene.get('validated_signature'),parts=[dict(ref=k,position=list(o.location)) for k,o in parts().items()],result=payload.get('results',{}).get('MissionPCB'),**connection())
def highlight():
 result=json.loads(bpy.context.scene['engine_results_json'])['results']['MissionPCB']
 subjects={s for c in result['checks'] if c['status']=='FAIL' for s in c.get('subjects',[])}
 collection=bpy.data.collections.get('MissionPCB Widget Flags')
 if not collection:
  collection=bpy.data.collections.new('MissionPCB Widget Flags');bpy.context.scene.collection.children.link(collection)
 for obj in list(collection.objects):
  mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
  if mesh.users==0:bpy.data.curves.remove(mesh)
 for ref,obj in parts().items():
  if ref not in subjects:continue
  curve=bpy.data.curves.new('Attention '+ref,'CURVE');curve.dimensions='3D';curve.bevel_depth=.15;curve.bevel_resolution=0
  spline=curve.splines.new('POLY');spline.points.add(47)
  for i,p in enumerate(spline.points):
   a=i*2*math.pi/48;p.co=(5*math.cos(a),5*math.sin(a),0,1)
  spline.use_cyclic_u=True
  flag=bpy.data.objects.new('ATTENTION '+ref,curve);collection.objects.link(flag);flag.location=obj.matrix_world.translation;flag.location.z+=float(obj.dimensions.z)+1;flag.show_in_front=True;flag.color=(1,.04,.02,1)
  mat=bpy.data.materials.get('Widget Attention Red') or bpy.data.materials.new('Widget Attention Red');mat.diffuse_color=(1,.04,.02,1);curve.materials.append(mat)
def execute(command):
 if command.get('action','').startswith('assembly_'):return assembly_module().execute(command)
 if assembly_active():
  assembly=assembly_module()
  action=command['action']
  if action=='check':return assembly.check()
  if action=='inspect':return 'Read ECG assembly state.'
  if action=='focus':return assembly.focus('part-'+{'MCU':'U1','Sensor':'U2','RF':'U3','Regulator':'U4','Driver':'U5','Battery':'J1'}.get(command.get('ref'),command.get('ref','')))
 guard();action=command['action'];r=runtime()
 if action=='check':r.recalculate_constraints();highlight();return 'Completed implemented geometry/policy checks. DRC/ERC, thermal physics and patient safety are not validated.'
 if action=='focus':
  obj=parts().get(command.get('ref'))
  if obj is None:raise ValueError('Unknown component')
  bpy.ops.object.select_all(action='DESELECT');obj.hide_set(False);obj.select_set(True);bpy.context.view_layer.objects.active=obj
  for area in bpy.context.screen.areas:
   if area.type=='VIEW_3D':
    region=next((r for r in area.regions if r.type=='WINDOW'),None)
    if region:
     with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_selected(use_all_regions=False)
  return 'Focused '+command['ref']
 if action=='inspect':return 'Read current scene. No objects changed.'
 raise ValueError('Unsupported Blender action')
def tick():
 # A newer adapter owns the shared queue. Retire old timers, including those
 # surviving a file load or running in another Blender window.
 if OWNER:
  try:
   if (IPC/'owner').read_text()!=OWNER:return None
  except OSError:return None
  connection()
 pending=IPC/'command.json'
 if pending.exists():
  cmd=None
  try:
   cmd=json.loads(pending.read_text());pending.unlink()
   if not isinstance(cmd,dict) or not re.fullmatch(r'[0-9a-f]{32}',str(cmd.get('id',''))):raise ValueError('Invalid command ID')
   created=cmd.get('created')
   if isinstance(created,bool) or not isinstance(created,(int,float)) or not math.isfinite(created) or not 0<=time.time()-created<=15:raise ValueError('Expired or invalid command')
   if SESSION and cmd.get('session')!=SESSION:raise ValueError('Blender file or scene changed. Refresh the widget and retry.')
   message=execute(cmd)
   current=snapshot();atomic(IPC/'state.json',current)
   atomic(IPC/(cmd['id']+'.json'),dict(ok=True,message=message,state=current))
  except Exception as e:
   if pending.exists():pending.unlink()
   if isinstance(cmd,dict) and re.fullmatch(r'[0-9a-f]{32}',str(cmd.get('id',''))):
    atomic(IPC/(cmd['id']+'.json'),dict(ok=False,message=str(e)))
   else:atomic(IPC/'last_error.json',dict(error=str(e),time=time.time()))
 try:atomic(IPC/'state.json',snapshot())
 except Exception as e:atomic(IPC/'state.json',dict(heartbeat=time.time(),file=bpy.data.filepath,error=str(e)))
 return .75
def start():
 global OWNER
 if not assembly_active():guard()
 old=bpy.app.driver_namespace.get('missionpcb_widget_timer')
 if old and bpy.app.timers.is_registered(old):bpy.app.timers.unregister(old)
 OWNER=uuid.uuid4().hex
 (IPC/'owner').write_text(OWNER)
 bpy.app.driver_namespace['missionpcb_widget_timer']=tick;bpy.app.timers.register(tick,first_interval=.1,persistent=True);tick()
 print('MISSIONPCB_BLENDER_WIDGET_READY')
if __name__=='__main__':start()
