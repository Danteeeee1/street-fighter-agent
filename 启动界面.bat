@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动街霸6录像分析界面...
"C:\Users\liuzo\AppData\Local\Programs\Python\Python314\python.exe" -m sf6_agent.gui
if errorlevel 1 pause
