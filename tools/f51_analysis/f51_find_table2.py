#!/usr/bin/env python3
"""F51 prep 3: locate the PF_CHARCODE codecvt pointer table in the 19.0.1
exFAT-capable FS, then find every blr site that loads slot0 through it."""
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

PATH = r'F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso'
data = open(PATH, 'rb').read()
text_off = struct.unpack_from('<I', data, 0x10)[0]
text_size = struct.unpack_from('<I', data, 0x14)[0]
ro_off = struct.unpack_from('<I', data, 0x1C)[0]
ro_size = struct.unpack_from('<I', data, 0x20)[0]
data_off = struct.unpack_from('<I', data, 0x28)[0]
data_size = struct.unpack_from('<I', data, 0x2C)[0]
text = data[text_off:text_off + text_size]
ro = data[ro_off:ro_off + ro_size]
dsec = data[data_off:data_off + data_size]

slots = [0xFEAC0, 0xFEC30, 0xFEE00, 0xFEE40, 0xFEE90, 0xFEEA0]
deltas = [slots[i+1] - slots[i] for i in range(5)]

def scan(blob, name, blob_off):
    print(f"--- scanning {name} (0x{blob_off:X}, {len(blob)} bytes) for codecvt table ---")
    hits = []
    for i in range(0, len(blob) - 40, 8):
        vals = [struct.unpack_from('<Q', blob, i + 8*k)[0] for k in range(6)]
        if all(vals[k+1] - vals[k] == deltas[k] for k in range(5)):
            hits.append((i, vals))
    if not hits:
        print("  no exact 6-run found")
    for i, vals in hits:
        base = vals[0] - slots[0]
        print(f"  FOUND @ {name}+0x{i:X} (file 0x{blob_off+i:X})  base=0x{base:X}")
        for k in range(6):
            print(f"    slot[{k}] = 0x{vals[k]:X} -> text 0x{vals[k]-base:X}")
    # partial runs: report runs of >=3 matching deltas
    partial = 0
    for i in range(0, len(blob) - 16, 8):
        run = 1
        j = i
        while j + 8 <= len(blob) - 8 and run < 6:
            a = struct.unpack_from('<Q', blob, j)[0]
            b = struct.unpack_from('<Q', blob, j + 8)[0]
            if run - 1 < 5 and b - a == deltas[run - 1]:
                run += 1
                j += 8
            else:
                break
        if run >= 3:
            partial += 1
            vals = [struct.unpack_from('<Q', blob, i + 8*k)[0] for k in range(run)]
            base = vals[0] - slots[0]
            print(f"  partial run of {run} @ {name}+0x{i:X} (file 0x{blob_off+i:X}) base=0x{base:X}")
    print(f"  partial runs >=3: {partial}")

scan(ro, '.rodata', ro_off)
scan(dsec, '.data', data_off)
