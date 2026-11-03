---
name: market-data-integrity
description: Review StockClock VN market-data changes or regressions that affect SSI source lineage, OHLCV, missing values, freshness, finality, coverage, anomalies, or provider ownership. Applies to changes in normalization, caching, consumers, or user-visible data claims.
---

# StockClock market-data integrity

Use [repository rules](../../../AGENTS.md), the current [VN data contract](../../../docs/VN_DATA_CONTRACT.md), [field dictionary](../../../docs/DATA_DICTIONARY.md), and [validation strategy](../../../docs/TEST_STRATEGY.md). Confirm the applicable contract against current code and tests.

1. Trace one affected output through provider operation and response identity, normalization, service and cache, and each affected API, UI, persistence, or alert consumer. Record the expected source, units, symbol or universe, provider session/time, finality, and availability at each boundary. Trace the failure/degradation path too.
2. Select the checks that distinguish the affected contracts.

   - For daily price and OHLCV, check canonical DailyOhlc lineage, valid candle shape and units, session ordering, and indicator inputs. If the existing newer-DailyStockPrice path applies, verify that its output remains explicitly partial.
   - For intraday and streaming, check sparse delayed bar semantics independently of quotes/trades. Compare provider time and session against receipt and cache age. Trace connection creation and recovery back to the shared lifecycle.
   - For flow, aggregates, and alerts, trace completed DailyStockPrice separately from provisional ForeignRoomMessage. Check null versus explicit zero, anomaly exclusion, SSI membership and the actual denominator, required windows or exact-session alignment, and finality at persistence and alert boundaries.

3. Find the closest deterministic cases in the touched services and consumers. Compare representative accepted, missing/partial, and stale or wrong-session inputs where applicable. Use sanitized injected data for offline checks. Run a bounded live check only within separately authorized acceptance scope.
4. Return findings with file/line, affected output, expected versus observed behavior, and the case that exposes it. List checks run and separate deterministic, dated live, and pending evidence. Route any confirmed documentation change through the subject owner in the [documentation map](../../../docs/DOCS_INDEX.md).
