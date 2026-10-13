import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sapera import core
from sapera import cli as patcher

DB = json.loads((ROOT / 'sapera' / 'builds.json').read_text())


def by_chd(name):
    for h, b in DB['builds'].items():
        if name in b.get('chds', []):
            return h, b
    raise KeyError(name)


def test_database_validates():
    patcher.validate_db(DB)
    assert len(DB['builds']) == 27


def test_only_one_runtime_verified_build_profile_default():
    defaults = []
    for h, b in DB['builds'].items():
        p = b['profiles'][b['default_profile']]
        if p['status'] == 'runtime_verified':
            defaults.append((h, b))
    assert len(defaults) == 1
    assert 'a41b02' in defaults[0][1]['chds']


def test_thrill_drive_2_runtime_recipe_is_six_writes():
    h, b = by_chd('a41b02')
    p = b['profiles'][b['default_profile']]
    assert p['status'] == 'runtime_verified'
    got = [(x['address'], x['original'], x['replacement']) for x in p['patches']]
    assert got == [
        ('0x0004CAE4', '40820024', '60000000'),
        ('0x0004CB4C', '40820024', '48000024'),
        ('0x0004CBCC', '41820014', '48000014'),
        ('0x0004CD80', '41820024', '48000024'),
        ('0x0005C2C8', '418200EC', '480000EC'),
        ('0x0005D848', '41820020', '48000020'),
    ]


def test_c22d02_preferred_native_recovery_profile():
    h, b = by_chd('c22d02')
    assert b['default_profile'] == 'erased_u39_preflight'
    assert b['profiles']['erased_u39_preflight']['status'] == 'runtime_advanced'
    assert b['profiles']['erased_u39_preflight']['patches'][0]['address'] == '0x010E4690'
    p = b['profiles']['native_recovery_A']
    assert p['status'] == 'native_recovery_candidate'
    assert [(x['address'],x['original'],x['replacement']) for x in p['patches']] == [
        ('0x010E4690','4086002C','4800002C'),
        ('0x010E48B0','409C1024','48001024'),
    ]
    assert b['profiles']['diagnostic_full']['status'] == 'known_incomplete'
    assert len(b['profiles']['diagnostic_full']['patches']) == 6


def test_c22c02_native_recovery_mapping():
    h, b = by_chd('c22c02')
    p = b['profiles']['native_recovery_A']
    assert [(x['address'],x['original'],x['replacement']) for x in p['patches']] == [
        ('0x010E43EC','4086002C','4800002C'),
        ('0x010E460C','409C1024','48001024'),
    ]


def test_c22a02_does_not_guess_initializer():
    h, b = by_chd('c22a02')
    assert b['default_profile'] == 'erased_u39_preflight'
    assert b['profiles']['erased_u39_preflight']['status'] == 'runtime_advanced'
    assert b['profiles']['erased_u39_preflight']['patches'][0]['address'] == '0x010E0FE8'
    assert 'native_recovery_A' not in b['profiles']
    assert len(b['profiles']['identity_gate']['patches']) == 1


def test_exact_hits_accepts_expected_and_rejects_mismatch():
    load = 0x1000
    program = bytearray(0x40)
    struct.pack_into('>I', program, 0x10, 0x41820024)
    profile = {'patches':[{'address':'0x00001010','original':'41820024','replacement':'48000024'}]}
    hits = patcher.exact_hits(bytes(program), load, profile)
    assert hits[0][2] == 0x41820024
    bad = bytearray(program)
    struct.pack_into('>I', bad, 0x10, 0x60000000)
    try:
        patcher.exact_hits(bytes(bad), load, profile)
    except ValueError as e:
        assert 'original-word mismatch' in str(e)
    else:
        raise AssertionError('mismatch was not rejected')


def test_zin_roundtrip():
    data = (b'Sapera Viper RTC test\x00' * 200) + bytes(range(256)) * 4
    comp = core.zin_compress(data)
    out, used = core.zin_decompress(comp)
    assert out == data
    assert used == len(comp)


if __name__ == '__main__':
    tests = [v for k,v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print('PASS', t.__name__)
        except Exception as e:
            failed += 1
            print('FAIL', t.__name__, repr(e))
    raise SystemExit(1 if failed else 0)
