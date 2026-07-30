# UTF-8 filesystem test program

This libnx homebrew program verifies CJK filename round trips through the
Switch filesystem APIs. It exercises file and directory creation, open,
write, read, metadata lookup, and directory enumeration.

## Build

The same devkitPro installation used by the main project can build the test:

```sh
cd test_program
./build.sh
```

On Windows PowerShell:

```powershell
.\test_program\build.ps1 -DevkitPro C:\devkitPro
```

Both commands produce `test_program/sdmc2.nro`. Generated build files are
ignored by Git.

## Run

Copy `sdmc2.nro` to the SD card and launch it through the Homebrew Menu. The
program tests this path:

```text
sdmc:/ROM/中文目录/往返测试.txt
```

It creates the directory and file when absent, or rewrites the test file when
it already exists. Back up any existing file at that exact path before running
the test. The file is intentionally retained after the test so its on-disk
name and contents can be inspected.

Use Up/Down to scroll and Plus to exit. A successful run reports `PASS` for
the direct read/write check, the `/ROM` directory listing, and the CJK
directory listing.

The program is a test client only. It is not part of the FS Overlay KIP and is
not loaded by Hekate or Fusee.
