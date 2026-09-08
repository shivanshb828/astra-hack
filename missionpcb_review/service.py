"""Loopback review handoff. Evaluates submitted snapshots; never edits CAD."""
import hashlib,json,re,sys,tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from constraint_engine import load_layout,load_parts,validate
DATA=Path(__file__).parent/'runs'

def evaluate(payload):
    if set(payload)-{'part_library'}!={'design_id','revision','brief','layout','kicad_refs'}:
        raise ValueError('Required fields: design_id, revision, brief, layout, kicad_refs')
    design=payload['design_id'];rev=payload['revision']
    if not isinstance(design,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',design):raise ValueError('Invalid design_id')
    if isinstance(rev,bool) or not isinstance(rev,int) or rev<0:raise ValueError('revision must be a nonnegative integer')
    if not isinstance(payload['brief'],str) or not payload['brief'].strip():raise ValueError('brief is required')
    refs=payload['kicad_refs']
    if not isinstance(refs,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in refs.items()):raise ValueError('kicad_refs maps layout refs to KiCad refs')
    encoded=json.dumps(payload,sort_keys=True,allow_nan=False).encode()
    digest=hashlib.sha256(encoded).hexdigest()
    folder=DATA/design;folder.mkdir(parents=True,exist_ok=True)
    dest=folder/f'{rev}.json'
    if dest.exists():
        old=json.loads(dest.read_text())
        if old['submission_sha256']!=digest:raise FileExistsError('Revision already used for different inputs; increment revision')
        return old
    revisions=[int(p.stem) for p in folder.glob('*.json') if p.stem.isdigit()]
    if revisions and rev<max(revisions):raise FileExistsError('Stale revision; submit a newer revision')
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'layout.json';path.write_text(json.dumps(payload['layout'],allow_nan=False))
        layout,warnings=load_layout(path)
    library=payload.get('part_library','ecg-fixture')
    if library not in ('ecg-fixture','native-six'):raise ValueError('Unknown part_library')
    parts,part_warnings=load_parts(Path(__file__).parent/'native-six-parts.json' if library=='native-six' else ROOT/'parts/ecg-patch-parts.json')
    result=validate(layout,parts,warnings+part_warnings).to_dict()
    findings=[]
    for check in result['checks']:
        subjects=check.get('subjects',[])
        check['kicad_refs']=[refs[r] for r in subjects if r in refs]
        check['unmapped_refs']=[r for r in subjects if r not in refs]
        if check['status']!='PASS':findings.append(check)
    output={'design_id':design,'revision':rev,'submission_sha256':digest,'brief':payload['brief'],
      'result':result,'findings':findings,'cad_mutated':False,
      'limitations':['Brief text is retained as context; only structured layout rules are evaluated.',
       'Uses checked-in ECG demo part properties, not arbitrary manufacturer parts.',
       'Thermal and EMI clearances are declared geometric proxies, not temperature or electromagnetic solutions.',
       'Not a complete electrical, routing, medical-safety or manufacturing validation.'],
      'ui_annotations':[{'check_id':c['id'],'revision':rev,'component_refs':c['kicad_refs'],
         'status':c['status'],'color':'red' if c['status']=='FAIL' else 'amber',
         'message':c.get('message',''),'overlay':c.get('overlay')} for c in findings]}
    temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(output,indent=2));temp.replace(dest)
    return output

class Handler(BaseHTTPRequestHandler):
    def reply(self,status,data):
        body=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path=='/health':return self.reply(200,{'ok':True,'service':'MissionPCB review','post':'/review'})
        return self.reply(404,{'error':'Not found'})
    def do_POST(self):
        if self.path!='/review':return self.reply(404,{'error':'Not found'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,{'error':'application/json required'})
        # No CORS: call from the teammate backend, not an arbitrary website.
        if self.headers.get('Origin'):return self.reply(403,{'error':'Use your backend to submit this request'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=2_000_000:raise ValueError('Body must be 1 byte to 2 MB')
            payload=json.loads(self.rfile.read(size),parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Non-finite number')))
            self.reply(200,evaluate(payload))
        except FileExistsError as e:self.reply(409,{'error':str(e)})
        except Exception as e:self.reply(422,{'error':str(e)})
    def log_message(self,*args):pass
if __name__=='__main__':HTTPServer(('127.0.0.1',8769),Handler).serve_forever()
