"""Build a separate reviewable wearable assembly; never opens or replaces live CAD."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent/'blender_widget'))
import assembly
bpy.ops.wm.read_factory_settings(use_empty=True)
manifest=OUT.parent/'kicad_bridge/runtime/wearable-assembly-source.json'
assembly.handoff(manifest)
scene=bpy.context.scene;scene['mission']='ECG chest patch · 14-day target · geometry review concept'
root,_=assembly.import_asset(OUT/'ecg-chest-enclosure.glb','ECG concept enclosure','m','product','enclosure')
# Imported asset floor includes electrodes at -0.8mm. Pocket begins 2.3mm above it.
pocket=assembly.region('board-bay',[0,0,5.8],[100,40,7],'Declared 100 × 40 × 7 mm enclosure interior')
pocket.parent=assembly.objects()['device']
board=assembly.objects()['board'];board.location.z=2.5;board['assigned_region']='region-board-bay'
body,_=assembly.import_asset(OUT/'human-chest-reference.glb','Bare chest · MakeHuman CC0','m','body','body')
# import_asset centers XY and places crop floor at zero; use midpoint of crop for chest.
lo,hi=assembly.bounds(body);z=(lo.z+hi.z)/2;tree=assembly.world_bvh(body)
hit=tree.ray_cast(Vector((0,-500,z)),Vector((0,1,0)),1000)[0]
if hit is None:raise ValueError('Chest surface not found')
region=assembly.region('chest',[0,hit.y-10,z],[130,65,25],'Reference chest region; geometric fit only');region.rotation_euler.x=math.pi/2
bpy.context.view_layer.update()
assembly.place('device','region-chest')
# Ensure surface clearance without claiming adhesive conformity.
device=assembly.objects()['device']
for _ in range(100):
 bpy.context.view_layer.update()
 if not assembly.world_bvh(device).overlap(tree):break
 device.location.y-=1;region.location.y-=1
else:raise ValueError('Could not clear reference chest')
assembly.check();snapshot=assembly.snapshot()
assert not assembly.world_bvh(device).overlap(tree)
assert len(snapshot['model_coverage'].get('modeled_refs',[]))>=19
assert not snapshot['component_check_error'],snapshot['component_check_error']
assert all(f['status']=='PASS' for f in snapshot['findings']),snapshot['findings']
scene['asset_scope']='Concept enclosure and representative chest, actual saved KiCad PCB. No physiological solve.'
# Hide removable lid in viewport only to reveal the actual electronics.
for o in root.children_recursive:
 if 'Removable lid' in o.name:o.hide_set(True);o.hide_render=True
points=assembly.corners(device);center=sum(points,Vector())/len(points)
bpy.ops.object.camera_add(location=center+Vector((150,-250,190)));camera=bpy.context.object;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=210;scene.camera=camera
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.display.shading.color_type='MATERIAL';scene.display.shading.light='STUDIO';scene.display.shading.show_cavity=True
scene.render.filepath=str(OUT/'wearable-assembly.png')
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  area.spaces.active.region_3d.view_location=center;area.spaces.active.region_3d.view_rotation=camera.rotation_euler.to_quaternion();area.spaces.active.region_3d.view_distance=200;area.spaces.active.overlay.show_overlays=False
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'wearable-assembly.blend'))
bpy.ops.render.render(write_still=True)
(OUT/'assembly-verification.json').write_text(json.dumps(snapshot,indent=2));print('ASSEMBLY_VERIFIED',len(snapshot['objects']))
