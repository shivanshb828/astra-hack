"""Generated overlays; status always comes from the constraint engine."""
import math
import bpy
from mathutils import Matrix, Vector
import scene_builder as s


def clear_overlays():
    for obj in list(bpy.data.objects):
        if obj.get('dynamic_overlay'):
            data=obj.data; bpy.data.objects.remove(obj,do_unlink=True)
            if data and data.users==0:
                if isinstance(data,bpy.types.Mesh): bpy.data.meshes.remove(data)
                elif isinstance(data,bpy.types.Curve): bpy.data.curves.remove(data)


def marker(name,pos,passed,col,parent,mat):
    x,y,z=pos
    if passed:
        s.line(name,[(x-.75,y,z),(x-.1,y-.65,z),(x+1.2,y+.9,z)],mat,col,parent,width=.15)
    else:
        s.line(name+' A',[(x-.7,y-.7,z),(x+.7,y+.7,z)],mat,col,parent,width=.15)
        s.line(name+' B',[(x-.7,y+.7,z),(x+.7,y-.7,z)],mat,col,parent,width=.15)


def update_overlays(results,snapshots):
    clear_overlays()
    initial=set(bpy.data.objects.keys())
    col=s.collection('03_Constraint_Overlays')
    good=s.material('PASS',s.GREEN,emission=True); bad=s.material('FAIL',s.RED,emission=True)
    white=s.material('White text',s.WHITE,emission=True)
    muted=s.material('Panel muted',(.47,.64,.69,1),emission=True)
    ink=s.material('Ink',s.INK,emission=True)
    panelmat=s.material('Dashboard background',(.018,.041,.061,1),emission=True)
    rulemat=s.material('Dashboard rules',(.07,.14,.18,1),emission=True)
    purple=s.material('RF boundary',(.39,.17,.7,1),emission=True)
    zone=s.material('RF zone',(.4,.20,.8,.12),emission=True)
    for layout,result in results.items():
        ecg=result.get('profile')=='ecg'; count=len(result['categories'])
        root=bpy.data.objects['Root_'+layout]
        parts={o['component_id']:o for o in bpy.context.scene.objects if o.get('role')=='component' and o.get('layout_id')==layout}
        passed=sum(r['status']=='PASS' for r in result['categories'])
        dashboard=s.empty('Dashboard_'+layout,(root.location.x,-48,16),col)
        dashboard['billboard']=True
        s.box('Dashboard surface '+layout,(0,0,-.25),(132,54 if ecg else 49,.4),panelmat,col,dashboard,bevel=.5)
        s.text('Dashboard title '+layout,'ECG Mission Constraint Check' if ecg else 'MissionPCB Constraint Check',(-61,21 if ecg else 18.4,.1),3.05,white,col,dashboard)
        s.text('Dashboard total '+layout,f'{passed}/{count} PASS',(60,21 if ecg else 18.4,.1),2.8,good if passed==count else bad,col,dashboard,align='RIGHT')
        s.line('Dashboard header rule '+layout,[(-61,17.5 if ecg else 15.2,.1),(61,17.5 if ecg else 15.2,.1)],rulemat,col,dashboard,width=.07)
        for i,row in enumerate(result['categories']):
            y=(13 if ecg else 10.7)-i*4.55; mat=good if row['status']=='PASS' else bad
            s.text(f'Row label {i} {layout}',row['category'],(-61,y,.1),2.6,white,col,dashboard)
            s.text(f'Row status {i} {layout}',row['status'],(3,y,.1),2.65,mat,col,dashboard)
            if row['value'] is None: detail='Incomplete geometry'
            elif row['unit']=='count': detail=f"{int(row['value'])} "+('crossings' if row['id']=='antenna' else 'overlaps')
            elif row['unit']=='degrees': detail=f"{row['value']:.1f} deg / max {row['threshold']:g}"
            else:
                prefix='wall' if i==0 else 'gap' if ecg and i in [1,3,5] else 'width' if ecg and i==6 else 'rear' if row['id']=='battery_gap' else 'd'
                value=f"{row['value']:.2f}" if prefix=='width' else f"{row['value']:.1f}"
                detail=f"{prefix} {value} / {row['operator']} {row['threshold']:g} mm"
            s.text(f'Row value {i} {layout}',detail,(24,y,.1),2.15,muted,col,dashboard)
        s.text('Snapshot notice '+layout,'EXAMPLE GEOMETRIC RULES / Recalculate after edits' if ecg else 'SNAPSHOT  /  Recalculate after edits',(-61,-24.3 if ecg else -21.9,.1),1.85,muted,col,dashboard)
        # Heat disks follow actual body position; radius metadata defines the rule.
        for name in ['Regulator','Driver']:
            if name not in parts: continue
            body=parts[name]; p=body.location; radius=body.get('heat_radius',0)
            if radius<=0: continue
            color=(1,.30,.05,.055) if name=='Regulator' else (.94,.08,.10,.055)
            if ecg and all(r['status']=='PASS' for r in result['checks'] if r['id'].startswith('skin_heat')):color=(.05,.6,.42,.05)
            heat=s.material('Influence '+name+(' ECG '+layout if ecg else ''),color,emission=True)
            edge=s.material('Influence edge '+name+(' ECG '+layout if ecg else ''),(*color[:3],.40),emission=True)
            disk=s.disk(f'HeatZone_{name}_{layout}',(p.x,p.y,3.78),radius,heat,col,root); disk['zone']=True
            ring=s.line(f'HeatRadius_{name}_{layout}',[(p.x+radius*math.cos(j*math.tau/96),p.y+radius*math.sin(j*math.tau/96),3.81) for j in range(97)],edge,col,root,width=.09); ring['zone']=True
        if 'RF' in parts:
            antenna=snapshots[layout]['antenna']; x0,x1,y0,y1=antenna['rect']; z=antenna['plane_z']
            frame=s.empty('RF zone frame '+layout,(0,0,0),col); frame.matrix_world=Matrix(antenna['frame'])
            patch=s.box('RFKeepout_'+layout,((x0+x1)/2,(y0+y1)/2,z),(x1-x0,y1-y0,.045),zone,col,frame); patch['zone']=True
            boundary=s.line('RFKeepout boundary '+layout,[(x0,y0,z+.04),(x1,y0,z+.04),(x1,y1,z+.04),(x0,y1,z+.04),(x0,y0,z+.04)],purple,col,frame,width=.12); boundary['zone']=True
            caption=s.text('RF zone label '+layout,f'ANTENNA / {x1-x0:g} mm',((x0+x1)/2,(y0+y1)/2,z+.1),1.55,purple,col,frame,align='CENTER'); caption['zone']=True
        # One line per pair; sensor heat and noise share the same XY center distance.
        pair_ids=['ecg_noise_MCU','ecg_noise_Regulator','ecg_noise_RF'] if ecg else ['sensor_noise_Driver','sensor_noise_Regulator','rf_noise_Regulator']
        by_id={r['id']:r for r in result['checks']}
        for n,id_ in enumerate(pair_ids):
            if id_ not in by_id: continue
            row=by_id[id_]; a,b=[parts[name].location for name in row['subjects']]
            related=[r for r in result['checks'] if r['subjects']==row['subjects'] and r['category'] in ['Sensor heat separation','Sensor noise separation','RF noise separation']]
            ok=row['status']=='PASS' if ecg else all(r['status']=='PASS' for r in related); mat=good if ok else bad
            z=10.7+n*.3
            s.line(f'Relation {id_} {layout}',[(a.x,a.y,z),(b.x,b.y,z)],mat,col,root,width=.13)
            midpoint=Vector(((a.x+b.x)/2,(a.y+b.y)/2,z))
            # Midpoint labels face active camera and get a small backing to stay legible.
            label_position=midpoint.copy()
            label_position.y=midpoint.y-8 if n==0 else 21 if n==1 else 27
            s.line('Distance leader '+id_+' '+layout,[tuple(midpoint),tuple(label_position)],mat,col,root,width=.055)
            label=s.empty('Distance '+id_+' '+layout,root.matrix_world@label_position,col); label['billboard']=True
            s.box('Distance backing '+id_+' '+layout,(0,1,0),(18,3,.12),s.material('Label paper',(.90,.94,.95,1),emission=True),col,label)
            s.text('Distance text '+id_+' '+layout,f"{row['value']:.1f} mm",(0,.25,.1),2.05,mat,col,label,align='CENTER')
            marker('Pair marker '+id_+' '+layout,(midpoint.x,midpoint.y-2.5,z),ok,col,root,mat)
        if 'Battery' in parts:
            p=parts['Battery'].location; row=result['categories'][-1]
            ok=row['status']=='PASS'; mat=good if ok else bad
            s.line('Battery access '+layout,[(p.x+5,p.y,9),(45,0,9)],mat,col,root,width=.14)
            marker('Battery access marker '+layout,(43,0,10),ok,col,root,mat)
        if 'antenna' in by_id and 'RF' in parts:
            rf=parts['RF']; ok=by_id['antenna']['status']=='PASS'
            marker('Antenna marker '+layout,(rf.location.x-15,rf.location.y+7,9),ok,col,root,good if ok else bad)
        if ecg:
            snap=snapshots[layout]; region=snap['contact_region']; x0,y0=region['min'][:2];x1,y1=region['max'][:2]
            cyan=s.material('Patient zone cyan',(.01,.7,.78,.09),emission=True)
            cyan_edge=s.material('Patient zone edge',(.025,.6,.67,1),emission=True)
            s.box('Patient-connected zone '+layout,((x0+x1)/2,(y0+y1)/2,3.72),(x1-x0,y1-y0,.03),cyan,col,root)
            s.line('Patient zone outline '+layout,[(x0,y0,3.8),(x1,y0,3.8),(x1,y1,3.8),(x0,y1,3.8),(x0,y0,3.8)],cyan_edge,col,root,width=.11)
            s.text('Patient surface label '+layout,'PATIENT CONTACT SURFACE / ELECTRODE SNAPS',(-44,-30,0),1.4,ink,col,root)
            afe=parts['Sensor']; x,y=afe.location[:2]
            region_mat=s.material('Protected ECG '+layout,(.05,.68,.4,.12) if result['categories'][2]['status']=='PASS' else (.9,.12,.06,.10),emission=True)
            s.box('Protected ECG AFE zone '+layout,(x,y,3.77),(10,10,.03),region_mat,col,root)
            noise_edge=s.material('Noise rings',(.28,.3,.75,.24),emission=True)
            for name,radius in [('RF',20),('Regulator',20),('MCU',18)]:
                p=parts[name].location
                for start in range(0,96,8):
                    ring=s.line(f'Noise arc {name} {start} {layout}',[(p.x+radius*math.cos(j*math.tau/96),p.y+radius*math.sin(j*math.tau/96),3.84) for j in range(start,start+5)],noise_edge,col,root,width=.06);ring['zone']=True
            pack=snap['battery_pack']; x0,y0=pack['min'][:2];x1,y1=pack['max'][:2]
            battery_edge=s.material('Battery hidden layer',(.6,.57,.30,.65),emission=True)
            s.line('LiPo under-board outline '+layout,[(x0,y0,3.79),(x1,y0,3.79),(x1,y1,3.79),(x0,y1,3.79),(x0,y0,3.79)],battery_edge,col,root,width=.08)
            s.text('Thin battery label '+layout,'LiPo below PCB',(22,-26,0),1.5,ink,col,root,align='CENTER')
            pack_ok=by_id['skin_heat_LiPo']['status']=='PASS'
            pack_heat=s.material('Battery heat '+layout,(.08,.6,.45,.07) if pack_ok else (.95,.15,.04,.12),emission=True)
            heat=s.disk('LiPo heat zone '+layout,(*pack['center'][:2],3.83),snap.get('ecg_rules',{}).get('battery_heat_radius_mm',9),pack_heat,col,root);heat['zone']=True
    for obj in bpy.data.objects:
        if obj.name not in initial: obj['dynamic_overlay']=True
    s.face_camera(bpy.context.scene.camera)
    bpy.context.view_layer.update()
