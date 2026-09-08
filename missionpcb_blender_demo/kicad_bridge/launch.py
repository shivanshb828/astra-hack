"""Launch the local widget and services without committing machine credentials."""
from pathlib import Path
import json,plistlib,secrets,subprocess,socket,sys
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
def listening(port):
 with socket.socket() as s:return s.connect_ex(('127.0.0.1',port))==0
if not (ROOT/'.widget-token').exists():(ROOT/'.widget-token').write_text(secrets.token_hex(32));(ROOT/'.widget-token').chmod(0o600)
app=ROOT/'MissionPCB Assistant.app';mac=app/'Contents/MacOS';mac.mkdir(parents=True,exist_ok=True)
subprocess.run(['swiftc',str(ROOT/'FloatingPanel.swift'),'-o',str(mac/'MissionPCBPanel'),'-framework','Cocoa','-framework','SwiftUI'],check=True)
with (app/'Contents/Info.plist').open('wb') as f:plistlib.dump({'CFBundleExecutable':'MissionPCBPanel','CFBundleIdentifier':'local.missionpcb.assistant','CFBundleName':'MissionPCB Assistant','CFBundlePackageType':'APPL','LSUIElement':True,'MissionPCBToken':(ROOT/'.widget-token').read_text()},f)
for port,script in [(8769,REPO/'missionpcb_review/service.py'),(8768,ROOT/'dashboard.py')]:
 if not listening(port):subprocess.Popen([sys.executable,str(script)],cwd=REPO,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['open',str(app)],check=True)
print('Widget opened. Services stay local on ports8768/8769.')
