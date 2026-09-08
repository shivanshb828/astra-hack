"""Update the existing scene in place; execute in its live Blender console.

The cached models are presentation geometry, not a fabrication-ready BOM.
Use --verify-only in background to exercise imports without saving the scene.
"""
from pathlib import Path
import hashlib
import json
import math
import sys
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
WORKING = HERE / 'component_pass/missionpcb_three_cad_components.blend'
OUT = WORKING.parent


def material(name, color, metallic=0.0, roughness=0.4):
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1); mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Metallic'].default_value=metallic
    shader.inputs['Roughness'].default_value=roughness
    return mat


def import_mesh(path):
    previous=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    added=list(set(bpy.data.objects)-previous)
    meshes=[o for o in added if o.type=='MESH']
    assert meshes, path
    for obj in meshes:
        world=obj.matrix_world.copy()
        obj.parent=None
        obj.matrix_world=Matrix.Identity(4)
        obj.data.transform(world)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes: obj.select_set(True)
    bpy.context.view_layer.objects.active=meshes[0]
    if len(meshes)>1: bpy.ops.object.join()
    obj=bpy.context.view_layer.objects.active
    for other in added:
        if other.name in bpy.data.objects and other!=obj:
            bpy.data.objects.remove(other,do_unlink=True)
    return obj


def main():
    assert Path(bpy.data.filepath).resolve()==WORKING.resolve(), 'Open the canonical working scene first'
    scene=bpy.context.scene
    assert scene.get('profile')=='ecg'
    assert abs(scene.unit_settings.scale_length-.001)<1e-8
    parts=HERE/'parts'
    # The user explicitly accepted visually useful approximations for this demo.
    selections=[
        ('MCU','MSP430FR2433','MSP430',parts/'verified_core/Texas_RGE0024H_VQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm.normalized.glb',
         [4,4,.8],'KiCad RGE0024H package matches the selected MCU drawing; nominal package geometry.',0),
        ('Sensor','ADS1292R / approximate QFN32','ADS1292R*',parts/'converted_models/QFN-32-1EP_4x4mm_P0.4mm_EP2.65x2.65mm.normalized.glb',
         [4,4,.92],'Approximate QFN32. Exposed pad is 2.65 mm rather than required 2.8 mm; visualization only.',0),
        ('RF','Raytac MDBT42Q / manufacturer family outline','MDBT42Q',parts/'converted_models/mdbt42q.normalized.glb',
         [16,10,2.2],'Official simplified Raytac family CAD, presentation materials added. Exact radio/flash suffix unresolved.',90),
        ('Regulator','TPS62740 / approximate WSON10 visual','BUCK*',parts/'converted_models/Texas_DSQ0010A_WSON-10-1EP_2x2mm_P0.4mm_EP0.9x1.5mm.normalized.glb',
         [2,1.975,.8],'WSON10 visual substitute: 2x2 mm / 10 pins rather than TPS62740 DSS 2x3 mm / 12 pins. Not pin-compatible; no fabrication claim.',0),
        ('Driver','MCP73831 / drawing-adapted SOT23-5','MCP73831*',parts/'verified_core/audit/MCP73831_OT_drawing_adapted.normalized.glb',
         [2.8,2.9,1.4],'KiCad SOT23-5 with molded height corrected to Microchip drawing; not manufacturer CAD.',0),
        ('Battery','JST BM02B-SRSS-TB / nominal family CAD','JST SH',parts/'converted_models/JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical.normalized.glb',
         [4,3.6,4.32],'Nominal KiCad JST SH top-entry family CAD; model standoff differs from drawing by 0.02 mm.',0),
    ]
    config=json.loads(scene['config_json'])
    records=[]
    for cid,label,short,path,expected,note,angle in selections:
        asset=import_mesh(path)
        if angle: asset.data.transform(Matrix.Rotation(math.radians(angle),4,'Z'))
        coords=[v.co for v in asset.data.vertices]
        low=Vector([min(v[i] for v in coords) for i in range(3)])
        high=Vector([max(v[i] for v in coords) for i in range(3)])
        dims=high-low
        assert all(abs(a-b)<.005 for a,b in zip(dims,expected)), (cid,list(dims),expected)
        asset.data.transform(Matrix.Translation(-(low+high)/2))
        if cid=='RF':
            # Raytac's supplied model has no materials; finish its actual surfaces.
            mats=[material('Raytac PCB',(.035,.12,.075),0,.55),
                  material('Raytac shield',(.58,.63,.67),.8,.3),
                  material('Raytac ceramic antenna',(.78,.75,.65),0,.5)]
            asset.data.materials.clear()
            for mat in mats: asset.data.materials.append(mat)
            for poly in asset.data.polygons:
                center=sum((asset.data.vertices[i].co for i in poly.vertices),Vector())/len(poly.vertices)
                poly.material_index=0 if center.z < -.7 else (2 if center.x < -5.5 else 1)
        for layout in ('Naive','MissionPCB'):
            obj=next(o for o in scene.objects if o.get('role')=='component' and o.get('component_id')==cid and o.get('layout_id')==layout)
            obj.data=asset.data.copy(); obj.modifiers.clear()
            obj.scale=(1,1,1); obj.rotation_euler=(0,0,0)
            obj.location.z=3.6+dims.z/2
            obj['seed_location']=list(obj.location); obj['seed_scale']=[1,1,1]
            obj['part_name']=label; obj['geometry_basis']=note
            obj['cad_asset']=str(path.relative_to(HERE)); obj['cad_source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            for child in list(obj.children):
                if child.type=='FONT':
                    child.data.body=short; child.data.size=.9
                    child.location=(0,-dims.y/2-1.25,dims.z/2+.08)
                elif child.get('role')=='conductor': bpy.data.objects.remove(child,do_unlink=True)
            bpy.context.view_layer.update()
            assert all(abs(a-b)<.005 for a,b in zip(obj.dimensions,expected)), obj.name
            records.append(dict(object=obj.name,component_id=cid,layout=layout,dimensions_mm=list(obj.dimensions),geometry_basis=note,asset=obj['cad_asset'],sha256=obj['cad_source_sha256']))
        bpy.data.objects.remove(asset,do_unlink=True)
        component=next(c for c in config['components'] if c['id']==cid)
        component.update(part_name=label,dimensions=list(dims),geometry_basis=note)
    scene['config_json']=json.dumps(config)
    scene['cad_import_notes']='Six core roles use imported package geometry. AFE and buck are explicitly approximate substitutes; charger is drawing-adapted. Raytac uses manufacturer family outline. Geometric demo only; no circuit, thermal, EMI or clinical validation. JST top-entry mating is not checked by the legacy rear-access rule.'
    scene['verification_notes']='Six imported CAD roles in both layouts: native dimensions, PCB mounting, stable recalculation, AFE failure and seeded restore verified. See active_import_verification.json and reopen_verification.json. '+scene['cad_import_notes']
    for name,body in [('Physics scope','IMPORTED PACKAGE CAD / * APPROXIMATE MODELS / GEOMETRIC DEMO ONLY'),('BOM strip','ECG PATCH / MSP430 + ADS1292R* + MDBT42Q + BUCK* + MCP73831* + JST')]:
        if bpy.data.objects.get(name): bpy.data.objects[name].data.body=body
    for name in ['constraints','scene_builder','overlays','runtime']:
        text=bpy.data.texts.get(name+'.py') or bpy.data.texts.new(name+'.py')
        text.clear(); text.write((HERE/(name+'.py')).read_text())
    for key in list(sys.modules):
        if key.startswith('missionpcb_'): del sys.modules[key]
    runtime=bpy.data.texts['runtime.py'].as_module()
    runtime.register()
    camera=bpy.data.objects['Camera_CAD_Closeup']
    target=Vector((70,18,3.6))
    camera.location=target+Vector((20,-38,65))
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'; camera.data.ortho_scale=88
    scene.camera=camera
    runtime.load_embedded('scene_builder').face_camera(camera)
    results=runtime.recalculate_constraints()
    count=len(bpy.data.objects)
    assert runtime.recalculate_constraints()==results and len(bpy.data.objects)==count
    for record in records:
        obj=bpy.data.objects[record['object']]
        b=runtime.bounds(obj,bpy.data.objects['Root_'+record['layout']])
        assert abs(b['min'][2]-3.6)<.005, (obj.name,b)
    bpy.ops.missionpcb.example_failure()
    assert json.loads(scene['results_json'])['MissionPCB']['categories'][2]['status']=='FAIL'
    bpy.ops.missionpcb.restore()
    assert json.loads(scene['results_json'])==results
    runtime.apply_presentation_visibility()
    bpy.ops.object.select_all(action='DESELECT')
    def set_view():
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='CONSOLE' and not bpy.app.background: area.type='VIEW_3D'
                if area.type!='VIEW_3D': continue
                space=area.spaces.active
                if not hasattr(space,'region_3d'): continue
                space.region_3d.view_perspective='CAMERA'; space.region_3d.view_camera_zoom=6
                space.overlay.show_overlays=False
                space.shading.type='MATERIAL'; space.shading.use_scene_world=False; space.shading.use_scene_lights=False
                space.show_region_ui=True
    set_view()
    scene.render.engine='BLENDER_EEVEE'; scene.eevee.taa_render_samples=16
    scene.render.threads_mode='FIXED'; scene.render.threads=4
    scene.render.resolution_x=1500; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    evidence=dict(status='PASS',scene=str(WORKING),imports=records,tests=['native-size mesh bounds','PCB mounting','stable repeated recalculation','AFE failure interaction','seed restore'],scope=scene['cad_import_notes'])
    if '--verify-only' not in sys.argv:
        bpy.ops.wm.save_as_mainfile(filepath=str(WORKING))
        (OUT/'active_import_verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
        runtime.export_results(OUT)
        if not bpy.app.background:
            def finish_live_view():
                set_view()
                bpy.ops.wm.save_as_mainfile(filepath=str(WORKING))
                return None
            bpy.app.timers.register(finish_live_view,first_interval=.5)
    print('WORKING_COMPONENT_IMPORT_PASS',json.dumps(evidence),flush=True)


if __name__=='__main__': main()
