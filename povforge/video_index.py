"""Event times in finished videos. Indexes are optional and bound to file identity."""
from __future__ import annotations

import json
import math
import secrets
from pathlib import Path

MAX_BYTES=4*1024*1024


def sidecar(video):
    return Path(str(video)+'.povforge.json')


def _read_json(path,default):
    try:
        if Path(path).stat().st_size>MAX_BYTES: return default
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return default


def clean(rows):
    result=[]
    for e in rows[:10000] if isinstance(rows,list) else []:
        if not isinstance(e,dict) or e.get('kind') not in ('round','kill','death','replay'): continue
        at=e.get('at')
        if type(at) not in (int,float) or not math.isfinite(at) or not 0<=at<=1e7: continue
        row={'at':float(at),'kind':e['kind']}
        if type(e.get('round')) is int and 0<=e['round']<=1000: row['round']=e['round']
        for key in ('player','victim','weapon','map','source'):
            if isinstance(e.get(key),str): row[key]=e[key][:256]
        if type(e.get('headshot')) is bool: row['headshot']=e['headshot']
        result.append(row)
    return sorted(result,key=lambda e:e['at'])


def write(video,events):
    path=sidecar(video); temp=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    try:
        st=Path(video).stat()
        data={'version':1,'size':st.st_size,'mtime_ns':st.st_mtime_ns,'events':clean(events)}
        body=json.dumps(data,ensure_ascii=False,allow_nan=False)
        if len(body.encode('utf-8'))>MAX_BYTES: return
        temp.write_text(body,encoding='utf-8')
        temp.replace(path)
    except (OSError,ValueError,TypeError):
        pass  # A missing index must never discard a valid video.
    finally:
        try: temp.unlink(missing_ok=True)
        except OSError: pass


def read(video):
    data=_read_json(sidecar(video),{})
    try:
        st=Path(video).stat()
        if not isinstance(data,dict) or data.get('version')!=1 or data.get('size')!=st.st_size or data.get('mtime_ns')!=st.st_mtime_ns:
            return []
        return clean(data.get('events'))
    except OSError:
        return []


def relocate(old,new):
    data=_read_json(sidecar(old),{})
    try:
        st=Path(new).stat()
        if isinstance(data,dict) and data.get('version')==1 and data.get('size')==st.st_size and data.get('mtime_ns')==st.st_mtime_ns:
            write(new,data.get('events',[]))
        sidecar(old).unlink(missing_ok=True)
    except OSError:
        pass


def record_events(job,demo,steamid):
    from .demo import event_round_end
    names={p.steamid:p.name for p in demo.players}
    rows=[]
    for r in demo.rounds:
        for d in demo.deaths:
            if not r.freeze_end_tick<=d.tick<event_round_end(demo,r): continue
            if d.attacker_steamid==steamid and d.victim_steamid!=steamid: kind='kill'
            elif d.victim_steamid==steamid: kind='death'
            else: continue
            rows.append({'tick':d.tick,'round':r.number,'kind':kind,'player':names.get(steamid,steamid),
                         'victim':names.get(d.victim_steamid,d.victim_steamid or ''),
                         'weapon':d.weapon or '', 'headshot':bool(d.headshot)})
    try: (Path(job)/'event-index.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
    except OSError: pass


def source_markers(job,plan,round_number):
    from .hlae import actual_starts,clip_id
    seg=next((s for s in plan.segments if s.round_number==round_number),None)
    if seg is None: return []
    start=actual_starts(job).get(clip_id(seg),float(seg.start_tick))
    rows=_read_json(Path(job)/'event-index.json',None)
    if not isinstance(rows,list):
        rows=[{'tick':r[0],'kind':'kill','round':seg.round_number} for r in _read_json(Path(job)/'kills.json',[])
              if isinstance(r,list) and r and type(r[0]) in (int,float) and seg.start_tick<=r[0]<seg.end_tick]
    result=[]
    for row in rows:
        if isinstance(row,dict) and row.get('round')==round_number and type(row.get('tick')) in (int,float):
            result.append({**row,'at':(row['tick']-start)/plan.tickrate,'player':plan.player.name,
                           'map':plan.map_name,'source':Path(plan.demo_path).name})
    return result


class IndexedOrder(list):
    pass


def index_order(order,windows,contexts):
    lookup={}
    for source,spans in windows.items():
        if source not in contexts: continue
        job,plan=contexts[source]
        for span in spans:
            lookup[str(span[0])]=(source_markers(job,plan,source[2]),source[2],plan)
    result=IndexedOrder(order); result.markers=[]
    for clip,a,b,_ in order:
        if str(clip) not in lookup:
            result.markers.append([{'at':0,'kind':'replay'}]);continue
        events,round_number,plan=lookup[str(clip)]
        result.markers.append([{'at':0,'kind':'round','round':round_number,'player':plan.player.name,
                               'map':plan.map_name,'source':Path(plan.demo_path).name}]+
                              [{**e,'at':e['at']-a} for e in events if a<=e['at']<b])
    return result


def flatten(markers,durations,offset=0):
    rows=[];cursor=offset
    for group,duration in zip(markers,durations):
        rows.extend({**e,'at':cursor+e['at']} for e in group if 0<=e['at']<duration)
        cursor+=duration
    return clean(rows)


def effect_events(moments,chosen,fx,sequence,durations,crossings):
    from .effects import mapped,time_map
    rows=[];cursor=0
    for i,((kind,value),duration) in enumerate(zip(sequence,durations)):
        if i: cursor-=crossings[i-1]
        if kind=='moment':
            m=moments[value]
            parts=time_map(m.length,chosen[value],fx['slowmo_speed'] if fx['kill_slowmo'] else None)
            rows.extend({**e,'at':cursor+mapped(e['at'],parts)} for e in m.events if 0<=e['at']<m.length)
        cursor+=duration
    return clean(rows)
