"""Standalone unit checks and optional ROM-backed integration tests."""
import hashlib
import json
import os
from pathlib import Path
from sapera import cli, core
from sapera.neutral import neutral_rewrite, NeutralRewriteError

ROOT = Path(__file__).resolve().parents[1]

def test_manifest_fingerprints_unique():
    paths = sorted((ROOT / 'sapera' / 'manifests').glob('*_ALL.json'))
    assert len(paths) == 28
    for path in paths:
        m = json.loads(path.read_text())
        assert len(m['old_program_sha256']) == 64
        assert len(m['new_program_sha256']) == 64
        assert len(m['edits']) > 0

def test_unknown_build_refused():
    db = cli.load_db()
    assert '0'*64 not in db['builds']

def test_noop_roundtrip():
    original = bytes(range(256))*12
    stream = core.zin_compress(original)
    patched, report = neutral_rewrite(stream, original, [], 0x10000)
    assert patched == stream
    assert report['result'] == 'noop'

def test_wrong_original_rejected():
    original = bytes(range(256))*12
    stream = core.zin_compress(original)
    try:
        neutral_rewrite(stream, original,
                        [{'address':0x10000,'old':b'ABCD','new':b'WXYZ'}],0x10000)
    except NeutralRewriteError as e:
        assert 'mismatch' in str(e)
    else:raise AssertionError('failed to reject an unexpected original instruction')

def test_real_gti_manifest_optional():
    # Supplied CHDs, BIOS and raw disk images are intentionally not bundled.
    fixture = os.environ.get('SAPERA_TEST_GTICLUB2_RAW')
    if not fixture:
        print('SKIP: set SAPERA_TEST_GTICLUB2_RAW to enable ROM-backed test')
        return
    data = Path(fixture).read_bytes()
    patched, report = cli.patch_container_exact(data, cli.load_db(), 'legacy_full', True, False)
    assert report['neutral_report']['backend'] == 'verified-manifest'
    m = json.loads((ROOT/'sapera/manifests/941a02_ALL.json').read_text())
    assert hashlib.sha256(data).hexdigest() != hashlib.sha256(patched).hexdigest()
    off, sz = m['stream_offset'],m['compressed_size']
    assert len(data)==len(patched)
    assert sum(data[off:off+sz])==sum(patched[off:off+sz])

if __name__=='__main__':
    for name, obj in list(globals().items()):
        if name.startswith('test_') and callable(obj):
            obj();print('PASS',name)
