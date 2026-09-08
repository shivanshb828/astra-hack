"""Run with Blender --background <file> --python-exit-code 1 --python this_file."""
import bpy
import json

scene=bpy.context.scene
ecg=scene.get('profile')=='ecg'
assert 'PCB_Naive' in bpy.data.objects, 'Missing generated PCB_Naive'
assert 'PCB_MissionPCB' in bpy.data.objects, 'Missing generated PCB_MissionPCB'
components=[o for o in scene.objects if o.get('role')=='component']
assert len(components)==12, f'Expected 12 independent bodies, got {len(components)}'
assert len({o.data.as_pointer() for o in components})==12, 'Component geometry unexpectedly linked'
assert all(o.type=='MESH' and not o.hide_select for o in components)
assert abs(scene.unit_settings.scale_length-.001)<1e-8
for name in ['00_Reference','01_Naive_Layout','02_MissionPCB_Layout','03_Constraint_Overlays','04_Cameras_Lights']:
    assert name in bpy.data.collections, name
for name in ['Camera_TopDown','Camera_Isometric','Camera_CloseConstraint']:
    assert bpy.data.objects[name].type=='CAMERA'
for name in ['PCB_Naive','PCB_MissionPCB']:
    assert all(abs(a-b)<.001 for a,b in zip(bpy.data.objects[name].dimensions,[72,38,1.6]))
assert 'runtime.py' in bpy.data.texts
module=bpy.data.texts['runtime.py'].as_module()
results=module.recalculate_constraints()
snapshot=module.extract_scene_snapshot('MissionPCB')
assert snapshot['enclosure']['min']==[-45,-25,0], 'Hidden reference transform must be layout-local'
assert snapshot['opening']['min']==[45,-5,3]
assert [r['status'] for r in results['Naive']['categories']]==(['PASS']+['FAIL']*7 if ecg else ['PASS','PASS']+['FAIL']*5)
assert [r['status'] for r in results['MissionPCB']['categories']]==['PASS']*(8 if ecg else 7)
counts=len(bpy.data.objects)
sensor=next(o for o in components if o['component_id']=='Sensor' and o['layout_id']=='MissionPCB'); original=sensor.location.copy()
sensor.location.x=25; sensor.location.y=-10
results=module.recalculate_constraints()
assert results['MissionPCB']['categories'][2]['status']=='FAIL'
assert sensor.location.x==25, 'Recalculation reset user placement'
sensor.location=original
results=module.recalculate_constraints()
assert results['MissionPCB']['status']=='PASS'
assert len(bpy.data.objects)==counts, 'Overlay refresh leaked objects'
root=bpy.data.objects['Root_MissionPCB']; origin=root.location.copy()
root.location.x+=100
assert module.recalculate_constraints()['MissionPCB']['status']=='PASS'
root.location=origin
module.recalculate_constraints()
# RF body scaling must not turn a fixed 22 mm antenna zone into a 33 mm zone.
rf=next(o for o in components if o['component_id']=='RF' and o['layout_id']=='MissionPCB'); rf.scale.x=1.5
bpy.ops.mesh.primitive_cube_add(size=.5,location=(root.location.x-65,root.location.y+10,3.7))
probe=bpy.context.object; probe['role']='conductor'; probe['layout_id']='MissionPCB'
bpy.context.view_layer.update()
snapshot=module.extract_scene_snapshot('MissionPCB')
engine=module.dependencies()[0]
row=next(r for r in engine.evaluate_constraints(snapshot)['checks'] if r['id']=='antenna')
assert row['status']=='PASS', 'RF scale incorrectly scaled the 22 mm keep-out rule'
bpy.data.objects.remove(probe,do_unlink=True); rf.scale.x=1
module.recalculate_constraints()
module.register(); module.register()
if ecg:
    for layout in ['Naive','MissionPCB']:
        assert len([o for o in scene.objects if o.get('role')=='patient_component' and o.get('layout_id')==layout])==3
        assert 'Skin_Facing_Surface_'+layout in bpy.data.objects
        assert 'Thin_LiPo_'+layout in bpy.data.objects
        for i,row in enumerate(results[layout]['categories']):
            assert bpy.data.objects[f'Row status {i} {layout}'].data.body==row['status']
            assert bpy.data.objects[f'Row label {i} {layout}'].data.body==row['category']
    # Restore is a real operation over seeded transforms, not cached PASS text.
    sensor.location.x=28;sensor.location.y=9;module.recalculate_constraints()
    bpy.ops.missionpcb.restore()
    assert json.loads(scene['results_json'])['MissionPCB']['status']=='PASS'
    assert tuple(sensor.location)==tuple(original)
    # Freshness marker responds before recalculation.
    sensor.location.x+=1;bpy.context.view_layer.update();module.freshness_timer()
    assert scene['constraints_stale']
    bpy.ops.missionpcb.restore()
    assert getattr(bpy.types,'MISSIONPCB_OT_example_failure',None), 'Missing deterministic demo-failure control'
    bpy.ops.missionpcb.example_failure()
    assert json.loads(scene['results_json'])['MissionPCB']['categories'][2]['status']=='FAIL'
    bpy.ops.missionpcb.restore()
    assert json.loads(scene['results_json'])['MissionPCB']['status']=='PASS'
module.unregister()
print('MISSIONPCB_INTEGRATION_PASS: objects, exact dimensions, fixture results, edit/recalculate/restore, root invariance, runtime registration')
