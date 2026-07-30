@ECHO OFF
cd /d %~dp0
TITLE [1-获取identifier_token] 紫光展锐解锁BL
ECHO.
ECHO 适用于紫光展锐 SpreadTrum 全系列，使用公钥签名解锁设备。
ECHO.
ECHO 请将设备处于 Fastboot 模式，然后按任意键继续...
pause>nul
ECHO.
ECHO 正在获取 identifier_token（如果卡住说明设备未连接或驱动未安装）...
fastboot_sprd.exe oem get_identifier_token 1>..\identifier_token.txt 2>&1
type ..\identifier_token.txt
start ..\identifier_token.txt
ECHO.
ECHO 注意：如果 identifier_token 没有正常显示，请检查设备连接和驱动。
ECHO.
ECHO 完成。请将上面的 token 复制出来，下一步生成签名用。
pause>nul & EXIT