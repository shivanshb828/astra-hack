"""Verify the native cached assembly without editing the user's current project."""
import bpy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import assembly,native_views
scene=bpy.context.scene;items=assembly.objects()
refs={o['kicad_ref']:o for o in items.values() if o.get('kicad_ref')}
assert len(refs)==20 and refs['L1']['missing_model']
assert list(items['generated-housing']['interior_mm'])==[100,40,7]
assert not scene.get('component_check_error')
before=scene['native_findings'];fit=scene['assembly_checks']
pose=items['board'].location.copy()
native_views.view('exploded')
assert (items['board'].location-pose).length>15
assert scene['assembly_checks']==fit,'Presentation changed assembled fit'
native_views.view('board')
assert (items['board'].location-pose).length<.001
assert all(o.hide_render for o in assembly.meshes(assembly.body_object()))
native_views.view('chest')
assert all(not o.hide_render for o in assembly.meshes(assembly.body_object()))
assert all(not o.hide_render for o in assembly.meshes(items['board']))
original=refs['U2'].location.copy();refs['U2'].location=refs['U4'].location.copy()
bpy.context.view_layer.update();assembly.check()
assert scene['native_findings']!=before,'Real component move did not change checks'
assert any(o.get('severity')=='FAIL' for o in scene.objects)
refs['U2'].location=original;bpy.context.view_layer.update();assembly.check()
assert scene['native_findings']==before
native_views.add_comment('fit-board','Verification note: inspect mounting clearance.','board')
assert json.loads(scene['engineering_comments'])[-1]['object']=='board'
assert any(o.get('note_id') for o in scene.objects)
assert not scene.get('component_check_error')
print('DETAILED_CACHE_VERIFIED: 20 references; explicit missing L1; 100x40x7 interior; reversible views; assembled fit stable; dynamic red flags; native note persistence. Strap/body intersection remains flagged.')
