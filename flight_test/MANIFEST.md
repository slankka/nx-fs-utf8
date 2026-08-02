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

| 52 | `91C73B43` | **F52 决定性实验**：仅把 F51 默认值翻转为 0（exFAT/full，F50 等价），其余不变——检验 FAT32 的 path-transform 锁存是否在首次两字节临时 codecvt 调用前触发 | 🧪 待真机（双介质） |

- F52 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`91C73B433F513728D6A1EF413EE77BE818DD3FCA63E86E34B2533ADDE81164B7`
- 大小：0x29C4 = 10692B；flags=0x78；bss_end=0x8000 对齐。加载器校验通过。
- **预期**：exFAT = 3 PASS（默认 full，无 FAT32 锁存触发）；FAT32 = 3 PASS（若锁存先于
  两字节临时调用）或黑屏（若两字节临时先于锁存）。F52 双介质均 3P 则 **dual 直接完成、无需锚点**。

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
