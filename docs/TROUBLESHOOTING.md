# When Sapera or the cabinet does something weird

The first rule: **don't change five things at once**. Work on a separate media copy and write down what happened before the change.

| Symptom | First thing I'd check |
| --- | --- |
| `chdman not found` | Install MAME's separate `chdman` tool and put it on PATH, or use a supported raw image |
| Unknown executable hash | Confirm the exact image/version; Sapera intentionally refuses unknown binaries |
| Original PowerPC word mismatch | You have a different revision or already-patched image. Don't force a recipe onto it |
| Checksum-neutral encoding fails | There may be no valid representation for that patch under the current constraints; don't disable verification |
| Game progresses to a new RTC/security error | A later validation phase is still failing; report both the original and new text |
| Game progresses to sensor/gun/I/O error | The initial boot validation may have advanced, but real cabinet hardware needs separate testing |
| Black screen or BIOS loop | It may be loader, video, or control-flow failure. That is not a confirmed recovery |
| Erased timekeeper still fails | The game may require initialized backup-memory structures, not merely skipped error branches |

`scan` and `verify` are read-only. Use them before writing anything. Keep original CF/HDD and security hardware backed up and separate from experiments.

When filing an issue, provide Sapera version, image hash, selected profile, exact error text and whether you used MAME or a physical board. Please don't upload full game files or unique security-device data.
