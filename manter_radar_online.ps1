$ErrorActionPreference = "SilentlyContinue"
$projectDir = "c:\Users\suporte.TECHCD\Documents\Bot ps5"
$frontendDir = "c:\Users\suporte.TECHCD\Documents\Bot ps5\frontend"
$pythonExe = "c:\Users\suporte.TECHCD\Documents\Bot ps5\.venv\Scripts\python.exe"
$nodeDir = "C:\Users\suporte.TECHCD\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.20.0-win-x64"
$gitExe = "C:\Program Files\Git\cmd\git.exe"
$env:PATH = "$nodeDir;C:\Program Files\Git\cmd;$env:PATH"

$cycleCounter = 0

while ($true) {
    # 1. Garantir Backend FastAPI na porta 8000
    $backendUp = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if (-not $backendUp) {
        Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory $projectDir -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    # 2. Garantir Frontend Vite na porta 5173
    $frontendUp = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if (-not $frontendUp) {
        Start-Process -FilePath "$nodeDir\node.exe" -ArgumentList "`"$frontendDir\node_modules\vite\bin\vite.js`" --port 5173 --host 0.0.0.0" -WorkingDirectory $frontendDir -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    # 3. A cada 10 minutos (60 ciclos de 10s), executar varredura automática, exportar JSONs e sincronizar com o GitHub Pages
    $cycleCounter++
    if ($cycleCounter -ge 60) {
        $cycleCounter = 0
        Set-Location $projectDir
        & $pythonExe scripts/export_static_data.py
        & $gitExe add frontend/public/data/*.json
        & $gitExe commit -m "chore(radar): sincronização automática de preços a cada 10 minutos"
        & $gitExe push origin main
    }

    Start-Sleep -Seconds 10
}
