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
| 49 | `B053C59A` | `install()` 装**并集**：六槽全 hook（slot0=`oem2unicode_dbcs_safe` 两字节安全保持 FAT32 安全）+ slot1/2/4/5 + path-transform + parseShortName + dir + sanitize NOP；`matches_fs` 严格要求六槽+path+SFN+dir+identity_checks | 🧪 待真机 |

- 文件：`flight_test/fs_codecvt_dual_unpacked.kip`
- SHA-256 完整：`B053C59A186E3D0FD06702AEEAC739DD547942AFD3B51FEE24B3B523A90CDA3A`
- KIP1 flags@0x1F=`0x78`（未压缩，与 D69657FD 相同）；三段之和+0x100 == 0x28BC == 文件大小；
  bss_end=0x8000 对齐。加载器校验通过。
- 大小：10428B（text=0x1C00 ro=0xAE4 data=0xD8 bss=0x4000）

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
