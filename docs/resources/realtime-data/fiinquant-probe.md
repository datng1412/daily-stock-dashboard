# FiinQuantX Realtime Probe

This note describes a standalone probe for evaluating whether a FiinQuantX account can provide realtime Vietnam quote fields for selected tickers.

The probe is not integrated into the application. It must not change Mozyfin behavior, daily OHLCV semantics, or dashboard `latest_price` semantics.

## Install

```powershell
.\.venv\Scripts\python.exe -m pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

The installed package may expose the Python module as `FiinQuantX`. If import fails with a missing transitive dependency, install that dependency into the same venv and rerun the probe. For example, some package versions may require `matplotlib` even though the probe does not use charts.

## Environment

Required:

```powershell
$env:FIINQUANT_USERNAME = "<username>"
$env:FIINQUANT_PASSWORD = "<password>"
```

Optional:

```powershell
$env:FIINQUANT_TICKERS = "FPT,HPG,VNINDEX"
$env:FIINQUANT_PROBE_SECONDS = "60"
$env:FIINQUANT_PROBE_CSV = ""
```

Do not print or commit credentials. The script reports missing credential variables by name only.

## Run

```powershell
.\.venv\Scripts\python.exe scripts\probe_fiinquant_realtime.py
```

Stop early with `Ctrl+C`.

## Expected Fields To Inspect

The first payload should print available column names. Inspect whether the payload includes:

- `Ticker`
- `TradingDate`
- `Reference`
- `Open`
- `Close`
- `High`
- `Low`
- `Change`
- `ChangePercent`
- `MatchVolume`
- `MatchValue`
- `TotalMatchVolume`
- `TotalMatchValue`
- `ForeignBuyVolumeTotal`
- `ForeignSellVolumeTotal`
- `ForeignBuyValueTotal`
- `ForeignSellValueTotal`

For realtime architecture planning, the key questions are:

- Is `Close` the latest matched price, or an end-of-day/delayed field?
- Does `TradingDate` include enough timestamp precision for freshness checks?
- Are `MatchVolume` and `MatchValue` per-match fields or latest-session cumulative fields?
- Are `TotalMatchVolume` and `TotalMatchValue` session cumulative fields?
- Does the account return realtime data, delayed data, or no stream data for the selected tickers?

## Semantic Guardrails

- FiinQuant realtime matched price must remain separate from Mozyfin daily OHLCV close.
- Realtime matched price must not replace `latest_price`.
- Daily OHLCV close must never be labeled realtime.
- Any future dashboard display must show source, timestamp, and realtime/delayed/stale status.
- This probe must not be used for scraping, public redistribution, or unofficial endpoints.
