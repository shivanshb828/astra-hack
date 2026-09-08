"""Replace three demo bodies with cached, native-size CAD in a separate scene."""
from pathlib import Path
import hashlib
import json
import sys
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime
import scene_builder

OUT = HERE / 'component_pass'
SELECTION = {
    'Sensor': ('ADS1292R — QFN32 candidate', 'QFN-32-1EP_4x4mm_P0.4mm_EP2.65x2.65mm'),
    'Driver': ('MCP73831 — SOT23-5 candidate', 'SOT-23-5'),
    'Battery': ('JST BM02B-SRSS — family CAD candidate', 'JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical'),
}


def main():
    OUT.mkdir(exist_ok=True)
    scene = bpy.context.scene
    assert scene.get('profile') == 'ecg', 'Load the saved ECG workbench first'
    source_path = Path(bpy.data.filepath)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    manifest = json.loads((HERE / 'parts/library/library_manifest.json').read_text())
    models = {m['package_model']: m for m in manifest['models']}
    config = json.loads(scene['config_json'])
    records = []
    for component_id, (label, package) in SELECTION.items():
        model = models[package]
        with bpy.data.libraries.load(str(HERE / 'parts/library/MissionPCB_Package_Candidates.blend'), link=False) as (src, dst):
            dst.objects = [model['asset_object']]
        asset = dst.objects[0]
        height = model['dimensions_mm'][2]
        for layout in ['Naive', 'MissionPCB']:
            obj = next(o for o in scene.objects if o.get('role') == 'component' and o.get('component_id') == component_id and o.get('layout_id') == layout)
            old_dims = list(obj.dimensions)
            obj.data = asset.data.copy()
            for vertex in obj.data.vertices:
                vertex.co.z -= height / 2
            obj.modifiers.clear()
            obj.scale = (1, 1, 1)
            obj.location.z = 3.6 + height / 2
            obj['seed_location'] = list(obj.location)
            obj['seed_scale'] = list(obj.scale)
            obj['part_name'] = label
            obj['cad_source_sha256'] = model['source_sha256']
            obj['cad_package'] = package
            obj['geometry_basis'] = 'Native-size cached KiCad CAD; provisional package/family match, exact MPN not confirmed'
            # Text stays beside the package; never enlarge the imported body for legibility.
            for child in list(obj.children):
                if child.type == 'FONT':
                    child.data.body = 'AFE CAD*' if component_id == 'Sensor' else 'CHG CAD*' if component_id == 'Driver' else 'JST CAD*'
                    child.data.size = 1.1
                    child.location = (0, -model['dimensions_mm'][1] / 2 - 1.5, height / 2 + .15)
                elif child.get('role') == 'conductor':
                    # Prior illustrative package pads must not survive at their old size.
                    bpy.data.objects.remove(child, do_unlink=True)
            bpy.context.view_layer.update()
            assert all(abs(a-b) < .002 for a,b in zip(obj.dimensions, model['dimensions_mm']))
            snap = runtime.bounds(obj, bpy.data.objects['Root_' + layout])
            assert abs(snap['min'][2] - 3.6) < .002, 'CAD does not sit on PCB'
            records.append(dict(component_id=component_id, layout=layout, object=obj.name,
                                old_dimensions_mm=old_dims, dimensions_mm=list(obj.dimensions),
                                package=package, source_sha256=model['source_sha256']))
        bpy.data.objects.remove(asset, do_unlink=True)
        comp = next(c for c in config['components'] if c['id'] == component_id)
        comp.update(part_name=label, dimensions=model['dimensions_mm'], geometry_basis='Native-size CAD candidate; exact MPN/package matching pending')
    scene['config_json'] = json.dumps(config)
    scene['cad_import_notes'] = ('Three roles use native-size imported CAD: ADS1292R QFN32 candidate, MCP73831 SOT23-5 candidate, JST BM02B-SRSS family candidate. '
        'The other roles remain illustrative envelopes. No schematic or footprint routing was generated. '
        'JST CAD is top-entry; the legacy rear-access corridor does not validate its mating direction or assembly access. '
        'Thermal/noise rules remain authored geometric proxies. Exact orderable suffixes and package drawing checks are pending.')
    bpy.data.objects['Physics scope'].data.body = '3 CAD CANDIDATES* / OTHER BODIES ARE ENVELOPES / GEOMETRIC DEMO RULES / EXACT PACKAGES PENDING'
    bpy.data.objects['BOM strip'].data.body = 'SMALL IMPORT PASS / AFE + CHARGER + JST / NATIVE CAD DIMENSIONS'
    for name in ['constraints', 'scene_builder', 'overlays', 'runtime']:
        block = bpy.data.texts.get(name + '.py') or bpy.data.texts.new(name + '.py')
        block.clear(); block.write((HERE / (name + '.py')).read_text())
    results = runtime.recalculate_constraints()
    count = len(bpy.data.objects)
    assert runtime.recalculate_constraints() == results
    assert len(bpy.data.objects) == count
    runtime.register()
    bpy.ops.missionpcb.example_failure()
    assert json.loads(scene['results_json'])['MissionPCB']['categories'][2]['status'] == 'FAIL'
    bpy.ops.missionpcb.restore()
    assert json.loads(scene['results_json']) == results, 'Restore differs from imported seed'
    scene['verification_notes'] = 'Three native-size CAD roles imported into both layouts. Mesh bounds, PCB mounting, repeat recalculation, AFE failure and exact seeded restore verified. ' + scene['cad_import_notes']
    runtime.export_results(OUT)
    report = OUT / 'validation_report.md'
    report.write_text(report.read_text().replace('missionpcb_lean_constraint_demo.blend', 'missionpcb_three_cad_components.blend').replace('- renders/top_down.png\n- renders/isometric.png', '- cad_closeup.png'))
    result_file = OUT / 'missionpcb_three_cad_components.blend'
    # Clean saved camera view; imported bodies remain individually editable.
    scene.camera = bpy.data.objects['Camera_Workbench']
    scene_builder.face_camera(scene.camera)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.overlay.show_overlays = False
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.type = 'MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(result_file))
    evidence = dict(source_scene=str(source_path), source_sha256=source_hash, artifact=str(result_file),
                    imports=records, source_unchanged=hashlib.sha256(source_path.read_bytes()).hexdigest()==source_hash,
                    tests=['native mesh bounds', 'PCB mounting', 'stable recalculation', 'AFE failure', 'exact seeded restore'],
                    categories={k:[dict(category=r['category'],status=r['status']) for r in v['categories']] for k,v in results.items()})
    (OUT / 'verification.json').write_text(json.dumps(evidence, indent=2) + '\n')
    # One close view makes the imported packages visible without changing physical scale.
    camera_data = bpy.data.cameras.new('CAD closeup camera')
    camera = bpy.data.objects.new('Camera_CAD_Closeup', camera_data)
    scene.collection.objects.link(camera)
    target = Vector((84, 15, 3.6))
    camera.location = target + Vector((24, -43, 70))
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.type = 'ORTHO'; camera_data.ortho_scale = 51
    scene.camera = camera
    scene_builder.face_camera(camera)
    # Hide annotation panels and transparent shell only for the package-detail image.
    hidden = {}
    for obj in scene.objects:
        if any(c.name == '03_Constraint_Overlays' for c in obj.users_collection) or obj.get('role') == 'shell':
            hidden[obj.name] = obj.hide_render
            obj.hide_render = True
    scene.render.engine = 'BLENDER_EEVEE'; scene.eevee.taa_render_samples = 32
    scene.render.resolution_x = 1400; scene.render.resolution_y = 1000; scene.render.resolution_percentage = 100
    scene.render.threads_mode = 'FIXED'; scene.render.threads = 4
    scene.render.filepath = str(OUT / 'cad_closeup.png')
    bpy.ops.render.render(write_still=True)
    for name, value in hidden.items():
        bpy.data.objects[name].hide_render = value
    scene.camera = bpy.data.objects['Camera_Workbench']; scene_builder.face_camera(scene.camera)
    bpy.ops.wm.save_as_mainfile(filepath=str(result_file))
    print('THREE_CAD_IMPORT_PASS', json.dumps(evidence), flush=True)


if __name__ == '__main__':
    main()
