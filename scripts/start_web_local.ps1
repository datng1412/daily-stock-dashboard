param(
[string]$ApiTarget = "http://127.0.0.1:8000",
[int]$Port = 5173
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$webRoot = Join-Path $repoRoot "apps\dsa-web"

if (-not (Test-Path $webRoot)) {
throw "Web app folder not found: $webRoot"
}

Set-Location $webRoot

$env:VITE_API_PROXY_TARGET = $ApiTarget

Write-Host "Web root: $webRoot"
Write-Host "VITE_API_PROXY_TARGET: $env:VITE_API_PROXY_TARGET"
Write-Host "Frontend: [http://127.0.0.1:$Port](http://127.0.0.1:$Port)"
Write-Host ""
Write-Host "Starting frontend in foreground. Press Ctrl+C to stop."
Write-Host ""

npm.cmd run dev -- --host 127.0.0.1 --port $Port

exit $LASTEXITCODE
