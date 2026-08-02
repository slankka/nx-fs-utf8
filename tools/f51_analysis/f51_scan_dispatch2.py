#!/usr/bin/env python3
"""F51 prep 6: scan .text for codecvt dispatch via base-relative offset table.
Pattern: ldr xN, [Xm, #k] ; add xN, xN, xBASE ; blr xN
(pointer table holds base-0 text offsets; caller adds the module base).
Report the slot index k/8 and the blr address for classification."""
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

PATH = r'F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso'
data = open(PATH, 'rb').read()
text_off = struct.unpack_from('<I', data, 0x10)[0]
text_size = struct.unpack_from('<I', data, 0x14)[0]
text = data[text_off:text_off + text_size]

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
insns = list(md.disasm(text, 0))
by_addr = {i.address: i for i in insns}

slot_names = {0:'slot0_oem2uni',1:'slot1_uni2oem',2:'slot2_oem_width',
              3:'slot3_is_oem_mb',4:'slot4_uni_width',5:'slot5_is_uni_mb'}

# 1) find all blr Xn ; look back for 'add Xn, Xn, Xbase' within 4 insns ;
#    and before that 'ldr Xn, [Xm, #k]'.
found = []
for i in insns:
    if i.mnemonic != 'blr':
        continue
    reg = i.operands[0].reg
    for back in range(1, 5):
        addp = by_addr.get(i.address - 4*back)
        if addp is None:
            break
        if addp.mnemonic == 'add' and addp.operands[0].reg == reg:
            rn = addp.operands[1]
            if rn.type == 1 and rn.reg == reg and addp.operands[2].type == 1:
                base_reg = addp.operands[2].reg
                # now find ldr of same reg before add
                for back2 in range(back + 1, back + 6):
                    ldrp = by_addr.get(i.address - 4*back2)
                    if ldrp is None:
                        break
                    if ldrp.mnemonic.startswith('ldr') and ldrp.operands[0].reg == reg:
                        mem = ldrp.operands[1]
                        if mem.type == 3:
                            disp = mem.mem.disp
                            slot = disp // 8 if disp % 8 == 0 else -1
                            found.append((i.address, ldrp.address, addp.address,
                                          base_reg, disp, slot))
                        break
            break

# also 2) direct 'ldr xN,[Xm,#k]; blr xN' where the loaded value is already absolute
# (the base-0 table could also be used as 'ldr + add' OR as a plain pointer table with
# absolute values in a different table).  Also scan ldr+blr with slot index.
found2 = []
for i in insns:
    if i.mnemonic != 'blr':
        continue
    reg = i.operands[0].reg
    for back in range(1, 5):
        prev = by_addr.get(i.address - 4*back)
        if prev is None:
            break
        if prev.mnemonic.startswith('ldr') and prev.operands[0].reg == reg:
            mem = prev.operands[1]
            if mem.type == 3:
                disp = mem.mem.disp
                if disp % 8 == 0 and 0 <= disp//8 <= 5:
                    found2.append((i.address, prev.address, -1, mem.mem.base, disp, disp//8))
            break

print("=== pattern ldr+add(base)+blr (codecvt via offset table) ===")
for a, l, ad, breg, disp, slot in sorted(found):
    print(f"  blr@0x{a:06X} ldr@0x{l:06X} add@0x{ad:06X} table+0x{disp:X} -> {slot_names.get(slot,'?'+str(slot))} (base=X{breg})")
print(f"  count={len(found)}")
print("\n=== pattern ldr+blr (direct table) with slot index 0-5 ===")
for a, l, ad, breg, disp, slot in sorted(found2):
    print(f"  blr@0x{a:06X} ldr@0x{l:06X} [X{breg},#0x{disp:X}] -> {slot_names.get(slot,'?'+str(slot))}")
print(f"  count={len(found2)}")
