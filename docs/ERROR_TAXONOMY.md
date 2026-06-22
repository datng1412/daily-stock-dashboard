# Error and Status Taxonomy

## ok

Provider returned usable data.

## unavailable

Provider is enabled but usable data is not available.

Examples:
- endpoint 404
- empty response
- stale intraday
- permission unavailable

## disabled

Feature/provider intentionally disabled.

Examples:
- news disabled
- Mozyfin disabled

## partial

Provider responded but key optional fields are missing.

Example:
- profile endpoint ok but company name/industry missing

## stale

Data exists but is not current enough to use.

## mismatched

Two sources disagree for same ticker/date.

## insufficient_history

Not enough rows to compute rolling fields.