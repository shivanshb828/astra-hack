"""Run using Blender --background canonical.blend --python this_file. Never saves."""
import runpy,tempfile,json,time
from pathlib import Path
import bpy
m=runpy.run_path(str(Path(__file__).with_name('addon.py')))
# Functions share their own globals; isolate every test write from the live adapter.
g=m['tick'].__globals__
with tempfile.TemporaryDirectory() as directory:
 g['IPC']=Path(directory)
 m['execute']({'action':'check'})
 baseline=m['snapshot']();assert len(baseline['parts'])==6
 obj=m['parts']()['Sensor'];old=obj.location.copy()
 try:
  obj.location.x=m['parts']()['Regulator'].location.x;obj.location.y=m['parts']()['Regulator'].location.y;bpy.context.view_layer.update()
  assert m['snapshot']()['stale']
  m['execute']({'action':'check'})
  assert m['snapshot']()['result']['summary']['FAIL']>0
  assert len(bpy.data.collections['MissionPCB Widget Flags'].objects)>0
 finally:
  obj.location=old;bpy.context.view_layer.update();m['execute']({'action':'check'})
 assert m['snapshot']()['result']['summary']==baseline['result']['summary']
 (g['IPC']/'command.json').write_text('{broken')
 assert m['tick']()==.75
 assert (g['IPC']/'last_error.json').exists()
 print('BLENDER_WIDGET_REGRESSION_PASS',baseline['result']['summary'])
