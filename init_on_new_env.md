# init venv
python -m venv venv

# activate venv
.\venv\Scripts\Activate.ps1

# install deps
pip install -r requirements-all.txt

# link brisk common (as admin, and under batch not ps1)
mklink /D C:\Users\brisk2\Documents\GitHub\SamoThraceTrader\brisk\common C:\Users\brisk2\Documents\GitHub\brisk-hack\gomihiroi\common

