/*
 * Copyright (c) 2019 m4xw
 * Copyright (c) 2019 Atmosphere-NX
 * Copyright (c) 2026 slankka
 * SPDX-License-Identifier: GPL-2.0-only
 */

/**
 * @file start.s
 * @brief fs_codecvt KIP entry point. Based on emuMMC start.s.
 *
 * On entry:
 *   X0 = context pointer (FS's original init context)
 *   X1 = main thread handle
 */

.macro push_all
    SUB SP, SP, #0x100
    STP X29, X30, [SP, #0x0]
    STP X27, X28, [SP, #0x10]
    STP X25, X26, [SP, #0x20]
    STP X23, X24, [SP, #0x30]
    STP X21, X22, [SP, #0x40]
    STP X19, X20, [SP, #0x50]
    STP X17, X18, [SP, #0x60]
    STP X15, X16, [SP, #0x70]
    STP X13, X14, [SP, #0x80]
    STP X11, X12, [SP, #0x90]
    STP X9, X10, [SP, #0xA0]
    STP X7, X8, [SP, #0xB0]
    STP X5, X6, [SP, #0xC0]
    STP X3, X4, [SP, #0xD0]
    STP X1, X2, [SP, #0xE0]
    STR X0, [SP, #0xF0]
.endm

.macro pop_all
    LDR X0, [SP, #0xF0]
    LDP X1, X2, [SP, #0xE0]
    LDP X3, X4, [SP, #0xD0]
    LDP X5, X6, [SP, #0xC0]
    LDP X7, X8, [SP, #0xB0]
    LDP X9, X10, [SP, #0xA0]
    LDP X11, X12, [SP, #0x90]
    LDP X13, X14, [SP, #0x80]
    LDP X15, X16, [SP, #0x70]
    LDP X17, X18, [SP, #0x60]
    LDP X19, X20, [SP, #0x50]
    LDP X21, X22, [SP, #0x40]
    LDP X23, X24, [SP, #0x30]
    LDP X25, X26, [SP, #0x20]
    LDP X27, X28, [SP, #0x10]
    LDP X29, X30, [SP, #0x0]
    ADD SP, SP, #0x100
.endm

.section ".crt0","ax"
.global _start
_start:
    B startup
.org _start+0x80

.section ".crt0","ax"
startup:
#if defined(FS_DIAG_KEEP_EXTENT)
    /* Keep the shipping 0x7000 KIP extent (inner_heap is 0x4000 of .bss) so
     * that diagnostic variants differ in executed code only, never in the
     * amount the FS image is shifted by.  These references are never
     * dereferenced; they exist to defeat --gc-sections. */
    ADRP X9, __initheap
    ADD  X9, X9, #:lo12:__initheap
#endif
#if defined(FS_DIAG_SKIP_ALL)
    /* Absolute minimum: do not touch permissions, bss, relocations or the
     * heap — just hand control to FS.  Used to separate "hekate prepended an
     * image and shifted the FS sections" from "this overlay's startup ran". */
#if defined(FS_DIAG_EXTENT_PAD)
    /* Real reference so the padding in .data survives --gc-sections and keeps
     * the overlay extent large without declaring any .bss. */
    ADRP X9, g_extent_pad
    ADD  X9, X9, #:lo12:g_extent_pad
#endif
    ADRP X16, __argdata__
    ADD  X16, X16, #:lo12:__argdata__
    BR   X16
#else
    /* Save LR */
    MOV  X7, X30

    /* Retrieve ASLR Base */
    BL   +4
    SUB  X6, X30, #0x88

    /* Context Ptr and MainThread Handle */
    MOV  X5, X0
    MOV  X4, X1

    /* Set memory permissions for our own segments */
    push_all

    /* Set .text + .rodata: RX */
    MOV W0, #0xFFFF8001
    ADR X1, __rodata_start
    ADR X2, __data_start
    SUB X2, X2, X1
    MOV X3, #1
    SVC 0x73

    /* Set .data: RW */
    MOV W0, #0xFFFF8001
    ADR X1, __data_start
    ADR X2, __argdata__
    SUB X2, X2, X1
    MOV X3, #3
    SVC 0x73

    pop_all

    /* Restore saved LR and context */
    MOV X27, X7
    MOV X25, X5
    MOV X26, X4

#if !defined(FS_DIAG_SKIP_BSS)
    /* Clear .bss */
    ADRP X0, __bss_start__
    ADRP X1, __bss_end__
    ADD  X0, X0, #:lo12:__bss_start__
    ADD  X1, X1, #:lo12:__bss_end__
    SUB  X1, X1, X0
    ADD  X1, X1, #7
    BIC  X1, X1, #7

1:  CBZ  X1, 2f
    SUB  X1, X1, #8
    STR  XZR, [X0, X1]
    B    1b

2:
#endif

#if !defined(FS_DIAG_SKIP_RELOC)
    /* Process .dynamic relocations. */
    MOV  X0, X6
    ADRP X1, __dynamic_start
    ADD  X1, X1, #:lo12:__dynamic_start
    BL   __nx_dynamic
#endif

#if !defined(FS_DIAG_SKIP_INIT)
    /* Initialize the local heap before running C++ constructors/hooks. */
    BL   __initheap
    BL   __init
#endif

    /* Restore FS's context and jump to FS */
    MOV X0, X25
    MOV X1, X26
    MOV X30, X27

    /* Jump to FS main */
    ADRP X16, __argdata__
    ADD  X16, X16, #:lo12:__argdata__
    BR X16
#endif
