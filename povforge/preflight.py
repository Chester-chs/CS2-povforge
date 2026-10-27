"""Read-only environment checks and disposable write probes in selected destinations."""
from pathlib import Path
import shutil
import tempfile

MIN_FREE = 512 * 1024**2


def probe_write(folder):
    with tempfile.TemporaryFile(prefix='.povforge-check-', dir=folder) as stream:
        stream.write(b'povforge')
        stream.flush()


def storage(paths):
    rows = []
    for key, value in paths.items():
        row = {'key': key, 'state': 'ok', 'reason': 'ready', 'free_bytes': None}
        try:
            target = Path(value).resolve()
            while not target.exists() and target != target.parent:
                target = target.parent
            if not target.is_dir():
                row.update(state='error', reason='not_directory')
            else:
                probe_write(target)
                row['free_bytes'] = shutil.disk_usage(target).free
                if row['free_bytes'] < MIN_FREE:
                    row.update(state='error', reason='low_space')
                elif row['free_bytes'] < 8 * 1024**3:
                    row.update(state='warning', reason='space_reserve')
        except (OSError, ValueError, TypeError):
            row.update(state='error', reason='not_writable')
        rows.append(row)
    return rows


def environment(status):
    rows = [{'key': key, 'state': 'ok' if status.get(key) else 'error',
             'reason': 'ready' if status.get(key) else 'missing'}
            for key in ('windows', 'cs2', 'hlae', 'ffmpeg', 'steam_running')]
    for key in ('anticheat', 'cs2_running', 'settings_pending', 'installing'):
        rows.append({'key': key, 'state': 'error' if status.get(key) else 'ok',
                     'reason': key if status.get(key) else 'ready'})
    if status.get('problems'):
        rows.append({'key': 'environment', 'state': 'warning', 'reason': 'detection_incomplete'})
    return rows
