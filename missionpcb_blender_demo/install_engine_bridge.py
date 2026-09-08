"""Run in the existing working scene; --verify-only never saves."""
from pathlib import Path
import sys,json
import bpy
HERE=Path(__file__).resolve().parent
assert Path(bpy.data.filepath).name=='missionpcb_three_cad_components.blend'
for name in ['engine_bridge.py','engine_bundle.json','runtime.py']:
    text=bpy.data.texts.get(name) or bpy.data.texts.new(name);text.clear();text.write((HERE/name).read_text())
for key in list(sys.modules):
    if key.startswith('missionpcb_'):del sys.modules[key]
runtime=bpy.data.texts['runtime.py'].as_module()
runtime.register();bpy.context.scene['use_upstream_engine']=True
bridge=runtime.load_embedded('engine_bridge')
result=runtime.recalculate_constraints();n=len(bpy.data.objects)
first=json.loads(bpy.context.scene['engine_results_json'])
runtime.recalculate_constraints();second=json.loads(bpy.context.scene['engine_results_json'])
assert first['results']==second['results'] and len(bpy.data.objects)==n
obj=next(o for o in bpy.context.scene.objects if o.get('role')=='component' and o.get('component_id')=='Sensor' and o.get('layout_id')=='MissionPCB')
old=obj.location.copy();obj.location.x+=2;bpy.context.view_layer.update()
assert bridge.compute(runtime)['results']['MissionPCB']!=first['results']['MissionPCB']
obj.location=old;bpy.context.view_layer.update()
oldrot=obj.rotation_euler.copy();obj.rotation_euler.z=.12;bpy.context.view_layer.update()
try:bridge.compute(runtime)
except ValueError:pass
else:raise AssertionError('Arbitrary rotation accepted')
obj.rotation_euler=oldrot;bpy.context.view_layer.update();runtime.recalculate_constraints()
if '--verify-only' in sys.argv:
    poses={o.name:(o.location.copy(),o.rotation_euler.copy()) for o in bpy.context.scene.objects if o.get('role')=='component'}
    for degrees in (0,90,180,270):
        obj.rotation_euler.z=__import__('math').radians(degrees);bpy.context.view_layer.update();bridge.compute(runtime)
    obj.rotation_euler=oldrot;bpy.context.view_layer.update()
    previous=obj['component_id'];obj['component_id']='Unknown'
    try:bridge.compute(runtime)
    except ValueError:pass
    else:raise AssertionError('Unknown ID accepted')
    obj['component_id']=previous
    bridge.optimize(runtime)
    for name,(loc,rot) in poses.items():bpy.data.objects[name].location=loc;bpy.data.objects[name].rotation_euler=rot
    bpy.context.view_layer.update();runtime.recalculate_constraints()
if '--verify-only' not in sys.argv:
    runtime.export_results(HERE/'component_pass')
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('BRIDGE_VERIFIED',json.dumps({k:v['summary'] for k,v in first['results'].items()}),flush=True)
