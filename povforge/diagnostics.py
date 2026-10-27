"""Explicit local exports with a whitelist and conservative log redaction."""
import json
from pathlib import Path
import re
import secrets
import time


def redact(value, names=()):
    text = str(value)[:2000]
    if re.search(r'(?i)api.?key|authorization|bearer\s|password|secret|token\s*[:=]|\bsk-[a-z]', text):
        return '[sensitive line removed]'
    text = re.sub(r'https?://\S+', '[url]', text, flags=re.I)
    text = re.sub(r'\b\d{17}\b', '[player id]', text)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', '[email]', text)
    text = re.sub(r'(?i)(?:[a-z]:[\\/]|\\\\|(?<!\w)/)[^\r\n]*', '[path]', text)
    for name in sorted({n for n in names if isinstance(n, str) and n}, key=len, reverse=True):
        text = text.replace(name, '[player]')
    return text


def build(version, prefs, setup, job):
    names = [job.get('player', '')]
    names += [v.get('name', '') for v in prefs.get('player_folders', {}).values() if isinstance(v, dict)]
    def allowed(key, values, default):
        return job.get(key) if job.get(key) in values else default
    return {'format': 1, 'app_version': version, 'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'components': {k: bool(setup.get(k)) for k in ('windows', 'cs2', 'hlae', 'ffmpeg',
                            'steam_running', 'cs2_running', 'settings_pending')},
            'anticheat_running': bool(setup.get('anticheat')),
            'recording': {'fps': prefs.get('record_fps', 60), 'resolution': '1080P'},
            'job': {'state': allowed('state', ('idle','running','done','error','cancelled'), 'unknown'),
                    'kind': allowed('kind', ('match','reel'), 'unknown'),
                    'stage': allowed('stage', ('read','record','overlays','intro','compose','extras','cut','done'), ''),
                    'error': redact(job.get('error', ''), names),
                    'recent_log': [redact(line, names) for line in job.get('lines', [])[-60:]]}}


def write(folder, report):
    folder = Path(folder)
    path = folder / ('PovForge-diagnostics-' + time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(4) + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return path
