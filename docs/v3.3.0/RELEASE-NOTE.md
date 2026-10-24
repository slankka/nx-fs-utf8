# v3.3.0 — SysNAND Support

**Release asset:** `fs_codecvt_dual_unpacked.kip`

The overlay now works on **SysNAND (sysMMC)**, not just emuMMC. That is the whole
of this release: no change to the UTF-8 conversion, the directory-name filter,
or the supported firmware list.

> **Supersedes v3.2.0's SysNAND warning.** That release said "Do not use this KIP
> on SysNAND … Supporting SysNAND is out of scope." The cause has been found and
> fixed. SysNAND is supported as of this version.

## What was actually wrong

Prepending the overlay shifts FS's sections. FS then runs its own RTLD pass over
`.dynamic`, and one entry's final check compares a computed end against a bound
derived from the section layout. Once shifted, that check fails and FS aborts
**before `main()`** — a black screen with no on-screen error, indistinguishable
from "the overlay broke something".

That is why every earlier SysNAND attempt failed, and why it looked like
SysNAND rejected prepending outright: an overlay with *zero* hooks failed
exactly the same way, and so did one that only branched straight back into the
stock entry point.

emuMMC has carried the workaround for years. It overwrites the trailing `b.cond`
of that RTLD loop with an unconditional branch, so the offending entry is
skipped instead of aborting:

```asm
; 22.5.0, rtld = 0x2DED0
0x2DED0  b.ne  0x2DE84     ; original
0x2DED0  b     0x2DE84     ; what v3.3.0 writes
0x2DED4  ...               ; the failing final check, now skipped
```

v3.3.0 applies the same patch from our own overlay, which is also why emuMMC's
code is no longer needed for this.

## Support Matrix

| HOS | SysNAND | emuMMC |
|---|---|---|
| 19.0.1 | offset verified | ✅ TESTED (3/3) |
| 20.2.0 | offset verified | ✅ TESTED (3/3) |
| 21.2.0 | offset verified | offset verified |
| 22.0.0 | offset verified | offset verified |
| 22.5.0 | offset verified | offset verified |
| **23.0.0 / 23.0.1** | ✅ **TESTED (3/3)** | ✅ **TESTED (3/3)** |

- **TESTED (3/3)** — real-hardware PASS for direct CJK read/write, `/ROM`
  enumeration showing the CJK directory, and enumeration *inside* the CJK
  directory.
- **offset verified** — the `matches_fs` opcode checks pass against that
  version's FS image. For the RTLD site this also means the site opcode matches
  *and* the branch delta decoded from its immediate matches the table, so the
  patch cannot land at a wrong target. On-console regression of that exact
  combination is still pending.

The 21.2.0 RTLD site sits at a **higher** offset (`0x2E1C0`) than 22.0.0's
(`0x2DED0`) despite being an older release. Every offset was measured against
the actual image rather than derived by shifting, for exactly that reason.

## Requirements

[slankka/hekate-fs-overlay](https://github.com/slankka/hekate-fs-overlay) — an
unofficial Hekate fork adding `fsoverlay=` support. This KIP cannot be loaded
without it.

### `bootloader/sys/emummc.kipm` must still exist

The loader copies the 0x80-byte capability array out of that file into the merged
KIP, and **injects none of its code**. The file is not optional: with it missing
the boot stops with `bootloader/sys/emummc.kipm is missing or invalid`.

Those capabilities are what allow the overlay to call `svcMapProcessMemory` on
its own process, which is how it obtains write access to FS's read-execute
pages. FS's own capability array is too small for that — tested, not assumed: a
build that keeps FS's caps and skips the file black-screens, because the mapping
fails, no hook is installed, and FS then aborts in the RTLD walk described above.

Removing this last dependency is planned, not done.

### Do not set `kip1patch=emummc`

That injects emuMMC's *code*, and five of its six hooks replace FS's media path
with emuMMC's own driver. On SysNAND that driver has nowhere to read from, so the
console does not boot. If you copied a boot entry from an older guide, delete
that line.

> **Note:** `fs_codecvt_dual_unpacked.kip` is an FS **Overlay** KIP, not a
> standalone Initial Process KIP. Do **not** load it with `kip1=` — it must be
> merged into the existing FS process image by the overlay-aware loader.

## Installation

1. Download `fs_codecvt_dual_unpacked.kip` from this release.
2. Place it at `sdmc:/bootloader/fsoverlays/fs_codecvt_dual_unpacked.kip`.
3. Add a boot entry.

On SysNAND:

```ini
[真实系统-中文路径]
pkg3=atmosphere/package3
emummc_force_disable=1
fsoverlay=bootloader/fsoverlays/fs_codecvt_dual_unpacked.kip
```

On emuMMC:

```ini
[虚拟系统-中文路径]
pkg3=atmosphere/package3
emummcforce=1
fsoverlay=bootloader/fsoverlays/fs_codecvt_dual_unpacked.kip
```

The entry is identical apart from which medium is being booted. There is no
SysNAND-specific variant, no extra key, and no `kip1patch=` line.

## Verify the CJK round trip

The `test_program` homebrew client creates and reads
`sdmc:/ROM/中文目录/往返测试.txt` and confirms both Chinese names appear through
directory enumeration. Launch it via the Homebrew Menu after boot.

A pass means all three of: the CJK directory can be created, it can be stat'd by
its own UTF-8 path, and it appears when the parent directory is listed.

## Checksums

```
File:    fs_codecvt_dual_unpacked.kip
Size:    11,140 bytes (0x2B84)
SHA-256: 68d889364d1302b410209b78098f3c64a48382117b30ef42c74a6f066ba98b25
```

The image grew by 552 bytes over v3.2.0 (10,588 → 11,140). The memory extent is
unchanged at `0x8000`, so deployments keep the same layout.

## Rollback

Remove the `fsoverlay=` line from `hekate_ipl.ini`. The stock FS image on disk is
never modified, so nothing needs to be restored.

If the console hangs, hold the power button for 12 seconds, take out the SD card,
and delete that line.

## Upgrading from v3.2.0

Nothing to do beyond replacing the `.kip` and deleting `kip1patch=emummc` if you
had it. The firmware list is unchanged, so an image that matched before still
matches.

Historical builds remain available in earlier releases.

---

## Attribution & Notes

Copyright (c) 2026 slankka and contributors. Licensed under
`GPL-2.0-only` — see [LICENSE](../../LICENSE).

The RTLD workaround was originally written for emuMMC by the Atmosphère project;
this release ports the idea to a standalone overlay. The KIP startup framework is
likewise derived from the Atmosphère emuMMC design.

Development was assisted by generative AI. The maintainer directed, reviewed,
modified, tested, and approved the resulting code. The AI tool is not an author
or copyright holder.
