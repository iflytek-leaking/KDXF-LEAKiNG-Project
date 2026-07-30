# FDL 文件使用说明

## 什么是 FDL 文件

FDL（Firmware Download）文件是紫光展锐（SpreadTrum/Unisoc）深刷工具 spd_dump 必须的固件加载文件。BootROM 本身不具备读写闪存的能力，需要通过 FDL 文件初始化内存和分区系统后才能进行读写操作。

| 文件 | 作用 | 加载顺序 |
|------|------|---------|
| FDL1 | 初始化设备内存空间 | 第一个加载 |
| FDL2 | 初始化分区系统 | 第二个加载 |

---

## 文件目录结构

```
fdls/
├── ud710/
│   ├── 0x5500_ud710       # FDL1 - 用于 chip0/1/2 UD710 机型
│   └── 0x9efffe00_ud710   # FDL2 - 用于 chip0/1/2 UD710 机型
├── ums9620/
│   ├── fdl1-dl.bin        # FDL1 - 用于 UMS9620 机型
│   └── fdl2-dl.bin        # FDL2 - 用于 UMS9620 机型
└── (其他芯片)
```

---

## 使用方法

### 方法一：新版 spd_dump（推荐）

新版 spd_dump 使用 `fdl` 命令，需要手动指定加载地址：

```
# UD710 芯片
BROM> loadfdl 0x5500_ud710
FDL1> loadfdl 0x9efffe00_ud710
FDL1> exec
FDL2>
```

```
# UMS9620 芯片
BROM> loadfdl fdl1-dl.bin
FDL1> loadfdl fdl2-dl.bin
FDL1> exec
FDL2>
```

### 方法二：旧版 spd_dump

旧版 spd_dump 使用 `loadfdl` 命令：

```
BROM> loadfdl 0x5500_ud710
FDL1> loadfdl 0x9efffe00_ud710
FDL1> exec
FDL2>
```

---

## 关键注意事项

| 警告 | 说明 |
|------|------|
| **【危险】不同芯片不通用** | 不同芯片使用的 FDL 文件完全不同，切勿混用！ |
| **【危险】加载地址错误** | 使用新版 `fdl` 命令时，地址参数错误会导致推送失败，严重时可能损坏设备 |
| **【注意】加载顺序** | 必须先加载 FDL1，再加载 FDL2，顺序不可颠倒 |
| **【注意】FDL1 文件名规则** | 文件名中带有加载地址提示（如 `0x5500`=0x5500, `fdl1-dl`=0x65000800） |

### 芯片与 FDL 对应关系

| 芯片 | FDL1 文件名 | FDL1 地址 | FDL2 文件名 | FDL2 地址 |
|------|------------|----------|------------|----------|
| UD710 chip0/1 | `0x5500_ud710` | `0x5500` | `0x9efffe00_ud710` | `0x9efffe00` |
| UD710 chip2 | `c2_0x5500` | `0x5500` | `c2_0x9efffe00` | `0x9efffe00` |
| T310 / ums312 | `0x5500_t310` | `0x5500` | `0x9efffe00_t310` | `0x9efffe00` |
| UMS9620 (T760) | `fdl1-dl.bin` | `0x65000800` | `fdl2-dl.bin` | `0xb4fffe00` |

> **【故障排除】** chip2 用户如果 `c2_0x5500` 推送失败，可尝试改用 `0x5500_ud710`。

---

## 自动推送 FDL 的批处理脚本

如果频繁进行刷机操作，可以创建 `.bat` 批处理文件以自动推送两个 FDL：

```batch
spd_dump --wait 300 fdl [fdl1文件路径] [fdl1地址] fdl [fdl2文件路径] [fdl2地址] exec
```

示例（UD710 chip0/1）：
```batch
spd_dump --wait 300 loadfdl 0x5500_ud710 loadfdl 0x9efffe00_ud710 exec
```
示例（UD710 chip2）：
```batch
spd_dump --wait 300 loadfdl c2_0x5500 loadfdl c2_0x9efffe00 exec
```
示例（T310 / ums312）：
```batch
spd_dump --wait 300 loadfdl 0x5500_t310 loadfdl 0x9efffe00_t310 exec
```

`--wait 300` 参数表示等待 300 秒以允许你在此期间将设备插入电脑。

---

## spd_dump 下载

| 平台 | 下载链接 |
|------|---------|
| **Windows** | [Prebuilt Program for Windows](https://nightly.link/TomKing062/action_spd_dump_it/workflows/build/main) |
| **Linux** | [Prebuilt Program for Linux](https://nightly.link/TomKing062/action_spd_dump_it/workflows/build-musl/main) |

## 参考资料

- [spd_dump 使用指南 - LinearTeam](https://www.linearteam.top/spd-dump-help/)
- [spd_dump 官方中文文档](https://github.com/TomKing062/spreadtrum_flash/blob/main/README_zh.md)
