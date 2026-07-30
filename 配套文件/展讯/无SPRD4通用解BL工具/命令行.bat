@ECHO OFF
cd /d %~dp0
TITLE [命令行] 紫光展锐解锁BL - 常用命令
:A
ECHO.
ECHO ========== 常用命令 ==========
ECHO 通用 fastboot:            fastboot
ECHO 展锐专用 fastboot:        fastboot_sprd
ECHO 获取 identifier_token:    fastboot_sprd oem get_identifier_token
ECHO 解锁 BL:                 fastboot_sprd flashing unlock_bootloader signature.bin
ECHO 重新上锁 BL:             fastboot_sprd flashing lock_bootloader
ECHO 查看 ADB 设备:            adb devices
ECHO 重启到 Fastboot:         adb reboot bootloader
ECHO FastbootD 返回 Fastboot:  fastboot reboot bootloader
ECHO =============================
ECHO.
cmd
ECHO.
ECHO 上一个会话已结束，返回菜单。
ECHO.
goto A