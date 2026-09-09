@echo off
setlocal
cd /d %~dp0

if not exist .venv py -3 -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

python -m unittest discover -s tests -v
if errorlevel 1 (
    echo Tests failed. Build stopped.
    pause
    exit /b 1
)

pyinstaller --noconfirm --clean --windowed --name "AI Dev Team" main.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\AI Dev Team\AI Dev Team.exe
pause
