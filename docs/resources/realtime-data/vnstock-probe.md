# vnstock KBS Realtime Probe

This note describes a standalone probe for checking whether vnstock KBS can return realtime or snapshot quote data for Vietnam tickers in the local environment.

The probe is not integrated into the application. It must not change Mozyfin behavior, daily OHLCV semantics, or dashboard `latest_price` semantics.

## Install

```powershell
.\.venv\Scripts\python.exe -m pip install -U vnstock
```

## Environment

Optional:

```powershell
$env:VNSTOCK_TICKERS = "FPT,ACB,VCB"
```

If unset, the probe uses `FPT,ACB,VCB`.

## Run

```powershell
.\.venv\Scripts\python.exe scripts\probe_vnstock_realtime.py
```

The probe checks:

- `Trading(source="KBS").price_board([...])`
- `Market().equity(symbol).quote()`
- `Market().equity(symbol).trades()`

Each method is isolated. If one method is unavailable or fails, the probe prints a compact method error and continues.

## Semantic Guardrails

- vnstock realtime or snapshot quote values must remain separate from Mozyfin daily OHLCV close.
- vnstock realtime or snapshot quote values must not replace dashboard `latest_price`.
- Daily OHLCV close must never be labeled realtime.
- Any future dashboard display must show source, timestamp, and realtime/delayed/stale status.
- Check vnstock and upstream data license/usage terms before public deployment.
- This probe must not be used for scraping, public redistribution, or unofficial endpoint abuse.
