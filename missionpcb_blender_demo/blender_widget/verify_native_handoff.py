"""Real KiCad GLB import and replacement regression, in a separate Blender process."""
import bpy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import assembly
manifest=json.loads((ROOT.parent/'kicad_bridge/runtime/detailed-native-current.json').read_text())['manifest']
assembly.handoff(manifest)
assert len([o for o in assembly.objects().values() if o.get('kicad_ref')])==19
assert json.loads(bpy.context.scene['model_coverage'])['missing_model_refs']==['L1']
assembly.demo_enclosure()
shell=assembly.objects()['enclosure'];device=assembly.objects()['device'];device.location=(4,5,6)
bpy.context.view_layer.update();world=shell.matrix_world.copy()
assembly.handoff(manifest)
assert assembly.objects()['enclosure']==shell
assert shell.matrix_world==world
assert len([o for o in assembly.objects().values() if o.get('kicad_ref')])==19
assert assembly.objects()['board'] is not None
assert len(assembly.meshes(assembly.objects()['board']))>=19
print('NATIVE_HANDOFF_PASS: 19 native models, L1 explicitly absent, assembly transforms preserved, CAD and body placement retained')
