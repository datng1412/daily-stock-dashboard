# StockClock

StockClock is a personal research workspace for Vietnam equities. Use it to scan a watchlist, inspect SSI market data and foreign flow, compare market participation and relative performance, and configure completed-session alerts.

The repository also includes the inherited A-share, Hong Kong, and US analysis, portfolio, backtesting, bot, and notification workflows. Those workflows have separate configuration and data sources.

## Quick start

For the Vietnam workspace, install the Python and web dependencies from the repository root.

```bash
python -m pip install -r requirements.txt
cd apps/dsa-web
npm ci
npm run build
cd ../..
```

Set `MARKET=VN`, configure SSI V3 through your local secret environment, and follow the [Vietnam runbook](docs/RUNBOOK_VN.md#live-ssi-mode) for enablement and provider settings. Then run `python main.py --serve-only` and open `http://127.0.0.1:8000/vietnam`. The [Docker and Render runbook](docs/RUNBOOK_DOCKER_RENDER.md) covers hosted operation.

For inherited analysis and automation, use the [configuration guide](docs/full-guide_EN.md) and [deployment guide](docs/DEPLOY_EN.md), including their GitHub Actions, local, and Docker entry points.

## Documentation

| Topic | Start here |
| --- | --- |
| Navigation and ownership | [Documentation index](docs/DOCS_INDEX.md) |
| Product and architecture | [PRD](docs/PRD.md) and [Architecture](docs/ARCHITECTURE.md) |
| Status and priorities | [Project State](docs/PROJECT_STATE.md) and [Vietnam roadmap](docs/VN_DASHBOARD_ROADMAP.md) |
| APIs and market-data semantics | [API catalog](docs/API_CATALOG.md) and [VN data contract](docs/VN_DATA_CONTRACT.md) |
| Contributing | [Contributing guide](docs/CONTRIBUTING_EN.md) and [AI development rules](AGENTS.md) |

## Sponsors

<div align="center">
  <p align="center">
    <a href="https://open.anspire.cn/?share_code=QFBC0FYC" target="_blank"><img src="docs/assets/anspire.png" alt="Anspire Open all-in-one model and search service" width="300" height="141" style="width: 300px; height: 141px; object-fit: contain;"></a>
    <a href="https://serpapi.com/baidu-search-api?utm_source=github_daily_stock_analysis" target="_blank"><img src="docs/assets/serpapi_banner_en.png" alt="Easily scrape real-time financial news data from search engines - SerpApi" width="300" height="141" style="width: 300px; height: 141px; object-fit: contain;"></a>
  </p>
</div>

## License and use

[MIT License](LICENSE). StockClock is for research and information. Review the source, session, and coverage before drawing conclusions from any metric.
