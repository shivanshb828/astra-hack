"""Native-six layout conversion, matching the existing widget adapter."""
import time
from native_review import MAP
def payload_for(before):
 placements=[dict(ref=MAP[p['ref']][0],part_id=MAP[p['ref']][1],pos_mm=[round(p['x_mm']-100,6),round(138-p['y_mm'],6)],rotation_deg=(-(p['rotation_deg']-(90 if p['ref']=='U3' else 0)))%360) for p in before['parts']]
 payload=dict(design_id='missionpcb-native-six',revision=time.time_ns(),part_library='native-six',brief='ECG chest patch. Review current six-component placement against authored demo spacing policies.',kicad_refs={v[0]:k for k,v in MAP.items()},layout=dict(name='Live MissionPCB KiCad placement',distance_metric='center',enclosure=dict(interior_mm=dict(length=90,width=50,height=10),wall_keepout_mm=0),board=dict(id='MissionPCB',size_mm=dict(length=72,width=38,thickness=1.6),origin_mm=[9,6,2],edge_margin_mm=1,max_component_height_mm=6.4,min_component_gap_mm=.5),placements=placements,mission_rules=[dict(id='afe_'+ref,type='min_separation',between=['Sensor',ref],distance_mm=dist,metric='center',rationale='Authored demo policy, not solved physics.') for ref,dist in [('MCU',18),('RF',20),('Regulator',20)]]))
 return payload
