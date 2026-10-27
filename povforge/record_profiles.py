"""Small named recording profiles; destinations and player identities stay local to tasks."""
import copy

MODES = ('match', 'kill_events', 'kills_deaths', 'duel', 'kills')
FLAGS = ('intro', 'minimap', 'keyboard', 'show_enemies', 'upload', 'check_video')
RATES = (24, 30, 60, 120, 144, 240)


def normalize(row):
    from .reel import ReelItem
    if not isinstance(row, dict):
        raise ValueError('Invalid recording profile.')
    name = row.get('name')
    if (not isinstance(name, str) or not name.strip() or len(name) > 40
            or any(ord(c) < 32 for c in name) or row.get('mode') not in MODES):
        raise ValueError('Use a profile name of 1–40 characters and a supported mode.')
    options = row.get('options', {})
    if not isinstance(options, dict):
        raise ValueError('Invalid profile options.')
    fps = options.get('record_fps', 60)
    if type(fps) is not int or fps not in RATES:
        raise ValueError('Invalid recording frame rate.')
    weapons = list(ReelItem(demo='profile', steamid='profile', round=1,
                            weapons=row.get('weapons', [])).weapons)
    return {'name': name.strip(), 'mode': row['mode'], 'weapons': weapons,
            'options': {'record_fps': fps, **{k: options[k] for k in FLAGS if type(options.get(k)) is bool}}}


def saved(prefs):
    rows = []
    for row in prefs.get('record_profiles', [])[:20] if isinstance(prefs.get('record_profiles'), list) else []:
        try:
            clean = normalize(row)
            if not any(r['name'] == clean['name'] for r in rows):
                rows.append(clean)
        except (ValueError, TypeError):
            continue
    return rows


def save(prefs, name, mode, weapons):
    row = normalize({'name': name, 'mode': mode, 'weapons': weapons,
                     'options': {k: prefs[k] for k in ('record_fps', *FLAGS) if k in prefs}})
    rows = [r for r in saved(prefs) if r['name'] != row['name']]
    if len(rows) >= 20:
        raise ValueError('Keep at most 20 recording profiles.')
    prefs['record_profiles'] = rows + [row]
    return row


def apply(prefs, name):
    row = next((r for r in saved(prefs) if r['name'] == name), None)
    if row is None:
        raise ValueError('Recording profile not found.')
    prefs.update(copy.deepcopy(row['options']))
    return row


def remove(prefs, name):
    prefs['record_profiles'] = [r for r in saved(prefs) if r['name'] != name]
