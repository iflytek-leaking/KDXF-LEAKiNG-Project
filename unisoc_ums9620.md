<!-- SPDX-FileCopyrightText: 2024-2026 IFLYTEK-LEAKING -->
<!-- SPDX-FileCopyrightText: 2024-2026 KawaiiSparkle -->
<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->
<!-- 全体贡献者见 CONTRIBUTORS.md -->
# 紫光展锐 UMS9620 机型破解教程

## 适用机型

- T30Lite
- Lumie10Pro
- S30Turbo
- P30Turbo
- T90
- P90
- T90Lite
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
| **时间** | 1~2h，取决于备份速度。保持耐心，仔细阅读完教程再操作 |

> **【严肃提醒】** 官方有云控可以在检测到你开ADB后直接给你远程关了

---

## 第一步：安装紫光展锐驱动
获取工具箱 https://github.com/iflytek-leaking/Unisoc_Toolbox/releases/latest
然后使用管理员权限运行它，选择`[1] 安装驱动与运行环境`
---

## 第二步：使用工具箱进入FDL2模式，备份全量分区
还是第一步提到的工具箱，回到主菜单后选择`[8] 进入 FDL2 深刷读写模式（备份/刷机）`，选择`T760`那一项
然后按照提示进入FDL2模式，然后输入
```
FDL2> path 一个你找得到的路径                  #如D:\iflytek-backup，且要有至少30G存储空间
FDL2> r all
```
大概过一个多小时，这个就OK了。
## 第三步：使用CVE解锁BL、关掉dm-verify
解压`配套文件\展讯\ums9620_unlock.zip`，执行里面autopatch那个bat，过了一会后你会发现：卡开机了！
使用工具箱进入T760的FDL2模式，然后使用`r miscdata 你备份的目录/miscdata`来读取这个解锁后的miscdata文件并让它覆盖已有的那个miscdata（如果目录下的是.bin请使用miscdata.bin覆盖）
然后`write_parts 你备份所在目录`并等待它跑完即可
然后使用`dis_avb`和`verity 0`来干掉两个校验（你看它改了哪些分区就把这些分区提取出来替换原备份里面的，这样你后面救砖后一刷就不用再次跑这个了）
OK，前置步骤完成。
## 第四步：使用在线16进制编辑器打开你备份的init_boot_a分区，查看是否有数据，并依据此决定修补哪种分区
打开这个网站：https://rivers.chaitin.cn/tools/hexeditor
点`打开文件`，将你的init_boot_a分区（_b也行）选中，查看0x0到0x1000区间是否存在数据和一些字符串，有的话这个就算是「有效数据」，反之就是「无效数据」
如果是「有效数据」则修补此分区，不是的话就修补boot分区
不管修补哪个，为防止只有50%的概率启动到有Root权限的情况，请把你修补分区的另一个槽位也用这个被修补后的数据覆盖
自此，Root完成。
## 第五步：装模块破解
由于实在没有安卓9那样的官方签名的原生无限制安装器来替换，这里要解除安装器（来自Framework的限制）和MDM那一堆限制就需要对系统进行hook才可以
这个在IFLYTEK-LEAKING的QQ群里有已经做出来的实现：卷巨澜
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

| 命令 | 功能 | 示例 |
|------|------|------|
| `r [分区名]` | 读取/备份分区 | `r boot_a` |
| `w [分区名] [文件]` | 写入/刷入分区 | `w boot_a boot_patched.img` |
| `e [分区名]` | 擦除分区 | `e userdata` |
| `reset` | 重启进入系统 | `reset` |
| `poweroff` | 关机 | `poweroff` |
|`dis_avb`|通过漏洞禁用AVB|`dis_avb`|
| `verity [1\|0]` | 设置 AVB 校验开关（1=开启，0=关闭） | `verifly 0` |
| `print` | 打印分区表 | `print` |

更多命令详见 [SPD Dump 使用指南](https://www.linearteam.top/spd-dump-help/)。

---

## 参考资料

- [spd_dump 使用指南 - LinearTeam](https://www.linearteam.top/spd-dump-help/)
- [spd_dump 官方中文文档](https://github.com/TomKing062/spreadtrum_flash/blob/main/README_zh.md)
