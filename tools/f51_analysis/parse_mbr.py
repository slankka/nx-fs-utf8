#!/usr/bin/env python3
"""Parse the whole-disk MBR dump (Whole_512_offset.txt): boot sig + partition
table entries (type byte / LBA start / sectors), the key for the Windows
FAT32-vs-exFAT display mystery."""
import re

PATH = r'C:\Users\Arvin\Desktop\Whole_512_offset.txt'
raw = open(PATH, 'r', encoding='utf-8', errors='replace').read()
hexs = re.sub(r'[^0-9a-fA-F]', '', raw)
b = bytes.fromhex(hexs[:1024])
print('bytes: %d  boot_sig=0x%02X%02X %s' % (len(b), b[0x1FE], b[0x1FF],
      'OK' if b[0x1FE] == 0x55 and b[0x1FF] == 0xAA else 'NOT 55AA'))

# Is it an MBR (partition table) or a VBR (EB.. at 0)?
print('byte0-2: %s' % b[0:3].hex(' '))
oem = b[3:11]
print('oem @3: %r' % oem)

def pt_entry(i):
    e = b[0x1BE + 16 * i:0x1BE + 16 * (i + 1)]
    if len(e) < 16:
        return None
    boot = e[0]
    type_byte = e[4]
    start = int.from_bytes(e[8:12], 'little')
    sectors = int.from_bytes(e[12:16], 'little')
    return dict(boot=boot, type=type_byte,
                start_lba=start, sectors=sectors,
                size_mb=round(sectors / 2048, 1))

print('\n--- partition table (0x1BE..0x1FD) ---')
any_entry = False
for i in range(4):
    e = pt_entry(i)
    if e and (e['type'] != 0 or e['start_lba'] != 0):
        any_entry = True
        print('P%d: boot=%s type=0x%02X start=0x%X(%d) sectors=%d (%.1f MB)'
              % (i, 'Y' if e['boot'] == 0x80 else 'n', e['type'],
                 e['start_lba'], e['start_lba'], e['sectors'], e['size_mb']))
    else:
        print('P%d: empty (type=0x00)' % i)

print('\n--- partition type byte meanings ---')
tmap = {0x0B: 'FAT32 (CHS)', 0x0C: 'FAT32 LBA', 0x07: 'NTFS/exFAT',
        0x06: 'FAT16', 0x0E: 'FAT16 LBA', 0x83: 'Linux', 0xEE: 'GPT'}
for i in range(4):
    e = pt_entry(i)
    if e and e['type'] != 0:
        print('P%d type 0x%02X -> %s' % (i, e['type'], tmap.get(e['type'], 'other')))
        print('   partition starts at LBA %d (= byte 0x%X = sector %d)'
              % (e['start_lba'], e['start_lba'] * 512, e['start_lba']))

# Check if byte0-2 looks like a VBR (super-floppy) instead
if b[0] == 0xEB and b[3:11] == b'EXFAT   ':
    print('\n=> LBA0 IS the exFAT VBR itself (super-floppy, no MBR partition table)')
elif b[0x1FE] == 0x55 and b[0x1FF] == 0xAA and not any_entry:
    print('\n=> LBA0 has 55AA but no partition entries -> super-floppy style')
