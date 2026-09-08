"""Live dashboard cycle. Restores original placements/pin; keeps labeled audit evidence."""
import json,time,urllib.request
from pathlib import Path
import bridge
from verify_e2e import models
ROOT=Path(__file__).resolve().parent
TOKEN=(ROOT/'.widget-token').read_text()
def request(path,payload=None):
 data=(payload if isinstance(payload,str) else json.dumps(payload)).encode() if payload is not None else None
 req=urllib.request.Request('http://127.0.0.1:8768'+path,data=data,headers={'X-Widget-Token':TOKEN})
 result=urllib.request.urlopen(req,timeout=50).read().decode()
 return json.loads(result) if path=='/state' else result
def command(text):
 result=request('/command',text)
 if result.startswith('Could not apply:'):raise RuntimeError(result)
 return result
def run():
 board=bridge.connect();before=bridge.snapshot(board);original_models=models(board)
 initial=request('/state');pin=initial.get('journal',{}).get('pins',{}).get('U1',False)
 evidence={'board':before['board'],'started_at':time.time(),'steps':{}}
 try:
  evidence['steps']['initial_review']=command('Full check')
  state=request('/state');reviews=[e for e in state['journal']['events'] if e['kind']=='engine_review']
  finding=reviews[-1]['payload']['findings'][0]['id']
  note='E2E verification: retain this finding comment across review cycles.'
  assert request('/comment',{'finding_id':finding,'text':note})=='Saved'
  assert any(c['text']==note and c['finding_id']==finding for c in request('/state')['journal']['comments'])
  request('/pin',{'ref':'U1','pinned':True})
  blocked=request('/command','Move U1 2 mm right')
  assert 'Pinned components would move' in blocked
  assert bridge.snapshot(board)==before
  evidence['steps']['pin_blocks_move']=True
  request('/pin',{'ref':'U1','pinned':False})
  evidence['steps']['move']=command('Move U1 2 mm right')
  assert bridge.snapshot(board)['revision']!=before['revision']
  assert models(board)==original_models
  state=request('/state');assert state['review_stale'] is True
  assert any(e['kind']=='design_change' for e in state['journal']['events'])
  evidence['steps']['review_and_annotate']=command('Review and annotate board')
  assert request('/state')['review_stale'] is False
 finally:
  current=bridge.snapshot(board)
  if current['revision']!=before['revision']:
   bridge.apply({'board':before['board'],'base_revision':current['revision'],'moves':[{k:p[k] for k in ('ref','x_mm','y_mm','rotation_deg')} for p in before['parts']]})
  request('/pin',{'ref':'U1','pinned':pin})
  assert bridge.snapshot(board)==before
  assert models(board)==original_models
  evidence['placements_and_models_restored']=True
 evidence['steps']['restored_review']=command('Flag and comment')
 final=request('/state')
 assert any(c['text']==note for c in final['journal']['comments'])
 assert final['review_stale'] is False
 evidence['comment_persisted']=True;evidence['status']='PASS'
 (bridge.TARGET.parent/'verification/dashboard-cycle-e2e.json').write_text(json.dumps(evidence,indent=2))
 print(json.dumps(evidence,indent=2))
if __name__=='__main__':run()
