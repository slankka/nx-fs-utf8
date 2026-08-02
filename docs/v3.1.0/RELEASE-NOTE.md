# v3.1.0 — Dual-Media UTF-8 FS Overlay KIP

**Release asset:** `fs_codecvt_dual_unpacked.kip`

This release delivers the final **dual-media** build of `nx-fs-utf8`, an FS
Overlay KIP that adds **UTF-8 (CJK / Chinese) filename compatibility** to the
Nintendo Switch FS sysmodule. It works on **both exFAT and FAT32** media with a
single, media-independent codecvt (no runtime media detection, no anchors).

## What's New in v3.1.0

- **Unified no-dispatch codecvt** — the six `PF_CHARCODE` slots are replaced
  with a fixed, media-independent implementation:
  - `slot0 (oem2unicode)`: full 3-byte UTF-8 decoder (exFAT fix)
  - `slot1 (unicode2oem)`: bounded ≤2-byte UTF-8 encoder (FAT32 safe)
  - `slots 2/4/5`: UTF-8 width / classification
- **No media signal** — no `g_fat_path` dispatch flag, no exFAT mount anchors.
  This removes the previous FAIL PASS FAIL failure mode caused by bounded
  slot0 on exFAT and the stack-overflow risk of a 3-byte slot1 on FAT32.
- **Cross-version** — one build targets the exFAT-capable FS of HOS 19.0.1,
  20.2.0, 21.2.0, 22.0.0 and 22.5.0.

## Verification Matrix

| HOS Version | FAT32 media (alone) | exFAT media (alone) | One-KIP dual-media |
|-------------|---------------------|---------------------|--------------------|
| 19.0.1 | ✅ TESTED (3/3) | ✅ offset verified | ✅ offset verified |
| 20.2.0 | ✅ offset verified | ✅ TESTED (3/3) | ✅ offset verified |
| 21.2.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |
| 22.0.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |
| 22.5.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |

The three checks cover: direct CJK file read/write, `/ROM` enumeration showing
the CJK directory, and enumerating files inside the CJK directory — including
the Chinese directory duplication issue previously reported.

Notes on the matrix:

- **TESTED (3/3)** — real-hardware PASS for all three checks with *this*
  release's KIP (`fs_codecvt_dual_unpacked.kip`): HOS 19.0.1 on FAT32, and
  HOS 20.2.0 on exFAT.
- **offset verified** — the `matches_fs` opcode-level offset check passes
  against that version's exFAT-capable FS image (six-slot table + dir/path/
  pattern/SFN + identity checks). The KIP is guaranteed to select and hook the
  correct version at runtime, but on-console regression on that combination is
  still pending.
- **One-KIP dual-media** is considered fully verified only when the *same* KIP
  passes 3/3 on **both** media within one HOS version. Cross-media operation is
  already demonstrated (the identical KIP passes on 19.0.1 FAT32 and
  20.2.0 exFAT); per-version dual regression is pending (offset verified).

## Requirements

- **[slankka/hekate-fs-overlay](https://github.com/slankka/hekate-fs-overlay)** —
  an unofficial Hekate fork adding support for prepending overlay KIPs to the
  FS process image. **This KIP can only be loaded by this modified Hekate.**
- exFAT-capable FS image (FAT32 media also boots on the exFAT-capable FS)

> **Note:** this is an FS Overlay KIP, **not** a standalone Initial Process KIP.
> Do **not** load it with Hekate's `kip1=` key. It must be merged into the
> existing `FS.kip1` process image by the FS Overlay-aware loader in the
> [`slankka/hekate-fs-overlay`](https://github.com/slankka/hekate-fs-overlay)
> fork.

## Installation

1. Download `fs_codecvt_dual_unpacked.kip` from this release.
2. Place it on the SD card at `sdmc:/bootloader/fsoverlays/fs_codecvt_unpacked.kip`

**Hekate boot entry** (`bootloader/hekate_ipl.ini`):

```ini
fsoverlay=bootloader/fsoverlays/fs_codecvt_unpacked.kip
```

(Rename `fs_codecvt_dual_unpacked.kip` to `fs_codecvt_unpacked.kip` if your
`fsoverlay=` config references that name, or update the path to the actual
filename.)

## Verify the CJK round trip

The `test_program` homebrew client creates and reads
`sdmc:/ROM/中文目录/往返测试.txt` and confirms both Chinese names appear through
directory enumeration. Launch it via the Homebrew Menu after boot.

## Checksums

```
File:    fs_codecvt_dual_unpacked.kip
Size:    10,428 bytes (0x28BC)
SHA-256: B78E72FB56085E130E445641426EDB2651EA19DE375473F49DE4B4DA8FDD7F55
```

## Rollback

- exFAT-only six-slot KIP (`codex/exfat` branch)
- FAT32 dual-contract KIP (earlier releases)

---

## Attribution & Notes

- For details see `docs/fs-header-formats-zh_CN.md` and the flight-test
  manifest (`flight_test/MANIFEST.md`).
