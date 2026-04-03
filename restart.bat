@echo off
chcp 65001 >nul 2>&1

echo.
echo ========================================
echo   tailorCV - 重启服务
echo   自动清理缓存 + 重启
echo ========================================
echo.

:: Step 1: Kill ALL Python processes
echo [1/4] 停止旧进程...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo   - 完成
echo.

:: Step 2: Clear Python caches
echo [2/4] 清理 Python 缓存...
for /d /r "%~dp0" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" 2>nul
)
del /s /q "%~dp0*.pyc" >nul 2>&1
echo   - Python 缓存已清理
echo.

:: Step 3: Clear business caches
echo [3/4] 清理业务缓存...
if exist "%~dp0cache" (
    del /q "%~dp0cache\*.json" >nul 2>&1
    echo   - cache/ 已清理
) else (
    echo   - cache/ 不存在，跳过
)
python -c "
import shutil, time, os
root = os.path.dirname(os.path.abspath(__file__))
threshold = time.time() - 30 * 86400
count = 0
for subdir in ['storage/uploads', 'storage/tailored']:
    base = os.path.join(root, subdir)
    if not os.path.exists(base):
        continue
    for user in os.listdir(base):
        user_path = os.path.join(base, user)
        if not os.path.isdir(user_path):
            continue
        for session in os.listdir(user_path):
            session_path = os.path.join(user_path, session)
            if os.path.isdir(session_path):
                try:
                    if os.path.getmtime(session_path) < threshold:
                        shutil.rmtree(session_path)
                        count += 1
                except:
                    pass
if count > 0:
    print(f'   - storage/: 已清理 {count} 个过期目录')
else:
    print(f'   - storage/: 无过期文件')
" 2>nul
echo.

:: Step 4: Start service
echo [4/4] 启动服务...
echo.

:: 设置应用模式
set FLASK_ENV=production

python "%~dp0run_simple.py"
