@echo off
echo ========================================
echo 运行CAB策略所有测试
echo ========================================
echo.

REM 激活虚拟环境并运行测试
call ..\..\venv\Scripts\activate.bat

echo 1. 运行CAB主测试...
python test\cab\test_closing_auction_bet.py
if %errorlevel% neq 0 (
    echo CAB主测试失败！
    pause
    exit /b 1
)

echo.
echo 2. 运行CAB动态参数测试...
python test\cab\test_dynamic_params.py
if %errorlevel% neq 0 (
    echo CAB动态参数测试失败！
    pause
    exit /b 1
)

echo.
echo 3. 运行CAB演示脚本...
python test\cab\demo_closing_auction_bet.py
if %errorlevel% neq 0 (
    echo CAB演示脚本失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo 所有CAB测试完成！
echo ========================================
pause
