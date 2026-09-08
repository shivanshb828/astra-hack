"""Live HTTP constraint edit/recheck test; restores the existing limit store."""
import json
import urllib.request
from pathlib import Path
import mission_constraints as mc
from verify_dashboard_cycle import request,command

def run():
 before=mc.OVERRIDES.read_bytes() if mc.OVERRIDES.exists() else None
 state=request('/state');old=state['mission_constraints'];row=next(r for r in old['rows'] if r['id']=='afe_MCU')
 try:
  assert request('/constraint',{'id':'afe_MCU','limit_mm':row['limit_mm']+1,'base_revision':old['revision']})=='Saved'
  changed=request('/state');assert changed['review_stale']
  command('Full check');updated=request('/state')
  rule=next(r for r in updated['mission_constraints']['rows'] if r['id']=='afe_MCU')
  assert rule['limit_mm']==row['limit_mm']+1 and rule['status'] in ('PASS','FAIL')
  assert rule['measured_mm'] is not None and not updated['review_stale']
  evidence={'status':'PASS','constraint':'afe_MCU','limit_before_mm':row['limit_mm'],'tested_limit_mm':rule['limit_mm'],'measured_mm':rule['measured_mm'],'stale_after_edit':True,'fresh_after_review':True}
 finally:
  if before is None:mc.OVERRIDES.unlink(missing_ok=True)
  else:mc.OVERRIDES.write_bytes(before)
  command('Full check')
 evidence['original_limits_restored']=True
 out=Path(__file__).resolve().parents[2]/'missionpcb_kicad/verification/constraint-limits-e2e.json';out.write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence,indent=2))
if __name__=='__main__':run()
