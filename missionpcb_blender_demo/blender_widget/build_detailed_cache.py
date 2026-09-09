"""Build a self-contained native Blender demo cache from the real KiCad export.

Run Blender on wearable-cad/wearable-assembly.blend with --python this file --
--manifest /path/to/manifest.json --profile /path/to/adopted-profile.json.
"""
import bpy,sys,json,argparse,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import assembly,pcb_presentation,native_views,housing
args=argparse.ArgumentParser();args.add_argument('--manifest',required=True);args.add_argument('--profile',required=True);args.add_argument('--output',default=str(ROOT.parent/'detailed-cache'))
options=args.parse_args(sys.argv[sys.argv.index('--')+1:]);output=Path(options.output);output.mkdir(parents=True,exist_ok=True)
profile=json.loads(Path(options.profile).read_text());profile['status']='adopted'
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
pcb_presentation.enable_existing(assembly)
assembly.handoff(options.manifest)
# Keep original uploaded/reference geometry as an archived source, then create
# the full-height CC0 reference explicitly requested by the user.
old=assembly.body_object()
if old:
 old['assembly_id']='archived-body';old['asset_role']='reference_body'
 for obj in [old,*old.children_recursive]:obj.hide_render=True;obj.hide_set(True)
scene['active_body_id']='body';assembly.body_reference();body=assembly.objects()['body']
body['source']='MakeHuman CC0 base surface, normalized to 1750 mm. Created reference geometry, not a user scan.'
for obj in assembly.meshes(body):
 for face in obj.data.polygons:face.use_smooth=True
 obj.data.materials.clear();obj.data.materials.append(pcb_presentation.finish('Anatomy · warm peach reference',(.72,.42,.29,1),0,.65))
print(housing.generate(profile),flush=True)
scene['mission']='ECG chest patch · adopted chest strap example · cached placement review'
scene['cache_profile']=json.dumps(profile);scene['cache_scope']='Native KiCad board and models; editable concept housing and cached cell envelope; CC0 body reference. No copper routing or physiology claimed.'
# Studio lighting remains native Blender data, packed in the saved project.
scene.world=bpy.data.worlds.new('MissionPCB studio world');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.24,.29,.33,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.24
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=.7
try:scene.view_settings.look='AgX - Medium High Contrast'
except TypeError:pass
for obj in list(scene.objects):
 if obj.type=='LIGHT':bpy.data.objects.remove(obj,do_unlink=True)
device=assembly.objects()['device'];board=assembly.objects()['board']
lo,hi=assembly.bounds(board,device.matrix_world);target=device.matrix_world@((lo+hi)/2)
for name,offset,power,size in [('Key',(-120,-100,220),180000,160),('Fill',(140,60,170),100000,130),('Rim',(-20,190,120),130000,110)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power*4;data.shape='DISK';data.size=size
 light=bpy.data.objects.new(name,data);scene.collection.objects.link(light);light.location=target+device.matrix_world.to_quaternion()@Vector(offset);light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
# Dimension/evidence notes stay outside package geometry.
label=pcb_presentation.text('Native board dimensions','72 x 38 mm  /  NATIVE KICAD PCB',(-35,-24,1),1.0,(.14,.19,.21,1),board)
label['is_presentation']=True
cell=assembly.objects().get('cached-cell')
if cell:
 label=pcb_presentation.text('Cell envelope evidence','150 mAh\n30 x 16 x 3.2 mm\nCACHED ENVELOPE',(-6,-5,1.8),.9,(.04,.05,.05,1),cell);label['is_presentation']=True
scene.render.resolution_x=1800;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
native_views.register()
initial=assembly.snapshot();assert not initial['component_check_error'],initial['component_check_error']
assert len([o for o in initial['objects'] if o.get('ref')])==20
for name in ('board','assembly','chest','exploded'):
 print(native_views.view(name),flush=True)
 scene.render.filepath=str(output/(name+'.png'));bpy.ops.render.render(write_still=True)
native_views.view('assembly');scene['presentation_view']='assembly'
# A named, self-contained snapshot is portable and quick to reopen.
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':area.spaces.active.show_region_ui=False
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(output/'missionpcb_detailed_assembly.blend'))
state=assembly.snapshot();(output/'state.json').write_text(json.dumps(state,indent=2))
manifest=json.loads(Path(options.manifest).read_text())
cache={'source_board':manifest['source_board'],'source_hash':manifest['source_hash'],'source_revision':manifest['revision'],'manifest':options.manifest,'profile':profile,'blender_file':str(output/'missionpcb_detailed_assembly.blend'),'views':['board','assembly','chest','exploded'],'modeled_refs':state['model_coverage']['modeled_refs'],'missing_model_refs':state['model_coverage']['missing_model_refs'],'scope':scene['cache_scope'],'verification':{'native_ref_count':20,'component_check_error':state['component_check_error'],'findings':state['findings']}}
(output/'cache-manifest.json').write_text(json.dumps(cache,indent=2));print('DETAILED_CACHE_SAVED',json.dumps(cache['verification']),flush=True)
