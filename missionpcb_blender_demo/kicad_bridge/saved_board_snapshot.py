"""Read saved KiCad geometry using KiCad's bundled Python. Never saves a board."""
import json,sys
import pcbnew
board=pcbnew.LoadBoard(sys.argv[1])
parts=[]
for fp in board.GetFootprints():
 parts.append({'ref':fp.GetReference(),'value':fp.GetValue(),'x_mm':pcbnew.ToMM(fp.GetPosition().x),'y_mm':pcbnew.ToMM(fp.GetPosition().y),'rotation_deg':fp.GetOrientationDegrees()})
print(json.dumps({'parts':sorted(parts,key=lambda p:p['ref'])}))
