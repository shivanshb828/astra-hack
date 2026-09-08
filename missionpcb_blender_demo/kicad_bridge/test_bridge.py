import copy
import unittest
import bridge
class ValidationTests(unittest.TestCase):
 def setUp(self):
  self.before={'revision':'r1','parts':[{'ref':'U1'}]}
  self.proposal={'board':str(bridge.TARGET),'base_revision':'r1','moves':[{'ref':'U1','x_mm':136,'y_mm':129,'rotation_deg':0}]}
 def test_valid(self): self.assertEqual(len(bridge.validate(self.proposal,self.before)),1)
 def test_rejections(self):
  variants=[]
  for key,value in [('board','Hypnos.kicad_pcb'),('base_revision','old')]:
   p=copy.deepcopy(self.proposal);p[key]=value;variants.append(p)
  for key,value in [('ref','missing'),('x_mm',float('nan')),('y_mm',999),('rotation_deg',45),('x_mm',True)]:
   p=copy.deepcopy(self.proposal);p['moves'][0][key]=value;variants.append(p)
  p=copy.deepcopy(self.proposal);p['moves']*=2;variants.append(p)
  for p in variants:
   with self.subTest(p=p), self.assertRaises(ValueError): bridge.validate(p,self.before)
if __name__=='__main__':unittest.main()
