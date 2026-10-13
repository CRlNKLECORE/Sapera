# Contributing

If you've got an actual Viper cabinet giving you grief, tell me what it's doing. The useful report is usually the boring stuff: exact board/game revision, what failed, what the screen says and what changed after you tried a profile.

For bugs, please include the Sapera version, `scan` output **without proprietary bytes**, selected profile, OS, and whether the result came from MAME or physical cabinet hardware. Don't report "fixed" just because the decompressor accepted an image or the screen changed to a different error.

When submitting code:

- Run `python -m pytest -q` and `python tools/audit_release.py`.
- Keep exact executable SHA-256 identification, original-instruction checks, branch validation and final checksum/decompression verification.
- Mark incomplete profiles honestly. `runtime_advanced` is not interchangeable with `runtime_verified` or "playable".
- Explain why a new change is relevant to repairing original hardware, and distinguish MAME validation from a real cabinet test.
- Submit code you wrote or code you can lawfully license. Include source and license details for any third-party material.

**Do not upload** game images, CHDs, executable dumps, BIOS ROMs, NVRAM/timekeeper contents, security dongle data, proprietary game screenshots, or encryption keys. A description of the failure and a program hash will usually do.

This is about keeping arcade hardware around, not building another place to exchange game dumps.
