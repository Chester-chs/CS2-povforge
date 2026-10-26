import json

from test_gui_security import http_app,session_token


def test_player_streams_only_library_videos_with_opaque_ids_and_ranges(http_app,monkeypatch,tmp_path):
    from povforge import video_index as vi
    from povforge.gui import server
    app,output,authority,request=http_app
    monkeypatch.setenv('POVFORGE_STATE',str(tmp_path/'state'))
    video=output/'clip.mp4';video.write_bytes(b'0123456789')
    vi.write(video,[{'at':1,'kind':'kill','round':2,'weapon':'awp'}])
    headers={'Origin':'http://'+authority,'X-Povforge-Token':session_token(request)}
    body=json.dumps({'path':str(video)})
    assert request('/api/library/play','POST',{},body)[0]==403
    status,payload=request('/api/library/play','POST',headers,body)
    assert status==200
    data=json.loads(payload);src=data['src']
    assert str(video) not in src and data['events'][0]['weapon']=='awp'
    assert request(src,headers={'Range':'bytes=2-5'})==(206,b'2345')
    assert request(src,headers={'Host':'evil.example'})[0]==403
    assert request('/api/library/video?id=guessed')[0]==404
    outside=tmp_path/'outside.mp4';outside.write_bytes(b'private')
    assert request('/api/library/play','POST',headers,json.dumps({'path':str(outside)}))[0]==404
    assert request('/api/library/video?path='+str(outside))[0]==404
    video.write_bytes(b'changed')
    assert request(src)[0]==404
