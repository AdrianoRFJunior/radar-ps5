$ErrorActionPreference = "SilentlyContinue"
$projectDir = "c:\Users\suporte.TECHCD\Documents\Bot ps5"
$frontendDir = "c:\Users\suporte.TECHCD\Documents\Bot ps5\frontend"
$pythonExe = "c:\Users\suporte.TECHCD\Documents\Bot ps5\.venv\Scripts\python.exe"
$nodeDir = "C:\Users\suporte.TECHCD\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.20.0-win-x64"
$gitExe = "C:\Program Files\Git\cmd\git.exe"
$env:PATH = "$nodeDir;C:\Program Files\Git\cmd;$env:PATH"

# Modo Turbo Black Friday: iniciar em 17 para disparar a primeira varredura imediatamente
$cycleCounter = 17

Write-Output "[RADAR BLACK FRIDAY] Modo Intensivo iniciado (varredura continua + sync GitHub a cada 3 min)."

while ($true) {
    # 1. Garantir Backend FastAPI na porta 8000
    $backendUp = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if (-not $backendUp) {
        Write-Output "[RADAR] Iniciando Backend FastAPI na porta 8000..."
        Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory $projectDir -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    # 2. Garantir Frontend Vite na porta 5173
    $frontendUp = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if (-not $frontendUp) {
        Write-Output "[RADAR] Iniciando Frontend Vite na porta 5173..."
        Start-Process -FilePath "$nodeDir\node.exe" -ArgumentList "`"$frontendDir\node_modules\vite\bin\vite.js`" --port 5173 --host 0.0.0.0" -WorkingDirectory $frontendDir -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    # 3. Modo Turbo Black Friday: a cada 3 minutos (18 ciclos de 10s), varrer lojas e sincronizar com GitHub Pages
    $cycleCounter++
    if ($cycleCounter -ge 18) {
        $cycleCounter = 0
        Set-Location $projectDir
        Write-Output "[RADAR BF] Executando varredura intensiva Black Friday em +20 lojas..."
        & $pythonExe scripts/export_static_data.py
        & $gitExe add frontend/public/data/*.json
        & $gitExe commit -m "chore(black-friday): atualização intensiva de promoções em tempo real"
        & $gitExe push origin main
        Write-Output "[RADAR BF] Sincronizacao concluida. Proxima sincronizacao em 3 minutos."
    }

    Start-Sleep -Seconds 10
}
