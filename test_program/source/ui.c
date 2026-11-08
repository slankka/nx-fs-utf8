#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <switch.h>
#include "lvgl.h"
#include "ui.h"

#define WIDTH 1280
#define HEIGHT 720
#define FONT_SIZE 18
#define FONT_COUNT 6
#define MARGIN_Y 4
#define LINE_SPACE 1
#define FOOTER_GAP 4

static Framebuffer fb;
static lv_disp_draw_buf_t draw_buf;
static lv_color_t pixels[WIDTH * 32];
static lv_disp_drv_t display_driver;
static lv_obj_t *label;
static lv_font_t *nintendo_font;
static int log_height;
static lv_ft_info_t fonts[FONT_COUNT];
static unsigned font_count;
static bool pl_ready, ft_ready, fb_ready;

/* LVGL can flush a single refresh in many strips. Acquire and present only
 * once so the linear framebuffer is copied and queued once per refresh. */
static void flush(lv_disp_drv_t *driver, const lv_area_t *area, lv_color_t *colors) {
    static u8 *dst;
    static u32 stride;
    if (!dst) dst = framebufferBegin(&fb, &stride);
    if (dst) {
        int width = area->x2 - area->x1 + 1;
        for (int y = area->y1; y <= area->y2; y++) {
            memcpy(dst + y * stride + area->x1 * sizeof(lv_color_t), colors,
                   width * sizeof(lv_color_t));
            colors += width;
        }
    }
    if (lv_disp_flush_is_last(driver) && dst) {
        framebufferEnd(&fb);
        dst = NULL;
    }
    lv_disp_flush_ready(driver);
}

bool ui_init(void) {
    static const PlSharedFontType types[FONT_COUNT] = {
        PlSharedFontType_Standard, PlSharedFontType_NintendoExt,
        PlSharedFontType_ChineseSimplified,
        PlSharedFontType_ExtChineseSimplified, PlSharedFontType_ChineseTraditional,
        PlSharedFontType_KO
    };
    static const char *names[FONT_COUNT] = {"standard", "nintendo", "simplified", "extended", "traditional", "korean"};
    Result rc = framebufferCreate(&fb, nwindowGetDefault(), WIDTH, HEIGHT, PIXEL_FORMAT_RGB_565, 2);
    if (R_FAILED(rc)) return false;
    fb_ready = true;
    if (R_FAILED(framebufferMakeLinear(&fb))) goto fail;
    lv_init();
    lv_disp_draw_buf_init(&draw_buf, pixels, NULL, WIDTH * 32);
    lv_disp_drv_init(&display_driver);
    display_driver.hor_res = WIDTH;
    display_driver.ver_res = HEIGHT;
    display_driver.flush_cb = flush;
    display_driver.draw_buf = &draw_buf;
    if (!lv_disp_drv_register(&display_driver)) goto fail;
    if (R_FAILED(plInitialize(PlServiceType_User))) goto fail;
    pl_ready = true;
    if (!lv_freetype_init(0, 0, LV_FREETYPE_CACHE_SIZE)) goto fail;
    ft_ready = true;
    for (unsigned i = 0; i < FONT_COUNT; i++) {
        PlFontData data;
        if (R_FAILED(plGetSharedFontByType(&data, types[i]))) continue;
        lv_ft_info_t *info = &fonts[font_count];
        info->name = names[i];
        info->mem = data.address;
        info->mem_size = data.size;
        info->weight = FONT_SIZE;
        info->style = FT_FONT_STYLE_NORMAL;
        if (!lv_ft_font_init(info)) continue;
        if (types[i] == PlSharedFontType_NintendoExt) nintendo_font = info->font;
        if (font_count) fonts[font_count - 1].font->fallback = info->font;
        font_count++;
    }
    if (!font_count) goto fail;
    lv_obj_t *screen = lv_scr_act();
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);
    label = lv_label_create(screen);
    lv_obj_set_style_text_font(label, fonts[0].font, 0);
    lv_obj_set_style_text_color(label, lv_color_white(), 0);
    lv_obj_set_style_text_line_space(label, LINE_SPACE, 0);
    lv_obj_set_style_pad_all(label, 0, 0);
    lv_obj_set_pos(label, 8, MARGIN_Y);
    int line_height = lv_font_get_line_height(fonts[0].font);
    log_height = HEIGHT - 2 * MARGIN_Y - line_height - FOOTER_GAP;
    lv_obj_set_size(label, WIDTH - 16, log_height);
    lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);

    /* The Nintendo font uses private-use Unicode code points for controls. */
    lv_font_glyph_dsc_t glyph;
    bool have_icons = nintendo_font &&
        lv_font_get_glyph_dsc(nintendo_font, &glyph, 0xE0B3, 0) &&
        !glyph.is_placeholder &&
        lv_font_get_glyph_dsc(nintendo_font, &glyph, 0xE0D1, 0) &&
        !glyph.is_placeholder &&
        lv_font_get_glyph_dsc(nintendo_font, &glyph, 0xE0D2, 0) &&
        !glyph.is_placeholder;
    lv_obj_t *footer = lv_label_create(screen);
    lv_obj_set_style_text_font(footer, fonts[0].font, 0);
    lv_obj_set_style_text_color(footer, lv_color_white(), 0);
    lv_obj_set_style_pad_all(footer, 0, 0);
    lv_obj_set_pos(footer, 8, HEIGHT - MARGIN_Y - line_height);
    lv_obj_set_size(footer, WIDTH - 16, line_height);
    lv_label_set_long_mode(footer, LV_LABEL_LONG_CLIP);
    lv_label_set_text(footer, have_icons ?
        "按 \uE0B3 (+) 退出程序，按 \uE0D1（上）和 \uE0D2（下）滚动屏幕" :
        "按 + 退出程序，按上和下可以滚动屏幕");
    return true;
fail:
    ui_exit();
    return false;
}

int ui_visible_lines(void) {
    int line_height = lv_font_get_line_height(fonts[0].font);
    int count = (log_height + LINE_SPACE) / (line_height + LINE_SPACE);
    return count > 0 ? count : 1;
}

void ui_show(const char *text) {
    if (strcmp(lv_label_get_text(label), text) != 0) lv_label_set_text(label, text);
}
void ui_update(void) {
    static u64 previous_ms;
    u64 now_ms = armTicksToNs(armGetSystemTick()) / 1000000;
    if (previous_ms) lv_tick_inc((u32)(now_ms - previous_ms));
    previous_ms = now_ms;
    lv_timer_handler();
}
void ui_exit(void) {
    for (unsigned i = 0; i < font_count; i++) lv_ft_font_destroy(fonts[i].font);
    font_count = 0;
    if (ft_ready) { lv_freetype_destroy(); ft_ready = false; }
    if (pl_ready) { plExit(); pl_ready = false; }
    if (fb_ready) { framebufferClose(&fb); fb_ready = false; }
}
