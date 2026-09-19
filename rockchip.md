<!-- SPDX-FileCopyrightText: 2024-2026 IFLYTEK-LEAKING -->
<!-- SPDX-FileCopyrightText: 2024-2026 KawaiiSparkle -->
<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->
<!-- 全体贡献者见 CONTRIBUTORS.md -->
# 瑞芯微 (Rockchip) 机型破解教程

> 本教程面向**新手**，每一步都解释了「为什么要这么做」。
> 请**一步一步**照做，不要跳步。操作前先看完一整章再动手。

---

## 你的机器属于哪一类？

先搞清楚你的机器，后面的步骤完全不同，**别搞混了**：

| 芯片方案 | 存储方式 | 机型 |
|---------|---------|------|
| **RK3588** | NVMe + SPI NOR | T20Pro、T30Pro、T30Ultra、T90Pro |
| **RK3576S** | 单 eMMC | S90、S90Pro、Lumie90 |

> 怎么判断？由你机型直接对应即可

---

## 为什么要做这件事？（背景一句话）

瑞芯微的平板在「Loader 模式」下，**只能正确读取存储器的前 32MB**，超过的部分会被一堆无意义的 `0xCC` 垃圾数据填充。

这会导致你**无法完整备份**，也无法正确刷机。所以我们第一步要做的，就是**解除这个 32MB 读取限制**，之后才能正常备份和刷机。

---

## 需要准备的东西

| 类别 | 需要 | 说明 |
|------|------|------|
| 电脑 | Windows 电脑 | Win7 以上即可 |
| 数据线 | 一条能传数据的 USB 线 | 不是充电线！ |
| 工具 | Zadig | 用来给设备装驱动 |
| 工具 | rktools | 刷机命令行工具 |
| 模块 | 群内提供的 MDM 禁用模块 | 破解后去限制用的 |

---

## 第一阶段：装驱动和工具（只做一次）

### 1. 下载 Zadig

浏览器打开这个链接，下载并保存：

```
https://gh.ddlc.top/https://github.com/pbatard/libwdi/releases/download/v1.5.1/zadig-2.9.exe
```

### 2. 让平板进入 Loader 模式，并安装驱动

1. 平板**完全关机**
2. **按住「音量+」键不放**
3. 保持按住音量+，把 USB 线插到电脑上
4. 打开刚才下载的 **Zadig**
5. 菜单栏点 `Options` → `List All Devices`（勾选上）
6. 在下拉框里找到 **VID 为 `2207`** 的 `USB Download Gadget`
7. 右侧驱动选 **`libusb-win32`**
8. 点 **Install**，等到提示 `Successfully` 就装好了

> **为什么要装这个驱动？** 默认驱动会让电脑「不认」这块平板的刷机接口，libusb-win32 是刷机工具认识的驱动。

### 3. 安装 rktools

1. 下载并安装 Rust（一路默认即可）：<https://rustup.rs>
2. 打开 **PowerShell**，运行：
   ```powershell
   cargo install rkusb
   ```
   （这一步要等几分钟，让它自己装完）

3. 把下面这个路径加入系统 PATH（环境变量）：
   ```
   C:\Users\你的用户名\.cargo\bin
   ```
   （`你的用户名` 换成你 Windows 的实际用户名）

4. **验证安装**：重新打开一个 PowerShell，输入：
   ```powershell
   rktools ls
   ```
   如果屏幕显示 `Loader`，说明连接成功，工具装好了。

---

## 第二阶段：解除 32MB 读取限制

> ⚠️ **这一步是整个教程最关键、也最容易翻车的地方。**
> 请先看清楚你机器的芯片类型，再走对应的分支。**别走错了！**

### 🅐 RK3576S 机型（S90、S90Pro、Lumie90）

1. 确保平板处于 **Loader 模式**（关机 → 按住音量+ → 插 USB）
2. 在 PowerShell 里执行：
   ```powershell
   rktools lba read 0 0x10000 pre_32MB.bin
   ```
   - 这条命令把存储器的前 32MB 完整备份到文件 `pre_32MB.bin`
3. 得到一个备份文件 **`pre_32MB.bin`**，**先把它复制保存到别处（非常重要！）**

### 🅑 RK3588 机型（T20Pro、T30Pro、T30Ultra、T90Pro）

RK3588 更麻烦一点，需要先进 MaskROM 模式：

1. 进入 MaskROM 模式：
   ```powershell
   rktools rst 3
   ```
   > MaskROM 是芯片最底层的模式，相当于「出厂模式」，能绕过 Loader 的限制。

2. 加载一个临时 Loader 文件，让 MaskROM 恢复读写能力：
   ```powershell
   rktools db 配套文件/RK/rk3588_download.bin
   ```
   （`配套文件/RK/` 是本仓库里的文件夹，路径按实际情况改）

3. 查询存储器的总扇区数，**记下返回的数字 N**：
   ```powershell
   rktools st i
   ```

4. 把整块存储器备份出来：
   ```powershell
   rktools lba read 0 <N> MaskROM_extracted.bin
   ```
   （把 `<N>` 换成上一步记下的数字）
5. 得到备份文件 **`MaskROM_extracted.bin`**，**先复制保存到别处（非常重要！）**

---

### 修补备份文件（两类机型都要做）

不管你是上面的 🅐 还是 🅑，现在手里都有一个原始备份文件：
- RK3576S：`pre_32MB.bin`
- RK3588：`MaskROM_extracted.bin`

**接下来把它修补一下，解除 32MB 限制：**

1. 在 PowerShell 里运行：
   ```powershell
   python3 配套文件/RK/rkusb_nolimit.py 你的备份文件.bin
   ```
2. 脚本会在自动生成的 `out` 文件夹里输出**修补后的文件**

> **这个脚本做了什么？** 它把备份文件里那些碍事的 `0xCC` 垃圾数据替换成真正有用的内容，相当于「解锁」了完整读写能力。

---

### 把修补后的文件刷回去

1. 用 `rktools lba write` 把修补后的文件写回设备：
   ```powershell
   rktools lba write 0 <N> out/修补后的文件.bin
   ```
   - `N` 填多少？
     - RK3576S（32MB 备份）：填 `0x10000`
     - RK3588（MaskROM 备份）：填你刚才记下的扇区数 `N`

2. 重启平板，看能不能正常进系统：
   ```powershell
   rktools rst 0
   ```
3. **如果顺利开机进系统** → 恭喜！读取限制已成功解除，进入第三阶段。

---

### ⚠️ 如果变砖了怎么办？（救砖）

> **千万、千万、千万**留好你修补前的原始备份文件！

如果平板开不了机，你需要：
1. 拿去手机店，请人拆开屏幕
2. 在主板上找到丝印写着 **`MaskROM`** 的按钮或触点
3. **长按**或**短接**它，让平板进入 MaskROM 模式
4.4. 然后刷入**修补前的原始备份文件**（不是修补后的那个）：
   ```powershell
   rktools lba write 0 <N> 你保存的原始备份.bin
   ```
5. 重启，应该能恢复正常了。

---

## 第三阶段：备份并破解系统

读取限制解除了，现在就能正常备份分区、刷入 Magisk 了。

### 1. 重新进入 Loader 模式

- 平板关机 → 按住「音量+」→ 插 USB

### 2. 查看分区表

```powershell
rktools st partition table > part_table.txt
```

这会生成一个 `part_table.txt` 文件，里面列了所有分区的名字和大小。**打开它看一眼**，方便你后面找分区名。

### 3. 备份指定分区

格式：

```powershell
rktools st partition read --name <分区名> <保存的绝对路径>
```

例如：

```powershell
rktools st partition read --name boot C:\backup\boot.img
```

> **写回（刷入）** 时，把 `read` 换成 `write` 即可。

### 4. 备份哪个分区？（关键判断）
| 机型 | 备份哪个分区 | 怎么处理 |
|------|------------|---------|
| **T90Pro前的RK3588机型** | `boot` | 备份后交给 Magisk 修补 |
| **RK3576S / RK3588的T90Pro** | `init_boot_a` | 先打开分区表确认 |
> **怎么确定到底备份哪个？** 打开刚才的 `part_table.txt`，看里面有没有 `init_boot` 或 `vendor_boot` 分区：
> - 有 `init_boot` → 备份 `init_boot`
> - 有 `vendor_boot` → 备份 `vendor_boot`（新机制）
> - 只有 `boot` → 备份 `boot`（老机制）
### 5. 用 Magisk 修补备份的分区
1. 把备份出来的 `.img` 文件**传到平板里**
2. 第二台设备安装 **Magisk** App
3. 打开 Magisk → 点「安装」→ 选「选择并修补一个文件」
4. 选中刚才传进来的 `.img` 文件
5. 点「开始」，Magisk 会在**同目录**生成一个 `magisk_patched-xxxxx.img` 修补文件
6. 把这个修补文件**拷回电脑**

> **Magisk 修补了什么？** 它往 boot 镜像里注入了 root 权限（supersu 的原理），这样系统启动时就会拿到 root。

### 6. 把修补文件刷回平板

把 Magisk 修补好的文件写回对应的分区（`write`）：

```powershell
rktools st partition write --name <分区名> magisk_patched-xxxxx.img
```

> 分区名要和你备份时用的**一模一样**。写回后重启，平板上就会出现「Magisk」图标，说明 root 成功了。

---

## 第四阶段：清除来自于MDM/Framework的限制

Root 拿到手，最后一步就是把系统里的软件安装、使用限制 给干掉，彻底「解锁」。

1. 群里获取 **卷巨澜模块**（Magisk 模块包，`.zip` 格式）
2. 把模块传到平板
3. 打开 **Magisk** → 底部菜单「模块」→「从本地安装」
4. 选中模块 `.zip` → 安装 → 重启
5. 重启后 软件安装、使用限制应该被移除，Have Fun！
