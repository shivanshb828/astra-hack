"""Live E2E check; restores original placements even when verification fails."""
import json,urllib.request
from pathlib import Path
import bridge
ROOT=Path(__file__).resolve().parent
TOKEN=(ROOT/'.widget-token').read_text()
def command(text):
 request=urllib.request.Request('http://127.0.0.1:8768/command',data=text.encode(),headers={'X-Widget-Token':TOKEN},method='POST')
 reply=urllib.request.urlopen(request,timeout=40).read().decode()
 if reply.startswith('Could not apply:'):raise RuntimeError(reply)
 return reply
def models(board):
 return {f.reference_field.text.value:[str(m) for m in f.definition.models] for f in board.get_footprints()}
def run():
 board=bridge.connect();before=bridge.snapshot(board);original_models=models(board);report={'board':before['board'],'initial_revision':before['revision'],'steps':{}}
 try:
  report['steps']['inspect']=command('Inspect the board')
  report['steps']['initial_review']=command('Full check')
  report['steps']['improve']=command('Improve the layout')
  after=bridge.snapshot(board);assert after['revision']!=before['revision'],'Improvement did not move parts'
  assert models(board)==original_models,'3D model definitions changed'
  report['steps']['improved_review']=command('Full check')
  result=json.loads((bridge.TARGET.parent/'verification/live-review.json').read_text())
  assert result['native_board_revision']==after['revision']
  report['improved_summary']=result['result']['summary']
  assert result['result']['summary']['FAIL']==0,'Improved placement still fails configured engine checks'
  report['saved_drc_violations']=len(result['saved_board_drc'].get('violations',[]))
 finally:
  current=bridge.snapshot(board)
  moves=[{k:p[k] for k in ('ref','x_mm','y_mm','rotation_deg')} for p in before['parts']]
  if current['revision']!=before['revision']:bridge.apply({'board':before['board'],'base_revision':current['revision'],'moves':moves})
  assert bridge.snapshot(board)==before,'Original placements were not restored'
  assert models(board)==original_models,'Model definitions were not restored'
  report['restored']=True
 report['steps']['restored_review']=command('Full check');report['status']='PASS'
 (bridge.TARGET.parent/'verification/widget-e2e.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='steps'},indent=2))
if __name__=='__main__':run()
