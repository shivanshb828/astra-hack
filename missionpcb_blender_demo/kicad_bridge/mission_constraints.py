"""Trace authored placement policies to the design brief and persist explicit edits."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OVERRIDES=Path(__file__).resolve().parent/'runtime/constraint-limits.json'
BRIEF=ROOT/'missions/ecg-patch.md'

def limits():
 return json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}

def revision():
 return hashlib.sha256((BRIEF.read_text()+json.dumps(limits(),sort_keys=True)).encode()).hexdigest()

def apply_limits(layout):
 overrides=limits()
 for rule in layout['mission_rules']:
  if rule['id'] in overrides:rule['distance_mm']=overrides[rule['id']]
 return layout

def update(rule_id,value,base_revision):
 if base_revision!=revision():raise ValueError('Constraints changed; refresh before editing')
 from design_context import get_context
 rules={r['id'] for r in get_context()['constraints']['mission_rules']}
 if rule_id not in rules:raise ValueError('Unknown constraint')
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<=100:raise ValueError('Limit must be greater than 0 and at most 100 mm')
 data=limits();data[rule_id]=value
 OVERRIDES.parent.mkdir(parents=True,exist_ok=True)
 tmp=OVERRIDES.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(OVERRIDES)

def view(state):
 from design_context import get_context
 context=get_context();mapping={p['role']:p['ref'] for p in context['parts']}
 present={p['ref'] for p in state.get('parts',[])}
 report=state.get('review') or {};checks=report.get('checks',report.get('findings',[]))
 by_id={c['id']:c for c in checks}
 current=revision();stale=state.get('review_stale',False) or report.get('constraint_revision')!=current
 rows=[]
 for rule in context['constraints']['mission_rules']:
  refs=[mapping.get(ref,ref) for ref in rule['between']]
  check=by_id.get('mission.'+rule['id']);available=set(refs)<=present
  maximum=rule['type']=='max_separation'
  rows.append({'id':rule['id'],'requirement':'Preserve the ECG signal while recording and communicating over BLE.',
   'brief_quote':'the patch records continuously and streams to the patient’s phone over BLE',
   'rule':('Keep supporting parts close to their circuit' if maximum else 'Separate sensitive circuitry from interference sources'),
   'refs':refs,'comparison':'≤' if maximum else '≥','limit_mm':rule['distance_mm'],
   'basis':'User-adjusted engineering policy' if rule['id'] in limits() else 'Authored engineering policy; the brief does not specify this distance',
   'rationale':rule.get('rationale',''),'status':('NOT PRESENT' if not available else 'STALE' if stale and report else check['status'] if check else 'NOT EVALUATED'),
   'measured_mm':check.get('measured_mm') if check and not stale else None,'editable':True})
 for ident,requirement,quote,reason in [
  ('enclosure','Fit a thin sealed enclosure','roughly 100 x 40 x 7 mm interior','Native demo uses a fixed 90 × 50 × 10 mm enclosure proxy; the brief’s enclosure is not validated.'),
  ('runtime','Record continuously for up to 14 days','worn continuously for up to 14 days','Battery cell, duty-cycle power budget and runtime model are not connected.'),
  ('water','Remain sealed during showers','showers included, never removed','No ingress or sealing assessment is implemented.'),
  ('charge','Charge through an accessible gasketed window','charged from a cradle through a gasketed contact window','The current enclosure has no modeled opening; connector access is not validated.'),
  ('patient','Support patient-contact ECG acquisition','Two Ag/AgCl electrodes pick up the biopotential','Electrical protection, electrodes and regulatory review are not validated.')]:
  rows.append({'id':ident,'requirement':requirement,'brief_quote':quote,'rule':reason,'refs':[],'basis':'Explicit brief requirement','status':'NOT EVALUATED','editable':False})
 return {'brief':BRIEF.read_text(),'source':'missions/ecg-patch.md','revision':current,'stale':stale,'rows':rows}
