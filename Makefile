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
DEFINES := -DINNER_HEAP_SIZE=0x4000

COMMON_FLAGS := -Wall -O2 -ffunction-sections -fdata-sections \
	-Wno-unused-function $(ARCH) $(DEFINES) $(INCLUDE) -D__SWITCH__
CFLAGS   := $(COMMON_FLAGS) -std=gnu11
CXXFLAGS := $(COMMON_FLAGS) -fno-rtti -fno-exceptions -std=gnu++17
ASFLAGS  := -g $(ARCH)
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
