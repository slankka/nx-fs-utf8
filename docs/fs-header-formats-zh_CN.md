# FS 固件头格式：KIP1 / NSO0 / NOS0 —— 实际固件角度

> 适用范围：HOS 19.0.1 ~ 22.5.0 的 FS sysmodule（exFAT-capable 变体）
> 日期：2026-08-03 · 分支：dual-union
> 所有布局均来自对 `F:\dumped_firmware` 下真实固件解包产物的实测，非理论推测。

## 1. 核心结论：FS 在真实固件里到底是什么

**FS 在真实固件里是 `FS.kip1` —— KIP1 格式（Nintendo 官方）**，不是 NSO0，也不是 NOS0。

固件链：
```
NCA（固件容器）
  └─ package2 (pk21)          ← 开机引导读的压缩包
       └─ INI1（含多个 KIP1 模块：FS/Loader/NCM/sm/...）
            └─ FS.kip1        ← FS 的真实形态（压缩的 KIP1）
                 ├─ FS_decomp.kip1   ← 解压后的 KIP1（分析用）
                 └─ FS_proper.nso    ← 工具转出的"类 NSO"（反汇编用）
```

- **`FS.kip1`**：真实固件形态，Nintendo 官方 KIP1 头。
- **`FS_proper.nso`**：本地工具（如 `kip1_to_nso.py`）把解压 KIP1 转出的扁平文件，**magic 可能是 NSO0 或 NOS0，头布局也因工具而异**——它只是分析产物，**不是固件原始格式**。

## 2. KIP1 头布局（真实固件格式，实测 22.5.0 exFAT）

KIP1 头共 0x100 字节，段表每段 0x10 字节：

| 偏移 | 字段 | 实测值（22.5.0 FS.kip1） |
|---|---|---|
| 0x00 | magic `"KIP1"` | `4B 49 50 31` |
| 0x04 | name[12] | `"FS"`（FS 模块名） |
| 0x10 | title_id (u64) | `0x0100000000000000` |
| 0x20 | .text: file_off / decomp_size / attrib / rsvd | off=0, size=`0x1E5CE4` |
| 0x30 | .rodata | off=`0x1E6000`, size=`0x6A4C0` |
| 0x40 | .data | off=`0x251000`, size=`0x1F558` |
| 0x50 | .bss | off=`0x271000`, size=`0xD9B000` |
| 0x100 | .text 数据起点（解压后连续排布） | — |

要点：
- **KIP1 的段在文件里各自压缩**（`FS.kip1` 是压缩态），`file_off` 是压缩前的逻辑偏移。
- **`FS_decomp.kip1`** = 解压后的 KIP1，段从 0x100 连续排布，`.text` 直接可读。
- KIP 加载器（fusee/Atmosphere）把 KIP1 载入内存后，`.text` 就是我们要 patch 的 FS 代码段。

## 3. 工具产物：NSO0 / NOS0 两种 magic，三种头布局

分析工具把解压 KIP1 转成"类 NSO"文件，实测出现**两种 magic、三种段表布局**：

| 布局 | magic | 段表排列 | 出现在 |
|---|---|---|---|
| **A. 标准 NSO0** | `NSO0` `4E 53 4F 30` | text@0x10/size@0x14, rodata@0x18/size@0x1C, data@0x20/size@0x24, bss@0x28 | 官方 NSO；部分工具 |
| **B. kip1_to_nso 3×u32** | `NOS0` `4E 4F 53 30` | text@0x10/size@0x14/0@0x18, rodata@0x1C/size@0x20/0@0x24, data@0x28/size@0x2C, bss@0x30 | 19.0.1 `FS_proper.nso` |
| **C. 8 字节对齐变体** | `NSO0` | text@0x10, **size@0x18**（0x14=0）, rodata@0x20… | 20.2.0 `FS_proper.nso` |

关键事实：
- **magic 与布局不一一对应**：19.0.1 与 22.5.0 都是 `NOS0`，但 19.0.1 用 3×u32 布局（B），22.5.0（本工具生成的 `FS_proper.nso`）用标准布局（A）。
- **`NOS0` 不是任天堂官方格式**：它是工具写 `0x30534F4E` 时用小端 pack，落盘字节变成 `4E 4F 53 30`（'O'/'S' 交换）。工具作者意图是 NSO0，但落盘是 NOS0；且有些工具自定义了段表排列。
- **`NSO0`（标准布局 A）是唯一"官方" NSO**：Atmosphere `utilities/nxo64.py` 等官方工具只认 `NSO0`。

## 4. 各版本 FS 的实际形态（实测）

| 版本 | 真实固件形态 | 解压态 | 工具 NSO 产物 |
|---|---|---|---|
| 19.0.1 | `FS.kip1` | — | `FS_proper.nso`（NOS0，布局 B 3×u32）|
| 20.2.0 | `FS.kip1` | — | `FS_proper.nso`（NSO0，布局 C，text size@0x18）|
| 21.2.0 | `FS.kip1` | — | `FS.nso`（实为 KIP1）|
| 22.0.0 | `FS.kip1` | `FS_decomp.kip1` | — |
| 22.5.0 | `FS.kip1` | `FS_decomp.kip1` | `FS_proper.nso`（NOS0，布局 A 标准）|

## 5. 到底以哪个为准？

- **回答"FS 是 FS.kip1 还是 NSO0 还是别的"**：真实固件里 FS 就是 **`FS.kip1`（KIP1）**；NSO0/NOS0 全是分析工具转出的副本。
- **对 KIP 运行时**：完全无关。我们的 KIP 通过 `matches_fs()` 在**已加载到内存的 FS 代码**里做 opcode 匹配找六槽，**从不解析任何容器头**。所以 NSO0/NOS0/KIP1 的差异只影响离线分析脚本。
- **对离线脚本**：必须按 magic 分流 + 布局自适应：
  - KIP1 → 读 0x20 段表，text 从 0x100 起；
  - NSO0/NOS0 → `text size = @0x14`，若为 0 则回退 `@0x18`。
  （`verify_all_versions.py::load_text()` 已实现。）

## 6. 经验教训

- 判断 FS 文件是哪个变体：读 ExFAT-capable 六槽 `@0x111520` 是否 = `0x39C00008`；是则 ExFAT-capable，否则查 FAT 六槽 `@0x1001D0`。
- 22.x 的 **FAT 变体与 ExFAT-capable 变体 offset 不同**（FAT: 六槽 0x1001D0/dir 0xE6F80；exFAT: 六槽 0x111520/dir 0xE7040），不要混用。
- `kip1_to_nso.py` 的 magic 注释已修正：`0x30534F4E` 小端落盘为 `NOS0`，不是 `NSO0`。
