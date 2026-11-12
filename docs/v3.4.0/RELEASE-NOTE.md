# v3.4.0 — HOS 23.5.0 Support

**Release asset:** `fs_codecvt_dual_unpacked.kip`

Adds the exFAT-capable FS of **HOS 23.5.0** to the offset table. Nothing else
changes: the media-independent conversion, the single-KIP-for-both-media design,
and the SysNAND/emuMMC behaviour are all as in v3.3.0.

## What's new

**FS 23.5.0 offset table.** The image is `FS.kip1` SHA-256 prefix
`7B902837F2002749…`, from BootImagePackageExFAT `010000000000081b`
(SDK 23.3.0.0, 1,413,364 bytes, `.text` `0x1E92A4` — the same `.text` length as
23.0.1).

One KIP now covers the exFAT-capable FS of **19.0.1, 20.2.0, 21.2.0, 22.0.0,
22.5.0, 23.0.0, 23.0.1 and 23.5.0**.

## Why the table could not simply be shifted

23.5.0 is *not* 23.0.1 moved by a constant. Aligning the two `.text` images on
4-byte words splits them into four bands:

| Range | Delta | Words identical | What it is |
|---|---|---|---|
| `0x00000..0x576B8` | 0 | 97.96 % | local recompiles |
| `0x576B8..0x58E28` | — | — | genuinely rewritten (string / path helpers) |
| `0x58E28..0x1E65AC` | **+0x10** | 95.19 % | a 4-instruction prologue was inserted early |
| `0x1E65AC..0x1E92A4` | 0 | 99.20 % | tail realigns |

Every anchor `fs_codecvt` hooks happens to fall in the `+0x10` band, but each one
was re-derived from the disassembly — same mnemonic, same operands, same
neighbouring instructions — rather than by adding `0x10` to the 23.0.1 table.
Two facts make the hook set safe:

- the 0xA0-byte code cave (`0x1147D0 → 0x1147E0`) is **byte-identical**, so the
  in-place patcher still fits;
- `Directory::Read` keeps the register contract the trampoline depends on:
  `name=X26`, `bound=X24`, `byte=W9`, scan index `X8`.

The only field that is not a shift is `identity_checks[5]`, the MOV immediate at
`dir_reject`:

| FS | `dir_reject` | Immediate |
|---|---|---|
| 22.5.0 | `0xE70C0` | `0xD28A9041` |
| 23.0.1 | `0xEA0F0` | `0xD2822461` (`mov x1, #0x1123`) |
| **23.5.0** | **`0xEA100`** | **`0xD28F7C81` (`mov x1, #0x7be4`)** |

This immediate changes on every release, which makes it the most reliable
version fingerprint available. The `23.5.0` profile uses it to reject 23.0.1,
22.5.0 and the FAT-only 23.5.0 build.

## Support Matrix

| HOS | SysNAND | emuMMC |
|---|---|---|
| 19.0.1 | offset verified | ✅ TESTED (3/3) |
| 20.2.0 | offset verified | ✅ TESTED (3/3) |
| 21.2.0 | offset verified | offset verified |
| 22.0.0 | offset verified | offset verified |
| 22.5.0 | offset verified | offset verified |
| 23.0.0 / 23.0.1 | ✅ TESTED (3/3) | ✅ TESTED (3/3) |
| **23.5.0** | ⚠️ offset verified | ⚠️ offset verified |

- **TESTED (3/3)** — real-hardware PASS for direct CJK read/write, `/ROM`
  enumeration showing the CJK directory, and enumeration *inside* the CJK
  directory.
- **offset verified** — every `matches_fs` opcode guard, the `identity_checks`
  and the RTLD check pass against that version's FS image. On-console regression
  of that exact combination is still pending.

The FAT-only 23.5.0 build (`0100000000000819`, SHA-256 `01ED6B874C1FEF41…`) is
**out of scope**: it has no usable NOP cave, and its six `PF_CHARCODE` slots are
laid out differently (`codecvt[1]`'s instruction sequence has zero hits in that
image). No profile matches it, so it runs unmodified rather than half-patched.

## Launcher support

23.5.0's `package1` timestamp is **`20260930`** (23.0.x used `20260730`), so a
launcher must recognise that entry or it refuses to boot before FS is even
reached. This is unrelated to FS, and **upstream has already handled it**:

| Component | Version | Commit |
|---|---|---|
| Atmosphere | 1.12.2 | `bab60d8ad ams: add enum recognition for 23.5.0` |
| hekate | v6.5.5 | `0928365b hos: add 23.5.0 support` |

hekate needed a follow-up fix, `184584a9 hos: pkg2_patches: fix non-exFAT 23.5.0
nogc offset` — the FAT32 branch had inherited the exFAT offset.

> **`emummc.kipm` must be rebuilt.** It is a gitignored artefact, so merging the
> source does not update it. The old KIPM has no `FS_VER_23_5_0(_EXFAT)` entry
> and will `fatal_abort(Fatal_UnknownVersion)` on 23.5.0 — a black screen.
> Rebuild with `cd Atmosphere/emummc && make clean && make kipm`.

## Verifying the table

Reproducing the claims above takes two entry points:

| File | Purpose |
|---|---|
| `tools/check_offsets.py` | `23.5.0` profile; replays every guard against any `FS.kip1` / `.text` |
| `tools/mk_fs_utf8.py` | builds the in-place patch from the same profile, which also proves the cave fits |

```bash
# is this image recognised? (and only by its own profile)
python tools/check_offsets.py <FS.kip1> --profile 23.5.0 --window 8

# does the in-place patch fit inside reclaim + page slack?
python tools/mk_fs_utf8.py --stock <FS.kip1> --elf fs_codecvt_dual.elf \
       --profile 23.5.0 --slot1-full --out out/FS_23.5.0_utf8.kip
```

What was checked, all point-by-point against the image:

- the six `PF_CHARCODE` slots moved `+0x10`, bodies instruction-identical;
- `dir_hook`'s `cmn` / `b.ls` shape is unchanged, and the `Directory::Read`
  register contract (`X26` / `X24` / `W9` / `X8`) is unchanged;
- the three `sanitize` TBNZ sites moved `+0x10`, and their targets moved with
  them;
- `path_from`, `path_in`, `pattern_next_char`, `parse_shortname` all moved `+0x10`;
- the cave `0x1147D0 → 0x1147E0` is byte-identical;
- `rtld` is **unchanged** at `0x2F530` (it sits before the insertion point),
  still `b.ne`, delta `-0x4C`;
- the cross matrix confirms `23.5.0` does not match 23.0.1, 22.5.0 or the
  FAT-only 23.5.0 build, and none of those profiles match 23.5.0 either.

## Upgrading

1. Replace the KIP in `sdmc:/atmosphere/fs_overlays/` with
   `fs_codecvt_dual_unpacked.kip`, and point `fsoverlay=` at it in
   `hekate_ipl.ini` (mutually exclusive with `stock=1`).
2. Use a launcher that knows 23.5.0 (Atmosphere 1.12.2+ / hekate v6.5.5+),
   otherwise boot is refused at the package1 stage.
3. On emuMMC, `bootloader/sys/emummc.kipm` must be rebuilt against the 23.5.0
   tables; the old one black-screens.
4. First boot is best verified with the three CJK checks: directory creation,
   path lookup, and enumeration.
