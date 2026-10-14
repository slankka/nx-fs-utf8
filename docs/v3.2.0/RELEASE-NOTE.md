# v3.2.0 — HOS 23.0.1 Support

**Release asset:** `fs_codecvt_dual_unpacked.kip`

Adds the exFAT-capable FS of **HOS 23.0.0 / 23.0.1** to the dual-media UTF-8 FS
Overlay KIP. Everything from v3.1.0 is unchanged — same media-independent
codecvt, same single-KIP-for-both-media design.

## What's New

- **New FS 23.0.1 offset table.** The 23.0.1 exFAT `FS.kip1`
  (SHA-256 prefix `FDAF163288E10805…`) is structurally the 22.5.0 image shifted
  by `+0x3030`. All six `PF_CHARCODE` slots, every `utf8dir` hook, the
  path / pattern / SFN guards and the code cave land at the shifted addresses
  byte-identically. The only field that is *not* a pure shift is one identity
  check at `dir_reject` (`0xD28A9041 → 0xD2822461`), updated accordingly.
- One KIP now covers the exFAT-capable FS of **19.0.1, 20.2.0, 21.2.0, 22.0.0,
  22.5.0 and 23.0.1** (23.0.0 shares the same FS binary).

## Support Matrix

| HOS Version | FAT32 media (alone) | exFAT media (alone) | One-KIP dual-media |
|---|---|---|---|
| 19.0.1 | ✅ TESTED (3/3) | ✅ offset verified | ✅ offset verified |
| 20.2.0 | ✅ offset verified | ✅ TESTED (3/3) | ✅ offset verified |
| 21.2.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |
| 22.0.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |
| 22.5.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |
| **23.0.1** | — | ⚠️ offset derived | ⚠️ offset derived |

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
- **⚠️ offset derived** — **23.0.1 is derived, not hardware-tested.** The image
  matches the 22.5.0 table shifted by `+0x3030` with the single non-shifted
  field adjusted, but no on-console regression has been run yet. Feedback
  welcome via [Issues](https://github.com/slankka/nx-fs-utf8/issues).

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
2. Place it on the SD card at
   `sdmc:/bootloader/fsoverlays/fs_codecvt_dual_unpacked.kip`

**Hekate boot entry** (`bootloader/hekate_ipl.ini`):

```ini
fsoverlay=bootloader/fsoverlays/fs_codecvt_dual_unpacked.kip
```

(If your `fsoverlay=` line already references a different filename, update the
path to match the file you actually copied.)

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

Remove the `fsoverlay=` line — the stock FS image is untouched. Historical
builds remain available on the `codex/exfat` branch and in earlier releases.

---

## Attribution & Notes

- For details see `docs/fs-header-formats-zh_CN.md` and the flight-test
  manifest (`flight_test/MANIFEST.md`).
