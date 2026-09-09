"""Extract reviewable numeric targets; never infer regulatory or circuit limits."""
import re

def extract(text):
    candidates=[];ambiguous=[]
    patterns=[
        ('required_runtime_hours',r'\b(\d+(?:\.\d+)?)\s*[- ]?days?\b',24,'Continuous wear target (hours)'),
        ('max_mass_g',r'\b(?:under|below|at most|maximum|max(?:imum)?\s+mass(?:\s+of)?)\s+(\d+(?:\.\d+)?)\s*(?:g|grams?)\b',1,'Maximum total mass (g)'),
    ]
    for key,pattern,factor,label in patterns:
        matches=list(re.finditer(pattern,text,re.I));values={float(m.group(1))*factor for m in matches}
        if len(values)>1:
            ambiguous.append({'field':key,'message':'Multiple values appear in the brief. Enter the intended target explicitly.'})
        elif matches:
            m=matches[0]
            candidates.append({'field':key,'value':next(iter(values)),'label':label,'quote':text[max(0,m.start()-55):min(len(text),m.end()+65)].strip(),'basis':'Explicit brief quantity; review its meaning before adoption.'})
    return {'candidates':candidates,'ambiguous':ambiguous,'limitations':['Internal enclosure dimensions are not treated as external wearable dimensions.','Part selection, circuit connections, biological limits and thermal/noise separation rules require engineering evidence.']}
