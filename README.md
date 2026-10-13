# Sapera

### Keeping the original Konami Viper hardware alive, one dead timekeeper at a time.

Okay, so here's the problem. There are still perfectly good Konami Viper arcade boards out there, but a bunch of them depend on battery-backed timekeeper memory to start their games. Eventually the battery dies, the saved state disappears, and suddenly you've got an otherwise functional cabinet that refuses to boot.

I think that's a pretty stupid reason for a piece of arcade history to turn into a giant paperweight.

**Sapera is my attempt to keep those original boards running.** It works with an image of the *existing* game media, identifies the exact PowerPC program, and can build a separate, modified image using a documented recovery profile. The whole point is to use the original Viper CPU, original board, original cabinet and original game hardware, instead of replacing everything with a PC because an aging backup-memory device went bad.

This project grew out of trying to bring real cabinets back to life. Things got a bit ridiculous when I discovered that changing a few PowerPC instructions could upset the game's compressed executable and prevent the original loader from starting. So I ended up building a checksum-neutral rewrite engine too. That part has turned into a pretty interesting reverse-engineering project in its own right.

**This is a cabinet repair and preservation project. It is not a ROM collection, emulator, or a promise that every Viper game has been fixed.** And no, it doesn't physically repair a failed timekeeper chip. Some profiles help the game continue despite bad backup data; others still need work.

## First things first

- **Keep your originals.** Image your CompactFlash/HDD before touching anything, and keep a separate backup of whatever timekeeper data you can still read. Sapera does not need to overwrite your original image.
- **Use media you own or are otherwise authorized to work with.** There are no games or proprietary firmware files in this repository.
- **Don't assume a new screen means success.** Going from `RTC SELF CHECK BAD` to `SENSOR BAD` is progress in tracing the boot path, not proof the cabinet is fully repaired.

See [the cabinet checklist](docs/CABINET_REPAIR.md) if you're actually standing in front of a machine with its guts hanging out. If Sapera throws something weird at you, try [troubleshooting](docs/TROUBLESHOOTING.md).

## Get it running

You need Python **3.10 or newer**. If you're feeding Sapera a `.chd`, install **chdman** separately from MAME and put it on your PATH. Raw CF/disk images and supported BIN files don't need chdman.

**Windows:** download the source ZIP, extract it, then double-click `Sapera.bat`. It opens a basic guided menu. You can paste or drag a file path into it.

**Linux / macOS / terminal:** open a terminal in this folder:

```bash
python -m sapera doctor
python -m sapera scan path/to/your/image.chd
```

`scan` only looks at the file. It doesn't change anything. If the exact build is recognized, it'll tell you what recovery profiles are available and whether anyone actually validated them.

Before writing anything, dry-run the recovery:

```bash
python -m sapera verify path/to/your/image.chd --experimental
```

If the profile is appropriate for your own cabinet and you want to create a **new copy**:

```bash
python -m sapera repair path/to/your/image.chd --experimental
```

You'll get a new output in `./sapera-output/`. The source image is left alone. `repair` and `patch` are interchangeable commands; `repair` is just the friendlier name for what this tool is actually meant for.

You can also install the package locally with `python -m pip install .`, then use `sapera` instead of `python -m sapera`.

### Commands worth remembering

| Command | What it does |
| --- | --- |
| `sapera wizard` | Interactive menu, no flags to memorize |
| `sapera doctor` | Check Python, database and CHD support |
| `sapera scan game.chd` | Identify exactly what you have; no writes |
| `sapera list` | List recognized executable builds |
| `sapera verify game.chd --experimental` | Try a recovery in memory and verify its encoding; no output image |
| `sapera repair game.chd --experimental` | Write a separately named candidate image |
| `sapera repair game.chd --profile NAME --experimental` | Choose a different recovery profile from `scan` |

If you want the original technical command, `sapera patch` still works. Existing lower-level CLI flags are retained for scripts.

Why the `--experimental` flag? Because not every game's recovery is finished, and I don't want a casual user mistaking "the output checksum matches" for "it's safe to flash this onto your only CF card." Profiles known to be incomplete need **both** `--experimental` and `--allow-incomplete`. Those are diagnostic experiments, not working repairs.

## What Sapera actually changes

On supported Viper media, Sapera finds the compressed game executable, expands it and checks the **SHA-256 of the entire original PowerPC program**. If it's not an exact known build, it refuses to guess.

Then it checks every original instruction in the selected recipe and reconstructs the modified program. The interesting bit is that it can re-encode that program while preserving the **original compressed size and 32-bit additive checksum**. It decodes the result again and checks it byte-for-byte before writing the output image.

That means the original Viper program loader can still accept a consistently encoded file. It does **not** mean we're spoofing a hardware timekeeper, fixing the board electrically, or guaranteeing any particular game will work. We're repairing specific software startup failures associated with damaged or erased battery-backed state.

If you're into the technical side, read [how the engine works](docs/TECHNICAL.md). There was also a particularly goofy PowerPC backward-branch bug during development, and the validator now explicitly guards against it.

## Okay, but which cabinets does it help?

Sapera currently recognizes **27 distinct executable hashes** in its exact-build database. That's *recognition*, not 27 confirmed playable cabinets.

During tests using deliberately erased U39 timekeeper data, several titles got past their initial failure and reached later cabinet setup or I/O diagnostics, including **Mocap Boxing**, **Police 911**, **Police 911 2**, **Thrill Drive 2**, **Jurassic Park III** and **Xtrial Racing**. The result varies by actual revision and chosen profile.

Other titles, particularly **Tsurugi / Blade of Honor**, **Boxing Mania** and **Mahjong Fight Club**, still need backup-memory initialization work. **ParaParaParadise 2nd Mix** uses a different media/security path and isn't covered by the standard CF/ZIN workflow.

Profiles are marked with one of these labels:

| Label | What it means in normal human terms |
| --- | --- |
| `runtime_verified` | Evidence exists for the stated behavior on that specific build; not a universal playability guarantee |
| `runtime_advanced` | The game got past a particular failure but may stop somewhere else |
| `family_transferred` | Based on a related revision; needs its own runtime test |
| `static_candidate` | Analyzed but not confirmed running |
| `native_recovery_candidate` | Experimental attempt to reuse original backup-memory logic |
| `known_incomplete` | It doesn't solve the whole problem, don't treat it as a finished fix |

The [compatibility page](docs/COMPATIBILITY.md) contains the actual build-by-build status. Please check that rather than guessing by game title.

## Actually using this on a cabinet

Make a clean backup, identify the media, dry-run the intended profile, and test an independently written copy. If you have an original timekeeper or serial/security device that still works, don't erase or overwrite it to make an experiment easier.

Keep in mind that sensor faults, gun calibration, motion hardware, I/O boards and damaged storage are completely separate issues. Sapera isn't going to magically fix all of those. It also isn't a replacement for proper board-level repair when a chip has physically failed.

MAME is useful for controlled startup tests, especially with simulated erased memory, but emulation and original cabinet hardware can behave differently. A **MAME pass is not a hardware certification**.

## What I'm publishing, and what I'm not

The repo contains original Sapera source, tests, build fingerprints, game-specific **instruction-difference** profiles and checksum-neutral rewrite recipes. These recipes are not complete game executables.

It does **not** contain any CHDs, ROMs, game BINs, BIOS images, timekeeper/NVRAM or dongle dumps, cryptographic keys, proprietary game artwork, or MAME binaries. Please don't put those in issues or pull requests either.

This is an independent hobbyist preservation project. **Konami isn't involved or endorsing it**, and the game names belong to their respective owners. I'm publishing the code to document this repair work and help keep the real machines usable, not to distribute commercial games.

There are still copyright and anti-circumvention questions around distributing game-specific modifications. The preservation goal doesn't automatically create an exception to those rules. Read the [legal/publication notes](docs/LEGAL_AND_PUBLISHING.md), and review the profile data before making your own redistributions. The MIT license only covers code its contributors have the rights to license.

## Want to help?

If you've got a Viper cabinet that refuses to start because of backup-memory/RTC trouble, I'd be interested in the result. Open an issue with the cabinet/game revision, Sapera version, program SHA-256 reported by `scan`, the profile you tried, and the exact text on the screen. Tell me whether you're testing in MAME or on actual hardware.

**Don't upload copyrighted media or your board's security/dongle data.** Logs and short descriptions are usually plenty to start narrowing things down. See [contributing](CONTRIBUTING.md).

I'd much rather keep another original cabinet running than see perfectly good arcade hardware get junked because a battery that lasted twenty-odd years finally gave up.
