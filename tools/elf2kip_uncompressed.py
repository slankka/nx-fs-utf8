#!/usr/bin/env python3
"""Build an uncompressed KIP1 directly from an AArch64 ELF image."""

# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 slankka

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ELF_HEADER_SIZE = 0x40
ELF_PROGRAM_HEADER_SIZE = 0x38
ELF_MACHINE_AARCH64 = 0xB7
PT_LOAD = 1
KIP_HEADER_SIZE = 0x100
KIP_SECTION_COUNT = 6
KIP_CAPABILITY_COUNT = 0x20
PAGE_SIZE = 0x1000
U32_MAX = 0xFFFFFFFF


@dataclass(frozen=True)
class LoadSegment:
    file_offset: int
    file_size: int
    memory_size: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an AArch64 ELF into an uncompressed KIP1 image."
    )
    parser.add_argument("elf", type=Path, help="input AArch64 ELF")
    parser.add_argument("descriptor", type=Path, help="KIP JSON descriptor")
    parser.add_argument("output", type=Path, help="output unpacked KIP1")
    return parser.parse_args()


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment


def parse_integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as error:
            raise ValueError(f"{field} is not a valid integer: {value}") from error
    raise ValueError(f"{field} must be an integer or numeric string")


def checked_u32(value: int, field: str) -> int:
    if not 0 <= value <= U32_MAX:
        raise ValueError(f"{field} does not fit in u32")
    return value


def read_load_segments(elf: bytes) -> list[LoadSegment]:
    if len(elf) < ELF_HEADER_SIZE or elf[:4] != b"\x7fELF":
        raise ValueError("input is not an ELF file")
    if elf[4] != 2 or elf[5] != 1:
        raise ValueError("input must be a little-endian ELF64 file")

    machine = struct.unpack_from("<H", elf, 0x12)[0]
    if machine != ELF_MACHINE_AARCH64:
        raise ValueError("input ELF is not AArch64")

    table_offset = struct.unpack_from("<Q", elf, 0x20)[0]
    entry_size, entry_count = struct.unpack_from("<HH", elf, 0x36)
    if entry_size < ELF_PROGRAM_HEADER_SIZE:
        raise ValueError("ELF program-header entries are too small")
    table_end = table_offset + entry_size * entry_count
    if table_end < table_offset or table_end > len(elf):
        raise ValueError("ELF program-header table is outside the file")

    segments: list[LoadSegment] = []
    for index in range(entry_count):
        offset = table_offset + index * entry_size
        values = struct.unpack_from("<IIQQQQQQ", elf, offset)
        segment_type = values[0]
        file_offset, file_size, memory_size = values[2], values[5], values[6]
        if segment_type != PT_LOAD:
            continue
        file_end = file_offset + file_size
        if file_end < file_offset or file_end > len(elf):
            raise ValueError(f"ELF load segment {len(segments)} exceeds the file")
        if memory_size < file_size:
            raise ValueError(f"ELF load segment {len(segments)} has invalid sizes")
        segments.append(LoadSegment(file_offset, file_size, memory_size))

    if len(segments) != 3:
        raise ValueError(f"expected exactly 3 ELF load segments, found {len(segments)}")
    return segments


def encode_capabilities(descriptor: dict[str, Any]) -> list[int]:
    encoded: list[int] = []
    capabilities = descriptor.get("kernel_capabilities")
    if not isinstance(capabilities, list):
        raise ValueError("kernel_capabilities must be an array")

    for capability in capabilities:
        if not isinstance(capability, dict):
            raise ValueError("each kernel capability must be an object")
        capability_type = capability.get("type")
        value = capability.get("value")

        if capability_type == "handle_table_size":
            handle_count = parse_integer(value, "handle_table_size")
            if not 0 <= handle_count <= 0xFFFF:
                raise ValueError("handle_table_size does not fit in u16")
            encoded.append((handle_count << 16) | 0x7FFF)
        elif capability_type == "syscalls":
            if not isinstance(value, dict):
                raise ValueError("syscalls capability must be an object")
            descriptors = [0] * 8
            for syscall_name, syscall_value in value.items():
                syscall_id = parse_integer(syscall_value, f"syscall {syscall_name}")
                if not 0 <= syscall_id < 0xC0:
                    raise ValueError(f"syscall {syscall_name} is outside [0, 0xBF]")
                descriptors[syscall_id // 0x18] |= 1 << (syscall_id % 0x18)
            for index, syscall_mask in enumerate(descriptors):
                if syscall_mask:
                    encoded.append(((syscall_mask | (index << 24)) << 5) | 0xF)
        else:
            raise ValueError(f"unsupported kernel capability: {capability_type}")

    if len(encoded) > KIP_CAPABILITY_COUNT:
        raise ValueError("too many encoded kernel capabilities")
    encoded.extend([U32_MAX] * (KIP_CAPABILITY_COUNT - len(encoded)))
    return encoded


def build_kip(elf: bytes, descriptor: dict[str, Any]) -> bytes:
    segments = read_load_segments(elf)

    name = descriptor.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("name must be a non-empty string")
    encoded_name = name.encode("ascii")
    if len(encoded_name) >= 12:
        raise ValueError("name must fit in 11 ASCII bytes")

    program_id_value = descriptor.get("program_id", descriptor.get("title_id"))
    program_id = parse_integer(program_id_value, "program_id")
    if not 0 <= program_id <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("program_id does not fit in u64")

    version_value = descriptor.get("version", descriptor.get("process_category", 1))
    version = checked_u32(parse_integer(version_value, "version"), "version")
    priority = parse_integer(descriptor.get("main_thread_priority"), "main_thread_priority")
    cpu_id = parse_integer(descriptor.get("default_cpu_id"), "default_cpu_id")
    if not 0 <= priority <= 0xFF or not 0 <= cpu_id <= 0xFF:
        raise ValueError("thread priority and CPU ID must fit in u8")

    stack_size = checked_u32(
        parse_integer(descriptor.get("main_thread_stack_size"), "main_thread_stack_size"),
        "main_thread_stack_size",
    )

    flags = 0x78
    if descriptor.get("use_secure_memory", True) is False:
        flags &= ~0x20
    if descriptor.get("immortal", True) is False:
        flags &= ~0x40

    section_headers: list[tuple[int, int, int, int]] = []
    payload = bytearray()
    destination_offset = 0
    for index, segment in enumerate(segments):
        file_size = checked_u32(segment.file_size, f"segment {index} file size")
        checked_offset = checked_u32(destination_offset, f"segment {index} offset")
        section_headers.append(
            (checked_offset, file_size, file_size, stack_size if index == 1 else 0)
        )
        payload.extend(elf[segment.file_offset : segment.file_offset + segment.file_size])
        destination_offset = align_up(destination_offset + file_size, PAGE_SIZE)

    data_segment = segments[-1]
    data_file_end = align_up(data_segment.file_size, PAGE_SIZE)
    bss_size = 0
    if data_segment.memory_size > data_file_end:
        bss_size = align_up(data_segment.memory_size - data_file_end, PAGE_SIZE)
    bss_offset = checked_u32(destination_offset, "BSS offset")
    section_headers.append((bss_offset, checked_u32(bss_size, "BSS size"), 0, 0))
    section_headers.extend([(0, 0, 0, 0)] * (KIP_SECTION_COUNT - len(section_headers)))

    header = bytearray(KIP_HEADER_SIZE)
    struct.pack_into(
        "<4s12sQIBBBB",
        header,
        0,
        b"KIP1",
        encoded_name.ljust(12, b"\0"),
        program_id,
        version,
        priority,
        cpu_id,
        0,
        flags,
    )
    for index, section in enumerate(section_headers):
        struct.pack_into("<4I", header, 0x20 + index * 0x10, *section)
    struct.pack_into("<32I", header, 0x80, *encode_capabilities(descriptor))

    return bytes(header + payload)


def main() -> None:
    args = parse_args()
    try:
        elf = args.elf.read_bytes()
        descriptor = json.loads(args.descriptor.read_text(encoding="utf-8"))
        if not isinstance(descriptor, dict):
            raise ValueError("KIP descriptor root must be an object")
        kip = build_kip(elf, descriptor)
        args.output.write_bytes(kip)
    except (OSError, ValueError, json.JSONDecodeError, struct.error) as error:
        raise SystemExit(f"error: {error}") from error

    print(f"built {args.output} (0x{len(kip):X} bytes, uncompressed)")


if __name__ == "__main__":
    main()
