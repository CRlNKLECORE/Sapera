#!/usr/bin/env python3
"""Sapera v1.0.0: exact-build recovery patcher for Konami Viper arcade media.

Sapera identifies the decompressed program by SHA-256, selects an exact
per-build recovery profile, verifies every expected PowerPC word before
writing, and round-trip verifies the rebuilt compressed resource. Unknown
builds are never modified automatically.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import tempfile
from collections import Counter
from pathlib import Path

from . import core

VERSION = "1.0.0"
ALLOWED_PROFILE_STATUSES = {
    "runtime_verified",
    "family_transferred",
    "static_candidate",
    "native_recovery_candidate",
    "known_incomplete",
    "runtime_advanced",
}
HEX32 = re.compile(r"^[0-9a-fA-F]{8}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_db() -> dict:
    p = Path(__file__).with_name("builds.json")
    db = json.loads(p.read_text(encoding="utf-8"))
    validate_db(db)
    return db



def _reject_malformed_ppc_conditional_widening(patch: dict, address: int) -> None:
    """Reject the BC->B sign-extension error found in archived Family B profiles.

    PPC conditional BD uses a signed 16-bit displacement; unconditional LI
    uses a signed 26-bit displacement. Copying a negative BD verbatim into
    an unconditional B creates a +0x10000 jump. Legitimate intentional
    redirections require an explicit `allow_branch_retarget` marker.
    """
    original = int(patch["original"], 16)
    replacement = int(patch["replacement"], 16)
    if (original >> 26) != 16 or (replacement >> 26) != 18:
        return
    displacement = original & 0xFFFC
    conditional_negative = (displacement & 0x8000) != 0
    copied_low_bits = (replacement & 0xFFFC) == displacement
    not_extended = (replacement & 0x3F0000) == 0
    if (conditional_negative and copied_low_bits and not_extended
            and not patch.get("allow_branch_retarget", False)):
        raise ValueError(
            f"suspected unsafe BC->B sign extension at {address:#010x}: "
            f"{original:08x}->{replacement:08x} shifts branch target by +0x10000"
        )


def validate_db(db: dict) -> None:
    if not isinstance(db, dict) or not isinstance(db.get("builds"), dict):
        raise ValueError("database must contain a builds object")
    seen_chds: dict[str, str] = {}
    for h, build in db["builds"].items():
        if not SHA256_RE.fullmatch(h):
            raise ValueError(f"invalid build SHA256 key: {h!r}")
        if build.get("program_sha256") != h:
            raise ValueError(f"program_sha256 mismatch for {h}")
        int(build["load_address"], 16)
        profiles = build.get("profiles") or {}
        if not profiles:
            raise ValueError(f"build {h} has no profiles")
        default = build.get("default_profile")
        if default not in profiles:
            raise ValueError(f"build {h} default_profile {default!r} is not present")
        for chd in build.get("chds", []):
            # Some old inventory aliases intentionally contain slash-separated names.
            if chd in seen_chds and seen_chds[chd] != h:
                raise ValueError(f"CHD alias {chd!r} maps to multiple program hashes")
            seen_chds[chd] = h
        for pname, profile in profiles.items():
            status = profile.get("status")
            if status not in ALLOWED_PROFILE_STATUSES:
                raise ValueError(f"build {h} profile {pname}: invalid status {status!r}")
            patches = profile.get("patches")
            if not isinstance(patches, list) or not patches:
                raise ValueError(f"build {h} profile {pname}: no patches")
            seen_addr = set()
            for patch in patches:
                addr = int(patch["address"], 16)
                if addr & 3:
                    raise ValueError(f"build {h} profile {pname}: unaligned address {addr:#x}")
                if addr in seen_addr:
                    raise ValueError(f"build {h} profile {pname}: duplicate address {addr:#x}")
                seen_addr.add(addr)
                if not HEX32.fullmatch(patch["original"]):
                    raise ValueError(f"build {h} profile {pname}: bad original word")
                if not HEX32.fullmatch(patch["replacement"]):
                    raise ValueError(f"build {h} profile {pname}: bad replacement word")
                _reject_malformed_ppc_conditional_widening(patch, addr)


def select_profile(build: dict, requested: str | None):
    profiles = build.get("profiles", {})
    name = requested or build.get("default_profile")
    if name not in profiles:
        raise ValueError(
            f"profile {name!r} is unavailable; choices: "
            + (", ".join(profiles) if profiles else "(none)")
        )
    return name, profiles[name]


def authorize_profile(profile_name: str, profile: dict,
                      allow_unverified: bool, allow_incomplete: bool) -> None:
    status = profile["status"]
    if status == "known_incomplete" and not allow_incomplete:
        raise ValueError(
            f"profile {profile_name!r} is marked known_incomplete; "
            "use --allow-incomplete only for explicit diagnostic testing"
        )
    if status != "runtime_verified" and not allow_unverified:
        raise ValueError(
            f"profile {profile_name!r} is {status}, not runtime_verified; "
            "use --allow-unverified to explicitly opt in"
        )


def extract_program(container: bytes):
    game_bin, binloc = core.pick_bin_from_input(container)
    desc = core.find_prog_descriptor(game_bin)
    stream = game_bin[desc.stream_off:desc.stream_off + desc.comp_size]
    if (sum(stream) & 0xFFFFFFFF) != desc.checksum:
        raise ValueError("game/prog.zin compressed-stream checksum mismatch")
    program, used = core.zin_decompress(stream)
    if len(program) != desc.out_size:
        raise ValueError(
            f"game/prog.zin decompressed size mismatch: "
            f"{len(program):#x} != {desc.out_size:#x}"
        )
    return game_bin, binloc, desc, program, used


def exact_hits(program: bytes, load_addr: int, profile: dict):
    hits = []
    seen = set()
    for p in profile["patches"]:
        va = int(p["address"], 16)
        off = va - load_addr
        if off < 0 or off + 4 > len(program) or off & 3:
            raise ValueError(f"patch address {va:#x} is outside/aligned incorrectly for this program")
        if off in seen:
            raise ValueError(f"duplicate patch site {va:#x} in recipe")
        seen.add(off)
        actual = struct.unpack_from(">I", program, off)[0]
        expected = int(p["original"], 16)
        replacement = int(p["replacement"], 16)
        if actual != expected:
            raise ValueError(
                f"original-word mismatch at {va:#010x}: "
                f"database expects {expected:08x}, program contains {actual:08x}"
            )
        hits.append((p, off, actual, replacement))
    return hits


def patch_container_exact(container: bytes, db: dict, requested_profile: str | None,
                          allow_unverified: bool, allow_incomplete: bool,
                          encoder: str = "neutral"):
    game_bin, binloc, desc, program, _ = extract_program(container)
    h = core.sha256(program)
    build = db["builds"].get(h)
    if build is None:
        raise ValueError(
            f"unknown decompressed program SHA256 {h}; exact-build mode refuses modification"
        )

    profile_name, profile = select_profile(build, requested_profile)
    authorize_profile(profile_name, profile, allow_unverified, allow_incomplete)
    hits = exact_hits(program, desc.load_addr, profile)

    patched_program = bytearray(program)
    for _, off, _, new in hits:
        struct.pack_into(">I", patched_program, off, new)
    patched_program = bytes(patched_program)

    if encoder == "neutral":
        from .neutral import neutral_rewrite
        original_stream = game_bin[desc.stream_off:desc.stream_off + desc.comp_size]
        comp, neutral_report = neutral_rewrite(
            original_stream, program,
            [dict(address=int(meta["address"],16), old=old.to_bytes(4,"big"),
                  new=new.to_bytes(4,"big")) for meta,_,old,new in hits],
            desc.load_addr)
        new_checksum = desc.checksum
        assert len(comp) == desc.comp_size
        assert (sum(comp)&0xffffffff) == desc.checksum
        new_bin = bytearray(game_bin)
        new_bin[desc.stream_off:desc.stream_off + desc.comp_size] = comp
        # Deliberately preserve original compressed length and descriptor checksum.
    elif encoder == "legacy":
        neutral_report = None
        comp = core.zin_compress(patched_program)
        if len(comp) > desc.comp_size:
            raise ValueError(f"patched ZIN too large ({len(comp):#x} > allocation {desc.comp_size:#x})")
        padded = comp + bytes(desc.comp_size - len(comp))
        new_checksum = sum(padded) & 0xFFFFFFFF
        new_bin = bytearray(game_bin)
        new_bin[desc.stream_off:desc.stream_off + desc.comp_size] = padded
        struct.pack_into(">I", new_bin, desc.marker_off + 16, new_checksum)
    else:
        raise ValueError(f"unknown encoder {encoder}")
    verify_stream = bytes(new_bin[desc.stream_off:desc.stream_off + desc.comp_size])
    verify_decoded, verify_used = core.zin_decompress(verify_stream)
    if verify_decoded != patched_program:
        raise AssertionError("modified executable round-trip mismatch")
    if encoder == "neutral":
        if verify_used != desc.comp_size or len(verify_stream) != desc.comp_size:
            raise AssertionError("neutral compressed length / consumed-byte mismatch")
        if (sum(verify_stream)&0xffffffff) != desc.checksum:
            raise AssertionError("neutral checksum mismatch")
    else:
        if verify_used != len(comp) or (sum(verify_stream)&0xffffffff) != new_checksum:
            raise AssertionError("legacy output failed validation")

    if binloc is None:
        final = bytes(new_bin)
    else:
        final = bytearray(container)
        final[binloc.offset:binloc.offset + binloc.size] = new_bin
        final = bytes(final)

    return final, {
        "hash": h,
        "build": build,
        "profile_name": profile_name,
        "profile": profile,
        "load_addr": desc.load_addr,
        "hits": hits,
        "new_checksum": new_checksum,
        "new_compressed_size": len(comp),
        "allocation": desc.comp_size,
        "encoder": encoder,
        "neutral_report": neutral_report,
    }


def print_recipe(rep):
    b = rep["build"]
    p = rep["profile"]
    print("Game:", " / ".join(b["games"]))
    print("CHD aliases:", ", ".join(b["chds"]))
    print("Program SHA256:", rep["hash"])
    print("Build classification:", b["classification"])
    print(f"Profile: {rep['profile_name']} ({p['status']})")
    if p["status"] != "runtime_verified":
        print("WARNING: this profile is NOT runtime verified.")
    print("Load address:", f"{rep['load_addr']:#010x}")
    print("Exact verified recovery sites:")
    for meta, _, old, new in rep["hits"]:
        print(f"  {meta['address']}: {old:08x} -> {new:08x}  [{meta['role']}]")


def identify_container(container: bytes, db: dict, requested_profile: str | None = None):
    _, _, desc, program, _ = extract_program(container)
    h = core.sha256(program)
    build = db["builds"].get(h)
    print("Program SHA256:", h)
    print("Load address:", f"{desc.load_addr:#010x}")
    print("Program size:", len(program))
    if not build:
        print("Exact database: UNKNOWN")
        return
    print("Exact database: recognized")
    print("Game:", " / ".join(build["games"]))
    print("CHD aliases:", ", ".join(build["chds"]))
    print("Build classification:", build["classification"])
    print("Default profile:", build.get("default_profile"))
    for name, profile in build["profiles"].items():
        marker = "*" if name == build.get("default_profile") else " "
        print(f" {marker} {name}: {profile['status']} ({len(profile['patches'])} writes)")
    if requested_profile:
        name, profile = select_profile(build, requested_profile)
        hits = exact_hits(program, desc.load_addr, profile)
        print(f"Requested profile {name!r}: all {len(hits)} original words verified")


def list_builds(db: dict) -> None:
    rows = []
    for h, b in db["builds"].items():
        dp = b["default_profile"]
        status = b["profiles"][dp]["status"]
        rows.append((b["chds"][0], " / ".join(b["games"]), b["classification"], dp, status, h[:12]))
    rows.sort(key=lambda x: x[0].lower())
    print(f"Sapera build database schema {db.get('schema_version')} | {len(rows)} program hashes")
    print(f"{'CHD':<18} {'DEFAULT PROFILE':<20} {'STATUS':<26} GAME")
    print("-" * 110)
    for chd, game, classification, dp, status, hp in rows:
        print(f"{chd:<18} {dp:<20} {status:<26} {game}")
    counts = Counter(b["classification"] for b in db["builds"].values())
    print("\nBuild classifications:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("Special media case: ppp2nd / ParaParaParadise 2nd Mix (HDD layout; no exact prog.zin recipe)")


def _load_input(path: Path):
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    is_chd = path.suffix.lower() == ".chd"
    chdman = core.find_chdman(Path(__file__).resolve().parent) if is_chd else None
    tmp_path = None
    geom = hunk = None
    if is_chd:
        if not chdman:
            raise RuntimeError(
                "CHD input requires chdman.exe/chdman in PATH, current directory, or beside this script"
            )
        geom, hunk = core.chd_info(chdman, path)
        fd, tmp = tempfile.mkstemp(prefix="sapera-", suffix=".raw")
        os.close(fd)
        tmp_path = Path(tmp)
        core.extract_chd(chdman, path, tmp_path)
        src = tmp_path.read_bytes()
    else:
        src = path.read_bytes()
    return path, is_chd, chdman, tmp_path, geom, hunk, src


def process_one(path: Path, args, db):
    path, is_chd, chdman, tmp_path, geom, hunk, src = _load_input(path)
    try:
        print(f"\n=== {path.name} ===")
        if args.identify:
            identify_container(src, db, args.profile)
            return []
        patched, rep = patch_container_exact(
            src, db, args.profile, args.allow_unverified, args.allow_incomplete, args.encoder
        )
        print_recipe(rep)

        if args.print_ram:
            print("\nMAME debugger commands for live-memory validation:")
            for meta, _, _, new in rep["hits"]:
                print(f"do d@{int(meta['address'],16):08x}={new:08x}".lower())
            return []

        if args.dry_run or args.verify_encode:
            print("Validated: hash, exact PowerPC words, and encoded output invariants; no output written.")
            return []

        outputs = []
        output_dir = getattr(args, "output_dir", None)
        if output_dir is not None:
            output_dir = Path(output_dir).expanduser().resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = path.parent
        if is_chd or core.pick_bin_from_input(src)[1] is not None:
            raw_out = core.unique_output(output_dir / (path.stem + "-sapera.raw"))
            raw_out.write_bytes(patched)
            outputs.append(raw_out)
            print("Wrote raw image:", raw_out)
            if is_chd and not args.raw_only:
                chd_out = core.unique_output(output_dir / (path.stem + "-sapera.chd"))
                if core.create_chd(chdman, raw_out, chd_out, geom, hunk):
                    outputs.append(chd_out)
                    print("Wrote recovered CHD copy:", chd_out)
                    print("NOTE: emulators that enforce a known media hash may reject modified images; live-memory validation can be used for testing.")
        else:
            out = core.unique_output(output_dir / (path.stem + "-sapera.bin"))
            out.write_bytes(patched)
            outputs.append(out)
            print("Wrote patched BIN:", out)

        print(f"Encoder: {rep['encoder']}")
        print(f"Recompressed: {rep['new_compressed_size']:#x} / allocation {rep['allocation']:#x}")
        print(f"New compressed checksum: {rep['new_checksum']:#010x}")
        return outputs
    finally:
        if tmp_path:
            try:
                tmp_path.unlink()
            except OSError:
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=f"Sapera {VERSION} - exact-build Viper timekeeper/backup-data recovery patcher")
    ap.add_argument("inputs", nargs="*", type=Path)
    ap.add_argument("--profile", help="exact profile name from the recognized build")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="allow exact recipes that are recognized but not yet runtime-verified")
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="additionally allow profiles explicitly known to be incomplete")
    ap.add_argument("--print-ram", action="store_true",
                    help="verify exact executable/words and print live-memory validation commands only")
    ap.add_argument("--dry-run", action="store_true",
                    help="verify exact executable/profile/original words without producing output")
    ap.add_argument("--identify", action="store_true",
                    help="identify exact program hash and list its profiles; never modifies input")
    ap.add_argument("--list-builds", action="store_true",
                    help="list every exact program hash represented in the bundled database")
    ap.add_argument("--check-db", action="store_true",
                    help="validate database schema/invariants and exit")
    ap.add_argument("--raw-only", action="store_true")
    ap.add_argument("--output-dir", type=Path, help="write copies to this directory")
    ap.add_argument("--encoder", choices=("neutral", "legacy"), default="neutral",
                    help="neutral keeps original compressed size and checksum; legacy rewrites descriptor (default neutral)")
    ap.add_argument("--verify-encode", action="store_true",
                    help="run full selected encoder with all checks, do not write output")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    db = load_db()
    if args.check_db:
        print(f"Database OK: schema {db.get('schema_version')}, {len(db['builds'])} exact program hashes")
        if not args.inputs and not args.list_builds:
            return 0
    if args.list_builds:
        list_builds(db)
        if not args.inputs:
            return 0
    if not args.inputs:
        ap.error("at least one input is required unless --list-builds or --check-db is used")

    failed = 0
    for p in args.inputs:
        try:
            process_one(p, args, db)
        except Exception as e:
            failed += 1
            print(f"\nERROR processing {p}: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
