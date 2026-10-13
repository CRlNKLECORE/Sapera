"""Friendly public CLI. The exact-build engine lives in sapera.cli.

Keep a strict boundary between inspecting media and writing derived copies.
Unknown or incomplete profiles never become silently writable.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import shutil
import sys

from . import __version__, cli, core


EXAMPLES = """examples:
  sapera scan game.chd                 See whether the game is recognized
  sapera list                          List the known builds
  sapera doctor                        Check your installation
  sapera verify game.chd --experimental   Validate a proposed patch (no output)
  sapera repair game.chd --experimental   Write a new copy to ./sapera-output/
  sapera wizard                        Walk through the process interactively

Original media is never overwritten. Experimental means exactly that.
"""


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="sapera", description="Sapera: help keep original Konami Viper cabinets alive.",
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--version", action="version", version=f"Sapera {__version__}")
    sub = ap.add_subparsers(dest="command")
    scan = sub.add_parser("scan", help="identify a game and its available profiles without changing anything")
    scan.add_argument("images", nargs="+", type=Path, metavar="IMAGE")
    verify = sub.add_parser("verify", help="simulate rebuilding a patch and verify it (no output)")
    patch = sub.add_parser("repair", aliases=["patch"], help="create a separately named candidate image for cabinet repair")
    for command in (verify, patch):
        command.add_argument("images", nargs="+", type=Path, metavar="IMAGE")
        command.add_argument("--profile", help="select a specific profile (shown by scan)")
        command.add_argument("--experimental", action="store_true", help="opt in to non-runtime-verified profiles")
        command.add_argument("--allow-incomplete", action="store_true", help="opt in to known-incomplete diagnostic profiles; requires --experimental")
        command.add_argument("--encoder", choices=["neutral", "legacy"], default="neutral", help="neutral preserves the compressed checksum (default)")
    patch.add_argument("--output-dir", type=Path, default=Path.cwd() / "sapera-output", help="destination directory (default: ./sapera-output)")
    patch.add_argument("--raw-only", action="store_true", help="skip CHD rebuilding and keep just the raw copy")
    sub.add_parser("list", help="list all recognized builds and confidence levels")
    sub.add_parser("doctor", help="check Python, the database, and chdman")
    sub.add_parser("wizard", help="start an interactive walkthrough")
    return ap


def _legacy_options(args: argparse.Namespace, mode: str) -> list[str]:
    opts: list[str] = []
    if mode == "scan":
        return ["--identify"]
    if args.profile:
        opts.extend(["--profile", args.profile])
    if args.experimental:
        opts.append("--allow-unverified")
    if args.allow_incomplete:
        if not args.experimental:
            raise ValueError("--allow-incomplete also needs --experimental")
        opts.append("--allow-incomplete")
    if args.encoder != "neutral":
        opts.extend(["--encoder", args.encoder])
    if mode == "verify":
        opts.append("--verify-encode")
    else:
        opts.extend(["--output-dir", str(args.output_dir)])
        if args.raw_only:
            opts.append("--raw-only")
    return opts


def _one_profile(image: Path, db: dict, profile_name: str | None):
    path, _, _, tmp, _, _, src = cli._load_input(image)
    try:
        _, _, desc, program, _ = cli.extract_program(src)
        build = db["builds"].get(core.sha256(program))
        if not build:
            raise ValueError("this build isn't in the exact-match database. I won't guess where to write.")
        if int(build["load_address"], 16) != desc.load_addr:
            raise ValueError("build load address didn't match the database. Refusing to write.")
        name, profile = cli.select_profile(build, profile_name)
        return build, name, profile
    finally:
        if tmp:
            Path(tmp).unlink(missing_ok=True)


def _run_command(args: argparse.Namespace) -> int:
    if args.command in ("list", "doctor"):
        db = cli.load_db()
        if args.command == "list":
            cli.list_builds(db)
            return 0
        counts = Counter(b['profiles'][b['default_profile']]['status'] for b in db['builds'].values())
        chdman = core.find_chdman(Path(__file__).resolve().parent)
        print(f"Sapera {__version__} | Python {sys.version.split()[0]}")
        print(f"Database: OK, {len(db['builds'])} recognized program hashes")
        print("Default profile states: " + ", ".join(f"{k}={v}" for k,v in sorted(counts.items())))
        print(f"CHD support: {'ready (' + chdman + ')' if chdman else 'chdman not found'}")
        print("RAW/BIN support: ready (no external tools required)")
        print("No ROMs, games, BIOS or dongle images are included.")
        if not chdman:
            print("Tip: get chdman from MAME and put it on PATH to use CHDs.")
        return 0
    if args.command == "scan":
        return cli.main(_legacy_options(args, 'scan') + [str(p) for p in args.images])
    if args.command in ("patch", "repair", "verify"):
        db = cli.load_db()
        failure = False
        for image in args.images:
            try:
                build, name, profile = _one_profile(image, db, args.profile)
                status = profile['status']
                title = ' / '.join(build['games'])
                print(f"\n{title} | {name} | {status}", flush=True)
                if status != 'runtime_verified':
                    print("Heads up: this is NOT a fully runtime-verified recovery.")
                    if not args.experimental:
                        print("Use --experimental to opt in after reading the scan result.", file=sys.stderr)
                        failure = True
                        continue
                if status == 'known_incomplete' and not args.allow_incomplete:
                    print("This profile is known incomplete. Diagnostic testing needs --allow-incomplete too.", file=sys.stderr)
                    failure = True
                    continue
                if args.encoder == 'legacy':
                    print("Warning: legacy encoding updates the checksum, which may fail on real Viper hardware.")
                if args.command in ('patch', 'repair'):
                    print('Input stays untouched; patched copies go to:', args.output_dir)
                rc = cli.main(_legacy_options(args, args.command) + [str(image)])
                failure |= rc != 0
            except Exception as exc:
                print(f"\nCouldn't process {image}: {exc}", file=sys.stderr)
                failure = True
        return 1 if failure else 0
    raise ValueError("unknown command")


def _ask_yes(question: str, default: bool=False) -> bool:
    marker = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {marker} ").strip().casefold()
    if not answer:
        return default
    return answer in ('y','yes')


def wizard() -> int:
    if not sys.stdin.isatty():
        print('The wizard needs an interactive terminal. Try `sapera --help` instead.', file=sys.stderr)
        return 2
    print(f"\nSapera {__version__}\nKeeping original Viper cabinets alive. Bring a backup of your own media.\n")
    while True:
        print("\n1) Scan an image    2) Repair (new copy) 3) Verify an image")
        print("4) List games       5) Doctor            6) Exit")
        choice = input("Pick one [1-6]: ").strip()
        if choice == '6' or choice.casefold() in ('q', 'quit', 'exit'):
            return 0
        if choice == '4':
            _run_command(argparse.Namespace(command='list'))
            continue
        if choice == '5':
            _run_command(argparse.Namespace(command='doctor'))
            continue
        if choice not in ('1','2','3'):
            print("Pick 1 through 6.")
            continue
        path = Path(input('Drag in your CHD, RAW or BIN (or paste a path): ').strip().strip('"\'' )).expanduser()
        if not path.is_file():
            print("Can't find that file. Nothing changed.")
            continue
        scan_args=argparse.Namespace(command='scan', images=[path])
        if _run_command(scan_args):
            print("Can't recognize this one yet. Not going to guess.")
            continue
        if choice == '1':
            continue
        try:
            build, name, profile = _one_profile(path, cli.load_db(), None)
        except Exception as exc:
            print("Couldn't inspect the profile:", exc)
            continue
        print(f"Default profile: {name} ({profile['status']})")
        if len(build.get('profiles',{})) > 1 and _ask_yes("Want to use a different profile?"):
            name = input('Enter the exact profile name from the scan above: ').strip()
            if name not in build['profiles']:
                print("Not a known profile. Nothing changed.")
                continue
            profile=build['profiles'][name]
        status = profile['status']
        experimental = status != 'runtime_verified'
        incomplete = status == 'known_incomplete'
        if incomplete:
            print('This one is KNOWN INCOMPLETE. It is useful for diagnosing things, not a complete repair.')
            if not _ask_yes('Really try the incomplete recipe?'):
                continue
        elif experimental:
            print('This recipe has NOT been confirmed as a complete recovery in MAME/hardware.')
            if not _ask_yes('Okay testing an experimental profile?'):
                continue
        action = 'verify' if choice == '3' else 'repair'
        opts = argparse.Namespace(command=action, images=[path], profile=name,
                experimental=experimental, allow_incomplete=incomplete, encoder='neutral',
                output_dir=Path.cwd() / 'sapera-output', raw_only=False)
        if action == 'repair' and not _ask_yes('Make a separate candidate image? Your original stays untouched.'):
            continue
        result=_run_command(opts)
        print('Done.' if result==0 else 'Did not complete. Read the error above.')


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Backwards-compatible commands retained for older scripts and test harnesses.
    legacy_flags={'--check-db','--list-builds','--identify','--verify-encode','--dry-run','--print-ram','--allow-unverified'}
    if argv and (argv[0] in legacy_flags or argv[0].lower().endswith(('.chd','.raw','.img','.bin'))):
        return cli.main(argv)
    ap=parser()
    if not argv:
        if sys.stdin.isatty():
            try: return wizard()
            except (EOFError,KeyboardInterrupt):
                print('\nBye.')
                return 0
        ap.print_help()
        return 0
    args=ap.parse_args(argv)
    if args.command is None:
        ap.print_help()
        return 0
    try:
        if args.command=='wizard':
            return wizard()
        return _run_command(args)
    except KeyboardInterrupt:
        print('\nCanceled. Your original files were not overwritten.', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'Sapera: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
