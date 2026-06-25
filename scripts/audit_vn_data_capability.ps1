param(
  [string]$ApiTarget = "http://127.0.0.1:8000",
  [string]$Tickers = "FPT,VPB,ACB,SSI,GMD,GAS,POW,VNM",
  [string]$SelectedTicker = "FPT",
  [switch]$ForceRefresh
)

$ErrorActionPreference = "Stop"

$allowedStatuses = @(
  "reliable",
  "partial",
  "unavailable",
  "disabled",
  "future-provider",
  "unknown-needs-verification"
)

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

function Get-Value {
  param(
    [object]$Object,
    [string[]]$Names
  )

  if ($null -eq $Object) {
    return $null
  }

  foreach ($name in $Names) {
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($name)) {
      return $Object[$name]
    }

    $property = $Object.PSObject.Properties[$name]
    if ($null -ne $property) {
      return $property.Value
    }
  }

  return $null
}

function Has-Value {
  param([object]$Value)

  if ($null -eq $Value) {
    return $false
  }

  if ($Value -is [string]) {
    return -not [string]::IsNullOrWhiteSpace($Value)
  }

  return $true
}

function Convert-ToList {
  param([object]$Value)

  if ($null -eq $Value) {
    return @()
  }

  if ($Value -is [System.Array]) {
    return @($Value)
  }

  if ($Value -is [System.Collections.IList] -and -not ($Value -is [string])) {
    return @($Value)
  }

  return @($Value)
}

function Test-SourceContains {
  param(
    [object]$Object,
    [string[]]$Names,
    [string]$Expected
  )

  foreach ($name in $Names) {
    $value = Get-Value $Object @($name)
    if ($null -ne $value -and ([string]$value) -match [regex]::Escape($Expected)) {
      return $true
    }
  }
  return $false
}

function Count-Matching {
  param(
    [object[]]$Rows,
    [scriptblock]$Predicate
  )

  $count = 0
  foreach ($row in $Rows) {
    if (& $Predicate $row) {
      $count += 1
    }
  }
  return $count
}

function Format-UniqueValues {
  param([object[]]$Values)

  $normalized = @(
    $Values |
      Where-Object { Has-Value $_ } |
      ForEach-Object { [string]$_ } |
      Select-Object -Unique
  )

  if ($normalized.Count -eq 0) {
    return "none"
  }

  return ($normalized -join ",")
}

function Format-ScalarValue {
  param([object]$Value)

  if (Has-Value $Value) {
    return [string]$Value
  }
  return "none"
}

function Get-Status {
  param([object]$Object)

  $value = Get-Value $Object @("status")
  if ($null -eq $value) {
    return $null
  }
  return ([string]$value).Trim().ToLowerInvariant()
}

function New-CapabilityRow {
  param(
    [string]$Domain,
    [string]$Status,
    [string]$SourceOwner,
    [string]$Evidence,
    [string]$SafeUiFields,
    [string]$Notes
  )

  if ($allowedStatuses -notcontains $Status) {
    $Status = "unknown-needs-verification"
  }

  [PSCustomObject]@{
    Domain = $Domain
    Status = $Status
    "Source owner" = $SourceOwner
    Evidence = $Evidence
    "Safe UI fields" = $SafeUiFields
    Notes = $Notes
  }
}

function Get-AuditJson {
  param(
    [string]$Uri,
    [string]$Label,
    [bool]$Required
  )

  try {
    $script:EndpointsCalled += $Label
    return Invoke-RestMethod -Method Get -Uri $Uri -TimeoutSec 90
  } catch {
    $statusCode = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $statusCode = [int]$_.Exception.Response.StatusCode
    }

    if ($Required -or ($statusCode -notin @(404, 405, 501))) {
      throw ("Audit request failed ({0}). Backend unreachable or request failed: {1}" -f $Label, $_.Exception.Message)
    }

    return [PSCustomObject]@{
      status = "unavailable"
      audit_request_failed = $true
      audit_status_code = $statusCode
      audit_label = $Label
    }
  }
}

function Get-OptionalStatusFromEndpoint {
  param(
    [object]$Payload,
    [string]$RowsProperty,
    [string]$DisabledStatus = "disabled"
  )

  if ($null -eq $Payload) {
    return "unknown-needs-verification"
  }

  if (Get-Value $Payload @("audit_request_failed")) {
    $code = Get-Value $Payload @("audit_status_code")
    if ($code -eq 404) {
      return "unknown-needs-verification"
    }
    return "unavailable"
  }

  $status = Get-Status $Payload
  if ($status -eq "disabled") {
    return $DisabledStatus
  }
  if ($status -eq "ok") {
    $rows = @(Convert-ToList (Get-Value $Payload @($RowsProperty)))
    if ($rows.Count -gt 0) {
      return "reliable"
    }
    return "partial"
  }
  if ($status -eq "unavailable") {
    return "unavailable"
  }
  return "unknown-needs-verification"
}

$apiBase = $ApiTarget.TrimEnd("/")
$requestedTickers = @(
  $Tickers.Split(",") |
    ForEach-Object { Normalize-Ticker $_ } |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
)
$selected = Normalize-Ticker $SelectedTicker

if ($requestedTickers.Count -eq 0) {
  throw "At least one ticker is required."
}

if ([string]::IsNullOrWhiteSpace($selected)) {
  throw "SelectedTicker is required."
}

$tickersQuery = [System.Uri]::EscapeDataString(($requestedTickers -join ","))
$selectedQuery = [System.Uri]::EscapeDataString($selected)
$forceSuffix = ""
if ($ForceRefresh) {
  $forceSuffix = "&force_refresh=true"
}

$script:EndpointsCalled = @()

Write-Host "VN data capability audit"
Write-Host ("API target: {0}" -f $apiBase)
Write-Host ("Tickers: {0}" -f ($requestedTickers -join ","))
Write-Host ("Selected ticker: {0}" -f $selected)
Write-Host ("Force refresh: {0}" -f [bool]$ForceRefresh)
Write-Host "Secrets: not printed"
Write-Host ""

$watchlistUrl = "{0}/api/v1/stocks/vn/watchlist?tickers={1}&include_intraday=true{2}" -f $apiBase, $tickersQuery, $forceSuffix
$companyUrl = "{0}/api/v1/stocks/vn/company/{1}?force_refresh={2}" -f $apiBase, $selectedQuery, ([bool]$ForceRefresh).ToString().ToLowerInvariant()
$observabilityUrl = "{0}/api/v1/stocks/vn/observability" -f $apiBase
$realtimeUrl = "{0}/api/v1/stocks/vn/realtime?tickers={1}" -f $apiBase, $tickersQuery
$tradesUrl = "{0}/api/v1/stocks/vn/realtime/trades?symbol={1}&limit=100" -f $apiBase, $selectedQuery
$indexListUrl = "{0}/api/v1/stocks/vn/index-list?market=HOSE" -f $apiBase
$indexComponentsUrl = "{0}/api/v1/stocks/vn/index-components?index_code=VN30" -f $apiBase

$watchlistResponse = Get-AuditJson $watchlistUrl "GET /api/v1/stocks/vn/watchlist" $true
$companyResponse = Get-AuditJson $companyUrl "GET /api/v1/stocks/vn/company/{ticker}" $true
$observabilityResponse = Get-AuditJson $observabilityUrl "GET /api/v1/stocks/vn/observability" $false
$realtimeResponse = Get-AuditJson $realtimeUrl "GET /api/v1/stocks/vn/realtime" $false
$tradesResponse = Get-AuditJson $tradesUrl "GET /api/v1/stocks/vn/realtime/trades" $false
$indexListResponse = Get-AuditJson $indexListUrl "GET /api/v1/stocks/vn/index-list" $false
$indexComponentsResponse = Get-AuditJson $indexComponentsUrl "GET /api/v1/stocks/vn/index-components" $false

$rows = @(Convert-ToList (Get-Value $watchlistResponse @("watchlist")))
$rowCount = $rows.Count
if ($rowCount -eq 0) {
  throw "Required watchlist response completed but returned no watchlist rows."
}

$dailyRows = Count-Matching $rows { param($row)
  (Has-Value (Get-Value $row @("latest_price_date", "ohlcv_date", "date"))) -and
  (Has-Value (Get-Value $row @("daily_close", "ohlcv_close", "close", "latest_price"))) -and
  (Has-Value (Get-Value $row @("volume"))) -and
  (
    (Test-SourceContains $row @("latest_price_source") "SSI DailyOhlc") -or
    (Test-SourceContains $row @("actual_source", "source", "primary_source") "SSI")
  )
}
$latestCloseRows = Count-Matching $rows { param($row)
  (Has-Value (Get-Value $row @("latest_price"))) -and
  (Test-SourceContains $row @("latest_price_source") "SSI DailyOhlc")
}
$dailyValueRows = Count-Matching $rows { param($row) Has-Value (Get-Value $row @("amount", "value")) }
$volumeRows = Count-Matching $rows { param($row) Has-Value (Get-Value $row @("volume")) }

$dspRows = Count-Matching $rows { param($row)
  $dsp = Get-Value $row @("daily_stock_price", "dailyStockPrice")
  (Get-Status $dsp) -eq "ok"
}
$limitRows = Count-Matching $rows { param($row)
  (Has-Value (Get-Value $row @("ssi_reference_price"))) -and
  (Has-Value (Get-Value $row @("ssi_ceiling_price"))) -and
  (Has-Value (Get-Value $row @("ssi_floor_price")))
}
$matchedRows = Count-Matching $rows { param($row)
  (Has-Value (Get-Value $row @("ssi_matched_volume"))) -and
  (Has-Value (Get-Value $row @("ssi_matched_value")))
}
$foreignVolumeRows = Count-Matching $rows { param($row)
  $foreign = Get-Value $row @("foreign")
  (Has-Value (Get-Value $foreign @("buy"))) -and
  (Has-Value (Get-Value $foreign @("sell"))) -and
  (Has-Value (Get-Value $foreign @("net", "foreign_net_volume"))) -and
  ((Get-Value $foreign @("source")) -match "SSI DailyStockPrice")
}
$foreignValueRows = Count-Matching $rows { param($row)
  $foreign = Get-Value $row @("foreign")
  (Has-Value (Get-Value $foreign @("buy_value"))) -and
  (Has-Value (Get-Value $foreign @("sell_value"))) -and
  (Has-Value (Get-Value $foreign @("net_value"))) -and
  ((Get-Value $foreign @("source")) -match "SSI DailyStockPrice")
}
$indicatorRows = Count-Matching $rows { param($row)
  $indicators = Get-Value $row @("indicators")
  (Has-Value (Get-Value $indicators @("rsi14_wilder", "rsi14"))) -and
  (Has-Value (Get-Value $indicators @("ma20"))) -and
  (Has-Value (Get-Value $indicators @("ma50")))
}
$intradayOkRows = Count-Matching $rows { param($row)
  $status = Get-Status (Get-Value $row @("intraday_status"))
  $candles = @(Convert-ToList (Get-Value $row @("intraday_candles")))
  $pulse = Get-Value $row @("intraday_pulse")
  $dateMatch = Get-Value $row @("date_match")
  ($status -eq "ok") -and ($candles.Count -gt 0) -and ($null -ne $pulse) -and ($dateMatch -eq "matched")
}
$intradayStatusValues = @($rows | ForEach-Object { Get-Status (Get-Value $_ @("intraday_status")) } | Where-Object { $_ })
$intradayPulseRows = Count-Matching $rows { param($row) $null -ne (Get-Value $row @("intraday_pulse")) }
$intradayCandleCounts = @($rows | ForEach-Object { @(Convert-ToList (Get-Value $_ @("intraday_candles"))).Count })
$intradayDateMatches = @($rows | ForEach-Object {
  $status = Get-Value $_ @("intraday_status")
  $value = Get-Value $status @("date_match")
  if (Has-Value $value) { $value } else { Get-Value $_ @("date_match") }
})
$intradayLatestDates = @($rows | ForEach-Object {
  $status = Get-Value $_ @("intraday_status")
  $value = Get-Value $status @("intraday_latest_date")
  if (Has-Value $value) { $value } else { Get-Value $_ @("intraday_latest_date") }
})
$intradayDailyDates = @($rows | ForEach-Object {
  $status = Get-Value $_ @("intraday_status")
  $value = Get-Value $status @("daily_price_date")
  if (Has-Value $value) { $value } else { Get-Value $_ @("daily_price_date", "latest_price_date", "ohlcv_date") }
})
$intradayRequestedTimeframes = @($rows | ForEach-Object {
  $status = Get-Value $_ @("intraday_status")
  $value = Get-Value $status @("intraday_requested_timeframe")
  if (Has-Value $value) { $value } else { Get-Value $_ @("intraday_requested_timeframe", "intraday_timeframe") }
})
$intradayGranularities = @($rows | ForEach-Object {
  $status = Get-Value $_ @("intraday_status")
  $value = Get-Value $status @("intraday_actual_granularity", "intraday_granularity")
  if (Has-Value $value) { $value } else { Get-Value $_ @("intraday_actual_granularity", "intraday_granularity") }
})
$intradayGranularitySeconds = @($rows | ForEach-Object {
  $status = Get-Value $_ @("intraday_status")
  $value = Get-Value $status @("intraday_actual_granularity_seconds", "intraday_granularity_seconds")
  if (Has-Value $value) { $value } else { Get-Value $_ @("intraday_actual_granularity_seconds", "intraday_granularity_seconds") }
})
$intradayMessages = @($rows | ForEach-Object {
  $status = Get-Value $_ @("intraday_status")
  Get-Value $status @("message", "reason")
})
$intradayDiagnostics = @($rows | ForEach-Object {
  $status = Get-Value $_ @("intraday_status")
  $diagnostics = Get-Value $status @("diagnostics")
  if ($null -ne $diagnostics) { $diagnostics } else { $status }
})
$intradayFailureModes = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("failure_class", "failure_mode") })
$intradayHttpStatuses = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("http_status") })
$intradayProviderCodes = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("provider_code", "code") })
$intradayErrorTypes = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("error_type") })
$intradayEndpoints = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("endpoint") })
$intradayPageSizes = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("pageSize", "request_page_size") })
$intradayPublicLimits = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("public_limit") })
$intradayCooldownActive = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("cooldown_active") })
$intradayCooldownRecorded = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("cooldown_recorded") })
$intradayCooldownSeconds = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("cooldown_seconds") })
$intradayCooldownRemaining = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("cooldown_remaining_seconds") })
$intradayCooldownUntil = @($intradayDiagnostics | ForEach-Object { Get-Value $_ @("cooldown_until") })
$intradayTimestamps = @()
foreach ($row in $rows) {
  foreach ($candle in @(Convert-ToList (Get-Value $row @("intraday_candles")))) {
    $value = Get-Value $candle @("date_time", "timestamp")
    if (Has-Value $value) {
      $intradayTimestamps += [string]$value
    }
  }
}
$intradayTimestampRange = "none"
if ($intradayTimestamps.Count -gt 0) {
  $orderedIntradayTimestamps = @($intradayTimestamps | Sort-Object)
  $intradayTimestampRange = "{0} to {1}" -f $orderedIntradayTimestamps[0], $orderedIntradayTimestamps[$orderedIntradayTimestamps.Count - 1]
}
$realtimeOkRows = Count-Matching $rows { param($row)
  ((Get-Status (Get-Value $row @("realtime_status"))) -eq "ok") -and
  ($null -ne (Get-Value $row @("realtime_snapshot")))
}
$realtimeMessages = @($rows | ForEach-Object {
  $status = Get-Value $_ @("realtime_status")
  $diagnostics = Get-Value $status @("diagnostics")
  $message = Get-Value $status @("message", "reason")
  $providerMessage = Get-Value $diagnostics @("provider_message")
  if (Has-Value $providerMessage) { $providerMessage }
  elseif (Has-Value $message) { $message }
})
$tradeTapeOkRows = Count-Matching $rows { param($row)
  $trades = @(Convert-ToList (Get-Value $row @("trade_tape")))
  ((Get-Status (Get-Value $row @("trade_tape_status"))) -eq "ok") -and ($trades.Count -gt 0)
}

$newsStatuses = @($rows | ForEach-Object { Get-Status (Get-Value $_ @("news_status")) } | Where-Object { $_ })

$capabilities = @()

$dailyStatus = if ($dailyRows -eq $rowCount) { "reliable" } elseif ($dailyRows -gt 0) { "partial" } else { "unavailable" }
$capabilities += New-CapabilityRow "Daily OHLCV" $dailyStatus "SSI DailyOhlc" ("{0}/{1} rows include date, close, volume, and SSI daily source evidence" -f $dailyRows, $rowCount) "date, open, high, low, close, daily_close, volume, amount when present" "Reliable means observed for this audit run and input set."

$latestStatus = if ($latestCloseRows -eq $rowCount) { "reliable" } elseif ($latestCloseRows -gt 0) { "partial" } else { "unavailable" }
$capabilities += New-CapabilityRow "Latest daily close" $latestStatus "SSI DailyOhlc" ("{0}/{1} rows expose latest_price with SSI DailyOhlc source" -f $latestCloseRows, $rowCount) "latest_price, latest_price_date, latest_price_source" "Do not infer realtime from this field."

$dailyVolumeStatus = if ($volumeRows -eq $rowCount -and $dailyValueRows -eq $rowCount) { "reliable" } elseif ($volumeRows -gt 0 -or $dailyValueRows -gt 0) { "partial" } else { "unavailable" }
$capabilities += New-CapabilityRow "Daily volume/value" $dailyVolumeStatus "SSI DailyOhlc" ("volume {0}/{1}; value/amount {2}/{1}" -f $volumeRows, $rowCount, $dailyValueRows) "volume; amount/value only when present" "Daily volume is separate from matched volume."

$limitStatus = if ($limitRows -eq $rowCount -and $dspRows -eq $rowCount) { "reliable" } elseif ($limitRows -gt 0 -or $dspRows -gt 0) { "partial" } else { "unavailable" }
$capabilities += New-CapabilityRow "DailyStockPrice reference/ceiling/floor" $limitStatus "SSI DailyStockPrice" ("DailyStockPrice ok {0}/{1}; limits present {2}/{1}" -f $dspRows, $rowCount, $limitRows) "reference_price, ceiling_price, floor_price" "Does not change canonical daily close ownership."

$matchedStatus = if ($matchedRows -eq $rowCount) { "reliable" } elseif ($matchedRows -gt 0) { "partial" } else { "unavailable" }
$capabilities += New-CapabilityRow "Matched volume/value" $matchedStatus "SSI DailyStockPrice" ("{0}/{1} rows include matched_volume and matched_value" -f $matchedRows, $rowCount) "matched_volume, matched_value" "Keep separate from SSI DailyOhlc volume/value."

$foreignVolStatus = if ($foreignVolumeRows -eq $rowCount) { "reliable" } elseif ($foreignVolumeRows -gt 0) { "partial" } else { "unavailable" }
$capabilities += New-CapabilityRow "Foreign buy/sell/net volume" $foreignVolStatus "SSI DailyStockPrice" ("{0}/{1} rows include foreign buy/sell/net volume from SSI DailyStockPrice" -f $foreignVolumeRows, $rowCount) "foreign_buy_volume, foreign_sell_volume, foreign_net_volume" "Null is not zero."

$foreignValueStatus = if ($foreignValueRows -eq $rowCount) { "reliable" } elseif ($foreignValueRows -gt 0) { "partial" } else { "unavailable" }
$capabilities += New-CapabilityRow "Foreign buy/sell/net value" $foreignValueStatus "SSI DailyStockPrice" ("{0}/{1} rows include foreign buy/sell/net value from SSI DailyStockPrice" -f $foreignValueRows, $rowCount) "foreign_buy_value, foreign_sell_value, foreign_net_value" "Use value fields separately from share volume fields."

$indicatorStatus = if ($indicatorRows -eq $rowCount) { "reliable" } elseif ($indicatorRows -gt 0) { "partial" } else { "unavailable" }
$capabilities += New-CapabilityRow "Technical indicators derived from daily OHLCV" $indicatorStatus "derived from SSI DailyOhlc" ("{0}/{1} rows include RSI14 and MA20/MA50" -f $indicatorRows, $rowCount) "rsi14, ma20, ma50, Bollinger when present, volume ratio" "RSI14 remains Wilder/RMA."

$intradayUsableRatio = "{0}/{1}" -f $intradayOkRows, $rowCount
$intradayStatus = if ($intradayOkRows -eq $rowCount) { "reliable" } elseif ($intradayOkRows -gt 0) { "partial" } elseif ($intradayStatusValues -contains "disabled") { "disabled" } elseif ($intradayStatusValues -contains "unavailable") { "unavailable" } else { "unknown-needs-verification" }
$intradayEvidence = "usable current pulse rows {0}/{1}; pulse rows {2}/{1}; public candle counts {3}; statuses {4}; date_match {5}; intraday_latest_date {6}; daily_price_date {7}; requested_timeframe {8}; observed_granularity {9}; observed_granularity_seconds {10}; timestamp_range {11}; failure_mode {12}; http_status {13}; provider_code {14}; error_type {15}; endpoint {16}; cooldown_active {17}; cooldown_remaining_seconds {18}; messages {19}" -f `
  $intradayOkRows,
  $rowCount,
  $intradayPulseRows,
  (Format-UniqueValues $intradayCandleCounts),
  (Format-UniqueValues $intradayStatusValues),
  (Format-UniqueValues $intradayDateMatches),
  (Format-UniqueValues $intradayLatestDates),
  (Format-UniqueValues $intradayDailyDates),
  (Format-UniqueValues $intradayRequestedTimeframes),
  (Format-UniqueValues $intradayGranularities),
  (Format-UniqueValues $intradayGranularitySeconds),
  $intradayTimestampRange,
  (Format-UniqueValues $intradayFailureModes),
  (Format-UniqueValues $intradayHttpStatuses),
  (Format-UniqueValues $intradayProviderCodes),
  (Format-UniqueValues $intradayErrorTypes),
  (Format-UniqueValues $intradayEndpoints),
  (Format-UniqueValues $intradayCooldownActive),
  (Format-UniqueValues $intradayCooldownRemaining),
  (Format-UniqueValues $intradayMessages)
$capabilities += New-CapabilityRow "Intraday OHLCV / intraday pulse" $intradayStatus "SSI IntradayOhlc" $intradayEvidence "intraday_candles, intraday_pulse only when status ok and date matched" "Evidence is from current API response fields; public candles stay empty when stale or mismatched."

$realtimeEndpointStatus = Get-OptionalStatusFromEndpoint $realtimeResponse "quotes"
$realtimeStatus = if ($realtimeEndpointStatus -eq "reliable" -and $realtimeOkRows -gt 0) { "reliable" } elseif ($realtimeEndpointStatus -eq "disabled") { "disabled" } elseif ($realtimeOkRows -gt 0) { "partial" } elseif ($realtimeEndpointStatus -eq "unavailable") { "unavailable" } else { "unknown-needs-verification" }
$realtimeQuoteCount = @(Convert-ToList (Get-Value $realtimeResponse @("quotes"))).Count
$realtimeEndpointDetail = Get-Value $realtimeResponse @("error_detail", "error")
if (-not (Has-Value $realtimeEndpointDetail)) {
  $realtimeEndpointDetail = "none"
}
$realtimeEndpointDiagnostics = Get-Value $realtimeResponse @("diagnostics")
$realtimeStreamingStatus = Get-Value $realtimeResponse @("streaming_status")
if (-not (Has-Value $realtimeStreamingStatus)) {
  $realtimeStreamingStatus = Get-Value $realtimeEndpointDiagnostics @("streaming_status")
}
$realtimeManagerState = Get-Value $realtimeResponse @("manager_state")
if (-not (Has-Value $realtimeManagerState)) {
  $realtimeManagerState = Get-Value $realtimeEndpointDiagnostics @("manager_state")
}
$realtimeCacheStatus = Get-Value $realtimeResponse @("cache_status")
if (-not (Has-Value $realtimeCacheStatus)) {
  $realtimeCacheStatus = Get-Value $realtimeEndpointDiagnostics @("cache_status")
}
$realtimeLiveAdapterStatus = Get-Value $realtimeEndpointDiagnostics @("live_adapter_status")
$realtimeParsedStreamingRows = Get-Value $realtimeResponse @("parsed_streaming_rows")
if (-not (Has-Value $realtimeParsedStreamingRows)) {
  $realtimeParsedStreamingRows = Get-Value $realtimeEndpointDiagnostics @("parser_rows_observed")
}
if (-not (Has-Value $realtimeParsedStreamingRows)) {
  $realtimeParsedStreamingRows = $realtimeQuoteCount
}
$realtimeClassificationDetail = "{0}; watchlist_messages={1}" -f $realtimeEndpointDetail, (Format-UniqueValues $realtimeMessages)
$realtimeFailureMode = "unknown-needs-verification"
if ($realtimeQuoteCount -gt 0 -or $realtimeOkRows -gt 0) {
  $realtimeFailureMode = if ($realtimeStreamingStatus -eq "cache_hit") { "streaming_cache_hit" } else { "streaming_parsed_rows" }
} elseif ($realtimeStreamingStatus -eq "disabled" -or $realtimeManagerState -eq "disabled" -or $realtimeClassificationDetail -match "streaming realtime manager disabled") {
  $realtimeFailureMode = "streaming_disabled"
} elseif ($realtimeStreamingStatus -eq "manager_not_started" -or $realtimeClassificationDetail -match "manager not started") {
  $realtimeFailureMode = "streaming_manager_not_started"
} elseif ($realtimeStreamingStatus -eq "cache_empty" -or $realtimeClassificationDetail -match "cache empty") {
  $realtimeFailureMode = "streaming_cache_empty"
} elseif ($realtimeStreamingStatus -eq "cache_stale" -or $realtimeClassificationDetail -match "cache stale") {
  $realtimeFailureMode = "streaming_cache_stale"
} elseif ($realtimeStreamingStatus -eq "manager_error" -or $realtimeManagerState -eq "errored") {
  $realtimeFailureMode = "streaming_manager_error"
} elseif ($realtimeLiveAdapterStatus -eq "not_enabled" -and $realtimeClassificationDetail -match "live adapter") {
  $realtimeFailureMode = "live_adapter_not_enabled"
} elseif ($realtimeClassificationDetail -match "streaming adapter|connection semantics not implemented") {
  $realtimeFailureMode = "streaming_adapter_not_implemented"
} elseif ($realtimeClassificationDetail -match "no streaming message") {
  $realtimeFailureMode = "streaming_no_message"
} elseif ($realtimeClassificationDetail -match "REST|endpoint not identified|unsupported realtime endpoint|RealtimeQuote|RealtimePrice|RealtimeSnapshot|SecuritiesRealtime") {
  $realtimeFailureMode = "rest_unsupported"
} elseif ($realtimeEndpointStatus -eq "disabled") {
  $realtimeFailureMode = "disabled"
} elseif ($realtimeEndpointStatus -eq "unavailable") {
  $realtimeFailureMode = "unavailable"
}
$capabilities += New-CapabilityRow "Realtime snapshot" $realtimeStatus "SSI realtime contract" ("endpoint status={0}; endpoint quote rows={1}; watchlist usable snapshots={2}/{3}; failure_mode={4}; streaming_status={5}; manager_state={6}; cache_status={7}; parsed_streaming_rows={8}; live_adapter={9}" -f (Get-Status $realtimeResponse), $realtimeQuoteCount, $realtimeOkRows, $rowCount, $realtimeFailureMode, (Format-ScalarValue $realtimeStreamingStatus), (Format-ScalarValue $realtimeManagerState), (Format-ScalarValue $realtimeCacheStatus), $realtimeParsedStreamingRows, (Format-ScalarValue $realtimeLiveAdapterStatus)) "realtime_snapshot fields only when status ok and snapshot is non-null" "Do not use realtime snapshot as official daily close."

$tradeEndpointStatus = Get-OptionalStatusFromEndpoint $tradesResponse "trades"
$tradeStatus = if ($tradeEndpointStatus -eq "reliable" -and $tradeTapeOkRows -gt 0) { "reliable" } elseif ($tradeEndpointStatus -eq "disabled") { "disabled" } elseif ($tradeTapeOkRows -gt 0) { "partial" } elseif ($tradeEndpointStatus -eq "unavailable") { "unavailable" } else { "unknown-needs-verification" }
$tradeCount = @(Convert-ToList (Get-Value $tradesResponse @("trades"))).Count
$capabilities += New-CapabilityRow "Trade tape" $tradeStatus "SSI trade-tape contract" ("endpoint status={0}; endpoint trade rows={1}; watchlist usable trade rows={2}/{3}" -f (Get-Status $tradesResponse), $tradeCount, $tradeTapeOkRows, $rowCount) "trade_tape rows only when status ok and rows exist" "Do not use trade tape as official daily close."

$indexListRows = @(Convert-ToList (Get-Value $indexListResponse @("rows"))).Count
$indexComponentRows = @(Convert-ToList (Get-Value $indexComponentsResponse @("rows"))).Count
$indexStatus = if ((Get-Status $indexListResponse) -eq "ok" -and $indexListRows -gt 0 -and (Get-Status $indexComponentsResponse) -eq "ok" -and $indexComponentRows -gt 0) { "reliable" } elseif ((Get-Status $indexListResponse) -eq "ok" -and $indexListRows -gt 0) { "partial" } elseif ((Get-Status $indexListResponse) -eq "disabled" -or (Get-Status $indexComponentsResponse) -eq "disabled") { "disabled" } elseif ((Get-Status $indexListResponse) -eq "unavailable" -or (Get-Status $indexComponentsResponse) -eq "unavailable") { "unavailable" } else { "unknown-needs-verification" }
$capabilities += New-CapabilityRow "Index data / index components" $indexStatus "SSI IndexList / SSI IndexComponents" ("index-list status={0}, rows={1}; VN30 components status={2}, rows={3}" -f (Get-Status $indexListResponse), $indexListRows, (Get-Status $indexComponentsResponse), $indexComponentRows) "index identifiers and component rows when returned" "Use SSI-returned identifiers; do not hardcode components."

$profile = Get-Value $companyResponse @("profile")
$profileStatusRaw = Get-Status $profile
$profileFields = 0
foreach ($field in @("name", "exchange", "industry")) {
  if (Has-Value (Get-Value $profile @($field))) {
    $profileFields += 1
  }
}
$profileStatus = if ($profileStatusRaw -eq "ok" -and $profileFields -ge 3) { "reliable" } elseif ($profileStatusRaw -eq "ok" -or $profileFields -gt 0) { "partial" } elseif ($profileStatusRaw -eq "missing") { "partial" } elseif ($profileStatusRaw -eq "unavailable") { "unavailable" } else { "unknown-needs-verification" }
$capabilities += New-CapabilityRow "Profile / securities metadata" $profileStatus "SSI Securities / SSI SecuritiesDetails" ("company profile status={0}; name/exchange/industry fields present={1}/3" -f $profileStatusRaw, $profileFields) "ticker, name, exchange, industry only when present" "Profile can be partial even when SSI metadata status is ok."

$newsStatus = if ($newsStatuses -contains "ok") { "partial" } elseif ($newsStatuses -contains "disabled") { "disabled" } else { "future-provider" }
$capabilities += New-CapabilityRow "News" $newsStatus "NewsProvider future" ("watchlist news statuses: {0}; company news status={1}" -f (($newsStatuses | Select-Object -Unique) -join ","), (Get-Status (Get-Value $companyResponse @("news")))) "news rows only after separate provider exists" "Current VN runtime must not use Mozyfin news fallback."

$financials = Get-Value $companyResponse @("financials")
$capabilities += New-CapabilityRow "Financials" "future-provider" "external provider future" ("company financials status={0}" -f (Get-Status $financials)) "none yet" "Requires a separate future provider contract."

$events = Get-Value $companyResponse @("events")
$capabilities += New-CapabilityRow "Corporate actions / dividends" "future-provider" "external provider future" ("company events status={0}; no explicit dividend/corporate-action provider observed" -f (Get-Status $events)) "none yet" "Do not infer dividends or corporate actions from price gaps."

$capabilities += New-CapabilityRow "Macro/events" "future-provider" "external provider future" "no macro provider block in current dashboard/company responses" "none yet" "Requires a separate future provider contract."

Write-Host "Endpoints called:"
foreach ($endpoint in ($script:EndpointsCalled | Select-Object -Unique)) {
  Write-Host ("- {0}" -f $endpoint)
}
Write-Host ""

Write-Host "Capability summary:"
$capabilities | Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "Intraday evidence:"
Write-Host ("- Statuses: {0}" -f (Format-UniqueValues $intradayStatusValues))
Write-Host ("- Usable current pulse rows: {0}/{1}" -f $intradayOkRows, $rowCount)
Write-Host ("- Public candle counts: {0}" -f (Format-UniqueValues $intradayCandleCounts))
Write-Host ("- Public timestamp range: {0}" -f $intradayTimestampRange)
Write-Host ("- Date match: {0}" -f (Format-UniqueValues $intradayDateMatches))
Write-Host ("- Intraday latest date: {0}" -f (Format-UniqueValues $intradayLatestDates))
Write-Host ("- Daily price date: {0}" -f (Format-UniqueValues $intradayDailyDates))
Write-Host ("- Requested timeframe: {0}" -f (Format-UniqueValues $intradayRequestedTimeframes))
Write-Host ("- Observed granularity: {0} ({1} seconds)" -f (Format-UniqueValues $intradayGranularities), (Format-UniqueValues $intradayGranularitySeconds))
Write-Host ("- Failure mode: {0}" -f (Format-UniqueValues $intradayFailureModes))
Write-Host ("- HTTP status: {0}" -f (Format-UniqueValues $intradayHttpStatuses))
Write-Host ("- Provider code: {0}" -f (Format-UniqueValues $intradayProviderCodes))
Write-Host ("- Error type: {0}" -f (Format-UniqueValues $intradayErrorTypes))
Write-Host ("- Endpoint: {0}" -f (Format-UniqueValues $intradayEndpoints))
Write-Host ("- Request page size: {0}" -f (Format-UniqueValues $intradayPageSizes))
Write-Host ("- Public limit: {0}" -f (Format-UniqueValues $intradayPublicLimits))
Write-Host ("- Cooldown active: {0}" -f (Format-UniqueValues $intradayCooldownActive))
Write-Host ("- Cooldown recorded: {0}" -f (Format-UniqueValues $intradayCooldownRecorded))
Write-Host ("- Cooldown seconds: {0}" -f (Format-UniqueValues $intradayCooldownSeconds))
Write-Host ("- Cooldown remaining seconds: {0}" -f (Format-UniqueValues $intradayCooldownRemaining))
Write-Host ("- Cooldown until: {0}" -f (Format-UniqueValues $intradayCooldownUntil))
Write-Host ("- Reason: {0}" -f (Format-UniqueValues $intradayMessages))
Write-Host "- Evidence source: current app API response fields; SSI is not called directly by this script."

Write-Host ""
Write-Host "Realtime evidence:"
Write-Host ("- Realtime endpoint status: {0}" -f (Get-Status $realtimeResponse))
Write-Host ("- Endpoint quote row count: {0}" -f $realtimeQuoteCount)
Write-Host ("- Parsed streaming row count: {0}" -f $realtimeParsedStreamingRows)
Write-Host ("- Watchlist usable snapshot ratio: {0}/{1}" -f $realtimeOkRows, $rowCount)
Write-Host ("- Failure mode: {0}" -f $realtimeFailureMode)
Write-Host ("- Streaming status: {0}" -f (Format-ScalarValue $realtimeStreamingStatus))
Write-Host ("- Manager state: {0}" -f (Format-ScalarValue $realtimeManagerState))
Write-Host ("- Cache status: {0}" -f (Format-ScalarValue $realtimeCacheStatus))
Write-Host ("- Live adapter: {0}" -f (Format-ScalarValue $realtimeLiveAdapterStatus))
Write-Host ("- Endpoint detail: {0}" -f $realtimeEndpointDetail)
Write-Host ("- Watchlist detail: {0}" -f (Format-UniqueValues $realtimeMessages))
Write-Host "- Evidence source: current app API response fields; SSI is not called directly by this script."

Write-Host ""
Write-Host "Observed reliable domains for this audit run:"
@($capabilities | Where-Object { $_.Status -eq "reliable" } | ForEach-Object {
  if ($_.Domain -eq "Intraday OHLCV / intraday pulse") {
    "- {0}: {1} usable current pulse rows" -f $_.Domain, $intradayUsableRatio
  } else {
    "- {0}" -f $_.Domain
  }
}) | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Partial/unavailable/disabled domains:"
@($capabilities | Where-Object { $_.Status -in @("partial", "unavailable", "disabled", "unknown-needs-verification") } | ForEach-Object {
  if ($_.Domain -eq "Intraday OHLCV / intraday pulse") {
    "- {0}: {1} ({2} usable current pulse rows)" -f $_.Domain, $_.Status, $intradayUsableRatio
  } else {
    "- {0}: {1}" -f $_.Domain, $_.Status
  }
}) | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Future-provider domains:"
@($capabilities | Where-Object { $_.Status -eq "future-provider" } | ForEach-Object { "- {0}" -f $_.Domain }) | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "Audit completed. Optional unavailable, disabled, partial, and future-provider domains are reported without failing the script."
exit 0
