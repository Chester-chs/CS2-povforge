"""Local finished-video catalog. Listing never opens the game or probes files."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time

_lock = threading.RLock()
LIMIT = 2000
EXTENSIONS = {'.mp4', '.mkv', '.mov'}


def read_duration(path):
    try:
        from .tools import find_ffmpeg
        from .media import ffprobe_for
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            return None
        r = subprocess.run([ffprobe_for(ffmpeg), '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', str(path)], capture_output=True, text=True, check=True, timeout=5,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        value = float(r.stdout.strip())
        return value if math.isfinite(value) and value > 0 else None
    except Exception:
        return None


def _read(root):
    try:
        f = Path(root) / 'recordings.json'
        if f.stat().st_size > 8*1024*1024:
            return []
        data = json.loads(f.read_text(encoding='utf-8'))
        rows = []
        for r in data[:LIMIT] if isinstance(data, list) else []:
            if (not isinstance(r, dict) or not isinstance(r.get('path'), str) or '\x00' in r['path']
                or not Path(r['path']).is_absolute()):
                continue
            if any(type(r.get(k)) not in (int,float) or not math.isfinite(r[k]) or r[k]<0 for k in ('mtime','size')):
                continue
            r['name'] = str(r.get('name') or Path(r['path']).stem)
            for k in ('players','maps'):
                r[k] = [v for v in r.get(k,[]) if isinstance(v,str)] if isinstance(r.get(k,[]),list) else []
            rows.append(r)
        return rows
    except (OSError, ValueError):
        return []


def signature(prefs, mode):
    return {'fps': prefs.get('record_fps', 60), 'mode': mode,
            'minimap': bool(prefs.get('minimap')) if mode == 'match' else False,
            'keyboard': bool(prefs.get('keyboard')) if mode == 'match' else False}


def remember(root, item, prefs, elapsed):
    """Best effort only: catalog failures must not turn a finished job into failure."""
    if not item.get('result'):
        return
    try:
        video = Path(item['result']).resolve()
        st = video.stat()
        if not video.is_file() or video.suffix.lower() not in EXTENSIONS:
            return
        sources = item.get('reel') or []
        mode = sources[0].get('mode', 'kills') if item.get('kind') == 'reel' and sources else 'match'
        players = list(dict.fromkeys(s.get('name') or s.get('steamid', '') for s in sources)) if sources else [item.get('name', '')]
        row = {'path': str(video), 'name': item.get('name') or video.stem, 'players': players,
            'maps': [item.get('map') or ''], 'mode': mode, 'mtime': st.st_mtime, 'size': st.st_size,
            'duration': read_duration(video), 'elapsed': max(0, elapsed), 'profile': item.get('_record_profile') or signature(prefs, mode),
            'created': time.time()}
        with _lock:
            data = [row] + [r for r in _read(root) if os.path.normcase(r['path']) != os.path.normcase(str(video))]
            root = Path(root); root.mkdir(parents=True, exist_ok=True)
            temp = root / ('recordings.' + secrets.token_hex(8) + '.tmp')
            try:
                temp.write_text(json.dumps(data[:LIMIT], ensure_ascii=False), encoding='utf-8')
                temp.replace(root / 'recordings.json')
            finally:
                temp.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError):
        return


def list_videos(root, prefs):
    with _lock:
        rows = _read(root)
    seen = {os.path.normcase(r['path']) for r in rows}
    folders = [Path(prefs['output'])] if prefs.get('output') else []
    folders += [Path(e['path']) for e in prefs.get('player_folders', {}).values() if e.get('path')]
    # Only configured folders and their immediate player folders; no work trees,
    # recursive disk scan or symlink/junction traversal.
    scanned = set(); examined = 0
    for base in folders:
        try:
            if base.is_symlink() or getattr(base, 'is_junction', lambda: False)():
                continue
            directories = [base]
            for child in base.iterdir():
                examined += 1
                if examined > 10000: break
                if (child.name not in ('工作文件', '.povforge-work') and child.is_dir()
                    and not child.is_symlink() and not getattr(child, 'is_junction', lambda: False)()):
                    directories.append(child)
            for folder in directories:
                key = str(folder.resolve())
                if key in scanned: continue
                scanned.add(key)
                for f in folder.iterdir():
                    examined += 1
                    if len(rows) >= LIMIT or examined > 10000: break
                    if f.suffix.lower() not in EXTENSIONS or f.is_symlink() or not f.is_file(): continue
                    resolved = str(f.resolve()); key = os.path.normcase(resolved)
                    if key in seen: continue
                    st = f.stat(); seen.add(key)
                    rows.append({'path': resolved, 'name': f.stem, 'players': [], 'maps': [], 'mode': 'unknown',
                        'mtime': st.st_mtime, 'size': st.st_size, 'duration': None, 'elapsed': None})
        except OSError:
            continue
    for row in rows:
        try:
            st = Path(row['path']).stat()
            row['missing'] = not Path(row['path']).is_file()
            if st.st_size != row.get('size') or st.st_mtime != row.get('mtime'):
                row['duration'] = row['elapsed'] = None
            row['size'] = st.st_size
        except OSError:
            row['missing'] = True
    free = None
    try:
        target = Path(prefs['output']).resolve()
        while not target.exists() and target != target.parent: target = target.parent
        free = shutil.disk_usage(target).free
    except (OSError, KeyError):
        pass
    return {'items': sorted(rows, key=lambda r: -r.get('mtime', 0)), 'free_bytes': free}
