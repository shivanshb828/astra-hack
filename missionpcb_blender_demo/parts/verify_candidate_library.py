"""Check saved library plus fresh normalized GLB reimports in millimetre scene."""
from pathlib import Path
import hashlib
import json
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'library'
manifest = json.loads((OUT / 'library_manifest.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(OUT / 'MissionPCB_Package_Candidates.blend'))
assert len(manifest['models']) == 23
assert len(manifest['families']) == 29
assert abs(bpy.context.scene.unit_settings.scale_length - 0.001) < 1e-9


def bounds(objects):
    vertices = [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]
    return (Vector([min(v[i] for v in vertices) for i in range(3)]),
            Vector([max(v[i] for v in vertices) for i in range(3)]))


for model in manifest['models']:
    obj = bpy.data.objects[model['asset_object']]
    assert obj.asset_data is not None
    assert obj['source_sha256'] == model['source_sha256']
    low, high = bounds([obj])
    assert abs(low.z) < 1e-4
    assert abs(low.x + high.x) < 1e-4 and abs(low.y + high.y) < 1e-4
    assert max(abs((high - low)[i] - model['dimensions_mm'][i]) for i in range(3)) < 1e-4
    file = ROOT / model['normalized_glb']
    assert hashlib.sha256(file.read_bytes()).hexdigest() == model['normalized_glb_sha256']
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(file))
    imported = list(set(bpy.data.objects) - before)
    low, high = bounds([o for o in imported if o.type == 'MESH'])
    assert abs(low.z) < 1e-4, model['package_model']
    assert abs(low.x + high.x) < 1e-4 and abs(low.y + high.y) < 1e-4
    assert max(abs((high - low)[i] - model['dimensions_mm'][i]) for i in range(3)) < 1e-3, (model['package_model'], list(high-low))
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
missing = [f for f in manifest['families'] if not f['candidate_assets']]
assert len(missing) == 6
for family in manifest['families']:
    assert family['exact_orderable_mpn'] is None and family['selected_package'] is None
    assert bpy.data.objects[family['family_record_object']].type == 'EMPTY'
    if not family['candidate_assets']:
        assert 'REVIEW_CANDIDATE__' + family['part_family'] not in bpy.data.objects
report = {'status': 'PASS', 'checks': ['23 saved mesh assets with provenance', '29 family metadata records',
          '6 unresolved families without substitute meshes', 'millimetre bounds and origin normalization',
          '23 normalized GLB hashes and fresh import round trips'],
          'dimensions_note': 'Measured CAD mesh envelopes, including leads. Not validated manufacturer dimensions.',
          'unresolved': [f['part_family'] for f in missing],
          'library_sha256': hashlib.sha256((OUT / 'MissionPCB_Package_Candidates.blend').read_bytes()).hexdigest()}
(OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print('CANDIDATE_LIBRARY_VERIFIED_23_MODELS_29_FAMILIES')
