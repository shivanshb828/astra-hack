import bpy,json,math
from pathlib import Path
from mathutils import Vector
r=Path(__file__).resolve().parent
for name in ['ecg-chest-enclosure','human-chest-reference']:
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(r/(name+'.glb')))
 pts=[o.matrix_world@v.co for o in bpy.context.scene.objects if o.type=='MESH' for v in o.data.vertices]
 low=Vector([min(p[i] for p in pts) for i in range(3)]);high=Vector([max(p[i] for p in pts) for i in range(3)]);size=high-low
 if name.startswith('ecg'):assert abs(size.x-.120)<.00001 and abs(size.y-.054)<.00001,(name,list(size))
 else:assert abs(size.z-.430)<.00001,(name,list(size))
 print('VERIFIED_METERS',name,list(size))
 scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1000;scene.render.resolution_y=800;scene.render.resolution_percentage=100
 scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
 center=(high+low)/2;bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';camera.data.ortho_scale=max(size)*1.5
 camera.location=center+Vector((.12,-.16,.16) if name.startswith('ecg') else (.35,-.8,.15));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
 scene.render.filepath=str(r/(name+'.png'));bpy.ops.render.render(write_still=True)
