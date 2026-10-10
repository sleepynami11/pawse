"""Private, single-user voice selection. Never read by a public demo."""
import json
import os
import tempfile
from pathlib import Path
from . import public


def path():
    return Path(os.getenv('PAWSE_VOICE_PROFILE_PATH') or Path(__file__).resolve().parent.parent / '.pawse-private' / 'voice.json')


def read():
    if public.enabled():
        return {}
    try:
        value = json.loads(path().read_text())
        return value if isinstance(value, dict) and value.get('approved') is True else {}
    except FileNotFoundError:
        return {}


def write(state):
    if public.enabled() or not state.get('approved'):
        return
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(dir=target.parent, prefix='.voice-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target)  # Atomic replacement; mkstemp creates mode 0600.
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def clear():
    if not public.enabled():
        path().unlink(missing_ok=True)
