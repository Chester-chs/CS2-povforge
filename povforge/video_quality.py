"""Bounded, optional local sample checks. Findings never delete or alter a movie."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import threading
import time

_store_lock = threading.Lock()
MAX_BYTES = 4 * 1024**2


def metadata(data):
    streams = data.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if video is None:
        raise ValueError('No video stream.')
    duration = float(video.get('duration') or data.get('format', {}).get('duration') or 0)
    width, height = int(video.get('width', 0)), int(video.get('height', 0))
    if not math.isfinite(duration) or not 0 < duration <= 86400 or not 0 < width <= 16384 or not 0 < height <= 16384:
        raise ValueError('Invalid video metadata.')
    try:
        a, b = str(video.get('avg_frame_rate', '0/1')).split('/')
        fps = float(a) / float(b)
        if not math.isfinite(fps) or not 0 < fps <= 1000: fps = None
    except (ValueError, ZeroDivisionError):
        fps = None
    return {'duration': duration, 'width': width, 'height': height, 'fps': fps,
            'audio': any(s.get('codec_type') == 'audio' for s in streams)}


def sample_windows(duration):
    if duration <= 45:
        return [(0, duration)]
    return [(0, 15), ((duration-15)/2, 15), (duration-15, 15)]


def detections(text, offset, length):
    issues = []
    for match in re.finditer(r'black_start:([\d.]+)\s+black_end:([\d.]+)', text):
        issues.append({'kind':'black','at':offset+float(match[1]),'end':offset+min(length,float(match[2]))})
    starts = re.findall(r'freeze_start:\s*([\d.]+)', text)
    ends = re.findall(r'freeze_end:\s*([\d.]+)', text)
    for i, start in enumerate(starts):
        issues.append({'kind':'freeze','at':offset+float(start),
                       'end':offset+min(length,float(ends[i]) if i < len(ends) else length)})
    return sorted(issues, key=lambda r: (r['at'], r['kind']))


def _run(args, timeout, owner=None):
    # Temporary files bound Python memory even when a decoder emits repeated errors.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            if owner is not None:
                with owner.lock:
                    if owner.closed: raise RuntimeError('Check cancelled.')
                    owner.proc = proc
            code = proc.wait(timeout=timeout)
            out.seek(0); err.seek(0)
            result = (out.read(1024*1024).decode('utf-8','replace'), err.read(256*1024).decode('utf-8','replace'))
            if code: raise ValueError('Video could not be decoded.')
            return result
        finally:
            if proc.poll() is None:
                proc.kill(); proc.wait(timeout=5)
            if owner is not None:
                with owner.lock:
                    if owner.proc is proc: owner.proc = None


def check(path, *, ffmpeg=None, owner=None):
    from .tools import find_ffmpeg
    from .media import ffprobe_for
    ffmpeg = ffmpeg or find_ffmpeg()
    if not ffmpeg: return {'state':'unavailable','issues':[], 'reason':'missing_tools'}
    try:
        out, _ = _run([ffprobe_for(ffmpeg), '-v','error','-show_entries',
            'format=duration:stream=codec_type,width,height,duration,avg_frame_rate','-of','json',str(path)], 10, owner)
        info = metadata(json.loads(out))
        issues = [] if info['audio'] else [{'kind':'no_audio','at':0,'end':0}]
        windows = sample_windows(info['duration'])
        for start, span in windows:
            _, log = _run([str(ffmpeg),'-nostdin','-hide_banner','-v','info','-ss',str(start),'-i',str(path),
                '-t',str(span),'-an','-sn','-dn','-map','0:v:0','-vf',
                'scale=320:-2,fps=5,blackdetect=d=2:pix_th=0.10,freezedetect=n=-50dB:d=3',
                '-f','null','-'], 45, owner)
            issues.extend(detections(log, start, span))
        return {**info, 'state':'warning' if issues else 'ok', 'issues':issues[:100],
                'sampled':info['duration']>45,'checked_seconds':sum(s for _,s in windows)}
    except subprocess.TimeoutExpired:
        return {'state':'unavailable','issues':[],'reason':'timeout'}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return {'state':'error','issues':[],'reason':'decode_failed'}


def _load(root):
    try:
        file = Path(root)/'quality.json'
        if file.stat().st_size > MAX_BYTES: return {}
        data = json.loads(file.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) and len(data) <= 2000 else {}
    except (OSError, ValueError): return {}


def _key(path):
    return os.path.normcase(str(Path(path).resolve()))


def read(root, path, *, data=None):
    try:
        row = (data if data is not None else _load(root)).get(_key(path))
        st = Path(path).stat()
        if (isinstance(row, dict) and row.get('size')==st.st_size and row.get('mtime_ns')==st.st_mtime_ns
                and isinstance(row.get('report'), dict)):
            return row['report']
    except (OSError, ValueError, TypeError): pass
    return None


def save(root, path, report, *, stamp=None):
    root = Path(root)
    st = Path(path).stat()
    if stamp is not None and stamp != (st.st_size, st.st_mtime_ns): return
    with _store_lock:
        data = _load(root)
        key = _key(path); data.pop(key, None)
        data[key] = {'size':st.st_size,'mtime_ns':st.st_mtime_ns,'report':report}
        while len(data)>2000: data.pop(next(iter(data)))
        body = json.dumps(data, ensure_ascii=False, allow_nan=False)
        while len(body.encode('utf-8'))>MAX_BYTES and len(data)>1:
            data.pop(next(iter(data)));body=json.dumps(data,ensure_ascii=False,allow_nan=False)
        root.mkdir(parents=True,exist_ok=True)
        temp = root/('quality-'+secrets.token_hex(8)+'.tmp')
        try:
            temp.write_text(body,encoding='utf-8');temp.replace(root/'quality.json')
        finally: temp.unlink(missing_ok=True)


class Manager:
    def __init__(self, root, on_idle=lambda:None):
        self.root, self.on_idle = Path(root), on_idle
        self.lock = threading.Lock()
        self.pending = []
        self.active = ''
        self.closed = False
        self.proc = None
        self.worker = None

    @property
    def busy(self):
        with self.lock: return bool(self.active or self.pending)

    def status(self, path):
        with self.lock:
            return {'state':'checking','issues':[]} if _key(path) in [self.active,*self.pending] else None

    def submit(self, path):
        key = _key(path)
        with self.lock:
            if self.closed or key in [self.active,*self.pending] or len(self.pending)>=8: return False
            self.pending.append(key)
            if self.worker is None:
                self.worker=threading.Thread(target=self._work,daemon=True)
                self.worker.start()
        return True

    def _work(self):
        while True:
            with self.lock:
                if self.closed or not self.pending:
                    self.active='';self.worker=None
                    break
                path=self.pending.pop(0);self.active=path
            try:
                st=Path(path).stat();stamp=(st.st_size,st.st_mtime_ns)
                report=check(path,owner=self)
                save(self.root,path,report,stamp=stamp)
            except (OSError, ValueError, TypeError):
                pass
        if not self.closed: self.on_idle()

    def close(self):
        with self.lock:
            self.closed=True;self.pending.clear();proc=self.proc
        if proc and proc.poll() is None:
            try: proc.kill()
            except OSError: pass
        if self.worker: self.worker.join(6)

