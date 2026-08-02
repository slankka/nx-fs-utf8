#!/usr/bin/env python3
"""F51 prep 5: full-.text scan for codecvt-table dispatch sites.

codecvt table (slot0 ptr) found at .data+0xFB58 (file 0x24FB58).
.text starts at NOS0 file 0x1000, so table relative-to-text = 0x24EB58.
We scan all 'ldr xN,[Xm,#imm]' + 'blr xN' pairs in .text, resolve Xm via
ADRP/ADD backwards, and report sites whose resolved base == 0x24EB58 area.
Also report the slot index (imm/8) to identify which codecvt slot is called.
"""
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

PATH = r'F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso'
data = open(PATH, 'rb').read()
text_off = struct.unpack_from('<I', data, 0x10)[0]
text_size = struct.unpack_from('<I', data, 0x14)[0]
text = data[text_off:text_off + text_size]

TABLE_REL = 0x24FB58 - 0x1000  # relative to .text start
print(f"codecvt table relative-to-text = 0x{TABLE_REL:X}")

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
insns = list(md.disasm(text, 0))
by_addr = {i.address: i for i in insns}

def resolve(addr, reg, depth=0):
    """resolve register 'reg' at 'addr' backwards to an absolute .text-relative
    address (via adrp+add) or None."""
    if depth > 24:
        return None
    a = addr
    while a > 0:
        p = by_addr.get(a - 4)
        if p is None:
            break
        a -= 4
        if p.mnemonic == 'adrp':
            if p.operands[0].reg == reg:
                return (p.address & ~0xFFF) + p.operands[1].imm
        elif p.mnemonic == 'add' and p.operands[0].reg == reg:
            op2 = p.operands[2]
            if op2.type == 2:  # imm
                r = resolve(a, p.operands[1].reg, depth + 1)
                if r is not None:
                    return r + op2.imm
        elif p.mnemonic in ('mov', 'movz') and p.operands[0].reg == reg:
            if p.operands[1].type == 2:
                return p.operands[1].imm
        elif p.mnemonic == 'movk' and p.operands[0].reg == reg:
            r = resolve(a, reg, depth + 1)
            if r is not None:
                return r | p.operands[1].imm
        # stop at function boundaries (ret / b) roughly
        if p.mnemonic in ('ret', 'b'):
            return None
    return None

REG = ['x%d' % i for i in range(31)]
slot_names = {0:'slot0_oem2uni',1:'slot1_uni2oem',2:'slot2_oem_width',
              3:'slot3_is_oem_mb',4:'slot4_uni_width',5:'slot5_is_uni_mb'}

hits = []
for i in insns:
    if i.mnemonic != 'blr':
        continue
    reg = i.operands[0].reg
    for back in range(1, 6):
        prev = by_addr.get(i.address - 4*back)
        if prev is None:
            break
        if prev.mnemonic.startswith('ldr') and prev.operands[0].reg == reg:
            mem = prev.operands[1]
            if mem.type == 3:
                base = resolve(prev.address, mem.mem.base)
                disp = mem.mem.disp
                if base is not None:
                    addr = base + disp
                    if 0x24E000 <= addr <= 0x24F000:
                        slot = disp // 8 if (disp % 8 == 0) else -1
                        hits.append((i.address, prev.address, addr, disp, reg, slot))
            break

print(f"\n=== codecvt dispatch sites (table @0x{TABLE_REL:X}) : {len(hits)} ===")
for a, l, taddr, disp, reg, slot in sorted(hits):
    name = slot_names.get(slot, f'??slot{slot}')
    print(f"  blr @0x{a:06X}  ldr@{l:06X}  table+0x{disp:X} -> {name}  (X{reg})")
