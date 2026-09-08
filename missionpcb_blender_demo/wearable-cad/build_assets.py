"""Generate editable concept CAD and crop existing CC0 reference anatomy."""
import bpy,math,json,bmesh
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001
scene.unit_settings.length_unit='MILLIMETERS'
def outline(w,h,r):
 points=[]
 for cx,cy,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
  for i in range(17):
   a=math.radians(start+i*90/16);points.append((cx+r*math.cos(a),cy+r*math.sin(a)))
 return points
def shape(name,rings,caps,color):
 n=len(rings[0][0]);verts=[(x,y,z) for ring,z in rings for x,y in ring];faces=[]
 for j in range(len(rings)-1):
  faces.extend((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n))
 if caps:faces.extend([tuple(reversed(range(n))),tuple((len(rings)-1)*n+i for i in range(n))])
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update();obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj)
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges),name;bm.to_mesh(mesh);bm.free()
 mat=bpy.data.materials.new(name);mat.diffuse_color=color;obj.data.materials.append(mat);return obj
outer=outline(104,44,7);inner=outline(100,40,5)
base=shape('ECG enclosure base · 2 mm walls',[(inner,1.5),(inner,8.5),(outer,8.5),(outer,0)],True,(.78,.85,.89,1))
lid=shape('Removable lid · 1.5 mm',[(outer,8.5),(outer,10)],True,(.9,.95,.96,1))
adhesive=shape('Adhesive carrier · concept',[(outline(120,54,14),-.5),(outline(120,54,14),0)],True,(.55,.72,.77,1))
for x in (-40,40):
 bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=8,depth=.3,location=(x,0,-.65));bpy.context.object.name='Electrode contact concept '+str(x)
for o in scene.objects:o['provenance']='Generated editable concept; no sealing, retention, contact-material or manufacturing qualification'
scene['interior_mm']=[100,40,7];scene['exterior_mm']=[104,44,10]
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ecg-chest-enclosure.blend'))
for o in scene.objects:o.matrix_world=__import__('mathutils').Matrix.Scale(.001,4)@o.matrix_world
bpy.ops.export_scene.gltf(filepath=str(OUT/'ecg-chest-enclosure.glb'),export_format='GLB',export_apply=True)
for o in scene.objects:o.matrix_world=__import__('mathutils').Matrix.Scale(1000,4)@o.matrix_world
for obj,name in [(base,'enclosure-base'),(lid,'enclosure-lid')]:
 bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
 bpy.ops.wm.stl_export(filepath=str(OUT/(name+'.stl')),export_selected_objects=True,apply_modifiers=True)
# A separate anatomical asset: no live scene is replaced.
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001
source=OUT.parent/'blender_widget/assets/body-surface.obj'
bpy.ops.wm.obj_import(filepath=str(source));meshes=[o for o in scene.objects if o.type=='MESH']
points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices];lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)]);factor=1750/(hi.z-lo.z)
for o in meshes:
 for v in o.data.vertices:v.co=(o.matrix_world@v.co-Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z)))*factor
 o.matrix_world.identity();bm=bmesh.new();bm.from_mesh(o.data)
 for z,normal in [(1080,(0,0,-1)),(1510,(0,0,1))]:
  bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.0001,plane_co=(0,0,z),plane_no=normal,clear_outer=True,clear_inner=False)
 for x,normal in [(-245,(-1,0,0)),(245,(1,0,0))]:
  bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.0001,plane_co=(x,0,0),plane_no=normal,clear_outer=True,clear_inner=False)
 bm.to_mesh(o.data);bm.free()
 for polygon in o.data.polygons:polygon.use_smooth=True
 o['provenance']='MakeHuman CC0; scaled to 1750mm stature then cropped; representative, not patient specific'
 o.name='Bare chest reference · MakeHuman CC0'
 mat=bpy.data.materials.new('Chest reference');mat.diffuse_color=(.52,.39,.32,1);o.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'human-chest-reference.blend'))
for o in scene.objects:o.matrix_world=__import__('mathutils').Matrix.Scale(.001,4)@o.matrix_world
bpy.ops.export_scene.gltf(filepath=str(OUT/'human-chest-reference.glb'),export_format='GLB',export_apply=True)
for o in scene.objects:o.matrix_world=__import__('mathutils').Matrix.Scale(1000,4)@o.matrix_world
bpy.ops.wm.obj_export(filepath=str(OUT/'human-chest-reference.obj'))
manifest={'enclosure':{'interior_mm':[100,40,7],'exterior_mm':[104,44,10],'wall_mm':2,'base_mm':1.5,'lid_mm':1.5,'source':'Generated editable concept','watertight_base_and_lid':True,'limitations':['No sealing/retention design','No battery or PCB mounting features','Electrodes and adhesive are conceptual geometry; materials unqualified']},'chest':{'source':'https://github.com/makehumancommunity/makehuman/blob/master/makehuman/data/3dobjs/base.obj','license':'CC0-1.0','height_normalization_mm':1750,'crop_z_mm':[1080,1510],'crop_x_mm':[-245,245],'scope':'Representative surface geometry, not physiological simulation'}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2));print('WEARABLE_CAD_VERIFIED',json.dumps(manifest))
