#!/usr/bin/env python3
"""F51 prep 4: disassemble the FAT32/PrFILE2-VF path region (0xF4000-0xF8000)
of the 19.0.1 exFAT-capable FS and enumerate codecvt dispatch (ldr+blr) sites,
resolving the load base via ADRP/ADD when possible."""
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

PATH = r'F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso'
data = open(PATH, 'rb').read()
text_off = struct.unpack_from('<I', data, 0x10)[0]
text_size = struct.unpack_from('<I', data, 0x14)[0]
text = data[text_off:text_off + text_size]

slots = [0xFEAC0, 0xFEC30, 0xFEE00, 0xFEE40, 0xFEE90, 0xFEEA0]
slot_names = ['slot0_oem2uni', 'slot1_uni2oem', 'slot2_oem_width',
              'slot3_is_oem_mb', 'slot4_uni_width', 'slot5_is_uni_mb']
# codecvt table runtime address = data_base + 0xFB58 ; we don't know data_base.
# But slot pointer values are base-0 offsets.  We instead detect the dispatch by
# searching for 'ldr xN, [xM, #imm]' followed within 2 insns by 'blr xN', then
# resolve xM to the table if possible (adrp+add).  Print everything in region.

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True

def decode_adrp(inst):
    if ((inst >> 24) & 0x9F) != 0x90:
        return None
    immlo = (inst >> 29) & 3
    immhi = (inst >> 5) & 0x7FFFF
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm |= ~((1 << 21) - 1)
    return inst & 0x1F, imm

def decode_add(inst):
    if ((inst >> 31) & 1) != 1 or ((inst >> 29) & 3) != 1:
        return None
    shift = (inst >> 22) & 3
    if shift > 1: return None
    imm12 = (inst >> 10) & 0xFFF
    return (inst & 0x1F), ((inst >> 5) & 0x1F), imm12 << (shift * 12)

# collect all instructions with addresses in region
insns = list(md.disasm(text, 0))
by_addr = {i.address: i for i in insns}

def resolve_xm(iaddr, reg):
    """Walk backwards from iaddr trying to resolve register 'reg' via adrp+add
    or mov; return (kind, value) where value is page*0x1000 (adrp) or addr."""
    addr = iaddr
    for _ in range(20):
        prev = by_addr.get(addr - 4)
        if prev is None:
            break
        addr -= 4
        p = prev
        # ADRP reg, page
        if p.mnemonic == 'adrp':
            rd = p.operands[0].reg
            if rd == reg:
                imm = p.operands[1].imm
                return ('adrp', (p.address & ~0xFFF) + imm)
        # ADD reg, reg2, #imm (full)
        if p.mnemonic == 'add' and p.operands[0].reg == reg:
            op2 = p.operands[2]
            if op2.type == 2:  # IMM
                base_res = resolve_xm(addr, p.operands[1].reg)
                if base_res and base_res[0] == 'adrp':
                    return ('adrp+add', base_res[1] + op2.imm)
        # MOV reg, #imm (movz)
        if p.mnemonic in ('mov', 'movz') and p.operands[0].reg == reg:
            op1 = p.operands[1]
            if op1.type == 2:
                return ('imm', op1.imm)
        # LDR reg, [reg2, #imm]  (reg = loaded value; if reg2 resolves to table...)
        if p.mnemonic.startswith('ldr') and p.operands[0].reg == reg:
            return ('ldr', (p.operands[1].mem.base, p.operands[1].mem.disp))
    return None

REG_NAMES = {}
for i in range(31):
    REG_NAMES[i] = f'x{i}'

print("=== codecvt dispatch (ldr+blr) sites in FAT32 path region 0xF4000-0xF8000 ===")
R0, R1 = 0xF4000, 0xF8000
count = 0
for i in insns:
    if not (R0 <= i.address < R1):
        continue
    if i.mnemonic == 'blr':
        reg = i.operands[0].reg
        # find preceding ldr of same reg within 4 insns
        for back in range(1, 5):
            prev = by_addr.get(i.address - 4*back)
            if prev is None:
                break
            if prev.mnemonic.startswith('ldr') and prev.operands[0].reg == reg:
                mem = prev.operands[1]
                if mem.type == 3:  # MEM
                    base_reg = mem.mem.base
                    disp = mem.mem.disp
                    res = resolve_xm(prev.address, base_reg)
                    print(f"@0x{i.address:06X} BLR {REG_NAMES[reg]}  <-  {prev.mnemonic} {REG_NAMES[reg]},[{REG_NAMES[base_reg]},#0x{disp:X}]  base_res={res}")
                    count += 1
                break
print(f"total dispatch sites in region: {count}")
