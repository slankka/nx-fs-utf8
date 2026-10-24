# nx-fs-utf8

> **Branch note (`codex/exfat`):** this branch builds an exFAT-only regression
> candidate using the original six-slot `PF_CHARCODE` replacement strategy.
> It intentionally does not match the FAT32-only FS image. The generated KIP
> still requires hardware regression testing before release.

`nx-fs-utf8` makes UTF-8 filenames work in the Nintendo Switch FS sysmodule.
On-disk names stay standard UTF-16 long filenames, so a card written by the
Switch is readable on Windows, macOS and Linux without any sidecar file or
helper tool.

It is delivered as a small **FS Overlay KIP**: an image prepended *inside* the
existing FS process by an FS-Overlay-aware Fusee or Hekate.

> **Support status: emuMMC and sysMMC.** Verified on hardware — HOS 23.0.1
> sysMMC, all three CJK checks passing (`create`, `stat`, `enumerate`).
>
> Two loader-side notes. `kip1patch=emummc` must **not** be set: that injects
> emuMMC's code, and five of its six hooks replace FS's media path. And
> `bootloader/sys/emummc.kipm` must still exist — the loader copies its
> capability array into the merged KIP, but injects none of its code. See
> [Deployment](#deployment).

> **Important:** the overlay is *not* a standalone Initial Process KIP. Do not
> load it with Hekate's `kip1=` key. It deliberately reuses the FS Program ID
> (`0100000000000000`) and must be merged into the existing `FS.kip1` process
> image by an FS-Overlay-aware loader.

## What the patch does

FS is one module containing several stacked implementations. Only two of them
decide whether a non-ASCII filename survives, and this project edits exactly
those two — plus the path handling that feeds them.

```text
application (libnx fsdev, UTF-8 path bytes)
      │
      ▼
L0  nn::fssrv            IPC server          unchanged
L1  nn::fs / fssystem    accessors, saves    unchanged
L2  nn::fat              SFAT wrapper        ← gate 2: name scan
L3  nn::e::prfile2       FAT engine          ← gate 1: codec
L4  nn::sdmmc / nn::gc   media drivers       unchanged
```

### How the overlay gets to write into FS

FS's `.text` is mapped read-execute. Before any hook is installed, the overlay:

1. **Locates FS.** `svcQueryMemory` on the page-aligned address just past its
   own image gives the RX region that contains FS (and emuMMC, when enabled).
   It then walks that region page by page and accepts the first base whose
   bytes match a supported profile — six codec entry signatures, the four
   high-level entry points, the directory-scan branch, and a handful of
   identity opcodes. No match means no hooks, and stock FS boots untouched.
2. **Obtains a handle to itself.** It creates a session with
   `svcCreateSession` and reads the process handle the kernel places in the
   reply TLS.
3. **Maps FS writable.** `svcMapProcessMemory` puts an alias of FS's RX pages
   at a scratch address, which is what makes the writes possible. This is the
   same privileged call emuMMC uses, so the merged KIP borrows emuMMC's
   capability array — not its code, and not its redirection.
4. **Writes, then flushes.** `armDCacheFlush` + `armICacheInvalidate`, then the
   writable alias is released.

### What gets written

Fifteen instructions are overwritten: twelve branches into the overlay, and
three `NOP`s.

| Site | Count | Replaced with |
|---|---|---|
| **RTLD `.dynamic` walk** | **1** | **branch to its own loop head (see below)** |
| `PF_CHARCODE` six entries | 6 | branch to the UTF-8 codec pair |
| path / pattern / short-name entries | 4 | branch to full-string converters |
| `Directory::Read`, mid-function | 1 | branch to a trampoline in a NOP hole |
| three ASCII folding points | 3 | `NOP` |

The directory hook is the awkward one: it sits inside a function rather than at
its entry, so the trampoline saves every live register, calls the C++ validator,
and branches back to one of three places depending on the answer — reject,
continue with the ASCII checks, or continue scanning. `X8` is deliberately left
free because it carries the next scan index back out.

#### The RTLD hook is not about filenames

Prepending the overlay shifts FS's sections. FS then runs its own RTLD pass
over `.dynamic`, and one entry's final check compares a computed end against a
bound derived from the section layout. Once shifted, that check fails and FS
aborts **before `main()`** — which looks exactly like "the overlay broke
something", with no on-screen error.

The fix is the same one emuMMC has carried for years: overwrite the trailing
`b.cond` of that loop with an unconditional branch, so the entry is skipped
instead of aborting.

```asm
; 22.5.0, rtld = 0x2DED0, delta = -0x4C
0x2DED0  b.ne  0x2DE84     ; original
0x2DED0  b     0x2DE84     ; what this project writes
0x2DED4  ...               ; the failing final check, now skipped
```

It is applied first, before any other hook, so a bad offset aborts cleanly
instead of leaving FS half-patched. The offset table stores the site, the
delta, and the original opcode; `matches_fs()` validates the opcode *and*
decodes the delta from its imm19 field, so a table belonging to a different
build is rejected rather than hooked mid-function.

The other five hooks emuMMC installs replace FS's media path with emuMMC's own
driver. They cannot be reused here at all — and they are the reason injecting a
full `emummc.kipm` on sysMMC black-screens even though the loader hook would be
harmless.

Two consequences worth stating explicitly:

- **Code has no relocation entries.** FS's own relocation pass rewrites pointers
  in `.data` at startup; it cannot touch `.text`. A branch written into code
  survives, which is why this works at all when the overlay runs before FS.
- **Nothing is moved.** The trampoline lives in a stretch of existing NOP
  padding (`cave` in the offset table), so section offsets are unchanged and no
  space has to be reclaimed.

Known limit: only the BMP is covered (no 4-byte UTF-8 / emoji), and on FAT32
the legacy 8.3 alias remains lossy because the short-name generator is not
replaced.

## FS.kip1 is six layers

FS looks like one sysmodule but is several implementations linked into one
process image. The split below is what the two gates have to be understood
against.

| # | Namespace | Role | On the filename path |
|---|---|---|---|
| L0 | `nn::fssrv` | IPC server, 10 CMIF interfaces | yes |
| L1 | `nn::fs` + `nn::fssystem` | accessors, save stack, storage decorators | yes |
| L2 | `nn::fat` | SFAT wrapper: `FatFileSystem`, name validation | yes — **gate 2** |
| L3 | `nn::e::prfile2` | FAT engine, `PF_CHARCODE` codec | yes — **gate 1** |
| L4 | `nn::sdmmc` / `nn::gc` | SD, eMMC, GameCard drivers | yes |
| L5 | `nn::sf`, `os`, `rtld`, `crypto`, `nlibsdk`, `diag` | platform runtime, linked into the same KIP | no |

L5 is not on the path, but it is not optional either: `nn::rtld` is what
applies `R_AARCH64_RELATIVE`, and without resolving those relocations virtually
every vtable and pointer table in `.data` reads as zero.

### The two gates

| Gate | Layer | Decides | If only the other gate is fixed |
|---|---|---|---|
| 1 | L3 `PF_CHARCODE` | UTF-16 ↔ disk bytes | names are written, but the directory listing stays empty |
| 2 | L2 name scan | whether those bytes may be enumerated | nothing is ever written in the first place |

Both must be handled. This is the single most common misunderstanding about
the whole problem, and it is why "just fix the codec" never worked.

## Why this project calls it an Overlay

We are aware that the word is not an Atmosphère term, and that calling this an
"Overlay" has been contested. We keep it, but not as a claim about anyone's
terminology — because the mechanism is not a rename of something that already
had a name, and because it turns out to have a property worth naming. The
distinction is:

```text
Standalone KIP:  creates another Initial Process
FS Overlay KIP:  becomes a prefix inside the existing FS process image
```

![How the FS Overlay gets in: stock layout, the shift, the injection, and the kernel's final view](docs/fs-overlay-comic.png)

In one line: the stock image is never edited. It is pushed to a higher address
and the freed page-aligned hole at offset 0 is filled.

### The property: the hash is checked before the injection

> **The short version.** The loader asks "which FS is this?" *before* we touch
> anything, and never asks again afterwards. So `nogc`, `emuMMC` and
> `patches.ini` all still see the stock build and keep working, while the code
> that actually runs is ours.

Both loaders identify FS by SHA-256 and then apply version-specific patches —
`nogc`, `emuMMC`, `patches.ini`. The order of those two steps is what matters.

```text
Fusee  fusee_stratosphere.cpp
  ConfigureStratosphere()
    AddInitialProcess(nn_fs_kip)   hash = SHA-256 of the stock FS KIP
    GetFsVersion(kip_hash)         known -> the nogc offset table is usable
  RebuildPackage2()
    dst = copy(meta->kip)          injection edits this copy only
    ...overlay at offset 0, sections shifted...

Hekate  bootloader/hos/hos.c
  ① pkg2_patch_kips()
  ② hash compare + patches.ini
  ③ pkg2_inject_fs_overlay()       overlay happens HERE, after hashing
```

An overlay is injected *after* that identification step, so at the moment the
hash is taken the image is still the pristine stock KIP. That is what keeps
these working:

| Still applied | Because |
|---|---|
| hekate `nogc` | its offsets are selected from the recognised FS hash |
| hekate `emuMMC` | same identification path |
| `patches.ini` / `.ips` entries | keyed on the same hash |
| fusee `GetFsVersion` | never reaches the unknown-hash fatal path |

So the overlay does not need to keep FS's hash intact — it needs only to not be
present yet when the hash is computed. FS continues to look like the stock
build to every loader-side decision, while the code that actually runs carries
the patch.

The overlay also fails *closed*: it verifies the FS build by instruction
signatures before installing anything, so an unsupported FS runs unmodified
instead of half-patched.

The exFAT branch contains profiles for the exFAT-capable FS variants used by
HOS 19.0.1, 20.2.0, 21.2.0, 22.0.0, and 22.5.0. It does not contain the
FAT32-only FS profile. Do not infer cross-version exFAT validation from the
earlier FAT32-media regression results.

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
fs_codecvt_exfat.elf
fs_codecvt_exfat_unpacked.kip
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

The KIP must be loaded through the FS Overlay mechanism. For Hekate, use only
the fork-specific `fsoverlay=` key shown below; `kip1=` is not compatible with
the overlay build and must not point to `fs_codecvt_exfat_unpacked.kip`.

Fusee-compatible layout:

```text
sdmc:/atmosphere/fs_overlays/fs_codecvt_exfat_unpacked.kip
```

Hekate Fork boot entry:

```ini
pkg3=atmosphere/package3
fsoverlay=atmosphere/fs_overlays/fs_codecvt_exfat_unpacked.kip
```

That is the whole configuration. The same entry works on emuMMC and on sysMMC;
the overlay does not read `emummc.ini`, does not inject emuMMC's code, and does
not care which medium FS ends up using.

If you boot emuMMC and have been following the older instructions, remove any
`kip1patch=emummc` line. Injecting the emuMMC KIPM is not only unnecessary now,
it is harmful: five of its six hooks replace FS's media path with emuMMC's own
driver, and on sysMMC that driver has nowhere to read from.

### `bootloader/sys/emummc.kipm` is still needed, for one reason

The loader copies the 0x80-byte capability array out of that file into the
merged KIP, then injects no code at all. It is not optional in the current
loader: the file missing produces `bootloader/sys/emummc.kipm is missing or
invalid` and the boot stops.

Those capabilities are what let the overlay call `svcMapProcessMemory` on its
own process, which is how it gets write access to FS's read-execute pages. FS's
own capability array is too small for that — measured, not assumed: a build
that keeps FS's caps and skips the file entirely black-screens on sysMMC,
because `map_fs()` fails, no hook is installed, and FS then aborts in its RTLD
walk.

So the dependency is on `emummc.kipm` *as a capability donor*, not as code.
Replacing it with a hand-written 0x80-byte capability blob would work just as
well — that is planned for a future version, so the deployment becomes a single
file. Until then the file has to be present on the SD card.

The merged FS process image is arranged from lower to higher virtual addresses:

```text
increasing virtual address ─────────────────────────────────────────────►

+----------------------+------------------------+--------------------------+
| fs_codecvt overlay   | emuMMC KIP             | original FS.kip1         |
| begins at offset 0   | only when emuMMC is on | every section shifted    |
+----------------------+------------------------+--------------------------+
|<---- 0x8000 -------->|<--- emuMMC extent ---->|
```

The layout below shows the emuMMC KIP present because that is what a boot with
emuMMC enabled looks like; on sysMMC that middle region is simply absent. Both
values are offsets inside the merged `.text` region, not absolute addresses.
Everything the original FS owns — `.rodata`, `.data`, `.bss`, and the virtual
addresses recorded in its section headers — moves up by the same total.

## Limitations

| Scope | Status |
|---|---|
| emuMMC | verified on hardware (20.2.0, 23.0.1) |
| sysMMC | verified on hardware (23.0.1, 3/3 CJK checks) |
| 4-byte UTF-8 (non-BMP, e.g. emoji) | not covered |
| FAT32 8.3 alias | lossy; the short-name generator is not replaced |
| Loader must read `emummc.kipm` | capability donor only; removing this dependency is planned |

### What sysMMC used to fail on

Earlier builds black-screened on sysMMC with no on-screen error. The cause was
not the memory extent, the section layout, the compression state, or the hooks
themselves — it was the RTLD walk described above. Once that single branch is
patched, sysMMC boots and passes the same three checks as emuMMC.

An overlay with no hooks at all used to fail the same way, which is what made
the bug hard to see: the abort happened before any of this project's code ran.

Capabilities are a separate, and still current, prerequisite — see the
`emummc.kipm` note under Deployment. Without them the overlay cannot map FS
writable, so it installs nothing and the same RTLD abort happens. That is why
the file stays in the requirements list rather than being a leftover.

## Safety

This project patches the FS process at runtime. Back up important storage before
testing a new firmware or FS variant.

The overlay fails closed: it identifies the FS build by instruction signatures
before installing anything, and an unsupported build simply runs unmodified.

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
