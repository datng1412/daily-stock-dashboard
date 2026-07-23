param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8000
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

      if ($name) {
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
      }
    }
  }

  Write-Host ".env loaded into current process."
} else {
  Write-Host ".env not found. Continuing with existing process env."
}

$ssiV3Enabled = [string]$env:SSI_V3_REST_ENABLED
$ssiV3ApiKeyPresent = [bool]$env:SSI_V3_API_KEY
$ssiV3ApiSecretPresent = [bool]$env:SSI_V3_API_SECRET
$mozyfinEnabled = [string]$env:MOZYFIN_ENABLED
$legacyMozyfinAllowed = [string]$env:VN_ALLOW_LEGACY_MOZYFIN_PROVIDER
$kbsEnabled = [string]$env:KBS_ENABLED
$legacyKbsAllowed = [string]$env:VN_ALLOW_LEGACY_KBS_PROVIDER

Write-Host ""
Write-Host "Safe env diagnostics:"
Write-Host "SSI_V3_REST_ENABLED: $ssiV3Enabled"
Write-Host "SSI_V3_API_KEY present: $ssiV3ApiKeyPresent"
Write-Host "SSI_V3_API_SECRET present: $ssiV3ApiSecretPresent"
Write-Host "MOZYFIN_ENABLED: $mozyfinEnabled"
Write-Host "VN_ALLOW_LEGACY_MOZYFIN_PROVIDER: $legacyMozyfinAllowed"
Write-Host "KBS_ENABLED: $kbsEnabled"
Write-Host "VN_ALLOW_LEGACY_KBS_PROVIDER: $legacyKbsAllowed"
Write-Host ("Backend: http://{0}:{1}" -f $HostName, $Port)
Write-Host ""
Write-Host "Starting backend in foreground. Press Ctrl+C to stop."
Write-Host ""

python main.py --serve-only --host $HostName --port $Port

exit $LASTEXITCODE
