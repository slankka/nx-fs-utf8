#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 slankka
"""
Host-side replica of fs_codecvt's matches_fs() + a near-miss reporter.

Purpose
-------
fs_codecvt decides "which FS version is this?" purely from opcode guards in
source/main.cpp.  When a table *almost* matches it still returns true, and the
result is a black screen instead of a graceful skip.  This tool replays the
exact same guard set offline so a variant FS can be classified before it is
ever booted.

Usage
-----
  python tools/check_offsets.py <FS.kip1 | FS.text.bin | nsо> --profile 23.0.1
  python tools/check_offsets.py <file> --profile 23.0.1 --window 64
  python tools/check_offsets.py <file> --list

--window N   for every failing guard, search +-N instructions (words) for the
             expected opcode and report the delta.  This tells you whether a
             variant is a uniform shift (all deltas equal) or a real recompile.

Exit code: 0 = MATCH, 1 = NO MATCH, 2 = bad input.
"""

import argparse
import struct
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Offset tables (mirrors source/fs_offsets.cpp).
# Only the exFAT-capable variants used by fs_codecvt are listed.
# ---------------------------------------------------------------------------

UNI2OEM_CODE_SIZE = 0x130


def _mk(codecvt, sanitize, dir_hook, dir_reject, dir_ascii, dir_scan,
        regs, entry, dir_op, path_from, path_from_op, path_in, path_in_op,
        pattern, pattern_op, ident, sfn, sfn_op, cave=None, rtld=None):
    name_reg, bound_reg, byte_reg = regs
    if cave is None:
        cave = codecvt[1] + UNI2OEM_CODE_SIZE
    return {
        "codecvt": codecvt,
        "sanitize": sanitize,
        "dir_hook": dir_hook,
        "dir_reject": dir_reject,
        "dir_ascii_checks": dir_ascii,
        "dir_scan_continue": dir_scan,
        "regs": (name_reg, bound_reg, byte_reg),
        "cave": cave,
        "cave_size": codecvt[2] - cave,
        "codecvt_entry": entry,
        "dir_hook_opcode": dir_op,
        "path_from_unicode": path_from,
        "path_from_entry": path_from_op,
        "path_in_unicode": path_in,
        "path_in_entry": path_in_op,
        "pattern_next_char": pattern,
        "pattern_entry": pattern_op,
        "identity_checks": ident,
        "parse_shortname_entry": sfn,
        "parse_shortname_entry_opcode": sfn_op,
        "rtld": rtld,
    }


PROFILES = {
    "19.0.1": _mk(
        [0xFEAC0, 0xFEC30, 0xFEE00, 0xFEE40, 0xFEE90, 0xFEEA0],
        [0xF5888, 0xF5B48, 0xF6638],
        0xD4AF4, 0xD4A90, 0xD4AF8, 0xD4B20,
        (25, 19, 9),
        (0x39C00008, 0x12001D0A), 0x54FFFCE3,
        0xF5840, 0xD10143FF, 0xF5960, 0xA9BC7BFD,
        0xF44E0, 0xD10103FF,
        [(0xF4D68, 0x54000261), (0xF5EE0, 0xF9400F48), (0xF5EE4, 0xD63F0100),
         (0x108510, 0x97FFB288), (0x1085A8, 0x2A0003F5), (0x1086BC, 0x52800055)],
        0xF5AC0, 0xA9BA7BFD,
        rtld=(0x275F0, 0x54FFFD81, -0x50)),
    "20.2.0": _mk(
        [0x109440, 0x1095B0, 0x109780, 0x1097C0, 0x109810, 0x109820],
        [0x100618, 0x1008D8, 0x1013C8],
        0xDE6B4, 0xDE650, 0xDE6B8, 0xDE6E0,
        (25, 19, 9),
        (0x39C00008, 0x12001D0A), 0x54FFFCE3,
        0x1005D0, 0xD10143FF, 0x1006F0, 0xA9BC7BFD,
        0xFF270, 0xD10103FF,
        [(0x1005D4, 0xA9017BFD), (0x1005E4, 0x910043FD), (0x100704, 0x39400028),
         (0xFF2A0, 0x7100053F), (0x10086C, 0xD108C3FF), (0x100890, 0x940363A0)],
        0x100850, 0xA9BA7BFD,
        rtld=(0x2B594, 0x54FFFDA1, -0x4C)),
    "21.2.0": _mk(
        [0x10ECC0, 0x10EE10, 0x10EFE0, 0x10F020, 0x10F070, 0x10F080],
        [0, 0, 0],
        0xE48D0, 0xE4864, 0xE48D4, 0xE48C0,
        (28, 9, 10),
        (0x39C00008, 0x12001D0B), 0x54FFFCA3,
        0x105ED0, 0xD10103FF, 0x105FE0, 0xA9BC7BFD,
        0x104BA0, 0xD10103FF,
        [(0x105ED4, 0xA9017BFD), (0x105EE4, 0x528005C8), (0x105FF4, 0x39400028),
         (0x104BC4, 0x7100053F), (0x10615C, 0xD10903FF), (0x106180, 0x94035E70)],
        0x106140, 0xA9BA7BFD,
        rtld=(0x2E1C0, 0x54FFFDA1, -0x4C)),
    "22.0.0": _mk(
        [0x111520, 0x111670, 0x111840, 0x111880, 0x1118D0, 0x1118E0],
        [0x108784, 0x108A30, 0x109584],
        0xE7040, 0xE70C0, 0xE7044, 0xE7088,
        (26, 24, 9),
        (0x39C00008, 0x12001D0B), 0x54000409,
        0x108740, 0xD10103FF, 0x108850, 0xA9BC7BFD,
        0x107410, 0xD10103FF,
        [(0x108744, 0xA9017BFD), (0x108754, 0x528005C8), (0x108864, 0x39400028),
         (0x107434, 0x7100053F), (0x1089CC, 0xD10903FF), (0xE70C0, 0xD29FBEE1)],
        0x1089B0, 0xA9BA7BFD,
        rtld=(0x2DED0, 0x54FFFDA1, -0x4C)),
    "22.5.0": _mk(
        [0x111520, 0x111670, 0x111840, 0x111880, 0x1118D0, 0x1118E0],
        [0x108784, 0x108A30, 0x109584],
        0xE7040, 0xE70C0, 0xE7044, 0xE7088,
        (26, 24, 9),
        (0x39C00008, 0x12001D0B), 0x54000409,
        0x108740, 0xD10103FF, 0x108850, 0xA9BC7BFD,
        0x107410, 0xD10103FF,
        [(0x108744, 0xA9017BFD), (0x108754, 0x528005C8), (0x108864, 0x39400028),
         (0x107434, 0x7100053F), (0x1089CC, 0xD10903FF), (0xE70C0, 0xD28A9041)],
        0x1089B0, 0xA9BA7BFD,
        rtld=(0x2DED0, 0x54FFFDA1, -0x4C)),
    "23.0.1": _mk(
        [0x114550, 0x1146A0, 0x114870, 0x1148B0, 0x114900, 0x114910],
        [0x10B7B4, 0x10BA60, 0x10C5B4],
        0xEA070, 0xEA0F0, 0xEA074, 0xEA0B8,
        (26, 24, 9),
        (0x39C00008, 0x12001D0B), 0x54000409,
        0x10B770, 0xD10103FF, 0x10B880, 0xA9BC7BFD,
        0x10A440, 0xD10103FF,
        [(0x10B774, 0xA9017BFD), (0x10B784, 0x528005C8), (0x10B894, 0x39400028),
         (0x10A464, 0x7100053F), (0x10B9FC, 0xD10903FF), (0xEA0F0, 0xD2822461)],
        0x10B9E0, 0xA9BA7BFD,    # FAT32-only (non-exFAT-capable) FS.  Values from
        rtld=(0x2F530, 0x54FFFDA1, -0x4C)),
    # Atmosphere/stratosphere/fs_codecvt/source/fs_offsets.cpp.
    "19.0.1-FAT": _mk(
        [0xECD20, 0xECE90, 0xED060, 0xED0A0, 0xED0F0, 0xED100],
        [0xFA458, 0xFA658, 0xFB148],
        0xD4A94, 0xD4A30, 0xD4A98, 0xD4AC0,
        (25, 19, 9),
        (0x39C00008, 0x12001D0A), 0x54FFFCE3,
        0xFA410, 0xD10143FF, 0xFA530, 0xA9BC7BFD,
        0xF9190, 0xD10103FF,
        [(0xF9938, 0x54000261), (0xFA9F0, 0xF9400F48), (0xFA9F4, 0xD63F0100),
         (0xF5D5C, 0x94000F69), (0xF5DF4, 0x2A0003F5), (0xF5EB0, 0x52800055)],
        0xFA5D0, 0xA9BA7BFD, cave=0xECF44,
        rtld=(0x275F0, 0x54FFFD81, -0x50)),}


# ---------------------------------------------------------------------------
# BLZ (Nintendo "BLZ" backward LZ) decompressor, mirroring BlzUncompress().
# ---------------------------------------------------------------------------

def _find_blz_footer(blob: bytes, expected_size: int):
    """Locate the 12-byte BLZ footer and the start of the BLZ stream.

    The kernel is called with `binary_size = section.size_comp` and derives
    `cmp_start = (section_data + size_comp) - total_size`.  So the section blob
    is:

        [ prefix (size_comp - total) ][ BLZ stream (total) ]

    and the decompressed image is `prefix + decompressed`, which is exactly
    `size_comp + additional` bytes.  That identity is the reliable check.
    """
    end = len(blob)
    total, footer, additional = struct.unpack_from("<III", blob, end - 12)
    prefix = end - total
    if total == 0 or footer > total or prefix < 0:
        raise ValueError(f"bad BLZ footer (total=0x{total:X} footer=0x{footer:X} "
                         f"blob=0x{end:X})")
    return prefix, end, total, footer, additional


def blz_uncompress(src: bytes, expected_size: int) -> bytes:
    prefix, end, total, footer, additional = _find_blz_footer(src, expected_size)
    produced = len(src) + additional
    if expected_size and produced != expected_size:
        print(f"  !! SECTION SIZE MISMATCH: section blob 0x{len(src):X} + additional "
              f"0x{additional:X} = 0x{produced:X}, header declares 0x{expected_size:X}")
        print("  !! Offsets below are NOT trustworthy.")

    # The kernel decompresses in place inside a page-aligned segment, so a
    # back-reference may legitimately read past `total + additional`.  Pad the
    # scratch buffer and treat the padding as zero instead of faulting.
    buf = bytearray(src[prefix:end])
    buf.extend(b"\x00" * (additional + 0x4000))
    limit = len(buf)

    cmp_ofs = total - footer
    out_ofs = total + additional

    while out_ofs:
        cmp_ofs -= 1
        control = buf[cmp_ofs]
        for _ in range(8):
            if not out_ofs:
                break
            if control & 0x80:
                cmp_ofs -= 2
                seg = buf[cmp_ofs] | (buf[cmp_ofs + 1] << 8)
                seg_ofs = (seg & 0xFFF) + 3
                seg_size = min(((seg >> 12) & 0xF) + 3, out_ofs)
                out_ofs -= seg_size
                for j in range(seg_size):
                    si = out_ofs + seg_ofs + j
                    buf[out_ofs + j] = buf[si] if si < limit else 0
            else:
                cmp_ofs -= 1
                out_ofs -= 1
                buf[out_ofs] = buf[cmp_ofs]
            control = (control << 1) & 0xFF

    # The bytes before cmp_start are untouched by the decompressor.
    out = bytes(src[:prefix]) + bytes(buf[:total + additional])
    if expected_size and len(out) != expected_size:
        print(f"  !! SECTION SIZE MISMATCH: BLZ produced 0x{len(out):X}, KIP1 header "
              f"declares 0x{expected_size:X}")
        print("  !! This dump was almost certainly re-packed by a script. Re-extract "
              "with:")
        print("  !!   hactool -k prod.keys -t ini1 --outdir=OUT <INI1.bin>")
        print("  !! Offsets below are NOT trustworthy.")
    return out

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

KIP1_MAGIC = b"KIP1"


NSO_MAGICS = (b"NSO0", b"NOS0")


def load_nso(path: Path, data: bytes) -> bytes:
    """Extract the .text segment of an NSO0 / NOS0 executable.

    Layouts differ between the two magics:
      NSO0: 0x10 text_offset, 0x18 text_size
      NOS0: 0x10 text_offset, 0x14 text_size   (older dumps, e.g. 19.0.1)
    The text segment is stored uncompressed in both, so this bypasses the
    fragile BLZ path entirely and is the preferred input for verification.
    """
    magic = data[:4]
    text_off = struct.unpack_from("<I", data, 0x10)[0]
    if magic == b"NSO0":
        text_size = struct.unpack_from("<I", data, 0x18)[0]
    else:
        text_size = struct.unpack_from("<I", data, 0x14)[0]
    end = text_off + text_size
    if end > len(data):
        raise SystemExit(f"{path.name}: text segment 0x{end:X} exceeds file 0x{len(data):X}")
    print(f"{path.name}: {magic.decode()} text @0x{text_off:X} size 0x{text_size:X}")
    return data[text_off:end]


def load_text(path: Path) -> bytes:
    data = path.read_bytes()

    if data[:4] in NSO_MAGICS:
        return load_nso(path, data)

    if data[:4] != KIP1_MAGIC:
        print(f"{path.name}: raw .text image, 0x{len(data):X} bytes")
        return data

    name = data[4:16].split(b"\x00")[0].decode("ascii", "replace")
    tid = struct.unpack_from("<Q", data, 0x10)[0]
    flags = data[0x1F]
    print(f"{path.name}: KIP1 name={name!r} tid=0x{tid:016X} flags=0x{flags:02X}")

    off, dec, comp, _attr = struct.unpack_from("<IIII", data, 0x20)
    print(f"  .text offset=0x{off:X} decomp=0x{dec:X} comp=0x{comp:X} "
          f"compressed={bool(flags & 1)}")

    if comp == 0:
        raise SystemExit(f"{path.name}: .text section is empty")

    blob = data[0x100 + off: 0x100 + off + comp]
    if len(blob) != comp:
        raise SystemExit(f"{path.name}: truncated .text ({len(blob)} != {comp})")

    text = blob if not (flags & 1) else blz_uncompress(blob, dec)
    print(f"  decompressed .text = 0x{len(text):X} bytes")
    return text


def u32(text: bytes, off: int):
    if off + 4 > len(text):
        return None
    return struct.unpack_from("<I", text, off)[0]


# ---------------------------------------------------------------------------
# Guard replay (mirrors matches_fs() in source/main.cpp)
# ---------------------------------------------------------------------------

def collect_guards(p):
    """Yield (label, offset, expected, kind) for every exact check."""
    g = []
    g.append(("codecvt[0].insn0", p["codecvt"][0], p["codecvt_entry"][0], "eq"))
    g.append(("codecvt[0].insn1", p["codecvt"][0] + 4, p["codecvt_entry"][1], "eq"))
    g.append(("dir_hook", p["dir_hook"], p["dir_hook_opcode"], "eq"))
    g.append(("path_from_unicode", p["path_from_unicode"],
              p["path_from_entry"], "eq"))
    g.append(("path_in_unicode", p["path_in_unicode"], p["path_in_entry"], "eq"))
    g.append(("pattern_next_char", p["pattern_next_char"],
              p["pattern_entry"], "eq"))
    for i, (off, op) in enumerate(p["identity_checks"]):
        g.append((f"identity[{i}]", off, op, "eq"))
    g.append(("parse_shortname", p["parse_shortname_entry"],
              p["parse_shortname_entry_opcode"], "eq"))
    if p.get("rtld"):
        g.append(("rtld", p["rtld"][0], p["rtld"][1], "eq"))
        g.append(("rtld.delta", p["rtld"][0], p["rtld"][2], "bcond"))
    for i, off in enumerate(p["sanitize"]):
        if off:
            g.append((f"sanitize[{i}]", off, 0x37000000, "tbnz"))
    return g


def check(text: bytes, profile: dict, window: int):
    guards = collect_guards(profile)

    print("\n--- exact guards (what makes the KIP decide to hook) ---")
    ok_all = True
    for label, off, expected, kind in guards:
        actual = u32(text, off)
        if actual is None:
            print(f"  {label:22s} @0x{off:06X}  OUT OF RANGE")
            ok_all = False
            continue
        if kind == "eq":
            ok = actual == expected
        elif kind == "bcond":
            imm19 = (actual >> 5) & 0x7FFFF
            if imm19 & 0x40000:
                imm19 -= 0x80000
            ok = imm19 * 4 == expected
        else:
            ok = (actual & 0x7F000000) == 0x37000000   # TBNZ family
        if not ok:
            ok_all = False

        mark = "OK  " if ok else "FAIL"
        line = f"  {label:22s} @0x{off:06X}  got 0x{actual:08X}  want 0x{expected:08X}  {mark}"

        if not ok and window > 0:
            found = []
            for d in range(-window, window + 1):
                if d == 0:
                    continue
                probe = u32(text, off + d * 4)
                if probe is None:
                    continue
                hit = (probe == expected) if kind == "eq" else \
                      ((probe & 0x7F000000) == 0x37000000)
                if hit:
                    found.append(d)
            if found:
                deltas = ", ".join(f"{d:+d}" for d in found[:8])
                line += f"   nearest match at word delta: {deltas}"
            else:
                line += f"   no match within +-{window} words"
        print(line)

    print("\n--- per-slot opcodes (NOT guarded today: a wrong value here still "
          "passes matches_fs and then hooks mid-function) ---")
    for i, off in enumerate(profile["codecvt"]):
        print(f"  codecvt[{i}] @0x{off:06X}  op=0x{u32(text, off) or 0:08X}")
    for i, off in enumerate(profile["sanitize"]):
        print(f"  sanitize[{i}] @0x{off:06X}  op=0x{u32(text, off) or 0:08X}")
    cave_op = u32(text, profile["cave"])
    print(f"  cave @0x{profile['cave']:06X} size=0x{profile['cave_size']:X} "
          f"op=0x{cave_op or 0:08X}")

    print(f"\nregs: name=x{profile['regs'][0]} bound=x{profile['regs'][1]} "
          f"byte=w{profile['regs'][2]}")
    print("\nRESULT:", "MATCH (KIP would hook this image)" if ok_all
          else "NO MATCH (KIP skips, FS boots unmodified)")
    return ok_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--profile", default="23.0.1")
    ap.add_argument("--window", type=int, default=64,
                    help="instructions to search around a failing guard")
    ap.add_argument("--list", action="store_true", help="list profiles and exit")
    args = ap.parse_args()

    if args.list:
        print("profiles:", ", ".join(PROFILES))
        return 0

    if args.profile not in PROFILES:
        print(f"unknown profile {args.profile!r}; have {list(PROFILES)}")
        return 2

    text = load_text(args.image)
    print(f"\nprofile: {args.profile} (exFAT-capable FS variant)")
    ok = check(text, PROFILES[args.profile], args.window)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
