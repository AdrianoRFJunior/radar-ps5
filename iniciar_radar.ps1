# Script de Inicialização Completa do RADAR BF 2026
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$nodeDir = "$env:LOCALAPPDATA\Programs\nodejs"
if (-not (Test-Path "$nodeDir\npm.cmd")) {
    $npmCmd = Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages", "C:\Program Files\nodejs", "$env:LOCALAPPDATA\Programs" -Filter "npm.cmd" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($npmCmd) { $nodeDir = $npmCmd.DirectoryName }
}
$env:PATH = "$nodeDir;$env:PATH"

Write-Host "============================================================" -ForegroundColor Green
Write-Host "   RADAR BF 2026 - INICIANDO BACKEND, SCHEDULER E FRONTEND  " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ProjectRoot'; .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PATH='$nodeDir;' + `$env:PATH; Set-Location '$ProjectRoot\frontend'; npm run dev"

Write-Host "Backend API & Monitoramento Automático: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Dashboard Interativo RADAR BF 2026:     http://localhost:5173" -ForegroundColor Green
