# Copyright (c) 2026 slankka and contributors
# SPDX-License-Identifier: GPL-2.0-only
#Requires -Version 5.1

[CmdletBinding()]
param(
    [string]$DevkitPro = $env:DEVKITPRO,

    [ValidateRange(1, 64)]
    [int]$Jobs = 4,

    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($DevkitPro)) {
    throw 'DEVKITPRO is not set. Pass -DevkitPro or set the DEVKITPRO environment variable.'
}

$scriptDirectory = $PSScriptRoot
$DevkitPro = [IO.Path]::GetFullPath($DevkitPro)
$bash = Join-Path $DevkitPro 'msys2\usr\bin\bash.exe'

if (-not (Test-Path -LiteralPath $bash -PathType Leaf)) {
    throw "MSYS2 Bash was not found at: $bash"
}

$env:DEVKITPRO = $DevkitPro
$env:DEVKITA64 = Join-Path $DevkitPro 'devkitA64'
$env:VERIFY_PROGRAM_DIR = $scriptDirectory
$env:BUILD_JOBS = $Jobs.ToString([Globalization.CultureInfo]::InvariantCulture)
$env:PATH = [string]::Join(
    [IO.Path]::PathSeparator,
    @(
        (Join-Path $DevkitPro 'msys2\usr\bin'),
        (Join-Path $DevkitPro 'devkitA64\bin'),
        (Join-Path $DevkitPro 'tools\bin'),
        $env:PATH
    )
)

$commands = @(
    'cd "$(cygpath -u "$VERIFY_PROGRAM_DIR")"'
)
if ($Clean) {
    $commands += 'make clean'
}
$commands += './build.sh'

& $bash -c ($commands -join ' && ')
if ($LASTEXITCODE -ne 0) {
    throw "Test-program build failed with exit code $LASTEXITCODE"
}

$output = Join-Path $scriptDirectory 'sdmc2.nro'
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw "Build completed without producing: $output"
}

Get-Item -LiteralPath $output | Select-Object FullName, Length, LastWriteTime
