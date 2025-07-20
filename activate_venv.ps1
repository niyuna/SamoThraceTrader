Write-Host "Activating vnpy virtual environment..." -ForegroundColor Green
& ".\venv\Scripts\Activate.ps1"
Write-Host "Virtual environment activated!" -ForegroundColor Green
Write-Host "Python version:" -ForegroundColor Yellow
python --version
Write-Host ""
Write-Host "To deactivate, type: deactivate" -ForegroundColor Cyan
Write-Host "" 