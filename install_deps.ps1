Write-Host "Installing vnpy dependencies..." -ForegroundColor Green
Write-Host ""

# 激活虚拟环境
& ".\venv\Scripts\Activate.ps1"

# 升级pip和wheel
Write-Host "Upgrading pip and wheel..." -ForegroundColor Yellow
python -m pip install --upgrade pip wheel

# 安装ta-lib（需要特殊处理）
Write-Host "Installing ta-lib..." -ForegroundColor Yellow
python -m pip install --extra-index-url https://pypi.vnpy.com ta_lib==0.6.4

# 安装所有依赖
Write-Host "Installing all dependencies..." -ForegroundColor Yellow
pip install -r requirements-all.txt

# 可编辑安装vnpy
Write-Host "Installing vnpy in editable mode..." -ForegroundColor Yellow
pip install -e .

Write-Host ""
Write-Host "Dependencies installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "To activate the environment, run:" -ForegroundColor Cyan
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "" 