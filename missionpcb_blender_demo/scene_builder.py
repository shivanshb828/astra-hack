"""Primitive engineering geometry and presentation assets for Blender 5.x."""
import math
import bpy
from mathutils import Vector

INK=(.018,.042,.062,1)
MUTED=(.20,.29,.34,1)
WHITE=(.94,.97,.98,1)
GREEN=(.015,.48,.24,1)
RED=(.85,.045,.07,1)


def collection(name):
    obj=bpy.data.collections.get(name)
    if not obj:
        obj=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(obj)
    return obj


def material(name,color,metallic=0,emission=False):
    mat=bpy.data.materials.get(name)
    if mat: return mat
    mat=bpy.data.materials.new(name); mat.diffuse_color=color
    mat.use_nodes=True
    nodes=mat.node_tree.nodes; nodes.clear()
    output=nodes.new('ShaderNodeOutputMaterial')
    if emission:
        shader=nodes.new('ShaderNodeEmission'); shader.inputs['Color'].default_value=color
        shader.inputs['Strength'].default_value=1
    else:
        shader=nodes.new('ShaderNodeBsdfPrincipled')
        shader.inputs['Base Color'].default_value=color
        shader.inputs['Roughness'].default_value=.48
        shader.inputs['Metallic'].default_value=metallic
    if color[3]<1:
        transparent=nodes.new('ShaderNodeBsdfTransparent')
        mix=nodes.new('ShaderNodeMixShader'); mix.inputs[0].default_value=color[3]
        mat.node_tree.links.new(transparent.outputs[0],mix.inputs[1])
        mat.node_tree.links.new(shader.outputs[0],mix.inputs[2])
        mat.node_tree.links.new(mix.outputs[0],output.inputs['Surface'])
        if hasattr(mat,'surface_render_method'): mat.surface_render_method='BLENDED'
        mat.use_transparent_shadow=False
        mat.use_transparency_overlap=False
    else: mat.node_tree.links.new(shader.outputs[0],output.inputs['Surface'])
    return mat


def attach(obj,col,parent=None,role='decoration'):
    col.objects.link(obj); obj.parent=parent
    obj['missionpcb_generated']=True; obj['role']=role
    obj.hide_select=role!='component'
    return obj


def empty(name,loc,col,parent=None,role='reference'):
    obj=attach(bpy.data.objects.new(name,None),col,parent,role)
    obj.location=loc; obj.empty_display_size=3
    return obj


def box(name,loc,size,mat,col,parent=None,bevel=0,role='decoration'):
    x,y,z=[v/2 for v in size]
    verts=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=attach(bpy.data.objects.new(name,mesh),col,parent,role); obj.location=loc
    obj.data.materials.append(mat)
    if bevel:
        mod=obj.modifiers.new('Small edge bevel','BEVEL'); mod.width=bevel; mod.segments=3
    return obj


def rounded_board(name,col,parent,mat):
    points=[]
    for x,y,start in [(35,18,0),(-35,18,90),(-35,-18,180),(35,-18,270)]:
        for j in range(9):
            a=math.radians(start+j*90/8)
            points.append((x+math.cos(a),y+math.sin(a)))
    n=len(points)
    vertices=[(x,y,z) for z in [-.8,.8] for x,y in points]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=attach(bpy.data.objects.new(name,mesh),col,parent,'pcb'); obj.location=(0,0,2.8)
    obj.data.materials.append(mat)
    return obj


def line(name,points,mat,col,parent=None,width=.12,role='decoration'):
    curve=bpy.data.curves.new(name,'CURVE'); curve.dimensions='3D'; curve.resolution_u=1
    curve.bevel_depth=width; curve.bevel_resolution=2; curve.resolution_u=1
    path=curve.splines.new('POLY'); path.points.add(len(points)-1)
    for vertex,p in zip(path.points,points): vertex.co=(*p,1)
    obj=attach(bpy.data.objects.new(name,curve),col,parent,role); obj.data.materials.append(mat)
    return obj


def text(name,body,loc,size,mat,col,parent=None,align='LEFT'):
    data=bpy.data.curves.new(name,'FONT'); data.body=body; data.size=size
    data.align_x=align; data.space_character=1.05; data.extrude=0
    obj=attach(bpy.data.objects.new(name,data),col,parent,'label'); obj.location=loc
    obj.data.materials.append(mat)
    return obj


def disk(name,center,radius,mat,col,parent=None):
    vertices=[(0,0,0)]+[(radius*math.cos(i*2*math.pi/96),radius*math.sin(i*2*math.pi/96),0) for i in range(96)]
    faces=[(0,i+1,(i+1)%96+1) for i in range(96)]
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=attach(bpy.data.objects.new(name,mesh),col,parent); obj.location=center; obj.data.materials.append(mat)
    return obj


def face_camera(camera):
    quat=camera.rotation_euler.to_quaternion()
    for obj in bpy.context.scene.objects:
        if obj.get('billboard'):
            obj.rotation_mode='QUATERNION'; obj.rotation_quaternion=quat


def rounded_points(width,depth,radius):
    points=[]
    for x,y,start in [(width/2-radius,depth/2-radius,0),(-width/2+radius,depth/2-radius,90),
                      (-width/2+radius,-depth/2+radius,180),(width/2-radius,-depth/2+radius,270)]:
        for j in range(13):
            angle=math.radians(start+j*90/12)
            points.append((x+radius*math.cos(angle),y+radius*math.sin(angle)))
    return points


def rounded_plate(name,loc,size,radius,mat,col,parent,role='decoration'):
    outline=rounded_points(size[0],size[1],radius); n=len(outline)
    vertices=[(x,y,z) for z in [-size[2]/2,size[2]/2] for x,y in outline]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=attach(bpy.data.objects.new(name,mesh),col,parent,role);obj.location=loc;obj.data.materials.append(mat)
    return obj


def upgrade_ecg(config):
    """Migrate the loaded working scene; preserve core meshes, PCB, roots and cameras."""
    scene=bpy.context.scene
    if not all('PCB_'+name in bpy.data.objects for name in ['Naive','MissionPCB']):
        raise RuntimeError('ECG conversion requires the existing saved MissionPCB scene')
    for obj in list(bpy.data.objects):
        if obj.get('ecg_auxiliary') or obj.get('role')=='shell' or obj.name.startswith(('Enclosure rim ','Enclosure corner ','Rear opening outline ')):
            bpy.data.objects.remove(obj,do_unlink=True)
    reference=collection('00_Reference'); white=material('White text',WHITE,emission=True)
    ink=material('Ink',INK,emission=True); muted=material('Muted',MUTED,emission=True)
    metal=material('Electrode metal',(.77,.65,.36,1),metallic=.7)
    protection=material('Patient protection',(.025,.48,.56,1),metallic=.1)
    peach=material('Skin reference',(.82,.42,.28,.22),emission=True)
    adhesive=material('Adhesive patch',(.73,.84,.83,.62))
    shell=material('ECG translucent polymer',(.33,.55,.59,.08))
    shell_edge=material('Patch edge',(.24,.40,.45,1),emission=True)
    patient_wire=material('Patient signal cyan',(.0,.58,.69,1),emission=True)
    battery_mat=material('LiPo foil',(.48,.55,.60,1),metallic=.7)
    display_names={'MCU':'MCU','Sensor':'ECG_AFE','RF':'BLE_Module','Regulator':'Buck_PMIC','Driver':'LiPo_Charger','Battery':'Battery_Connector'}
    for layout,settings in config['layouts'].items():
        root=bpy.data.objects['Root_'+layout]; col=root.users_collection[0]
        for comp in config['components']:
            obj=next(o for o in scene.objects if o.get('role')=='component' and o.get('layout_id')==layout and o.get('component_id')==comp['id'])
            obj.name=display_names[comp['id']]+'_'+layout
            x,y=settings['positions'][comp['id']]; obj.location.x=x; obj.location.y=y
            obj['seed_location']=list(obj.location);obj['seed_scale']=list(obj.scale)
            for key in ['part_name','datasheet_url','geometry_basis','component_type','noise_source']:
                obj[key]=comp[key]
            obj['patient_connected']=comp.get('patient_connected',False)
            for child in obj.children:
                if child.type=='FONT': child.data.body=comp['label'];child.data.size=1.55 if comp['id']=='Sensor' else 1.65
        inside=bpy.data.objects['Interior_'+layout]
        # Explicitly update reference mesh and origin without replacing its identity.
        zmax=max(v.co.z for v in inside.data.vertices)
        for v in inside.data.vertices: v.co.z*=5/zmax
        inside.location.z=5
        opening=bpy.data.objects['Opening_'+layout]; zmax=max(v.co.z for v in opening.data.vertices)
        for v in opening.data.vertices:v.co.z*=3.5/zmax
        opening.location.z=6.5
        created=[]
        created.append(rounded_plate('Skin_Facing_Surface_'+layout,(0,0,-2.35),(104,64,.12),23,peach,col,root,'skin_surface'))
        created.append(rounded_plate('Adhesive_Patch_'+layout,(0,0,-2.05),(100,60,.35),21,adhesive,col,root,'adhesive'))
        created.append(rounded_plate('Patch_Floor_'+layout,(0,0,-1),(94,54,2),12,shell,col,root,'shell'))
        created.append(rounded_plate('Patch_Lid_'+layout,(0,0,10.4),(94,54,.8),12,shell,col,root,'shell'))
        outline=rounded_points(94,54,12)
        for z in [0,10]:
            created.append(line(f'Rounded patch edge {z} {layout}',[(*p,z) for p in outline+[outline[0]]],shell_edge,col,root,width=.12))
        # Thin side walls follow the rounded outline. Leave the rear connector aperture open.
        for i,(a,b) in enumerate(zip(outline,outline[1:]+outline[:1])):
            if a[0]>45 and b[0]>45 and abs((a[1]+b[1])/2)<6: continue
            mesh=bpy.data.meshes.new('Patch wall');mesh.from_pydata([(*a,0),(*b,0),(*b,10),(*a,10)],[],[(0,1,2,3)]);mesh.update()
            wall=attach(bpy.data.objects.new(f'Patch wall {i} {layout}',mesh),col,root,'shell');wall.data.materials.append(shell);created.append(wall)
        created.append(line('Rear aperture '+layout,[(45,-5,3),(45,5,3),(45,5,10),(45,-5,10)],shell_edge,col,root,width=.18))
        # Reference volume for the explicitly designated contact-zone heat proxy.
        region=box('ContactRegion_'+layout,(-4,6.5,-2.3),(16,19,.1),peach,col,root,role='contact_region')
        region.hide_render=True;region.hide_viewport=True;created.append(region)
        for name,xy in settings['patient_positions'].items():
            height=1.5 if name=='Protection' else 1.3
            size=(4,4,height) if name=='Protection' else (3.6,3.6,height)
            obj=rounded_plate(name+'_'+layout,(*xy,3.6+height/2),size,.45 if name=='Protection' else 1.8,
                              protection if name=='Protection' else metal,col,root,'patient_component')
            obj['component_id']=name;obj['patient_connected']=True;obj['layout_id']=layout
            obj.hide_select=False;obj['seed_location']=list(obj.location);obj['seed_scale']=list(obj.scale)
            created.append(obj)
            label=text('Patient label '+name+' '+layout,'ESD' if name=='Protection' else '+' if name=='ElectrodeA' else '-',
                       (0,-.45,height/2+.04),1.3,white,col,obj,align='CENTER');created.append(label)
        pack=rounded_plate('Thin_LiPo_'+layout,settings['battery_pack_position'],(24,16,1.6),1,battery_mat,col,root,'battery_pack')
        pack['layout_id']=layout;pack['component_id']='LiPo';pack.hide_select=False;pack['seed_location']=list(pack.location);pack['seed_scale']=list(pack.scale);created.append(pack)
        # The battery is under the board; a linked outline at board height makes it legible.
        for obj in list(scene.objects):
            if obj.get('role')=='conductor' and obj.get('layout_id')==layout and obj.name.startswith('SignalTrace_'):
                bpy.data.objects.remove(obj,do_unlink=True)
            elif obj.name.startswith('PowerTrace_') and obj.get('layout_id')==layout:
                obj.data.bevel_depth=settings['power_width_mm']/2;obj['trace_width_mm']=settings['power_width_mm'];obj['trace_current_demo_a']=.15
        protection_xy=settings['patient_positions']['Protection']; afe=settings['positions']['Sensor']
        routes=[]
        for name in ['ElectrodeA','ElectrodeB']:
            x,y=settings['patient_positions'][name];px,py=protection_xy
            routes.append([(x,y),(x,py),(px,py)])
        routes.append([protection_xy,(afe[0],protection_xy[1]),afe])
        for i,route in enumerate(routes):
            for j,(a,b) in enumerate(zip(route,route[1:])):
                if a==b:continue
                trace=line(f'PatientTrace_{i}_{j}_{layout}',[(*a,3.73),(*b,3.73)],patient_wire,col,root,width=.1,role='conductor')
                trace['layout_id']=layout;trace['patient_connected']=True;trace['trace_width_mm']=.2;created.append(trace)
        for obj in created:obj['ecg_auxiliary']=True
        # ECG labels reuse existing editorial blocks.
        bpy.data.objects['Layout heading '+layout].data.body='Naive Layout' if layout=='Naive' else 'MissionPCB Layout'
        bpy.data.objects['Layout caption '+layout].data.body='ECG CHEST PATCH / FIRST PASS' if layout=='Naive' else 'ECG CHEST PATCH / MISSION VALIDATED'
        bpy.data.objects['Airflow label '+layout].data.body='PATIENT CONTACT  /  ANALOG  /  POWER'
    bpy.data.objects['Demo descriptor'].data.body='SINGLE-LEAD ECG CHEST PATCH  /  BEFORE FABRICATION'
    bpy.data.objects['Demo descriptor'].data.size=2.4
    bpy.data.objects['Demo series'].data.body='ONE DEVICE. ONE MISSION.'
    bpy.data.objects['Instructions'].data.body='Seeded offline demo. Move ECG AFE, recalculate, then Restore Demo to return to the verified layouts.'
    bpy.data.objects['Physics scope'].data.body='EXAMPLE RULES / HEAT, SPACING AND TRACE-WIDTH PROXIES / ENGINEER REVIEW REQUIRED / NO MEDICAL CERTIFICATION'
    bpy.data.objects['Footer'].location.y=-77.5
    wave=line('ECG identity waveform',[(30,76,10),(38,76,10),(41,79,10),(44,76,10),(49,76,10),(52,72,10),(55,82,10),(58,70,10),(61,76,10),(70,76,10),(74,79,10),(79,76,10),(89,76,10)],
              material('ECG identity green',GREEN,emission=True),reference,width=.32);wave['ecg_auxiliary']=True
    bom=text('BOM strip','STM32L071  |  ADS1292R  |  nRF52 BLE  |  TPS62740  |  MCP73831  |  JST-SH + LiPo',(0,-10,0),1.85,muted,reference,bpy.data.objects['Title block']);bom['ecg_auxiliary']=True
    bpy.data.objects['Header divider'].hide_render=True
    bpy.data.objects['Header divider'].hide_viewport=True
    scene['config_json']=__import__('json').dumps(config);scene['profile']='ecg'
    scene['verification_notes']='ECG pass under verification; prior generic scene preserved in astra 2.'
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                overlay=area.spaces.active.overlay
                overlay.show_relationship_lines=False;overlay.show_axis_x=False;overlay.show_axis_y=False;overlay.show_cursor=False
                area.spaces.active.region_3d.view_camera_zoom=14
    bpy.context.view_layer.update()
    face_camera(scene.camera)


def build_scene(config):
    if config['enclosure_material'] not in ['plastic','metal']:
        raise ValueError('Confirm enclosure material before building the final fixtures')
    # Only the explicit factory-startup build path calls this function.
    for obj in list(bpy.data.objects): bpy.data.objects.remove(obj,do_unlink=True)
    for col in list(bpy.data.collections): bpy.data.collections.remove(col)
    reference=collection('00_Reference'); naive=collection('01_Naive_Layout')
    corrected=collection('02_MissionPCB_Layout'); collection('03_Constraint_Overlays')
    lighting=collection('04_Cameras_Lights')
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=.001
    scene.unit_settings.length_unit='MILLIMETERS'
    scene['config_json']=__import__('json').dumps(config)
    scene['constraints_stale']=False
    ink=material('Ink',INK,emission=True); muted=material('Muted',MUTED,emission=True)
    white=material('White text',WHITE,emission=True)
    shell=material('Smoky polymer',(.18,.25,.29,.07))
    lid=material('Faint lid',(.25,.34,.38,.025))
    outline=material('Shell outline',(.30,.43,.49,1),emission=True)
    pcbmat=material('Green solder mask',(.025,.22,.13,1),metallic=.1)
    copper=material('Copper',(.82,.43,.16,1),metallic=.55)
    silk=material('Silkscreen',(.57,.82,.70,1),emission=True)
    warning=material('Wall margin',(.87,.12,.19,.06),emission=True)
    floor=material('Studio',(.87,.91,.93,1))
    grid=material('Reference grid',(.73,.80,.83,1),emission=True)
    box('Studio floor',(0,0,-3),(2000,2000,.5),floor,reference)
    for x in range(-140,141,10): line(f'GridX_{x}',[(x,-10,-2.7),(x,46,-2.7)],grid,reference,width=.022)
    for y in range(-10,47,10): line(f'GridY_{y}',[(-140,y,-2.7),(140,y,-2.7)],grid,reference,width=.022)
    header=empty('Title block',(-133,74,10),reference); header['billboard']=True
    text('MissionPCB wordmark','MISSIONPCB', (0,0,0),6.0,ink,reference,header)
    text('Demo descriptor','MISSION CONSTRAINTS  /  PHYSICAL VALIDATION', (0,-6,0),2.1,muted,reference,header)
    text('Demo series','01   /   PLACEMENT STUDY', (266,0,0),2.3,muted,reference,header,align='RIGHT')
    line('Header divider',[(-133,64,0),(133,64,0)],outline,reference,width=.075)

    for layout,settings in config['layouts'].items():
        col=naive if layout=='Naive' else corrected
        root=empty('Root_'+layout,settings['offset'],col,role='layout_root')
        root['layout_id']=layout; root.lock_location=(True,True,True); root.lock_rotation=(True,True,True); root.lock_scale=(True,True,True)
        # Hidden reference boxes represent exact air volume and access opening.
        inside=box('Interior_'+layout,(0,0,9),(90,50,18),shell,col,root,role='interior')
        inside.hide_render=True; inside.hide_viewport=True
        opening=box('Opening_'+layout,(46,0,7),(2,10,8),shell,col,root,role='opening')
        opening.hide_render=True; opening.hide_viewport=True
        walls=[('Floor',(0,0,-1),(94,54,2)),('Front',(-46,0,9),(2,50,18)),
               ('SideA',(0,-26,9),(94,2,18)),('SideB',(0,26,9),(94,2,18)),
               ('RearLeft',(46,-15,9),(2,20,18)),('RearRight',(46,15,9),(2,20,18)),
               ('RearBottom',(46,0,1.5),(2,10,3)),('RearTop',(46,0,14.5),(2,10,7)),
               ('Lid',(0,0,19),(94,54,2))]
        for label,loc,size in walls:
            obj=box(f'Shell_{label}_{layout}',loc,size,lid if label=='Lid' else shell,col,root,role='shell')
            obj['conductive']=config['enclosure_material']=='metal'
        for z in [0,18]:
            line(f'Enclosure rim {z} {layout}',[(-45,-25,z),(45,-25,z),(45,25,z),(-45,25,z),(-45,-25,z)],outline,col,root,width=.10)
        for x in [-45,45]:
            for y in [-25,25]: line(f'Enclosure corner {x} {y} {layout}',[(x,y,0),(x,y,18)],outline,col,root,width=.07)
        line('Rear opening outline '+layout,[(45,-5,3),(45,5,3),(45,5,11),(45,-5,11),(45,-5,3)],outline,col,root,width=.2)
        for label,loc,size in [('L',(-43.5,0,.15),(3,50,.12)),('R',(43.5,0,.15),(3,50,.12)),
                               ('B',(0,-23.5,.15),(84,3,.12)),('T',(0,23.5,.15),(84,3,.12))]:
            box('WallKeepout_'+label+'_'+layout,loc,size,warning,col,root)
        board=rounded_board('PCB_'+layout,col,root,pcbmat); board['layout_id']=layout
        text('Board size '+layout,'72 x 38 x 1.6 mm',(-34,-17.6,3.64),1.4,silk,col,root)
        for comp in config['components']:
            name=comp['id']; x,y=settings['positions'][name]; w,d,h=comp['dimensions']
            mat=material('Package '+name,tuple(comp['color']),metallic=.13)
            obj=box(name+'_'+layout,(x,y,3.6+h/2),(w,d,h),mat,col,root,bevel=.22,role='component')
            obj['layout_id']=layout
            for key,value in comp.items():
                if key not in ['color','dimensions','label']: obj[key if key!='id' else 'component_id']=value
            obj['nominal_dimensions_mm']=comp['dimensions']; obj['max_height_mm']=14
            if name=='Sensor': obj['min_heat_distance_mm']=15; obj['min_noise_distance_mm']=18
            if name=='RF': obj['min_noise_distance_mm']=20; obj['antenna_length_mm']=22
            if name=='Battery': obj['max_rear_gap_mm']=12
            size=1.45 if name=='Sensor' else 1.7
            text('Label_'+name+'_'+layout,comp['label'],(0,-size*.32,h/2+.045),size,white,col,obj,align='CENTER')
            # Pads are separate, selectable in Outliner and included in RF exclusion checks.
            for ix in [-1,1]:
                for iy in [-1,1]:
                    pad=box(f'Pad_{name}_{ix}_{iy}_{layout}',(ix*(w/2-.6),iy*(d/2-.65),-h/2+.035),(.7,1.0,.06),copper,col,obj,role='conductor')
                    pad['layout_id']=layout; pad['owner_id']=name
        path=settings['power_path']
        for i,(a,b) in enumerate(zip(path,path[1:])):
            trace=line(f'PowerTrace_{i}_{layout}',[(*a,3.69),(*b,3.69)],copper,col,root,width=.3,role='conductor')
            trace['layout_id']=layout; trace['trace_width_mm']=.6
        # A few low-current illustrative lines; every copper object is classified.
        for i,(a,b) in enumerate([((-10,-15),(8,-15)),((8,-15),(8,-11)),((-11,-3),(-11,0))]):
            trace=line(f'SignalTrace_{i}_{layout}',[(*a,3.67),(*b,3.67)],copper,col,root,width=.075,role='conductor')
            trace['layout_id']=layout; trace['trace_width_mm']=.15
        # Ruler in mm, separate from circuit geometry.
        line('Ruler '+layout,[(-25,-34,0),(25,-34,0)],outline,col,root,width=.1)
        for value in range(0,51,10):
            line(f'Ruler tick {value} {layout}',[(value-25,-33.1,0),(value-25,-34.9,0)],outline,col,root,width=.1)
            text(f'Ruler label {value} {layout}',str(value), (value-25,-38,0),1.65,muted,col,root,align='CENTER')
        text('Scale units '+layout,'mm',(29,-35,0),1.7,muted,col,root)
        line('Airflow '+layout,[(-28,29,1),(28,29,1),(24,31,1)],outline,col,root,width=.11)
        text('Airflow label '+layout,'FRONT   /   AIRFLOW ASSUMPTION   /   REAR',(-26,31,1),1.35,muted,col,root)
        title=empty('Layout title '+layout,(settings['offset'][0]-60,54,12),reference); title['billboard']=True
        text('Layout number '+layout,'01' if layout=='Naive' else '02',(0,0,0),3,muted,reference,title)
        text('Layout heading '+layout,'Naive Layout' if layout=='Naive' else 'MissionPCB Layout',(10,0,0),4.6,ink,reference,title)
        text('Layout caption '+layout,'FIRST PASS  /  CONSTRAINTS IGNORED' if layout=='Naive' else 'CORRECTED  /  GEOMETRY VALIDATED',(10,-4.3,0),1.65,muted,reference,title)
    # Global floor axes.
    line('X axis',[(-130,-19,0),(-120,-19,0),(-122,-18,0)],material('Axis X',RED,emission=True),reference,width=.12)
    line('Y axis',[(-130,-19,0),(-130,-9,0),(-131,-11,0)],material('Axis Y',GREEN,emission=True),reference,width=.12)
    text('Axis labels','X  /  Y',(-134,-23,0),1.5,muted,reference)
    foot=empty('Footer',(-133,-78,10),reference); foot['billboard']=True
    text('Instructions','Orbit, zoom, and select individual components. Move parts to inspect how constraints would change.',(0,0,0),1.9,ink,reference,foot)
    text('Physics scope','GEOMETRIC DEMO  /  APPROXIMATE HEAT + NOISE ZONES  /  NOT THERMAL, ELECTRICAL OR EM SIMULATION',(0,-4,0),1.6,muted,reference,foot)
    for name,loc,target,scale in [('Camera_TopDown',(0,0,420),(0,0,0),300),
        ('Camera_Isometric',(12,-200,360),(0,0,0),314),
        ('Camera_CloseConstraint',(-70,-72,110),(-70,18,5),106)]:
        data=bpy.data.cameras.new(name); data.type='ORTHO'; data.ortho_scale=scale; data.clip_end=2000
        obj=attach(bpy.data.objects.new(name,data),lighting); obj.location=loc
        obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=bpy.data.objects['Camera_Isometric']
    for name,loc,energy,size in [('Key',(-80,-60,190),28000,180),('Fill',(110,60,140),18000,150),('Rim',(0,150,160),14000,140)]:
        data=bpy.data.lights.new(name,'AREA'); data.energy=energy; data.shape='DISK'; data.size=size
        obj=attach(bpy.data.objects.new(name,data),lighting); obj.location=loc
        obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
    scene.world=bpy.data.worlds.new('Engineering world'); scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.86,.92,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
    engines=scene.render.bl_rna.properties['engine'].enum_items.keys()
    scene.render.engine='BLENDER_EEVEE' if 'BLENDER_EEVEE' in engines else 'CYCLES'
    scene.render.resolution_x=1920; scene.render.resolution_y=1080; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
    scene.view_settings.view_transform='Standard'; scene.view_settings.look='None'
    scene.render.image_settings.color_mode='RGBA'
    face_camera(scene.camera)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active; space.clip_end=2000; space.clip_start=.1
                space.shading.type='MATERIAL'; space.shading.use_scene_world=True; space.shading.use_scene_lights=True
                space.overlay.show_floor=False; space.overlay.show_extras=False
                space.region_3d.view_perspective='CAMERA'
    bpy.context.view_layer.update()
    return scene
