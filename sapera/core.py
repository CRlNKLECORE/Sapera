"""Low-level media and ZIN helpers for Sapera.

This module intentionally contains no heuristic patch discovery or unknown-build
auto-patching logic. Sapera only writes recipes from its exact-build database.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
import shutil
import struct
import subprocess

MAX_DIST = 0xFFF
MIN_LEN = 3
MAX_LEN = 18
PROG_MARKER = bytes.fromhex("b6b656ef")
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sign_extend(v: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (v ^ sign) - sign


def conditional_to_unconditional(word: int) -> int:
    """Keep a PPC conditional branch's target, but make the branch unconditional."""
    # BC uses a signed 16-bit displacement including the low two zero bits.
    disp = sign_extend(word & 0xFFFC, 16)
    return 0x48000000 | (disp & 0x03FFFFFC)


def zin_decompress(data: bytes) -> tuple[bytes, int]:
    out = bytearray()
    i = 0
    ctrl = 0
    nbits = 0
    while i < len(data):
        if nbits == 0:
            ctrl = data[i]
            i += 1
            nbits = 8
        bit = ctrl & 1
        ctrl >>= 1
        nbits -= 1
        if bit:
            if i >= len(data):
                raise ValueError("truncated ZIN literal")
            out.append(data[i])
            i += 1
        else:
            if i + 1 >= len(data):
                raise ValueError("truncated ZIN match")
            a, b = data[i], data[i + 1]
            i += 2
            dist = ((a & 0xF0) << 4) | b
            length = (a & 0x0F) + 3
            if dist == 0:
                return bytes(out), i
            if dist > len(out):
                raise ValueError(f"invalid ZIN distance {dist:#x}")
            src = len(out) - dist
            for _ in range(length):
                out.append(out[src])
                src += 1
    raise ValueError("ZIN stream has no EOS marker")


def zin_compress(data: bytes, max_candidates: int = 96) -> bytes:
    hist: dict[bytes, deque[int]] = defaultdict(deque)
    n = len(data)

    def prune(dq: deque[int], pos: int) -> None:
        cutoff = pos - MAX_DIST
        while dq and dq[0] < cutoff:
            dq.popleft()

    def addpos(pos: int) -> None:
        if pos + 3 <= n:
            dq = hist[data[pos:pos + 3]]
            prune(dq, pos)
            dq.append(pos)

    def best(pos: int) -> tuple[int, int]:
        if pos + 3 > n:
            return 0, 0
        dq = hist.get(data[pos:pos + 3])
        if not dq:
            return 0, 0
        prune(dq, pos)
        best_len = best_dist = checked = 0
        for q in reversed(dq):
            d = pos - q
            if not 1 <= d <= MAX_DIST:
                continue
            ml = min(MAX_LEN, n - pos)
            l = 3
            while l < ml and data[pos + l] == data[pos + l - d]:
                l += 1
            if l > best_len:
                best_len, best_dist = l, d
            checked += 1
            if l == MAX_LEN or checked >= max_candidates:
                break
        return best_len, best_dist

    toks: list[tuple[int, int, int]] = []
    pos = 0
    while pos < n:
        length, dist = best(pos)
        # Tiny lazy matching improvement.
        if length >= 3 and pos + 1 < n:
            addpos(pos)
            l2, _ = best(pos + 1)
            dq = hist[data[pos:pos + 3]]
            if dq and dq[-1] == pos:
                dq.pop()
            if l2 >= length + 2:
                length = 0
        if length >= 3:
            toks.append((0, dist, length))
            for p in range(pos, pos + length):
                addpos(p)
            pos += length
        else:
            toks.append((1, data[pos], 1))
            addpos(pos)
            pos += 1

    toks.append((0, 0, 3))  # EOS
    out = bytearray()
    for base in range(0, len(toks), 8):
        grp = toks[base:base + 8]
        ctrl = 0
        payload = bytearray()
        for j, (literal, x, length) in enumerate(grp):
            if literal:
                ctrl |= 1 << j
                payload.append(x)
            elif x == 0:
                payload += b"\x00\x00"
            else:
                payload += bytes(((((x >> 8) & 0x0F) << 4) | ((length - 3) & 0x0F), x & 0xFF))
        out.append(ctrl)
        out += payload

    rt, used = zin_decompress(bytes(out))
    if rt != data or used != len(out):
        raise AssertionError("ZIN compressor self-check failed")
    return bytes(out)


@dataclass
class BinLocation:
    name: str
    offset: int
    size: int
    blob: bytes


def fat16_bins(raw: bytes) -> list[BinLocation]:
    if len(raw) < 1024 or raw[510:512] != b"\x55\xaa":
        return []
    entries = []
    # Try all four primary MBR partitions.
    for pi in range(4):
        pe = raw[0x1BE + pi * 16:0x1CE + pi * 16]
        if len(pe) < 16:
            continue
        ptype = pe[4]
        part_lba = struct.unpack_from("<I", pe, 8)[0]
        if not ptype or not part_lba:
            continue
        p = part_lba * 512
        if p + 64 > len(raw):
            continue
        bps = struct.unpack_from("<H", raw, p + 11)[0]
        spc = raw[p + 13]
        rsv = struct.unpack_from("<H", raw, p + 14)[0]
        nf = raw[p + 16]
        rootent = struct.unpack_from("<H", raw, p + 17)[0]
        spf = struct.unpack_from("<H", raw, p + 22)[0]
        if not bps or not spc or not nf or not spf:
            continue
        root_lba = part_lba + rsv + nf * spf
        root_secs = (rootent * 32 + bps - 1) // bps
        data_lba = root_lba + root_secs
        root_off = root_lba * bps
        for i in range(rootent):
            e = raw[root_off + i * 32:root_off + (i + 1) * 32]
            if len(e) < 32 or e[0] == 0:
                break
            if e[0] == 0xE5 or e[11] == 0x0F or (e[11] & 0x08):
                continue
            name = e[:8].decode("ascii", "ignore").rstrip()
            ext = e[8:11].decode("ascii", "ignore").rstrip()
            if ext.upper() != "BIN":
                continue
            cl = struct.unpack_from("<H", e, 26)[0]
            size = struct.unpack_from("<I", e, 28)[0]
            if cl < 2 or not size:
                continue
            off = (data_lba + (cl - 2) * spc) * bps
            if off + size <= len(raw):
                entries.append(BinLocation(f"{name}.{ext}", off, size, raw[off:off + size]))
    return entries


@dataclass
class ProgDescriptor:
    marker_off: int
    flags: int
    comp_size: int
    load_addr: int
    checksum: int
    out_size: int
    stream_off: int


def plausible_descriptor(blob: bytes, off: int) -> tuple[int, int, int, int, int] | None:
    if off + 24 > len(blob):
        return None
    flags, comp, load, csum, outsz = struct.unpack_from(">5I", blob, off + 4)
    if not (0x1000 <= comp <= min(0x02000000, len(blob))):
        return None
    if not (0x1000 <= outsz <= 0x04000000):
        return None
    if load & 3:
        return None
    if not (0x00010000 <= load <= 0x08000000):
        return None
    if not csum:
        return None
    return flags, comp, load, csum, outsz


def locate_stream(blob: bytes, comp_size: int, checksum: int, out_size: int) -> int:
    """Find a compressed resource by additive checksum + successful ZIN output size.

    Viper resources observed so far are sector/subsector aligned near the front of the BIN.
    We scan at 0x20-byte alignment first, then a broader 0x200 alignment fallback.
    """
    def scan(start: int, end: int, step: int) -> list[int]:
        end = min(end, len(blob) - comp_size)
        if end < start:
            return []
        # Align start upward.
        start = ((start + step - 1) // step) * step
        if start > end:
            return []
        cur = sum(blob[start:start + comp_size]) & 0xFFFFFFFF
        hits = []
        off = start
        while True:
            if cur == checksum:
                try:
                    dec, used = zin_decompress(blob[off:off + comp_size])
                    if used <= comp_size and len(dec) == out_size:
                        hits.append(off)
                except Exception:
                    pass
            nxt = off + step
            if nxt > end:
                break
            cur -= sum(blob[off:off + step])
            cur += sum(blob[off + comp_size:off + comp_size + step])
            cur &= 0xFFFFFFFF
            off = nxt
        return hits

    # Fast/high-confidence region used by all three independently reversed titles.
    hits = scan(0x10000, min(0x400000, len(blob)), 0x20)
    if not hits:
        # Broader fallback, still sector aligned to keep runtime sane.
        hits = scan(0, len(blob), 0x200)
    hits = sorted(set(hits))
    if len(hits) != 1:
        raise ValueError(f"could not uniquely locate game/prog.zin stream (candidates={len(hits)}: {[hex(x) for x in hits[:8]]})")
    return hits[0]


def find_prog_descriptor(blob: bytes) -> ProgDescriptor:
    candidates = []
    pos = 0
    while True:
        i = blob.find(PROG_MARKER, pos)
        if i < 0:
            break
        pos = i + 1
        p = plausible_descriptor(blob, i)
        if not p:
            continue
        flags, comp, load, csum, outsz = p
        try:
            stream_off = locate_stream(blob, comp, csum, outsz)
        except Exception:
            continue
        candidates.append(ProgDescriptor(i, flags, comp, load, csum, outsz, stream_off))
    if len(candidates) != 1:
        raise ValueError(f"could not uniquely identify game/prog.zin descriptor (found {len(candidates)})")
    return candidates[0]


def find_chdman(script_dir: Path) -> str | None:
    for name in ("chdman.exe", "chdman"):
        p = shutil.which(name)
        if p:
            return p
        for base in (script_dir, Path.cwd()):
            q = base / name
            if q.exists():
                return str(q)
    return None


def chd_info(chdman: str, path: Path) -> tuple[tuple[int, int, int, int] | None, int | None]:
    r = subprocess.run([chdman, "info", "-i", str(path)], text=True, capture_output=True)
    txt = (r.stdout or "") + "\n" + (r.stderr or "")
    if r.returncode != 0:
        return None, None
    m = re.search(r"CYLS:(\d+),HEADS:(\d+),SECS:(\d+),BPS:(\d+)", txt, re.I)
    geom = tuple(map(int, m.groups())) if m else None
    hm = re.search(r"Hunk Size:\s*([\d,]+)", txt, re.I)
    hunk = int(hm.group(1).replace(",", "")) if hm else None
    return geom, hunk


def extract_chd(chdman: str, path: Path, dest: Path) -> None:
    # mkstemp() creates the destination path before chdman runs.
    # chdman refuses to overwrite an existing file unless -f is supplied.
    r = subprocess.run([chdman, "extractraw", "-f", "-i", str(path), "-o", str(dest)], text=True, capture_output=True)
    if r.returncode:
        raise RuntimeError(f"chdman could not extract {path.name}: {(r.stderr or r.stdout).strip()[-600:]}")


def create_chd(chdman: str, raw: Path, dest: Path, geom: tuple[int, int, int, int] | None, hunk: int | None) -> bool:
    if not geom:
        return False
    c, h, s, bps = geom
    cmd = [chdman, "createhd", "-f", "-i", str(raw), "-o", str(dest), "-chs", f"{c},{h},{s}", "-ss", str(bps)]
    if hunk:
        cmd += ["-hs", str(hunk)]
    r = subprocess.run(cmd, text=True, capture_output=True)
    if r.returncode:
        raise RuntimeError(f"chdman could not rebuild {dest.name}: {(r.stderr or r.stdout).strip()[-600:]}")
    return True


def pick_bin_from_input(data: bytes) -> tuple[bytes, BinLocation | None]:
    # Standalone Viper BIN: identify by game/prog.zin resource marker.
    if PROG_MARKER in data and not fat16_bins(data):
        return data, None
    bins = fat16_bins(data)
    candidates = []
    for ent in bins:
        try:
            desc = find_prog_descriptor(ent.blob)
            candidates.append((ent, desc))
        except Exception:
            pass
    if len(candidates) != 1:
        raise ValueError(f"expected exactly one patchable Viper BIN in disk image, found {len(candidates)}")
    return candidates[0][0].blob, candidates[0][0]


def unique_output(base: Path) -> Path:
    if not base.exists():
        return base
    for i in range(2, 1000):
        p = base.with_name(f"{base.stem}-{i}{base.suffix}")
        if not p.exists():
            return p
    raise RuntimeError("could not choose a unique output filename")


