@ECHO OFF
cd /d %~dp0
set path=%cd%;%path%
TITLE [2-生成signature] 紫光展锐解锁BL
ECHO.
ECHO 适用于紫光展锐 SpreadTrum 全系列，使用公钥签名解锁设备。
ECHO.
ECHO 注意：本脚本需要 VC++ 运行库才能运行 openssl.exe
ECHO 如果提示缺少 DLL 报错，先运行「安装运行库和驱动.bat」安装运行库。
ECHO.
:A
set identifier_token=
set /p identifier_token=请输入 identifier_token（从上一步复制）:
if "%identifier_token%"=="" goto A
ECHO.
ECHO 正在生成 signature...
busybox.exe ash unlockbl.sh %identifier_token% sign.pem ..\signature.bin || ECHO.签名失败.
ECHO.
ECHO 如果显示 "Identifier sign successfully"，说明签名生成成功。
ECHO 如果报错请检查 identifier_token 是否完整正确。
ECHO.
ECHO 完成。生成的 signature.bin 在上级目录中。
pause>nul & EXIT