import bpy,json
from pathlib import Path
from collections import defaultdict
ROOT=Path('/Users/dhruvavutukury/Documents/ChatGPT/astra/missionpcb_blender_demo/parts')
rows=[]
for name in ['SOT-23-5','JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical','QFN-32-1EP_4x4mm_P0.4mm_EP2.65x2.65mm']:
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=1
 bpy.ops.import_scene.gltf(filepath=str(ROOT/'converted_models'/(name+'.normalized.glb')));bpy.context.view_layer.update()
 for o in bpy.context.scene.objects:
  if o.type!='MESH':continue
  groups=defaultdict(set)
  for p in o.data.polygons:groups[p.material_index].update(p.vertices)
  for i,verts in groups.items():
   mat=o.data.materials[i];coords=[(o.matrix_world@o.data.vertices[j].co)*1000 for j in verts];lo=[min(v[k] for v in coords) for k in range(3)];hi=[max(v[k] for v in coords) for k in range(3)]
   rows.append(dict(model=name,material=mat.name,color=list(mat.diffuse_color),min=lo,max=hi,dims=[hi[k]-lo[k] for k in range(3)]))
(ROOT/'verified_core/audit/material_bounds.json').write_text(json.dumps(rows,indent=2))
for row in rows:print(row)
