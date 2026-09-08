"""Blender integration checks for decorative workbench isolation and embedded runtime."""
import bpy
import json

scene=bpy.context.scene
module=bpy.data.texts['runtime.py'].as_module()
module.register()
col=bpy.data.collections.get('05_Workbench_Environment')
assert col and len(col.objects)>20
assert all(o.get('role')=='decoration' and not o.get('layout_id') and not o.get('dynamic_overlay') for o in col.objects)
assert all(o.parent is None or o.parent in list(col.objects) for o in col.objects)
assert not any(o.type=='LIGHT' for o in col.objects)
assert bpy.data.objects['Camera_Workbench'].type=='CAMERA'
assert scene.render.engine=='BLENDER_EEVEE'
assert 'Camera_Workbench' in bpy.data.texts['runtime.py'].as_string()
before=module.signature()
snapshots={name:module.extract_scene_snapshot(name) for name in ['Naive','MissionPCB']}
results=module.recalculate_constraints()
assert [r['status'] for r in results['Naive']['categories']]==['PASS']+['FAIL']*7
assert results['MissionPCB']['status']=='PASS'
prop=next(o for o in col.objects if o.type=='MESH');old=prop.location.copy()
prop.location.x+=500;bpy.context.view_layer.update()
assert module.signature()==before
assert {name:module.extract_scene_snapshot(name) for name in snapshots}==snapshots
assert module.recalculate_constraints()==results
prop.location=old;bpy.context.view_layer.update()
count=len(bpy.data.objects)
for i in range(2):assert module.recalculate_constraints()==results
assert len(bpy.data.objects)==count
bpy.ops.missionpcb.example_failure()
assert json.loads(scene['results_json'])['MissionPCB']['categories'][2]['status']=='FAIL'
bpy.ops.missionpcb.restore()
assert json.loads(scene['results_json'])['MissionPCB']['status']=='PASS'
module.unregister()
print('WORKBENCH_INTEGRATION_PASS: isolated decoration, embedded runtime, optional camera, stable recalculation, failure and restore')
