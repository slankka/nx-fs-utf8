# nx-fs-utf8

`nx-fs-utf8` is an independently buildable FS Overlay KIP that adds UTF-8
filename compatibility to the Nintendo Switch FS sysmodule. It is designed to
be prepended to FS by a compatible Fusee or Hekate FS Overlay loader.

> **Important:** this is not a standalone Initial Process KIP. Do not load it
> with Hekate's `kip1=` key. The overlay intentionally uses the same FS Program
> ID (`0100000000000000`) and must be merged into the existing `FS.kip1`
> process image by an FS Overlay-aware loader.

## Why this project calls it an Overlay

The word **Overlay** is used here to distinguish the module from an ordinary
KIP loaded as a separate Initial Process. The loader does not add a second FS
process. Instead, it places the `fs_codecvt` image in front of the existing FS
image, shifts the original FS sections, and rebuilds one combined `FS.kip1`.
Both components therefore execute inside the same FS process and address
space. In that practical sense, `fs_codecvt` is layered over, or prepended to,
the original FS image.

This terminology is local to the `nx-fs-utf8` project. **FS Overlay is not
claimed to be an official Atmosphère feature name, file format, or public API.**
Atmosphère may describe comparable image-merging or emuMMC injection behavior
using different terms, and its maintainers may not agree with or adopt the
word "Overlay" for this mechanism. The name is retained here because it makes
the deployment distinction clear:

```text
Standalone KIP: creates another Initial Process
FS Overlay KIP: becomes a prefix inside the existing FS process image
```

The current offset table supports the tested HOS 19.0.1, 20.2.0, 21.2.0,
22.0.0, and 22.5.0 FS variants used by this project. Those versions completed
the FAT32-media hardware regression in the original development environment.

## Requirements

- devkitPro with devkitA64 and libnx
- GNU Make
- Python 3.9 or newer

The repository contains its own uncompressed ELF-to-KIP1 packer. Atmosphère,
`elf2kip`, and `hactool` source trees are not required to build it.

## Build

```sh
export DEVKITPRO=/opt/devkitpro
make -j4
```

The build produces:

```text
fs_codecvt.elf
fs_codecvt_unpacked.kip
```

The unpacked KIP is the deployable FS Overlay. Its loadable sections are stored
without BLZ compression because both supported loaders require an unpacked
overlay image.

Clean generated files with:

```sh
make clean
```

## Test program

[`test_program`](test_program) contains the libnx homebrew program used to
verify CJK filename round trips on hardware. It creates and reads
`sdmc:/ROM/中文目录/往返测试.txt`, then verifies that both Chinese names appear
through directory enumeration. This test client is separate from the Overlay
KIP and is launched through the Homebrew Menu.

Build it with devkitPro:

```sh
cd test_program
./build.sh
```

See [`test_program/README.md`](test_program/README.md) for Windows build steps,
controls, expected results, and the SD-card write warning.

## Deployment

This KIP must be loaded through an FS Overlay mechanism. For Hekate, use only
the fork-specific `fsoverlay=` key shown below; `kip1=` is not compatible with
this project and must not point to `fs_codecvt_unpacked.kip`.

Fusee-compatible layout:

```text
sdmc:/atmosphere/fs_overlays/fs_codecvt_unpacked.kip
```

Hekate Fork boot entry:

```ini
pkg3=atmosphere/package3
fsoverlay=atmosphere/fs_overlays/fs_codecvt_unpacked.kip
```

When emuMMC is enabled in the Hekate path, use the relocatable emuMMC build
that derives its text base from `_start`.

The merged FS process image is arranged from lower to higher virtual addresses:

```text
Lower address                                             Higher address
     |                                                          |
     v                                                          v
+----------------------+----------------------+------------------------+
| fs_codecvt overlay   | emuMMC overlay       | original FS.kip1       |
| offset 0x0000        | optional             | shifted after overlays |
+----------------------+----------------------+------------------------+
          execution continues through the combined FS image --->
```

On sysMMC, the optional emuMMC region is absent, so the original `FS.kip1`
immediately follows the `fs_codecvt` overlay. The current `fs_codecvt` memory
extent is `0x8000`; every following FS section is shifted by that amount.

## Safety

This project patches the FS process at runtime. Back up important storage before
testing a new firmware or FS variant. An unknown FS build is rejected when its
runtime signatures do not match the supported offset table.

## License and credits

Copyright (c) 2026 slankka and contributors.

This project is licensed under the GNU General Public License version 2 only
(`GPL-2.0-only`). See [LICENSE](LICENSE).

The KIP startup/runtime framework is derived from the Atmosphère emuMMC design.
Copyright and attribution for upstream-derived portions remain with m4xw and
Atmosphere-NX. UTF-8 codec conversion, FS discovery, validation, and hook logic
are maintained by the `nx-fs-utf8` project.

Development was assisted by generative AI. The maintainer directed, reviewed,
modified, tested, and approved the resulting code. The AI tool is not an author
or copyright holder.
