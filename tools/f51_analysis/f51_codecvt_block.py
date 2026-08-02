#!/usr/bin/env python3
"""F51 prep 7: disassemble the 6-slot codecvt block and the region around it,
plus the single direct BL->slot0 site (0xFEE18) and its enclosing function."""
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

PATH = r'F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso'
data = open(PATH, 'rb').read()
text_off = struct.unpack_from('<I', data, 0x10)[0]
text_size = struct.unpack_from('<I', data, 0x14)[0]
text = data[text_off:text_off + text_size]
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)

def dis(start, n):
    print(f"\n--- 0x{start:X} .. 0x{start+n:X} ---")
    for i in md.disasm(text[start:start+n], start):
        print(f"  0x{i.address:06X}: {i.mnemonic:8s} {i.op_str}")

dis(0xFEAC0, 0x60)      # slot0
dis(0xFEC30, 0x60)      # slot1
dis(0xFEE00, 0x80)      # slot2 + slot3 start
dis(0xFEE18, 0x20)      # the direct BL to slot0 site

# find the function containing 0xFEE18 (walk back to a ret/b boundary)
def func_start(addr):
    a = addr
    while a > 0:
        p = struct.unpack_from('<I', text, a)[0]
        if (p & 0xFF) == 0xC0:  # RET
            return a + 4
        a -= 4
    return 0
fs = func_start(0xFEE18)
print(f"\n--- function containing 0xFEE18 starts at 0x{fs:X} ---")
dis(fs, 0xFEE18 - fs + 0x30)
