# 瑞芯微机型破解教程

## 适用机型

T20 Pro，T30 Pro，T30 Ultra及后面的任何RK机型

# 方法

* 提取boot(DSU法,硬读存储芯片,或者全量包boot.img+更新路径上的N个差分包的boot.img.p并使用[KawaiiSparkle/imgpatchtools-python3](https://github.com/KawaiiSparkle/imgpatchtools-python3 "半成品这一块")中的ApplyPatch.py自行修补到机器系统目前运行的版本)
* 随便修补下镜像(毕竟无AVB),在电脑上用MIO-Kitchen或同类工具解包修补后的镜像,把你修补进去版本的完整安装包(ramdisk必须<=50M)用XZ算法压缩成stub.xz并与镜像中已有的替换,打包刷入即可
* 重启修复完环境后Root就大功告成了
* 装一个群内模块以完全使MDM无法使用
