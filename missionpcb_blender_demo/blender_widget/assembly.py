"""Editable ECG product assembly, explicit mounting regions and geometry checks."""
import bpy,json,math,hashlib
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent

def active():return bool(bpy.context.scene.get('missionpcb_assembly'))
def objects():return {o['assembly_id']:o for o in bpy.context.scene.objects if o.get('assembly_id')}
def body_object():
 items=objects();selected=items.get(bpy.context.scene.get('active_body_id','body'))
 return selected if selected and selected.get('asset_role')=='body' else next((o for o in items.values() if o.get('asset_role')=='body'),None)
def vector(value,positive=False):
 if not isinstance(value,list) or len(value)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>10000 or (positive and x<=0) for x in value):raise ValueError('Expected three finite millimeter values (maximum 10000).')
 return Vector(value)
def empty(name,identifier,parent=None):
 o=bpy.data.objects.new(name,None);bpy.context.scene.collection.objects.link(o);o['assembly_id']=identifier;o.parent=parent;return o
def meshes(root):return [o for o in [root,*root.children_recursive] if o.type=='MESH' and not o.get('is_flag') and not o.get('region') and not o.get('is_presentation')]
def corners(root,frame=None):
 transform=frame.inverted() if frame is not None else Matrix.Identity(4)
 return [transform@o.matrix_world@Vector(c) for o in meshes(root) for c in o.bound_box]
def bounds(root,frame=None):
 pts=corners(root,frame)
 if not pts:raise ValueError('Object has no mesh geometry.')
 return Vector([min(p[i] for p in pts) for i in range(3)]),Vector([max(p[i] for p in pts) for i in range(3)])
def material(name,color):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.diffuse_color=color;return m
def box(name,location,size,parent=None,color=(.6,.65,.7,1)):
 bpy.ops.mesh.primitive_cube_add(size=1);o=bpy.context.object;o.name=name;o.location=location;o.dimensions=size
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.parent=parent;o.data.materials.append(material(name+' finish',color));return o

def import_asset(path,label,units='mm',role='product',identifier=None):
 path=Path(path).resolve()
 if units not in ('mm','m'):raise ValueError('Units must be mm or m.')
 if path.suffix.lower() not in ('.glb','.obj','.stl','.ply','.blend'):raise ValueError('Unsupported CAD format; export STEP as GLB/STL first.')
 before=set(bpy.data.objects)
 try:
  ext=path.suffix.lower()
  if ext=='.glb':bpy.ops.import_scene.gltf(filepath=str(path))
  elif ext=='.obj':bpy.ops.wm.obj_import(filepath=str(path))
  elif ext=='.stl':bpy.ops.wm.stl_import(filepath=str(path))
  elif ext=='.ply':bpy.ops.wm.ply_import(filepath=str(path))
  else:
   with bpy.data.libraries.load(str(path),link=False) as (source,target):target.objects=source.objects
   for o in target.objects:
    if o:bpy.context.scene.collection.objects.link(o)
  new=set(bpy.data.objects)-before
  if not any(o.type=='MESH' for o in new):raise ValueError('File contains no mesh geometry.')
  root=empty(label,identifier or 'asset-'+__import__('uuid').uuid4().hex[:10],objects().get('device') if role=='product' else None)
  for o in new:
   if o.parent not in new:o.parent=root
  # GLTF is standardized in meters. OBJ/STL/PLY use the declared source unit.
  factor=1 if ext=='.glb' else 1000 if units=='m' else 1
  root.scale=(factor,)*3;root['asset_role']=role;root['source']=str(path)
  root['source_units']='m' if ext=='.glb' else units
  bpy.context.view_layer.update()
  lo,hi=bounds(root,root.parent.matrix_world if root.parent else None);root.location-=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
  bpy.context.view_layer.update();return root,new
 except Exception:
  for o in set(bpy.data.objects)-before:bpy.data.objects.remove(o,do_unlink=True)
  raise

def scene_setup():
 scene=bpy.data.scenes.new('MissionPCB · ECG chest assembly');scene['missionpcb_assembly']=True
 bpy.context.window.scene=scene
 scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001;scene.unit_settings.length_unit='MILLIMETERS'
 scene.world=bpy.data.worlds.new('ECG neutral world');scene.world.color=(.14,.14,.14)
 scene['mission']='Single-lead ECG chest patch · 7-day continuous wear · BLE · sealed rechargeable enclosure · pogo charging'
 empty('ECG chest patch','device')
 return scene

def handoff(manifest):
 data=json.loads(Path(manifest).read_text());old=bpy.context.scene
 existing=active();scene=old if existing else scene_setup();previous=objects().get('board') if existing else None
 before=set(scene.objects);old_properties=dict(scene.items())
 try:
  board,imported=import_asset(data['glb'],'Confirmed KiCad PCB','m','product','board')
  if scene.get('presentation_style')=='native_pcb':
   import pcb_presentation
   pcb_presentation.rebase_import(board)
  board['asset_role']='electronics'
  if previous:
   board.matrix_basis=previous.matrix_basis.copy()
   if previous.get('assigned_region'):board['assigned_region']=previous['assigned_region']
  else:board.location.z=2
  bpy.context.view_layer.update()
  refs={p['ref']:p for p in data['parts']}
  for o in imported:
   ref=o.name.split('.')[0]
   if ref in refs:
    o['kicad_ref']=ref;o['assembly_id']='part-'+ref;o['asset_role']='component';o['value']=refs[ref]['value']
    local=board.matrix_world.inverted()@o.matrix_world
    o['native_baseline']=json.dumps(refs[ref]);o['import_location']=list(local.translation);o['import_rotation_z']=local.to_euler().z
  # Keep every native reference in the checker, even when no package mesh exported.
  exported={o.get('kicad_ref') for o in imported}
  lo,hi=bounds(board,board.matrix_world);center=(lo+hi)/2
  for ref,row in refs.items():
   if ref in exported:continue
   anchor=empty(ref+' · missing package model','part-'+ref,board)
   anchor['kicad_ref']=ref;anchor['value']=row['value'];anchor['asset_role']='component';anchor['missing_model']=True
   anchor.location=(row['x_mm']-136+center.x,119-row['y_mm']+center.y,lo.z+1.645)
   anchor['native_baseline']=json.dumps(row);anchor['import_location']=list(anchor.location);anchor['import_rotation_z']=0
  scene['model_coverage']=json.dumps(data.get('model_coverage',{}))
  scene['handoff_manifest']=str(manifest);scene['board_revision']=data['revision'];scene['source_hash']=data['source_hash'];scene['mission']=data['mission'];scene['native_findings']=json.dumps(data.get('native_findings',[]))
  if not existing:region('board-bay',[0,0,6],[76,42,12],'PCB pocket from ECG demo brief','device')
 except Exception:
  for o in set(scene.objects)-before:bpy.data.objects.remove(o,do_unlink=True)
  if not existing:
   bpy.context.window.scene=old;bpy.data.scenes.remove(scene)
  else:
   for key in list(scene.keys()):del scene[key]
   for key,value in old_properties.items():scene[key]=value
  raise
 # Commit the replacement only after a complete import. Preserve body, CAD and regions.
 if previous:
  for o in [*previous.children_recursive,previous]:bpy.data.objects.remove(o,do_unlink=True)
 if scene.get('presentation_style')=='native_pcb':
  import pcb_presentation
  pcb_presentation.board_finish(board,__import__(__name__))
 record('Updated KiCad PCB; preserved enclosure and body placement' if previous else 'Confirmed KiCad board imported with reference IDs')
 bpy.context.view_layer.update();focus('board');check()
 return 'KiCad board updated in the ECG assembly.' if previous else 'Confirmed board imported. Widget is ready for ECG chest assembly.'

def region(name,center,size,reason,parent_id=None):
 if not isinstance(name,str) or not name.strip() or len(name)>80:raise ValueError('Name the mounting region (up to 80 characters).')
 center=vector(center);size=vector(size,True)
 identifier='region-'+name
 obj=objects().get(identifier)
 if obj is None:obj=empty(name,identifier,objects().get(parent_id))
 obj['region']=True;obj['size_mm']=list(size);obj['reason']=str(reason)[:1000];obj.location=center
 obj.empty_display_type='CUBE';obj.empty_display_size=1;obj.scale=size/2;obj.show_in_front=True;obj.color=(.4,.85,.2,1)
 return obj

def place(identifier,region_id):
 items=objects();obj=items.get(identifier);target=items.get(region_id)
 if obj is None or target is None or not target.get('region'):raise ValueError('Select an object and a named mounting region.')
 if target in obj.children_recursive:raise ValueError('Cannot place an assembly inside its own region; choose the board or another region.')
 # Match region orientation without inheriting the display size scale.
 rotation=target.matrix_world.to_quaternion().to_matrix().to_4x4()
 scale=obj.matrix_world.to_scale();obj.matrix_world=Matrix.Translation(target.matrix_world.translation)@rotation@Matrix.Diagonal((*scale,1))
 bpy.context.view_layer.update();lo,hi=bounds(obj);obj.matrix_world.translation+=target.matrix_world.translation-(lo+hi)/2
 obj['assigned_region']=region_id
 bpy.context.view_layer.update();record('Placed '+obj.name+' in '+target.name);return check()

def record(reason):
 scene=bpy.context.scene;rows=json.loads(scene.get('timeline','[]'));rows.append({'reason':reason,'kind':'edit'});scene['timeline']=json.dumps(rows[-30:]);scene['assembly_checks']='[]'

def edit(identifier,position=None,rotation=None,dimensions=None):
 obj=objects().get(identifier)
 if obj is None or obj.get('region'):raise ValueError('Choose an editable assembly object.')
 # Validate every requested field before changing any transform.
 new_position=vector(position) if position is not None else None
 new_rotation=[math.radians(v) for v in vector(rotation)] if rotation is not None else None
 new_scale=None
 if dimensions is not None:
  if obj.get('asset_role') in ('electronics','component'):raise ValueError('PCB/component dimensions come from KiCad. Resize the product CAD instead.')
  wanted=vector(dimensions,True);lo,hi=bounds(obj,obj.matrix_world);size=hi-lo
  if min(size)<1e-8:raise ValueError('Cannot resize flat geometry.')
  new_scale=Vector([wanted[i]/size[i] for i in range(3)])
 if new_position is not None:obj.location=new_position
 if new_rotation is not None:obj.rotation_euler=new_rotation
 if new_scale is not None:obj.scale=new_scale
 bpy.context.view_layer.update();record('Edited '+obj.name);return check()

def focus(identifier):
 obj=objects().get(identifier)
 if obj is None:raise ValueError('Object not found.')
 bpy.ops.object.select_all(action='DESELECT')
 for o in meshes(obj) or [obj]:o.hide_set(False);o.select_set(True)
 bpy.context.view_layer.objects.active=obj
 areas=list(bpy.context.screen.areas)
 if not any(a.type=='VIEW_3D' for a in areas):
  max(areas,key=lambda a:a.width*a.height).type='VIEW_3D'
 for area in areas:
  if area.type=='VIEW_3D':
   area.spaces.active.clip_end=100000
   try:area.spaces.active.shading.type='MATERIAL'
   except TypeError:
    area.spaces.active.shading.type='SOLID';area.spaces.active.shading.color_type='MATERIAL'
   for reg in area.regions:
    if reg.type=='WINDOW':
     with bpy.context.temp_override(area=area,region=reg):bpy.ops.view3d.view_selected(use_all_regions=False)
 import red_flags
 red_flags.focus(identifier)
 return 'Focused '+obj.name

def demo_enclosure():
 if objects().get('enclosure'):focus('enclosure');return 'Showing the existing sample enclosure in Blender.'
 root=empty('Sample ECG shell · editable','enclosure',objects()['device']);root['asset_role']='product';root['source']='Generated sample, not user CAD'
 # Open top intentionally exposes electronics; user can model this geometry directly.
 box('Skin-side shell',[0,0,0],[82,48,1.4],root,(.72,.8,.85,1))
 for x in (-40.3,40.3):box('Side wall',[x,0,5.5],[1.4,48,11],root,(.72,.8,.85,1))
 for y in (-23.3,23.3):box('End wall',[0,y,5.5],[79.2,1.4,11],root,(.72,.8,.85,1))
 record('Added editable sample ECG enclosure');result=check();focus('enclosure');return result

def body_reference():
 if objects().get('body'):focus('body');return 'Showing the existing body reference in Blender.'
 # Import only the explicit body group, excluding MakeHuman helper geometry.
 source=ROOT/'assets/body.obj';target=ROOT/'assets/body-surface.obj'
 lines=[];keep=True
 for line in source.read_text().splitlines():
  if line.startswith('g '):keep=line.strip()=='g body'
  if not line.startswith(('f ','g ')) or keep:lines.append(line)
 target.write_text('\n'.join(lines)+'\n')
 body,_=import_asset(target,'Human body · MakeHuman CC0','mm','body','body')
 lo,hi=bounds(body);scale=1750/(hi.z-lo.z);body.scale*=scale
 bpy.context.view_layer.update();lo,hi=bounds(body);body.location-=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z));bpy.context.view_layer.update()
 for o in meshes(body):o.data.materials.clear();o.data.materials.append(material('Body reference',(.35,.45,.52,1)))
 body['reference_only']=True;body['source']='MakeHuman CC0 base mesh, normalized to 1750 mm; representative geometry, not patient-specific'
 # Ray at the anterior chest; the imported OBJ has Y-up converted to Blender Z-up.
 tree=world_bvh(body);hit=tree.ray_cast(Vector((0,-500,1300)),Vector((0,1,0)),1000)
 if hit[0] is None:raise ValueError('Body imported, but chest surface was not found. Define chest region manually.')
 center=hit[0]+Vector((0,-10,0));r=region('chest',list(center),[100,65,20],'Anterior chest placement area for ECG patch')
 r.rotation_euler.x=math.pi/2
 bpy.context.view_layer.update();record('Added body reference and chest mounting area');focus('body');return 'Body reference loaded with an anterior chest region.'

def fit_chest():
 items=objects()
 if 'body' not in items:body_reference();items=objects()
 if not meshes(items['device']):raise ValueError('Import the electronics first.')
 tree=world_bvh(items['body']);hits=[]
 for x in (-45,-22.5,0,22.5,45):
  for z in (1275,1287.5,1300,1312.5,1325):
   hit=tree.ray_cast(Vector((x,-500,z)),Vector((0,1,0)),1000)[0]
   if hit is not None:hits.append(hit.y)
 if not hits:raise ValueError('Chest surface could not be sampled.')
 target=items['region-chest'];target.location.y=min(hits)-12
 place('device','region-chest');device=items['device']
 for _ in range(50):
  if not world_bvh(device).overlap(tree):break
  device.location.y-=1;target.location.y-=1;bpy.context.view_layer.update()
 else:raise ValueError('Automatic chest fit did not resolve surface intersection. Adjust manually.')
 record('Placed ECG patch outside sampled chest surface; verified no triangle intersections')
 focus('device');return check()

def world_bvh(root):
 vertices=[];faces=[];deps=bpy.context.evaluated_depsgraph_get()
 for obj in meshes(root):
  evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();offset=len(vertices)
  try:
   vertices.extend(obj.matrix_world@v.co for v in mesh.vertices);faces.extend(tuple(offset+i for i in p.vertices) for p in mesh.polygons)
  finally:evaluated.to_mesh_clear()
 return BVHTree.FromPolygons(vertices,faces)

def flags(findings):
 if bpy.context.scene.get('presentation_style')=='native_pcb':
  import pcb_presentation
  pcb_presentation.draw(findings,__import__(__name__))
 else:
  import red_flags
  red_flags.draw(findings,__import__(__name__))
 import native_views
 native_views.draw_comments(__import__(__name__))

def live_component_findings():
 import sys,tempfile
 repo=ROOT.parents[1]
 for folder in (repo/'src',repo/'missionpcb_review',repo/'missionpcb_blender_demo/kicad_bridge'):
  if str(folder) not in sys.path:sys.path.insert(0,str(folder))
 from layout_adapter import payload_for
 from constraint_engine import load_layout,load_parts,validate
 board=objects()['board'];parts=[]
 # Unmodeled components still have authoritative saved KiCad placements.
 # Keep them in constraint evaluation; never fabricate render geometry.
 manifest=bpy.context.scene.get('handoff_manifest')
 baseline={}
 if manifest and Path(manifest).exists():
  data=json.loads(Path(manifest).read_text())
  baseline={p['ref']:p for p in data.get('parts',[])}
 modeled=set()
 for obj in objects().values():
  if not obj.get('kicad_ref'):continue
  original=json.loads(obj['native_baseline']);modeled.add(original['ref']);start=Vector(obj['import_location']);local=board.matrix_world.inverted()@obj.matrix_world
  pos=local.translation
  parts.append({**original,'x_mm':original['x_mm']+pos.x-start.x,'y_mm':original['y_mm']-(pos.y-start.y),'rotation_deg':(original['rotation_deg']-math.degrees(local.to_euler().z-obj.get('import_rotation_z',0)))%360})
 parts.extend(p for ref,p in baseline.items() if ref not in modeled)
 payload=payload_for({'parts':parts})
 with tempfile.TemporaryDirectory() as directory:
  path=Path(directory)/'layout.json';path.write_text(json.dumps(payload['layout']));layout,warnings=load_layout(path)
 library,notes=load_parts(repo/'missionpcb_review/native-six-parts.json');result=validate(layout,library,warnings+notes).to_dict()
 findings=[]
 for c in result['checks']:
  if c['status']=='PASS':continue
  c['kicad_refs']=[payload['kicad_refs'][ref] for ref in c.get('subjects',[]) if ref in payload['kicad_refs']]
  c['source']='Recomputed from current Blender component transforms; authored demo spacing policies'
  findings.append(c)
 return findings

def _check_assembled():
 bpy.context.view_layer.update();items=objects();findings=[]
 for identifier,obj in items.items():
  assignment=obj.get('assigned_region')
  if assignment:
   target=items.get(assignment)
   if target:
    # The region's unit cube is [-1,1] in its scaled local frame.
    points=[target.matrix_world.inverted()@mesh.matrix_world@Vector(c) for mesh in meshes(obj) if not mesh.get('outside_mounting_pocket') for c in mesh.bound_box];overflow=max([abs(p[i])-1 for p in points for i in range(3)],default=0)
    findings.append({'id':'fit-'+identifier,'object':identifier,'title':obj.name+' · '+('fits '+target.name if overflow<=1e-5 else 'outside '+target.name),'status':'PASS' if overflow<=1e-5 else 'FAIL','method':'mesh bounding-box corners in oriented region','reason':target.get('reason',''),'margin_note':'Declared mounting volume, not automatic interior reconstruction.'})
 board=items.get('board');body=body_object()
 if board and not board.get('assigned_region'):
  findings.append({'id':'unassigned-board','object':'board','title':'Assign PCB to its mounting pocket','status':'UNKNOWN','method':'placement workflow','reason':'Confirm where electronics fit in the enclosure.'})
 if body and items.get('device') and items['device'].get('assigned_region')=='region-chest':
  device=items['device'];overlap=world_bvh(device).overlap(world_bvh(body))
  findings.append({'id':'body-intersection','object':'device','title':'Device intersects body' if overlap else 'No body surface intersection','status':'FAIL' if overlap else 'PASS','method':'triangle surface intersection','reason':'ECG enclosure must remain outside the chest surface. Does not validate comfort, pressure, physiology or full containment.'})
 # Imported native board review remains identifiable; geometry checks do not replace it.
 scene=bpy.context.scene
 try:scene['native_findings']=json.dumps(live_component_findings());scene['component_check_error']=''
 except Exception as exc:scene['component_check_error']=str(exc)
 scene['assembly_checks']=json.dumps(findings);scene['assembly_signature']=signature()
 native=[{**f,'object':'part-'+ref,'title':ref+' · '+f.get('title',f.get('id','KiCad finding')),'status':f['status']} for f in json.loads(scene.get('native_findings','[]')) if f.get('status')!='PASS' for ref in f.get('kicad_refs',[])]
 flags(findings+native)
 native=json.loads(scene.get('native_findings','[]'))
 return 'Assembly fit: '+str(sum(f['status']=='FAIL' for f in findings))+' failures, '+str(sum(f['status']=='UNKNOWN' for f in findings))+' pending placements. Components: '+str(sum(f['status']=='FAIL' for f in native))+' flagged checks, '+str(sum(f['status'] in ('SKIP','WARN') for f in native))+' needing review.'

def check():
 import native_views
 with native_views.assembled_pose():result=_check_assembled()
 bpy.context.scene['assembly_signature']=signature()
 return result+(' Fit uses assembled positions; exploded offsets are presentation only.' if native_views.offsets() else '')

def mesh_signature(obj):
 import array
 coords=array.array('f',[0.0])*(3*len(obj.data.vertices));obj.data.vertices.foreach_get('co',coords)
 return hashlib.sha256(coords.tobytes()).hexdigest()
def signature():
 data=[(o.name,[list(row) for row in o.matrix_world],list(o.dimensions),mesh_signature(o) if o.type=='MESH' else 0) for o in bpy.context.scene.objects if not o.get('is_flag')]
 return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
def snapshot():
 scene=bpy.context.scene;rows=[]
 for identifier,o in objects().items():
  row={'id':identifier,'name':o.name,'role':'region' if o.get('region') else o.get('asset_role','assembly'),'position_mm':list(o.location),'rotation_deg':[math.degrees(v) for v in o.rotation_euler],'region':o.get('assigned_region'),'ref':o.get('kicad_ref'),'value':o.get('value',''),'missing_model':bool(o.get('missing_model')),'selected':o.select_get(),'source':o.get('source','')}
  if meshes(o):
   lo,hi=bounds(o);row['dimensions_mm']=list(hi-lo)
  rows.append(row)
 return {'stage':'Blender','source_board':json.loads(Path(scene['handoff_manifest']).read_text()).get('source_board'),'comments':json.loads(scene.get('engineering_comments','[]')),'design_gaps':json.loads(scene.get('design_gaps','[]')),'device_profile':json.loads(scene.get('device_profile','{}')),'active_body_id':body_object().get('assembly_id') if body_object() else None,'presentation':{'view':scene.get('presentation_view','assembly'),'exploded':bool(json.loads(scene.get('presentation_offsets','{}'))),'validation_pose':'assembled'},'model_coverage':json.loads(scene.get('model_coverage','{}')),'mission':scene.get('mission'),'objects':rows,'native_findings':json.loads(scene.get('native_findings','[]')),'findings':json.loads(scene.get('assembly_checks','[]')),'timeline':json.loads(scene.get('timeline','[]')),'stale':signature()!=scene.get('assembly_signature'),'source_revision':scene.get('board_revision'),'source_hash':scene.get('source_hash'),'component_check_error':scene.get('component_check_error',''),'body_scope':'Reference anatomy, chest placement and geometric fit only.'}

def execute(command):
 action=command['action']
 if action=='assembly_handoff':
  import native_views
  native_views.restore()
  return handoff(command['manifest'])
 if not active():raise ValueError('Confirm a KiCad board to start the assembly workspace.')
 if action=='assembly_import':
  root,_=import_asset(command['path'],command['label'],command['units'],command['role'])
  if command['role']=='body':bpy.context.scene['active_body_id']=root['assembly_id']
  record('Imported '+root.name);check();focus(root['assembly_id']);return 'Imported editable CAD: '+root.name
 if action=='assembly_select_body':
  obj=objects().get(command['object'])
  if not obj or obj.get('asset_role')!='body':raise ValueError('Select an imported body model.')
  bpy.context.scene['active_body_id']=obj['assembly_id'];record('Selected body CAD: '+obj.name);return check()
 if action=='assembly_view':
  import native_views
  return native_views.view(command['view'])
 if action=='assembly_comment':
  import native_views
  return native_views.add_comment(command['finding_id'],command['text'],command.get('object'))
 if action=='assembly_generate_housing':
  import housing
  return housing.generate(command['profile'])
 if action=='assembly_region':region(command['name'],command['center'],command['size'],command.get('reason','ECG brief placement'),command.get('parent'));record('Defined '+command['name']);return check()
 if action=='assembly_place':return place(command['object'],command['region'])
 if action=='assembly_edit':return edit(command['object'],command.get('position'),command.get('rotation'),command.get('dimensions'))
 if action=='assembly_focus':
  import native_views
  return native_views.contextual_focus(command['object'])
 if action=='assembly_flag_motion':
  scene=bpy.context.scene;scene['red_flag_motion']=not scene.get('red_flag_motion',True)
  return 'Red pulse '+('enabled' if scene['red_flag_motion'] else 'paused')
 if action=='assembly_check':
  result=check();focus('board' if objects().get('board') else 'device');return result
 if action=='assembly_body':return body_reference()
 if action=='assembly_fit_chest':return fit_chest()
 if action=='assembly_sample':return demo_enclosure()
 if action=='assembly_save':
  path=Path(bpy.data.filepath) if bpy.data.filepath else Path(scene_manifest()).parent/'assembly.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));return 'Saved '+str(path)
 raise ValueError('Unsupported assembly action')
def scene_manifest():return bpy.context.scene['handoff_manifest']
