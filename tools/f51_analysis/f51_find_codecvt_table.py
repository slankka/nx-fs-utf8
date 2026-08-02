#!/usr/bin/env python3
"""F51 prep 2: locate the PF_CHARCODE codecvt function-pointer table in the
19.0.1 exFAT-capable FS and enumerate all indirect (blr) slot0 call sites."""
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

PATH = r'F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso'

# NOS0 header
data = open(PATH, 'rb').read()
text_off = struct.unpack_from('<I', data, 0x10)[0]
text_size = struct.unpack_from('<I', data, 0x14)[0]
ro_off = struct.unpack_from('<I', data, 0x1C)[0]
ro_size = struct.unpack_from('<I', data, 0x20)[0]
data_off = struct.unpack_from('<I', data, 0x28)[0]
data_size = struct.unpack_from('<I', data, 0x2C)[0]
text = data[text_off:text_off + text_size]
ro = data[ro_off:ro_off + ro_size]
data_sec = data[data_off:data_off + data_size]

# codecvt slots in .text (FsVer_19_0_0_Exfat)
slots = [0xFEAC0, 0xFEC30, 0xFEE00, 0xFEE40, 0xFEE90, 0xFEEA0]
deltas = [slots[i+1] - slots[i] for i in range(5)]
print("slot deltas:", [hex(d) for d in deltas])

# Scan data/rodata (u64 little-endian) for 6 consecutive pointers with these deltas
def find_table(blob, blob_name, blob_off):
    for i in range(0, len(blob) - 48, 8):
        vals = [struct.unpack_from('<Q', blob, i + 8*k)[0] for k in range(6)]
        # the 6 codecvt pointers: relative to an unknown base; require deltas match
        if all(vals[k+1] - vals[k] == deltas[k] for k in range(5)):
            base = vals[0] - slots[0]
            print(f"FOUND codecvt table in {blob_name} @ file 0x{blob_off + i:X}")
            print(f"  table file offset 0x{blob_off+i:X}; base = 0x{base & 0xFFFFFFFFFFFFFFFF:X}")
            for k in range(6):
                print(f"    slot[{k}] ptr = 0x{vals[k]:X} (-> text 0x{vals[k]-base:X})")
            return i, base
    return None, None

tbl_idx, base = find_table(ro, '.rodata', ro_off)
if tbl_idx is None:
    tbl_idx, base = find_table(data_sec, '.data', data_off)

if tbl_idx is None:
    print("!! codecvt table not found by delta pattern")
else:
    # Now find all blr sites in .text and identify codecvt-slot calls.
    # A slot0 call typically: ldr xN, [xM, #slot_off_in_struct] ; blr xN
    # We locate by scanning for blr and checking preceding loads from the table base.
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    # table runtime address = base + tbl location... but the pointer VALUES give us base
    # The struct address is where codecvt[0] pointer is stored (runtime) = ?
    # We don't know the runtime vaddr of the table; instead, search for ldr xN,[xM,#imm]
    # followed by blr xN, then resolve xM via preceding ADRP/ADD.
    # Simpler: search the whole .text for "blr xN" where xN was loaded via
    # 'ldr xN, [xM, #imm]' within the prior 3 instructions.
    print("\n=== blr sites loading from a struct (candidate codecvt calls) ===")
    n = 0
    for i in range(0, len(text) - 4, 4):
        inst = struct.unpack_from('<I', text, i)[0]
        if (inst & 0xFFFFFC1F) == 0xD63F0000:  # BLR Xn
            reg = (inst >> 5) & 0x1F
            # look back up to 6 instructions for ldr x<reg>, [xM, #imm]
            for j in range(i - 24, i, 4):
                p = struct.unpack_from('<I', text, j)[0]
                # LDR (unsigned imm) 64-bit: 11111001 01 imm12 Rn Rt  -> F9400000 | (imm12<<10)|(Rn<<5)|Rt
                if (p & 0xFFC00000) == 0xF9400000:
                    rt = p & 0x1F
                    rn = (p >> 5) & 0x1F
                    imm = ((p >> 10) & 0xFFF) * 8
                    if rt == reg:
                        print(f"  @0x{i:06X}: BLR X{reg}   (ldr X{reg},[X{rn},#0x{imm:X}] @0x{j:06X})")
                        n += 1
                        break
    print(f"total candidate indirect calls: {n}")
