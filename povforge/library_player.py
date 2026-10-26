"""Short-lived opaque handles for already indexed local videos, never arbitrary paths."""
from pathlib import Path
import secrets
import threading
import time


class LibraryPlayer:
    def __init__(self):
        self.lock=threading.Lock()
        self.sessions={}

    def open(self,path,library):
        try:
            target=Path(path).resolve()
            row=next((v for v in library if Path(v['path']).resolve()==target and not v.get('missing')),None)
            if row is None or target.suffix.lower() not in ('.mp4','.mkv','.mov') or not target.is_file(): return None
            st=target.stat();key=secrets.token_urlsafe(24)
            with self.lock:
                self.sessions={k:v for k,v in self.sessions.items() if time.monotonic()-v[3]<7200}
                while len(self.sessions)>=16: self.sessions.pop(next(iter(self.sessions)))
                self.sessions[key]=(target,st.st_size,st.st_mtime_ns,time.monotonic())
            from .video_index import read
            return {'src':'/api/library/video?id='+key,'events':read(target),'name':row.get('name',target.stem)}
        except (OSError,ValueError,TypeError):
            return None

    def get(self,key):
        with self.lock: item=self.sessions.get(key)
        if item is None: return None
        path,size,stamp,created=item
        try:
            st=path.stat()
            if time.monotonic()-created<7200 and path.is_file() and st.st_size==size and st.st_mtime_ns==stamp:
                return path
        except OSError: pass
        with self.lock: self.sessions.pop(key,None)
        return None
