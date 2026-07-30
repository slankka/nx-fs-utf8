/*
 * Copyright (c) 2019 m4xw
 * Copyright (c) 2019 Atmosphere-NX
 * Copyright (c) 2026 slankka
 * SPDX-License-Identifier: GPL-2.0-only
 */

/**
 * @file smc.h
 * @brief Secure monitor call wrappers.
 */
#pragma once
#include "../utils/types.h"
#include "svc.h"

#ifdef __cplusplus
extern "C" {
#endif

u64 smcGenerateRandomU64(void);

#ifdef __cplusplus
}
#endif
