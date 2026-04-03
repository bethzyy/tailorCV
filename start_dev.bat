@echo off
chcp 65001 >/dev/null 2>&1
echo.
echo ========================================
echo   tailorCV - 开发模式启动
echo   特性: 自动重载 + 详细错误 + 全量清缓存
echo ========================================
echo.

:: 设置开发模式环境变量
set FLASK_ENV=development

:: 预清理 Python 缓存（run_simple.py 启动时会做完整清理）
echo 清理 __pycache__...
for /d /r "%~dp0" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)
del /s /q "%~dp0*.pyc" >nul 2>&1

:: 启动服务
python "%~dp0run_simple.py"
pause
