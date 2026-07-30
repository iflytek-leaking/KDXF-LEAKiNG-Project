# 瑞芯微 (Rockchip) 机型破解教程

## 适用机型

- T20 Pro
- T30 Pro
- T30 Ultra
- 后续使用瑞芯微 RK 芯片的科大讯飞学习机

## 原理说明

瑞芯微机型没有 BootLoader 锁和 AVB 2.0 验证，因此破解流程相对简单：
1. 获取设备当前运行的 boot 镜像
2. 使用 Magisk/Apatch 修补 boot 镜像
3. 通过 RKDevTool 刷入修补后的 boot 镜像
4. 安装模块以完全禁用 MDM（移动设备管理）

---

## 操作前准备

| 类别 | 要求 |
|------|------|
| **硬件** | Windows 电脑、USB 数据线 |
| **工具** | RKDevTool（瑞芯微刷机工具）、RK 驱动 |
| **镜像** | 目标设备的 boot 镜像 |
| **模块** | 群内提供的 MDM 禁用模块 |

---

## 第一步：获取 boot 镜像

有两种方式获取 boot 镜像：

### 方法一：通过 RKDevTool 读取分区（推荐）

1. 安装 RK 驱动和 RKDevTool
2. 学习机关机后连接电脑
3. 按住学习机的三个实体按键（电源 + 音量加 + 音量减），直到 RKDevTool 显示"发现一个 Loader 设备"
4. 在 RKDevTool 中读取分区表，找到 boot 分区的起始地址和大小
5. 导出 boot 分区镜像

### 方法二：通过全量包 + 差分包合成

如果无法直接读取存储芯片：

1. 找到设备的全量刷机包，提取其中的 `boot.img`
2. 找到设备更新路径上所有差分包的 `boot.img.p` 文件
3. 使用 [KawaiiSparkle/imgpatchtool](https://github.com/KawaiiSparkle/imgpatchtool) 中的 `ApplyPatch.py` 脚本，按更新顺序依次将差分包应用到全量包 boot.img，合成到设备当前运行版本

```bash
# 依次应用每个差分包
python ApplyPatch.py boot.img delta1.img.p boot_v2.img
python ApplyPatch.py boot_v2.img delta2.img.p boot_v3.img
# ... 重复直到最新版本
```

---

## 第二步：修补 boot 镜像

### Magisk 法

1. 将 boot 镜像传输到学习机或使用模拟器
2. 安装 Magisk 管理器
3. 在 Magisk 中选择"安装" → "选择并修补一个文件"
4. 选择 boot.img，等待修补完成
5. 从设备中导出修补后的镜像

### Apatch 法

参考 [APatch 安装指南](https://apatch.dev/zh_CN/install.html) 进行修补。

---

## 第三步：刷入修补后的 boot 镜像

1. 学习机**完全关机**
2. 连接电脑，打开 RKDevTool
3. 按住学习机三个按键（电源 + 音量加 + 音量减）进入 Loader 模式
4. RKDevTool 检测到设备后，切换到"下载镜像"选项卡
5. 勾选 boot 分区，选择修补后的 boot 镜像文件
6. 点击"执行"开始刷写
7. 等待刷写完成，设备将自动重启

---

## 第四步：安装 MDM 禁用模块

设备启动后：

1. 安装 Magisk 管理器（如未安装）
2. 将群内提供的 MDM 禁用模块传输到设备
3. 在 Magisk 管理器中进入「模块」→「从本地安装」
4. 选择 MDM 禁用模块并安装
5. 重启设备生效

安装此模块后，MDM（移动设备管理）将被完全禁用，设备恢复为普通安卓平板功能。

---

## 故障排查

| 问题 | 解决方法 |
|------|---------|
| 无法进入 Loader 模式 | 确认驱动安装正确，尝试先按住按键再插 USB 线 |
| 刷入后无法开机 | 使用备份的原始 boot 镜像恢复 |
| 修补后的 boot 无法启动 | 检查 boot 镜像版本是否与当前系统匹配 |

---

## 参考资料

- [APatch 安装指南](https://apatch.dev/zh_CN/install.html)
