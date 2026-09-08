"""Lightweight decorative electronics workbench; never enters validation."""
import math
import bpy
from mathutils import Vector
import scene_builder as s

COLLECTION = '05_Workbench_Environment'


def build_environment():
    col=s.collection(COLLECTION)
    for obj in list(col.objects):
        data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
        if data and data.users==0:
            if isinstance(data,bpy.types.Mesh):bpy.data.meshes.remove(data)
            elif isinstance(data,bpy.types.Curve):bpy.data.curves.remove(data)
            elif isinstance(data,bpy.types.Camera):bpy.data.cameras.remove(data)
    def mat(name,color,metallic=0):return s.material('Workbench '+name,(*color,1),metallic=metallic)
    wood=mat('oak',(.43,.26,.14));woodline=mat('oak seam',(.31,.18,.095))
    blue=mat('ESD mat',(.53,.66,.69));edge=mat('mat edge',(.34,.46,.49))
    charcoal=mat('charcoal',(.038,.054,.060));rubber=mat('rubber',(.016,.022,.025))
    steel=mat('steel',(.52,.57,.59),.78);silver=mat('solder',(.67,.69,.68),.8)
    yellow=mat('warm tool grip',(.79,.43,.10));red=mat('red silicone',(.58,.045,.03))
    paper=mat('notebook paper',(.86,.85,.77));cover=mat('notebook cover',(.19,.27,.25))
    muted=mat('quiet marks',(.25,.35,.36));screen=mat('LCD glass',(.045,.085,.080))
    lcd=s.material('Workbench LCD lettering',(.44,.67,.56,1),emission=True)
    def box(name,loc,size,material,bevel=0):return s.box('Workbench '+name,loc,size,material,col,bevel=bevel)
    def plate(name,loc,size,radius,material):return s.rounded_plate('Workbench '+name,loc,size,radius,material,col,None)
    def line(name,points,material,width=.2):return s.line('Workbench '+name,points,material,col,width=width)
    def label(name,body,loc,size,material,align='LEFT'):
        obj=s.text('Workbench '+name,body,loc,size,material,col,align=align);obj['role']='decoration';return obj
    def cylinder(name,loc,radius,depth,material,vertices=24):
        coords=[(radius*math.cos(i*math.tau/vertices),radius*math.sin(i*math.tau/vertices),z) for z in [-depth/2,depth/2] for i in range(vertices)]
        faces=[tuple(reversed(range(vertices))),tuple(range(vertices,vertices*2))]+[(i,(i+1)%vertices,(i+1)%vertices+vertices,i+vertices) for i in range(vertices)]
        mesh=bpy.data.meshes.new('Workbench '+name);mesh.from_pydata(coords,[],faces);mesh.update()
        obj=s.attach(bpy.data.objects.new('Workbench '+name,mesh),col);obj.location=loc;obj.data.materials.append(material);return obj
    def along(obj,start,end):
        a,b=Vector(start),Vector(end);obj.location=(a+b)/2;obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return obj
    def rod(name,start,end,radius,material):return along(cylinder(name,(0,0,0),radius,(Vector(end)-Vector(start)).length,material,16),start,end)
    # Table top at -5 mm; mat top at -2.8 mm clears every original device surface.
    plate('oak desktop',(0,0,-13),(560,360,16),12,wood)
    for y in [-124,-44,44,124]:line('plank seam '+str(y),[(-280,y,-4.99),(280,y,-4.99)],woodline,.09)
    # Subtle sparse longitudinal grain, geometry only; no textures or simulation.
    for i in range(16):
        y=-170+i*22
        points=[(-277+j*34.6,y+.8*math.sin(j*.8+i),-4.985) for j in range(17)]
        line('wood grain '+str(i),points,woodline,.025)
    plate('mat edge',(0,0,-4.0),(334,214,2),8,edge)
    plate('ESD work mat',(0,0,-3.35),(330,210,1.1),7,blue)
    line('mat inner border',[(-158,-98,-2.78),(158,-98,-2.78),(158,98,-2.78),(-158,98,-2.78),(-158,-98,-2.78)],muted,.09)
    # Only edge ticks; keep device and dashboard areas uncluttered.
    for x in range(-150,151,10):line('mat tick '+str(x),[(x,-97,-2.77),(x,-94 if x%50==0 else -95.5,-2.77)],muted,.09)
    label('mat identity','MISSIONPCB / ECG ASSEMBLY',(-151,90,-2.74),2.7,muted)
    label('mat note','ESD WORK SURFACE',(-151,-91,-2.74),1.8,muted)
    cylinder('ground snap',(151,90,-1.9),2,1.8,steel)
    # A restrained bench meter; display deliberately has no fabricated measurements.
    plate('meter bumper',(203,27,1),(48,79,12),7,yellow)
    plate('meter face',(203,27,7.6),(40,71,2),5,charcoal)
    plate('meter screen',(203,47,8.9),(32,22,.7),2,screen)
    label('meter display','BENCH\nSTANDBY',(203,50,9.35),3.0,lcd,'CENTER')
    cylinder('meter dial',(203,18,10.1),10,3,rubber)
    line('meter pointer',[(203,18,11.7),(207,24,11.7)],paper,.65)
    for i in range(7):
        a=math.radians(i*40-25);x,y=203+14*math.cos(a),18+14*math.sin(a)
        line('meter dial tick '+str(i),[(x,y,8.75),(203+16*math.cos(a),18+16*math.sin(a),8.75)],paper,.18)
    for x,material in [(195,rubber),(210,red)]:
        cylinder('meter socket '+str(x),(x,-.5,9.8),2.2,2,material)
        line('meter lead '+str(x),[(x,-.5,10),(x,-13,0),(x+10,-27,-3.5),(x+19,-42,-3.5),(x+15,-59,-3.5),(x+1,-70,-3.5),(x-5,-62,-3.5)],material,.55)
    rod('red probe',(208,-82,-1),(222,-57,-1),1.8,red)
    rod('red probe tip',(222,-57,-1),(226,-50,-1),.45,steel)
    rod('black probe',(217,-88,-1),(231,-63,-1),1.8,rubber)
    rod('black probe tip',(231,-63,-1),(235,-56,-1),.45,steel)
    # Small notebook with visible pages/binding, not a second information panel.
    plate('notebook cover',(-209,35,-3),(66,91,3),3,cover)
    plate('notebook pages',(-208,35,-.4),(61,87,2.2),2,paper)
    box('notebook binding',(-236,35,1),(4,88,2),charcoal,.5)
    label('notebook title','ECG PATCH',(-226,68,.9),3.5,muted)
    label('notebook subtitle','ASSEMBLY NOTES',(-226,61,.9),1.8,muted)
    for i in range(9):line('notebook rule '+str(i),[(-226,48-i*6,.8),(-183,48-i*6,.8)],muted,.05)
    for i in range(7):
        y=2+i*11;line('notebook staple '+str(i),[(-239,y,1),(-239,y+2.5,2),(-233,y+2.5,2),(-233,y,1)],steel,.32)
    rod('pencil',(-178,-10,-2),(-181,66,-2),1.8,yellow)
    rod('pencil tip',(-178,-10,-2),(-177.8,-15,-2),.6,charcoal)
    # Solder reel and a short wire tail at the lower-left corner.
    cylinder('spool lower flange',(-211,-67,-2),16,3,charcoal,32)
    cylinder('solder winding',(-211,-67,4),13,10,silver,32)
    cylinder('spool upper flange',(-211,-67,10),16,2.5,charcoal,32)
    cylinder('spool hub',(-211,-67,11.4),5,.5,rubber,24)
    for radius in [7,10,13]:line('spool circular mark '+str(radius),[(-211+radius*math.cos(i*math.tau/40),-67+radius*math.sin(i*math.tau/40),11.35) for i in range(41)],muted,.16)
    line('solder tail',[(-198,-67,3),(-189,-65,-1),(-184,-74,-3),(-190,-88,-3),(-183,-97,-3),(-172,-98,-3)],silver,.32)
    # Tweezers and precision screwdriver laid horizontally beyond the mat.
    for offset in [-2.1,2.1]:
        line('tweezer arm '+str(offset),[(-99,126+offset,-2.8),(-64,128+offset,-2.8),(-45,131+offset*.25,-2.8)],steel,.8)
    rod('driver shaft',(91,129,-2),(133,130,-2),.8,steel)
    rod('driver grip',(56,128,-1),(91,129,-1),3.8,yellow)
    rod('driver collar',(88,128.9,-1),(94,129.1,-1),4.1,charcoal)
    for x in [62,69,76,83]:rod('driver grip ring '+str(x),(x,128+(x-56)/35,-1),(x+.7,128+(x-56)/35,-1),3.85,charcoal)
    # Hide only unvalidated stage decoration from the previous editorial scene.
    for obj in bpy.context.scene.objects:
        if obj.name=='Studio floor' or obj.name.startswith(('GridX_','GridY_')):
            obj.hide_render=True;obj.hide_set(True)
    camdata=bpy.data.cameras.new('Camera_Workbench');camdata.type='ORTHO';camdata.ortho_scale=475;camdata.clip_end=2000
    camera=s.attach(bpy.data.objects.new('Camera_Workbench',camdata),col);camera.location=(12,-230,420)
    camera.rotation_euler=(Vector((0,8,0))-camera.location).to_track_quat('-Z','Y').to_euler()
    for obj in col.objects:
        obj['role']='decoration';obj['environment_only']=True;obj.hide_select=True
    scene=bpy.context.scene;scene.camera=camera;s.face_camera(camera)
    scene['workbench_note']='Decorative context only; original component geometry and validation unchanged.'
    for screen_obj in bpy.data.screens:
        for area in screen_obj.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.region_3d.view_camera_zoom=0
    bpy.context.view_layer.update()
    return camera
