"""Run this embedded Text block once to enable the MissionPCB sidebar."""
import hashlib
import importlib.util
import json
import platform
from pathlib import Path
import sys
import types
from datetime import datetime
import bpy
from mathutils import Matrix, Vector


def load_embedded(name):
    key='missionpcb_'+name
    if key in sys.modules: return sys.modules[key]
    filename=name+'.py'
    mod=types.ModuleType(key); mod.__file__=filename
    sys.modules[key]=mod
    if filename in bpy.data.texts:
        exec(compile(bpy.data.texts[filename].as_string(),filename,'exec'),mod.__dict__)
    else:
        path=Path(__file__).resolve().parent/filename
        exec(compile(path.read_text(),str(path),'exec'),mod.__dict__)
    return mod


def dependencies():
    engine=load_embedded('constraints')
    builder=load_embedded('scene_builder')
    # Overlay helpers import the explicitly bundled scene builder.
    sys.modules['scene_builder']=builder
    return engine,load_embedded('overlays')


def corners(obj,frame=None):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    matrix=evaluated.matrix_world
    # Disabled reference volumes are not evaluated by Blender's dependency graph.
    # They have no modifiers/constraints: explicitly compose their parent transform.
    if obj.get('role') in ['interior','opening','contact_region']:
        matrix=obj.parent.matrix_world@obj.matrix_parent_inverse@obj.matrix_basis
    if frame is not None:
        frame_matrix=frame.matrix_world if hasattr(frame,'matrix_world') else frame
        matrix=frame_matrix.inverted()@matrix
    return [matrix@Vector(p) for p in evaluated.bound_box]


def bounds(obj,frame=None):
    vertices=corners(obj,frame)
    return dict(min=[min(v[i] for v in vertices) for i in range(3)],
                max=[max(v[i] for v in vertices) for i in range(3)])


def extract_scene_snapshot(layout):
    objects=list(bpy.context.scene.objects); errors=[]
    snapshot=dict(layout=layout,parts=[],errors=errors)
    config=json.loads(bpy.context.scene.get('config_json','{}'))
    snapshot['profile']=config.get('profile','generic')
    root=bpy.data.objects.get('Root_'+layout)
    if root is None:
        errors.append('Missing layout root'); return snapshot
    for key,name in [('pcb','PCB_'),('enclosure','Interior_'),('opening','Opening_')]:
        obj=bpy.data.objects.get(name+layout)
        if obj is None: errors.append('Missing '+name+layout)
        else: snapshot[key]=bounds(obj,root)
    parts=[o for o in objects if o.get('role')=='component' and o.get('layout_id')==layout]
    for obj in parts:
        b=bounds(obj,root); matrix=root.matrix_world.inverted()@obj.matrix_world
        center=matrix.translation; up=matrix.to_3x3()@Vector((0,0,1))
        part=dict(b,id=obj.get('component_id'),center=list(center),
                  upright=up.normalized().dot(Vector((0,0,1)))>.9999,
                  facing=list(matrix.to_3x3()@Vector((1,0,0))))
        for prop in ['heat_source','noise_source','heat_radius','sensitive','component_type','part_name','datasheet_url','geometry_basis']:
            if prop in obj: part[prop]=obj[prop]
        if min(abs(v) for v in obj.scale)<1e-7: errors.append('Zero component scale: '+obj.name)
        snapshot['parts'].append(part)
    rf=next((o for o in parts if o.get('component_id')=='RF'),None)
    if rf:
        # Extract local dimensions from actual geometry; zone follows RF transform.
        frame=Matrix.Translation(rf.matrix_world.translation)@rf.matrix_world.to_quaternion().to_matrix().to_4x4()
        local=bounds(rf,frame); antenna_rect=[local['min'][0]-float(rf.get('antenna_length_mm',22)),local['min'][0],local['min'][1],local['max'][1]]
        conductors=[]
        for obj in objects:
            if obj==rf or obj.get('owner_id')=='RF': continue
            if obj.get('layout_id')!=layout and obj.parent!=root: continue
            role=obj.get('role')
            if role not in ['component','conductor','patient_component','battery_pack'] and not (role=='shell' and obj.get('conductive')): continue
            b=bounds(obj,frame)
            conductors.append(dict(id=obj.name,rect=[b['min'][0],b['max'][0],b['min'][1],b['max'][1]]))
        snapshot['antenna']=dict(rect=antenna_rect,conductors=conductors,frame=list(map(list,frame)),plane_z=local['min'][2]+.22)
    if snapshot['profile']=='ecg':
        snapshot['ecg_rules']=config.get('ecg_rules',{})
        snapshot['patient_parts']=[];snapshot['patient_paths']=[];snapshot['power_traces']=[]
        for obj in objects:
            if obj.get('layout_id')!=layout: continue
            role=obj.get('role')
            if role in ['patient_component','battery_pack']:
                b=dict(bounds(obj,root),id=obj.get('component_id',obj.name),center=list((root.matrix_world.inverted()@obj.matrix_world).translation))
                if role=='patient_component':snapshot['patient_parts'].append(b)
                else:snapshot['battery_pack']=b
            if role=='conductor' and obj.get('patient_connected'):
                snapshot['patient_paths'].append(dict(bounds(obj,root),id=obj.name))
            if role=='conductor' and obj.name.startswith('PowerTrace_'):
                world_scale=obj.matrix_world.to_scale()
                snapshot['power_traces'].append(dict(id=obj.name,width=2*obj.data.bevel_depth*min(abs(world_scale.x),abs(world_scale.y))))
        region=bpy.data.objects.get('ContactRegion_'+layout)
        if region:snapshot['contact_region']=bounds(region,root)
    return snapshot


def signature():
    relevant=[('__config__',bpy.context.scene.get('config_json',''))]
    for obj in bpy.context.scene.objects:
        if obj.get('role') in ['component','conductor','pcb','layout_root','opening','interior','shell','patient_component','battery_pack','contact_region']:
            relevant.append((obj.name,list(map(list,obj.matrix_world)),list(obj.dimensions),
                [(key,str(obj.get(key))) for key in ['heat_source','noise_source','heat_radius','antenna_length_mm','conductive']],
                obj.data.bevel_depth if obj.type=='CURVE' else None))
    return hashlib.sha256(json.dumps(sorted(relevant),sort_keys=True).encode()).hexdigest()


def recalculate_constraints():
    if bpy.context.scene.get("use_upstream_engine"):
        return load_embedded("engine_bridge").recalculate(types.SimpleNamespace(**globals()))
    bpy.context.view_layer.update()
    engine,overlays=dependencies()
    snapshots={layout:extract_scene_snapshot(layout) for layout in ['Naive','MissionPCB']}
    results={layout:engine.evaluate_constraints(snapshot) for layout,snapshot in snapshots.items()}
    overlays.update_overlays(results,snapshots)
    scene=bpy.context.scene
    scene['results_json']=json.dumps(results,allow_nan=False)
    scene['snapshots_json']=json.dumps(snapshots,allow_nan=False)
    scene['validated_at']=datetime.now().astimezone().isoformat()
    scene['validated_signature']=signature(); scene['constraints_stale']=False
    apply_presentation_visibility()
    return results


def apply_presentation_visibility():
    """Keep package inspection clear, including after overlays are regenerated."""
    scene=bpy.context.scene
    close=bool(scene.camera and scene.camera.name=='Camera_CAD_Closeup')
    for obj in scene.objects:
        if obj.get('role')=='shell' or any(c.name=='03_Constraint_Overlays' for c in obj.users_collection):
            if close:
                if 'inspection_previous_render' not in obj:
                    obj['inspection_previous_render']=obj.hide_render
                    obj['inspection_previous_view']=obj.hide_get()
                obj.hide_set(True); obj.hide_render=True
            elif 'inspection_previous_render' in obj:
                obj.hide_render=obj['inspection_previous_render']; obj.hide_set(obj['inspection_previous_view'])
                del obj['inspection_previous_render']; del obj['inspection_previous_view']


def export_results(directory):
    if bpy.context.scene.get("use_upstream_engine"):
        return load_embedded("engine_bridge").export(types.SimpleNamespace(**globals()),directory)
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    if scene.get('constraints_stale') or signature()!=scene.get('validated_signature'):
        recalculate_constraints()
    results=json.loads(scene['results_json']); snapshots=json.loads(scene['snapshots_json'])
    config=json.loads(scene['config_json']);ecg=config.get('profile')=='ecg'
    def save(name,content):
        temporary=directory/(name+'.tmp'); temporary.write_text(content); temporary.replace(directory/name)
    save('validation_results.json',json.dumps(dict(generated_at=scene['validated_at'],geometry_revision=scene['validated_signature'],results=results,snapshots=snapshots),indent=2))
    report=['# MissionPCB ECG chest-patch validation' if ecg else '# MissionPCB geometric validation', '', 'Generated: '+scene['validated_at'],
        '',f'Blender: {bpy.app.version_string}. Engine: {scene.render.engine}.',
        f'Environment: {platform.platform()}; {platform.machine()}; bundled Python {platform.python_version()}.',
        'Units: one Blender unit = one millimeter. Enclosure: nonconductive polymer.'
        if json.loads(scene['config_json'])['enclosure_material']=='plastic' else 'Units: millimeters. Enclosure: conductive metal.',
        '', 'Authored demonstration placements; this is geometric validation, not an AI placement optimizer.',
        '', '## Components', '', '| Layout | Component / part | Dimensions mm | Center mm | Heat | Noise | Sensitivity |', '|---|---|---|---|---|---|---|']
    for layout,snapshot in snapshots.items():
        for p in snapshot['parts']:
            dimensions=[p['max'][i]-p['min'][i] for i in range(3)]
            fmt=lambda xs:', '.join(f'{x:.2f}' for x in xs)
            report.append(f"| {layout} | {p.get('part_name',p['id'])} | {fmt(dimensions)} | {fmt(p['center'])} | {p.get('heat_source')} | {p.get('noise_source')} | {p.get('sensitive')} |")
        if ecg:
            for p in snapshot['patient_parts']+[snapshot['battery_pack']]:
                report.append(f"| {layout} | {p['id']} | {fmt([p['max'][i]-p['min'][i] for i in range(3)])} | {fmt(p['center'])} | proxy only | n/a | patient-connected / support |")
    for layout,result in results.items():
        report+=['',f'## {layout}: {result["status"]}','','| Category | Status | Reason |','|---|---|---|']
        for r in result['categories']: report.append(f"| {r['category']} | {r['status']} | {r['reason']} |")
        report+=['','| Check | Measured | Rule | Status | Explanation |','|---|---|---|---|---|']
        for r in result['checks']:
            report.append(f"| {r['id']} | {r['value']:.4f} {r['unit']} | {r['operator']} {r['threshold']:g} | {r['status']} | {r['reason']} |")
        for error in result['errors']: report.append('ERROR: '+error)
    report+=['','## Simplifications','',
        'This demo uses geometric constraints and approximate heat/noise zones. It is not a substitute for thermal FEA, SPICE electrical simulation, electromagnetic simulation, or manufacturing DFM review.',
        '', 'Distances are XY center separations. Heat additionally checks sensor-footprint clearance from the drawn disk. Collision and antenna tests use conservative rectangles/bounding boxes. Package tilt fails mounting. Copper is illustrative and has no electrical netlist. Antenna keep-out excludes its own package/pads and permits nonconductive air, plastic and copper-free FR-4.',
        'Demo policies: AFE/MCU center offsets ≤12/'+('18' if ecg else '15')+' mm, PCB edge margin ≥1 mm, mounting gap ≤0.05 mm, rear access gap ≤12 mm, connector facing within 5 degrees. Connector access uses a straight clearance corridor, not cable bend physics.',
        '', '## Verification evidence','',scene.get('verification_notes','Automated and GUI verification not yet recorded.'),
        '', '## Artifacts','', '- '+Path(bpy.data.filepath).name,'- validation_results.json',
        '', '## Next steps','', '- KiCad import/export','- Part metadata ingestion','- Real thermal solver','- SPICE/electrical checks','- Enclosure CAD/STL import','- Drag-and-drop web UI']
    if ecg:
        report+=['','## ECG interpretation and limits','',
            'All PASS results mean only that these configured geometric demo policies pass. No skin temperature, electrical leakage, isolation, creepage path over real materials, biosignal noise floor, or copper ampacity has been simulated. Charging while worn and clinical ECG performance are not validated.',
            'Patient-contact heat measures XY distance from a heat source to the designated contact region, not the temperature of the entire skin-facing patch. Moving heat outward is a placement heuristic, not proof of patient safety.',
            'Patient-connected spacing is conservative XY envelope spacing. Trace width is measured from curve bevel geometry and compared with an example 0.6 mm rule; the illustrative 0.15 A input is not used as an ampacity calculation.',
            scene.get('cad_import_notes') or 'The six named IC/module roles retain illustrative functional placement envelopes, which include room for surrounding circuitry. They are not manufacturer footprint-accurate package models. BLE module, JST-SH connector and LiPo variants are unspecified.',
            'MCP73831 is a linear charger, so it is treated as a potential heat source rather than as a switching regulator. ADS1292R supports two channels; this demo depicts a single-lead mission and does not implement its electrical circuit.',
            'Standards-informed review categories; all numeric separation/heat-radius policies are authored examples, not values extracted from a medical standard. No IEC compliance or medical certification is claimed.',
            '', '## Offline part references','']
        for comp in config['components']:
            report.append('- '+comp['part_name']+(' — '+comp['datasheet_url'] if comp['datasheet_url'] else ' — exact variant unspecified'))
        report+=['','See cached part_metadata.md for manufacturer context. FDA testing context: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/electromagnetic-compatibility-emc-medical-devices . This is a testing-context reference, not a source for the demo distance thresholds.']
    save('validation_report.md','\n'.join(report)+'\n')
    return directory


class MISSIONPCB_OT_recalculate(bpy.types.Operator):
    bl_idname='missionpcb.recalculate'; bl_label='Recalculate Constraints'; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        try:
            recalculate_constraints(); self.report({'INFO'},'Constraints recalculated from current geometry')
        except Exception as error:
            context.scene['constraints_stale']=True; self.report({'ERROR'},str(error)); return {'CANCELLED'}
        return {'FINISHED'}


class MISSIONPCB_OT_restore(bpy.types.Operator):
    bl_idname='missionpcb.restore';bl_label='Restore Seeded Demo';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        for obj in context.scene.objects:
            if 'seed_location' in obj:
                obj.location=obj['seed_location'];obj.scale=obj['seed_scale'];obj.rotation_euler=(0,0,0)
        config=json.loads(context.scene['config_json'])
        for obj in context.scene.objects:
            if obj.name.startswith('PowerTrace_') and obj.type=='CURVE':
                obj.data.bevel_depth=config['layouts'][obj['layout_id']].get('power_width_mm',.6)/2
        recalculate_constraints();self.report({'INFO'},'Seeded component positions restored; geometry recalculated')
        return {'FINISHED'}


class MISSIONPCB_OT_example_failure(bpy.types.Operator):
    bl_idname='missionpcb.example_failure';bl_label='Demo: Move AFE Near Buck';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        objects={o.get('component_id'):o for o in context.scene.objects if o.get('role')=='component' and o.get('layout_id')=='MissionPCB'}
        if 'Sensor' not in objects or 'Regulator' not in objects:
            self.report({'ERROR'},'AFE or buck object is missing');return {'CANCELLED'}
        afe=objects['Sensor'];buck=objects['Regulator']
        afe.location.x=buck.location.x-4;afe.location.y=buck.location.y-2
        for obj in context.selected_objects:obj.select_set(False)
        afe.select_set(True);context.view_layer.objects.active=afe
        recalculate_constraints();self.report({'INFO'},'AFE moved; displayed failures are recalculated from actual geometry')
        return {'FINISHED'}


class MISSIONPCB_OT_view(bpy.types.Operator):
    bl_idname='missionpcb.view'; bl_label='Change Camera'
    camera: bpy.props.StringProperty()
    def execute(self,context):
        obj=bpy.data.objects.get(self.camera)
        if not obj: return {'CANCELLED'}
        context.scene.camera=obj; load_embedded('scene_builder').face_camera(obj)
        apply_presentation_visibility()
        for area in context.screen.areas:
            if area.type=='VIEW_3D': area.spaces.active.region_3d.view_perspective='CAMERA'
        return {'FINISHED'}


class MISSIONPCB_OT_toggle(bpy.types.Operator):
    bl_idname='missionpcb.toggle'; bl_label='Toggle Visibility'; target: bpy.props.StringProperty()
    def execute(self,context):
        objects=[o for o in context.scene.objects if (o.get('role')=='shell' if self.target=='shell' else o.get('zone'))]
        hide=not all(o.hide_get() for o in objects)
        for obj in objects: obj.hide_set(hide)
        return {'FINISHED'}


class MISSIONPCB_OT_export(bpy.types.Operator):
    bl_idname='missionpcb.export'; bl_label='Export Validation Report'
    def execute(self,context):
        try:
            directory=Path(bpy.data.filepath).parent if bpy.data.filepath else Path.home()/'MissionPCB'
            export_results(directory); self.report({'INFO'},str(directory/'validation_report.md'))
        except Exception as error:
            self.report({'ERROR'},str(error)); return {'CANCELLED'}
        return {'FINISHED'}


class MISSIONPCB_PT_panel(bpy.types.Panel):
    bl_label='MissionPCB'; bl_idname='MISSIONPCB_PT_panel'; bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='MissionPCB'
    def draw(self,context):
        ui=self.layout; scene=context.scene
        ui.label(text='Geometric constraints / approximate zones')
        if scene.get('profile')=='ecg':ui.label(text='ECG / example rules / engineer review')
        stale=scene.get('constraints_stale',True)
        ui.label(text='STALE: recalculate after edits' if stale else 'Validated snapshot',icon='ERROR' if stale else 'CHECKMARK')
        ui.operator('missionpcb.recalculate')
        if scene.get('use_upstream_engine'):
            ui.label(text='Shivansh engine / Aayush catalog')
            ui.operator('missionpcb.solve_engine')
        if scene.get('profile')=='ecg':
            ui.operator('missionpcb.example_failure');ui.operator('missionpcb.restore')
        cameras=[('Camera_TopDown','Top down'),('Camera_Isometric','Isometric'),('Camera_CloseConstraint','Close constraint')]
        if bpy.data.objects.get('Camera_Workbench'):
            cameras.insert(0,('Camera_Workbench','Workbench'))
        if bpy.data.objects.get('Camera_CAD_Closeup'):
            cameras.insert(0,('Camera_CAD_Closeup','Inspect imported parts'))
        for name,label in cameras:
            op=ui.operator('missionpcb.view',text=label); op.camera=name
        row=ui.row(); row.operator('missionpcb.toggle',text='Shell').target='shell'; row.operator('missionpcb.toggle',text='Zones').target='zones'
        obj=context.active_object
        if obj and obj.get('role') in ['component','patient_component','battery_pack']:
            ui.label(text=obj.name); ui.label(text=' x '.join(f'{v:.1f}' for v in obj.dimensions)+' mm')
            if obj.get('part_name'):ui.label(text=obj['part_name'])
            if obj.get('catalog_part_id'):ui.label(text='Catalog: '+obj['catalog_part_id'])
        results=json.loads(scene.get('results_json','{}'))
        for name,result in results.items():
            panel=ui.box(); panel.label(text=name)
            for r in result['categories']:
                panel.label(text=r['category']+': '+('STALE' if stale else r['status']))
        ui.operator('missionpcb.export')
        ui.label(text='Snapshot only until Recalculate is clicked.')


class MISSIONPCB_OT_solve_engine(bpy.types.Operator):
    bl_idname='missionpcb.solve_engine'; bl_label='Optimize Core Placement'; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        try:
            load_embedded('engine_bridge').optimize(types.SimpleNamespace(**globals()))
            self.report({'INFO'},'Core placement optimized; coverage gaps remain')
        except Exception as error:
            self.report({'ERROR'},str(error)); return {'CANCELLED'}
        return {'FINISHED'}


CLASSES=[MISSIONPCB_OT_solve_engine,MISSIONPCB_OT_recalculate,MISSIONPCB_OT_restore,MISSIONPCB_OT_example_failure,MISSIONPCB_OT_view,MISSIONPCB_OT_toggle,MISSIONPCB_OT_export,MISSIONPCB_PT_panel]


def freshness_timer():
    if bpy.app.is_job_running('RENDER'): return .75
    scene=bpy.context.scene
    if 'validated_signature' not in scene: return None
    if not scene.get('constraints_stale') and signature()!=scene.get('validated_signature'):
        scene['constraints_stale']=True
        for obj in scene.objects:
            if obj.name.startswith('Snapshot notice ') and obj.type=='FONT': obj.data.body='STALE  /  Click Recalculate Constraints'
            if obj.get('dynamic_overlay') and (obj.name.startswith('Relation ') or obj.name.startswith('Distance ') or obj.name.startswith('Row status ') or obj.name.startswith('Dashboard total ')):
                obj.hide_set(True)
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D': area.tag_redraw()
    return .5


def unregister():
    old=bpy.app.driver_namespace.pop('missionpcb_timer',None)
    if old and bpy.app.timers.is_registered(old): bpy.app.timers.unregister(old)
    for cls in reversed(CLASSES):
        existing=getattr(bpy.types,cls.__name__,None)
        if existing:
            try: bpy.utils.unregister_class(existing)
            except RuntimeError: pass


def register():
    unregister()
    for cls in CLASSES: bpy.utils.register_class(cls)
    if not bpy.app.background:
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D':
                    area.spaces.active.region_3d.view_perspective='CAMERA'
                    area.spaces.active.overlay.show_extras=False
                    area.spaces.active.overlay.show_relationship_lines=False
                    area.spaces.active.overlay.show_axis_x=False;area.spaces.active.overlay.show_axis_y=False
                    area.spaces.active.overlay.show_cursor=False
                    area.spaces.active.show_region_ui=True
                    for region in area.regions:
                        if region.type=='UI':
                            try:region.active_panel_category='MissionPCB'
                            except (AttributeError,RuntimeError):pass
        bpy.app.timers.register(freshness_timer,first_interval=.5)
        bpy.app.driver_namespace['missionpcb_timer']=freshness_timer
    print('MissionPCB sidebar ready. Use N > MissionPCB > Recalculate Constraints.')


if __name__=='__main__': register()
