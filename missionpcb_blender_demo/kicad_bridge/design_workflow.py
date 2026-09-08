"""Persistent, explicit engineer decisions around immutable native PCB proposals."""
import copy,hashlib,json,sys,tempfile,threading,uuid,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'missionpcb_review')]
import bridge,review_journal,mission_constraints
from layout_adapter import payload_for
from constraint_engine import load_layout,load_parts,validate
from constraint_engine.wearable import evaluate_wearable,compare_checks
LOCK=threading.RLock()
CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
SOURCES=[
 {'id':'ti-layout','title':'TI ADS1292R layout guidance','url':'https://www.ti.com/lit/ds/symlink/ads1292r.pdf','requirement':'Review analog return paths, decoupling and digital-current isolation. Spacing alone does not validate noise performance.','status':'EVIDENCE REQUIRED'},
 {'id':'skin-contact','title':'FDA biocompatibility assessment','url':'https://www.fda.gov/medical-devices/biocompatibility-assessment-resource-center/biocompatibility-evaluation-endpoints-contact-duration-periods','requirement':'Assess contact materials and contact duration for the intended intact-skin use. No biological test result is inferred from CAD.','status':'EVIDENCE REQUIRED'},
 {'id':'electrical','title':'KiCad DRC and ERC tooling','url':'https://docs.kicad.org/10.0/en/cli/cli.html','requirement':'Validate routing/manufacturing rules with DRC and schematic electrical rules with ERC. Neither is a medical-safety certification.','status':'EVIDENCE REQUIRED'}]
DEFAULTS={'max_length_mm':104,'max_width_mm':44,'max_height_mm':10,'required_runtime_hours':336}

def events():return review_journal.get_state(str(bridge.TARGET))['events']
def append(kind,payload):return review_journal.append_event(str(bridge.TARGET),kind,payload)
def inputs():
 rows=[e for e in events() if e['kind']=='wearable_inputs']
 return rows[-1]['payload']['inputs'] if rows else DEFAULTS.copy()
def input_revision():return hashlib.sha256(json.dumps(inputs(),sort_keys=True).encode()).hexdigest()
def evaluate(snapshot):
 payload=payload_for(snapshot)
 with tempfile.TemporaryDirectory() as directory:
  file=Path(directory)/'layout.json';file.write_text(json.dumps(payload['layout']));layout,warnings=load_layout(file)
 library,notes=load_parts(ROOT/'missionpcb_review/native-six-parts.json')
 result=validate(layout,library,warnings+notes).to_dict()
 for check in result['checks']:check['kicad_refs']=[payload['kicad_refs'][r] for r in check.get('subjects',[]) if r in payload['kicad_refs']]
 return result

def capture(label='Initial design'):
 with LOCK:
  before=bridge.snapshot(bridge.connect());report=evaluate(before)
  if bridge.snapshot(bridge.connect())['revision']!=before['revision']:raise ValueError('Board changed during capture. Retry.')
  return append('design_snapshot',dict(label=label,snapshot=before,report=report,constraint_revision=mission_constraints.revision(),wearable_inputs=inputs(),wearable_checks=evaluate_wearable(inputs())))

def propose(payload):
 with LOCK:
  before=bridge.snapshot(bridge.connect())
  proposal={'board':before['board'],'base_revision':payload['base_revision'],'moves':payload['moves']}
  moves=bridge.validate(proposal,before)
  pins=review_journal.get_state(before['board'])['pins']
  for move in moves:
   old=next(p for p in before['parts'] if p['ref']==move['ref'])
   if pins.get(move['ref']) and any(move[k]!=old[k] for k in ('x_mm','y_mm','rotation_deg')):raise ValueError('Unpin '+move['ref']+' before proposing its movement.')
  after=copy.deepcopy(before)
  for move in moves:next(p for p in after['parts'] if p['ref']==move['ref']).update(move)
  after['revision']=hashlib.sha256(json.dumps({k:v for k,v in after.items() if k!='revision'},sort_keys=True).encode()).hexdigest()
  baseline=evaluate(before);candidate=evaluate(after)
  if bridge.snapshot(bridge.connect())['revision']!=before['revision']:raise ValueError('Board changed during preview. Retry.')
  rationale=payload.get('rationale','').strip()
  if not rationale or len(rationale)>2000:raise ValueError('Provide a rationale of 1–2000 characters.')
  return append('design_proposal',dict(proposal_id=uuid.uuid4().hex,proposal=proposal,before=before,after=after,baseline=baseline,candidate=candidate,tradeoffs=compare_checks(baseline['checks'],candidate['checks']),rationale=rationale,pins=pins,constraint_revision=mission_constraints.revision(),input_revision=input_revision(),limitations=['Placement preview only. Copper routing and electrical behavior are not recomputed by this preview.','Moving footprints may disconnect existing tracks. Background DRC follows acceptance.']))

def decide(payload):
 with LOCK:
  ident=payload['proposal_id'];decision=payload['decision'];note=payload.get('note','').strip()
  if decision not in ('accept','reject'):raise ValueError('Choose accept or reject.')
  if not note or len(note)>2000:raise ValueError('Record an engineering decision note of 1–2000 characters.')
  rows=events();found=[e for e in rows if e['kind']=='design_proposal' and e['payload']['proposal_id']==ident]
  if not found:raise ValueError('Unknown proposal')
  if any(e['kind'] in ('proposal_decision','proposal_applying') and e['payload']['proposal_id']==ident for e in rows):raise ValueError('Proposal already decided or apply outcome needs inspection.')
  p=found[-1]['payload']
  if decision=='reject':return append('proposal_decision',dict(proposal_id=ident,decision=decision,note=note))
  current=bridge.snapshot(bridge.connect())
  if current['revision']!=p['proposal']['base_revision'] or mission_constraints.revision()!=p['constraint_revision'] or input_revision()!=p['input_revision']:raise ValueError('Design or constraints changed. Create a fresh proposal.')
  if review_journal.get_state(current['board'])['pins']!=p['pins']:raise ValueError('Pins changed. Create a fresh proposal.')
  append('proposal_applying',dict(proposal_id=ident,note=note))
  try:result=bridge.apply(p['proposal'])
  except Exception as e:
   append('proposal_apply_error',dict(proposal_id=ident,error=str(e)));raise
  event=append('proposal_decision',dict(proposal_id=ident,decision='accept',note=note,result=result))
  capture('Accepted revision '+ident[:8])
  # Save the accepted native revision before checking disk-based tools.
  try:
   board=bridge.connect()
   if bridge.snapshot(board)['revision']!=result['after']['revision']:raise ValueError('Board changed after apply; not saved automatically.')
   import native_flags
   native_flags.apply_findings({'native_board_revision':result['after']['revision'],'findings':[c for c in p['candidate']['checks'] if c['status']!='PASS']})
   board.save();start_checks(result['after']['revision'])
   try:
    import widget_command
    widget_command.record_review([c for c in p['candidate']['checks'] if c['status']!='PASS'],p['candidate']['summary'],result['after']['revision'],annotated=True,checks=p['candidate']['checks'])
    widget_command.open_native_3d()
   except Exception as presentation_error:append('presentation_unavailable',dict(proposal_id=ident,error=str(presentation_error),placement_applied=True))
  except Exception as e:append('validation_unavailable',dict(proposal_id=ident,error=str(e),placement_applied=True))
  return event

def start_checks(revision=None):
 """Copy saved CAD and project rules, then run tools on that immutable evidence."""
 folder=Path(__file__).parent/'runtime/validation'/uuid.uuid4().hex;folder.mkdir(parents=True)
 source=bridge.TARGET;copy_path=folder/source.name;shutil.copy2(source,copy_path)
 for suffix in ('.kicad_pro','.kicad_dru'):
  project=source.with_suffix(suffix)
  if project.exists():shutil.copy2(project,folder/project.name)
 digest=hashlib.sha256(copy_path.read_bytes()).hexdigest();ident=folder.name
 append('validation_started',dict(id=ident,revision=revision,saved_board_sha256=digest,scope='Saved board snapshot; no automatic routing',folder=str(folder)))
 def worker():
  results={}
  for kind,path in [('drc',copy_path),('erc',source.with_suffix('.kicad_sch'))]:
   if not path.exists():results[kind]={'status':'SKIP','reason':'No schematic exists for the active PCB.'};continue
   output=folder/(kind+'.json')
   try:
    command=[CLI,'pcb' if kind=='drc' else 'sch',kind,'--format','json','-o',str(output),str(path)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=90)
    if p.returncode!=0 or not output.exists():raise ValueError(p.stderr or p.stdout or 'Tool produced no report')
    report=json.loads(output.read_text());violations=report.get('violations',[]) if kind=='drc' else [v for sheet in report.get('sheets',[]) for v in sheet.get('violations',[])]
    results[kind]={'status':'FAIL' if violations else 'PASS','violations':len(violations),'report':str(output),'tool':'KiCad CLI','scope':'Saved board' if kind=='drc' else 'Existing schematic, not generated by widget'}
   except Exception as e:results[kind]={'status':'ERROR','reason':str(e)}
  results['routing']={'status':'SKIP','reason':'No configured autorouter or verified schematic-to-PCB netlist pipeline. Placement changes do not create copper connections.'}
  append('validation_completed',dict(id=ident,revision=revision,saved_board_sha256=digest,results=results))
 threading.Thread(target=worker,daemon=True).start();return {'id':ident,'status':'running'}

def save_inputs(payload):
 with LOCK:
  if payload.get('base_revision')!=input_revision():raise ValueError('Wearable inputs changed; refresh.')
  data=payload['inputs']
  if not isinstance(data,dict) or len(json.dumps(data))>10000:raise ValueError('Invalid wearable inputs')
  checks=evaluate_wearable(data)
  return append('wearable_inputs',dict(inputs=data,checks=checks,basis='Engineer-authored design targets and evidence; not regulatory limits'))

def view():
 rows=events();data=inputs()
 try:current=bridge.snapshot(bridge.connect());connected=True;error=None
 except Exception as e:current=None;connected=False;error=str(e)
 saved_digest=hashlib.sha256(bridge.TARGET.read_bytes()).hexdigest() if bridge.TARGET.exists() else None
 validations=[e for e in rows if e['kind']=='validation_completed']
 validation_stale=bool(validations and validations[-1]['payload'].get('saved_board_sha256')!=saved_digest)
 return dict(validation_stale=validation_stale,connected=connected,error=error,current=current,events=[e for e in rows if e['kind'].startswith(('design_','proposal_','validation_','wearable_','finding_'))],inputs=data,input_revision=input_revision(),wearable_checks=evaluate_wearable(data),sources=SOURCES,brief=mission_constraints.BRIEF.read_text(),constraints=mission_constraints.view({'parts':current['parts'] if current else []}),engine='Shivansh constraint engine + explicit wearable budgets',upstream_checked='fb8ecb6')

def report_markdown(data):
 lines=['# MissionPCB engineering design report','',data['brief'],'','## Wearable budgets','', 'Targets are engineer-authored. Missing evidence is not a pass.','']
 for c in data['wearable_checks']:lines.append(f"- {c['status']} · {c['title']}: {c['message']}")
 lines+=['','## Design timeline','']
 for e in data['events']:
  p=e['payload'];lines+=['### '+e['timestamp']+' · '+e['kind'],'',p.get('label',p.get('rationale',p.get('note','')))]
  if p.get('report'):lines.append('Checks: '+json.dumps(p['report']['summary']))
  if p.get('tradeoffs'):
   for key,value in p['tradeoffs'].items():lines.append('- '+key+': '+(', '.join(value) if isinstance(value,list) else value))
  if p.get('decision'):lines.append('Decision: '+p['decision']+' — '+p.get('note',''))
  if p.get('technical_status'):lines.append('Technical status remains: '+p['technical_status'])
  if p.get('results'):
   for key,value in p['results'].items():lines.append('- '+key+': '+value['status']+' · '+str(value.get('reason',str(value.get('violations',''))+' violations')))
  if p.get('error'):lines.append('Error: '+p['error'])
  if p.get('snapshot'):
   lines+=['','| Component | X mm | Y mm | Rotation |','|---|---:|---:|---:|']
   for part in p['snapshot']['parts']:lines.append(f"| {part['ref']} | {part['x_mm']} | {part['y_mm']} | {part['rotation_deg']} |")
  lines.append('')
 lines+=['## Source requirements','']
 for source in SOURCES:lines.append(f"- [{source['title']}]({source['url']}): {source['requirement']}")
 lines+=['','## Scope','Geometry and declared budgets are evaluated. Clinical sensitivity, biocompatibility, electrical patient protection, ingress protection and manufacturing readiness require additional evidence. No automatic copper routing is implemented. Download the JSON report for complete snapshots, measurements and decisions.']
 return '\n'.join(lines)

def decide_finding(payload):
 with LOCK:
  current=bridge.snapshot(bridge.connect())
  if payload['base_revision']!=current['revision']:raise ValueError('Board changed; capture a fresh review.')
  if payload.get('constraint_revision')!=mission_constraints.revision():raise ValueError('Constraints changed; capture a fresh review.')
  decision=payload['decision'];note=payload.get('note','').strip()
  if decision not in ('accept_tradeoff','request_change') or not note or len(note)>2000:raise ValueError('Choose a decision and provide a reason of 1–2000 characters.')
  check=next((c for c in evaluate(current)['checks'] if c['id']==payload['finding_id']),None)
  if not check or check['status']=='PASS':raise ValueError('This finding is no longer open. Capture a fresh review.')
  return append('finding_decision',dict(finding_id=check['id'],decision=decision,note=note,board_revision=current['revision'],constraint_revision=mission_constraints.revision(),technical_status=check['status'],scope='Engineering disposition only; technical check outcome is unchanged'))
