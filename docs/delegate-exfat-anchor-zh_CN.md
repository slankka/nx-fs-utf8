# 委托任务书：定位 exFAT 挂载锚点（nx-fs-utf8 Dual KIP）

> 委托给：`ams-reverse-engineering-agent`
> 日期：2026-08-02
> 关联项目：`f:\nx_fscodecvt`（分支 `dual-union`，Flight F53 基座）

## 1. 背景与目标

`nx-fs-utf8` 是 FS Overlay KIP，给 Switch FS sysmodule 加 UTF-8 文件名兼容。当前
Dual KIP（F53）用 `g_fat_path` 标志在两种介质间切换 codecvt 行为：

| 介质 | slot0 `oem2unicode` | slot1 `unicode2oem` |
|---|---|---|
| FAT32（`g_fat_path=1`） | `oem2unicode_dbcs_safe`（2 字节受限） | `unicode2oem_bounded_utf8`（写 ≤2B） |
| exFAT（`g_fat_path=0`） | `oem2unicode_utf8`（全量 3 字节） | `unicode2oem_utf8`（全量） |

已实机验证：FAT32 3 PASS（F53 `8DC516AA`）、exFAT 3 PASS（F50 `63FCE7FF`）。
但**同一 KIP 不能同时双介质**：exFAT 需 `g_fat_path=0`（全量），F53 默认 `=1`（受限，
安全）导致 exFAT 3 FAIL。

**任务：在 19.0.1 exFAT-capable FS 二进制中定位一个"只在 exFAT 卷挂载时触发"的
函数/指令点**，用作 exFAT 锚点，接线到已预留的 `fs_codecvt_note_exfat_path()`（置
`g_fat_path=0`），使 F53 在 exFAT 上也能 3 PASS，从而单一 KIP 双介质。

## 2. 输入

- **二进制**：`F:\dumped_firmware\AMS-19.0.1\exFAT\pkg2_out\ini1_out\FS_proper.nso`
  - 格式 NOS0：text @0x1000（0x1CB0E4B）、rodata @0x1CD000、data @0x240000
  - **已验证与 `FsVer_19_0_0_Exfat` offset 表匹配**：codecvt[0]=0xFEAC0（入口
    `39C00008 12001D0A`）、dir_hook=0xD4AF4（`54FFFCE3`）
- **TFP2 参考源码**（PrFILE2，FAT 路径）：`F:\RetroArchCompileProject\TFP2\src\vf\`
  - 已确认：FAT32 路径经全局 `VFipf_vol_set.codeset`（PF_CHARCODE 六槽）分发
  - exFAT 驱动**不在** TFP2 中（FAT-only），需从二进制单独逆向

## 3. 关键事实（已实证）

- **两种介质都走 PrFILE2 path 层**（`transformInUnicode`/`transformFromUnicodeToNormal`
  /`GetNextCharOfPattern` 在 FAT32 和 exFAT 上都被调用，F52 实机证实）→ 这些**不能**
  当介质信号
- FAT32 专属：SFN/pattern 字节级 codecvt 调用（`parseShortName` 等），exFAT 无 8.3 SFN
- 运行变体恒为 **exFAT-capable** FS（19.x ExFAT 变体，含双驱动），介质只决定内部走
  FAT32/PrFILE2 还是 exFAT 驱动路径
- SD 介质实测为真实 exFAT（MBR 类型 0x07、VBR "EXFAT   " 签名、卷标 SamSung-ExF）
- Switch 挂载流：读 MBR 分区表 → 定位分区（实测 LBA 0x10000）→ 读 VBR → 检
  `"EXFAT   "`（偏移 3）签名选 exFAT 驱动

## 4. 目标函数特征（锚点候选）

找到一个**满足全部**条件的函数/指令点：

1. **只在 exFAT 卷挂载时执行**（FAT32 卷挂载不执行，或执行但走不同分支）
2. 在 FS 启动后、首次 exFAT 路径操作前触发（确保 `g_fat_path=0` 先于 codecvt 调用）
3. 偏移可定位、可 B 分支改写（hook 到 `fs_codecvt_note_exfat_path`）
4. 各支持版本（19.0.1/20.2.0/21.2.0/22.0.0/22.5.0）都有对应点（可后续逐个补表）

**最佳候选**：
- exFAT 驱动挂载函数（读 exFAT VBR、校验 BPB 字段）
- exFAT 卷初始化 / codeset 绑定（若有独立 codeset）
- exFAT 目录项读取函数（exFAT 目录项类型码 0x85/0x83 等）
- MBR 分区类型 0x07 → exFAT 驱动的分发点

## 5. 已排查并排除（勿重复）

| 尝试 | 结果 |
|---|---|
| "EXFAT"/"FAT32" 串 ADRP xref（rodata base 0x1CC000） | 0 命中（串是死数据/未引用） |
| 同上 ADR xref | 0 命中 |
| 引导签名立即数 MOVK（"EXFA" 0x41465845、"FAT3" 0x33344154） | 0 命中 |
| rodata 指向串的指针表（u32/u64） | 0 命中 |
| `0x7A1DC` "EXTC"(0x43545845) 检测候选 | 无 vtable 引用、无 "EXTC" 串 → 排除 |
| codecvt 表（.data+0xFB58，base-0 偏移表） | 找到，但分发藏在嵌套结构体指针（volume→codeset→slot） |
| `ldr+blr` / `ldr+add+blr` 分发点扫描 | 0 命中（非该模式） |

分析脚本在 `f:\nx_fscodecvt\tools\f51_analysis\`（f51_*.py、parse_*.py）。

## 6. 推荐切入点

1. 从 **SD/存储挂载层**入手：FS 读 MBR → 分区表 → 逐分区读 VBR → 按签名分发到
   FAT32 或 exFAT 驱动。找"读 VBR 偏移 3 并比较 8 字节"的代码（可能用 memcmp 或
   逐字节比较，不一定引用 rodata 串）
2. 从 **exFAT 驱动注册/初始化**入手：exFAT 驱动挂载函数在卷结构初始化时校验 BPB
   （bytes_per_sector_shift==9、sectors_per_cluster_shift、cluster_count>0 等），
   特征区别于 FAT32 驱动
3. 交叉验证：找到候选后，检查它**不在** FAT32 挂载路径上（对照 FAT32 的
   `VFiPFVOL_p_mount` / `VFiPFFAT_InitFATRegion` 等价物）

## 7. 交付物

1. 锚点函数入口偏移（相对 .text）或指令点偏移（相对 .text）
2. 入口前 2 条原始指令（供 B 分支 + trampoline）
3. 触发语义说明（何时执行、是否 exFAT-only）
4. 若为条件分支点，给出"仅 exFAT 成功路径"的精确位置（最好 hook 在签名匹配成功处，
   避免 FAT32 卷也走到该函数）
5. （可选）各版本偏移

## 8. 验收

- 锚点 hook 后，F53 + 锚点在 exFAT 介质上 3 PASS（direct r/w、/ROM 列 CJK 目录、
  CJK 目录列文件）
- FAT32 介质无回归（3 PASS）
- 无黑屏（优雅降级保持）

## 9. 接口（已就绪）

```cpp
// main.cpp 已预留（F53 基座）
extern "C" void fs_codecvt_note_exfat_path(void);  // g_fat_path = 0
// codecvt_utf8.hpp 已声明；main.cpp 已定义
```

逆向代理只需给出锚点偏移，集成由 nx-fs-utf8 侧完成。
