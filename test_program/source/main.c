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

#define MAX_LINES 160
#define LINE_LEN 128
#define VISIBLE_LINES 38

#define CJK_DIR_NAME "\xE4\xB8\xAD\xE6\x96\x87\xE7\x9B\xAE\xE5\xBD\x95"
#define CJK_FILE_NAME "\xE5\xBE\x80\xE8\xBF\x94\xE6\xB5\x8B\xE8\xAF\x95.txt"
#define CJK_DIR_PATH "/ROM/" CJK_DIR_NAME
#define CJK_FILE_PATH CJK_DIR_PATH "/" CJK_FILE_NAME

static char g_lines[MAX_LINES][LINE_LEN];
static int g_line_count;

static void log_line(const char *fmt, ...) {
    if (g_line_count >= MAX_LINES)
        return;

    va_list args;
    va_start(args, fmt);
    vsnprintf(g_lines[g_line_count], LINE_LEN, fmt, args);
    va_end(args);
    g_line_count++;
}

static void log_result(const char *label, Result rc) {
    log_line("%s: 0x%X %s", label, rc, R_SUCCEEDED(rc) ? "OK" : "FAIL");
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
    consoleInit(NULL);
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);

    PadState pad;
    padInitializeDefault(&pad);

    FsFileSystem *fs = fsdevGetDeviceFileSystem("sdmc");
    int top = 0;

    log_line("=== sdmc2 v8 CJK roundtrip ===");
    log_line("base: sdmc:/ROM");
    log_line("dir : %s", CJK_DIR_NAME);
    log_line("file: %s", CJK_FILE_NAME);
    log_line("PLUS exit, UP/DOWN scroll");

    if (!fs) {
        log_line("sdmc filesystem handle is NULL");
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

    while (appletMainLoop()) {
        padUpdate(&pad);
        u64 keys = padGetButtonsDown(&pad);

        if (keys & HidNpadButton_Plus)
            break;
        if ((keys & HidNpadButton_Down) && top + VISIBLE_LINES < g_line_count)
            top++;
        if ((keys & HidNpadButton_Up) && top > 0)
            top--;

        consoleClear();
        for (int i = 0; i < VISIBLE_LINES && top + i < g_line_count; i++)
            printf("%s\n", g_lines[top + i]);
        consoleUpdate(NULL);
    }

    consoleExit(NULL);
    return 0;
}
