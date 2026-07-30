@echo off
cd /d %~dp0
echo ========================================
echo   一键进入 FDL2 读写模式 (chip2)
echo ========================================
echo.
echo 请确保已在当前目录放置以下文件：
echo   - c2_0x5500
echo   - c2_0x9efffe00
echo   - spd_dump.exe
echo   - Channel9.dll
echo.
echo 操作步骤：
echo   1. 将平板完全关机
echo   2. 用 USB 线连接电脑
echo   3. 按任意键开始推送 FDL...
echo.
pause>nul
echo.
echo 正在推送 FDL1 和 FDL2，等待设备连接（最多 600 秒）...
spd_dump --wait 600 loadfdl c2_0x5500 loadfdl c2_0x9efffe00 exec
echo.
echo 如果终端显示 FDL2^> 提示符，说明已成功进入读写模式。
echo 如果推送失败，可尝试改用 chip0/chip1 的 FDL 文件重试。
pause