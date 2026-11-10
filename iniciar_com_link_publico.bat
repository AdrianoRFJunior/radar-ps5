@echo off
title RADAR BF 2026 - Servidores e Link Publico Permanente
echo ========================================================
echo   INICIANDO RADAR BF 2026 COM LINK PERMANENTE (NGROK)
echo ========================================================
echo.
cd /d "%~dp0"

echo 1. Iniciando Backend FastAPI (Porta 8000)...
start "Radar Backend (FastAPI)" /min cmd /c ".\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo 2. Iniciando Frontend Vite (Porta 5173)...
set "nodeDir=C:\Users\suporte.TECHCD\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.20.0-win-x64"
set "PATH=%nodeDir%;%PATH%"
cd frontend
start "Radar Frontend (Vite)" /min cmd /c "%nodeDir%\npm.cmd run dev"
cd ..

timeout /t 4 /nobreak >nul

echo 3. Iniciando Link Publico Permanente Ngrok...
echo.
echo ========================================================
echo Seu link fixo permanente para compartilhar com os amigos:
echo.
echo    https://shredder-cloud-ladder.ngrok-free.dev
echo.
echo (Mantenha esta janela aberta para seus amigos acessarem)
echo ========================================================
echo.

set "ngrokExe=C:\Users\suporte.TECHCD\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
"%ngrokExe%" http 5173 --domain=shredder-cloud-ladder.ngrok-free.dev
pause
