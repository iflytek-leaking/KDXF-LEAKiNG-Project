# 紫光展锐 UD710 机型深刷破解教程

## 适用机型

| 芯片版本 | 机型 | 深刷模式说明 |
|---------|------|-------------|
| chip0/chip1-ud710 | Z1, X2, X2Pro, X3Pro, T10, T20 | SPRD4 被阉割，走SPRD3 |
| chip2-ud710 | SA30Pro(S30/S30D), SA30(P30/Q30), TX20(C10全系/A10) | SPRD4 被阉割，走SPRD3 |
| 其他 | C6, C8, Q1（课堂版，因不可抗力因素无法提供完整支持） | SPRD4 被阉割，走SPRD3 |
| T310/ums312 | Q10 | **FDL 文件不同**，其余操作可套用本教程 |

> C6 刷入V99后如果图省事可直接输入开发者密码：`IFlyCBaistudy5121`

## 原理说明

此方案通过 spd_dump 深刷工具将学习机的 `system` 分区替换为已破解的无限制版系统，从而删除学习功能并允许自由安装应用。理论上所有使用 UD710 芯片的机型可通刷。

> **【说明】** UD710 芯片对应的系统版本固定为 **Android 9**。本文档适用于所有科大讯飞 UD710 机型，以及 **T310/ums312**（如 Q10）。T310 用户操作流程与本教程完全一致，仅 FDL 文件不同——需从 `配套文件/展讯/fdls/ums312/` 获取。
>
> **【Ud710 特别说明】** 科大讯飞所有 UD710 机型（chip0/chip1/chip2）的 SPRD4 深刷模式均被厂商阉割，无法通过标准的 开机 => kick to 1 / 2 => SPRD4 流程操作。但因此可以利用 spd_dump 的 `--kickto 1` 参数进入一个特殊的 Recovery 模式（屏幕黑屏但 ADB 开启，Aka. Cali-Mode），以此作为跳板进入 Bootloader 模式进行解锁。

---

## 第一步：准备工作

1. 将本仓库克隆或下载到本地
3. 将该目录整体复制到一个**路径不含中文和空格**的位置（例如 `D:\`）

---

## 第二步：解锁 BootLoader

`配套文件/展讯/无SPRD4通用解BL工具/` 目录已包含Windows 7及更高的系统上运行所需的全套自动化脚本。

1. **右键**以管理员身份运行 **`安装运行库和驱动.bat`**（自动安装 VC++ 运行库 + 紫光展锐驱动）
2. 按编号顺序依次双击运行 **`0-` 到 `4-`** 开头的 bat 脚本：
   - `0-关机方法进入bootloader.bat` => 进入 Kick 模式 => Fastboot
   - `1-获取identifier_token.bat` => 获取解锁令牌
   - `2-生成signature.bat` => 生成签名文件
   - `3-解锁BL.bat` => 执行解锁（设备上按音量键选 YES，电源键确认）
   - `4-检查是否解锁成功.bat` => 验证解锁结果
3. 每个脚本执行完毕后按提示操作即可，脚本内部有详细的中文指引

> **【提示】** 如果 `2-生成signature.bat` 提示缺少 DLL，说明 VC++ 运行库未安装，重新以管理员身份运行 `安装运行库和驱动.bat` 即可。

解锁成功后开机，屏幕底部会显示：
```
info:lock flag is unlock!!!
warning: lock flag is unlock, skip verify!!!
```
按两次电源键或等待几秒即可正常开机。解锁会触发恢复出厂设置，请耐心等待。

---

## 第三步：下载最新 spd_dump 并准备 FDL

虽然 `配套文件/展讯/无SPRD4通用解BL工具/` 中已内置了一个 spd_dump 版本，但上游可能已有体验优化（如大分区读取速度更快）。**建议下载最新版**，当然如果你不在乎也可以直接用内置的。

### 3.1 下载 spd_dump

1. 打开 [spd_dump 仓库](https://github.com/TomKing062/action_spd_dump_it)
2. 根据你的操作系统下载对应版本：
   - **Windows**：[Prebuilt Program for Windows](https://nightly.link/TomKing062/action_spd_dump_it/workflows/build/main)
   - **Linux**：[Prebuilt Program for Linux](https://nightly.link/TomKing062/action_spd_dump_it/workflows/build-musl/main)
3. 将下载的压缩包解压到一个**不含中文和空格**的目录（例如 `D:\SPRD_NEW`）

### 3.2 复制 FDL 文件和运行库

根据你的芯片版本，将对应文件复制到 spd_dump 解压目录（即 `D:\SPRD_NEW`）：

| 芯片版本 | 需复制的文件 | 来源目录 |
|---------|-------------|---------|
| chip0 / chip1（UD710） | `0x5500_ud710` + `0x9efffe00_ud710` | `配套文件/展讯/fdls/ud710/` |
| chip2（UD710） | `c2_0x5500` + `c2_0x9efffe00` | `配套文件/展讯/fdls/ud710/` |
| T310 / ums312 | `0x5500_t310` + `0x9efffe00_t310` | `配套文件/展讯/fdls/ums312/` |

### 3.3 复制一键 FDL2 初始化脚本

根据你的芯片版本，将 `配套文件/展讯/` 中对应的脚本复制到 spd_dump 解压目录：

| 芯片版本 | 脚本文件 |
|---------|---------|
| chip0 / chip1 | `一键进入FDL2_c0c1.bat` |
| chip2 | `一键进入FDL2_c2.bat` |
| T310 / ums312 | `一键进入FDL2_t310.bat` |

> **【重要警告】** 不同芯片使用的 FDL 文件完全不同，切勿混用！使用错误的 FDL 文件不会变砖（重新进入 u2s 即可恢复），但使用错误的 FDL 地址刷入文件可能导致芯片永久损坏！

---

## 第四步：进入 FDL2 读写模式

1. 将学习机**完全关机**
2. 双击运行 spd_dump 解压目录中的 `一键进入FDL2_xxx.bat`
3. 脚本开始等待后，将设备按住全部音量和电源键然后通过USB数据线连接电脑
4. 终端显示 `FDL2>` 提示符后，表示已成功进入 FDL2 读写模式

> **【故障排除】** 如果 FDL2 中命令运行时报 `usb send failed`，尝试更换数据线，或者将其插在机箱后侧供电足的USB口，然后重新运行脚本。

---

## 第五步：备份全部分区（必须执行）

在刷入任何内容之前，**必须先完整备份**，这是后续救砖的唯一保障。

在 `FDL2>` 终端中依次执行：

```
path D:\backup\kdxf（换成你自己的备份目录）
r all
```

- `path` 指定备份文件存放目录（请使用绝对路径，不含中文和空格）
- `r all` 备份除 `userdata` `cache` 外的所有分区，自动生成分区表 XML 文件

备份完成后，**将整个备份目录打包为 zip 压缩包**妥善保存。

---

## 第六步：获取 Root 权限（Magisk Boot 法）

### 6.1 提取分区镜像

在 `FDL2>` 终端中执行：

```
r boot
r recovery
```

将提取出的所有 `.bin` 文件（新版本默认无后缀名，可以试一下能不能直接用，如果不行就添加一个.bin后缀）打包为一个 zip 压缩包。

### 6.2 在线修补并签名

1. 将压缩包上传到 GitHub 仓库并获取直链
2. Fork [签名仓库](https://github.com/TomKing062/action_big_resign_with_magisk) 并启用 Actions
3. 在 Actions 中选择 `resign_v3` 工作流，输入压缩包直链
4. 运行后在 Releases 中下载 `resign.zip`
5. 解压获取修补好的 `boot.img`

### 6.3 刷入修补后的 boot

在 `FDL2>` 终端中执行：

```
w boot D:\SPRD_NEW\boot.img（替换为你Boot修补后文件的绝对路径）
reset
```

设备重启后，Magisk 即已安装。打开 Magisk App 确认 Root 状态。

---

## 第七步：选择最终方案

Root 完成后，根据你的需求选择以下一种方案。
**但不管如何选择：都不能继续接受后续的系统更新了，因为肯定会砖**
---

### 方案 A：不需要学习功能（制作无限制平板）

此方案将彻底移除学习功能，得到一个可自由安装应用的普通 Android 平板。

#### 工具准备

下载 [MIO-KITCHEN](https://github.com/ColdWindScholar/MIO-KITCHEN) 或你熟悉的 system 镜像解包工具。

#### 精简 system 分区

1. 使用 MIO-KITCHEN 解包 system 镜像
2. 删除以下目录/文件：
   - `/system/priv-app/` 中所有 `Hardware` 开头的应用
   - `/system/priv-app/` 中所有 `Tye` 和 `IFly` 开头的应用（**保留** `Hwc`、`Iflytek Server`、`Iflytek Service`）
   - `/system/app/` 中所有 `Tye` 和 `IFly` 开头的应用（**保留** `IFlyIMESigned`）
3. 添加第三方启动器和浏览器（推荐 **微软桌面 + Via** 组合，均在 Android 9 验证可用）：
   - 新建一个文件夹，名称随意（英文），例如 `MyLauncher`
   - 将启动器 apk 放入该文件夹，**apk 文件名与文件夹名一致**：`MyLauncher/MyLauncher.apk`
   - 浏览器同理，创建 `MyBrowser/MyBrowser.apk`
   - 将这两个文件夹放入 `/system/app/` 或 `/system/priv-app/`
4. 重新打包 system 镜像，EXT4设置-打包方式【mke2fs+e2fsdroid】,大小处理【自动读取】，打包格式【raw】，点打包

#### 刷入新 system

在 `FDL2>` 终端中：

```
w system D:\SPRD_NEW\system_new.img
e userdata
reset
```

设备重启后即得到一个与普通平板无异的无限制系统。

---

### 方案 B：保留学习功能

Root 后，前往 iflytek-leaking QQ审核群（1027759100）并按照要求给予审核材料并在5分钟以内解答管理员提出的问题，成功后会被拉入正式群，你可通过群文件获取内部公开的公益破解模块，即可在保留学习功能的同时解除应用安装限制以及实现一些高级功能。

#### 前置依赖

破解模块需要以下框架支持，请先安装：

- **Zygisk-Next**（Magisk 模块，[下载地址](https://github.com/Dr-TSNG/ZygiskNext/releases/latest)）
- **LSPosed/Vector**（[下载地址](https://github.com/JingMatrix/Vector/releases/latest)）

#### 警告

> **【严正声明】** 本模块为内部公益项目，仅供授权用户使用。如检测到未经授权的分发行为，我们将：
> - 公开泄露者的所有信息
> - 与所有合作科大群联动，将泄露者的信息列入黑名单
> - 在其他圈子传播其恶劣行径
>
> 请尊重开发者的劳动成果。

---

## 常用 spd_dump 命令速查

| 命令 | 简写 | 功能 |
|------|------|------|
| `r [分区名]` | — | 读取（备份）指定分区 |
| `w [分区名] [文件路径]` | — | 写入（刷入）指定分区 |
| `e [分区名]` | — | 擦除指定分区 |
| `r all` | — | 备份除 userdata 外的全部分区 |
| `path [目录]` | — | 指定备份/读取文件的存放目录 |
| `reset` | — | 重启进入安卓系统 |
| `print` | `p` | 重新打印分区表 |

更多命令详见 [spd_dump 使用指南](https://www.linearteam.top/spd-dump-help/)。

---

## 参考资料

- [spd_dump 官方中文文档](https://github.com/TomKing062/spreadtrum_flash/blob/main/README_zh.md)
- [SPD Dump 使用指南 – LinearTeam](https://www.linearteam.top/spd-dump-help/)
- [MIO-KITCHEN](https://github.com/ColdWindScholar/MIO-KITCHEN)
- [科大讯飞展讯机型救砖用基础镜像备份](https://github.com/KawaiiSparkle/KDXF_IMP_IMAGES)

## 捐赠
> 如果我们项目帮到了你，欢迎通过发送你用不完的Kimi-V3/MiMO/Deepseek-v4/GLM-5.2的api端点及api-key到qwq0d000721@proton.me这个团队公用邮箱，以提高我们找靶点和修教程的效率。
