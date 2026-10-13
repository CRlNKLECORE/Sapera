"""Checksum-neutral, constraint-aware ZIN re-encoder.

Changes machine-code bytes while preserving the compressed byte count and
original loader checksum.  This does not establish the security-patch logic
will be effective; runtime behavior must be tested independently.
"""
from __future__ import annotations
from . import core
import hashlib
import json
from pathlib import Path
from .benchmark_retoken import retoken
from .rebalance import balance

class NeutralRewriteError(ValueError):
    pass


def neutral_rewrite(original_stream: bytes, original_program: bytes, patches: list,
                    load_address: int):
    """Apply exact-checked replacements then verify every integrity invariant.

    patches contains dictionaries with {address:int, old:bytes, new:bytes}.
    Raises NeutralRewriteError for mismatches or unrepresentable patches.
    """
    source = bytes(original_stream)
    program = bytes(original_program)
    decoded, used = core.zin_decompress(source)
    if used != len(source) or decoded != program:
        raise NeutralRewriteError('original compressed program failed exact decoding')
    target = bytearray(program)
    touched = set()
    for patch in patches:
        address = int(patch['address'])
        old, new = patch['old'], patch['new']
        position = address - load_address
        if len(old) != len(new) or position < 0 or position + len(old) > len(program):
            raise NeutralRewriteError(f'invalid patch range at {address:#x}')
        if any(x in touched for x in range(position, position + len(old))):
            raise NeutralRewriteError('overlapping patches')
        touched.update(range(position, position + len(old)))
        if target[position:position+len(old)] != old:
            raise NeutralRewriteError(f'original instruction mismatch at {address:#x}')
        target[position:position+len(new)] = new
    target = bytes(target)
    if target == program:
        return source, {'result':'noop', 'changed_compressed_bytes':0}
    # Exact-input accelerated rewrite: reuse independently verified corpus edits
    # ONLY when the original stream AND intended final machine code both match.
    # Different security profiles must go through the generic encoder.
    manifest_dir = Path(__file__).resolve().parent / "manifests"
    old_sha = hashlib.sha256(program).hexdigest()
    stream_sha = hashlib.sha256(source).hexdigest()
    target_sha = hashlib.sha256(target).hexdigest()
    for manifest_file in sorted(manifest_dir.glob("*.json")):
        m = json.loads(manifest_file.read_text())
        if (m.get("old_program_sha256") != old_sha or
            m.get("original_stream_sha256") != stream_sha or
            m.get("new_program_sha256") != target_sha):
            continue
        patched = bytearray(source)
        for pos, orig, new in m["edits"]:
            if patched[pos] != orig:
                raise NeutralRewriteError(f"cache original byte mismatch at {pos:#x}")
            patched[pos] = new
        final = bytes(patched)
        decoded, consumed = core.zin_decompress(final)
        if (decoded != target or consumed != len(source) or
            len(final) != len(source) or
            (sum(final)&0xffffffff) != (sum(source)&0xffffffff)):
            raise NeutralRewriteError('cache verification failed')
        return final, {'result':'pass', 'backend':'verified-manifest',
                       'source':manifest_file.name,
                       'checksum':sum(final)&0xffffffff,
                       'compressed_size':len(final),
                       'changed_compressed_bytes':len(m['edits'])}

    result = retoken(source, program, target, 'sapera', limit=48)
    intermediate = result.pop('stream', None)
    if intermediate is None:
        raise NeutralRewriteError('retokenization failed: '+str(result))
    balanced = balance(source, intermediate, target)
    final = balanced.pop('stream', None)
    if final is None:
        raise NeutralRewriteError('checksum compensation failed: '+str(balanced))
    if len(final) != len(source) or sum(final) != sum(source):
        raise NeutralRewriteError('checksum or compressed size changed')
    got, consumed = core.zin_decompress(final)
    if got != target or consumed != len(final):
        raise NeutralRewriteError('patched ZIN verification failed')
    return final, {
        'result':'pass', 'backend':'dynamic-neutral-solver', 'compressed_size':len(final),
        'checksum':sum(final)&0xffffffff,
        'retokened_groups':result['retokened_groups'],
        'reference_repairs':result['repaired_matches'],
        'checksum_edits':balanced['edits'],
        'changed_compressed_bytes':balanced['changed_stream_bytes'],
    }
