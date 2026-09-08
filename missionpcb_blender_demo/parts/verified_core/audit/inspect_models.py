import bpy,json
from pathlib import Path
ROOT=Path('/Users/dhruvavutukury/Documents/ChatGPT/astra/missionpcb_blender_demo/parts')
def b(coords):
 low=[min(v[i] for v in coords) for i in range(3)];high=[max(v[i] for v in coords) for i in range(3)]
 return dict(min=low,max=high,dims=[high[i]-low[i] for i in range(3)])
rows=[]
for name in ['SOT-23-5','JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical','QFN-32-1EP_4x4mm_P0.4mm_EP2.65x2.65mm']:
 for suffix in ['.glb','.normalized.glb']:
  bpy.ops.wm.read_factory_settings(use_empty=True)
  bpy.context.scene.unit_settings.scale_length=1
  bpy.ops.import_scene.gltf(filepath=str(ROOT/'converted_models'/(name+suffix)))
  bpy.context.view_layer.update()
  objects=[];allcoords=[]
  for o in bpy.context.scene.objects:
   if o.type!='MESH':continue
   coords=[(o.matrix_world@v.co)*1000 for v in o.data.vertices];allcoords+=coords
   objects.append(dict(name=o.name,matrix=[list(r) for r in o.matrix_world],local=b([v.co*1000 for v in o.data.vertices]),world=b(coords),materials=[m.name if m else '' for m in o.data.materials]))
  rows.append(dict(model=name+suffix,objects=objects,bounds=b(allcoords)))
(ROOT/'verified_core/audit/model_bounds.json').write_text(json.dumps(rows,indent=2))
for row in rows:print(row['model'],row['bounds'])
