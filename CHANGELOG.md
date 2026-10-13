# Changelog

## 1.0.0 - Cabinet repair / public source edition (October 2026)

The public version starts at 1.0.0. The internal research builds had higher numbers; this is not an engine downgrade.

- Reframed the project around recovering real Konami Viper cabinets affected by battery-backed RTC/backup-memory failures.
- Added a cabinet-first checklist, clearer readiness labels, and a README written for people dealing with actual arcade hardware.
- Introduced the `repair` alias for the original `patch` command while retaining compatibility with older scripts.
- Preserved the checksum-neutral ZIN encoder, exact-build fingerprinting, patch manifests and PowerPC branch safety checks.
- Kept read-only `scan` and `verify` operations, separate output copies and explicit opt-in for experimental/incomplete profiles.
- Added the Windows launcher, interactive menu, GitHub Actions checks, release content audit, and contributor/security guidance.
- Excluded copyrighted game assets, test ROMs/CHDs, real timekeeper and dongle dumps, MAME binaries and private debugging directories.

**Still unresolved:** some games do not recover usable backup-memory state, Thrill Drive 2 C has a separate early boot issue, and ParaParaParadise 2nd Mix doesn't use the standard supported CF/ZIN path. Passing an encoding test isn't the same as fixing a cabinet.
