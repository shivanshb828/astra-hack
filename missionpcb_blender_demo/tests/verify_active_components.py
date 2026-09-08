"""Reopen verification for the canonical saved component scene."""
import json
from pathlib import Path
import sys
import bpy

root=Path(__file__).resolve().parents[1]
scene=bpy.context.scene
runtime=bpy.data.texts['runtime.py'].as_module()
runtime.register()
evidence=json.loads((root/'component_pass/active_import_verification.json').read_text())
assert scene.camera.name=='Camera_CAD_Closeup'
assert len(evidence['imports'])==12
for entry in evidence['imports']:
    obj=bpy.data.objects[entry['object']]
    assert all(abs(a-b)<.005 for a,b in zip(obj.dimensions,entry['dimensions_mm']))
    assert obj.get('cad_source_sha256')==entry['sha256']
    assert abs(runtime.bounds(obj,bpy.data.objects['Root_'+entry['layout']])['min'][2]-3.6)<.005
    assert not obj.hide_get()
assert scene.get('use_upstream_engine'), 'Saved scene is not integrated'
before=json.loads(scene['results_json'])
native_before=json.loads(scene['engine_results_json'])['results']
poses={o.name:list(o.location) for o in scene.objects if o.get('role')=='component'}
assert runtime.recalculate_constraints()==before
bpy.ops.missionpcb.example_failure()
assert json.loads(scene['engine_results_json'])['results']['MissionPCB']['summary']['FAIL']>native_before['MissionPCB']['summary']['FAIL']
bpy.ops.missionpcb.restore()
assert json.loads(scene['results_json'])==before
assert json.loads(scene['engine_results_json'])['results']==native_before
assert all(list(bpy.data.objects[name].location)==loc for name,loc in poses.items())
assert all(o.hide_render for o in scene.objects if any(c.name=='03_Constraint_Overlays' for c in o.users_collection))
scene.camera=bpy.data.objects['Camera_Workbench']; runtime.apply_presentation_visibility()
assert any(not o.hide_render for o in scene.objects if any(c.name=='03_Constraint_Overlays' for c in o.users_collection))
scene.camera=bpy.data.objects['Camera_CAD_Closeup']; runtime.apply_presentation_visibility()
report=dict(status='PASS',checks=['12 component instances survive save/reopen','dimensions and mounting unchanged','recalculation matches saved results','failure/reset remains interactive','inspection overlays restore between views'],categories={k:[dict(category=r['category'],status=r['status']) for r in v['categories']] for k,v in before.items()})
(root/'component_pass/reopen_verification.json').write_text(json.dumps(report,indent=2)+'\n')
if '--render' in sys.argv:
    scene.render.filepath=str(root/'component_pass/imported_parts.png')
    bpy.ops.render.render(write_still=True)
print('SAVED_COMPONENT_SCENE_PASS',json.dumps(report),flush=True)
