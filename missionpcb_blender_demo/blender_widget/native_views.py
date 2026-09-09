"""Native Blender camera views, reversible exploded inspection, and engineering notes."""
import bpy,json,math,textwrap,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from mathutils import Vector,Matrix

VIEWS=('board','assembly','chest','workbench','exploded')

def _assembly():
 import assembly
 return assembly

def offsets():return json.loads(bpy.context.scene.get('presentation_offsets','{}'))

def restore_visibility():
 scene=bpy.context.scene
 for name,state in json.loads(scene.get('presentation_visibility','{}')).items():
  obj=scene.objects.get(name)
  if obj:obj.hide_render=state['render'];obj.hide_set(state['viewport'])
 scene['presentation_visibility']='{}'

def _visibility(name,board,a):
 """Presentation hides occluders without removing geometry from fit checks."""
 scene=bpy.context.scene;states={};keep={board,*board.children_recursive}
 body=a.body_object();body_objects={body,*body.children_recursive} if body else set()
 for obj in scene.objects:
  if obj.type not in ('MESH','CURVE','FONT'):continue
  hide=(name=='board' and obj not in keep)
  hide=hide or (name in ('assembly','exploded') and (obj in body_objects or obj.get('outside_mounting_pocket')))
  hide=hide or (name in ('assembly','chest') and obj.get('mechanical_role')=='lid')
  if hide:
   states[obj.name]={'render':obj.hide_render,'viewport':obj.hide_get()};obj.hide_render=True;obj.hide_set(True)
 scene['presentation_visibility']=json.dumps(states)

def restore():
 a=_assembly()
 for identifier,offset in offsets().items():
  obj=a.objects().get(identifier) or bpy.context.scene.objects.get(identifier)
  if obj:obj.location-=Vector(offset)
 bpy.context.scene['presentation_offsets']='{}';bpy.context.view_layer.update()

@contextmanager
def assembled_pose():
 """Checks use assembled coordinates; explosion is a reversible presentation offset."""
 a=_assembly();rows=offsets();moved=[]
 try:
  for identifier,offset in rows.items():
   obj=a.objects().get(identifier) or bpy.context.scene.objects.get(identifier)
   if obj:obj.location-=Vector(offset);moved.append((obj,Vector(offset)))
  bpy.context.view_layer.update();yield
 finally:
  for obj,offset in moved:
   if obj.name in bpy.context.scene.objects:obj.location+=offset
  bpy.context.view_layer.update()

def _camera(target,frame,width,view):
 scene=bpy.context.scene
 if scene.render.engine=='BLENDER_WORKBENCH':scene.render.engine='BLENDER_EEVEE'
 if bpy.context.screen and not any(a.type=='VIEW_3D' for a in bpy.context.screen.areas):
  max(bpy.context.screen.areas,key=lambda a:a.width*a.height).type='VIEW_3D'
 name='MissionPCB camera · '+view
 camera=scene.objects.get(name)
 if camera is None:
  data=bpy.data.cameras.new(name);camera=bpy.data.objects.new(name,data);scene.collection.objects.link(camera)
 camera.data.type='ORTHO';camera.data.ortho_scale=width;camera.data.clip_start=.1;camera.data.clip_end=10000
 # PCB coordinates are millimetres; view axes follow the actual mounted board.
 offset=Vector((.23,-.66,1.3))*width
 if view=='board':offset=Vector((.14,-.48,1.7))*width
 if view=='chest':offset=Vector((.12,-.16,1.8))*width
 if view=='exploded':offset=Vector((.62,-1.1,1.25))*width
 camera.location=target+frame.to_quaternion()@offset
 camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':
    area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.region_3d.view_camera_zoom=10
    area.spaces.active.overlay.show_overlays=False;area.spaces.active.shading.type='MATERIAL'
    area.spaces.active.shading.use_scene_world=False;area.spaces.active.shading.use_scene_lights=False
 return camera

def view(name):
 if name not in VIEWS:raise ValueError('Choose PCB, assembly, body, workbench, or exploded view.')
 a=_assembly();restore();restore_visibility();scene=bpy.context.scene
 if scene.get('presentation_style')!='native_pcb':
  import pcb_presentation
  pcb_presentation.enable_existing(a)
 items=a.objects();board=items.get('board');device=items.get('device')
 if not board or not device:raise ValueError('Import the native PCB first.')
 # Material repair is idempotent even if an older adapter set the style tag.
 import pcb_presentation
 pcb_presentation.board_finish(board,a)
 if name=='exploded':
  rows={};board.location.z+=16;rows['board']=[0,0,16]
  enclosure=items.get(scene.get('active_enclosure_id','enclosure'))
  if enclosure:
   for obj in enclosure.children_recursive:
    if obj.get('mechanical_role')=='lid' or 'lid' in obj.name.lower():
     obj.location.z+=36;rows[obj.get('assembly_id',obj.name)]=[0,0,36]
  scene['presentation_offsets']=json.dumps(rows)
 bpy.context.view_layer.update()
 lo,hi=a.bounds(board,device.matrix_world);center=(lo+hi)/2;width=max(hi.x-lo.x,hi.y-lo.y)
 if name!='board':
  points=[device.matrix_world.inverted()@obj.matrix_world@Vector(c) for obj in a.meshes(device) if not obj.get('outside_mounting_pocket') for c in obj.bound_box]
  lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
  center=(lo+hi)/2;width=max(hi.x-lo.x,hi.y-lo.y)
 factor={'board':1.3,'assembly':1.45,'chest':3.5,'workbench':1.8,'exploded':1.65}[name]
 if name=='chest' and a.body_object() is None:raise ValueError('Import and select a body CAD model first.')
 _camera(device.matrix_world@center,device.matrix_world,max(50,width*factor),name)
 scene['presentation_view']=name
 a.check()
 _visibility(name,board,a)
 return 'Showing '+{'board':'native PCB detail','assembly':'device in its mounting context','chest':'body placement','workbench':'assembly overview','exploded':'exploded inspection; fit checks use assembled positions'}[name]+' in Blender.'

def add_comment(finding_id,text,identifier=None):
 a=_assembly();scene=bpy.context.scene
 if not isinstance(text,str) or not text.strip() or len(text)>2000:raise ValueError('Write a note between 1 and 2,000 characters.')
 comments=json.loads(scene.get('engineering_comments','[]'))
 findings=json.loads(scene.get('assembly_checks','[]'))+json.loads(scene.get('native_findings','[]'))
 finding=next((f for f in findings if f.get('id')==finding_id),None)
 if finding is None and not any(c['finding_id']==finding_id for c in comments):raise ValueError('Select a current finding or an existing note thread.')
 if identifier is None:identifier=(finding or {}).get('object') or 'part-'+((finding or {}).get('kicad_refs') or [''])[0]
 if identifier not in a.objects():raise ValueError('Select the affected component or assembly.')
 comments.append({'id':uuid.uuid4().hex,'finding_id':finding_id,'object':identifier,'text':text.strip(),'created':datetime.now(timezone.utc).isoformat()})
 scene['engineering_comments']=json.dumps(comments)
 a.record('Engineering note added to '+a.objects()[identifier].name);a.check()
 return 'Saved the engineering note in the Blender project. Select the component to read it in the MissionPCB sidebar.'

def draw_comments(a):
 from pcb_presentation import line,text,AMBER
 board=a.objects().get('board')
 if not board:return
 seen=set()
 for comment in json.loads(bpy.context.scene.get('engineering_comments','[]')):
  target=a.objects().get(comment['object'])
  if not target or target.name in seen:continue
  seen.add(target.name)
  if not a.meshes(target):continue
  lo,hi=a.bounds(target,board.matrix_world);p=Vector((hi.x+1.0,hi.y+1.0,max(hi.z,2)+.5))
  pin=line('Engineering note · '+target.name,[(p.x,p.y,p.z-.9),tuple(p)],AMBER,board,comment['object'],.2)
  pin['note_id']=comment['id']
  text('Note reference','NOTE '+target.get('kicad_ref',''),tuple(p+Vector((.5,0,0))),.9,AMBER,board,True)

def contextual_focus(identifier):
 a=_assembly();obj=a.objects().get(identifier)
 if obj is None:raise ValueError('Unknown component or assembly.')
 if not a.meshes(obj):return view('board')
 bpy.ops.object.select_all(action='DESELECT')
 obj.hide_set(False);obj.select_set(True);bpy.context.view_layer.objects.active=obj
 for child in a.meshes(obj):child.hide_set(False);child.select_set(True)
 board=a.objects().get('board');frame=board.matrix_world if board else Matrix.Identity(4)
 lo,hi=a.bounds(obj,frame);width=max(hi.x-lo.x,hi.y-lo.y,hi.z-lo.z)
 _camera(frame@((lo+hi)/2),frame,max(26,width*2.3),'selection')
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':area.spaces.active.show_region_ui=True
 bpy.context.scene['presentation_view']='selection'
 return 'Focused '+obj.get('kicad_ref',obj.name)+' with its surrounding geometry and native review notes.'

class MISSIONPCB_OT_native_view(bpy.types.Operator):
 bl_idname='missionpcb.native_view';bl_label='MissionPCB view'
 view_name:bpy.props.StringProperty()
 def execute(self,context):
  try:view(self.view_name)
  except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
  return {'FINISHED'}

class MISSIONPCB_PT_review(bpy.types.Panel):
 bl_label='MissionPCB review';bl_idname='MISSIONPCB_PT_review';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='MissionPCB'
 @classmethod
 def poll(cls,context):return bool(context.scene.get('missionpcb_assembly'))
 def draw(self,context):
  layout=self.layout;row=layout.row(align=True)
  for name,title in [('board','PCB'),('assembly','Device'),('chest','Body')]:row.operator('missionpcb.native_view',text=title).view_name=name
  row=layout.row(align=True)
  for name,title in [('workbench','Overview'),('exploded','Exploded')]:row.operator('missionpcb.native_view',text=title).view_name=name
  if offsets():layout.label(text='Fit evaluated in assembled pose',icon='INFO')
  obj=context.active_object
  while obj and not obj.get('assembly_id'):obj=obj.parent
  if not obj:layout.label(text='Select a component for its findings');return
  identifier=obj.get('assembly_id');ref=obj.get('kicad_ref');layout.label(text=ref or obj.name,icon='OBJECT_DATA')
  if obj.get('value'):layout.label(text=str(obj['value']))
  if obj.get('missing_model'):layout.label(text='Package 3D model missing',icon='ERROR')
  findings=json.loads(context.scene.get('native_findings','[]'))+json.loads(context.scene.get('assembly_checks','[]'))
  for finding in [f for f in findings if f.get('object')==identifier or ref and ref in f.get('kicad_refs',[])][:6]:
   box=layout.box();box.label(text=finding['status']+' · '+finding.get('title',finding['id'])[:35])
   for line in textwrap.wrap(finding.get('message',finding.get('reason','')),42):box.label(text=line)
  for comment in json.loads(context.scene.get('engineering_comments','[]')):
   if comment['object']!=identifier:continue
   box=layout.box();box.label(text='Engineering note',icon='TEXT')
   for line in textwrap.wrap(comment['text'],42):box.label(text=line)

def register():
 for cls in (MISSIONPCB_OT_native_view,MISSIONPCB_PT_review):
  previous=getattr(bpy.types,cls.__name__,None)
  if previous:
   try:bpy.utils.unregister_class(previous)
   except RuntimeError:pass
  bpy.utils.register_class(cls)
