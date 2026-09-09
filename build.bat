@echo off
setlocal
cd /d %~dp0

if not exist .venv (
    py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

pyinstaller --noconfirm --clean --windowed --name "AI Dev Team" main.py

echo.
echo Build complete. See dist\AI Dev Team\
pause
