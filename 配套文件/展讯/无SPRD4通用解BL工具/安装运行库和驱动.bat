@ECHO OFF
cd /d %~dp0
TITLE 安装运行库和驱动 - 紫光展锐 UD710
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo 【警告】需要管理员权限！
    echo 请右键选择「以管理员身份运行」本脚本。
    echo.
    pause
    exit /b
)
echo.
echo ================================
echo   第一步：安装 VC++ 运行库
echo ================================
echo.
if exist "运行库\VisualCppRedist_AIO_x86_x64.exe" (
    echo 正在静默安装所有 VC++ 版本...
    "运行库\VisualCppRedist_AIO_x86_x64.exe" /y /aiV
    echo 运行库安装完成。
) else if exist "运行库\vc_redist.x64.exe" (
    echo 正在安装 VC++ 运行库...
    "运行库\vc_redist.x64.exe" /install /quiet /norestart
    echo 运行库安装完成。
) else (
    echo 未找到 VC++ 运行库安装包，跳过此步骤。
    echo 如果后面 openssl 报错，请手动安装运行库。
)
echo.
echo ================================
echo   第二步：安装设备驱动
echo ================================
echo.
set OS_DIR=Win10
ver | find "6.1" >nul && set OS_DIR=Win7
ver | find "6.2" >nul && set OS_DIR=Win8
ver | find "6.3" >nul && set OS_DIR=Win8
echo 系统版本：%OS_DIR%
echo 导入 USB 配置...
regedit /s Drivers\%OS_DIR%\config.reg
echo 安装 %OS_DIR% 驱动...
if exist "Drivers\%OS_DIR%\DriverSetup.exe" (
    Drivers\%OS_DIR%\DriverSetup.exe
) else (
    echo 驱动安装程序不存在，请手动运行 Drivers\%OS_DIR%\DriverSetup.exe
)
echo.
echo ================================
echo   全部安装完成！
echo ================================
echo.
echo 请将设备关机并连接电脑，然后执行 0-关机方法进入bootloader.bat
echo.
pause