param(
  [string]$ApiTarget = "http://127.0.0.1:8000",
  [string]$FrontendTarget = "http://127.0.0.1:5173",
  [string]$Tickers = "FPT,VPB,MSB,SCS,ACV,ACB",
  [string]$SelectedTicker = "FPT",
  [switch]$SkipFrontendOpen,
  [switch]$ForceRefresh
)

$ErrorActionPreference = "Stop"

$script:Failures = @()
$script:PassCount = 0

function Fail {
  param([string]$Message)
  $script:Failures += $Message
  Write-Host ("[FAIL] {0}" -f $Message) -ForegroundColor Red
}

function Pass {
  param([string]$Message)
  $script:PassCount += 1
  Write-Host ("[PASS] {0}" -f $Message) -ForegroundColor Green
}

function Assert-True {
  param(
    [bool]$Condition,
    [string]$Message
  )

  if ($Condition) {
    Pass $Message
  } else {
    Fail $Message
  }
}

function Get-Property {
  param(
    [object]$Object,
    [string[]]$Names
  )

  if ($null -eq $Object) {
    return $null
  }

  foreach ($name in $Names) {
    if ($Object -is [System.Collections.IDictionary]) {
      if ($Object.Contains($name)) {
        return ,$Object[$name]
      }
    }

    $property = $Object.PSObject.Properties[$name]
    if ($null -ne $property) {
      return ,$property.Value
    }
  }

  return $null
}

function Test-HasProperty {
  param(
    [object]$Object,
    [string[]]$Names
  )

  if ($null -eq $Object) {
    return $false
  }

  foreach ($name in $Names) {
    if ($Object -is [System.Collections.IDictionary]) {
      if ($Object.Contains($name)) {
        return $true
      }
    }

    $property = $Object.PSObject.Properties[$name]
    if ($null -ne $property) {
      return $true
    }
  }

  return $false
}

function Get-Json {
  param([string]$Uri)

  try {
    return Invoke-RestMethod -Method Get -Uri $Uri -TimeoutSec 90
  } catch {
    Fail ("GET failed: {0} - {1}" -f $Uri, $_.Exception.Message)
    return $null
  }
}

function Convert-ToList {
  param([object]$Value)

  if ($null -eq $Value) {
    return @()
  }

  if ($Value -is [System.Array]) {
    return ,$Value
  }

  if ($Value -is [System.Collections.IList] -and -not ($Value -is [string])) {
    return ,$Value
  }

  return @($Value)
}

function Test-IsList {
  param([object]$Value)

  if ($Value -is [System.Array]) {
    return $true
  }

  if ($Value -is [System.Collections.IList] -and -not ($Value -is [string])) {
    return $true
  }

  return $false
}

function Convert-ToNumberOrNull {
  param([object]$Value)

  if ($null -eq $Value) {
    return $null
  }

  if ($Value -is [string] -and [string]::IsNullOrWhiteSpace($Value)) {
    return $null
  }

  try {
    return [double]$Value
  } catch {
    return $null
  }
}

function Normalize-Ticker {
  param([string]$Ticker)

  if ($null -eq $Ticker) {
    return ""
  }

  $normalized = $Ticker.Trim().ToUpperInvariant()
  if ($normalized.EndsWith(".VN")) {
    $normalized = $normalized.Substring(0, $normalized.Length - 3)
  }
  return $normalized
}

function Get-Text {
  param(
    [object]$Object,
    [string[]]$Names
  )

  $value = Get-Property $Object $Names
  if ($null -eq $value) {
    return $null
  }
  return [string]$value
}

function Test-PrimaryMessageLeak {
  param([string]$Message)

  if ([string]::IsNullOrWhiteSpace($Message)) {
    return $false
  }

  return $Message -match "(?i)(attempted\s+endpoints?|last\s+endpoint|http\s+status|raw\s+provider|RealtimeQuote|RealtimePrice|MatchedTrades|/api/)"
}

function Assert-PublicMessageClean {
  param(
    [string]$Label,
    [object]$Object
  )

  $message = Get-Text $Object @("message")
  if ([string]::IsNullOrWhiteSpace($message)) {
    Pass ("{0} public message absent or empty" -f $Label)
    return
  }

  Assert-True (-not (Test-PrimaryMessageLeak $message)) ("{0} public message is short and user-safe" -f $Label)
}

function Write-DiagnosticsSummary {
  param(
    [string]$Label,
    [object]$Object
  )

  $diagnostics = Get-Property $Object @("diagnostics")
  if ($null -eq $diagnostics) {
    return
  }

  $keys = @($diagnostics.PSObject.Properties | ForEach-Object { $_.Name })
  if ($keys.Count -gt 0) {
    Write-Host ("[INFO] {0} diagnostics keys: {1}" -f $Label, ($keys -join ", "))
  }
}

function Assert-Source {
  param(
    [string]$Label,
    [object]$Object,
    [string[]]$Names,
    [string]$Expected
  )

  $actual = Get-Text $Object $Names
  Assert-True ($actual -eq $Expected) ("{0} source is {1}" -f $Label, $Expected)
}

function Assert-NotSsiLabeled {
  param(
    [string]$Label,
    [object]$Object
  )

  $source = Get-Text $Object @("source")
  $isSsi = $false
  if (-not [string]::IsNullOrWhiteSpace($source)) {
    $isSsi = $source -match "(?i)\bSSI\b"
  }
  Assert-True (-not $isSsi) ("{0} is not SSI-labeled" -f $Label)
}

function Get-UrlWithForceRefresh {
  param(
    [string]$BaseUrl,
    [bool]$UseForceRefresh
  )

  if ($UseForceRefresh) {
    if ($BaseUrl.Contains("?")) {
      return ($BaseUrl + "&force_refresh=true")
    }
    return ($BaseUrl + "?force_refresh=true")
  }

  return $BaseUrl
}

$apiBase = $ApiTarget.TrimEnd("/")
$frontendBase = $FrontendTarget.TrimEnd("/")
$requestedTickers = @(
  $Tickers.Split(",") |
    ForEach-Object { Normalize-Ticker $_ } |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
)
$selected = Normalize-Ticker $SelectedTicker

Write-Host "VN dashboard smoke/regression harness"
Write-Host ("API target: {0}" -f $apiBase)
Write-Host ("Frontend target: {0}" -f $frontendBase)
Write-Host ("Tickers: {0}" -f ($requestedTickers -join ","))
Write-Host ("Selected ticker: {0}" -f $selected)
Write-Host ("Force refresh: {0}" -f [bool]$ForceRefresh)
Write-Host "Secrets: not printed"
Write-Host ""

if ($requestedTickers.Count -eq 0) {
  Fail "At least one ticker is required."
}

if ([string]::IsNullOrWhiteSpace($selected)) {
  Fail "SelectedTicker is required."
}

$tickersQuery = [System.Uri]::EscapeDataString(($requestedTickers -join ","))
$watchlistUrl = Get-UrlWithForceRefresh ("{0}/api/v1/stocks/vn/watchlist?tickers={1}" -f $apiBase, $tickersQuery) ([bool]$ForceRefresh)
$companyTickerPath = [System.Uri]::EscapeDataString($selected)
$companyUrl = Get-UrlWithForceRefresh ("{0}/api/v1/stocks/vn/company/{1}" -f $apiBase, $companyTickerPath) ([bool]$ForceRefresh)

Write-Host ("GET {0}" -f $watchlistUrl)
$watchlistResponse = Get-Json $watchlistUrl

$watchlistRows = @()
if ($null -ne $watchlistResponse) {
  $watchlistRows = Convert-ToList -Value (Get-Property $watchlistResponse @("watchlist"))
}

Assert-True ($watchlistRows.Count -gt 0) "watchlist response has watchlist rows"

$rowsByTicker = @{}
foreach ($row in $watchlistRows) {
  $rowTicker = Normalize-Ticker (Get-Text $row @("ticker", "symbol"))
  if (-not [string]::IsNullOrWhiteSpace($rowTicker)) {
    $rowsByTicker[$rowTicker] = $row
  }
}

foreach ($ticker in $requestedTickers) {
  Assert-True ($rowsByTicker.ContainsKey($ticker)) ("watchlist contains {0}" -f $ticker)
}

$foreignNetVolumeSum = 0.0
$foreignNetVolumeCount = 0

foreach ($ticker in $requestedTickers) {
  if (-not $rowsByTicker.ContainsKey($ticker)) {
    continue
  }

  $row = $rowsByTicker[$ticker]
  $latestPrice = Get-Property $row @("latest_price", "latestPrice")
  $dailyClose = Get-Property $row @("daily_close", "dailyClose", "ohlcv_close", "ohlcvClose")
  $volume = Get-Property $row @("volume")
  Assert-True ($null -ne $latestPrice) ("{0} has latest_price" -f $ticker)
  Assert-True ($null -ne $dailyClose) ("{0} has daily_close or ohlcv_close" -f $ticker)
  Assert-True ($null -ne $volume) ("{0} has volume" -f $ticker)

  Assert-True (Test-HasProperty $row @("ssi_foreign_net_volume", "ssiForeignNetVolume")) ("{0} has ssi_foreign_net_volume basis" -f $ticker)
  $foreignNetVolume = Convert-ToNumberOrNull (Get-Property $row @("ssi_foreign_net_volume", "ssiForeignNetVolume"))
  if ($null -ne $foreignNetVolume) {
    $foreignNetVolumeSum += $foreignNetVolume
    $foreignNetVolumeCount += 1
  }

  $tradeTape = Get-Property $row @("trade_tape", "tradeTape")
  Assert-True (Test-IsList -Value $tradeTape) ("{0} trade_tape is a list" -f $ticker)
  Assert-True (Test-HasProperty $row @("trade_tape_status", "tradeTapeStatus")) ("{0} has trade_tape_status" -f $ticker)

  $intradayPulse = Get-Property $row @("intraday_pulse", "intradayPulse")
  $intradayCandles = Get-Property $row @("intraday_candles", "intradayCandles")
  $realtimeSnapshot = Get-Property $row @("realtime_snapshot", "realtimeSnapshot")
  Assert-True (($null -eq $intradayPulse) -or ($intradayPulse -is [object])) ("{0} intraday_pulse is nullable object" -f $ticker)
  Assert-True (Test-IsList -Value $intradayCandles) ("{0} intraday_candles is a list" -f $ticker)
  Assert-True (($null -eq $realtimeSnapshot) -or ($realtimeSnapshot -is [object])) ("{0} realtime_snapshot is nullable object" -f $ticker)

  $intradayStatus = Get-Property $row @("intraday_status", "intradayStatus")
  $realtimeStatus = Get-Property $row @("realtime_status", "realtimeStatus")
  $tradeTapeStatus = Get-Property $row @("trade_tape_status", "tradeTapeStatus")
  Assert-PublicMessageClean ("{0} intraday_status" -f $ticker) $intradayStatus
  Assert-PublicMessageClean ("{0} realtime_status" -f $ticker) $realtimeStatus
  Assert-PublicMessageClean ("{0} trade_tape_status" -f $ticker) $tradeTapeStatus
  Write-DiagnosticsSummary ("{0} intraday_status" -f $ticker) $intradayStatus
  Write-DiagnosticsSummary ("{0} realtime_status" -f $ticker) $realtimeStatus
  Write-DiagnosticsSummary ("{0} trade_tape_status" -f $ticker) $tradeTapeStatus
}

Write-Host ("EXPECTED Foreign net volume = {0}" -f ([Math]::Round($foreignNetVolumeSum, 4)))
Write-Host ("Foreign net volume rows used = {0}" -f $foreignNetVolumeCount)
Write-Host ""

Write-Host ("GET {0}" -f $companyUrl)
$companyResponse = Get-Json $companyUrl

if ($null -ne $companyResponse) {
  $price = Get-Property $companyResponse @("price")
  $tradingStats = Get-Property $companyResponse @("trading_stats", "tradingStats")
  $foreignFlow = Get-Property $companyResponse @("foreign_flow", "foreignFlow")
  $intraday = Get-Property $companyResponse @("intraday")
  $realtimeSnapshot = Get-Property $companyResponse @("realtime_snapshot", "realtimeSnapshot")
  $realtimeStatus = Get-Property $companyResponse @("realtime_status", "realtimeStatus")
  $tradeTapeRows = Get-Property $companyResponse @("trade_tape", "tradeTape")
  $tradeTapeStatus = Get-Property $companyResponse @("trade_tape_status", "tradeTapeStatus")
  $news = Get-Property $companyResponse @("news")
  $financials = Get-Property $companyResponse @("financials")
  $events = Get-Property $companyResponse @("events")

  $priceSource = Get-Text $price @("source")
  $priceCanonicalSource = Get-Text $price @("canonical_source", "canonicalSource")
  Assert-True (($priceSource -eq "SSI DailyOhlc") -or ($priceCanonicalSource -eq "SSI DailyOhlc")) "company price source or canonical_source is SSI DailyOhlc"
  Assert-Source "company price reference" $price @("reference_source", "referenceSource") "SSI DailyStockPrice"
  Assert-Source "company trading_stats" $tradingStats @("source") "SSI DailyOhlc"
  Assert-Source "company foreign_flow" $foreignFlow @("source") "SSI DailyStockPrice"

  $companyIntradayPulse = Get-Property $intraday @("pulse")
  $companyIntradayCandles = Get-Property $intraday @("candles")
  Assert-True (($null -eq $companyIntradayPulse) -or ($companyIntradayPulse -is [object])) "company intraday.pulse is nullable object"
  Assert-True (Test-IsList -Value $companyIntradayCandles) "company intraday.candles is a list"
  Assert-True (($null -eq $realtimeSnapshot) -or ($realtimeSnapshot -is [object])) "company realtime_snapshot is nullable object"
  Assert-True (Test-IsList -Value $tradeTapeRows) "company trade_tape is a list"

  Assert-NotSsiLabeled "company news block" $news
  Assert-NotSsiLabeled "company financials block" $financials
  Assert-NotSsiLabeled "company events block" $events

  $sourceCoverage = Convert-ToList -Value (Get-Property $companyResponse @("source_coverage", "sourceCoverage"))
  foreach ($coverage in $sourceCoverage) {
    $block = Get-Text $coverage @("block")
    if ($block -in @("News", "Financials", "Corporate actions", "Events")) {
      Assert-NotSsiLabeled ("company source coverage {0}" -f $block) $coverage
    }
  }

  Assert-PublicMessageClean "company intraday" $intraday
  Assert-PublicMessageClean "company realtime_status" $realtimeStatus
  Assert-PublicMessageClean "company trade_tape_status" $tradeTapeStatus
  Write-DiagnosticsSummary "company intraday" $intraday
  Write-DiagnosticsSummary "company realtime_status" $realtimeStatus
  Write-DiagnosticsSummary "company trade_tape_status" $tradeTapeStatus
}

Write-Host ""
Write-Host "API status summary"
if ($null -ne $watchlistResponse) {
  Write-Host ("watchlist source: {0}" -f (Get-Text $watchlistResponse @("source")))
  Write-Host ("watchlist rows: {0}" -f $watchlistRows.Count)
  Write-Host ("fixture mode: {0}" -f (Get-Text $watchlistResponse @("fixture_mode", "fixtureMode")))
}
if ($null -ne $companyResponse) {
  Write-Host ("company status: {0}" -f (Get-Text $companyResponse @("status")))
  $summaryPrice = Get-Property $companyResponse @("price")
  $summaryRealtime = Get-Property $companyResponse @("realtime_status", "realtimeStatus")
  $summaryTradeTape = Get-Property $companyResponse @("trade_tape_status", "tradeTapeStatus")
  Write-Host ("company price source: {0}" -f (Get-Text $summaryPrice @("source")))
  Write-Host ("company realtime status: {0}" -f (Get-Text $summaryRealtime @("status")))
  Write-Host ("company trade tape status: {0}" -f (Get-Text $summaryTradeTape @("status")))
}

$dashboardUrl = "{0}/vietnam" -f $frontendBase
$companyFrontendUrl = "{0}/vietnam/company/{1}" -f $frontendBase, $selected
Write-Host ""
Write-Host "Expected frontend URLs:"
Write-Host $dashboardUrl
Write-Host $companyFrontendUrl
if ($SkipFrontendOpen) {
  Write-Host "Frontend open skipped."
} else {
  Write-Host ("Open {0}" -f $dashboardUrl)
  Write-Host ("Open {0}" -f $companyFrontendUrl)
}

Write-Host ""
if ($script:Failures.Count -gt 0) {
  Write-Host ("FAIL: {0} check(s) failed, {1} passed." -f $script:Failures.Count, $script:PassCount) -ForegroundColor Red
  Write-Host "Failed checks:"
  foreach ($failure in $script:Failures) {
    Write-Host ("- {0}" -f $failure) -ForegroundColor Red
  }
  exit 1
}

Write-Host ("PASS: {0} check(s) passed." -f $script:PassCount) -ForegroundColor Green
exit 0
