"""Red 3D review beacons. Presentation only; excluded from engineering geometry."""
import bpy,math,time,json
from mathutils import Vector
RED=(1.0,.008,.025,1.0)
MAT='MissionPCB · signal red'

def material():
 m=bpy.data.materials.get(MAT) or bpy.data.materials.new(MAT)
 m.diffuse_color=RED;m.use_nodes=True
 shader=m.node_tree.nodes.get('Principled BSDF')
 if shader:
  shader.inputs['Base Color'].default_value=RED
  shader.inputs['Roughness'].default_value=.28
  shader.inputs['Emission Color'].default_value=RED
  shader.inputs['Emission Strength'].default_value=1
 return m

def tag(obj,kind,target,parent=None):
 obj['is_flag']=True;obj['flag_kind']=kind;obj['flag_target']=target
 obj.show_in_front=True;obj.color=RED
 if parent:obj.parent=parent
 obj.data.materials.clear();obj.data.materials.append(material())
 for area in bpy.context.screen.areas if bpy.context.screen else []:
  if area.type=='VIEW_3D' and area.spaces.active.local_view:
   obj.local_view_set(area.spaces.active,True)
 return obj

def line(name,points,width,kind,target,parent,closed=False):
 data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.bevel_depth=width;data.bevel_resolution=3
 spline=data.splines.new('POLY');spline.points.add(len(points)-1)
 for p,co in zip(spline.points,points):p.co=(*co,1)
 spline.use_cyclic_u=closed
 obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj)
 return tag(obj,kind,target,parent)

def label(name,text,position,size,target,parent,kind='label'):
 data=bpy.data.curves.new(name,'FONT');data.body=text;data.size=size;data.align_x='CENTER';data.extrude=.035;data.bevel_depth=.01
 obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);obj.location=position
 return tag(obj,kind,target,parent)

def clear():
 for obj in list(bpy.context.scene.objects):
  if not obj.get('is_flag'):continue
  data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
  if data and data.users==0:
   if isinstance(data,bpy.types.Mesh):bpy.data.meshes.remove(data)
   elif isinstance(data,bpy.types.Curve):bpy.data.curves.remove(data)

def draw(findings,assembly):
 clear();bpy.context.scene.view_settings.view_transform='Standard';items=assembly.objects();board=items.get('board');grouped={}
 for finding in findings:
  if finding.get('status')=='PASS':continue
  key=finding.get('object');target=items.get(key)
  # Avoid a giant beacon covering the entire board for setup-only notices.
  if not target or not assembly.meshes(target) or (key=='board' and finding.get('status')!='FAIL'):continue
  grouped.setdefault(key,[]).append(finding)
 for index,(key,rows) in enumerate(sorted(grouped.items()),1):
  target=items[key];parent=board if target!=board else None
  frame=parent.matrix_world if parent else None
  lo,hi=assembly.bounds(target,frame);center=(lo+hi)/2
  radius=max(2.6,math.hypot(hi.x-lo.x,hi.y-lo.y)/2+.8)
  z=hi.z+.6
  # A pair of open neon rings identifies the component without filling it.
  for wave in range(2):
   points=[(radius*math.cos(i*math.tau/64),radius*math.sin(i*math.tau/64),0) for i in range(64)]
   ring=line('Signal ring · '+key,points,.13 if wave==0 else .055,'halo',key,parent,True)
   ring.location=(center.x,center.y,z);ring['pulse_phase']=wave*math.pi;ring['base_scale']=1+wave*.17
  pin=Vector((center.x+radius*.72,center.y-radius*.72,z+6+index%3*1.2))
  line('Beacon stem · '+key,[(center.x,center.y,z),tuple(pin)],.085,'stem',key,parent)
  bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.8,location=pin)
  beacon=tag(bpy.context.object,'beacon',key,parent);beacon.name='RED BEACON '+str(index)+' · '+key
  severity='FAIL' if any(r.get('status')=='FAIL' for r in rows) else 'WATCH'
  text=label('Beacon label · '+key,f'{index:02d}  {target.get("kicad_ref",target.name)}  {severity}',pin+Vector((0,0,1.8)),1.65,key,parent)
  text['billboard']=True
  # Selected outlines trace the actual imported mesh, not proxy cubes.
  for source in assembly.meshes(target):
   obj=bpy.data.objects.new('Red outline · '+source.name,source.data.copy())
   bpy.context.scene.collection.objects.link(obj);obj.matrix_world=source.matrix_world.copy()
   tag(obj,'outline',key)
   modifier=obj.modifiers.new('Signal edges','WIREFRAME');modifier.thickness=.075;modifier.use_replace=True
   obj.hide_set(True);obj.hide_render=True
  measured=set()
  for row in rows:
   refs=row.get('kicad_refs',[])
   if len(refs)!=2 or row.get('measured_mm') is None or row.get('required_mm') is None:continue
   other=items.get('part-'+next((r for r in refs if 'part-'+r!=key),''))
   if other is None:continue
   identity=row.get('id',str(refs))
   if identity in measured:continue
   measured.add(identity)
   a,b=assembly.bounds(other,frame);end=(a+b)/2;start=center.copy();start.z=end.z=max(hi.z,b.z)+2
   measure=line('Clearance · '+identity,[tuple(start),tuple(end)],.10,'measurement',key,parent)
   measure.hide_set(True);measure.hide_render=True
   text=label('Measured gap · '+identity,f'{row["measured_mm"]:.1f} mm / needs {row["required_mm"]:.1f}',(start+end)/2+Vector((0,0,1.5)),1.2,key,parent,'measurement')
   text['billboard']=True;text.hide_set(True);text.hide_render=True
 bpy.context.scene['red_flag_count']=len(grouped)
 bpy.context.scene['red_flag_motion']=bpy.context.scene.get('red_flag_motion',True)
 start_pulse()

def focus(identifier):
 for obj in bpy.context.scene.objects:
  if obj.get('flag_kind') in ('outline','measurement'):
   obj.hide_set(obj.get('flag_target')!=identifier);obj.hide_render=obj.get('flag_target')!=identifier

def pulse():
 scene=bpy.context.scene;t=time.monotonic()*math.tau*.65
 motion=scene.get('red_flag_motion',True)
 view=next((a.spaces.active for a in bpy.context.screen.areas if a.type=='VIEW_3D'),None) if bpy.context.screen else None
 for obj in scene.objects:
  if obj.get('flag_kind')=='halo':
   scale=obj.get('base_scale',1)*(1+.10*math.sin(t+obj.get('pulse_phase',0))) if motion else obj.get('base_scale',1)
   obj.scale=(scale,scale,1)
  if obj.get('billboard') and view:
   rotation=view.region_3d.view_rotation
   obj.rotation_mode='QUATERNION'
   obj.rotation_quaternion=obj.parent.matrix_world.to_quaternion().inverted()@rotation if obj.parent else rotation
 mat=bpy.data.materials.get(MAT)
 if mat and mat.use_nodes:
  shader=mat.node_tree.nodes.get('Principled BSDF')
  if shader:shader.inputs['Emission Strength'].default_value=.65+.35*(1+math.sin(t)) if motion else 1
 if bpy.context.screen:
  for area in bpy.context.screen.areas:
   if area.type=='VIEW_3D':area.tag_redraw()
 return 1/24

def start_pulse():
 old=bpy.app.driver_namespace.get('missionpcb_red_pulse')
 if old and bpy.app.timers.is_registered(old):bpy.app.timers.unregister(old)
 if not bpy.app.background:
  bpy.app.driver_namespace['missionpcb_red_pulse']=pulse
  bpy.app.timers.register(pulse,first_interval=.05)
