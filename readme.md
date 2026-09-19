<!-- SPDX-FileCopyrightText: 2024-2026 IFLYTEK-LEAKING -->
<!-- SPDX-FileCopyrightText: 2024-2026 KawaiiSparkle -->
<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->
<!-- 全体贡献者见 CONTRIBUTORS.md -->
# 科大讯飞AI学习机玩机教程合集

## 项目说明

本项目提供科大讯飞AI学习机各系列机型的玩机教程，目标是将学习机改造为普通安卓平板使用。所有教程和资源均为免费提供。

## 风险警告

| 级别 | 说明 |
|------|------|
| **刷机操作** | 所有刷机行为均会清空设备数据，操作前请务必备份。 |
| **保修失效** | 根据《科大讯飞AI学习机AI学习软件服务用户协议》，对学习机进行刷机行为（包括但不限于获取root权限、刷入第三方ROM）将使设备从官方技术支持和软件保修服务中移除。 |
| **变砖风险** | 操作不当可能导致设备无法开机。官方售后救砖费用约为60-100元。 |
| **责任声明** | 本教程编写团队对因操作不当导致的设备损坏、数据丢失不承担任何责任。 |

## 教程目录

根据你的设备处理器平台，选择对应的教程：

| 处理器平台 | 教程文件 | 适用机型 |
|-----------|---------|---------|
| 紫光展锐（无SPRD4/Android 9） | [Unisoc_ud710.md](./Unisoc_ud710.md) | Z1, X2, X2Pro, X3Pro, T10, T20, C6, C8, SA30(P30、Q30), SA30Pro(S30、S30D), TX20(C10、C10S、C10Pro、A10)、Lumie10, Q10 |
| 紫光展锐 UMS9620 | [unisoc_ums9620.md](./unisoc_ums9620.md) | T30Lite, Lumie10Pro, S30Turbo, P30Turbo, T90Lite, P90 |
| 瑞芯微系列 | [rockchip.md](./rockchip.md) | T20Pro, T30Pro, T30Ultra, T90Pro |
| 高通 骁龙系列 | [Qualcomm.md](./Qualcomm.md) | X1, X1Pro, P30-5G, X3-5G |

## 操作前准备（通用）

1. 一台 Windows 7 或更高版本的电脑
2. 一条可传输数据的 USB 数据线
3. 基本的电脑操作能力
4. 白天充足的时间（避免疲劳操作导致失误）
5. 确保设备电量充足（建议50%以上）

## 需要的文件资源

| 资源 | 位置 |
|------|------|
| （展讯）科大讯飞工具箱 | https://github.com/iflytek-leaking/Unisoc_Toolbox/releases |
| 高通 firehose 文件 | `files/firehoses/` 目录下对应机型子目录 |

## 版权与许可

本项目由[IFLYTEK-LEAKING](https://github.com/IFLYTEK-LEAKING)开发，主要作者为[KawaiiSparkle](https://github.com/KawaiiSparkle)，全体贡献者见[CONTRIBUTORS.md](./CONTRIBUTORS.md) 。

- `.py`、`.bat` 脚本、`.zip` 分发包、闭源二进制：PolyForm Noncommercial 1.0.0
- `.md` 教程文档：CC BY-NC-SA 4.0
- 禁止任何形式的商业性使用，包括但不限于倒卖、付费远程协助、打包售卖、付费社群传播等。

## 反馈与交流
如遇问题，请进入科大硬破解交流群（入群审核）：1027759100并私聊管理员负责处理。
当然开issue也是支持的。

## 捐赠
> 如果我们项目帮到了你，欢迎通过发送你用不完的api端点及api-key到qwq0d000721@proton.me这个团队公用邮箱，以提高我们找靶点和修教程的效率。
