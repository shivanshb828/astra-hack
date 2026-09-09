"""Persistent, explicit engineer decisions around immutable native PCB proposals."""
import copy,hashlib,json,sys,tempfile,threading,uuid,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'missionpcb_review')]
import bridge,review_journal,mission_constraints,brief_store
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
def input_revision():return hashlib.sha256(json.dumps({'inputs':inputs(),'brief_revision':brief_store.current()['revision']},sort_keys=True).encode()).hexdigest()
def inputs_stale():
 rows=[e for e in events() if e['kind']=='wearable_inputs']
 current=brief_store.current()['revision']
 if rows:return rows[-1]['payload'].get('brief_revision')!=current
 return brief_store.current()['text'].strip()!=brief_store.CANONICAL_BRIEF.read_text().strip()
def profile_state():
 import device_profile
 brief=brief_store.current();rows=[e for e in events() if e['kind']=='device_profile_adopted']
 adopted=rows[-1]['payload'] if rows else None
 return dict(proposed=device_profile.extract_profile(brief['text'],source=brief['source'],revision=brief['revision']),adopted=adopted['profile'] if adopted else None,revision=rows[-1]['id'] if rows else 'none',stale=bool(adopted and adopted['brief_revision']!=brief['revision']),brief_revision=brief['revision'])

def save_profile(payload):
 import device_profile
 with LOCK:
  current=profile_state()
  if payload.get('base_profile_revision')!=current['revision'] or payload.get('brief_revision')!=current['brief_revision']:raise ValueError('Brief or device profile changed. Review the current proposal.')
  profile=device_profile.validate_profile(payload['profile'])
  return append('device_profile_adopted',dict(profile=profile,brief_revision=current['brief_revision'],proposed=current['proposed'],basis='Engineer-reviewed housing and body-placement profile; geometry fit remains to be checked.'))

def generate_housing(payload):
 import blender_handoff
 with LOCK:
  if not isinstance(payload.get('expected_session'),str) or not payload['expected_session']:raise ValueError('Refresh the Blender connection before generating housing.')
  current=profile_state()
  if not current['adopted'] or current['stale'] or payload.get('profile_revision')!=current['revision']:raise ValueError('Review and save the device profile for the current brief before generating housing.')
  result=blender_handoff.dispatch('assembly_generate_housing',profile={**current['adopted'],'status':'adopted','revision':current['revision'],'brief_revision':current['brief_revision']},expected_session=payload.get('expected_session'))
  append('device_housing_generated',dict(profile_revision=current['revision'],brief_revision=current['brief_revision'],result=result))
  return result
def brief_targets():
 import brief_targets as parser
 brief=brief_store.current()
 return {**parser.extract(brief['text']),'brief_revision':brief['revision'],'input_revision':input_revision()}

def adopt_brief_targets(payload):
 with LOCK:
  targets=brief_targets()
  if payload.get('brief_revision')!=targets['brief_revision'] or payload.get('input_revision')!=targets['input_revision']:raise ValueError('Brief or evidence changed. Review fresh targets.')
  selected=payload.get('fields',[])
  available={c['field']:c['value'] for c in targets['candidates']}
  if not selected or not isinstance(selected,list) or any(k not in available for k in selected):raise ValueError('Select supported targets from the brief preview.')
  data=inputs();data.update({k:available[k] for k in selected})
  saved=save_inputs({'base_revision':targets['input_revision'],'inputs':data})
  append('brief_targets_adopted',dict(brief_revision=targets['brief_revision'],targets={k:available[k] for k in selected},evidence_event=saved['id']))
  return saved

def summary():
 """Journal and declared evidence only: no live KiCad requests."""
 rows=events();snapshots=[e for e in rows if e['kind']=='design_snapshot'];brief=brief_store.current()
 return dict(board=str(bridge.TARGET),project_name=bridge.TARGET.parent.name,project_brief=brief,brief=brief['text'],device_profile=profile_state(),input_revision=input_revision(),inputs_stale=inputs_stale(),inputs=inputs(),wearable_checks=evaluate_wearable(inputs()),brief_targets=brief_targets(),latest_snapshot=snapshots[-1] if snapshots else None,decisions=[e for e in rows if e['kind'] in ('finding_decision','proposal_decision')],sources=SOURCES)

def add_comment(payload):
 with LOCK:
  ident=payload.get('finding_id');note=payload.get('text','')
  if not isinstance(note,str) or not 0<len(note.strip())<=2000:raise ValueError('Write an engineering note of 1–2000 characters.')
  if not any(ident==c.get('id') for e in events() if e['kind']=='design_snapshot' for c in e['payload']['report']['checks']):raise ValueError('Capture a finding before adding a note.')
  return review_journal.add_comment(str(bridge.TARGET),ident,note.strip())

def focus_finding(payload):
 current=bridge.snapshot(bridge.connect())
 if payload.get('base_revision')!=current['revision']:raise ValueError('Board changed. Capture a fresh review before selecting a finding.')
 check=next((c for c in evaluate(current)['checks'] if c['id']==payload.get('finding_id')),None)
 if not check:raise ValueError('Finding no longer exists.')
 refs=check.get('kicad_refs',[])
 if not refs:raise ValueError('This requirement has no component geometry to select.')
 import widget_command
 return {'message':widget_command.run('select '+','.join(refs)),'refs':refs}
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
  warnings=[]
  try:capture('Accepted revision '+ident[:8])
  except Exception as error:
   warnings.append('Placement applied; snapshot capture failed: '+str(error))
   append('validation_unavailable',dict(proposal_id=ident,error=str(error),placement_applied=True,stage='snapshot'))
  # Save the accepted native revision before checking disk-based tools.
  try:
   board=bridge.connect()
   if bridge.snapshot(board)['revision']!=result['after']['revision']:raise ValueError('Board changed after apply; not saved automatically.')
   try:
    import native_flags
    native_flags.apply_findings({'native_board_revision':result['after']['revision'],'findings':[c for c in p['candidate']['checks'] if c['status']!='PASS']})
   except Exception as annotation_error:
    warnings.append('Placement applied; markers could not refresh: '+str(annotation_error))
    append('presentation_unavailable',dict(proposal_id=ident,error=str(annotation_error),placement_applied=True,stage='annotations'))
   board.save();start_checks(result['after']['revision'])
   try:
    import widget_command
    widget_command.record_review([c for c in p['candidate']['checks'] if c['status']!='PASS'],p['candidate']['summary'],result['after']['revision'],annotated=True,checks=p['candidate']['checks'])
    widget_command.open_native_3d()
   except Exception as presentation_error:
    warnings.append('Placement applied; native presentation could not refresh: '+str(presentation_error))
    append('presentation_unavailable',dict(proposal_id=ident,error=str(presentation_error),placement_applied=True))
  except Exception as e:
   warnings.append('Placement applied; save or background validation failed: '+str(e))
   append('validation_unavailable',dict(proposal_id=ident,error=str(e),placement_applied=True))
  return {**event,'placement_applied':True,'warnings':warnings}

def validation_fingerprint(board,project=None,rules=None,schematic=None,erc_project=None,schematic_error=None):
 values={name:hashlib.sha256(path.read_bytes()).hexdigest() if path and path.exists() else None for name,path in [('board',board),('project',project),('rules',rules),('schematic',schematic),('erc_project',erc_project)]}
 if schematic_error:values['schematic_error']=schematic_error
 return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

def drc_counts(report):
 return {key:len(report.get(key,[])) for key in ('violations','unconnected_items','schematic_parity')}

def start_checks(revision=None):
 """Copy saved CAD and project rules, then run tools on that immutable evidence."""
 folder=Path(__file__).parent/'runtime/validation'/uuid.uuid4().hex;folder.mkdir(parents=True)
 source=bridge.TARGET;copy_path=folder/source.name;shutil.copy2(source,copy_path)
 for suffix in ('.kicad_pro','.kicad_dru'):
  project=source.with_suffix(suffix)
  if project.exists():shutil.copy2(project,folder/project.name)
 digest=hashlib.sha256(copy_path.read_bytes()).hexdigest();ident=folder.name
 import circuit_readiness
 try:
  schematic=circuit_readiness.get_erc_source();schematic_error=None
  if schematic:
   frozen=folder/'source.kicad_sch';shutil.copy2(schematic,frozen)
   project=schematic.with_suffix('.kicad_pro')
   if project.exists():shutil.copy2(project,folder/'source.kicad_pro')
   schematic=frozen
 except Exception as error:schematic=None;schematic_error=str(error)
 fingerprint=validation_fingerprint(copy_path,folder/source.with_suffix('.kicad_pro').name,folder/source.with_suffix('.kicad_dru').name,schematic,folder/'source.kicad_pro',schematic_error)
 append('validation_started',dict(id=ident,revision=revision,saved_board_sha256=digest,inputs_sha256=fingerprint,scope='Saved PCB, schematic and rule snapshots; no automatic routing',folder=str(folder)))
 def worker():
  results={}
  for kind,path in [('drc',copy_path),('erc',schematic)]:
   if not path or not path.exists():results[kind]={'status':'SKIP','reason':schematic_error or 'No schematic exists for the active PCB.'};continue
   output=folder/(kind+'.json')
   try:
    command=[CLI,'pcb' if kind=='drc' else 'sch',kind,'--format','json','-o',str(output),str(path)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=90)
    if p.returncode!=0 or not output.exists():raise ValueError(p.stderr or p.stdout or 'Tool produced no report')
    report=json.loads(output.read_text());counts=drc_counts(report) if kind=='drc' else {'violations':sum(len(sheet.get('violations',[])) for sheet in report.get('sheets',[]))};total=sum(counts.values())
    results[kind]={'status':'FAIL' if total else 'PASS','violations':total,'categories':counts,'report':str(output),'tool':'KiCad CLI','scope':'Saved board; no-net designs still require connectivity evidence' if kind=='drc' else 'Immutable schematic source; PCB connectivity comparison is separate'}
   except Exception as e:results[kind]={'status':'ERROR','reason':str(e)}
  results['routing']={'status':'SKIP','reason':'No configured autorouter or verified schematic-to-PCB netlist pipeline. Placement changes do not create copper connections.'}
  append('validation_completed',dict(id=ident,revision=revision,saved_board_sha256=digest,inputs_sha256=fingerprint,results=results))
 threading.Thread(target=worker,daemon=True).start();return {'id':ident,'status':'running'}

def save_inputs(payload):
 with LOCK:
  if payload.get('base_revision')!=input_revision():raise ValueError('Wearable inputs changed; refresh.')
  data=payload['inputs']
  if not isinstance(data,dict) or len(json.dumps(data))>10000:raise ValueError('Invalid wearable inputs')
  checks=evaluate_wearable(data)
  return append('wearable_inputs',dict(inputs=data,checks=checks,brief_revision=brief_store.current()['revision'],basis='Engineer-authored design targets and evidence; not regulatory limits'))

def view():
 rows=events();data=inputs()
 try:current=bridge.snapshot(bridge.connect());connected=True;error=None
 except Exception as e:current=None;connected=False;error=str(e)
 saved_digest=hashlib.sha256(bridge.TARGET.read_bytes()).hexdigest() if bridge.TARGET.exists() else None
 validations=[e for e in rows if e['kind']=='validation_completed']
 import circuit_readiness
 try:schematic=circuit_readiness.get_erc_source();schematic_error=None
 except Exception as err:schematic=None;schematic_error=str(err)
 fingerprint=validation_fingerprint(bridge.TARGET,bridge.TARGET.with_suffix('.kicad_pro'),bridge.TARGET.with_suffix('.kicad_dru'),schematic,schematic.with_suffix('.kicad_pro') if schematic else None,schematic_error)
 validation_stale=bool(validations and validations[-1]['payload'].get('inputs_sha256')!=fingerprint)
 latest=next((e['payload'] for e in reversed(rows) if e['kind']=='design_snapshot'),None)
 review_state={'parts':current['parts'] if current else []}
 if latest:review_state.update(review={**latest['report'],'constraint_revision':latest['constraint_revision']},review_stale=not current or latest['snapshot']['revision']!=current['revision'])
 import circuit_readiness
 try:circuit=circuit_readiness.view()
 except Exception as circuit_error:circuit={'status':'ERROR','blockers':[str(circuit_error)],'coverage':{}}
 return dict(inputs_stale=inputs_stale(),device_profile=profile_state(),circuit=circuit,journal=review_journal.get_state(str(bridge.TARGET)),brief_targets=brief_targets(),validation_stale=validation_stale,connected=connected,error=error,current=current,events=[e for e in rows if e['kind'].startswith(('design_','device_','proposal_','validation_','wearable_','finding_','presentation_','comment_','constraint_','brief_','engine_review','design_change','pin_','schematic_'))],inputs=data,input_revision=input_revision(),wearable_checks=evaluate_wearable(data),sources=SOURCES,brief=brief_store.current()['text'],project_brief=brief_store.current(),constraints=mission_constraints.view(review_state),engine='Shivansh constraint engine + explicit wearable budgets',upstream_checked='fb8ecb6')

def report_markdown(data):
 lines=['# MissionPCB engineering design report','',data['brief'],'','## Wearable budgets','', 'Targets are engineer-authored. Missing evidence is not a pass.','']
 for c in data['wearable_checks']:lines.append(f"- {c['status']} · {c['title']}: {c['message']}")
 circuit=data.get('circuit',{})
 if circuit:
  lines+=['','## Electrical design readiness','',str(circuit.get('status','UNKNOWN')).upper(),'']
  for key,value in circuit.get('coverage',{}).items():lines.append('- '+key.replace('_',' ')+': '+str(value))
  for blocker in circuit.get('blockers',[]):lines.append('- '+str(blocker))
 profile=data.get('device_profile',{})
 if profile:
  lines+=['','## Device and body profile','', 'Reviewed profile' if profile.get('adopted') else 'Proposed profile; not yet adopted','',json.dumps(profile.get('adopted') or profile.get('proposed'),indent=2)]
  if profile.get('stale'):lines.append('STALE: the brief changed after this profile was adopted.')
 snapshots=[e for e in data['events'] if e['kind']=='design_snapshot']
 if snapshots:
  latest=snapshots[-1]['payload'];lines+=['','## Latest captured findings','', 'Captured board revision: '+latest['snapshot']['revision'],'']
  for c in latest['report']['checks']:
   if c['status']=='PASS':continue
   lines+=['### '+c['id']+' · '+c['status'],'',c.get('message',''),'']
   if c.get('kicad_refs'):lines.append('Components: '+', '.join(c['kicad_refs']))
   if c.get('measured_mm') is not None:lines.append('Measured: '+str(c['measured_mm'])+'; required: '+str(c.get('required_mm','unknown')))
   for note in data.get('journal',{}).get('comments',[]):
    if note['finding_id']==c['id']:lines.append('Engineering note: '+note['text'])
 lines+=['','## Design timeline','']
 for e in data['events']:
  p=e['payload'];lines+=['### '+e['timestamp']+' · '+e['kind'],'',p.get('label',p.get('rationale',p.get('note',p.get('text',''))))]
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
