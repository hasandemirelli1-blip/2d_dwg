@echo off
REM T2D-CAD - kaynak koddan calistirma (Python 3.10+ gerekir)
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Ilk calistirma: gerekli paketler kuruluyor, lutfen bekleyin...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" run_t2dcad.py %*
