@echo off
cd /d %~dp0
echo ========================================
echo   0-进入 Bootloader
echo ========================================
echo.
echo 请先确保驱动和运行库已安装（运行安装运行库和驱动.bat）。
echo.
echo 操作步骤：
echo   1. 将平板完全关机
echo   2. 按任意键执行spd_dump...
echo   3. 用 USB 线连接电脑（此时不要按任何平板上按键）
echo.
pause>nul
echo.
echo 请用 USB 线连接电脑（此时不要按任何平板上按键）
spd_dump --kickto 1 --wait 100
echo.
echo 如果出现【Successfully connected to port】，说明已进入 Kick 模式。
echo 按任意键继续...
pause
echo.
echo 正在扫描 ADB 设备...
adb devices
echo 如果看到 recovery 设备，按任意键继续...
pause
echo.
echo 正在重启到 Bootloader...
adb reboot bootloader
echo.
ping 127.0.0.1 -n 3 >nul
fastboot devices
echo.
echo 如果看到 fastboot 设备，说明已成功进入 Bootloader。
echo 请按数字顺序执行后续脚本。
pause