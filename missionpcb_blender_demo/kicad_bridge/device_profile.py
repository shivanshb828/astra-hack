"""Reviewable wearable geometry inputs extracted conservatively from brief text.

This is an explicit-text parser, not a medical inference or CAD generation service.
The limits below are modeling/input limits, not physiological safety thresholds.
Unknown or conflicting inputs remain unresolved until the engineer chooses them.
"""
import hashlib
import math
import re


SCHEMA_VERSION = 1
MAX_DIMENSION_MM = 2000.0
MAX_WEAR_HOURS = 87600.0
GEOMETRY_FIELDS = ('device_kind', 'mount', 'attachment', 'interior_mm', 'required_wear_hours')
SUPPORTED = {
    'device_kind': ('ecg', 'eeg', 'general'),
    'mount': ('chest', 'head', 'wrist', 'unspecified'),
    'attachment': ('adhesive', 'strap', 'unspecified'),
}
DEFAULTS = {'device_kind': 'general', 'mount': 'unspecified', 'attachment': 'unspecified'}
_NUM = r'(?:\d+(?:\.\d+)?|\.\d+)'
_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
          'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
          'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14}
_DURATION_NUM = rf'(?:{_NUM}|{"|".join(_WORDS)})'
_DIMS = re.compile(
    rf'(?<![\w.-])(?P<length>{_NUM})\s*[x×]\s*(?P<width>{_NUM})\s*[x×]\s*'
    rf'(?P<height>{_NUM})\s*(?P<unit>mm|millimet(?:er|re)s?|cm|centimet(?:er|re)s?)\b',
    re.I,
)
_DURATION = re.compile(
    rf'(?<![\w.])(?P<number>{_DURATION_NUM})\s*[- ]?\s*'
    r'(?P<unit>hours?|hrs?|days?|weeks?)\b', re.I,
)
_PATTERNS = {
    'device_kind': {'ecg': r'\b(?:ECG|EKG|electrocardiogra\w*)\b',
                    'eeg': r'\b(?:EEG|electroencephalogra\w*)\b'},
    'mount': {'chest': r'\b(?:chest|thorax|thoracic|sternum)\b',
              'head': r'\b(?:head|headset|scalp|cranial|brain)\b',
              'wrist': r'\b(?:wrist|wristband)\b'},
    'attachment': {'adhesive': r'\b(?:adhesive|adhesives|adhesively)\b',
                   'strap': r'\b(?:strap|straps|strapped|belt|belts|headband|wristband)\b'},
}


def _number(value, name, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number.')
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f'{name} is outside the supported range.') from exc
    if not math.isfinite(number) or not 0 < number <= maximum:
        raise ValueError(f'{name} must be finite, greater than zero, and at most {maximum:g}.')
    return number


def validate_profile(payload):
    """Return normalized geometry fields for a reviewed profile/override.

    Metadata from extraction is deliberately not copied: old evidence cannot be
    relabeled as support for an engineer's override. The caller records the edit,
    rationale, brief revision and adoption event separately.
    """
    if not isinstance(payload, dict):
        raise ValueError('Device profile must be an object.')
    metadata = {'schema_version', 'status', 'evidence', 'assumptions', 'unresolved', 'provenance'}
    unknown = set(payload) - set(GEOMETRY_FIELDS) - metadata
    if unknown:
        raise ValueError('Unsupported device profile fields: ' + ', '.join(sorted(map(str, unknown))) + '.')
    result = {}
    for field, values in SUPPORTED.items():
        value = payload.get(field, DEFAULTS[field])
        if not isinstance(value, str) or value not in values:
            raise ValueError(f'{field} must be one of: {", ".join(values)}.')
        result[field] = value
    dimensions = payload.get('interior_mm')
    if dimensions is not None:
        if not isinstance(dimensions, dict) or set(dimensions) != {'length', 'width', 'height'}:
            raise ValueError('interior_mm must contain exactly length, width, and height.')
        dimensions = {axis: _number(dimensions[axis], f'interior_mm.{axis}', MAX_DIMENSION_MM)
                      for axis in ('length', 'width', 'height')}
    result['interior_mm'] = dimensions
    duration = payload.get('required_wear_hours')
    result['required_wear_hours'] = (None if duration is None else
                                     _number(duration, 'required_wear_hours', MAX_WEAR_HOURS))
    return result


def _sentence(text, start, end):
    # Decimal points are not sentence boundaries; newlines may wrap PDF text.
    separators = list(re.finditer(r'(?<!\d)[.!?](?!\d)|[;\n]{2,}|;', text))
    left = max((m.end() for m in separators if m.end() <= start), default=0)
    right = min((m.start() for m in separators if m.start() >= end), default=len(text))
    while left < start and text[left].isspace():
        left += 1
    return left, right


def _excluded(text, start):
    """Avoid treating explicitly negated or illustrative alternatives as choices."""
    left, _ = _sentence(text, start, start)
    prefix = text[left:start]
    prefix = re.split(r'[,;]|\b(?:but|instead use|rather use|use instead)\b', prefix, flags=re.I)[-1]
    return bool(re.search(
        r'\b(?:not|no|without|non[- ]?|instead of|rather than|for example|e\.g\.|such as)\b',
        prefix, re.I,
    ))


def _evidence(text, start, end):
    return {'quote': text[start:end], 'start': start, 'end': end}


def extract_profile(text, source='project_brief', revision=None):
    """Propose supported parameters with exact evidence; never invent missing CAD.

    Three explicitly interior dimensions use conventional length × width × height
    order, which is disclosed as an assumption. Device type does not imply mount,
    attachment, size, body registration, fit, or clinical suitability.
    """
    if not isinstance(text, str) or not text.strip() or '\x00' in text or len(text) > 50000:
        raise ValueError('Provide readable brief text between 1 and 50,000 characters.')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('Profile source must be a non-empty string.')
    if revision is not None and (not isinstance(revision, str) or not revision):
        raise ValueError('Brief revision must be a non-empty string.')
    result = validate_profile({})
    evidence = {field: [] for field in GEOMETRY_FIELDS}
    assumptions = []
    unresolved = []

    def unresolved_field(field, reason):
        unresolved.append({'field': field, 'reason': reason})

    for field, choices in _PATTERNS.items():
        found = {}
        for value, pattern in choices.items():
            matches = [m for m in re.finditer(pattern, text, re.I)
                       if not _excluded(text, m.start()) and
                       not re.match(r'[- ]free\b', text[m.end():], re.I)]
            if matches:
                found[value] = matches
                evidence[field].extend(_evidence(text, m.start(), m.end()) for m in matches)
        evidence[field].sort(key=lambda item: item['start'])
        if len(found) == 1:
            result[field] = next(iter(found))
        elif found:
            unresolved_field(field, 'Multiple alternatives are stated: ' + ', '.join(found) + '. Choose one.')
        else:
            unresolved_field(field, 'No explicit supported choice is stated. Confirm before generating the assembly.')

    dimensions = []
    invalid_dimensions = False
    for match in _DIMS.finditer(text):
        start, end = _sentence(text, *match.span())
        sentence = text[start:end]
        if not re.search(r'\b(?:interior|internal|inside|inner|cavity)\b', sentence, re.I):
            continue
        if _excluded(text, match.start()):
            continue
        # A PCB dimension mentioned next to an interior requirement is not a cavity dimension.
        prefix = text[max(start, match.start() - 45):match.start()]
        size_subjects = list(re.finditer(r'\b(?:PCB|board|exterior|outer|interior|internal|inside|inner|cavity)\b',
                                       prefix, re.I))
        if size_subjects and size_subjects[-1].group().lower() in ('pcb', 'board', 'exterior', 'outer'):
            continue
        factor = 10. if match['unit'].lower().startswith(('cm', 'centim')) else 1.
        value = {axis: float(match[axis]) * factor for axis in ('length', 'width', 'height')}
        evidence['interior_mm'].append(_evidence(text, start, end))
        try:
            dimensions.append(validate_profile({'interior_mm': value})['interior_mm'])
        except ValueError:
            invalid_dimensions = True
    distinct = {tuple(round(item[axis], 9) for axis in ('length', 'width', 'height')) for item in dimensions}
    if len(distinct) == 1 and not invalid_dimensions:
        result['interior_mm'] = dimensions[0]
        assumptions.append('Unlabeled interior dimensions are interpreted as length × width × height; confirm axis order.')
        if any(re.search(r'\b(?:roughly|about|approximate(?:ly)?)\b', item['quote'], re.I)
               for item in evidence['interior_mm']):
            assumptions.append('Interior dimensions are approximate in the brief; they are a proposed modeling target, not a tolerance specification.')
    else:
        reason = ('Interior dimensions conflict or are outside the supported modeling range.'
                  if distinct or invalid_dimensions else 'No explicit interior length × width × height and units are stated.')
        unresolved_field('interior_mm', reason)

    durations = []
    ambiguous_duration = False
    maximum_duration = False
    for match in _DURATION.finditer(text):
        start, end = _sentence(text, *match.span())
        sentence = text[start:end]
        if not re.search(r'\b(?:wear|wearing|worn)\b|continuous (?:use|monitoring)', sentence, re.I):
            continue
        if _excluded(text, match.start()):
            continue
        evidence['required_wear_hours'].append(_evidence(text, start, end))
        if re.search(rf'{_DURATION_NUM}\s*(?:-|–|—|to|or)\s*$', text[start:match.start()], re.I):
            ambiguous_duration = True
        if re.search(r'\b(?:between|at least|minimum)\b', sentence, re.I):
            ambiguous_duration = True
        raw = match['number'].lower()
        number = float(_WORDS[raw]) if raw in _WORDS else float(raw)
        factor = 168. if match['unit'].lower().startswith('week') else 24. if match['unit'].lower().startswith('day') else 1.
        try:
            durations.append(_number(number * factor, 'required_wear_hours', MAX_WEAR_HOURS))
        except ValueError:
            ambiguous_duration = True
        maximum_duration |= bool(re.search(r'\b(?:up to|maximum|at most)\b', sentence, re.I))
    if len(set(durations)) == 1 and not ambiguous_duration:
        result['required_wear_hours'] = durations[0]
        if maximum_duration:
            assumptions.append('The stated maximum wear duration is used as the proposed duration target.')
    else:
        unresolved_field('required_wear_hours', 'Wear duration is conflicting, ranged, or a lower bound; confirm one target.'
                         if ambiguous_duration or durations else 'No explicit wear duration is stated; battery life alone does not establish it.')
    result.update({
        'schema_version': SCHEMA_VERSION,
        'status': 'proposed',
        'evidence': evidence,
        'assumptions': assumptions,
        'unresolved': unresolved,
        'provenance': {'method': 'explicit_text_rules', 'source': source,
                       'brief_revision': revision or hashlib.sha256(text.encode()).hexdigest()},
    })
    return result
