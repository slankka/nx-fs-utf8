#!/usr/bin/env python3
"""F51 prep: verify NOS0 FS_proper.nso matches the FsVer_19_0_0_Exfat offset
table and enumerate all codecvt[0] (oem2unicode, 0xFEAC0) call sites."""
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

PATH = r'F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso'

def parse_nos0(data):
    assert data[0:4] in (b'NSO0', b'NOS0'), data[0:4]
    if data[0:4] == b'NOS0':
        # NOS0 (Wii U style): +0x10 text_off, +0x14 text_size,
        # +0x1C ro_off, +0x20 ro_size, +0x28 data_off, +0x2C data_size,
        # +0x30 bss_size
        return {
            'text_off': struct.unpack_from('<I', data, 0x10)[0],
            'text_size': struct.unpack_from('<I', data, 0x14)[0],
            'ro_off': struct.unpack_from('<I', data, 0x1C)[0],
            'ro_size': struct.unpack_from('<I', data, 0x20)[0],
            'data_off': struct.unpack_from('<I', data, 0x28)[0],
            'data_size': struct.unpack_from('<I', data, 0x2C)[0],
            'bss_size': struct.unpack_from('<I', data, 0x30)[0],
        }
    else:
        return {
            'text_off': struct.unpack_from('<I', data, 0x10)[0],
            'text_size': struct.unpack_from('<I', data, 0x18)[0],
            'ro_off': struct.unpack_from('<I', data, 0x20)[0],
            'ro_size': struct.unpack_from('<I', data, 0x28)[0],
            'data_off': struct.unpack_from('<I', data, 0x30)[0],
            'data_size': struct.unpack_from('<I', data, 0x38)[0],
            'bss_size': struct.unpack_from('<I', data, 0x3C)[0],
        }

data = open(PATH, 'rb').read()
h = parse_nos0(data)
print(f"magic={data[0:4].decode()} text_off=0x{h['text_off']:X} text_size=0x{h['text_size']:X} "
      f"ro_off=0x{h['ro_off']:X} ro_size=0x{h['ro_size']:X} data_off=0x{h['data_off']:X} "
      f"data_size=0x{h['data_size']:X} bss=0x{h['bss_size']:X}")
print(f"file size = 0x{len(data):X}")

text = data[h['text_off']:h['text_off'] + h['text_size']]
print(f"text len = 0x{len(text):X}")

# Offset table (FsVer_19_0_0_Exfat) — relative to .text start
codecvt0 = 0xFEAC0
path_from = 0xF5840
path_in = 0xF5960
pattern = 0xF44E0
parse_shortname = 0xF5AC0
dir_hook = 0xD4AF4

# Verify codecvt[0] entry signature {0x39C00008, 0x12001D0A} (ldrsb w8,[x0]/and w11,w8,#0xff)
w0 = struct.unpack_from('<I', text, codecvt0)[0]
w1 = struct.unpack_from('<I', text, codecvt0 + 4)[0]
print(f"\ncodecvt[0] @0x{codecvt0:X}: {w0:08X} {w1:08X}  (expect 39C00008 12001D0A) -> {'MATCH' if (w0==0x39C00008 and w1==0x12001D0A) else 'MISMATCH'}")

# dir_hook opcode
dw = struct.unpack_from('<I', text, dir_hook)[0]
print(f"dir_hook @0x{dir_hook:X}: {dw:08X}  (expect 54FFFCE3) -> {'MATCH' if dw==0x54FFFCE3 else 'MISMATCH'}")

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = False

def bl_targets_to(text, target_off):
    """Find all BL/BR sites whose target == target_off (offset in .text)."""
    sites = []
    for i in range(0, len(text) - 4, 4):
        inst = struct.unpack_from('<I', text, i)[0]
        opc = (inst >> 26) & 0x3F
        if opc == 0x25:  # BL
            imm26 = inst & 0x3FFFFFF
            if imm26 & (1 << 25):
                imm26 |= ~((1 << 26) - 1)
            t = i + imm26 * 4
            if t == target_off:
                sites.append(i)
        elif opc == 0x05:  # B
            imm26 = inst & 0x3FFFFFF
            if imm26 & (1 << 25):
                imm26 |= ~((1 << 26) - 1)
            t = i + imm26 * 4
            if t == target_off:
                sites.append(i)
    return sites

def bl_targets_in_range(text, start, end):
    """All BL targets within [start,end) in .text."""
    out = []
    for i in range(start, end - 3, 4):
        inst = struct.unpack_from('<I', text, i)[0]
        opc = (inst >> 26) & 0x3F
        if opc == 0x25:  # BL
            imm26 = inst & 0x3FFFFFF
            if imm26 & (1 << 25):
                imm26 |= ~((1 << 26) - 1)
            out.append((i, (i + imm26 * 4) & 0xFFFFFFFF))
    return out

# All direct callers of codecvt[0] (slot0) across .text
slot0_callers = bl_targets_to(text, codecvt0)
print(f"\n=== ALL direct callers of codecvt[0]=oem2unicode @0x{codecvt0:X}: {len(slot0_callers)} ===")
for s in slot0_callers:
    print(f"  BL @ 0x{s:06X}")

# Callers of codecvt[0] within / near the FAT32 path routines
print(f"\n=== slot0 callers inside/after FAT32 path functions ===")
fat_regions = [
    ('transformFromUnicodeToNormal', path_from, path_from + 0x200),
    ('transformInUnicode', path_in, path_in + 0x200),
    ('parseShortName', parse_shortname, parse_shortname + 0x300),
    ('pattern_region', pattern, pattern + 0x300),
]
for name, s, e in fat_regions:
    hits = [x for x in slot0_callers if s <= x < e]
    print(f"  {name} @0x{s:X}-0x{e:X}: {[hex(x) for x in hits]}")

# All BLs from the FAT32 path functions to ANY codecvt slot
print(f"\n=== BL targets from FAT32 path functions ===")
for name, s, e in fat_regions:
    print(f"  -- {name} @0x{s:X} --")
    for i, t in bl_targets_in_range(text, s, e):
        print(f"    @0x{i:06X} -> 0x{t:06X}")
