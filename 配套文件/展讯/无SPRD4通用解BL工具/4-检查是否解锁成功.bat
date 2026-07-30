@ECHO OFF
cd /d %~dp0
TITLE [4-检查是否解锁成功] 紫光展锐解锁BL
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
ECHO 正在检查解锁状态...
fastboot_sprd.exe oem get_identifier_token
fastboot_sprd.exe flashing unlock_bootloader ..\signature.bin
ECHO.
ECHO 如果显示 "Bootloader can not been unlocked repeatly"，说明解锁成功。
ECHO 如果显示其他错误信息，说明解锁失败，请重新尝试。
ECHO 注意：首次解锁时设备屏幕会有确认提示，请按提示操作。
ECHO.
pause>nul & EXIT
:: 重新上锁
:: fastboot flashing lock_bootloader