# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 slankka

.SUFFIXES:

ifeq ($(strip $(DEVKITPRO)),)
$(error "Please set DEVKITPRO in your environment. export DEVKITPRO=<path-to-devkitpro>")
endif

TARGET  := fs_codecvt_dual
BUILD   := build
SOURCES := source/nx source source/utils
INCLUDES := include
PYTHON  ?= python3

ifneq ($(BUILD),$(notdir $(CURDIR)))
PROJECT_DIR ?= $(CURDIR)
else
PROJECT_DIR ?= $(CURDIR)/../
endif

include $(DEVKITPRO)/libnx/switch_rules

ARCH    := -march=armv8-a -mtune=cortex-a57 -mtp=soft -fPIE

# Overlay .bss size.  extent = bss_offset + bss_size, so this directly controls
# how far the following FS image is shifted.
HEAP    ?= 0x4000
DEFINES := -DINNER_HEAP_SIZE=$(HEAP)

# Diagnostic: grow the overlay extent using .data instead of .bss, so that
# "extent is too large" can be tested independently of "bss was declared".
#   make DIAG=11 EXTENT_PAD=0x4fc0
ifdef EXTENT_PAD
DEFINES += -DFS_DIAG_EXTENT_PAD=$(EXTENT_PAD)
endif

ifdef EXTRA_DEFINES
DEFINES += $(EXTRA_DEFINES)
endif

# Diagnostic build: use the full three-byte UTF-8 encoder in codecvt slot 1
# (F57-equivalent).  The default (bounded, <=2 bytes) is what v3.2.0 ships.
#   make SLOT1_FULL=1
ifdef SLOT1_FULL
DEFINES += -DFS_SLOT1_FULL=1
endif

# Diagnostic build: install only a subset of the hooks, to bisect a boot-time
# black screen on real hardware.  Default (4) is the shipping behaviour.
#   0 = overlay injected but completely inert
#   1 = codecvt[0] only
#   2 = codecvt[0..5] + sanitize NOPs
#   3 = 2 + path/pattern/SFN string hooks (no Directory::Read trampoline)
#   4 = full
#   make DIAG=2
ifdef DIAG
DEFINES += -DFS_DIAG_LEVEL=$(DIAG)
endif

# Diagnostic builds for the startup sequence only (no hooks are installed at
# all).  Each step adds exactly one action, so a black screen pinpoints the
# offending instruction group.
#   10 = jump straight to FS, 0x3000 extent (no bss at all)
#   11 = jump straight to FS, shipping 0x7000 extent
#   12 = 11 + SVC 0x73 permission calls
#   13 = 12 + clear .bss
#   14 = 13 + .dynamic relocations
#   15 = 14 + __initheap/__init  (identical to the shipping path with DIAG=9)
ifeq ($(DIAG),10)
DEFINES += -DFS_DIAG_SKIP_ALL=1
endif
ifeq ($(DIAG),11)
DEFINES += -DFS_DIAG_SKIP_ALL=1 -DFS_DIAG_KEEP_EXTENT=1
endif
ifeq ($(DIAG),12)
DEFINES += -DFS_DIAG_SKIP_BSS=1 -DFS_DIAG_SKIP_RELOC=1 -DFS_DIAG_SKIP_INIT=1 -DFS_DIAG_KEEP_EXTENT=1
endif
ifeq ($(DIAG),13)
DEFINES += -DFS_DIAG_SKIP_RELOC=1 -DFS_DIAG_SKIP_INIT=1 -DFS_DIAG_KEEP_EXTENT=1
endif
ifeq ($(DIAG),14)
DEFINES += -DFS_DIAG_SKIP_INIT=1 -DFS_DIAG_KEEP_EXTENT=1
endif

COMMON_FLAGS := -Wall -O2 -ffunction-sections -fdata-sections \
	-Wno-unused-function $(ARCH) $(DEFINES) $(INCLUDE) -D__SWITCH__
CFLAGS   := $(COMMON_FLAGS) -std=gnu11
CXXFLAGS := $(COMMON_FLAGS) -fno-rtti -fno-exceptions -std=gnu++17
ASFLAGS  := -g $(ARCH) $(DEFINES)
LDFLAGS  := -specs=$(PROJECT_DIR)/fs_codecvt.specs -g $(ARCH) \
	-Wl,-Map,$(notdir $*.map)

# Link through the C++ driver so constructors and the C++ runtime ABI match.
LD := $(CXX)

ifneq ($(BUILD),$(notdir $(CURDIR)))

export OUTPUT := $(CURDIR)/$(TARGET)
export TOPDIR := $(PROJECT_DIR)

export VPATH := $(foreach dir,$(SOURCES),$(CURDIR)/$(dir))
export DEPSDIR := $(CURDIR)/$(BUILD)

CFILES   := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.c)))
CPPFILES := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.cpp)))
SFILES   := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.s)))

export OFILES := $(CPPFILES:.cpp=.o) $(CFILES:.c=.o) $(SFILES:.s=.o)
export INCLUDE := $(foreach dir,$(INCLUDES),-I$(CURDIR)/$(dir)) \
	$(foreach dir,$(SOURCES),-I$(CURDIR)/$(dir)) \
	-I$(CURDIR)/$(BUILD)

.PHONY: all clean $(BUILD)

all: $(BUILD)

$(BUILD):
	@mkdir -p $@
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile

clean:
	@echo "cleaning $(TARGET)"
	@rm -rf $(BUILD) $(OUTPUT).elf $(OUTPUT)_unpacked.kip

else

DEPENDS := $(OFILES:.o=.d)

.PHONY: all

all: $(OUTPUT)_unpacked.kip

$(OUTPUT)_unpacked.kip: $(OUTPUT).elf $(PROJECT_DIR)/fs_codecvt.json \
	$(PROJECT_DIR)/tools/elf2kip_uncompressed.py
	@$(PYTHON) $(PROJECT_DIR)/tools/elf2kip_uncompressed.py \
		$(OUTPUT).elf $(PROJECT_DIR)/fs_codecvt.json $@
	@echo "built ... $(notdir $@)"

$(OUTPUT).elf: $(OFILES)

-include $(DEPENDS)

endif
