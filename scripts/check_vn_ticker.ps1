param(
  [string]$Ticker = "FPT",
  [string]$ApiBase = "http://127.0.0.1:8000",
  [switch]$ForceRefresh
)

$ErrorActionPreference = "Stop"

$force = if ($ForceRefresh) { "true" } else { "false" }
$url = "$ApiBase/api/v1/stocks/vn/watchlist?tickers=$Ticker&force_refresh=$force"

Write-Host "Checking: $url"
Write-Host ""

$r = Invoke-RestMethod $url
$rows = if ($r.watchlist) { $r.watchlist } elseif ($r.items) { $r.items } else { @() }

if (-not $rows -or $rows.Count -eq 0) {
  throw "No watchlist rows returned."
}

$item = $rows | Select-Object -First 1

$newsCount = if ($null -ne $item.news) { $item.news.Count } else { 0 }
$newsError = if ($item.cache_errors.news) { $item.cache_errors.news } else { "" }
$intradayError = if ($item.cache_errors.intraday_ohlcv) { $item.cache_errors.intraday_ohlcv } else { "" }

Write-Host "===== DATA SUMMARY: $Ticker ====="

[PSCustomObject]@{
  ticker = $item.ticker
  status = $item.status
  source = $item.source
  actual_source = $item.actual_source
  fallback_used = $item.fallback_used
  daily_close = $item.daily_close
  ohlcv_close = $item.ohlcv_close
  latest_price = $item.latest_price
  price_date = $item.price_date
  reference_source = $item.reference_source
  foreign_flow_source = $item.foreign_flow_source
  news_count = $newsCount
  news_cache = $item.cache_status.news_cache
  news_error = $newsError
  intraday_cache = $item.cache_status.intraday_cache
  intraday_error_present = [bool]$intradayError
} | Format-List

Write-Host "===== DAILY STOCK PRICE ====="
$item.daily_stock_price | ConvertTo-Json -Depth 8

Write-Host "===== CACHE STATUS ====="
$item.cache_status | ConvertTo-Json -Depth 8

Write-Host "===== CACHE ERRORS ====="
$item.cache_errors | ConvertTo-Json -Depth 8

Write-Host "===== NEWS ====="
if ($newsCount -gt 0) {
  $item.news | Select-Object -First 5 title,source,published_at,url | Format-List
} else {
  Write-Host "NO NEWS RETURNED"
}