"""Isolated, bounded PDF text extraction for local brief intake."""
import sys
from pypdf import PdfReader
reader=PdfReader(sys.argv[1])
if reader.is_encrypted or len(reader.pages)>100:raise ValueError('Use an unencrypted brief of at most 100 pages.')
text='\n\n'.join(page.extract_text() or '' for page in reader.pages)
if len(text)>50000:raise ValueError('Brief is too long.')
print(text)
