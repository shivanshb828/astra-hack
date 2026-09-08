"""Low-cost, unlit review images. Does not alter the verified library file."""
from pathlib import Path
import bpy
import json

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'library'
FILE = OUT / 'MissionPCB_Package_Candidates.blend'
bpy.ops.wm.open_mainfile(filepath=str(FILE))
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_cavity = False
scene.display.shading.show_shadows = False
scene.display.shading.background_type = 'WORLD'
scene.world.color = (0.96, 0.96, 0.96)
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
for obj in bpy.data.objects:
    if obj.type == 'FONT':
        obj.data.size *= 1.6 if obj.name.startswith('Family_') else 1.45
        for mat in obj.data.materials:
            mat.diffuse_color = (0.015, 0.025, 0.04, 1)
scene.render.resolution_x = 1800
scene.render.resolution_y = 1406
scene.render.resolution_percentage = 100
scene.render.filepath = str(OUT / 'library_overview.png')
bpy.ops.render.render(write_still=True)

# A shared-scale detail sheet: no per-cell geometry scaling.
for obj in bpy.data.collections['FAMILY_REVIEW_29_RECORDS'].objects:
    obj.hide_render = True
detail = bpy.data.collections.new('PREVIEW_DETAILS_ONLY')
scene.collection.children.link(detail)
manifest = json.loads((OUT / 'library_manifest.json').read_text())
chosen = [
    ('CC2652R', 'Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm', 'VQFN48 package candidate'),
    ('ISO7741', 'SOIC-16W_7.5x10.3mm_P1.27mm', 'Wide SOIC16 package candidate'),
    ('BM02B-SRSS', 'JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical', 'JST family CAD candidate'),
    ('MCP73831 / OPA333', 'SOT-23-5', 'Shared SOT23-5 package candidate'),
    ('DRV2605L / TMUX1104', 'TSSOP-10_3x3mm_P0.5mm', 'Shared VSSOP10 package candidate'),
    ('ABS07', 'Crystal_SMD_3215-2Pin_3.2x1.5mm', 'Generic crystal; height differs'),
]


def text(name, body, pos, size):
    curve = bpy.data.curves.new(name, 'FONT')
    curve.body = body
    curve.size = size
    obj = bpy.data.objects.new(name, curve)
    detail.objects.link(obj)
    obj.location = pos
    mat = bpy.data.materials.get('Preview_Text') or bpy.data.materials.new('Preview_Text')
    mat.diffuse_color = (0.01, 0.02, 0.03, 1)
    curve.materials.append(mat)


for i, (family, package, note) in enumerate(chosen):
    x, y = (i % 3) * 19, -(i // 3) * 22
    model = next(m for m in manifest['models'] if m['package_model'] == package)
    source = bpy.data.objects[model['asset_object']]
    obj = bpy.data.objects.new('Detail_' + family, source.data)
    detail.objects.link(obj)
    obj.location = (x, y, 0)
    text('Title_' + family, family, (x - 7.5, y + 7.5, 0), 0.85)
    text('Note_' + family, note + '\n' + ' x '.join(f'{d:.2f}' for d in model['dimensions_mm']) + ' mm mesh envelope', (x - 7.5, y - 8, 0), 0.5)
text('Preview_Heading', 'Finished CAD package details', (-7.5, 17, 0), 1.4)
text('Preview_Scope', 'All six cells share one physical scale; exact orderable variants remain unresolved.\nNo geometry was enlarged per cell. Source models and leads are preserved.', (-7.5, 13, 0), 0.6)
scene.camera.location = (19, -6, 180)
scene.camera.data.ortho_scale = 64
scene.render.resolution_x = 1600
scene.render.resolution_y = 1400
scene.render.filepath = str(OUT / 'package_details.png')
bpy.ops.render.render(write_still=True)
print('LIBRARY_PREVIEWS_RENDERED')
