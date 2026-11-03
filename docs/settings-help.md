# Settings help

The [backend configuration registry](../src/core/config_registry.py) supplies `help_key`, `examples`, `docs`, and `warning_codes`. The [frontend localization](../apps/dsa-web/src/locales/settingsHelp.ts) owns short and long user-facing help. Keep supported UI languages semantically aligned and use placeholders for sensitive values.

## Scope

- The settings page edits registered fields. Unregistered keys can remain in `.env` and configuration backups.
- The `LLM_CHANNELS` editor reads and writes dynamic channel keys. Its `settings.llm_channel.*` entries describe editor fields and do not each represent an environment variable.
- Check [.env.example](../.env.example), the registry, and executable validation for defaults and effective behavior. Link to the English [LLM guide](LLM_CONFIG_GUIDE_EN.md), [notification guide](notifications.md), or [deployment guide](DEPLOY_EN.md) for details.

## Applying changes

Saving updates `.env` and reloadable settings. Changing `WEBUI_HOST` or `WEBUI_PORT` requires a process restart. `RUN_IMMEDIATELY` applies at startup. Changing `SCHEDULE_ENABLED` or `SCHEDULE_RUN_IMMEDIATELY` requires restarting the scheduler in its intended mode. An already-running scheduler checks for `SCHEDULE_TIME` changes and rebuilds the daily job. Saving that field in web-only mode does not create a scheduler.
