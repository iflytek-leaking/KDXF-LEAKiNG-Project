# 紫光展锐 UMS9620 机型破解教程

## 适用机型

- T30 Lite
- Lumie10 Pro
- S30 Turbo
- P30 Turbo
- T90 Lite
- 其他使用 UMS9620 (T760) 芯片的科大讯飞学习机

## 原理说明

UMS9620 机型在 Android 系统上启用了完整的 AVB（Android Verified Boot）校验。虽然 spd_dump 提供了 AVB 开关，但解锁 BootLoader 后 AVB 并不会自动关闭。因此本方案的核心步骤是：

1. 解锁 BootLoader
2. 手动关闭 AVB 校验
3. 刷入修补后的 boot 镜像获取 Root
4. 安装模块以解除设备限制

> **【重要警告】** 本教程操作会清空设备所有数据，请务必提前备份重要文件。

---

## 操作前准备

| 类别 | 要求 |
|------|------|
| **硬件** | Windows 7 或更高版本的电脑、USB Type-C to A 数据线 |
| **软件** | 本仓库配套文件包 |
| **辅助设备** | 一台可自由安装应用的安卓手机（用于解除 Magisk 时间限制） |
| **时间** | 建议在白天进行，保持耐心，仔细阅读完教程再操作 |

> **【严肃提醒】** 由于新云控系统限制，开发者选项已被禁用，无法通过常规方式开启 ADB。本教程通过深刷模式绕过此限制。

---

## 第一步：安装紫光展锐驱动

1. 解压文件包，进入 `driver` 文件夹
2. 双击运行驱动安装程序：
   - 64 位系统：双击 `64install.exe`
   - 32 位系统：双击 `32install.exe`（如果 64 位版本无法运行）
3. 按照安装向导提示完成驱动安装

---

## 第二步：解锁 BootLoader

本步骤利用 CVE-2022-38694 漏洞解锁 BootLoader，无需进入开发者选项。

### 操作步骤

1. 将学习机**完全关机**
2. 使用 USB 数据线将学习机连接到电脑
3. 等待屏幕上的充电动画**完全消失**
4. 在电脑上打开文件包中的 `unlock_autopatch_9620.bat`（Linux 用户运行对应的 `.sh` 脚本）
5. **同时按住**学习机的**电源键 + 音量上键 + 音量下键**
6. 观察电脑上脚本开始输出日志，直到学习机屏幕提示"清除数据"
7. 此时 BootLoader 已解锁

### 预期结果

解锁成功后再开机，屏幕底部会显示两行提示：

```
info:lock flag is unlock!!!
warning: lock flag is unlock, skip verify!!!
```

此提示属于正常现象，按两次电源键或等待几秒即可正常开机。

---

## 第三步：关闭 AVB 校验

AVB 校验不关闭将无法刷入修改后的 boot 镜像。

### 操作步骤

1. 将学习机**完全关机**，等待充电动画消失
2. 在电脑上打开 spd_dump 所在目录，打开终端：
   - Windows 11：在文件夹空白处右键 → "在终端中打开"
   - Windows 10/8/7：在地址栏输入 `cmd` 后回车
   - Linux：在目录中打开终端
3. 在终端中输入 `spd_dump`（按 Tab 键自动补全文件名）
4. 同时按住学习机的**电源键 + 音量上键 + 音量下键**
5. 观察终端窗口，等待出现 `BROM>` 提示符后松开按键
6. 依次输入以下命令：

```
fdl fdl1-dl.bin 0x65000800
```

等待提示符变为 `FDL1>`，然后输入：

```
fdl fdl2-dl.bin 0xb4fffe00
```

再输入：

```
exec
```

等待分区表输出完成，提示符变为 `FDL2>`，最后输入：

```
verifly 0
```

7. 工具将自动读取并修改 vbmeta 分区，关闭 AVB 校验
8. 等待提示符 `FDL2>` 重新出现，表示 AVB 已关闭

> **【关键提醒】** 不要关闭此终端窗口！否则需要重新进入 FDL2 模式。

### 完整命令流程参考

```
BROM> fdl fdl1-dl.bin 0x65000800
FDL1> fdl fdl2-dl.bin 0xb4fffe00
FDL1> exec
FDL2> verifly 0
```

---

## 第四步：刷写修补后的 boot 镜像

### 4.1 备份原版 boot 分区

在同一个终端窗口中输入：

```
r boot_a
```

备份文件将保存为 `boot_a.bin`，位于当前目录下。

将 `boot_a.bin` 重命名为 `boot_a.img` 妥善保存。如果后续出现问题，可以使用此文件恢复。

### 4.2 刷入修补后的 boot

文件包中应包含一个已修补好的 boot 镜像（基于系统版本 1.01.8）。执行以下命令：

```
w boot_a boot_patched.img
```

等待进度条完成，提示 `Write Part Done` 表示刷写成功。

### 4.3 重启设备

```
reset
```

学习机应正常开机。

> **【故障排除】** 如果设备无法开机，请参考下方的"救砖"章节，或联系管理员协助。

### 完整命令流程参考

```
FDL2> r boot_a
FDL2> w boot_a boot_patched.img
FDL2> reset
```

---

## 第五步：安装 Magisk 及模块

### 5.1 安装 Magisk 管理器

学习机桌面上的 Alpha 版本可能无法正常联网运行。推荐以下安装方法：

1. 将文件包中的 `alpha.apk` 复制到学习机存储中
2. 在学习机开机状态下连接电脑，在家长端解除 USB 限制
3. 通知栏选择"传输文件"模式
4. 在学习机「设置」→「文档」中，选择用文件管理器打开
5. 左侧会出现设备名称，点击进入后找到 `alpha.apk`
6. 直接安装

### 5.2 补全 Magisk 运行环境

打开已安装的 Magisk Alpha，按照提示补全运行环境。

### 5.3 安装解锁模块

1. 将文件包中的模块文件复制到学习机（方法与安装 APK 相同）
2. 在 Magisk Alpha 中进入「模块」页面
3. 选择「从本地安装」
4. 搜索 `a13_a12` 找到模块文件并安装
5. 安装完成后重启学习机

### 5.4 配置默认安装器

打开「爱玩机工具箱」，将其锁定为默认安装器。之后即可正常安装 APK 应用。

---

## 常用 spd_dump 命令速查

| 命令 | 功能 | 示例 |
|------|------|------|
| `r [分区名]` | 读取/备份分区 | `r boot_a` |
| `w [分区名] [文件]` | 写入/刷入分区 | `w boot_a boot_patched.img` |
| `e [分区名]` | 擦除分区 | `e userdata` |
| `reset` | 重启进入系统 | `reset` |
| `poweroff` | 关机 | `poweroff` |
| `verifly [1\|0]` | 设置 AVB 校验开关（1=开启，0=关闭） | `verifly 0` |
| `print` | 打印分区表 | `print` |

更多命令详见 [SPD Dump 使用指南](https://www.linearteam.top/spd-dump-help/)。

---

## 参考资料

- [spd_dump 使用指南 - LinearTeam](https://www.linearteam.top/spd-dump-help/)
- [spd_dump 官方中文文档](https://github.com/TomKing062/spreadtrum_flash/blob/main/README_zh.md)
