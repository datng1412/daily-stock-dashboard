# Trading strategies

The inherited Ask-Stock agent loads the bundled strategy definitions from this directory. The product calls these strategies. Code, configuration, and API fields use the term `skill`.

Add a YAML file with a unique `name` and describe the strategy in the appropriate language for its users. A strategy can specify a category, core rules, required tool names, aliases, and default routing metadata.

```yaml
name: my_strategy
display_name: My Strategy
description: Inspect trend and trading volume.
category: trend
core_rules: [2, 3]
required_tools: [get_daily_history, analyze_trend]
aliases: [my trend check]
default_active: false
default_router: false
default_priority: 100
market_regimes: [trending_up]
instructions: |
  Explain the observed moving-average structure and volume evidence.
  Identify missing inputs and state the conditions that would change the interpretation.
```

Categories include `trend`, `pattern`, `reversal`, and `framework`. Smaller `default_priority` values sort first. Inspect the [loader](../src/agent/skills/base.py) and the bundled YAML for the executable metadata and examples.

Set `AGENT_SKILL_DIR` to an additional directory to load custom definitions. A custom definition with the same name overrides the bundled definition. This strategy system is separate from StockClock's repository collaboration skills and VN dashboard indicators.
