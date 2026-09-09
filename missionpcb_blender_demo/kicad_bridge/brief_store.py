"""Board-scoped project brief intake. Uploaded text is context, never executable code."""
import hashlib,json,os,subprocess,sys,tempfile,uuid
from pathlib import Path
import bridge,review_journal
ROOT=Path(__file__).resolve().parent
STORAGE=ROOT/'runtime/project-briefs'
CANONICAL_BRIEF=ROOT.parents[1]/'missions/ecg-patch.md'
DEFAULT=CANONICAL_BRIEF.read_text()
MAX_BYTES=5*1024*1024

def path():return STORAGE/(hashlib.sha256(str(bridge.TARGET).encode()).hexdigest()+'.json')
def current():
 if path().exists():return json.loads(path().read_text())
 return {'text':DEFAULT,'filename':'ECG chest patch brief','revision':hashlib.sha256(DEFAULT.encode()).hexdigest(),'source':'missions/ecg-patch.md','interpretation_status':'Existing demo rules; new brief interpretation is not connected to a model.'}

def extract(filename,data):
 if not data or len(data)>MAX_BYTES:raise ValueError('Choose a brief up to 5 MB.')
 ext=Path(filename).suffix.lower()
 if ext in ('.txt','.md'):
  try:text=data.decode('utf-8-sig')
  except UnicodeError as exc:raise ValueError('Use a UTF-8 text file or a PDF.') from exc
 elif ext=='.pdf':
  if not data.startswith(b'%PDF-'):raise ValueError('This is not a valid PDF.')
  runtime=Path(os.environ.get('MISSIONPCB_PDF_PYTHON',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')))
  if not runtime.is_file():runtime=Path(sys.executable)
  with tempfile.TemporaryDirectory() as directory:
   source=Path(directory)/'brief.pdf';source.write_bytes(data)
   result=subprocess.run([str(runtime),str(ROOT/'pdf_brief_text.py'),str(source)],capture_output=True,text=True,timeout=20)
   if result.returncode:raise ValueError('Could not read the PDF text. Use a text-based PDF, or paste the brief.')
   text=result.stdout
 else:raise ValueError('Use PDF, TXT or Markdown, or paste the brief.')
 return validate(text)

def validate(text):
 if not isinstance(text,str) or not text.strip():raise ValueError('The brief has no readable text. Paste the text if the PDF is scanned.')
 if len(text)>50000 or '\x00' in text:raise ValueError('Keep the brief under 50,000 characters.')
 return text.strip()

def save(text,filename,base_revision):
 text=validate(text)
 if base_revision!=current()['revision']:raise ValueError('The brief changed in another window. Reload before saving.')
 name=Path(str(filename)).name[:180] or 'Project brief'
 data={'text':text,'filename':name,'revision':hashlib.sha256(text.encode()).hexdigest(),'source':'Engineer-provided brief','interpretation_status':'Saved for mission interpretation. Existing numeric rules are unchanged; live model interpretation is not connected.'}
 STORAGE.mkdir(parents=True,exist_ok=True)
 temp=path().with_suffix('.'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(data));temp.replace(path())
 review_journal.append_event(str(bridge.TARGET),'brief_saved',{'revision':data['revision'],'filename':name,'text':text,'previous_revision':base_revision})
 return data
