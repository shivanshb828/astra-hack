import bpy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import assembly
assert (ROOT/'red_flags.py').exists(),'3D red flags are not implemented'
import red_flags
scene=assembly.scene_setup()
board=assembly.box('PCB',(0,0,0),(72,38,1));board['assembly_id']='board'
part=assembly.box('U1',(0,0,2),(4,4,2),board);part['assembly_id']='part-U1';part['kicad_ref']='U1'
other=assembly.box('U2',(10,0,2),(4,4,2),board);other['assembly_id']='part-U2';other['kicad_ref']='U2'
bpy.context.view_layer.update();sig=assembly.signature();dims=tuple(part.dimensions)
findings=[{'id':'sep.test','status':'FAIL','object':'part-U1','kicad_refs':['U1','U2'],'measured_mm':6,'required_mm':15}]
red_flags.draw(findings,assembly)
flags=[o for o in scene.objects if o.get('is_flag')]
assert any(o.get('flag_kind')=='beacon' for o in flags)
assert any(o.get('flag_kind')=='halo' for o in flags)
assert any(o.get('flag_kind')=='outline' for o in flags)
assert assembly.signature()==sig
assert tuple(part.dimensions)==dims
red_flags.focus('part-U1')
assert any(o.get('flag_kind')=='measurement' and not o.hide_get() for o in scene.objects)
red_flags.draw(findings,assembly)
assert len([o for o in scene.objects if o.get('flag_kind')=='beacon'])==1
red_flags.draw([],assembly)
assert not any(o.get('is_flag') for o in scene.objects)
print('RED_FLAGS_PASS: 3D beacons, halos, outlines, selected measurements; no geometry edits; cleanup verified')
