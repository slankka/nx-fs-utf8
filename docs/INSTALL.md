# FS 中文路径支持补丁（KIP）安装说明

> 本补丁通过 **Hekate 修改版** 加载 KIP，对 `FS.kip1` 进行增强，解除任天堂对 OEM 字符集写死 **CP932** 的限制，使 FS 支持 UTF-8（中文）文件路径。

---

## 适用对象

- 本 KIP **仅面向自制软件开发者**。
- 如果您是**非开发者**，除非特别必要，请**勿使用**。

## 反馈

- 反馈地址：<https://github.com/slankka/nx-fs-utf8/issues>
- 请**文明发言**，禁止辱骂、攻击；可以使用中文。

---

## 安装方法

1. 将发布包内容复制到 **SD 卡根目录**。
2. `nyx`即Hekate图形界面为英文原版，可自行用其他汉化版本覆盖 `nyx`。

**最小安装（必须的文件）：**

```text
bootloader/update.bin
fsoverlays/（整个文件夹）
sys/emummc.kipm(这个也必须替换，具体原因详见下方仓库)
atmosphere/reboot_payload.bin
```

## Hekate 配置（hekate_ipl.ini）

> ⚠️ **禁止使用 `kip1=` 方式**——这是原版方式，不支持本 KIP。

请在启动项中通过 `fsoverlay=` 加载，且 **KIP 文件名必须与文件夹内实际文件名一致**：

```ini
fsoverlay=bootloader/fsoverlays/fs_codecvt_dual_unpacked.kip
```

---

## 发布链接

| 项目 | 链接 |
|---|---|
| 本 KIP 发布地址 | <https://github.com/slankka/nx-fs-utf8/releases/tag/3.1.0> |
| 加载本 KIP 所需的 Hekate（当前**唯一**支持 `fsoverlay` 的版本）| <https://github.com/slankka/hekate-fs-overlay/releases/tag/fo-1> |

## 排障

- **测试发现问题** → 直接删除 `fsoverlay=` 这一项即可。
- **创建了重复的中文目录** → 使用 `chkdsk` 修复 SD 卡即可。

> 注意：由于测试过程繁琐，**未能覆盖全部固件版本**，仅对一部分版本做了实机回归。

---

## 支持版本矩阵

| HOS Version | FAT32 media (alone) | exFAT media (alone) | One-KIP dual-media |
|---|---|---|---|
| 19.0.1 | ✅ TESTED (3/3) | ✅ offset verified | ✅ offset verified |
| 20.2.0 | ✅ offset verified | ✅ TESTED (3/3) | ✅ offset verified |
| 21.2.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |
| 22.0.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |
| 22.5.0 | ✅ offset verified | ✅ offset verified | ✅ offset verified |

---

## 免责声明

- 本补丁仅面向自制软件与开发者场景。**理论上，正常使用的任何程序都不会故意读写 UTF-8 编码的 CJK（中文）目录名**——除非您是开发者，或专门构造了此类文件名。因此，在日常使用中，本补丁不应产生任何可感知的副作用。
- 本补丁不会主动修改、删除或影响您现有的文件与目录；它只增强 FS 对 UTF-8 CJK 路径的处理能力。
- 但以下原因仍使风险在理论上无法完全排除：
  - 固件版本差异 / 测试面未完全覆盖（目前仅对部分版本做过实机回归，其余为 offset verified）；
  - 未覆盖到的使用场景或系统服务行为。
- 万一（极小概率）出现**无法开机、无法关机**等情况，请**不要慌张**：
  1. 直接**强制关机**（长按电源键 12 秒以上）；
  2. 取出 SD 卡，删除 `fsoverlay=` 这一项（或直接移除补丁 KIP）；
  3. 重新开机即可恢复原状。
- **为稳妥起见，强烈建议**：安装本补丁前**备份好您的重要数据**（尤其是 SD 卡上的数据）。
- 使用本补丁即表示您已知悉并自行承担上述风险。

---

*作者：知识碎片 · 时间：2026-08-03*
