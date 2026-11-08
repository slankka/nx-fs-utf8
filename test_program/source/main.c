/*
 * Copyright (c) 2026 slankka and contributors
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * sdmc2 v8 - CJK SD-card round-trip test for libnx FS APIs.
 *
 * Expected test target:
 *   sdmc:/ROM/<CJK directory>/<CJK file>
 *
 * The test checks direct create/open/write/read and directory enumeration.
 */
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <switch.h>
#include "ui.h"

#define MAX_LINES 160
#define LINE_LEN 128

/* FS module 2, description 1: path does not exist. */
#define FS_PATH_NOT_FOUND 0x202
#define ROM_PATH "/ROM"

#define CJK_DIR_NAME "\xE4\xB8\xAD\xE6\x96\x87\xE7\x9B\xAE\xE5\xBD\x95"
#define CJK_FILE_NAME "\xE5\xBE\x80\xE8\xBF\x94\xE6\xB5\x8B\xE8\xAF\x95.txt"
#define CJK_DIR_PATH "/ROM/" CJK_DIR_NAME
#define CJK_FILE_PATH CJK_DIR_PATH "/" CJK_FILE_NAME

static char g_lines[MAX_LINES][LINE_LEN];
static int g_line_count;

/* Directory entries are untrusted bytes, and vsnprintf may truncate UTF-8.
 * Replace malformed sequences before passing text to LVGL. */
static void sanitize_utf8(char *text) {
    unsigned char *src = (unsigned char *)text, *dst = src;
    while (*src) {
        unsigned n = 1;
        if (*src < 0x80) {
            *dst++ = (*src == '\n' || *src == '\r') ? ' ' : *src;
            src++;
            continue;
        }
        if (*src >= 0xc2 && *src <= 0xdf) n = 2;
        else if (*src >= 0xe0 && *src <= 0xef) n = 3;
        else if (*src >= 0xf0 && *src <= 0xf4) n = 4;
        else { *dst++ = '?'; src++; continue; }
        unsigned i;
        for (i = 1; i < n && src[i] && (src[i] & 0xc0) == 0x80; i++) {}
        if (i != n || (n == 3 && ((*src == 0xe0 && src[1] < 0xa0) ||
                                    (*src == 0xed && src[1] >= 0xa0))) ||
                      (n == 4 && ((*src == 0xf0 && src[1] < 0x90) ||
                                    (*src == 0xf4 && src[1] >= 0x90)))) {
            *dst++ = '?'; src++; continue;
        }
        while (n--) *dst++ = *src++;
    }
    *dst = 0;
}

static void log_line(const char *fmt, ...) {
    if (g_line_count >= MAX_LINES)
        return;

    va_list args;
    va_start(args, fmt);
    vsnprintf(g_lines[g_line_count], LINE_LEN, fmt, args);
    va_end(args);
    sanitize_utf8(g_lines[g_line_count]);
    g_line_count++;
}

static void log_result(const char *label, Result rc) {
    log_line("%s: 0x%X %s", label, rc, R_SUCCEEDED(rc) ? "OK" : "FAIL");
}

static bool ensure_rom_directory(FsFileSystem *fs) {
    FsDirEntryType type;
    Result rc = fsFsGetEntryType(fs, ROM_PATH, &type);
    if (R_SUCCEEDED(rc)) {
        if (type != FsDirEntryType_Dir) {
            log_line("setup: /ROM exists but is not a directory");
            return false;
        }
        log_line("setup: /ROM directory exists");
        return true;
    }
    if (rc != FS_PATH_NOT_FOUND) {
        log_result("stat /ROM", rc);
        return false;
    }
    rc = fsFsCreateDirectory(fs, ROM_PATH);
    log_result("create /ROM", rc);
    return R_SUCCEEDED(rc);
}

static bool name_equals(const char *a, const char *b) {
    return strcmp(a, b) == 0;
}

static bool list_dir_find(FsFileSystem *fs, const char *path, const char *needle) {
    FsDir dir;
    FsDirectoryEntry entry;
    Result rc;
    s64 count = 0;
    int total = 0;
    bool found = false;

    log_line("--- list %s ---", path);

    rc = fsFsOpenDirectory(fs, path, FsDirOpenMode_ReadFiles | FsDirOpenMode_ReadDirs, &dir);
    if (R_FAILED(rc)) {
        log_result("open dir", rc);
        return false;
    }

    while (R_SUCCEEDED((rc = fsDirRead(&dir, &count, 1, &entry))) && count > 0) {
        const char *type = entry.type == FsDirEntryType_Dir ? "dir" : "file";
        bool match = name_equals(entry.name, needle);

        log_line("[%02d] %s '%s'%s", total, type, entry.name, match ? " <==" : "");
        found |= match;
        total++;
    }

    if (R_FAILED(rc))
        log_result("read dir", rc);

    fsDirClose(&dir);
    log_line("total=%d target=%s", total, found ? "FOUND" : "MISSING");
    return found;
}

static bool ensure_cjk_file(FsFileSystem *fs) {
    static const char payload[] =
        "sdmc2 cjk roundtrip: "
        "\xE4\xB8\xAD\xE6\x96\x87/"
        "\xE5\xBE\x80\xE8\xBF\x94\xE6\xB5\x8B\xE8\xAF\x95\n";

    FsFile file;
    FsDirEntryType type;
    char read_buf[128] = {0};
    u64 bytes_read = 0;
    const u64 payload_size = strlen(payload);
    Result rc;

    log_line("--- direct CJK path test ---");

    rc = fsFsCreateDirectory(fs, CJK_DIR_PATH);
    log_result("create CJK dir", rc);

    rc = fsFsGetEntryType(fs, CJK_DIR_PATH, &type);
    if (R_SUCCEEDED(rc))
        log_line("stat CJK dir: 0x%X type=%d", rc, (int)type);
    else
        log_result("stat CJK dir", rc);

    rc = fsFsCreateFile(fs, CJK_FILE_PATH, payload_size, 0);
    log_result("create CJK file", rc);

    rc = fsFsOpenFile(fs, CJK_FILE_PATH, FsOpenMode_Write, &file);
    if (R_FAILED(rc)) {
        log_result("open write", rc);
        return false;
    }

    rc = fsFileSetSize(&file, payload_size);
    log_result("set size", rc);

    if (R_SUCCEEDED(rc)) {
        rc = fsFileWrite(&file, 0, payload, payload_size, FsWriteOption_Flush);
        log_result("write", rc);
    }

    fsFileClose(&file);

    rc = fsFsCommit(fs);
    log_result("commit", rc);

    rc = fsFsOpenFile(fs, CJK_FILE_PATH, FsOpenMode_Read, &file);
    if (R_FAILED(rc)) {
        log_result("open read", rc);
        return false;
    }

    rc = fsFileRead(&file, 0, read_buf, sizeof(read_buf) - 1, FsReadOption_None, &bytes_read);
    if (R_SUCCEEDED(rc))
        read_buf[bytes_read < sizeof(read_buf) ? bytes_read : sizeof(read_buf) - 1] = '\0';

    log_result("read", rc);
    fsFileClose(&file);

    if (R_FAILED(rc))
        return false;

    log_line("read bytes=%llu", bytes_read);
    log_line("readback: %s", read_buf);
    log_line("compare: %s", strcmp(payload, read_buf) == 0 ? "MATCH" : "DIFFER");

    rc = fsFsGetEntryType(fs, CJK_FILE_PATH, &type);
    if (R_SUCCEEDED(rc))
        log_line("stat CJK file: 0x%X type=%d", rc, (int)type);
    else
        log_result("stat CJK file", rc);

    return strcmp(payload, read_buf) == 0;
}

int main(void) {
    if (!ui_init()) {
        consoleInit(NULL);
        printf("LVGL / FreeType initialization failed.\nPress PLUS to exit.\n");
        consoleUpdate(NULL);
        padConfigureInput(1, HidNpadStyleSet_NpadStandard);
        PadState error_pad;
        padInitializeDefault(&error_pad);
        while (appletMainLoop()) {
            padUpdate(&error_pad);
            if (padGetButtonsDown(&error_pad) & HidNpadButton_Plus) break;
            consoleUpdate(NULL);
        }
        consoleExit(NULL);
        return 1;
    }
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);

    PadState pad;
    padInitializeDefault(&pad);

    FsFileSystem *fs = fsdevGetDeviceFileSystem("sdmc");
    int top = 0;
    int visible_lines = ui_visible_lines();
    if (visible_lines > MAX_LINES) visible_lines = MAX_LINES;

    log_line("=== sdmc2 v8 CJK roundtrip ===");
    log_line("base: sdmc:/ROM");
    log_line("dir : %s", CJK_DIR_NAME);
    log_line("file: %s", CJK_FILE_NAME);
    log_line("PLUS exit, UP/DOWN scroll");

    if (!fs) {
        log_line("sdmc filesystem handle is NULL");
    } else if (!ensure_rom_directory(fs)) {
        log_line("setup failed: CJK tests not run");
    } else {
        bool io_ok = ensure_cjk_file(fs);
        bool dir_found = list_dir_find(fs, "/ROM", CJK_DIR_NAME);
        bool file_found = list_dir_find(fs, CJK_DIR_PATH, CJK_FILE_NAME);

        log_line("--- summary ---");
        log_line("direct read/write: %s", io_ok ? "PASS" : "FAIL");
        log_line("/ROM lists CJK dir: %s", dir_found ? "PASS" : "FAIL");
        log_line("CJK dir lists file: %s", file_found ? "PASS" : "FAIL");
    }

    log_line("=== Done ===");

    int held_direction = 0;
    u64 next_repeat_ms = 0;
    while (appletMainLoop()) {
        padUpdate(&pad);
        u64 keys = padGetButtonsDown(&pad);
        u64 held = padGetButtons(&pad);

        if (keys & HidNpadButton_Plus)
            break;
        int direction = !!(held & HidNpadButton_Down) - !!(held & HidNpadButton_Up);
        u64 now_ms = armTicksToNs(armGetSystemTick()) / 1000000;
        bool scroll = direction && (direction != held_direction || now_ms >= next_repeat_ms);
        if (scroll) {
            if (direction > 0 && top + visible_lines < g_line_count) top++;
            if (direction < 0 && top > 0) top--;
            next_repeat_ms = now_ms + (direction != held_direction ? 300 : 50);
        }
        held_direction = direction;

        static char screen[MAX_LINES * (LINE_LEN + 1) + 1];
        size_t used = 0;
        for (int i = 0; i < visible_lines && top + i < g_line_count; i++) {
            size_t len = strlen(g_lines[top + i]);
            memcpy(screen + used, g_lines[top + i], len);
            used += len;
            screen[used++] = '\n';
        }
        screen[used] = '\0';
        ui_show(screen);
        ui_update();
        svcSleepThread(16000000);
    }

    ui_exit();
    return 0;
}
