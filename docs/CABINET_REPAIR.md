# Actual cabinet repair checklist

If you've got a Konami Viper cabinet with battery-backed memory trouble, this is the order I'd do things. Nothing here requires wiping original media or pretending a bad chip isn't bad.

## Before touching anything

1. **Figure out what you're working with.** Get the game name, board revision, storage type and the actual error text. A black screen can be video, power, I/O, storage or a dead security component. Don't assume it's RTC.
2. **Make a verified backup of the original storage.** Read it twice if you can and compare checksums. Put the original card/disk somewhere safe. Don't run experiments on the only surviving copy.
3. **If the M48T58 timekeeper is readable, preserve a dump** as private repair data. Do not post its contents on GitHub. Keep original serial/dongle devices with their cabinet.
4. Check power, socketed chips, battery leakage, connectors and obvious board problems. Software cannot fix a floating supply rail or a dead storage bus.
5. Use an isolated copy for testing. If a board has persistent settings, take care not to overwrite them just to try an experimental patch.

## What Sapera can do

Run `sapera doctor`, then `sapera scan YOUR_IMAGE`. If it's recognized, read the profile status and the specific known error. `sapera verify YOUR_IMAGE --experimental` checks whether the candidate image can be constructed cleanly without writing the output. `sapera repair YOUR_IMAGE --experimental` makes a separate output for further testing.

A green encoder result means the program's compressed structure is internally consistent. The next step is a controlled MAME or cabinet test. It does **not** mean the game has been restored to working condition.

## What success looks like

Record the before and after behavior. An initial RTC error becoming a later bookkeeping or cabinet sensor check means the boot path got further. That's useful research, but don't call the entire repair complete until the real hardware is functioning normally.

## Things I'd avoid

- Writing anything back to your original CF/HDD before you have a verified backup.
- Erasing unique board identity data in a timekeeper or serial security device.
- Treating an `ALL` / `known_incomplete` profile as known good without checking its actual status.
- Flashing a different game region just because the executable name looks similar.
- Posting complete game images, serial-device dumps or timekeeper contents when asking for help.

The reason this tool exists is to preserve **real hardware**, not destroy another surviving copy of it.
