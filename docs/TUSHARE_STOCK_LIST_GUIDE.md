# Tushare stock-list tools

This workflow maintains the inherited A-share, Hong Kong, and US symbol lists. Set `TUSHARE_TOKEN` through the local secret environment and use [the fetch script](../scripts/fetch_tushare_stock_list.py) from the repository root.

```bash
python scripts/fetch_tushare_stock_list.py
python scripts/fetch_tushare_stock_list.py --a-rk
```

The script writes per-market CSV files and a generated data README under `data/`. A-shares use `stock_basic`, Hong Kong uses `hk_basic`, and the US list uses paged `us_basic`. The optional `--a-rk` pass uses `rt_k` to correct selected A-share display names with XD, XR, DR, N, or C prefixes. Check the provider entitlement and request limits for the selected interfaces. A failure for one market is reported separately.

To fetch lists and rebuild the index, use `python scripts/refresh_stock_index.py`. For existing CSVs, run `python scripts/generate_index_from_csv.py --test` before rebuilding with `python scripts/generate_index_from_csv.py`. Pinyin generation requires `pypinyin` from the standard requirements.

The application can refresh its bundled autocomplete index through `STOCK_INDEX_REMOTE_UPDATE_ENABLED`. Failed remote refresh retains a valid cached index or the bundled index. The Web UI still reads the local `/stocks.index.json` and supports manual ticker entry. See [.env.example](../.env.example) for configuration and the [index refresh script](../scripts/refresh_stock_index.py) for maintenance steps.
