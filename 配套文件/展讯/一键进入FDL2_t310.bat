@echo off
cd /d %~dp0
echo ========================================
echo   一键进入 FDL2 读写模式 (T310/ums312)
echo ========================================
echo.
echo 请确保已在当前目录放置以下文件：
echo   - 0x5500_t310
echo   - 0x9efffe00_t310
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
spd_dump --wait 600 loadfdl 0x5500_t310 loadfdl 0x9efffe00_t310 exec
echo.
echo 如果终端显示 FDL2^> 提示符，说明已成功进入读写模式。
echo 如果推送失败，请尝试更换 USB 端口或数据线后重试。
pause