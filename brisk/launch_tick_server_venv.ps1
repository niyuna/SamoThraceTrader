Write-Host "Starting brisk tick server in virtual environment..." -ForegroundColor Green
Write-Host ""

# 激活虚拟环境
& "..\venv\Scripts\Activate.ps1"

# 切换到brisk目录
Set-Location $PSScriptRoot

# 启动服务器
Write-Host "Starting uvicorn server on port 8001..." -ForegroundColor Yellow
uvicorn tick_server:app --host=0.0.0.0 --port=8001 --log-level info 