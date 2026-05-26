@echo off
chcp 65001 >nul
:: Semble搜索包装器 - 自动配置代理

:: 设置代理（请根据实际情况修改端口）
set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
set HF_HUB_OFFLINE=1

:: 调用Semble
"C:\Users\李文彬\AppData\Local\Programs\Python\Python312\Scripts\semble" %*
