"""Pinned upstream engine adapter. No network, no tolerant part defaults."""
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path
import bpy
from mathutils import Vector

MAPPING = {'MCU':'msp430fr2433','Sensor':'ads1292r','RF':'mdbt42q','Regulator':'tps62740','Driver':'mcp73831','Battery':'bm02b_srss'}
CATEGORIES = {'MCU':'processor','Sensor':'sensor','RF':'wireless','Regulator':'power_regulator','Driver':'driver','Battery':'connector'}


def engine():
    bundle=json.loads(bpy.data.texts['engine_bundle.json'].as_string())
    digest=hashlib.sha256(json.dumps(bundle,sort_keys=True).encode()).hexdigest()
    root=Path(tempfile.gettempdir())/('missionpcb_engine_'+digest[:16]); package=root/'constraint_engine'
    package.mkdir(parents=True,exist_ok=True)
    for name,content in bundle['engine'].items():
        if Path(name).name!=name or not name.endswith('.py'): raise ValueError('Invalid bundled module')
        p=package/name
        if not p.exists() or p.read_text()!=content:p.write_text(content)
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    import constraint_engine as e
    if Path(e.__file__).parent!=package:raise ValueError('Different engine already loaded; restart Blender before changing engine version')
    return e,bundle,digest


def inputs(runtime,name):
    e,bundle,digest=engine();scene=bpy.context.scene
    if abs(scene.unit_settings.scale_length-.001)>1e-9:raise ValueError('Expected one Blender unit per millimetre')
    snap=runtime.extract_scene_snapshot(name)
    if snap['errors']:raise ValueError('; '.join(snap['errors']))
    pcb=snap['pcb'];enc=snap['enclosure']
    size=lambda b:[b['max'][i]-b['min'][i] for i in range(3)]
    ps=size(pcb);es=size(enc)
    objs=[o for o in scene.objects if o.get('role')=='component' and o.get('layout_id')==name]
    ids=[o.get('component_id') for o in objs]
    if len(ids)!=len(set(ids)) or set(ids)!=set(MAPPING):raise ValueError('Missing, duplicate or unsupported component IDs')
    parts={};placements=[];bindings=[]
    root=bpy.data.objects['Root_'+name]
    for obj in objs:
        ref=obj['component_id'];pid=MAPPING[ref];record=bundle['catalog'][pid]
        matrix=root.matrix_world.inverted()@obj.matrix_world
        if (matrix.to_3x3()@Vector((0,0,1))).normalized().z<.99999:raise ValueError(ref+': tilted package unsupported')
        angle=math.degrees(math.atan2(matrix[1][0],matrix[0][0]))%360
        rot=round(angle/90)*90%360
        if abs((angle-rot+180)%360-180)>.01:raise ValueError(ref+': use 90 degree rotation increments')
        b=runtime.bounds(obj,root);dims=size(b)
        if any(not math.isfinite(v) for v in sum([b['min'],b['max']],[])) or min(dims)<=0:raise ValueError(ref+': invalid mesh bounds')
        if abs(b['min'][2]-pcb['max'][2])>.05:raise ValueError(ref+': package must sit on PCB top')
        native=dims[:]
        if rot%180:native[0],native[1]=native[1],native[0]
        # Native CAD dimensions drive geometry; catalog dimensions remain separate cited facts.
        parts[pid]=e.Part(id=pid,name=record['mpn'],category=CATEGORIES[ref],length_mm=native[0],width_mm=native[1],height_mm=native[2],
            heat_source=ref in ('Regulator','Driver'),noise_source=ref in ('Regulator','MCU','RF'),
            sensitivity='high' if ref in ('Sensor','RF') else 'low',
            heat_zone_radius_mm=float(obj.get('heat_radius',0)) or None,
            raw=record,datasheet_url=record.get('provenance',{}).get('datasheet_url'))
        if ref=='RF':parts[pid].keepout=e.Keepout(float(obj.get('antenna_length_mm',22)),native[1],'-x')
        center=[(b['min'][i]+b['max'][i])/2 for i in range(3)]
        placements.append(e.Placement(ref,pid,center[0]-pcb['min'][0],center[1]-pcb['min'][1],rot))
        bindings.append({'ref':ref,'part_id':pid,'object':obj.name,'mesh_bounds_mm':dims,'catalog_mechanical':record.get('mechanical',{}),'geometry_basis':obj.get('geometry_basis','Unverified model'),'cad_hash':obj.get('cad_source_sha256','')})
    rules=json.loads(scene['config_json']).get('ecg_rules',{})
    mission=[e.MissionRule('afe_'+ref,'min_separation',['Sensor',ref],float(rules.get(key,default)),'center',rationale='Authored demo clearance; not derived from datasheet physics.') for ref,key,default in [('MCU','afe_digital_mm',18),('RF','afe_rf_mm',20),('Regulator','afe_power_mm',20)]]
    layout=e.Layout(name,e.Enclosure(*es,wall_keepout_mm=0),e.Board('PCB_'+name,*ps,origin_mm=tuple(pcb['min'][i]-enc['min'][i] for i in range(3)),edge_margin_mm=1,max_component_height_mm=enc['max'][2]-pcb['max'][2],min_component_gap_mm=.5),placements,distance_metric='center',mission_rules=mission)
    return layout,parts,bindings,snap,digest


def compute(runtime):
    e,bundle,digest=engine();outputs={};snapshots={};bindings={}
    for name in ('Naive','MissionPCB'):
        layout,parts,links,snap,_=inputs(runtime,name)
        warnings=['Geometry uses actual CAD bounds; catalog properties retain source conditions.',
            'Heat radii, antenna extent and separations are authored demo policies, not solved physics.',
            'Coverage gap: under-board battery, patient contacts, copper paths and top-entry mating are not checked by this bridge.',
            'Some CAD models are approximate; catalog attachment does not certify package geometry.']
        result=e.validate(layout,parts,warnings).to_dict()
        result['coverage_complete']=False;result['passed']=False
        result['checks'].append({'id':'coverage.unmodeled','title':'Patient / battery / routing coverage','status':'SKIP','severity':'info','subjects':[],'message':warnings[2]})
        result['summary']['SKIP']+=1
        outputs[name]=result;snapshots[name]=snap;bindings[name]=links
    return {'engine_revision':bundle['revision'],'bundle_sha256':digest,'results':outputs,'bindings':bindings,'snapshots':snapshots}


def draw(runtime,payload):
    s=runtime.load_embedded('scene_builder');sys.modules['scene_builder']=s
    runtime.load_embedded('overlays').clear_overlays()
    before=set(bpy.data.objects.keys());col=s.collection('03_Constraint_Overlays')
    for name,result in payload['results'].items():
        root=bpy.data.objects['Root_'+name];enc=payload['snapshots'][name]['enclosure']
        def local(p):return tuple(p[i]+enc['min'][i] for i in range(3))
        white=s.material('Engine white',(.85,.95,1,1),emission=True)
        amber=s.material('Engine amber',(1,.65,.12,1),emission=True)
        dashboard=s.empty('Dashboard_'+name,(root.location.x,-48,16),col);dashboard['billboard']=True
        s.box('Engine dashboard '+name,(0,0,-.25),(132,50,.4),s.material('Engine panel',(.018,.041,.061,1)),col,dashboard)
        summary=result['summary'];title=f"{name}: {summary['FAIL']} FAIL / {summary['SKIP']} SKIP"
        s.text('Dashboard total '+name,title,(-61,18,.1),3,white,col,dashboard)
        rows=[c for c in result['checks'] if c['status']=='FAIL'][:5]
        if not rows:rows=[{'title':'Configured geometry checks pass; coverage incomplete','status':'SKIP'}]
        for i,c in enumerate(rows):s.text('Row status '+str(i)+' '+name,c['status']+'  '+c['title'][:68],(-61,11-i*5,.1),1.85,amber,col,dashboard)
        s.text('Snapshot notice '+name,'UPSTREAM ENGINE / GEOMETRIC POLICIES / COVERAGE GAPS',(-61,-21,.1),1.55,amber,col,dashboard)
        overlays=[c['overlay'] for c in result['checks'] if c.get('overlay') and c['status']=='FAIL'][:12]+result['zone_overlays']
        for i,o in enumerate(overlays):
            mat=s.material('Engine overlay '+name+str(i),tuple(o['color'])+(1,),emission=True)
            if o['type']=='measure_line':s.line('Relation '+name+str(i),[local(o['from']),local(o['to'])],mat,col,root,width=.1)
            elif o['type']=='zone_circle':
                p=local(o['center']);r=o['radius_mm'];obj=s.line('Engine zone '+name+str(i),[(p[0]+r*math.cos(a*math.tau/64),p[1]+r*math.sin(a*math.tau/64),p[2]) for a in range(65)],mat,col,root,width=.08);obj['zone']=True
            elif o['type']=='zone_rect':
                p=local(o['center']);x,y=o['size_mm'][:2];obj=s.line('Engine zone '+name+str(i),[(p[0]+a*x/2,p[1]+b*y/2,p[2]) for a,b in [(-1,-1),(1,-1),(1,1),(-1,1),(-1,-1)]],mat,col,root,width=.08);obj['zone']=True
    for o in bpy.data.objects:
        if o.name not in before:o['dynamic_overlay']=True
    s.face_camera(bpy.context.scene.camera)


def recalculate(runtime):
    scene=bpy.context.scene;bpy.context.view_layer.update()
    payload=compute(runtime) # fail before changing objects or the last good result
    payload['geometry_signature']=runtime.signature()
    payload['revision']=int(scene.get('engine_revision_counter',0))+1
    draw(runtime,payload)
    for links in payload['bindings'].values():
        for link in links:
            obj=bpy.data.objects[link['object']];obj['catalog_part_id']=link['part_id'];obj['catalog_record_json']=json.dumps(engine()[1]['catalog'][link['part_id']])
    scene['engine_results_json']=json.dumps(payload,allow_nan=False);scene['engine_revision_counter']=payload['revision']
    display={name:{'categories':[{'category':k,'status':'FAIL' if any(c['status']=='FAIL' for c in r['checks'] if c['id'].startswith(k)) else 'PASS'} for k in ['fit.','mission.','zone.']], 'status':'INCOMPLETE'} for name,r in payload['results'].items()}
    for r in display.values():r['categories'].append({'category':'Patient / battery / routing','status':'SKIP'})
    scene['results_json']=json.dumps(display);scene['validated_signature']=runtime.signature();scene['constraints_stale']=False
    runtime.apply_presentation_visibility()
    return display


def export(runtime,directory):
    if bpy.context.scene.get('constraints_stale') or runtime.signature()!=bpy.context.scene.get('validated_signature'):recalculate(runtime)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    p=directory/'engine_validation_results.json';tmp=p.with_suffix('.json.tmp');tmp.write_text(bpy.context.scene['engine_results_json']);tmp.replace(p)
    return directory


def optimize(runtime):
    e,_,_=engine();layout,parts,_,snap,_=inputs(runtime,'MissionPCB')
    # Search only core packages; do not imply this routes copper or solves excluded parts.
    solved,cost=e.solve(layout,parts,seeds=(0,))
    if not math.isfinite(cost):raise ValueError('No finite placement candidate')
    old={};root=bpy.data.objects['Root_MissionPCB']
    try:
        for p in solved.placements:
            obj=next(o for o in bpy.context.scene.objects if o.get('layout_id')=='MissionPCB' and o.get('role')=='component' and o.get('component_id')==p.ref)
            old[obj.name]=(obj.location.copy(),obj.rotation_euler.copy())
            obj.location.x=p.x_mm+snap['pcb']['min'][0];obj.location.y=p.y_mm+snap['pcb']['min'][1];obj.rotation_euler.z=math.radians(p.rotation_deg)
        bpy.context.view_layer.update()
        actual,actual_parts,_,_,_=inputs(runtime,'MissionPCB')
        expected=e.validate(solved,parts).to_dict();observed=e.validate(actual,actual_parts).to_dict()
        a={c['id']:c for c in expected['checks']};b={c['id']:c for c in observed['checks']}
        if set(a)!=set(b):raise ValueError('Solver / mesh check set mismatch')
        for key in a:
            if a[key]['status']!=b[key]['status']:raise ValueError('Solver / mesh status mismatch: '+key)
            for metric in ['measured_mm','required_mm','margin_mm']:
                x,y=a[key].get(metric),b[key].get(metric)
                if x is not None and y is not None and abs(x-y)>.002:raise ValueError('Solver / mesh metric mismatch: '+key)
        recalculate(runtime)
        bpy.context.scene['engine_solver_residual_cost']=cost
    except Exception:
        for name,(loc,rot) in old.items():bpy.data.objects[name].location=loc;bpy.data.objects[name].rotation_euler=rot
        bpy.context.view_layer.update();raise
