# Publishing and legal notes

This is a risk checklist, not legal advice or a claim that a preservation project is automatically exempt from copyright restrictions.

Sapera is meant to help people restore **their original Konami Viper hardware** when aging battery-backed RTC, SRAM or associated board state prevents otherwise functioning cabinets from starting. That is its actual purpose. But wording a project as "repair" doesn't change how copyright or anti-circumvention law applies to specific features.

The repository intentionally excludes games, CHDs, original ROM/BIOS firmware, complete game executables, encryption keys, timekeeper/NVRAM data, security-dongle dumps and MAME binaries. This reduces obvious distribution issues, but it does **not** settle the treatment of game-specific instruction changes.

In the United States, 17 U.S.C. §1201 restricts certain circumvention and distribution of circumvention technology. Some narrow interoperability and preservation exceptions exist. Those exceptions are fact-specific, and a user's preservation or repair purpose doesn't necessarily authorize public distribution of the tool itself. Other countries have different rules.

The generic ZIN parser/re-encoder has independent technical applications. `sapera/builds.json` and `sapera/manifests/*.json` are different: they encode game-specific changes, including security-related decisions. **Those are the files most worth professional legal review before putting this repo on a public GitHub account.**

The MIT license is only for code/data the licensors have the rights to distribute. It does not grant permission to copy Konami's games and does not prevent third parties from raising claims. Check the provenance of all code and build manifests; do not assume reverse-engineered equals freely publishable.

## Last check before going public

- [ ] Verify authorship and license compatibility of every source file and contribution.
- [ ] Review the exact-game profiles and precomputed manifests with qualified counsel if possible.
- [ ] Ensure no copyrighted images, ROM/CHD files, complete executables, BIOS, original dongle/NVRAM data, proprietary screenshots or keys are tracked.
- [ ] Run the included audit and unit tests. These are *technical* checks, not legal clearance.
- [ ] Inspect **Git history** and release attachments, not only the working tree.
- [ ] Keep compatibility labels honest and distinguish MAME progression from original-hardware playability.
- [ ] Publish only the code you're authorized to publish; keep private material out of bug reports and discussions.

If the game-specific profiles are not cleared for publication, the lower-risk alternative is a public core-only repository with the generic analyzer/encoder while withholding exact per-game modifications pending review. That would be less useful for repair today, but lowers a distinct category of risk.

Primary materials: [17 U.S.C. §1201](https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title17-section1201&num=0&edition=prelim), [U.S. Copyright Office §1201](https://www.copyright.gov/1201/) and [GitHub repository licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
