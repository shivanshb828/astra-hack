"""Numerical acceptance tests independent of Blender."""
import importlib.util
import math
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'constraints.py'
api = None
if MODULE.exists():
    spec = importlib.util.spec_from_file_location('missionpcb_constraints', MODULE)
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)


def fixture(corrected=True):
    xy = ([(-2,-9),(-2,4),(-27,10),(29,9),(27,-10),(30,0)] if corrected else
          [(0,-10),(5,0),(-20,9),(-5,10),(18,-4),(-28,-11)])
    sizes = [(12,12,2),(6,6,1.5),(16,10,2),(8,8,3),(14,10,3),(10,6,5)]
    ids = ['MCU','Sensor','RF','Regulator','Driver','Battery']
    parts = []
    for name,(x,y),(w,d,h) in zip(ids,xy,sizes):
        parts.append(dict(id=name, center=[x,y,3.6+h/2],
            min=[x-w/2,y-d/2,3.6], max=[x+w/2,y+d/2,3.6+h],
            heat_source=name in ['Regulator','Driver'],
            noise_source=name in ['Regulator','Driver'],
            heat_radius=18 if name=='Regulator' else 22 if name=='Driver' else 0,
            facing=[1,0,0], upright=True))
    return dict(layout='MissionPCB' if corrected else 'Naive', parts=parts,
        pcb=dict(min=[-36,-19,2],max=[36,19,3.6]),
        enclosure=dict(min=[-45,-25,0],max=[45,25,18]),
        opening=dict(min=[45,-5,3],max=[47,5,11]),
        antenna=dict(rect=[-30,-8,-5,5], conductors=[
            dict(id='trace',rect=[10,11,0,1] if corrected else [-11.3,-10.7,-20,7])]),errors=[])


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(api, 'Constraint engine has not been implemented')

    def test_distance_thresholds(self):
        for limit in [15,18,20]:
            self.assertFalse(api.at_least(limit-.001, limit))
            self.assertTrue(api.at_least(limit, limit))
            self.assertTrue(api.at_least(limit+.001, limit))

    def test_rectangle_contact_and_width(self):
        zone=[-30,-8,-5,5]
        self.assertTrue(api.rect_overlap(zone,[-8,-7,0,1]))
        self.assertFalse(api.rect_overlap(zone,[-7.999,-7,0,1]))
        self.assertTrue(api.rect_overlap(zone,[-8.1,-7.5,0,1]))

    def test_disk_corner_clearance(self):
        self.assertAlmostEqual(api.point_rect_distance([0,0],[3,6,4,8]),5)
        self.assertEqual(api.point_rect_distance([4,5],[3,6,4,8]),0)
        for radius in [18,22]:
            self.assertFalse(api.at_least(api.point_rect_distance([0,0],[radius-.1,radius+1,0,1]),radius))
            self.assertTrue(api.at_least(api.point_rect_distance([0,0],[radius,radius+1,0,1]),radius))

    def test_both_layouts(self):
        good=api.evaluate_constraints(fixture())
        bad=api.evaluate_constraints(fixture(False))
        self.assertEqual([x['status'] for x in good['categories']],['PASS']*7)
        self.assertEqual([x['status'] for x in bad['categories']],['PASS','PASS']+['FAIL']*5)
        row=next(x for x in good['checks'] if x['id']=='sensor_heat_Driver')
        self.assertAlmostEqual(row['value'],math.sqrt(1037),places=5)

    def test_height_boundary(self):
        for height,expected in [(14,'PASS'),(14.001,'FAIL')]:
            data=fixture(); data['parts'][0]['max'][2]=3.6+height
            result=api.evaluate_constraints(data)
            self.assertEqual(result['categories'][1]['status'],expected)

    def test_missing_component_is_error(self):
        data=fixture(); data['parts'].pop()
        self.assertEqual(api.evaluate_constraints(data)['status'],'ERROR')

    def test_collision_and_mounting(self):
        data=fixture(); sensor=data['parts'][1]; driver=data['parts'][4]
        sensor['center']=driver['center'][:]
        sensor['min']=[24,-13,3.6]; sensor['max']=[30,-7,5.1]
        self.assertEqual(api.evaluate_constraints(data)['categories'][0]['status'],'FAIL')
        data=fixture(); data['parts'][0]['min'][2]+=1
        self.assertEqual(api.evaluate_constraints(data)['categories'][0]['status'],'FAIL')

    def test_connector_facing_and_corridor(self):
        data=fixture(); data['parts'][-1]['facing']=[0,1,0]
        self.assertEqual(api.evaluate_constraints(data)['categories'][-1]['status'],'FAIL')
        data=fixture(); driver=data['parts'][4]
        driver['min']=[36,-2,4]; driver['max']=[40,2,8]
        self.assertEqual(api.evaluate_constraints(data)['categories'][-1]['status'],'FAIL')

    def test_invalid_geometry_is_error(self):
        data=fixture(); data['parts'][0]['min'][0]=float('nan')
        self.assertEqual(api.evaluate_constraints(data)['status'],'ERROR')


if __name__ == '__main__':
    unittest.main()
