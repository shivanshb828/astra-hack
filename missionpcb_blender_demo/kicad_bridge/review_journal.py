"""Board-scoped user comments, component pins, and chronological review events.

This module stores user-authored content as data only. It never executes comments,
changes CAD files, or treats a pinned component as a native KiCad lock. Callers must
render text safely and explicitly enforce pin policy before proposing mutations.
"""
import copy
import fcntl
import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

STORAGE_ROOT = Path(__file__).resolve().parent / 'runtime' / 'review-journal'
_LOCK = threading.RLock()


def _string(value, name, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\x00' in value:
        raise ValueError(f'{name} must be a non-empty string of at most {maximum} characters')
    return value


def _empty():
    return {'comments': [], 'pins': {}, 'events': []}


def _record(**fields):
    return {'id': uuid.uuid4().hex, 'timestamp': datetime.now(timezone.utc).isoformat(), **fields}


@contextmanager
def _store(board):
    board = _string(board, 'board', 4096)
    root = Path(STORAGE_ROOT)
    key = hashlib.sha256(board.encode('utf-8')).hexdigest()
    with _LOCK:
        root.mkdir(parents=True, exist_ok=True)
        with (root / (key + '.lock')).open('a') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                path = root / (key + '.json')
                state = _empty()
                if path.exists():
                    try:
                        state = json.loads(path.read_text(encoding='utf-8'))
                        if (not isinstance(state, dict) or set(state) != {'comments', 'pins', 'events'}
                                or not isinstance(state['comments'], list)
                                or not isinstance(state['pins'], dict)
                                or not isinstance(state['events'], list)):
                            raise ValueError('Unexpected journal structure')
                    except (ValueError, UnicodeError) as exc:
                        raise ValueError('Stored review journal is invalid; preserve it for recovery') from exc
                yield path, state
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _save(path, state):
    data = json.dumps(state, ensure_ascii=False, allow_nan=False, indent=2)
    fd, temporary = tempfile.mkstemp(prefix=path.stem + '-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def get_state(board):
    """Read independent copies of comments, latest pin states, and audit events."""
    with _store(board) as (_, state):
        return copy.deepcopy(state)


def add_comment(board, finding_id, text):
    """Persist exact text against a finding ID and append a comment audit event."""
    finding_id = _string(finding_id, 'finding_id', 256)
    text = _string(text, 'text', 10000)
    comment = _record(finding_id=finding_id, text=text)
    with _store(board) as (path, state):
        state['comments'].append(comment)
        state['events'].append(_record(kind='comment_added', payload={
            'comment_id': comment['id'], 'finding_id': finding_id, 'text': text}))
        _save(path, state)
    return copy.deepcopy(comment)


def set_pin(board, ref, pinned):
    """Record user pin intent; the caller is responsible for enforcing it."""
    ref = _string(ref, 'ref', 64)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', ref):
        raise ValueError('ref must be a component reference such as U2 or J1')
    if type(pinned) is not bool:
        raise ValueError('pinned must be a boolean')
    record = _record(kind='pin_changed', payload={'ref': ref, 'pinned': pinned})
    with _store(board) as (path, state):
        state['pins'][ref] = pinned
        state['events'].append(record)
        _save(path, state)
    return copy.deepcopy(record)


def append_event(board, kind, payload):
    """Append JSON-compatible event details (e.g. before/after design positions)."""
    kind = _string(kind, 'kind', 80)
    if not isinstance(payload, dict):
        raise ValueError('payload must be an object')
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode('utf-8')) > 262144:
            raise ValueError('payload exceeds 256 KiB')
        detached = json.loads(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError('payload must be finite JSON data of at most 256 KiB') from exc
    event = _record(kind=kind, payload=detached)
    with _store(board) as (path, state):
        state['events'].append(event)
        _save(path, state)
    return copy.deepcopy(event)
