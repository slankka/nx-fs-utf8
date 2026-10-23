# v3.2.0 — HOS 23.0.0 / 23.0.1 Support

**Release asset:** `fs_codecvt_dual_unpacked.kip`

Adds the exFAT-capable FS of **HOS 23.0.0 / 23.0.1** to the dual-media UTF-8 FS
Overlay KIP. Everything from v3.1.0 is unchanged — same media-independent
codecvt, same single-KIP-for-both-media design.

> **Revision note.** An earlier revision of this note marked 23.0.1 as
> "offset derived" and implied it was unverified. That was wrong.
> **23.0.1 is confirmed on real hardware in emuMMC.**

## What's New

- **New FS 23.0.1 offset table.** The 23.0.1 exFAT `FS.kip1`
  (SHA-256 prefix `FDAF163288E10805…`) is structurally the 22.5.0 image shifted
  by `+0x3030`. All six `PF_CHARCODE` slots, every `utf8dir` hook, the
  path / pattern / SFN guards and the code cave land at the shifted addresses
  byte-identically. The only field that is *not* a pure shift is one identity
  check at `dir_reject` (`0xD28A9041 → 0xD2822461`), updated accordingly.
- One KIP now covers the exFAT-capable FS of **19.0.1, 20.2.0, 21.2.0, 22.0.0,
  22.5.0 and 23.0.1** (23.0.0 shares the same FS binary as 23.0.1).

## Support Matrix

This KIP is an **emuMMC** deliverable. See the SysNAND note below.

| HOS | FAT32 media | exFAT media |
|---|---|---|
| 19.0.1 | ✅ TESTED (3/3) | ✅ offset verified |
| 20.2.0 | ✅ offset verified | ✅ TESTED (3/3) |
| 21.2.0 | ✅ offset verified | ✅ offset verified |
| 22.0.0 | ✅ offset verified | ✅ offset verified |
| 22.5.0 | ✅ offset verified | ✅ offset verified |
| **23.0.0 / 23.0.1** | — | ✅ **TESTED (3/3)** |

- **TESTED (3/3)** — real-hardware PASS for direct CJK read/write, `/ROM`
  enumeration showing the CJK directory, and enumeration *inside* the CJK
  directory.
- **offset verified** — the `matches_fs` opcode check passes against that
  version's FS image; on-console regression on that exact combination is still
  pending.

## SysNAND: known black screen

**Do not use this KIP on SysNAND.** Loading it against the real system produces
a **black screen with no on-screen error** — the console hangs before anything
can be displayed.

This is not specific to 23.0.1. It reproduces identically on 19.0.1, 22.5.0 and
23.0.1, and at every overlay extent from `0x1000` to `0x60000`. Prepending code
to the FS process image on SysNAND does not work, because FS is the first
initial process and `fatal` is not yet available to report anything.

It works on emuMMC because there the overlay is placed in front of *emummc's*
`_start`, which performs its own `SVC 0x73` permission setup before handing over
to FS. That composition does not exist on SysNAND.

If you need UTF-8 paths on SysNAND, keep booting SysNAND without an overlay.
Supporting SysNAND is out of scope for this release.

## Requirements

[slankka/hekate-fs-overlay](https://github.com/slankka/hekate-fs-overlay) — an
unofficial Hekate fork adding `fsoverlay=` support. This KIP cannot be loaded
without it.

> **Note:** `fs_codecvt_dual_unpacked.kip` is an FS **Overlay** KIP, not a
> standalone Initial Process KIP. Do **not** load it with `kip1=` — it must be
> merged into the existing FS process image by the overlay-aware loader.

## Installation

1. Download `fs_codecvt_dual_unpacked.kip` from this release.
2. Place it at `sdmc:/bootloader/fsoverlays/fs_codecvt_dual_unpacked.kip`

**Hekate boot entry** (`bootloader/hekate_ipl.ini`) — emuMMC only:

```ini
[虚拟系统-中文路径]
emummcforce=1
fsoverlay=bootloader/fsoverlays/fs_codecvt_dual_unpacked.kip
```

## Verify the CJK round trip

The `test_program` homebrew client creates and reads
`sdmc:/ROM/中文目录/往返测试.txt` and confirms both Chinese names appear through
directory enumeration. Launch it via the Homebrew Menu after boot.

## Checksums

```
File:    fs_codecvt_dual_unpacked.kip
Size:    10,588 bytes (0x295C)
SHA-256: C438EB09D6ED9A921F7DB834A020143811224369A4195F56D3B8A3114A0D445F
```

## Rollback

Remove the `fsoverlay=` line from `hekate_ipl.ini`. The stock FS image on disk
is never modified, so nothing needs to be restored.

Historical builds remain available on the `codex/exfat` branch and in earlier
releases.

---

## Attribution & Notes

- For the overlay mechanism and header layouts see
  `docs/fs-header-formats-zh_CN.md`, and the flight-test manifest
  (`flight_test/MANIFEST.md`).
