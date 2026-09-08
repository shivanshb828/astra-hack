"""Create an 18-part placement candidate; never overwrite the active board.
Run with KiCad's bundled Python (pcbnew). No netlist or routing is synthesized.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import tempfile
import uuid
import pcbnew as p

ROOT = Path(__file__).resolve().parent
LIB = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
MODELS = LIB.parent / '3dmodels'
TARGET = ROOT / 'cache/ExpandedECG.kicad_pcb'
TI = 'https://www.ti.com/lit/ds/symlink/tps62740.pdf'
SPECS = [
 ('C1', 'MCU decoupling', 'U1', (-4,0), 'TBD', 'cap'),
 ('C2', 'AFE decoupling', 'U2', (-4,0), 'TBD', 'cap'),
 ('C3', 'RF decoupling', 'U3', (10,0), 'TBD', 'cap'),
 ('C4', 'Buck input capacitor', 'U4', (4,0), '10uF', 'cap'),
 ('C5', 'Buck output capacitor', 'U4', (0,4), '10uF', 'cap'),
 ('C6', 'Charger capacitor', 'U5', (0,4), 'TBD', 'cap'),
 ('R1', 'AFE input series resistor', 'U2', (-4,4), 'TBD', 'res'),
 ('R2', 'AFE input series resistor', 'U2', (-4,-4), 'TBD', 'res'),
 ('R3', 'Charge programming resistor', 'U5', (4,0), 'TBD', 'res'),
 ('L1', 'Buck inductor', 'U4', (-4,0), '2.2uH', 'ind'),
 ('J2', 'Electrode lead connector', 'U2', (-10,0), 'JST SH 3 pin', 'j3'),
 ('J3', 'Debug connector', 'U1', (5.5,0), 'JST SH 4 pin', 'j4'),
]
PACKAGES = {
 'cap': ('Capacitor_SMD', 'C_0603_1608Metric', (1.6,.8,.8)),
 'res': ('Resistor_SMD', 'R_0603_1608Metric', (1.6,.8,.5)),
 'ind': ('Inductor_SMD', 'L_Coilcraft_LPS3314', (3.3,3.3,1.4)),
 'j3': ('Connector_JST', 'JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal', (5,4.25,3)),
 'j4': ('Connector_JST', 'JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal', (6,4.25,3)),
}

def footprint_blocks(text):
    """Return complete top-level footprint S-expressions, respecting quoted text."""
    result = []
    for match in re.finditer(r'^\t\(footprint ', text, re.M):
        start = match.start(); depth = 0; quoted = False; escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if quoted:
                if escape: escape = False
                elif ch == '\\': escape = True
                elif ch == '"': quoted = False
            elif ch == '"': quoted = True
            elif ch == '(': depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    result.append(text[start:i+1]); break
    return result

def build():
    source = ROOT / 'MissionPCB.kicad_pcb'
    original = source.read_text()
    board = p.LoadBoard(str(source))
    core = {fp.GetReference(): fp for fp in board.GetFootprints()}
    if set(core) != {'U1','U2','U3','U4','U5','J1'}:
        raise RuntimeError('Expected the original six-part board; refusing to duplicate/replace parts.')
    additions = p.BOARD()
    manifest = []
    (ROOT / 'models/support').mkdir(parents=True, exist_ok=True)
    for ref, role, anchor, offset, value, kind in SPECS:
        library, name, dimensions = PACKAGES[kind]
        fp = p.FootprintLoad(str(LIB / (library + '.pretty')), name)
        assert fp, name
        fp.SetReference(ref); fp.SetValue(value)
        origin = core[anchor].GetPosition()
        fp.SetPosition(p.VECTOR2I(origin.x+p.FromMM(offset[0]), origin.y+p.FromMM(offset[1])))
        fp.Reference().SetTextSize(p.VECTOR2I(p.FromMM(.65),p.FromMM(.65)))
        fp.Reference().SetTextThickness(p.FromMM(.1))
        fp.Value().SetVisible(False)
        model_src = MODELS / (library+'.3dshapes') / (name+'.step')
        model_dst = ROOT / 'models/support' / model_src.name
        if model_src.exists(): shutil.copy2(model_src, model_dst)
        available = model_dst.exists()
        fp.Models().clear()
        if available:
            model = p.FP_3DMODEL()
            model.m_Filename = '${KIPRJMOD}/models/support/' + model_dst.name
            fp.Models().push_back(model)
        additions.Add(fp)
        limitation = 'Placement-only package; value, rating and circuit connectivity require schematic design.'
        if kind == 'cap': limitation += ' Generic 0603 model; capacitance/DC-bias/rating suitability is unverified.'
        if kind == 'ind': limitation += ' Official footprint available but matching STEP unavailable; no substitute 3D body.'
        if kind in ('j3','j4'): limitation += ' Connector body/envelope dimensions are conservative; not a complete mating cable or electrode assembly.'
        manifest.append(dict(ref=ref,engine_ref=ref,part_id='support_'+ref.lower(),role=role,value=value,
            dimensions_mm=dict(zip(('length','width','height'),dimensions)),
            footprint=library+':'+name,model_path=str(model_dst.relative_to(ROOT)) if available else None,
            model_source=str(model_src) if available else None,model_available=available,
            model_sha256=hashlib.sha256(model_dst.read_bytes()).hexdigest() if available else None,
            limitation=limitation,anchor_ref=anchor,offset_mm=list(offset),
            value_source=TI+' (typical application, page 1)' if ref in ('C4','C5','L1') else None))
    with tempfile.TemporaryDirectory(prefix='missionpcb-expand-') as tmp:
        temp = Path(tmp)/'additions.kicad_pcb'; p.SaveBoard(str(temp),additions)
        blocks = footprint_blocks(temp.read_text())
    assert len(blocks) == 12
    deterministic = []
    for block in sorted(blocks, key=lambda b: re.search(r'\(property "Reference" "([^"]+)"', b).group(1)):
        ref = re.search(r'\(property "Reference" "([^"]+)"',block).group(1)
        counter = [0]
        def stable_uuid(match):
            counter[0] += 1
            return '(uuid "'+str(uuid.uuid5(uuid.NAMESPACE_URL,'missionpcb-expanded/'+ref+'/'+str(counter[0])))+'")'
        deterministic.append(re.sub(r'\(uuid "[^"]+"\)',stable_uuid,block))
    final = original.rstrip()
    assert final.endswith(')')
    TARGET.write_text(final[:-1]+'\n'+'\n'.join(deterministic)+'\n)\n')
    checked = p.LoadBoard(str(TARGET))
    assert len(list(checked.GetFootprints())) == 18
    assert len(list(checked.GetTracks())) == len(list(board.GetTracks()))
    assert all(block in TARGET.read_text() for block in footprint_blocks(original)), 'Core footprint changed'
    assert source.read_text() == original, 'Canonical board was modified'
    # Cached candidate is intended for installation at ROOT; KIPRJMOD resolves there.
    paths = [m.m_Filename for fp in checked.GetFootprints() for m in fp.Models()]
    assert len(paths) == 17, paths
    assert all(Path(path.replace('${KIPRJMOD}',str(ROOT))).exists() for path in paths)
    output = dict(schema_version=1,description='18-part cached ECG placement candidate; original six cores preserved. No nets or routes added.',
        project_root=str(ROOT),model_attribution={'creator':'KiCad Library Team and contributors','source':'https://gitlab.com/kicad/libraries/kicad-packages3D','license':'CC-BY-SA-4.0 with KiCad libraries exception','license_url':'https://www.kicad.org/libraries/license/','scope':'Copied support STEP models; unmodified files from installed KiCad 10 library.'},parts=manifest,limitations=['L1 has no available matching STEP model.','Existing U2/U4 package approximations remain unchanged.','Not an electrically complete or validated medical device.'])
    (ROOT/'expanded-support-parts.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(dict(candidate=str(TARGET),footprints=18,resolved_models=len(paths),missing_models=['L1'],core_footprints_byte_preserved=True,canonical_unchanged=True)))

if __name__ == '__main__': build()
