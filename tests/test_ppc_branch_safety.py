"""Regression for PowerPC BC (BD16) -> B (LI26) widening incident."""
import json
from pathlib import Path
import pytest
from sapera.cli import _reject_malformed_ppc_conditional_widening, load_db


def _relative_target(address: int, instruction: int) -> int:
    opcode = instruction >> 26
    if opcode == 16:
        off, width = instruction & 0xfffc, 16
    elif opcode == 18:
        off, width = instruction & 0x03fffffc, 26
    else:
        raise ValueError('not a PowerPC branch instruction')
    if off & (1 << (width-1)):
        off -= (1 << width)
    return (address + off) & 0xffffffff


def test_conditional_displacement_must_sign_extend():
    addr = 0x010B1F20
    assert _relative_target(addr, 0x4082FEE4) == 0x010B1E04
    assert _relative_target(addr, 0x4800FEE4) == 0x010C1E04
    assert _relative_target(addr, 0x4BFFFEE4) == 0x010B1E04


def test_sapera_rejects_accidental_bc_to_b_widening():
    bad = dict(original='4082FEE4', replacement='4800FEE4')
    with pytest.raises(ValueError, match='sign extension'):
        _reject_malformed_ppc_conditional_widening(bad, 0x010B1F20)
    for good in ['60000000', '4BFFFEE4']:
        _reject_malformed_ppc_conditional_widening(dict(original='4082FEE4',replacement=good),0x010B1F20)


def test_entire_shipped_database_branch_safety():
    db = load_db()
    for b in db['builds'].values():
        for pr in b['profiles'].values():
            for p in pr['patches']:
                _reject_malformed_ppc_conditional_widening(p,int(p['address'],16))


def test_family_b_unsafe_sites_are_repaired():
    db = load_db()
    for b in db['builds'].values():
        if set(b['chds']) & {'a30b02', 'a30c02', 'a45a02'}:
            for pr in b['profiles'].values():
                for p in pr['patches']:
                    if p['role'].endswith('_safe_fallthrough'):
                        assert p['replacement'] == '60000000'
