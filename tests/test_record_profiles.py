import pytest


def test_profiles_keep_options_but_never_destinations_or_players():
    from povforge import record_profiles as profiles
    prefs={'output':'private','player_folders':{'a':{'path':'private'}},'record_fps':120,'intro':False,'minimap':True}
    profiles.save(prefs,'AWP 120','kill_events',['weapon_awp','awp'])
    row=prefs['record_profiles'][0]
    assert row['weapons']==['awp'] and row['options']['record_fps']==120
    assert 'output' not in row['options'] and 'player_folders' not in row['options']
    prefs['record_fps']=60; prefs['output']='current'
    selected=profiles.apply(prefs,'AWP 120')
    assert prefs['record_fps']==120 and prefs['output']=='current'
    assert selected['mode']=='kill_events' and selected['weapons']==['awp']


def test_profile_validation_replacement_and_removal():
    from povforge import record_profiles as profiles
    prefs={}
    for name,mode,weapons in [('', 'match',[]),('x','unknown',[]),('x','kills',['../bad'])]:
        with pytest.raises(ValueError): profiles.save(prefs,name,mode,weapons)
    profiles.save(prefs,'My profile','match',[])
    prefs['record_fps']=30
    profiles.save(prefs,'My profile','kills_deaths',[])
    assert len(prefs['record_profiles'])==1
    assert profiles.apply(prefs,'My profile')['mode']=='kills_deaths'
    profiles.remove(prefs,'My profile')
    assert prefs['record_profiles']==[]
    with pytest.raises(ValueError): profiles.apply(prefs,'missing')
