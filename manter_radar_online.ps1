$ErrorActionPreference = "SilentlyContinue"
$projectDir = "c:\Users\suporte.TECHCD\Documents\Bot ps5"
$frontendDir = "c:\Users\suporte.TECHCD\Documents\Bot ps5\frontend"
$pythonExe = "c:\Users\suporte.TECHCD\Documents\Bot ps5\.venv\Scripts\python.exe"
$nodeDir = "C:\Users\suporte.TECHCD\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.20.0-win-x64"
$ngrokExe = "C:\Users\suporte.TECHCD\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
$env:PATH = "$nodeDir;$env:PATH"

while ($true) {
    # 1. Garantir Backend FastAPI na porta 8000
    $backendUp = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if (-not $backendUp) {
        Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $projectDir -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    # 2. Garantir Frontend Vite na porta 5173
    $frontendUp = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if (-not $frontendUp) {
        Start-Process -FilePath "$nodeDir\node.exe" -ArgumentList "`"$frontendDir\node_modules\vite\bin\vite.js`" --port 5173 --host" -WorkingDirectory $frontendDir -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }

    # 3. Garantir Túnel Fixo do Ngrok ativo
    $ngrokProc = Get-Process -Name "ngrok" -ErrorAction SilentlyContinue
    if (-not $ngrokProc) {
        Start-Process -FilePath $ngrokExe -ArgumentList "http 5173 --url=https://shredder-cloud-ladder.ngrok-free.dev" -WorkingDirectory $projectDir -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }

    Start-Sleep -Seconds 10
}
