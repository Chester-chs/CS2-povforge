import json


def test_report_redacts_secrets_paths_ids_and_names(tmp_path):
    from povforge import diagnostics
    raw={'state':'error','kind':'reel','stage':'record','player':'PrivatePlayer',
         'error':r'Failed C:\Users\Chester\secret.dem',
         'lines':['api_key=very-private-key','Authorization: Bearer secret','sk-proj-private',
                  'Player 76561198000000000 PrivatePlayer','mail user@example.com',
                  'Download https://example.com/private?token=abc','Composing 1/4']}
    report=diagnostics.build('test',{'record_fps':60,'output':'private'}, {'ffmpeg':'private/path'},raw)
    text=json.dumps(report)
    for private in ('Chester','secret.dem','very-private-key','Bearer secret','sk-proj-private',
                    '76561198000000000','PrivatePlayer','user@example.com','token=abc','private/path'):
        assert private not in text
    assert 'Composing 1/4' in text and report['components']['ffmpeg'] is True
    path=diagnostics.write(tmp_path,report)
    assert json.loads(path.read_text(encoding='utf-8'))==report
    assert diagnostics.write(tmp_path,report)!=path
