import json,struct,tempfile,unittest
from pathlib import Path
import detailed_export
class ExportTests(unittest.TestCase):
 def test_reports_absent_models_without_inventing_geometry(self):
  payload=json.dumps({'nodes':[{'name':'U1','children':[1]},{'mesh':0},{'name':'board','mesh':1}], 'meshes':[{'primitives':[{}]},{'primitives':[{}]}]}).encode()
  payload+=b' '*((-len(payload))%4)
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'board.glb'
   path.write_bytes(struct.pack('<III',0x46546c67,2,20+len(payload))+struct.pack('<II',len(payload),0x4e4f534a)+payload)
   report=detailed_export.inspect_export(path,['U1','L1'])
  self.assertEqual(report['modeled_refs'],['U1'])
  self.assertEqual(report['missing_model_refs'],['L1'])
  self.assertEqual(report['mesh_count'],2)
 def test_full_surface_options(self):
  for option in ('--include-tracks','--include-pads','--include-zones','--include-silkscreen','--include-soldermask'):
   self.assertIn(option,detailed_export.OPTIONS)
if __name__=='__main__':unittest.main()
