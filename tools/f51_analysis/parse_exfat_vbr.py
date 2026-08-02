#!/usr/bin/env python3
"""Parse the exFAT Volume Boot Record dump (512-offset.txt) and report fields."""
import re

PATH = r'C:\Users\Arvin\Desktop\512-offset.txt'
raw = open(PATH, 'r', encoding='utf-8', errors='replace').read()
# strip whitespace/hex separators
hexs = re.sub(r'[^0-9a-fA-F]', '', raw)
b = bytes.fromhex(hexs)
print('decoded bytes: %d' % len(b))
if len(b) > 512:
    b = b[:512]
    print('truncated to 512')

def u16(o): return int.from_bytes(b[o:o+2], 'little')
def u32(o): return int.from_bytes(b[o:o+4], 'little')
def u64(o): return int.from_bytes(b[o:o+8], 'little')

print('\n--- VBR header ---')
print('jump      : %s' % b[0:3].hex(' '))
print('oem name  : %r' % b[3:11])
print('bpb zeros : all-zero @0x0B-0x3F = %s' % (all(x == 0 for x in b[0x0B:0x40])))
print('partition_offset = 0x%X (%d)' % (u64(0x40), u64(0x40)))
print('volume_length    = 0x%X (%d)' % (u64(0x48), u64(0x48)))
print('fat_offset       = 0x%X (%d)' % (u32(0x50), u32(0x50)))
print('fat_length       = 0x%X (%d)' % (u32(0x54), u32(0x54)))
print('cluster_heap_off = 0x%X (%d)' % (u32(0x58), u32(0x58)))
print('cluster_count    = 0x%X (%d)' % (u32(0x5C), u32(0x5C)))
print('root_cluster     = 0x%X (%d)' % (u32(0x60), u32(0x60)))
print('volume_serial    = 0x%08X' % u32(0x64))
print('fs_revision      = %d.%d' % (b[0x68], b[0x69]))
print('volume_flags     = 0x%04X' % u16(0x6A))
print('bytes/sec shift  = %d (=> %d B/sector)' % (b[0x6C], 1 << b[0x6C]))
print('sectors/clu shift= %d (=> %d sectors/cluster)' % (b[0x6D], 1 << b[0x6D]))
print('num_fats         = %d' % b[0x6E])
print('drive_select     = 0x%02X' % b[0x6F])
print('percent_in_use   = %d' % b[0x70])
print('boot_sig         = 0x%02X%02X' % (b[0x1FE], b[0x1FF]), '(55AA ok)' if b[0x1FE] == 0x55 and b[0x1FF] == 0xAA else '(NOT 55AA!)')

# FAT32-style fields Windows might read at the same offsets:
print('\n--- what a FAT32 reader would see (offset 0x0B = FAT32 BPB) ---')
print('bytes_per_sector(0x0B) = 0x%04X (%d)' % (u16(0x0B), u16(0x0B)))
print('sectors_per_cluster(0x0D) = %d' % b[0x0D])
print('total_sectors32(0x20)  = 0x%08X (%d)' % (u32(0x20), u32(0x20)))
print('fat_sz32(0x24)         = 0x%08X (%d)' % (u32(0x24), u32(0x24)))
print('root_ent_cnt(0x11)     = %d' % u16(0x11))
print('root_cluster(0x2C)     = 0x%08X' % u32(0x2C))
