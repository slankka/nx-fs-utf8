# Flight Test Manifest — F49 dual-union（FAT32 + exFAT 并集）

> 分支：`dual-union`（从 `codex/exfat` 派生）。目标：解决 D69657FD（FAT32 双契约）
> 在 exFAT 介质上 FAIL PASS FAIL 的问题，同时不破坏 FAT32 介质回归。
> 编号接续 lineage：F48 = `B20FFE7A`（FAT32 双契约跨版本静态推广）。

## 背景（根因已确认）

Dual KIP（D69657FD，9972B）实际只是 **FAT32 双契约**：只装 slot0（两字节有损）+
slot3 + path-transform + parseShortName + dir，**缺 slot1/2/4/5，且不 NOP sanitize**。
exFAT 驱动路径直接依赖六槽 PF_CHARCODE（不走 path-transform），因此 exFAT 介质上
codecvt 层自相矛盾 → direct r/w FAIL；dir hook 两分支逐字节相同，exFAT 上 test 2
PASS 证明 dir hook 不是差异化因素。

## F49 产物（dual-union 首次构建）

| # | SHA256 | 变更 | 结果 |
|---|--------|------|------|
| 49 | `B053C59A` | `install()` 装**并集**：六槽全 hook（slot0=`oem2unicode_dbcs_safe` 两字节安全保持 FAT32 安全）+ slot1/2/4/5 + path-transform + parseShortName + dir + sanitize NOP；`matches_fs` 严格要求六槽+path+SFN+dir+identity_checks | ❌ exFAT：FAIL PASS FAIL，目录重复创建（与 D69657FD 相同） |

> **F49 结论**：F49 新增的 slot1/2/4/5 + sanitize NOP 在 exFAT 上无任何效果（结果与
> D69657FD 逐项相同），证明 exFAT 失败路径由 **slot0 两字节有损解码**驱动：exFAT 驱动
> 路径依赖 slot0 做完整三字节 CJK 解码，有损后建名不匹配 → 重复创建。

| 50 | `63FCE7FF` | F49 基础上 **slot0 换回完整三字节 `oem2unicode_utf8`**（其余并集不变：slot1/2/4/5 + path-transform + SFN + dir + sanitize NOP） | ✅ **exFAT：3 PASS** |

> **F50 结论**：slot0 完整三字节 = exFAT 侧唯一缺口，并集（六槽+path-transform+SFN+
> dir+sanitize NOP）在 exFAT 上完全成立。⚠️ F50 在 **FAT32 上预计黑屏**：源码确认
> `unicode2oem`（slot1）存在两字节临时缓冲（`pf_path.c:167 tmp_wc` / `:595 Dest[2]`），
> FAT32 路径写爆 → 真正 dual 需 slot0+slot1 按介质分发。

| 51 | `07DD6224` | **F51 介质分发**：`g_fat_path` 标志（默认 1=FAT32 受限，安全）驱动 slot0/slot1 分发器——slot0（FAT32=`oem2unicode_dbcs_safe` / exFAT=`oem2unicode_utf8`），slot1（FAT32=`unicode2oem_bounded_utf8` 写≤2B / exFAT=`unicode2oem_utf8`）；FAT32 锁存=4 个 path-transform hook 入口；exFAT 锚点 `fs_codecvt_note_exfat_path` 预留未接线；slot2/4/5 保持全量 UTF-8 | ✅ **FAT32：3 PASS** |

> **F51 结论**：FAT32 侧分发器成立——受限 slot0/slot1 + slot2/4/5 UTF-8 + sanitize NOP 均不破坏
> FAT32。至此双介质各自 3P：exFAT=F50（`63FCE7FF`），FAT32=F51（`07DD6224`）。

| 52 | `91C73B43` | **F52 决定性实验**：仅把 F51 默认值翻转为 0（exFAT/full，F50 等价），其余不变——检验 FAT32 的 path-transform 锁存是否在首次两字节临时 codecvt 调用前触发 | ⚠️ FAT32：3 PASS；**exFAT：FAIL PASS FAIL（重复建目录）** |

> **F52 关键结论（推翻旧假设）**：exFAT 上 `g_fat_path` 被锁存成 1（受限），唯一置 1 的
> 是 4 个 path-transform hook 入口 → **path-transform 例程在 exFAT 上也被调用**（两种介质
> 都走 PrFILE2 path 层，仅 SFN/pattern 字节级 codecvt 是 FAT32 专属）。因此：
> ① path-transform **不能**当 FAT32 信号；② F52 的锁存正是 exFAT 失败元凶；
> ③ 真正的 dual 需**移除 path-transform 锁存** + 默认 1（受限安全）+ **exFAT 专属锚点**（如
> 0x7A1DC "EXTC" 检测，vtable 间接调用，待确认）置 0。

| 53 | `8DC516AA` | **F53 锚点就绪基座**：移除 4 个 path-transform 锁存调用（F52 元凶，也会撤销未来 exFAT 锚点），默认=1（受限安全），`fs_codecvt_note_exfat_path()` 保持预留 | 🧪 待真机（预期同 F51：FAT32 3P / exFAT 3 FAIL） |

- F53 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`8DC516AA3AB66382ABC11A5853A984F93F86F6CB138527D3443B926D45866953`
- 大小：0x2988 = 10632B；flags=0x78；bss_end=0x8000 对齐。加载器校验通过。
- **待接入**：exFAT 专属锚点（定位 exFAT 挂载/检测函数后调 `fs_codecvt_note_exfat_path()` 置 0），
  完成后 F53+锚点 = 双介质 dual（FAT32 3P + exFAT 3P）。

| 55 | `1A374E1E` | **F55 锚点集成**：在 F53 基座上 hook **exFAT 引导区校验和函数**（19.0.1 @`0x0E2BA0`，`ams-reverse-engineering-agent` 交付，唯一调用点 `0x0FE690`⊂exFAT 挂载 `0x0FE550`）→ 探针（0xFED00 死区）置 `g_fat_path=0` → slot0/slot1 全量 UTF-8 | 🧪 待真机（双介质） |

- F55 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`1A374E1E128BBF23866A5BD1455F922205AB9A9AD1A9F3A131D498078F05480B`
- 大小：0x2AC8 = 10952B；flags=0x78；bss_end=0x8000 对齐。加载器校验通过。
- **锚点语义**（已验证）：exFAT VBR 校验通过后才执行（FAT32 走独立 PrFILE 驱动，VBR 校验把关），
  挂载期早于任何路径操作；函数体 0x340B 在 FAT32-only 二进制中不存在（最强证据）。
- **⚠️ 多卷风险**：锚点对**任意 exFAT 卷**触发。若 eMMC USER 分区是 exFAT 且先于 SD 挂载，
  会把 `g_fat_path` 置 0 → FAT32 SD 操作可能用全量越界（黑屏/FAIL）。F55 双介质测试将揭示：
  - exFAT SD：预期 **3 PASS**（SD exFAT 挂载触发锚点）
  - FAT32 SD：若 eMMC USER 为 FAT32/其他 → 3 PASS；若为 exFAT → 可能回归（此时需把锚点限定到 SD 卷）
- **多版本**：20.5.0=`0x0EDA80`、21.2.0=`0x0F3210`、22.0/22.5=`0x0F59C0`（cave 待补，本次仅 19.0.1 启用）

| 56 | `A195CEFF` | **F56 20.2.0 锚点启用**：定位并接线 20.2.0 exFAT 引导区校验和锚点。20.2.0 为 **NSO0** 格式（19.0.1 为 NOS0，text_size 字段偏移不同）；锚点 `0x0ED980`=`D101C3FF`(sub sp,#0x70)+`A9017BFD`，体内 `cmp #0x70/#0x6a + ror w24,#1` 校验和循环与 19.0.1 同构（对照 20.5.0 `0x0EDA80` 仅差 0x300）；FAT-only 二进制 `0x0ED980`=`2A1803E3` 非锚点（exFAT-only 验证）；探针死区 `0x1096C0`（dead uni2oem body，dir trampoline `0x1096E0` 前 0x20B，不重叠） | 🧪 待真机（20.2.0 exFAT 3P？） |

- F56 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`A195CEFF6AABF48C5A19DA0538485FA2915CC45CB541C0F24F43FB320CB0372C`
- 大小：0x2AC8 = 10952B；flags=0x78；bss_end=0x8000 对齐。加载器校验通过。
- **20.2.0 锚点定位方法**（capstone）：FS_proper.nso（NSO0）→ codecvt[0]@`0x109440`=`39C00008` 匹配 → 在 20.5.0 锚点 `0x0EDA80` 附近反汇编 → 0x0ED980 起 `sub sp,#0x70`+校验和循环（跳过 0x6a/0x70 偏移）。
- **版本选择不受 hash 影响**：`matches_fs` 为纯 opcode 匹配（codecvt[0] 双指令 + dir/path/pattern/SFN 入口 + identity_checks），`g_fs_hashes` 仅文档（已把 20.2.0 实际 hash `ADEDF4BC...` 填回表）。
- **F55 遗留 20.2.0 FAIL PASS FAIL 根因**：20.2.0 表 exfat_cave=0 被 install() 跳过 → 锚点未接线 → g_fat_path 保持 1（受限）→ 20.2.0 exFAT 驱动路径走受限 slot0/slot1 → 重复建目录。F56 已接线。
- **多卷风险同 F55**：锚点对任意 exFAT 卷触发，需双介质实测确认无 eMMC USER exFAT 误触发。

| 57 | `66C47498` | **F57 决定性二分实验**：仅把 `g_fat_path` 默认翻转为 **0**（exFAT 全量 UTF-8，F50 等价，**无锚点依赖**），其余与 F56 完全相同（含 20.2.0 锚点字段，但默认已是 0） | 🧪 待真机（**只测 20.2.0 exFAT**；FAT32 会黑屏勿测） |

- F57 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`66C47498CD20A23F012CDE43E25B8D4095BFDF6DDBC1FEE7A20EFC8A1E021DDA`
- 大小：0x2AC4 = 10948B；flags=0x78；bss_end=0x8000 对齐。加载器校验通过。
- **F56 20.2.0 FAIL PASS FAIL 的分支判定**（二选一）：
  - **若 F57 20.2.0 exFAT = 3 PASS** → 20.2.0 全量 codecvt OK → F56 失败 = **锚点未生效**（g_fat_path 保持 1 受限）→ 查探针写入/地址/触发（F49 受限模式特征 FAIL PASS FAIL 吻合）
  - **若 F57 20.2.0 exFAT ≠ 3 PASS** → **20.2.0 全量 codecvt 本身有 bug**（20.2.0 从未验证过全量；F50 的 3P 是 19.0.1）→ 查 20.2.0 六槽偏移/调用约定差异

> **✅ F57 实机：20.2.0 exFAT = 3 PASS** → 分支 1 成立：**20.2.0 全量 codecvt OK，F56 失败 = 锚点未生效**。

| 58 | `9FF8B436` | **F58 探针执行检测**：默认 0（F57 全量基座，exFAT 3P 已验证）+ 锚点探针**反向写 `g_fat_path=1`**（mov w17,#1 + str w17,[x16]）。探针未执行→全程 0→3P；探针执行→挂载时置 1→受限→FAIL PASS FAIL | 🧪 待真机（20.2.0 exFAT，检测探针是否执行） |

- F58 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`9FF8B436ABB8090BC0B79AF7817CAC9398DAD76361F827CFFE3CE2C2EF57A745`
- 大小：0x2AC4 = 10948B；flags=0x78。探针 6 指令 0x18B（cave 0x1096C0+0x18=0x1096D8 < dir trampoline 0x1096E0 ✓）
- **背景链**：F56（默认1+锚点写0）FAIL PASS FAIL → 已强烈暗示探针未执行（若执行应 3P）。F57（默认0）3P 证明全量 OK，但默认 0 掩蔽了探针。F58 用反向探针一锤定音。
- **探针地址已排除 bug**：KIP 链接基址 0x0（fs_codecvt.ld），ADRP 为 PC 相对，install() 里 `&g_fat_path` 运行时正确；encode_adrp delta < 1MB（F56 有 hook 证明 encode_adrp 成功）
- **最可能根因**：`0x0ED980` 虽在"挂载函数"（读 VBR+校验+置标志+注册卷）内被唯一调用，但 20.2.0 该函数可能处理**其他 exFAT 卷**（eMMC 分区），SD exFAT 挂载走新路径 → 锚点不触发

| 59 | `B78E72FB` | **F59 无分发方案（锚点方案弃用）**：slot0 永远全量 UTF-8（`oem2unicode_utf8`）+ slot1 永远受限 ≤2B（`unicode2oem_bounded_utf8`）+ slot2/4/5 UTF-8；**移除锚点探针 + 清零全部 exfat offset 字段**。依据 PrFILE2 源码（见下） | ✅ **双介质 3 PASS：20.2.0 exFAT 3P + 19.0.1 FAT32 3P** |

- F59 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`B78E72FB56085E130E445641426EDB2651EA19DE375473F49DE4B4DA8FDD7F55`
- 大小：0x28BC = 10428B（比 F56-58 小，探针已移除）
- **PrFILE2 源码依据**（Explore 代理全量分析 `TFP2\src\vf\`）：
  - **codeset 全局 CP932 永不切换**：`VFiPFVOL_p_setcode` 仅 `InitModule` 调用一处，挂载/格式化/卷切换均不改 → **锚点方案架构上不成立**（exFAT 挂载无 codeset 翻转信号）
  - **slot0 全量 FAT32 安全**：oem2unicode 所有调用点输出**单 pf_u16**（BMP 2 字节天然满足），无受限数组（唯一 `FileNameW[13]` 承载短名够用）
  - **slot1 必须受限**：3 处严格 2 字节 DBCS 临时缓冲 —— `OEM_ConvertFWchar`(dst)、`GetNextCharOfPattern`(tmp_wc)、`GetLengthFromUnicode`(Dest[2])，CJK 3 字节写入 = **栈破坏**（FAT32 黑屏源码级根因）；受限 + slot2 对 CJK 返回 2 与 FAT32 SFN 8.3 记账兼容（`parseShortName` 硬编码 `width-=2`）
  - **待验证风险**：exFAT 路径 slot1 受限是否够用（受限把 3 字节 CJK 截 2 字节；若 exFAT 的 slot1 调用点需完整编码 → 建名不匹配 → 需转调用点分发）
- **方案对比**：F59 若双介质 3P = 终极方案（无 g_fat_path、无锚点、无介质信号，纯静态六槽）

> **✅ F59 实机：双介质 3 PASS（20.2.0 exFAT 3P + 19.0.1 FAT32 3P）—— 终极方案达成！**
> **结论**：exFAT 路径的 slot1 受限（截 3B→2B）**不影响**中文文件名读写/枚举（F59 的 slot0 全量正确解码 + slot1 受限编码仍保持 UTF-8 语义，长度记账按 slot2 宽 2 与两介质兼容）。F49→F59 迭代闭环：
> - slot0 全量 = exFAT 修复（F50）+ FAT32 安全（PrFILE2 源码：oem2unicode 调用点输出单 u16）
> - slot1 受限 = FAT32 修复（F51）+ exFAT 兼容（F59 实测）
> - **不再需要 g_fat_path 分发 / exFAT 锚点 / 介质信号**——纯静态六槽，跨版本仅依赖六槽偏移表（已支持 19.0.1/20.2.0/21.2.0/22.0.0/22.5.0）

- F50 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`63FCE7FF645B39C3592983496C3D535077A916D965F483748769C817621D9546`
- 大小：0x284C = 10316B；flags@0x1F=`0x78`；bss_end=0x8000 对齐。加载器校验通过。
- **预期**：exFAT 上等价于已验证的 exFAT 六槽 KIP（slot0=完整三字节）→ 3 PASS；
  **FAT32 上预计黑屏**（完整三字节重犯 FAT 两字节临时缓冲越界，F16/F24/F28）——这正用于确认 slot0 冲突，随后做 LR 分发（F51）。

## 预期

- **exFAT 介质**：六槽补齐 + sanitize NOP → direct r/w 应恢复 PASS；dir hook 不变 → 枚举 PASS。
  风险：slot0 用两字节有损，若 exFAT 路径的 slot0 调用点也遇到三字节 CJK，名称可能有损
  （此时需升级为运行时路径/卷型判定）。
- **FAT32 介质**：保持 slot0 两字节安全 + path-transform + SFN，行为与 D69657FD 相同 → 应无回归。
  风险：新增 sanitize NOP 是否对 FAT32 有害（F46 仅确认"不需要"，未确认"无害"）。

## 测试清单

- [ ] exFAT 介质：`--- summary ---` 三项（direct read/write / /ROM lists CJK dir / CJK dir lists file）
- [ ] FAT32 介质：同样三项回归，确认 sanitize NOP 无回归
- [ ] 启动无黑屏（优雅降级未受影响）

## 回退

- exFAT 六槽（6581B857，`codex/exfat`）
- FAT32 双契约（D69657FD，`main` / 旧 fsoverlays 部署）
