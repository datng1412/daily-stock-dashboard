param(
[string]$HostName = "127.0.0.1",
[int]$Port = 8000,
[switch]$NoMozyfinPathPatch
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

Write-Host "Repo root: $repoRoot"

$envPath = Join-Path $repoRoot ".env"

if (Test-Path $envPath) {
Get-Content $envPath | ForEach-Object {
$line = $_.Trim()
if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
$parts = $line.Split("=", 2)
$name = $parts[0].Trim()
$value = $parts[1].Trim().Trim('"').Trim("'")
[Environment]::SetEnvironmentVariable($name, $value, "Process")
}
}

Write-Host ".env loaded into current process."
} else {
Write-Host ".env not found. Continuing with existing process env."
}

if (-not $NoMozyfinPathPatch) {
try {
$npmRoot = npm.cmd root -g
$npmBin = Split-Path $npmRoot

```
if (Test-Path $npmBin) {
  $env:PATH = "$npmBin;$env:PATH"

  $mozyfinCmd = Join-Path $npmBin "mozyfin-cli.cmd"
  if (Test-Path $mozyfinCmd) {
    $env:MOZYFIN_COMMAND = $mozyfinCmd
  }
}
```

} catch {
Write-Host "Could not resolve npm global bin. Mozyfin CLI may not be available."
}
}

$ssiIdPresent = [bool]$env:SSI_FASTCONNECT_CONSUMER_ID
$ssiSecretPresent = [bool]$env:SSI_FASTCONNECT_CONSUMER_SECRET
$mozyfinKeyPresent = [bool]$env:MOZYFIN_API_KEY
$mozyfinCommandFound = $false

if ($env:MOZYFIN_COMMAND -and (Test-Path $env:MOZYFIN_COMMAND)) {
$mozyfinCommandFound = $true
} elseif (Get-Command mozyfin-cli.cmd -ErrorAction SilentlyContinue) {
$mozyfinCommandFound = $true
}

Write-Host ""
Write-Host "Safe env diagnostics:"
Write-Host "SSI_FASTCONNECT_CONSUMER_ID present: $ssiIdPresent"
Write-Host "SSI_FASTCONNECT_CONSUMER_SECRET present: $ssiSecretPresent"
Write-Host "MOZYFIN_API_KEY present: $mozyfinKeyPresent"
Write-Host "MOZYFIN_COMMAND: $env:MOZYFIN_COMMAND"
Write-Host "mozyfin-cli command found: $mozyfinCommandFound"
Write-Host "Backend: http://$HostName`:$Port"
Write-Host ""
Write-Host "Starting backend in foreground. Press Ctrl+C to stop."
Write-Host ""

python main.py --serve-only --host $HostName --port $Port

exit $LASTEXITCODE
