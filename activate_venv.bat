@echo off
echo Activating vnpy virtual environment...
call venv\Scripts\activate.bat
echo Virtual environment activated!
echo Python version:
python --version
echo.
echo To deactivate, type: deactivate
echo.
cmd /k 