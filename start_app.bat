@echo off
chcp 65001 >/dev/null 2>&1
echo.
echo ========================================
echo   tailorCV - 应用模式启动
echo   特性: 稳定运行 (修改代码需手动重启)
echo ========================================
echo.

:: 设置应用模式环境变量
set FLASK_ENV=production

:: 启动服务
python "%~dp0run_simple.py"
pause
