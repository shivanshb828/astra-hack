"""Run in Blender background after convert_candidates.py. No ECG scene changes."""
from pathlib import Path
from mathutils import Matrix, Vector
import bpy
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'library'
OUT.mkdir(exist_ok=True)
inventory = json.loads((ROOT / 'model_candidates.json').read_text())
converted = json.loads((ROOT / 'converted_models/conversion_manifest.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.001
scene['units_note'] = '1 Blender unit = 1 mm. Normalized GLBs use standard metres. Blender glTF importer automatically applies scene scale .001; do not scale again. If importing at scene scale 1, multiply coordinates by 1000 afterwards.'
scene['scope'] = '29 family records; package candidates only. No exact orderable MPN selected. Six missing models remain metadata only.'
assets = bpy.data.collections.new('PACKAGE_AND_FAMILY_CAD_ASSETS')
scene.collection.children.link(assets)
gallery = bpy.data.collections.new('FAMILY_REVIEW_29_RECORDS')
scene.collection.children.link(gallery)
index = {}
records = []


def label(name, body, location, size=0.55, color=(0.08, 0.13, 0.18, 1)):
    data = bpy.data.curves.new(name, 'FONT')
    data.body = body
    data.size = size
    data.space_line = 1.2
    obj = bpy.data.objects.new(name, data)
    gallery.objects.link(obj)
    obj.location = location
    mat = bpy.data.materials.get('Text_' + str(color)) or bpy.data.materials.new('Text_' + str(color))
    mat.diffuse_color = color
    data.materials.append(mat)
    return obj


for entry in converted['models']:
    src = ROOT / entry['raw_glb']
    assert hashlib.sha256(src.read_bytes()).hexdigest() == entry['raw_glb_sha256']
    previous = set(bpy.data.objects)
    # glTF importer respects scene units. Import at metre scale before explicit conversion.
    scene.unit_settings.scale_length = 1.0
    bpy.ops.import_scene.gltf(filepath=str(src))
    scene.unit_settings.scale_length = 0.001
    imported = list(set(bpy.data.objects) - previous)
    imported_names = [obj.name for obj in imported]
    meshes = [obj for obj in imported if obj.type == 'MESH']
    assert meshes, entry['package_model']
    for obj in meshes:
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        for vertex in obj.data.vertices:
            vertex.co = (world @ vertex.co) * 1000.0
            angle = entry.get('source_metadata', {}).get('normalization_rotation_x_degrees', 0)
            if angle:
                vertex.co = Matrix.Rotation(math.radians(angle), 4, 'X') @ vertex.co
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    for name in imported_names:
        other = bpy.data.objects.get(name)
        if other is not None and other != obj:
            bpy.data.objects.remove(other, do_unlink=True)
    coords = [v.co.copy() for v in obj.data.vertices]
    low = Vector([min(v[i] for v in coords) for i in range(3)])
    high = Vector([max(v[i] for v in coords) for i in range(3)])
    shift = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
    for v in obj.data.vertices:
        v.co -= shift
    obj.data.update()
    dims = high - low
    assert min(dims) > 0 and max(dims) < 50, (entry['package_model'], dims)
    manufacturer = entry.get('source_metadata', {}).get('source_kind') == 'manufacturer_family_model'
    obj.name = ('MANUFACTURER_FAMILY__' if manufacturer else 'PACKAGE_CANDIDATE__') + entry['package_model']
    obj.data.name = obj.name + '__mesh_mm'
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    assets.objects.link(obj)
    obj['model_status'] = 'MANUFACTURER_FAMILY_SUFFIX_UNRESOLVED' if manufacturer else 'PACKAGE_CANDIDATE_NOT_CONFIRMED_EXACT_MPN'
    obj['package_model'] = entry['package_model']
    obj['source_step'] = entry['source_step']
    obj['source_sha256'] = entry['source_sha256']
    obj['dimensions_mm'] = list(dims)
    obj.asset_mark()
    obj.asset_data.description = 'KiCad package CAD candidate. Native size in mm; bottom Z=0, centred XY. Full manufacturer suffix and package drawing must be checked.'
    obj.asset_data.author = 'Raytac; manufacturer download provenance retained' if manufacturer else 'KiCad library contributors; original STEP attribution retained'
    obj.asset_data.tags.new('Candidate')
    obj.asset_data.tags.new('Package CAD')
    obj.data.calc_loop_triangles()
    # Export a standards-compliant normalized GLB in metres, without board offsets.
    export_obj = obj.copy()
    export_obj.data = obj.data.copy()
    gallery.objects.link(export_obj)
    for v in export_obj.data.vertices:
        v.co *= 0.001
    bpy.ops.object.select_all(action='DESELECT')
    export_obj.select_set(True)
    bpy.context.view_layer.objects.active = export_obj
    normalized = ROOT / 'converted_models' / (entry['package_model'] + '.normalized.glb')
    scene.unit_settings.scale_length = 1.0
    bpy.ops.export_scene.gltf(filepath=str(normalized), export_format='GLB', use_selection=True,
                             export_cameras=False, export_lights=False, export_extras=True)
    scene.unit_settings.scale_length = 0.001
    copied_mesh = export_obj.data
    bpy.data.objects.remove(export_obj, do_unlink=True)
    bpy.data.meshes.remove(copied_mesh)
    record = dict(entry)
    record.update({'asset_object': obj.name, 'normalized_glb': str(normalized.relative_to(ROOT)),
                   'normalized_glb_sha256': hashlib.sha256(normalized.read_bytes()).hexdigest(),
                   'dimensions_mm': [round(x, 6) for x in dims], 'origin': 'centred XY; bottom Z=0', 'source_kind': 'manufacturer_family_model' if manufacturer else 'kicad_package_candidate',
                   'glb_units': 'metres', 'glb_to_library_scale': 1000,
                   'vertices': len(obj.data.vertices), 'triangles': len(obj.data.loop_triangles),
                   'materials': len(obj.data.materials)})
    records.append(record)
    index[entry['source_step']] = obj

family_records = []
for i, part in enumerate(inventory['parts']):
    x, y = (i % 6) * 24.0, -(i // 6) * 22.0
    family = bpy.data.objects.new('FAMILY_RECORD__' + part['part_family'], None)
    gallery.objects.link(family)
    family.empty_display_size = 0.05
    family.hide_render = True
    family['part_family'] = part['part_family']
    family['status'] = part['status']
    family['exact_orderable_mpn'] = 'UNRESOLVED'
    family['mapping_note'] = part['mapping_note']
    model_objects = []
    for candidate in part['candidates']:
        for model in candidate['models']:
            if model['cached_path'] in index:
                name = index[model['cached_path']].name
                if name not in model_objects:
                    model_objects.append(name)
    family['candidate_assets'] = json.dumps(model_objects)
    label('Family_' + part['part_family'], part['part_family'], (x - 8, y + 9.5, 0.02), 0.8)
    if model_objects:
        original = bpy.data.objects[model_objects[0]]
        item = bpy.data.objects.new('REVIEW_CANDIDATE__' + part['part_family'], original.data)
        gallery.objects.link(item)
        item.location = (x, y, 0)
        item['source_asset'] = original.name
        item['display_note'] = 'First listed candidate for visual review only; not selected for board.'
        item['source_sha256'] = original['source_sha256']
        label('Status_' + part['part_family'], f'CANDIDATE | {len(model_objects)} package option(s)\nExact MPN/package unresolved', (x - 8, y - 9, 0.02), 0.47)
    else:
        label('Missing_' + part['part_family'], 'MODEL NOT CACHED\nMetadata only', (x - 8, y, 0.02), 0.65, (0.55, 0.2, 0.08, 1))
    family_records.append({'part_family': part['part_family'], 'status': part['status'],
                           'family_record_object': family.name, 'candidate_assets': model_objects,
                           'exact_orderable_mpn': None, 'selected_package': None,
                           'note': part['mapping_note']})

assets.hide_viewport = True
assets.hide_render = True
label('Library_title', 'MissionPCB | Package candidate library', (-8, 24, 0), 1.6)
label('Library_subtitle', '29 family records / 23 families with CAD candidates / 6 awaiting models\nTrue-size CAD at 1 BU = 1 mm. First listed options shown for review; no board selections.', (-8, 19, 0), 0.62)
manifest = {'status': 'CANDIDATE_LIBRARY_BUILT', 'blender_version': bpy.app.version_string,
            'counts': inventory['counts'], 'units': scene['units_note'],
            'models': records, 'families': family_records,
            'license': inventory['license'], 'note': 'No exact manufacturer MPN is confirmed by this library. No placeholder geometry is used for unresolved parts.'}
(OUT / 'library_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
embedded = bpy.data.texts.new('LIBRARY_MANIFEST.json')
embedded.write(json.dumps(manifest, indent=2))
readme = bpy.data.texts.new('START_HERE.txt')
readme.write('Candidate CAD library only.\n23 CAD assets are in PACKAGE_AND_FAMILY_CAD_ASSETS (hidden in gallery).\nAppend an asset object by name: PACKAGE_CANDIDATE__...\nEach has geometry in millimetres, bottom Z=0, centred XY.\nGallery repeats linked meshes for family review; first listed options are not selections.\nSix unresolved records have text/metadata only.\nSource/package uncertainty and hashes are in LIBRARY_MANIFEST.json.\n' + scene['units_note'] + '\n')
camera_data = bpy.data.cameras.new('Library_Overview')
camera = bpy.data.objects.new('Library_Overview', camera_data)
scene.collection.objects.link(camera)
camera.location = (60, -37, 180)
camera.rotation_euler = (0, 0, 0)
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 170
scene.camera = camera
scene.render.resolution_x = 1600
scene.render.resolution_y = 1250
scene.render.resolution_percentage = 100
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.background_type = 'WORLD'
scene.world = bpy.data.worlds.new('Library_World')
scene.world.color = (0.8, 0.83, 0.85)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
            area.spaces.active.overlay.show_extras = False
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'MissionPCB_Package_Candidates.blend'))
print('CANDIDATE_LIBRARY_BUILT', len(records), 'models;', len(family_records), 'family records', flush=True)
