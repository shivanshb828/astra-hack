"""KiCad project package exchange. Incoming files are staged, never auto-applied."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'missionpcb_kicad'
EXCHANGE=Path(__file__).parent/'exchange'
def sha(data):return hashlib.sha256(data).hexdigest()
def prepare(revision, metadata=None):
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',revision):raise ValueError('Invalid revision')
 target=EXCHANGE/revision
 if target.exists():raise ValueError('Revision already exists; choose another')
 files={}
 for name in ('MissionPCB.kicad_pcb','MissionPCB.kicad_pro','MissionPCB.kicad_sch','MissionPCB.kicad_dru','fp-lib-table','sym-lib-table'):
  path=PROJECT/name
  if path.exists():files['project/'+name]=path.read_bytes()
 for directory in ('models','footprints','symbols'):
  for path in (PROJECT/directory).rglob('*'):
   if path.is_file() and not path.is_symlink():files['project/'+path.relative_to(PROJECT).as_posix()]=path.read_bytes()
 board=files['project/MissionPCB.kicad_pcb']
 for model in re.findall(r'\(model\s+"([^"]+)"',board.decode()):
  prefix='${KIPRJMOD}/'
  if not model.startswith(prefix) or 'project/'+model[len(prefix):] not in files:raise ValueError('Unbundled model dependency: '+model)
 brief={'product':'Single-lead ECG chest patch','review_scope':'Review supplied placement and declared constraints; preserve all electrical content.',
  'limitations':['Six core components only; no complete schematic or routing.','U2 and U4 use approximate package models.','Thermal/noise distance thresholds are proxies, not solved physics.'],
  'requested_review':['mechanical fit','component separation','analog/noise proximity','antenna keep-out','patient-contact and battery concerns; mark missing inputs explicitly']}
 files['brief.json']=json.dumps(brief,indent=2).encode()
 if metadata is not None:
  files['engineering.json']=json.dumps(metadata,indent=2,allow_nan=False).encode()
  files['parts.json']=(Path(__file__).parent/'native-six-parts.json').read_bytes()
 manifest={'schema':'missionpcb-project-review/1','revision':revision,'board':'project/MissionPCB.kicad_pcb','files':{k:sha(v) for k,v in files.items()},'schematic_present':'project/MissionPCB.kicad_sch' in files,
  'return_contract':'Preserve manifest.json. Return same project files with annotations on Cmts.User only, and findings.json. Do not change placement, connectivity, models, or other files.'}
 files['manifest.json']=json.dumps(manifest,indent=2).encode()
 target.mkdir(parents=True)
 for name,data in files.items():
  p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 out=target.with_suffix('.zip')
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in files.items():z.writestr(name,data)
 return out

def tokens(text):return re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text)
def without_review(text):
 ts=tokens(text);out=[];i=0
 while i<len(ts):
  if ts[i]=='(' and i+1<len(ts) and ts[i+1] in ('gr_text','gr_line','gr_rect','gr_circle','gr_poly'):
   depth=0;j=i
   while j<len(ts):
    depth+=(ts[j]=='(')-(ts[j]==')');j+=1
    if depth==0:break
   block=ts[i:j]
   if block[1]=='gr_text' and len(block)>2 and block[2].startswith('"MissionPCB review: ') and any(block[k:k+4]==['(','layer','"Cmts.User"',')'] for k in range(len(block)-3)):
    i=j;continue
  out.append(ts[i]);i+=1
 return out

def receive(archive):
 with zipfile.ZipFile(archive) as z:
  names=z.namelist()
  if len(names)>500 or len(set(names))!=len(names):raise ValueError('Too many or duplicate ZIP entries')
  if sum(i.file_size for i in z.infolist())>100_000_000:raise ValueError('Package exceeds100MB')
  for n in names:
   p=PurePosixPath(n)
   if p.is_absolute() or '..' in p.parts or '\\' in n:raise ValueError('Unsafe ZIP path')
  data={n:z.read(n) for n in names if not n.endswith('/')}
 m=json.loads(data['manifest.json']);rev=m.get('revision','')
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',rev):raise ValueError('Invalid revision')
 base=EXCHANGE/rev;original=json.loads((base/'manifest.json').read_text())
 if m!=original:raise ValueError('Manifest differs from our original submission')
 allowed=set(m['files'])|{'manifest.json','findings.json'}
 if set(data)!=allowed:raise ValueError('Return exactly the submitted files plus findings.json')
 board=m['board']
 for name,digest in m['files'].items():
  if name!=board and sha(data[name])!=digest:raise ValueError('Changed dependency: '+name)
  if name.startswith('project/'):
   local=PROJECT/name.removeprefix('project/')
   if not local.exists() or sha(local.read_bytes())!=digest:raise ValueError('Local project changed since submission: '+name)
 if without_review(data[board].decode())!=without_review((base/board).read_text()):raise ValueError('Returned board changes more than Cmts.User review drawings')
 findings=json.loads(data['findings.json'])
 if findings.get('revision')!=rev or not isinstance(findings.get('findings'),list):raise ValueError('findings.json requires matching revision and findings array')
 dest=EXCHANGE/(rev+'-reviewed')
 if dest.exists():raise ValueError('Review already staged')
 dest.mkdir()
 for name,content in data.items():
  path=dest/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
 return dest/board
if __name__=='__main__':
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
 sub.add_parser('prepare').add_argument('revision');sub.add_parser('receive').add_argument('zip')
 a=p.parse_args();print(prepare(a.revision) if a.action=='prepare' else receive(a.zip))
