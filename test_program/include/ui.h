#pragma once
#include <stdbool.h>
bool ui_init(void);
int ui_visible_lines(void);
void ui_show(const char *text);
void ui_update(void);
void ui_exit(void);
