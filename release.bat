@echo off
setlocal
cd /d %~dp0
call build.bat
if errorlevel 1 exit /b 1

powershell -NoProfile -Command "if (Test-Path 'AI-Dev-Team-Windows.zip') { Remove-Item 'AI-Dev-Team-Windows.zip' }; Compress-Archive -Path 'dist\AI Dev Team\*' -DestinationPath 'AI-Dev-Team-Windows.zip'"
if errorlevel 1 exit /b 1

echo Release ZIP created: AI-Dev-Team-Windows.zip
pause
