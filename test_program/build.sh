#!/usr/bin/env bash
# Copyright (c) 2026 slankka and contributors
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${DEVKITPRO:-}" ]]; then
    echo "DEVKITPRO is not set." >&2
    echo "Set it to your devkitPro installation before building." >&2
    exit 1
fi

# PowerShell may pass a Windows path into an MSYS2 Bash process.
if command -v cygpath >/dev/null 2>&1 && [[ "${DEVKITPRO}" == *:\\* ]]; then
    DEVKITPRO="$(cygpath -u "${DEVKITPRO}")"
    export DEVKITPRO
fi

export DEVKITA64="${DEVKITA64:-${DEVKITPRO}/devkitA64}"
export PATH="${DEVKITA64}/bin:${DEVKITPRO}/tools/bin:${PATH}"

cd "${SCRIPT_DIR}"
make --jobs="${BUILD_JOBS:-4}"
