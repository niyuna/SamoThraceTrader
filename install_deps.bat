@echo off
echo Installing vnpy dependencies...
echo.

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 升级pip和wheel
echo Upgrading pip and wheel...
python -m pip install --upgrade pip wheel

REM 安装ta-lib（需要特殊处理）
echo Installing ta-lib...
python -m pip install --extra-index-url https://pypi.vnpy.com ta_lib==0.6.4

REM 安装所有依赖
echo Installing all dependencies...
pip install -r requirements-all.txt

REM 可编辑安装vnpy
echo Installing vnpy in editable mode...
pip install -e .

echo.
echo Dependencies installed successfully!
echo.
echo To activate the environment, run:
echo   venv\Scripts\activate.bat
echo.
pause 