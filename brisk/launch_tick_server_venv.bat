@echo off
echo Starting brisk tick server in virtual environment...
echo.

REM 激活虚拟环境
call ..\venv\Scripts\activate.bat

REM 切换到brisk目录
cd /d "%~dp0"

REM 启动服务器
echo Starting uvicorn server on port 8001...
uvicorn tick_server:app --host=0.0.0.0 --port=8001 --log-level info

pause 