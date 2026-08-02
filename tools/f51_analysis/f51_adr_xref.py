#!/usr/bin/env python3
"""Find ADR (PC-relative) xrefs to the 'EXFAT'/'FAT32' signature strings and to
the filesystem-type name table, plus any ADRP+ADD combos, in .text."""
import struct

PATH = r'F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso'
data = open(PATH, 'rb').read()
text_off = struct.unpack_from('<I', data, 0x10)[0]
text_sz = struct.unpack_from('<I', data, 0x14)[0]
text = data[text_off:text_off + text_sz]

# target rel addresses (runtime) for the strings
targets = {
    'EXFAT@0x1DFF25': 0x1DFF25,
    'FAT32@0x1DFC51': 0x1DFC51,
    'FAT16@0x1DFF1A': 0x1DFF1A,
    'EXFAT@0x1CCA63': 0x1CCA63,
}


def decode_adr(inst):
    """ADR Xd, #imm: 1 0 0 0 0 immlo immhi Rd ; imm = (immhi<<2)|immlo, signed."""
    if ((inst >> 31) & 1) != 1 or ((inst >> 24) & 0x1F) != 0:  # 64-bit, op==0
        if ((inst >> 24) & 0x9F) != 0x90:
            return None
    # ADR: bit31=1, bits[28:24]=0b00000, bit23=0 (ADRP has bit31=1, [28:24]=0b10000)
    if ((inst >> 24) & 0x1F) != 0:
        return None
    if ((inst >> 23) & 1) != 0:
        return None
    immlo = (inst >> 29) & 3
    immhi = (inst >> 5) & 0x7FFFF
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm |= ~((1 << 21) - 1)
    return (inst & 0x1F), imm


for name, tgt in targets.items():
    hits = []
    for i in range(0, len(text) - 4, 4):
        inst = struct.unpack_from('<I', text, i)[0]
        r = decode_adr(inst)
        if r is None:
            continue
        rd, imm = r
        if (i + imm) & 0xFFFFFFFF == tgt:
            hits.append((i, rd))
    print('%s: %d adr hits -> %s' % (name, len(hits),
                                     ', '.join('@0x%06X x%d' % (a, rd) for a, rd in hits[:8])))

# also: ADRP (page) targeting the page of 0x1DFF25 (0x1DF000) and 0x1DFC51 (0x1DF000)
def decode_adrp(inst):
    if ((inst >> 24) & 0x9F) != 0x90:
        return None
    immlo = (inst >> 29) & 3
    immhi = (inst >> 5) & 0x7FFFF
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm |= ~((1 << 21) - 1)
    return (inst & 0x1F), imm

for page, name in [(0x1DF000, 'page0x1DF000'), (0x1CC000, 'page0x1CC000')]:
    hits = []
    for i in range(0, len(text) - 4, 4):
        inst = struct.unpack_from('<I', text, i)[0]
        r = decode_adrp(inst)
        if r is None:
            continue
        rd, imm = r
        if ((i & ~0xFFF) + imm) & 0xFFFFFFFF == page:
            hits.append((i, rd))
    print('%s: %d adrp hits -> %s' % (name, len(hits),
                                      ', '.join('@0x%06X x%d' % (a, rd) for a, rd in hits[:8])))
