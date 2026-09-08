"""Audit native KiCad GLB component coverage; never create substitute models."""
import json,struct
OPTIONS=['--include-tracks','--include-pads','--include-zones','--include-silkscreen','--include-soldermask']
VERSION='native-full-detail-v1'
def inspect_export(path,refs):
 data=path.read_bytes()
 if len(data)<20 or struct.unpack_from('<III',data)!=(0x46546c67,2,len(data)):
  raise ValueError('Invalid KiCad GLB export')
 size,kind=struct.unpack_from('<II',data,12)
 if kind!=0x4e4f534a:raise ValueError('GLB has no JSON scene')
 scene=json.loads(data[20:20+size]);nodes=scene.get('nodes',[])
 def has_mesh(index,seen=None):
  seen=set() if seen is None else seen
  if index in seen:return False
  seen.add(index);node=nodes[index]
  return 'mesh' in node or any(has_mesh(i,seen) for i in node.get('children',[]))
 modeled={node.get('name') for i,node in enumerate(nodes) if has_mesh(i)} & set(refs)
 return {'modeled_refs':sorted(modeled),'missing_model_refs':sorted(set(refs)-modeled),
         'mesh_count':len(scene.get('meshes',[])),'export_options':OPTIONS,
         'source':'Native KiCad GLB; no generated component substitutes'}
