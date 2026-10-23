import json

from povforge import hlae


def test_quality_change_preserves_old_takes_without_reusing_them(tmp_path):
    job = tmp_path / 'job'
    (job / 'clips').mkdir(parents=True)
    (job / 'clips' / 'clip_000.mp4').write_bytes(b'old 60 fps take')
    (job / 'plan.json').write_text('analysis stays')
    (job / 'recorded.json').write_text('{"r01": 10}')
    settings = hlae.RecordSettings(width=2560, height=1440, fps=120)
    assert not hlae.quality_matches(job, settings)
    hlae.prepare_quality_cache(job, settings)
    assert not (job / 'clips' / 'clip_000.mp4').exists()
    assert (job / 'plan.json').read_text() == 'analysis stays'
    assert [p.read_bytes() for p in (job / 'previous-quality').rglob('clip_000.mp4')] == [b'old 60 fps take']
    assert hlae.quality_matches(job, settings)
    (job / 'clips').mkdir(exist_ok=True)
    (job / 'clips' / 'clip_000.mp4').write_bytes(b'new take')
    hlae.prepare_quality_cache(job, settings)
    assert (job / 'clips' / 'clip_000.mp4').read_bytes() == b'new take'


def test_legacy_default_quality_remains_reusable(tmp_path):
    assert hlae.quality_matches(tmp_path, hlae.RecordSettings())
    hlae.prepare_quality_cache(tmp_path, hlae.RecordSettings())
    assert json.loads((tmp_path / 'record-quality.json').read_text()) == {'width': 1920, 'height': 1080, 'fps': 60}


def test_corrupt_quality_metadata_is_not_reused(tmp_path):
    (tmp_path / 'record-quality.json').write_text('broken')
    assert not hlae.quality_matches(tmp_path, hlae.RecordSettings())
