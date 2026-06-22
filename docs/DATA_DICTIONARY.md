# Data Dictionary

| Field | Meaning | Source | Unit | Nullable | Canonical | Caveat |
|---|---|---|---|---|---|---|
| latest_price | Canonical dashboard daily price | SSI DailyOhlc close | VND | yes | yes | May differ from DailyStockPrice close |
| daily_stock_price.close | SSI DailyStockPrice close | SSI DailyStockPrice | VND | yes | no/pending | Used for reference detail |
| volume | DailyOhlc volume | SSI DailyOhlc | shares | yes | yes | May differ from matched_volume |
| matched_volume | Matched volume | SSI DailyStockPrice | shares | yes | no | Source-specific |
| realtime_snapshot | Realtime quote object | SSI realtime | mixed | yes | no | null if unavailable |
| trade_tape | Trade rows | SSI trade tape | list | yes | no | [] if unavailable |