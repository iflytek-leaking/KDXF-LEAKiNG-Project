# 高通 (Qualcomm) 机型破解教程

## 适用机型

| 机型 | 芯片 | Android 版本 | Firehose 文件位置 |
|------|------|-------------|-------------------|
| X1Pro (TYE100) | 骁龙 625 | Android 8.1 | `files/firehoses/x1pro/` |
| P30 5G | 骁龙 750G | — | `files/firehoses/` |
| X3 5G | 骁龙 750G | — | `files/firehoses/` |

> **注意**：课堂版机型因不可抗力因素无法提供完整支持。

---

## 操作前准备

| 类别 | 要求 |
|------|------|
| **硬件** | Windows 电脑、USB 数据线 |
| **驱动** | 9008 驱动（原链接已失效，请自行搜索 "Qualcomm HS-USB QDLoader 9008 driver" 下载） |
| **工具** | [高通工具箱](https://syxz.lanzoue.com/b01g1c7ve)（密码：`bulf`） |
| **文件** | 对应机型的 firehose 文件（位于 `files/firehoses/` 目录） |

---

## P30 5G / X3 5G 机型教程

### 第一步：解锁 BootLoader

#### 1.1 安装 9008 驱动

从上述链接下载并安装 9008 驱动。

#### 1.2 进入 9008 深度刷机模式

1. 将设备**完全关机**
2. 按住**音量上键**
3. 保持按住音量上键，将 USB 数据线插入电脑
4. 设备即进入 9008 模式

#### 1.3 使用高通工具箱刷写解锁分区

1. 打开高通工具箱
2. 加载对应机型的 firehose 文件
3. 读取 boot 相关分区和 vbmeta 分区（建议先备份）
4. 刷写解锁文件：
   - 将 `unlock_bl` 目录下的 `frp.img` 刷入 `frp` 分区
   - 将 `unlock_bl` 目录下的 `misc.img` 刷入 `misc` 分区
5. 重启设备

#### 1.4 执行 BootLoader 解锁

1. 重启后设备将默认进入 fastbootd 模式
2. 使用 ADB 工具或工具箱将设备重启到 bootloader 模式：

```bash
fastboot reboot bootloader
```

3. 执行解锁命令：

```bash
fastboot flashing unlock
```

4. 设备屏幕将显示解锁确认界面（英文），使用音量键选择，电源键确认
5. 解锁过程会清空设备所有数据

---

### 第二步：刷入 Recovery

解锁 BL 后，需要刷入第三方 Recovery 来安装 Magisk。

1. 从 [OFRP Releases](https://github.com/OrangeFoxRecovery/OrangeFox Recovery) 或相关链接下载 OFRP（OrangeFox Recovery，TWRP 的美化分支）镜像包
2. 在 bootloader 模式下临时启动 OFRP：

```bash
fastboot boot ofrp.img
```

3. 在 OFRP 中刷入 OFRP 安装包以永久安装到 Recovery 分区

---

### 第三步：获取 Root

1. 下载最新版 [Magisk](https://github.com/topjohnwu/Magisk/releases) 安装包
2. 将 Magisk 安装包通过 U 盘或其他方式传输到设备
3. 重启到 OFRP（按住音量上 + 电源键启动）
4. 在 OFRP 中使用"安装"功能刷入 Magisk 安装包（.zip 格式）
5. 重启设备，Magisk 将自动修补 boot 镜像

---

### 第四步（可选）：刷回联想官方系统

如果需要恢复为联想官方原版系统：

1. 前往 [联想固件站](https://mirrors-obs-1.lolinet.com/firmware/lenowow/2021/Tab_P11_5G/TB-J607Z/) 下载对应 9008 刷机包
2. 使用高通工具箱**先备份全机所有分区**（除 `cache` 和 `userdata` 外）
3. 将 9008 包中的所有分区镜像逐一刷入对应分区
4. 重启设备

> **【故障恢复】** 如果刷回官方系统后无法开机，使用之前备份的分区镜像恢复。

---

## X1Pro (TYE100) 机型教程

X1Pro 使用骁龙 625 芯片，Firehose 文件位于 `files/firehoses/x1pro/` 目录。

基本流程与 P30 5G / X3 5G 相同：
1. 安装 9008 驱动
2. 进入 9008 模式
3. 使用高通工具箱加载对应 firehose 文件
4. 刷写解锁分区
5. 执行 `fastboot flashing unlock`
6. 刷入 Recovery 并安装 Magisk

> **注意**：如遇具体操作问题，请在本仓库提交 Issue。

---

## 常用 fastboot 命令速查

| 命令 | 功能 |
|------|------|
| `fastboot devices` | 检查设备是否连接 |
| `fastboot reboot bootloader` | 重启到 bootloader 模式 |
| `fastboot flashing unlock` | 解锁 BootLoader |
| `fastboot boot [镜像.img]` | 临时启动指定镜像 |
| `fastboot flash recovery [镜像.img]` | 刷入 Recovery |
| `fastboot reboot` | 重启设备 |

---

## 参考资料

- [高通工具箱](https://syxz.lanzoue.com/b01g1c7ve)（密码：`bulf`）
- [联想固件下载](https://mirrors-obs-1.lolinet.com/firmware/lenowow/2021/Tab_P11_5G/TB-J607Z/)
- [Magisk 官方](https://github.com/topjohnwu/Magisk/releases)
