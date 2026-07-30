# 科大讯飞AI学习机破解教程合集

## 项目说明

本项目提供科大讯飞AI学习机各系列机型的破解教程，目标是将学习机改造为普通安卓平板使用。所有教程和资源均为免费提供。

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
| 紫光展锐 UMS9620 | [unisoc_ums9620.md](./unisoc_ums9620.md) | T30Lite, Lumie10Pro, S30Turbo, P30Turbo, T90Lite |
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
| 紫光展锐驱动 | `配套文件/展讯/紫光驱动_R4.21.3201.zip` |
| FDL 文件 | `配套文件/展讯/fdls/` 目录下对应芯片子目录 |
| BL 解锁脚本（无SPRD4方案） | `配套文件/展讯/无SPRD4通用/`（含驱动、运行库、一键解锁） |
| 高通 firehose 文件 | `files/firehoses/` 目录下对应机型子目录 |

## 贡献者

- [@KawaiiSparkle](https://github.com/KawaiiSparkle) / [@qwqlemon2333](https://github.com/qwqlemon2333) / [@WalleoAndrew](https://github.com/WalleoAndrew) — 伪造apk更新包教程 + Root教程
- [@Tomking062](https://github.com/TomKing062) — system-root 方案、spd_dump 改进版本、resign工作流
- [@YedLeo1](https://github.com/YedLeo1) — T20 Pro 机型破解，现已退坑
- [@KawaiiSparkle](https://github.com/KawaiiSparkle) / [@LYao2514](https://github.com/LYao2514) — 一键自动patch系统分区脚本，不过现在用不着WSL了，直接在Windows上拿MIO-KITCHEN灌入文件后通过改配置文件来等效chmod/chown
- [@ig25138](https://github.com/ig25138) — T30 Pro 机型破解
- [@misaka_pardola](https://github.com/misaka-pardola) — 技术支持
- [酷安@某贼](http://www.coolapk.com/u/3463951) — 文件转存萤火虫资源站

## 反馈与交流

如遇问题，请进入科大硬破解交流群（入群审核）：1027759100并私聊管理员负责处理。

## 捐赠
> 如果我们项目帮到了你，欢迎通过发送你用不完的Kimi-V3/MiMO/Deepseek-v4/GLM-5.2的api端点及api-key到qwq0d000721@proton.me这个团队公用邮箱，以提高我们找靶点和修教程的效率。
