#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""
kip1_to_nso: convert a decompressed KIP1 to a flat NSO-like file.

PREREQUISITE: the input must be a DECRYPTED / DECOMPRESSED KIP1 (e.g.
FS_decomp.kip1) that you extracted yourself from a firmware dump.  This tool
does NOT decrypt anything; it only repacks the already-decompressed segment
data into a flat layout for offline disassembly/analysis.

Usage:
    python kip1_to_nso.py <input.kip1> <output.nso>

NOTE ON THE MAGIC: 0x30534F4E packed little-endian yields the 4 bytes
4E 4F 53 30 == "NOS0" (NOT the standard "NSO0").  This is a LOCAL tool format,
not the Nintendo-standard NSO0 header: the segment table here is three u32 per
segment (file_off / size / 0-pad), text size lives at 0x14, and rodata/data
offsets at 0x1C/0x28.  Other tools (e.g. the 20.2.0 FS_proper.nso) emit a real
"NSO0" with a different layout (text size at 0x18).  Always parse with a
layout-aware loader such as load_text() in verify_all_versions.py.
"""
import struct
import sys

if len(sys.argv) != 3:
    print(__doc__)
    sys.exit("usage: %s <input.kip1> <output.nso>" % sys.argv[0])

KIP1_PATH, NSO_OUT = sys.argv[1], sys.argv[2]

data = bytearray(open(KIP1_PATH, 'rb').read())

magic = data[0:4]
print(f"Magic: {magic}")
name = data[4:16].rstrip(b'\x00').decode()
title_id = struct.unpack_from('<Q', data, 0x10)[0]
print(f"Name: {name}")
print(f"Title ID: 0x{title_id:016X}")

# Parse KIP1 section headers
names = ['.text', '.rodata', '.data', '.bss', '.reserved1', '.reserved2']
sections = {}
for i, sname in enumerate(names):
    off = 0x20 + i * 0x10
    out_offset = struct.unpack_from('<I', data, off)[0]
    decomp_size = struct.unpack_from('<I', data, off + 4)[0]
    attrib = struct.unpack_from('<I', data, off + 8)[0]
    reserved = struct.unpack_from('<I', data, off + 0xC)[0]
    compressed = attrib & 1
    if decomp_size > 0:
        sections[sname] = (out_offset, decomp_size, compressed)
        print(f"{sname:12s}: file_off=0x{out_offset:07X} decomp=0x{decomp_size:07X}({decomp_size:>9,}) compr={compressed}")

# In decompressed KIP1, sections are contiguous starting at 0x100
# Compute actual offsets in the decompressed file
KIP1_HDR_SIZE = 0x100
text_start = KIP1_HDR_SIZE
text_size = sections['.text'][1]
rodata_start = text_start + text_size
rodata_size = sections['.rodata'][1]
data_start = rodata_start + rodata_size
data_size = sections['.data'][1]

print(f"\nComputed NSO layout:")
print(f"  .text:   offset=0x{text_start:X} size=0x{text_size:X} ({text_size:,})")
print(f"  .rodata: offset=0x{rodata_start:X} size=0x{rodata_size:X} ({rodata_size:,})")
print(f"  .data:   offset=0x{data_start:X} size=0x{data_size:X} ({data_size:,})")

# Verify data is within file bounds
total_needed = data_start + data_size
print(f"Needed: 0x{total_needed:X}, Available: 0x{len(data):X}")
if total_needed > len(data):
    print(f"WARNING: Need {total_needed} bytes but file is {len(data)} bytes!")

# Extract sections
text_data = data[text_start:text_start + text_size]
rodata_data = data[rodata_start:rodata_start + rodata_size]
data_data = data[data_start:data_start + data_size]

# Verify we got ARM64 code
print(f"\n.text first 16 bytes: {text_data[:16].hex()}")
print(f".rodata first 16 bytes: {rodata_data[:16].hex()}")

# Build NOS0 header (local flat layout, 3 x u32 per segment)
# NSO layout: 0x100-byte header + segments (each padded to 0x1000)
NSO_HEADER_SIZE = 0x100
PAGE_SIZE = 0x1000


def align_up(x, align=PAGE_SIZE):
    return (x + align - 1) & ~(align - 1)


# Segment offsets in NSO file
text_file_off = align_up(NSO_HEADER_SIZE, PAGE_SIZE)
rodata_file_off = align_up(text_file_off + text_size, PAGE_SIZE)
data_file_off = align_up(rodata_file_off + rodata_size, PAGE_SIZE)
bss_size = sections.get('.bss', (0, 0, 0))[1]

total_nso_size = data_file_off + data_size

nso = bytearray(total_nso_size)

# Write magic. 0x30534F4E little-endian => bytes 4E 4F 53 30 = "NOS0", NOT
# "NSO0" (endianness swaps the 'O' and 'S'). Standard NSO0 would be bytes
# 4E 53 4F 30 = 0x30534F4E in memory as big-endian; here it is packed LE.
struct.pack_into('<I', nso, 0, 0x30534F4E)  # LE => magic "NOS0"
struct.pack_into('<I', nso, 4, 0)            # version (0)
struct.pack_into('<I', nso, 8, 0)            # reserved
struct.pack_into('<I', nso, 0xC, 0)          # flags (0 = compressed)

# Segment 0: .text
struct.pack_into('<I', nso, 0x10, text_file_off)   # file offset
struct.pack_into('<I', nso, 0x14, text_size)        # size
struct.pack_into('<I', nso, 0x18, 0)                # .text segment size (same as file in NOS0)

# Segment 1: .rodata
struct.pack_into('<I', nso, 0x1C, rodata_file_off)
struct.pack_into('<I', nso, 0x20, rodata_size)
struct.pack_into('<I', nso, 0x24, 0)

# Segment 2: .data
struct.pack_into('<I', nso, 0x28, data_file_off)
struct.pack_into('<I', nso, 0x2C, data_size)
struct.pack_into('<I', nso, 0x30, bss_size)          # bss_size

# Build ID area (0x40-0x80)
# Use the first 32 bytes from KIP1 name + title_id
struct.pack_into('<12s', nso, 0x40, name.encode())
struct.pack_into('<Q', nso, 0x40 + 12, title_id)
# Pad remaining build_id with zeros

# Fill NOS header hash area (hash of header, computed after building)
# For now, we'll leave it as zeros - tools like loader.py don't strictly need it

# Copy segment data
nso[text_file_off:text_file_off + text_size] = text_data
nso[rodata_file_off:rodata_file_off + rodata_size] = rodata_data
nso[data_file_off:data_file_off + data_size] = data_data

# Write out
open(NSO_OUT, 'wb').write(nso)
print(f"\nNSO written to: {NSO_OUT}")
print(f"Total NSO size: {len(nso):,} bytes ({len(nso)/1024/1024:.1f} MB)")
print(f"  .text:   0x{text_file_off:X} - 0x{text_file_off + text_size:X}")
print(f"  .rodata: 0x{rodata_file_off:X} - 0x{rodata_file_off + rodata_size:X}")
print(f"  .data:   0x{data_file_off:X} - 0x{data_file_off + data_size:X}")
