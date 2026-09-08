"""Run with Blender --background combined-pcb/missionpcb_native_workbench.blend --python this_file."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import assembly,pcb_presentation
scene=bpy.context.scene
assert scene.get('presentation_style')=='native_pcb'
manifest=json.loads(Path(scene['handoff_manifest']).read_text())
refs={o['kicad_ref']:o for o in assembly.objects().values() if o.get('kicad_ref')}
assert set(refs)=={p['ref'] for p in manifest['parts']}
assert len(refs)==20
assert refs['L1'].get('missing_model') and not assembly.meshes(refs['L1'])
board=assembly.objects()['board'];lo,hi=assembly.bounds(board,board.matrix_world)
enclosure=assembly.objects()['enclosure'];a,b=assembly.bounds(enclosure,board.matrix_world)
assert abs((a.x+b.x)/2)<.01 and abs((a.y+b.y)/2)<.01,'Enclosure and PCB centres diverged'
assert b.x-a.x<=100.01,'Presentation geometry included in product bounds'
assert abs(hi.x-lo.x-72)<.01 and abs(hi.y-lo.y-38)<.01
for ref,obj in refs.items():
 row=json.loads(obj['native_baseline']);position=(board.matrix_world.inverted()@obj.matrix_world).translation
 assert abs(position.x-(row['x_mm']-136))<.01,(ref,position,row)
 assert abs(position.y-(119-row['y_mm']))<.01,(ref,position,row)
assert not scene.get('component_check_error')
assert any(o.get('severity')=='FAIL' for o in scene.objects)
assert any(o.get('severity')=='WARN' for o in scene.objects)
count=sum(bool(o.get('is_flag')) for o in scene.objects)
before=scene['native_findings'];obj=refs['U2'];original=obj.location.copy();obj.location.x+=8
bpy.context.view_layer.update();assembly.check()
assert scene['native_findings']!=before,'Component move did not change computed findings'
obj.location=original;bpy.context.view_layer.update();assembly.check()
assert scene['native_findings']==before,'Restoring component did not restore findings'
assert sum(bool(o.get('is_flag')) for o in scene.objects)==count,'Repeated check leaked flags'
assert all('ring' not in o.name.lower() and 'beacon' not in o.name.lower() for o in scene.objects if o.get('is_flag'))
enclosure=assembly.objects()['enclosure'];pose=enclosure.matrix_world.copy();camera=scene.camera
assembly.handoff(scene['handoff_manifest'])
assert assembly.objects()['enclosure']==enclosure and enclosure.matrix_world==pose
assert scene.camera==camera and scene['native_findings']==before
assert len([o for o in assembly.objects().values() if o.get('kicad_ref')])==20
assert not scene.get('component_check_error')
print('PCB_PRESENTATION_VERIFIED: 20 native refs; real 72x38 mm board; red/amber flags; component edits recompute; repeat import preserves enclosure/camera; missing L1 explicit.',flush=True)
