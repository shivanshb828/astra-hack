import json,tempfile,unittest,zipfile
from pathlib import Path
import packages as p
class RoundTrip(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  root=Path(self.tmp.name);self.old=(p.PROJECT,p.EXCHANGE);self.addCleanup(self.restore)
  p.PROJECT=root/'project';p.PROJECT.mkdir();p.EXCHANGE=root/'exchange'
  self.board='(kicad_pcb (version 20260101) (gr_text "original" (at 1 2) (layer "F.SilkS")))'
  (p.PROJECT/'MissionPCB.kicad_pcb').write_text(self.board)
  (p.PROJECT/'MissionPCB.kicad_pro').write_text('{}')
  self.archive=p.prepare('r1')
 def restore(self):p.PROJECT,p.EXCHANGE=self.old
 def returned(self,change=lambda b:b,extra=None):
  with zipfile.ZipFile(self.archive) as z:d={n:z.read(n) for n in z.namelist()}
  d['project/MissionPCB.kicad_pcb']=change(self.board).encode()
  d['findings.json']=json.dumps({'revision':'r1','findings':[]}).encode()
  if extra:d.update(extra)
  out=Path(self.tmp.name)/'return.zip'
  with zipfile.ZipFile(out,'w') as z:
   for n,b in d.items():z.writestr(n,b)
  return out
 def test_annotation_round_trip(self):
  out=p.receive(self.returned(lambda b:b[:-1]+' (gr_text "MissionPCB review: clearance" (at 3 4) (layer "Cmts.User")))'))
  self.assertTrue(out.exists());self.assertEqual((p.PROJECT/'MissionPCB.kicad_pcb').read_text(),self.board)
 def test_reject_design_edit(self):
  with self.assertRaises(ValueError):p.receive(self.returned(lambda b:b.replace('1 2','8 9')))
 def test_reject_stale(self):
  (p.PROJECT/'MissionPCB.kicad_pcb').write_text(self.board+'\n')
  with self.assertRaises(ValueError):p.receive(self.returned())
 def test_reject_traversal(self):
  with self.assertRaises(ValueError):p.receive(self.returned(extra={'../escape':b'x'}))
if __name__=='__main__':unittest.main()
