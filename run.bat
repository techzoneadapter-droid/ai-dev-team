@echo off
setlocal
cd /d %~dp0

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher ^(py.exe^) was not found.
    echo Install Python 3.11 or newer from python.org and enable the Python Launcher.
    pause
    exit /b 1
)

if not exist .venv (
    py -3 -m venv .venv
    if errorlevel 1 exit /b 1
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)
python main.py
