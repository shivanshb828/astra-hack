"""Blender-independent, millimeter-based geometric demo constraints."""
from math import acos, degrees, hypot, isfinite, sqrt
from itertools import combinations

EPS = 1e-6
CATEGORIES = ['Mechanical fit', 'Component height', 'Sensor heat separation',
              'Sensor noise separation', 'RF noise separation',
              'RF antenna keep-out', 'Battery connector access']
REQUIRED = {'MCU', 'Sensor', 'RF', 'Regulator', 'Driver', 'Battery'}


def at_least(value, limit):
    return value >= limit - EPS


def rect_overlap(a, b):
    """Inclusive rectangle intersection; boundary contact violates RF keep-out."""
    return not (a[1] < b[0]-EPS or b[1] < a[0]-EPS or
                a[3] < b[2]-EPS or b[3] < a[2]-EPS)


def point_rect_distance(p, r):
    return hypot(max(r[0]-p[0], 0, p[0]-r[1]), max(r[2]-p[1], 0, p[1]-r[3]))


def box_overlap(a, b):
    return all(min(a['max'][i], b['max'][i])-max(a['min'][i], b['min'][i]) > EPS
               for i in range(3))


def xy_rect(body):
    return [body['min'][0],body['max'][0],body['min'][1],body['max'][1]]


def evaluate_constraints(snapshot):
    """All display/report consumers use this returned result set."""
    if snapshot.get('profile')=='ecg':
        return evaluate_ecg_constraints(snapshot)
    checks = []
    errors = list(snapshot.get('errors', []))
    parts = snapshot.get('parts', [])
    ids = [p.get('id') for p in parts]
    if set(ids) != REQUIRED or len(ids) != len(REQUIRED):
        errors.append('Six unique required component IDs must be present')
    for p in parts:
        try:
            values = p['min']+p['max']+p['center']
            if not all(isfinite(v) for v in values) or any(p['max'][i]<=p['min'][i] for i in range(3)):
                errors.append(f"Invalid dimensions: {p.get('id')}")
            for key in ['heat_source','noise_source','upright','facing','heat_radius']:
                if key not in p:
                    errors.append(f"Missing {key}: {p.get('id')}")
        except (KeyError, TypeError, ValueError):
            errors.append(f"Invalid geometry: {p.get('id')}")
    for key in ['pcb','enclosure','opening','antenna']:
        if key not in snapshot:
            errors.append(f'Missing {key}')
    if errors:
        return dict(layout=snapshot.get('layout','unknown'),status='ERROR',checks=[],errors=errors,
                    categories=[dict(category=c,status='ERROR',reason=errors[0],value=None,threshold=None)
                                for c in CATEGORIES])

    by_id = {p['id']:p for p in parts}
    board, enclosure, opening = [snapshot[k] for k in ['pcb','enclosure','opening']]

    def record(id_, category, value, threshold, op, reason, subjects=(), unit='mm'):
        ok = at_least(value, threshold) if op=='>=' else at_least(threshold,value)
        checks.append(dict(id=id_,category=category,value=value,threshold=threshold,
            operator=op,unit=unit,status='PASS' if ok else 'FAIL',reason=reason,
            subjects=list(subjects),margin=(value-threshold if op=='>=' else threshold-value)))

    lateral=lambda b: min(b['min'][i]-enclosure['min'][i] for i in [0,1])
    lateral_clearance=lambda b: min(lateral(b),*(enclosure['max'][i]-b['max'][i] for i in [0,1]))
    record('pcb_wall',CATEGORIES[0],lateral_clearance(board),3,'>=','PCB wall clearance')
    record('pcb_floor',CATEGORIES[0],board['min'][2]-enclosure['min'][2],0,'>=','PCB above floor')
    record('pcb_ceiling',CATEGORIES[0],enclosure['max'][2]-board['max'][2],0,'>=','PCB below ceiling')
    for p in parts:
        name=p['id']
        edge=min(*(p['min'][i]-board['min'][i] for i in [0,1]),
                 *(board['max'][i]-p['max'][i] for i in [0,1]))
        record(f'board_{name}',CATEGORIES[0],edge,1,'>=',f'{name} PCB edge clearance',[name])
        record(f'wall_{name}',CATEGORIES[0],lateral_clearance(p),3,'>=',f'{name} wall clearance',[name])
        record(f'mount_{name}',CATEGORIES[0],abs(p['min'][2]-board['max'][2]),.05,'<=',f'{name} mounting gap',[name])
        record(f'upright_{name}',CATEGORIES[0],int(p['upright']),1,'>=',f'{name} upright',[name],unit='boolean')
        record(f'height_{name}',CATEGORIES[1],p['max'][2]-board['max'][2],14,'<=',f'{name} above PCB',[name])
        record(f'ceiling_{name}',CATEGORIES[1],enclosure['max'][2]-p['max'][2],0,'>=',f'{name} lid clearance',[name])
    for a,b in combinations(parts,2):
        record(f"collision_{a['id']}_{b['id']}",CATEGORIES[0],int(box_overlap(a,b)),0,'<=',
               f"{a['id']}/{b['id']} body overlaps",[a['id'],b['id']],unit='count')
    for name,limit in [('Sensor',12),('MCU',15)]:
        p=by_id[name]
        bx=(board['min'][0]+board['max'][0])/2; by=(board['min'][1]+board['max'][1])/2
        record(f'center_{name}',CATEGORIES[0],hypot(p['center'][0]-bx,p['center'][1]-by),limit,'<=',
               f'{name} center offset (demo policy)',[name])
    sensor=by_id['Sensor']; rf=by_id['RF']
    for p in parts:
        name=p['id']
        d=lambda target: hypot(target['center'][0]-p['center'][0],target['center'][1]-p['center'][1])
        if p['heat_source']:
            record(f'sensor_heat_{name}',CATEGORIES[2],d(sensor),15,'>=',f'Sensor to {name} centers',['Sensor',name])
            clearance=point_rect_distance(p['center'],xy_rect(sensor))
            record(f'sensor_disk_{name}',CATEGORIES[2],clearance,p['heat_radius'],'>=',
                   f'{name} center to sensor footprint',['Sensor',name])
        if p['noise_source']:
            record(f'sensor_noise_{name}',CATEGORIES[3],d(sensor),18,'>=',f'Sensor to {name} centers',['Sensor',name])
            record(f'rf_noise_{name}',CATEGORIES[4],d(rf),20,'>=',f'RF to {name} centers',['RF',name])
    antenna=snapshot['antenna']
    crossing=[c['id'] for c in antenna['conductors'] if rect_overlap(antenna['rect'],c['rect'])]
    record('antenna',CATEGORIES[5],len(crossing),0,'<=',
           'Conductors in antenna zone'+(': '+', '.join(crossing) if crossing else ''),['RF'],unit='count')
    batt=by_id['Battery']
    gap=opening['min'][0]-batt['max'][0]
    record('battery_gap',CATEGORIES[6],gap,12,'<=','Rear opening distance',['Battery'])
    record('battery_inside',CATEGORIES[6],gap,0,'>=','Connector inside enclosure',['Battery'])
    corridor=dict(min=[batt['max'][0],batt['min'][1]-1,batt['min'][2]],
                  max=[opening['max'][0],batt['max'][1]+1,batt['max'][2]+1])
    align=min(corridor['min'][1]-opening['min'][1],opening['max'][1]-corridor['max'][1],
              corridor['min'][2]-opening['min'][2],opening['max'][2]-corridor['max'][2])
    record('battery_alignment',CATEGORIES[6],align,0,'>=','Opening projection clearance',['Battery'])
    direction=batt['facing']; norm=sqrt(sum(v*v for v in direction))
    angle=degrees(acos(max(-1,min(1,direction[0]/norm)))) if norm>EPS else 180
    record('battery_facing',CATEGORIES[6],angle,5,'<=','Connector facing rear',['Battery'],unit='degrees')
    obstacles=[p['id'] for p in parts if p['id']!='Battery' and box_overlap(corridor,p)]
    record('battery_corridor',CATEGORIES[6],len(obstacles),0,'<=','Insertion corridor obstacles'+
           (': '+', '.join(obstacles) if obstacles else ''),['Battery'],unit='count')

    categories=[]
    # Prefer useful dashboard measurements over trivial mounting/collision zeroes.
    preferred={CATEGORIES[0]:'pcb_wall',CATEGORIES[1]:'height_Battery',CATEGORIES[2]:'sensor_heat_Regulator',
               CATEGORIES[3]:'sensor_noise_Regulator',CATEGORIES[4]:'rf_noise_Regulator',
               CATEGORIES[5]:'antenna',CATEGORIES[6]:'battery_gap'}
    for category in CATEGORIES:
        entries=[r for r in checks if r['category']==category]
        failed=[r for r in entries if r['status']=='FAIL']
        critical=min(failed,key=lambda r:r['margin']) if failed else next(r for r in entries if r['id']==preferred[category])
        categories.append(dict(critical,category=category,status='FAIL' if failed else 'PASS',
                               check_count=len(entries),failure_count=len(failed)))
    return dict(layout=snapshot['layout'],status='FAIL' if any(r['status']=='FAIL' for r in checks) else 'PASS',
                checks=checks,categories=categories,errors=[])


ECG_CATEGORIES=['Patch mechanical fit','Patient-contact heat proxy','ECG analog noise separation',
    'Patient-connected spacing','RF antenna keep-out','Regulator / battery heat zone',
    'Power trace width proxy','Connector / assembly access']


def rect_distance(a,b):
    return hypot(max(a[0]-b[1],b[0]-a[1],0),max(a[2]-b[3],b[2]-a[3],0))


def evaluate_ecg_constraints(snapshot):
    """Configurable geometric demo policies, not medical/thermal/ampacity certification."""
    base=evaluate_constraints(dict(snapshot,profile='generic'))
    errors=base['errors'][:]
    for key in ['patient_parts','patient_paths','contact_region','battery_pack','power_traces']:
        if key not in snapshot: errors.append('Missing ECG geometry: '+key)
    if not errors and (len(snapshot['patient_parts'])!=3 or not snapshot['power_traces']):
        errors.append('Expected protection, two electrodes and at least one power trace')
    if errors:
        return dict(layout=snapshot['layout'],status='ERROR',checks=[],errors=errors,
            categories=[dict(category=c,status='ERROR',reason=errors[0],value=None,threshold=None) for c in ECG_CATEGORIES])
    rules=dict(afe_power_mm=20,afe_rf_mm=20,afe_digital_mm=18,patient_spacing_mm=3,
               trace_width_mm=.6,battery_heat_radius_mm=9,mcu_center_mm=18)
    rules.update(snapshot.get('ecg_rules',{}))
    checks=[]
    mapping={CATEGORIES[0]:ECG_CATEGORIES[0],CATEGORIES[1]:ECG_CATEGORIES[0],
             CATEGORIES[2]:ECG_CATEGORIES[5],CATEGORIES[5]:ECG_CATEGORIES[4],CATEGORIES[6]:ECG_CATEGORIES[7]}
    for r in base['checks']:
        if r['category'] in mapping and r['id']!='center_MCU':
            checks.append(dict(r,category=mapping[r['category']],reason=r['reason'].replace('Sensor','ECG AFE').replace('Driver','Charger')))

    def record(id_,category,value,limit,reason,subjects=(),op='>=',unit='mm'):
        passed=at_least(value,limit) if op=='>=' else at_least(limit,value)
        checks.append(dict(id=id_,category=category,value=value,threshold=limit,operator=op,unit=unit,
            status='PASS' if passed else 'FAIL',reason=reason,subjects=list(subjects),margin=value-limit if op=='>=' else limit-value))
    parts={p['id']:p for p in snapshot['parts']}; sensor=parts['Sensor']
    mcu=parts['MCU']; record('center_MCU',ECG_CATEGORIES[0],hypot(*mcu['center'][:2]),rules['mcu_center_mm'],'MCU center offset',op='<=')
    board=snapshot['pcb']; aux=snapshot['patient_parts']+[snapshot['battery_pack']]
    for p in aux:
        edge=min(*(p['min'][i]-board['min'][i] for i in [0,1]),*(board['max'][i]-p['max'][i] for i in [0,1]))
        record('aux_fit_'+p['id'],ECG_CATEGORIES[0],edge,1,p['id']+' board envelope')
        record('aux_floor_'+p['id'],ECG_CATEGORIES[0],p['min'][2]-snapshot['enclosure']['min'][2],0,p['id']+' floor clearance')
        record('aux_ceiling_'+p['id'],ECG_CATEGORIES[0],snapshot['enclosure']['max'][2]-p['max'][2],0,p['id']+' lid clearance')
    for a,b in combinations(list(parts.values())+aux,2):
        if a in snapshot['parts'] and b in snapshot['parts']: continue
        record('aux_collision_'+a['id']+'_'+b['id'],ECG_CATEGORIES[0],int(box_overlap(a,b)),0,
               a['id']+'/'+b['id']+' body overlap',op='<=',unit='count')
    for name,key in [('Regulator','afe_power_mm'),('RF','afe_rf_mm'),('MCU','afe_digital_mm')]:
        p=parts[name]; d=hypot(sensor['center'][0]-p['center'][0],sensor['center'][1]-p['center'][1])
        record('ecg_noise_'+name,ECG_CATEGORIES[2],d,rules[key],'AFE to '+name+' centers',['Sensor',name])
    pack=snapshot['battery_pack']; region=xy_rect(snapshot['contact_region'])
    sources=[(parts['Regulator'],parts['Regulator']['heat_radius']),(parts['Driver'],parts['Driver']['heat_radius']),
             (pack,rules['battery_heat_radius_mm'])]
    for source,radius in sources:
        d=point_rect_distance(source['center'],region)
        record('skin_heat_'+source['id'],ECG_CATEGORIES[1],d,radius,'Source to designated contact region; heat proxy',[source['id']])
    record('battery_afe_heat',ECG_CATEGORIES[5],point_rect_distance(pack['center'],xy_rect(sensor)),rules['battery_heat_radius_mm'],
           'LiPo center to AFE footprint; heat proxy',['Sensor','LiPo'])
    patient=[sensor]+snapshot['patient_parts']+snapshot['patient_paths']
    others=[p for p in parts.values() if p['id']!='Sensor']+[pack]
    for a in patient:
        for b in others:
            record('patient_gap_'+a['id']+'_'+b['id'],ECG_CATEGORIES[3],rect_distance(xy_rect(a),xy_rect(b)),
                   rules['patient_spacing_mm'],a['id']+' to '+b['id']+' XY envelope; spacing proxy',[a['id'],b['id']])
    for trace in snapshot['power_traces']:
        record('trace_width_'+trace['id'],ECG_CATEGORIES[6],trace['width'],rules['trace_width_mm'],
               'Measured copper width; example threshold, not ampacity',[trace['id']])
    categories=[]
    preferred=['pcb_wall','skin_heat_Driver','ecg_noise_Regulator',None,'antenna','sensor_disk_Driver',None,'battery_gap']
    for category,wanted in zip(ECG_CATEGORIES,preferred):
        rows=[r for r in checks if r['category']==category]; fails=[r for r in rows if r['status']=='FAIL']
        critical=min(fails,key=lambda r:r['margin']) if fails else next((r for r in rows if r['id']==wanted),min(rows,key=lambda r:r['margin']))
        categories.append(dict(critical,status='FAIL' if fails else 'PASS',failure_count=len(fails),check_count=len(rows)))
    return dict(layout=snapshot['layout'],profile='ecg',status='FAIL' if any(r['status']=='FAIL' for r in checks) else 'PASS',
                checks=checks,categories=categories,errors=[])
