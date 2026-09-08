"""Ten seeded layout searches, validated by the real engine; no CAD writes."""
import copy,json,math,random,sys,tempfile,uuid,os,subprocess,fcntl,time
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'missionpcb_review')]
from constraint_engine import load_layout,load_parts,validate
from constraint_engine.solver import solve
from layout_adapter import payload_for
import bridge,mission_constraints,review_journal
JOB_FILE=Path(__file__).resolve().parent/'runtime/layout-search.json'
_pending_key=None
_pending_since=0.0

def input_key(before,pins,constraint_revision):
 return (before['board'],before['revision'],constraint_revision,json.dumps(pins,sort_keys=True))

def ensure_background(before,now=None):
 """Debounce edits and search each board/rule/pin state once; never apply it."""
 global _pending_key,_pending_since
 if not before.get('connected',True):return
 pins=review_journal.get_state(before['board'])['pins'];revision=mission_constraints.revision()
 key=input_key(before,pins,revision);clock=time.monotonic() if now is None else now
 if key!=_pending_key:
  _pending_key=key;_pending_since=clock;return
 if clock-_pending_since<1.5:return
 old=status()
 if old:
  if old['status']=='running':return
  if input_key(old['before'],old['pins'],old['constraint_revision'])==key:return
 start(before=before,pins=pins,constraint_revision=revision)


def save_job(job):
 JOB_FILE.parent.mkdir(parents=True,exist_ok=True)
 temporary=JOB_FILE.with_name(JOB_FILE.name+'.'+uuid.uuid4().hex+'.tmp')
 temporary.write_text(json.dumps(job))
 temporary.replace(JOB_FILE)

def process_running(pid):
 if not pid:return False
 try:os.kill(pid,0);return True
 except ProcessLookupError:return False

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
 if not JOB_FILE.exists():return None
 job=json.loads(JOB_FILE.read_text())
 if job['before']['board']!=str(bridge.TARGET):return None
 if job['status']=='running' and not process_running(job.get('pid')):
  job.update(status='failed',error='Layout search stopped unexpectedly. Start a new search; completed candidates are retained.')
 return job

def start(before=None,pins=None,constraint_revision=None):
 if before is None:before=bridge.snapshot(bridge.connect())
 if pins is None:pins=review_journal.get_state(before['board'])['pins']
 if constraint_revision is None:constraint_revision=mission_constraints.revision()
 # Persist only native geometry, not dashboard events or previous search results.
 before={key:before[key] for key in ('board','revision','parts')}
 JOB_FILE.parent.mkdir(parents=True,exist_ok=True)
 with JOB_FILE.with_suffix('.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  old=status()
  if old and old['status']=='running':return 'Search already running.'
  job={'id':uuid.uuid4().hex,'status':'running','completed':0,'total':10,'candidates':[],'board_revision':before['revision'],'constraint_revision':constraint_revision,'pins':pins,'before':before}
  request=JOB_FILE.with_name('layout-search-'+job['id']+'.request.json');request.write_text(json.dumps(job))
  # The worker waits for its PID to be published before writing progress.
  with JOB_FILE.with_suffix('.log').open('a') as log:
   process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(request)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  job['pid']=process.pid;save_job(job)
 return 'Searching 10 candidate layouts. Progress survives widget restarts; the best candidate is selected automatically.'

def worker(request):
 import time
 job=json.loads(request.read_text());job['pid']=os.getpid()
 try:
  for _ in range(100):
   if JOB_FILE.exists() and json.loads(JOB_FILE.read_text()).get('id')==job['id']:break
   time.sleep(.05)
  else:raise ValueError('Search could not publish its initial state.')
  if mission_constraints.revision()!=job['constraint_revision']:raise ValueError('Constraints changed before search started. Run again.')
  def progress(rows):
   job.update(completed=len(rows),candidates=rows);save_job(job)
  rows=generate(job['before'],job['pins'],progress);winner=choose_best(rows)
  job.update(status='complete',winner=winner,reason='Fewest hard failures, then total failures, violation deficit, unknown checks, and movement. Ties use candidate number.')
 except Exception as e:job.update(status='failed',error=str(e))
 finally:
  save_job(job);request.unlink(missing_ok=True)

def revalidate():
 job=status()
 if not job or job['status'] not in ('complete','applied'):raise ValueError('Finish a search first')
 before=bridge.snapshot(bridge.connect())
 if before['revision']!=job['board_revision']:raise ValueError('Board changed; start a new search')
 revision=mission_constraints.revision();parts,pw=load_parts(ROOT/'missionpcb_review/native-six-parts.json')
 for candidate in job['candidates']:
  moves={m['ref']:m for m in candidate['moves']}
  state={**before,'parts':[{**p,**moves[p['ref']]} for p in before['parts']]}
  payload=payload_for(state)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'layout.json';path.write_text(json.dumps(payload['layout']));layout,warnings=load_layout(path)
  report=validate(layout,parts,warnings+pw).to_dict()
  movement=sum(math.hypot(moves[p['ref']]['x_mm']-p['x_mm'],moves[p['ref']]['y_mm']-p['y_mm']) for p in before['parts'])
  candidate.update(checks=report['checks'],summary=report['summary'],rank=rank_report(report,movement))
 if mission_constraints.revision()!=revision:raise ValueError('Constraints changed during recheck; recheck again')
 job.update(status='complete',constraint_revision=revision,winner=choose_best(job['candidates']),reason='All ten candidates rechecked against current rules; ranked by hard failures, total failures, deficit, unknown checks, and movement.')
 save_job(job);return 'Rechecked all ten candidates. Candidate '+str(job['winner']['id'])+' selected.'

def apply_winner():
 job=status()
 if not job or job['status']!='complete':raise ValueError('Finish a candidate search first')
 before=bridge.snapshot(bridge.connect())
 if before['revision']!=job['board_revision'] or mission_constraints.revision()!=job['constraint_revision']:raise ValueError('Board or constraints changed; run the search again')
 pins=review_journal.get_state(before['board'])['pins']
 if pins!=job['pins']:raise ValueError('Component pins changed; run the search again')
 moves=job['winner']['moves'];result=bridge.apply({'board':before['board'],'base_revision':before['revision'],'moves':moves})
 review_journal.append_event(before['board'],'design_change',{'command':'Apply best of 10','before':result['before'],'after':result['after'],'moves':moves,'source':'seeded layout search','winner':job['winner']['id'],'ranking':[{'id':c['id'],'rank':c['rank']} for c in job['candidates']]})
 job['status']='applied';save_job(job)
 from widget_command import refresh_native_flags_after_move
 return 'Applied and verified the suggested placement in KiCad. '+refresh_native_flags_after_move()

if __name__=='__main__' and len(sys.argv)==3 and sys.argv[1]=='--worker':worker(Path(sys.argv[2]))
