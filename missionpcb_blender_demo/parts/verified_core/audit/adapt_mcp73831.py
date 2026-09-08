"""Drawing-adapt generic KiCad SOT23-5 body; never claim manufacturer CAD."""
import bpy,json,hashlib
from pathlib import Path
ROOT=Path('/Users/dhruvavutukury/Documents/ChatGPT/astra/missionpcb_blender_demo/parts')
OUT=ROOT/'verified_core/audit'
SRC=ROOT/'converted_models/SOT-23-5.normalized.glb'
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.unit_settings.scale_length=1.0
bpy.ops.import_scene.gltf(filepath=str(SRC));bpy.context.view_layer.update()
obj=next(o for o in scene.objects if o.type=='MESH')
assert len(obj.data.materials)==3
ids={i:set() for i in range(3)}
for poly in obj.data.polygons:ids[poly.material_index].update(poly.vertices)
body,pins,mark=ids[0],ids[1],ids[2]
assert not(body&pins or body&mark or pins&mark)
old_coords={v.index:tuple(v.co) for v in obj.data.vertices}
def bounds(indices):
 c=[obj.data.vertices[i].co*1000 for i in indices]
 lo=[min(v[k] for v in c) for k in range(3)];hi=[max(v[k] for v in c) for k in range(3)]
 return dict(min=lo,max=hi,dimensions=[hi[k]-lo[k] for k in range(3)])
before={name:bounds(group) for name,group in [('body',body),('pins',pins),('mark',mark)]}
assert abs(before['body']['min'][2]-.1)<.00001 and abs(before['body']['max'][2]-1.55)<.00001
for i in body:
 v=obj.data.vertices[i];v.co.z=(.1+(v.co.z*1000-.1)*(1.3/1.45))*.001
for i in mark:obj.data.vertices[i].co.z-=.15*.001
obj.data.update()
after={name:bounds(group) for name,group in [('body',body),('pins',pins),('mark',mark)]}
assert all(tuple(obj.data.vertices[i].co)==old_coords[i] for i in pins)
assert all(tuple(obj.data.vertices[i].co)[:2]==old_coords[i][:2] for i in old_coords)
assert abs(after['body']['dimensions'][2]-1.3)<.00001
assert abs(after['body']['min'][2]-.1)<.00001
assert max(v.co.z*1000 for v in obj.data.vertices)<=1.45
assert after['pins']==before['pins']
obj.name='DRAWING_ADAPTED_MCP73831_OT_SOT23_5'
obj['geometry_basis']='Drawing-adapted KiCad generic SOT-23-5. Not manufacturer CAD or exact production geometry.'
obj['drawing_url']='https://ww1.microchip.com/downloads/en/DeviceDoc/MCP73831-Family-Data-Sheet-DS20001984H.pdf'
obj['drawing_reference']='Page23, C04-091-OT Rev F Sheet2: body A2 max1.30mm, overall A max1.45mm, standoff A1 max.15mm'
obj['correction']='Body Z thickness1.45 to1.30mm about bottomZ.10mm; markingZ1.55 to1.40mm; every pin coordinate and every XY coordinate unchanged.'
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
result=OUT/'MCP73831_OT_drawing_adapted.normalized.glb'
bpy.ops.export_scene.gltf(filepath=str(result),export_format='GLB',use_selection=True,export_cameras=False,export_lights=False,export_extras=True)
provenance=dict(status='DRAWING_ADAPTED_GENERIC_PACKAGE_NOT_MANUFACTURER_MODEL',source=str(SRC),source_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),artifact=str(result),artifact_sha256=hashlib.sha256(result.read_bytes()).hexdigest(),drawing_url=obj['drawing_url'],drawing_reference=obj['drawing_reference'],correction=obj['correction'],units='GLB metres; dimensions in this report mm',before=before,after=after,overall_bounds= bounds(set(old_coords)),checks=dict(pin_vertices_exactly_unchanged=True,all_xy_vertices_exactly_unchanged=True,body_bottom_unchanged=True,body_thickness_1_30=True,overall_height_at_most_1_45=True))
(OUT/'MCP73831_OT_adaptation.json').write_text(json.dumps(provenance,indent=2)+'\n')
print('MCP73831_DRAWING_ADAPTATION_PASS',str(result),provenance['overall_bounds'],flush=True)
