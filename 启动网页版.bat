@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动街霸6录像分析网页版...
echo 启动后会自动打开浏览器 http://127.0.0.1:8765
start "" "http://127.0.0.1:8765"
"C:\Users\liuzo\.workbuddy\binaries\python\versions\3.13.12\python.exe" -m sf6_agent.webapp
if errorlevel 1 pause
