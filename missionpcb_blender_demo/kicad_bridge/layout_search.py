"""Ten seeded layout searches, validated by the real engine; no CAD writes."""
import copy,json,math,random,sys,tempfile,threading,uuid
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'missionpcb_review')]
from constraint_engine import load_layout,load_parts,validate
from constraint_engine.solver import solve
from layout_adapter import payload_for
import bridge,mission_constraints,review_journal
_lock=threading.Lock()
_job=None

def rank_report(report,movement):
 checks=report['checks'];fails=[c for c in checks if c['status']=='FAIL']
 hard=sum(c.get('severity') in ('blocker','error','critical') for c in fails)
 deficit=sum(max(0,-(c.get('margin_mm') or 0)) for c in fails)
 uncertain=sum(c['status'] in ('WARN','SKIP') for c in checks)
 return [hard,len(fails),round(deficit,6),uncertain,round(movement,6)]

def choose_best(candidates):return min(candidates,key=lambda c:(c['rank'],c['id']))

def to_native_moves(placements,mapping):
 return [{'ref':mapping[p['ref']],'x_mm':round(100+p['x_mm'],6),'y_mm':round(138-p['y_mm'],6),'rotation_deg':((90 if mapping[p['ref']]=='U3' else 0)-p['rotation_deg'])%360} for p in placements]

def generate(before,pins,progress=lambda rows:None):
 payload=payload_for(before)
 for p in payload['layout']['placements']:p['anchored']=bool(pins.get(payload['kicad_refs'][p['ref']]))
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp)/'layout.json';path.write_text(json.dumps(payload['layout']));layout,warnings=load_layout(path)
 parts,pw=load_parts(ROOT/'missionpcb_review/native-six-parts.json')
 baseline={p.ref:p for p in layout.placements}
 def evaluate(candidate,index):
  report=validate(candidate,parts,warnings+pw).to_dict()
  movement=sum(math.hypot(p.x_mm-baseline[p.ref].x_mm,p.y_mm-baseline[p.ref].y_mm) for p in candidate.placements)
  placements=[{'ref':p.ref,'x_mm':p.x_mm,'y_mm':p.y_mm,'rotation_deg':p.rotation_deg} for p in candidate.placements]
  return {'id':index,'rank':rank_report(report,movement),'summary':report['summary'],'moves':to_native_moves(placements,payload['kicad_refs']),'movement_mm':round(movement,2),'checks':report['checks']}
 original=evaluate(layout,0);rows=[]
 for index in range(10):
  rng=random.Random(index);start=layout
  if index:
   start=replace(layout,placements=[p if p.anchored else replace(p,x_mm=rng.uniform(8,64),y_mm=rng.uniform(8,30)) for p in layout.placements])
  solved,_=solve(start,parts,seeds=(0,),name='Candidate '+str(index+1))
  row=evaluate(solved,index+1)
  # Retain a no-regression candidate even if the solver's proxy cost differs.
  if index==0 and original['rank']<row['rank']:row={**original,'id':1,'retained_current':True}
  rows.append(row);progress(copy.deepcopy(rows))
 return rows

def status():
 with _lock:return copy.deepcopy(_job)

def start():
 global _job
 before=bridge.snapshot(bridge.connect());pins=review_journal.get_state(before['board'])['pins'];constraint_revision=mission_constraints.revision()
 with _lock:
  if _job and _job['status']=='running':return 'Search already running.'
  _job={'id':uuid.uuid4().hex,'status':'running','completed':0,'total':10,'candidates':[],'board_revision':before['revision'],'constraint_revision':constraint_revision,'pins':pins,'before':before}
 def worker():
  def progress(rows):
   with _lock:_job.update(completed=len(rows),candidates=rows)
  try:
   rows=generate(before,pins,progress);winner=choose_best(rows)
   with _lock:_job.update(status='complete',winner=winner,reason='Fewest hard failures, then total failures, violation deficit, unknown checks, and movement. Ties use candidate number.')
  except Exception as e:
   with _lock:_job.update(status='failed',error=str(e))
 threading.Thread(target=worker,daemon=True).start()
 return 'Searching 10 candidate layouts. The best candidate will be selected automatically; see Search results in the widget.'

def apply_winner():
 job=status()
 if not job or job['status']!='complete':raise ValueError('Finish a candidate search first')
 before=bridge.snapshot(bridge.connect())
 if before['revision']!=job['board_revision'] or mission_constraints.revision()!=job['constraint_revision']:raise ValueError('Board or constraints changed; run the search again')
 pins=review_journal.get_state(before['board'])['pins']
 if pins!=job['pins']:raise ValueError('Component pins changed; run the search again')
 moves=job['winner']['moves'];result=bridge.apply({'board':before['board'],'base_revision':before['revision'],'moves':moves})
 review_journal.append_event(before['board'],'design_change',{'command':'Apply best of 10','before':result['before'],'after':result['after'],'moves':moves,'source':'seeded layout search','winner':job['winner']['id'],'ranking':[{'id':c['id'],'rank':c['rank']} for c in job['candidates']]})
 with _lock:_job['status']='applied'
 return 'Applied candidate '+str(job['winner']['id'])+' of 10. One Undo reverses the placement. Run Review & annotate to update native flags.'
