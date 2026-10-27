"""Bounded, atomic task snapshots. Reading never starts a task."""
import json
import os
from pathlib import Path
import secrets

SETTINGS = ('output','record_res','record_fps','minimap','keyboard','show_enemies',
            'intro','upload','by_player','player_folders')
MAX_BYTES = 8*1024*1024


def settings(prefs):
    return json.loads(json.dumps({k:prefs[k] for k in SETTINGS if k in prefs},allow_nan=False))


def load(path):
    if not path or not Path(path).exists():
        return [], ''
    try:
        if Path(path).stat().st_size > MAX_BYTES:
            raise ValueError('Task snapshot is too large.')
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('version') != 1 or not isinstance(data.get('items'),list) or len(data['items'])>2000:
            raise ValueError('Unsupported task snapshot.')
        from .reel import ReelItem
        ids=set(); items=[]
        for item in data['items']:
            if not isinstance(item,dict) or type(item.get('id')) is not int or item['id']<1 or item['id'] in ids:
                raise ValueError('Invalid task identity.')
            ids.add(item['id'])
            if item.get('kind') not in ('match','reel') or item.get('state') not in ('queued','running','done','error','cancelled'):
                raise ValueError('Invalid task type or state.')
            for key in ('name','path','steamid','map','result','error'):
                if not isinstance(item.get(key,''),str) or len(item.get(key,''))>8192:
                    raise ValueError('Invalid task text.')
            if not isinstance(item.get('rounds'),list) or any(type(r) is not int or not 1<=r<=1000 for r in item['rounds']):
                raise ValueError('Invalid rounds.')
            if item['kind']=='match' and (not item.get('path') or not item.get('steamid')):
                raise ValueError('Missing Demo or player.')
            if item['kind']=='reel':
                rows=item.get('reel')
                if not isinstance(rows,list) or not rows or len(rows)>10000:
                    raise ValueError('Invalid reel.')
                for row in rows:
                    ReelItem(**{k:v for k,v in row.items() if k!='name'})
            if not isinstance(item.get('settings',{}),dict):
                raise ValueError('Invalid recording settings.')
            item['settings']=settings(item.get('settings',{}))
            if item['state']=='running':
                item['state']='queued'
                item['error']=''
            items.append(item)
        return items,''
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return [],'Saved tasks could not be read. The original snapshot was kept.'


def save(path,items):
    if path is None:
        return ''
    path=Path(path); temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    try:
        body=json.dumps({'version':1,'items':items},ensure_ascii=False,allow_nan=False)
        if len(body.encode('utf-8'))>MAX_BYTES or len(items)>2000:
            raise ValueError('Task snapshot is too large.')
        path.parent.mkdir(parents=True,exist_ok=True)
        with temporary.open('w',encoding='utf-8') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        return ''
    except (OSError,ValueError,TypeError):
        return 'Tasks could not be saved. Keep the app open and check free disk space.'
    finally:
        try: temporary.unlink(missing_ok=True)
        except OSError: pass
