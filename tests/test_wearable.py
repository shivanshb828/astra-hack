import unittest
from constraint_engine.wearable import evaluate_wearable,compare_checks
class WearableTests(unittest.TestCase):
 def test_unknown_is_not_pass(self):
  self.assertTrue(all(c['status']=='SKIP' for c in evaluate_wearable({})))
 def test_runtime_and_mass(self):
  rows={c['id']:c for c in evaluate_wearable(dict(battery_capacity_mah=100,average_current_ma=1,usable_capacity_fraction=.8,required_runtime_hours=100,mass_items_g={'pcb':2,'battery':3},mass_budget_complete=True,max_mass_g=6))}
  self.assertEqual(rows['wearable.runtime']['measured'],80);self.assertEqual(rows['wearable.runtime']['status'],'FAIL');self.assertEqual(rows['wearable.mass']['status'],'PASS')
 def test_partial_mass_and_noise_bandwidth(self):
  rows={c['id']:c for c in evaluate_wearable(dict(mass_items_g={'battery':None},mass_budget_complete=True,max_mass_g=20,minimum_signal_uv_rms=100,input_noise_uv_rms=1,required_snr_db=20))}
  self.assertEqual(rows['wearable.mass']['status'],'SKIP');self.assertEqual(rows['wearable.signal']['status'],'SKIP')
 def test_invalid_capacity_fraction(self):
  with self.assertRaises(ValueError):evaluate_wearable(dict(battery_capacity_mah=100,average_current_ma=1,usable_capacity_fraction=2,required_runtime_hours=1))
 def test_existing_failure_regression(self):
  old=[dict(id='x',status='FAIL',margin_mm=-1),dict(id='y',status='FAIL',margin_mm=-3)]
  new=[dict(id='x',status='FAIL',margin_mm=-2),dict(id='y',status='PASS',margin_mm=1)]
  d=compare_checks(old,new);self.assertEqual(d['verdict'],'mixed');self.assertEqual(d['worsened'],['x']);self.assertEqual(d['fixed'],['y'])

 def test_sparse_collision_resolution(self):
  d=compare_checks([dict(id='fit.overlap::a|b',status='FAIL',margin_mm=-1)],[])
  self.assertEqual(d['fixed'],['fit.overlap::a|b'])
  d=compare_checks([],[dict(id='fit.courtyard::a|c',status='FAIL',margin_mm=-1)])
  self.assertEqual(d['introduced'],['fit.courtyard::a|c'])
