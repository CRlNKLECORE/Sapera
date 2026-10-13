# Putting Sapera on GitHub

The actual reason for this repo is simple: keep surviving Konami Viper boards running when their battery-backed state stops cooperating. That's how I've written the README and release notes. It does **not** mean a repair disclaimer erases legal risk.

**Before making the repo public:** read [LEGAL_AND_PUBLISHING.md](LEGAL_AND_PUBLISHING.md). Confirm code ownership and have the game-specific bypass profiles / manifests reviewed as appropriate. There are no proprietary game images in this package, but that's only part of the analysis.

## Create the repository

On GitHub, create a new **empty** repository named `Sapera` in the account you want to use. Do not initialize it with a README or license because those files are already in this folder.

If you're using `CRlNKLECORE`, the destination should be `https://github.com/CRlNKLECORE/Sapera`.

Then, from *inside this extracted Sapera folder*:

```bash
python -m pytest -q
python tools/audit_release.py
git init
git add .
git diff --cached --stat
git commit -m "Sapera v1.0.0: keep original Viper cabinets alive"
git branch -M main
git remote add origin https://github.com/CRlNKLECORE/Sapera.git
git push -u origin main
```

If publishing to another account, change the remote URL. Review the staged file list first; **never upload a working directory containing copyrighted CHDs, ROMs, NVRAM dumps or keys**.

## GitHub About box

**Description:** `Helping original Konami Viper arcade cabinets survive dead RTC and battery-backed memory.`

**Topics:** `konami-viper`, `arcade-preservation`, `arcade-repair`, `reverse-engineering`, `powerpc`, `timekeeper`, `retrogaming`

Create a GitHub release tagged `v1.0.0`, title `Sapera v1.0.0 - Cabinet Repair`, using `RELEASE_NOTES.md`. GitHub can generate a source archive automatically. Do not attach ROMs, CHDs, dongle/timekeeper dumps or proprietary screenshots.

**Important:** Once something has been published into Git history, deleting the newest copy doesn't necessarily remove it from earlier revisions or forks. Review everything *before* pushing.
