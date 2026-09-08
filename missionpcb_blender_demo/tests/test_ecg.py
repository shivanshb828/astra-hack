"""ECG profile acceptance checks; the original generic tests remain unchanged."""
import copy
import math
import unittest
from test_constraints import api, fixture


def body(name,center,size):
    return dict(id=name,center=list(center),min=[center[i]-size[i]/2 for i in range(3)],
                max=[center[i]+size[i]/2 for i in range(3)])


def ecg_fixture(corrected=True):
    data=fixture(corrected); data['profile']='ecg'
    data['parts'][4]['noise_source']=False  # MCP73831 is a linear charger.
    if corrected:
        mcu=data['parts'][0]; mcu.update(center=[12,-11,4.6],min=[6,-17,3.6],max=[18,-5,5.6])
    points=[(-9,6,4.35),(-9,0,4.25),(-9,12,4.25)] if corrected else [(-13,1,4.35),(-16,-3,4.25),(-13,16,4.25)]
    data['patient_parts']=[body(name,pos,size) for name,pos,size in zip(['Protection','ElectrodeA','ElectrodeB'],points,[(4,4,1.5),(3.6,3.6,1.3),(3.6,3.6,1.3)])]
    data['patient_paths']=[]
    data['contact_region']=body('ContactRegion',[-4,6.5,-2.3],[16,19,.1])
    data['battery_pack']=body('LiPo',[22 if corrected else -12,-5,1],[24,16,1.6])
    data['power_traces']=[dict(id='PowerTrace',width=.6 if corrected else .25)]
    return data


class ECGTests(unittest.TestCase):
    def test_expected_ecg_categories(self):
        good=api.evaluate_constraints(ecg_fixture())
        bad=api.evaluate_constraints(ecg_fixture(False))
        self.assertEqual(len(good['categories']),8,'ECG needs eight mission checks')
        self.assertEqual([r['status'] for r in good['categories']],['PASS']*8)
        self.assertEqual([r['status'] for r in bad['categories']],['PASS']+['FAIL']*7)

    def test_ecg_move_and_restore(self):
        data=ecg_fixture(); original=copy.deepcopy(data['parts'][1])
        data['parts'][1]=dict(original,center=[28,9,4.35],min=[25,6,3.6],max=[31,12,5.1])
        result=api.evaluate_constraints(data)
        self.assertEqual(result['categories'][2]['status'],'FAIL')
        data['parts'][1]=original
        self.assertEqual(api.evaluate_constraints(data)['status'],'PASS')

    def test_power_width_boundary(self):
        for width,expected in [(.599,'FAIL'),(.6,'PASS'),(.601,'PASS')]:
            data=ecg_fixture(); data['power_traces'][0]['width']=width
            self.assertEqual(api.evaluate_constraints(data)['categories'][6]['status'],expected)

    def test_patient_spacing_uses_actual_geometry(self):
        data=ecg_fixture(); data['patient_parts'][0]=body('Protection',[28,9,4.35],[4,4,1.5])
        self.assertEqual(api.evaluate_constraints(data)['categories'][3]['status'],'FAIL')

    def test_missing_contact_geometry_is_error(self):
        data=ecg_fixture(); del data['contact_region']
        self.assertEqual(api.evaluate_constraints(data)['status'],'ERROR')


if __name__=='__main__': unittest.main()
