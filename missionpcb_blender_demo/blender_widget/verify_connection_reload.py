"""Run in a separate Blender --background session; never touches live IPC or saves CAD."""
import bpy,runpy,json,tempfile,time
from pathlib import Path
namespace=runpy.run_path(str(Path(__file__).with_name('addon.py')))
g=namespace['start'].__globals__
with tempfile.TemporaryDirectory() as directory:
 g['IPC']=Path(directory)
 def snapshot():return {'heartbeat':time.time(),'file':bpy.data.filepath,**g['connection']()}
 g['snapshot']=snapshot
 g['start']()
 first=g['SESSION'];callback=g['tick'];source=bpy.data.filepath
 bpy.ops.wm.open_mainfile(filepath=source)
 assert bpy.app.timers.is_registered(callback),'Adapter timer was lost on file reload'
 callback()
 assert g['SESSION']!=first,'Reload retained the old command session'
 command=dict(id='a'*32,action='assembly_check',session=first,created=time.time())
 (g['IPC']/'command.json').write_text(json.dumps(command))
 callback();reply=json.loads((g['IPC']/('a'*32+'.json')).read_text())
 assert reply['ok'] is False and 'scene changed' in reply['message']
 bpy.app.timers.unregister(callback)
 print('NATIVE_RELOAD_PASS persistent_timer=True old_session_rejected=True')
