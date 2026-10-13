# Sapera v1.0.0: cabinet repair release

This is the first cleaned-up release of Sapera for people trying to keep original Konami Viper arcade boards running when their battery-backed RTC/backup-memory state goes bad.

I started this because it seemed ridiculous for a functional cabinet to die over a decades-old timekeeper. It turns out Viper's compressed PowerPC executables are also a bit of a nightmare to change, so the project includes the checksum-neutral rewrite engine we developed to do it without breaking the original loader's size/checksum expectations.

**What you can do:** scan media from your own cabinet, identify the exact executable revision, dry-run a documented recovery profile, and create a separately named candidate image. There's a Windows launcher, interactive menu and a `repair` command so you don't have to memorize a pile of flags.

**What I'm not claiming:** that every supported game boots to gameplay. The tool has 27 recognized program hashes, but profile validation varies. Some erased-U39 tests got to new cabinet diagnostics; others, including the Family B backup-memory group, remain unfinished. Sapera shows those statuses instead of calling everything fixed.

No games, CHDs, BIOS ROMs, timekeeper dumps, dongle images, cryptographic keys or MAME executables are included.

Please keep your original storage and security chips intact, work from copies, and read the compatibility list and cabinet repair checklist before trying anything on hardware. This is independent repair/preservation research, not a Konami product or a legal exemption for distributing copyrighted games.
