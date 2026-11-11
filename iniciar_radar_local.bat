@echo off
title RADAR BF 2026 - Acesso Local e GitHub Pages
echo ========================================================
echo            RADAR BF 2026 - INICIALIZADOR LOCAL
echo ========================================================
echo.
cd /d "%~dp0"

echo 1. Iniciando Backend FastAPI (Porta 8000)...
start "Radar Backend (FastAPI)" /min cmd /c ".\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo 2. Iniciando Frontend Vite (Porta 5173)...
set "nodeDir=C:\Users\suporte.TECHCD\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.20.0-win-x64"
set "PATH=%nodeDir%;%PATH%"
cd frontend
start "Radar Frontend (Vite)" /min cmd /c "%nodeDir%\npm.cmd run dev -- --host 0.0.0.0"
cd ..

timeout /t 3 /nobreak >nul

echo.
echo ========================================================
echo   PROGRAMA PRONTO! ACESSE NOS LINKS ABAIXO:
echo.
echo   [PC LOCAL]:       http://localhost:5173
echo   [REDE LOCAL]:     http://192.168.0.52:5173
echo.
echo   [LINK PUBLICO]:   https://adrianorfjunior.github.io/radar-ps5/
echo ========================================================
echo.
echo Abrindo o painel no seu navegador...
start http://localhost:5173
echo.
echo Pressione qualquer tecla para fechar este aviso (os servidores continuarao rodando).
pause >nul
