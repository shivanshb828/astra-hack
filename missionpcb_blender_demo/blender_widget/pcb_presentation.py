"""Native KiCad geometry on the existing Blender workbench, with concise review marks.

Presentation materials never add electrical connectivity or change footprint placement.
"""
import bpy,json,math
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parent
RED=(1,.035,.02,1);AMBER=(1,.56,.025,1)

def finish(name,color,metal=0,rough=.4):
 m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=color
 n=m.node_tree.nodes.get('Principled BSDF')
 if n:
  n.inputs['Base Color'].default_value=color;n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=rough;n.inputs['Alpha'].default_value=color[3]
 return m

def rebase_import(board):
 # Put the assembly origin at board centre while preserving imported world geometry.
 # KiCad GLB children use absolute board coordinates, not centre-relative positions.
 bpy.context.view_layer.update();poses={o:o.matrix_world.copy() for o in board.children}
 board.matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
 for obj,world in poses.items():obj.matrix_world=world
 bpy.context.view_layer.update()

def board_finish(board,assembly):
 """Keep the imported triangles. Assign physical finishes by KiCad mesh identity."""
 for obj in assembly.meshes(board):
  name=obj.data.name.lower()
  if 'soldermask' in name:
   mat=finish('PCB · green solder mask',(.012,.17,.071,1),.05,.3)
  elif 'silkscreen' in name:mat=finish('PCB · white legend',(.88,.92,.86,1),0,.68)
  elif name.endswith('_pcb') or '_pcb.' in name:mat=finish('PCB · FR4 edge',(.11,.14,.047,1),0,.74)
  elif name.endswith('_pad') or '_pad.' in name:mat=finish('PCB · solder finish',(.63,.67,.71,1),.82,.23)
  else:
   # Respect the package's separate moulding and lead materials.
   for material in obj.data.materials:
    if material and material.use_nodes:
     n=material.node_tree.nodes.get('Principled BSDF')
     if n:
      c=n.inputs['Base Color'].default_value
      metal=.7 if .48<c[0]<.7 and abs(c[0]-c[1])<.06 else 0
      n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=.26 if metal else .43
   if not obj.data.materials:obj.data.materials.append(finish('PCB · RF shield',(.55,.59,.62,1),.72,.27))
   continue
  obj.data.materials.clear();obj.data.materials.append(mat)
 # Every native reference remains in the checker, including a missing 3D model.
 manifest=json.loads(Path(bpy.context.scene['handoff_manifest']).read_text())
 existing={o.get('kicad_ref') for o in board.children_recursive}
 for row in manifest['parts']:
  if row['ref'] in existing:continue
  obj=assembly.empty(row['ref']+' · missing package model','part-'+row['ref'],board)
  obj['kicad_ref']=row['ref'];obj['value']=row['value'];obj['asset_role']='component';obj['missing_model']=True
  obj.location=(row['x_mm']-136,119-row['y_mm'],1.645)
  obj['native_baseline']=json.dumps(row);obj['import_location']=list(obj.location);obj['import_rotation_z']=0
 bpy.context.view_layer.update()

def enable_existing(assembly):
 """Upgrade an existing mounted native import without changing its world geometry."""
 board=assembly.objects()['board'];parent=board.parent.matrix_world if board.parent else Matrix.Identity(4)
 bpy.context.view_layer.update();lo,hi=assembly.bounds(board,parent);poses={o:o.matrix_world.copy() for o in board.children}
 board.matrix_basis=Matrix.Translation(Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z)))
 bpy.context.view_layer.update()
 for obj,world in poses.items():obj.matrix_world=world
 bpy.context.view_layer.update()
 for obj in board.children_recursive:
  if obj.get('kicad_ref'):
   local=board.matrix_world.inverted()@obj.matrix_world
   obj['import_location']=list(local.translation);obj['import_rotation_z']=local.to_euler().z
 bpy.context.scene['presentation_style']='native_pcb';bpy.context.scene['red_flag_motion']=False
 board_finish(board,assembly)
 bpy.context.scene.view_settings.view_transform='AgX'
 assembly.check()

def clear_flags():
 import red_flags
 red_flags.clear()

def line(name,points,color,parent,target='',width=.16):
 curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.bevel_depth=width;curve.bevel_resolution=2
 spline=curve.splines.new('POLY');spline.points.add(len(points)-1)
 for point,xyz in zip(spline.points,points):point.co=(*xyz,1)
 obj=bpy.data.objects.new(name,curve);bpy.context.scene.collection.objects.link(obj);obj.parent=parent;obj['is_flag']=True;obj['flag_target']=target;obj.show_in_front=True
 mat=finish('Review · error' if color==RED else 'Review · watch',color,0,.5)
 shader=mat.node_tree.nodes.get('Principled BSDF');shader.inputs['Emission Color'].default_value=color;shader.inputs['Emission Strength'].default_value=.35
 curve.materials.append(mat);return obj

def text(name,body,position,size,color,parent=None,flag=False):
 curve=bpy.data.curves.new(name,'FONT');curve.body=body;curve.size=size;curve.align_x='LEFT'
 obj=bpy.data.objects.new(name,curve);bpy.context.scene.collection.objects.link(obj);obj.parent=parent;obj.location=position
 curve.materials.append(finish(name+' ink',color,0,.8))
 if flag:obj['is_flag']=True
 return obj

def draw(findings,assembly):
 clear_flags();scene=bpy.context.scene;items=assembly.objects();board=items.get('board')
 if board is None:return
 grouped={}
 for finding in findings:
  if finding.get('status')=='PASS':continue
  key=finding.get('object');obj=items.get(key)
  if not obj or (key in ('board','device') and finding.get('status')!='FAIL'):continue
  if key not in grouped or finding['status']=='FAIL':grouped[key]=finding
 errors=warnings=0
 for key,finding in grouped.items():
  target=items[key];failed=finding['status']=='FAIL';color=RED if failed else AMBER
  if target.get('asset_role')=='component':
   parent=board
   if target.get('missing_model'):
    center=target.location;lo=center-Vector((1.65,1.65,0));hi=center+Vector((1.65,1.65,0))
   else:lo,hi=assembly.bounds(target,board.matrix_world)
   # Review geometry sits at board level, leaving the actual package unobscured.
   z=1.68;x0,y0=lo.x-.65,lo.y-.65;x1,y1=hi.x+.65,hi.y+.65
   edge=min(1.8,(x1-x0)/2,(y1-y0)/2)
   for x,y,dx,dy in [(x0,y0,1,1),(x1,y0,-1,1),(x1,y1,-1,-1),(x0,y1,1,-1)]:
    mark=line(('ERROR' if failed else 'WATCH')+' · '+target['kicad_ref'],[(x+dx*edge,y,z),(x,y,z),(x,y+dy*edge,z)],color,parent,key)
    mark['severity']='FAIL' if failed else 'WARN'
   if target.get('missing_model'):text('Missing model note','L1 / MODEL MISSING',(x0,y1+.65,z),.7,AMBER,parent,True)
  elif assembly.meshes(target):
   frame=board.matrix_world
   points=[frame.inverted()@mesh.matrix_world@Vector(c) for mesh in assembly.meshes(target) if not mesh.get('outside_mounting_pocket') for c in mesh.bound_box]
   if points:
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)));z=hi.z+.6
    line('Assembly issue',[(lo.x,lo.y,z),(hi.x,lo.y,z),(hi.x,hi.y,z),(lo.x,hi.y,z),(lo.x,lo.y,z)],color,board,key,.22)
  errors+=int(failed);warnings+=int(not failed)
 # One calm legend outside the board replaces overlapping per-component callouts.
 text('Review legend',f'{errors} ERROR AREAS   /   {warnings} WATCH AREAS',(-36,-25,0),1.4,(.04,.1,.13,1),board,True)
 line('Error key',[(-36,-27,0),(-32,-27,0)],RED,board,width=.25)
 text('Error key text','constraint failed',(-31,-27.4,0),.9,(.07,.13,.15,1),board,True)
 line('Watch key',[(-12,-27,0),(-8,-27,0)],AMBER,board,width=.25)
 text('Watch key text','needs review',(-7,-27.4,0),.9,(.07,.13,.15,1),board,True)
 scene['presentation_flag_count']=len(grouped)

def build(manifest):
 import assembly
 scene=bpy.context.scene
 if not bpy.data.objects.get('Root_MissionPCB'):raise ValueError('Load the original detailed workbench scene first.')
 # Preserve only the original right-hand enclosure and presentation environment.
 keep_roles={'layout_root','shell','skin_surface','adhesive'}
 keep_names=('Rounded patch edge','Ruler','Scale units','Rear aperture')
 enclosure_objects=[]
 for name in ('00_Reference','01_Naive_Layout','03_Constraint_Overlays'):
  col=bpy.data.collections.get(name)
  if col:
   for obj in list(col.all_objects):bpy.data.objects.remove(obj,do_unlink=True)
 col=bpy.data.collections['02_MissionPCB_Layout']
 keep={o for o in col.objects if o.get('role') in keep_roles or o.name.startswith(keep_names)}
 victims={o for o in col.objects if o not in keep}
 for obj in list(victims):victims.update(c for c in obj.children_recursive if c not in keep)
 for obj in victims:bpy.data.objects.remove(obj,do_unlink=True)
 device=bpy.data.objects['Root_MissionPCB'];device['assembly_id']='device';device.name='ECG device assembly'
 enclosure=assembly.empty('Original translucent ECG enclosure','enclosure',device);enclosure['asset_role']='product';enclosure['source']='Existing detailed workbench enclosure'
 bpy.context.view_layer.update()
 for obj in list(device.children):
  if obj==enclosure:continue
  if obj.get('role') in ('shell','skin_surface','adhesive'):
   world=obj.matrix_world.copy();obj.parent=enclosure;obj.matrix_world=world
   if obj.get('role')=='skin_surface':obj['is_presentation']=True
 # Keep schematic placement separate from the original demonstration's synthetic routes.
 scene['missionpcb_assembly']=True;scene['presentation_style']='native_pcb';scene['red_flag_motion']=False
 scene['timeline']='[]'
 assembly.handoff(manifest)
 board=assembly.objects()['board'];board.location.z=2
 board_finish(board,assembly)
 assembly.region('board-bay',[0,0,5],[76,42,8],'Electronics pocket in the existing ECG enclosure','device');board['assigned_region']='region-board-bay'
 # The saved close-up camera already frames the right enclosure; use its composition.
 scene.camera=bpy.data.objects['Camera_CAD_Closeup'];scene.camera.data.type='ORTHO';scene.camera.data.ortho_scale=109
 target=device.matrix_world.translation+Vector((0,0,3));scene.camera.location=target+Vector((30,-42,76));scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
 scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
 scene.view_settings.exposure=.35
 for name,offset,energy,size in [('Key',(-60,-55,100),95000,95),('Fill',(65,25,105),55000,100),('Rim',(0,65,85),70000,65)]:
  light=bpy.data.objects.get(name)
  if light:
   light.location=target+Vector(offset);light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler();light.data.energy=energy;light.data.size=size
 scene.view_settings.view_transform='AgX';scene.render.engine='BLENDER_EEVEE'
 scene.render.resolution_x=1800;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
 text('ECG assembly identification','MISSIONPCB  /  ECG CHEST PATCH',(-36,27,0),1.5,(.04,.12,.14,1),device)
 text('Native board source','NATIVE KICAD PCB   /   72 x 38 mm   /   PLACEMENT REVIEW',(-36,24.5,0),.85,(.16,.25,.28,1),device)
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':
    area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_overlays=False
    area.spaces.active.shading.type='MATERIAL';area.spaces.active.show_region_ui=False
 assembly.check()
 return assembly.snapshot()
