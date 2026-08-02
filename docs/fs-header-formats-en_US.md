# FS Header Formats: KIP1 / NSO0 / NOS0 — from the real-firmware angle

> Scope: FS sysmodule of HOS 19.0.1 ~ 22.5.0 (exFAT-capable variant)
> Date: 2026-08-03
> Every layout below was measured from real firmware extraction artifacts under
> `F:\dumped_firmware` — not theoretical speculation.

## 1. Core conclusion: what FS actually is in real firmware

**In real firmware, FS is `FS.kip1` — the KIP1 format (Nintendo official)** —
not NSO0 and not NOS0.

Firmware chain:

```
NCA (firmware container)
  └─ package2 (pk21)          ← compressed blob read at boot
       └─ INI1 (contains KIP1 modules: FS/Loader/NCM/sm/...)
            └─ FS.kip1        ← FS's real form (compressed KIP1)
                 ├─ FS_decomp.kip1   ← decompressed KIP1 (for analysis)
                 └─ FS_proper.nso    ← tool-converted "NSO-like" (for disasm)
```

- **`FS.kip1`**: the real firmware form with Nintendo's official KIP1 header.
- **`FS_proper.nso`**: a flat file produced by local tools (e.g.
  `kip1_to_nso.py`) from the decompressed KIP1. Its magic may be **NSO0 or
  NOS0** and its segment layout varies by tool — it is only an analysis
  artifact, **not** the original firmware format.

## 2. KIP1 header layout (real firmware format, measured on 22.5.0 exFAT)

The KIP1 header is 0x100 bytes; each segment descriptor is 0x10 bytes:

| Offset | Field | Measured value (22.5.0 FS.kip1) |
|---|---|---|
| 0x00 | magic `"KIP1"` | `4B 49 50 31` |
| 0x04 | name[12] | `"FS"` (module name) |
| 0x10 | title_id (u64) | `0x0100000000000000` |
| 0x20 | .text: file_off / decomp_size / attrib / rsvd | off=0, size=`0x1E5CE4` |
| 0x30 | .rodata | off=`0x1E6000`, size=`0x6A4C0` |
| 0x40 | .data | off=`0x251000`, size=`0x1F558` |
| 0x50 | .bss | off=`0x271000`, size=`0xD9B000` |
| 0x100 | .text data starts here (contiguous after decompression) | — |

Key points:

- **KIP1 segments are individually compressed in the file** (`FS.kip1` is the
  compressed state); `file_off` is the logical offset *before* compression.
- **`FS_decomp.kip1`** = the decompressed KIP1: segments are contiguous from
  0x100, so `.text` is directly readable.
- Once the KIP loader (fusee/Atmosphere) maps the KIP1 into memory, `.text` is
  the FS code segment we patch.

## 3. Tool artifacts: two magics (NSO0 / NOS0), three header layouts

Analysis tools convert the decompressed KIP1 into "NSO-like" files. Measured
artifacts show **two magics and three segment-table layouts**:

| Layout | magic | Segment-table arrangement | Seen in |
|---|---|---|---|
| **A. Standard NSO0** | `NSO0` `4E 53 4F 30` | text@0x10/size@0x14, rodata@0x18/size@0x1C, data@0x20/size@0x24, bss@0x28 | official NSO; some tools |
| **B. kip1_to_nso 3×u32** | `NOS0` `4E 4F 53 30` | text@0x10/size@0x14/0@0x18, rodata@0x1C/size@0x20/0@0x24, data@0x28/size@0x2C, bss@0x30 | 19.0.1 `FS_proper.nso` |
| **C. 8-byte-aligned variant** | `NSO0` | text@0x10, **size@0x18** (0x14=0), rodata@0x20… | 20.2.0 `FS_proper.nso` |

Key facts:

- **Magic and layout do not map 1:1**: 19.0.1 and 22.5.0 are both `NOS0`, yet
  19.0.1 uses the 3×u32 layout (B) while 22.5.0 (the `FS_proper.nso` generated
  by this repo's tool) uses the standard layout (A).
- **`NOS0` is not a Nintendo-official format**: it is produced when a tool
  writes `0x30534F4E` with little-endian packing, which lands on disk as
  `4E 4F 53 30` (the 'O'/'S' are swapped). The author intended NSO0, but the
  file bytes read NOS0; some tools also customize the segment-table order.
- **`NSO0` (standard layout A) is the only "official" NSO**: official tools
  such as Atmosphere's `utilities/nxo64.py` only accept `NSO0`.

## 4. Actual form of FS per version (measured)

| Version | Real firmware form | Decompressed | Tool NSO artifact |
|---|---|---|---|
| 19.0.1 | `FS.kip1` | — | `FS_proper.nso` (NOS0, layout B 3×u32) |
| 20.2.0 | `FS.kip1` | — | `FS_proper.nso` (NSO0, layout C, text size@0x18) |
| 21.2.0 | `FS.kip1` | — | `FS.nso` (actually a KIP1) |
| 22.0.0 | `FS.kip1` | `FS_decomp.kip1` | — |
| 22.5.0 | `FS.kip1` | `FS_decomp.kip1` | `FS_proper.nso` (NOS0, layout A standard) |

## 5. So which one wins?

- **Answering "is FS a FS.kip1, an NSO0, or something else"**: in real firmware
  FS **is `FS.kip1` (KIP1)**; NSO0/NOS0 are all tool-converted copies.
- **For the KIP at runtime**: completely irrelevant. Our KIP uses
  `matches_fs()` to match opcodes against the **already-loaded FS code in
  memory** to find the six slots — it **never parses any container header**.
  So the NSO0/NOS0/KIP1 differences only affect offline analysis scripts.
- **For offline scripts**: you must branch by magic and adapt the layout:
  - KIP1 → read the 0x20 segment table; `.text` starts at 0x100;
  - NSO0/NOS0 → `text size = @0x14`; if 0, fall back to `@0x18`.
  (`verify_all_versions.py::load_text()` already does this.)

## 6. Lessons learned

- To identify which variant an FS file is: read the ExFAT-capable six-slot
  offset `@0x111520` and check whether it equals `0x39C00008`; if so it is the
  ExFAT-capable variant, otherwise check the FAT six-slot `@0x1001D0`.
- On 22.x, the **FAT variant and the ExFAT-capable variant have different
  offsets** (FAT: six-slot 0x1001D0 / dir 0xE6F80; exFAT: six-slot 0x111520 /
  dir 0xE7040) — do not mix them up.
- The magic comment in `kip1_to_nso.py` has been corrected: `0x30534F4E`
  little-endian lands on disk as `NOS0`, not `NSO0`.
