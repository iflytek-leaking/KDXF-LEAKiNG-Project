@ECHO OFF
cd /d %~dp0
TITLE [3-解锁BL] 紫光展锐解锁BL
ECHO.
ECHO 适用于紫光展锐 SpreadTrum 全系列，使用公钥签名解锁设备。
ECHO.
:A
if not exist ..\signature.bin (
    ECHO.
    ECHO 找不到 signature.bin！
    ECHO 请将 signature.bin 文件放到上级目录。
    ECHO.
    pause>nul & goto A
)
ECHO 请将设备处于 Fastboot 模式，然后按任意键继续...
pause>nul
ECHO.
ECHO 正在解锁 BL，请按设备屏幕提示操作（选择 YES 并确认）...
fastboot_sprd.exe oem get_identifier_token
fastboot_sprd.exe flashing unlock_bootloader ..\signature.bin
ECHO.
ECHO 完成。设备将自动恢复出厂并重启。
pause>nul & EXIT