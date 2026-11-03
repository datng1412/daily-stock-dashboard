# Notifications

This guide covers static notification channels, routing, configuration checks, and failure handling in the inherited application. See the [VN alert contract](VN_DATA_CONTRACT.md#vn-alert-1-completed-session-rule-contract) for VN rule inputs, finality, and deduplication.

## Channel configuration

Set the required keys for at least one channel. Advanced keys tune behavior for a channel that is already enabled. Configure secrets through the local or deployment secret environment.

| Channel | Required keys | Additional configuration |
| --- | --- | --- |
| WeChat Work | `WECHAT_WEBHOOK_URL` | `WECHAT_MSG_TYPE` |
| Feishu webhook | `FEISHU_WEBHOOK_URL` | `FEISHU_WEBHOOK_SECRET` and `FEISHU_WEBHOOK_KEYWORD` as required by the bot. App credentials configure a separate integration. |
| Telegram | `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` | `TELEGRAM_MESSAGE_THREAD_ID` |
| Email | `EMAIL_SENDER` and `EMAIL_PASSWORD` | `EMAIL_RECEIVERS` defaults to the sender when empty. `EMAIL_SENDER_NAME` sets the display name. |
| Pushover | `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN` | |
| ntfy | `NTFY_URL` | Use a full topic URL. `NTFY_TOKEN` is optional. |
| Gotify | `GOTIFY_URL` and `GOTIFY_TOKEN` | Use the server base URL, optionally with a proxy prefix. The sender appends `/message` and uses the `X-Gotify-Key` header. |
| PushPlus | `PUSHPLUS_TOKEN` | `PUSHPLUS_TOPIC` |
| ServerChan3 | `SERVERCHAN3_SENDKEY` | |
| Custom webhook | `CUSTOM_WEBHOOK_URLS` | Comma-separated endpoints. Optional `CUSTOM_WEBHOOK_BEARER_TOKEN` and `CUSTOM_WEBHOOK_BODY_TEMPLATE`. |
| Discord | `DISCORD_WEBHOOK_URL` or `DISCORD_BOT_TOKEN` and `DISCORD_MAIN_CHANNEL_ID` | `DISCORD_INTERACTIONS_PUBLIC_KEY` supports interactions. |
| Slack | `SLACK_WEBHOOK_URL` or `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` | Bot mode takes precedence for sending text and images together. |
| AstrBot | `ASTRBOT_URL` | Optional `ASTRBOT_TOKEN`. |

`WEBHOOK_VERIFY_SSL` controls certificate verification in the senders that read it. Keep verification enabled on public endpoints. DingTalk, Feishu, and Telegram interactive replies can use the originating conversation context. The `UNKNOWN` enum is an internal fallback.

## Routing and delivery

- `NOTIFICATION_REPORT_CHANNELS` covers reports and related delivery. `NOTIFICATION_ALERT_CHANNELS` covers alerts. `NOTIFICATION_SYSTEM_ERROR_CHANNELS` is reserved for system-error routing.
- With an empty route, delivery targets all enabled static channels. An explicit route targets only its intersection with enabled channels. An empty intersection sends nothing.
- Conversation replies remain separate from static routing and noise controls. An interactive command with a source context replies there. Scheduled, CLI, API, and context-free work uses static report routing.
- Routing precedes Markdown-to-image conversion. Merged email requires email in the selected route. The aggregate report loop isolates failures by channel and email recipient group.
- `REPORT_SHOW_LLM_MODEL` controls the report footer. Model and route settings are owned by the [LLM guide](LLM_CONFIG_GUIDE_EN.md).

## Custom webhook templates

`CUSTOM_WEBHOOK_BODY_TEMPLATE` is a global JSON object template for configured custom webhook URLs. It takes precedence over URL-based payload detection. Use `$title_json` and `$content_json` for escaped JSON values. The raw `$title` and `$content` variants can produce invalid JSON when inputs contain quotes, backslashes, or newlines. Invalid rendered JSON falls back to the default payload.

```dotenv
CUSTOM_WEBHOOK_BODY_TEMPLATE={"title":$title_json,"content":$content_json}
```

Bark uses the custom webhook path. The default detector for `api.day.app` uses `title`, `body`, and `group`. For OneBot-style endpoints, choose the private-message or group endpoint and provide its `user_id` or `group_id` and `message` fields. Keep IDs and endpoint credentials in local configuration.

## Noise controls

`NOTIFICATION_DEDUP_TTL_SECONDS` and `NOTIFICATION_COOLDOWN_SECONDS` default to zero. Quiet hours use `NOTIFICATION_QUIET_HOURS` in `HH:MM-HH:MM` form, including overnight intervals. `NOTIFICATION_TIMEZONE` defaults to the runtime timezone. `NOTIFICATION_MIN_SEVERITY` can filter `info`, `warning`, `error`, and `critical`. Report, alert, and system-error routes default to info, warning, and error respectively. `NOTIFICATION_DAILY_DIGEST_ENABLED` is reserved.

Static routing deduplication and cooldown are process-local. A concurrent reservation blocks duplicate sends, then commits on any static-channel success or releases when all attempts fail. The noise check fails open on errors. This mechanism is separate from persistent alert rule cooldown and VN completed-session deduplication.

## Check configuration and delivery

```bash
python main.py --check-notify
```

The CLI checks configuration without sending or writing `.env`. It exits with 1 for configuration errors such as missing paired credentials or unknown route targets. Valid route targets that are disabled generate a warning.

The Web and desktop channel test sends a real message using current draft values. It reports sanitized diagnostics, including per-endpoint attempts for custom webhooks. Save configuration separately. Remove a channel's required keys to disable it. Desktop configuration import and backup are covered by [Desktop packaging](desktop-package.md).

## GitHub Actions mapping

The [daily analysis workflow](../.github/workflows/00-daily-analysis.yml) forwards explicitly mapped keys. It does not forward arbitrary numbered stock/email groups, `MARKDOWN_TO_IMAGE_CHANNELS`, or `MERGE_EMAIL_NOTIFICATION` by default. Use the [deployment guide](DEPLOY_EN.md) for local, container, and scheduled deployment.

Check the generated mapping with `python scripts/generate_notification_actions_env_table.py --check`.

<!-- notification-actions-env-table:start -->

| Key | Tier | Channel / feature | Actions source | Default |
| --- | --- | --- | --- | --- |
| `WECHAT_WEBHOOK_URL` | minimal | wechat | Secret | - |
| `WECHAT_MSG_TYPE` | advanced | wechat | Variable or Secret | `markdown` |
| `FEISHU_WEBHOOK_URL` | minimal | feishu | Secret | - |
| `FEISHU_WEBHOOK_SECRET` | advanced | feishu | Secret | - |
| `FEISHU_WEBHOOK_KEYWORD` | advanced | feishu | Variable or Secret | - |
| `TELEGRAM_BOT_TOKEN` | minimal | telegram | Secret | - |
| `TELEGRAM_CHAT_ID` | minimal | telegram | Secret | - |
| `TELEGRAM_MESSAGE_THREAD_ID` | advanced | telegram | Secret | - |
| `EMAIL_SENDER` | minimal | email | Variable or Secret | - |
| `EMAIL_PASSWORD` | minimal | email | Secret | - |
| `EMAIL_RECEIVERS` | advanced | email | Variable or Secret | - |
| `EMAIL_SENDER_NAME` | advanced | email | Variable or Secret | `daily_stock_analysis股票分析助手` |
| `PUSHOVER_USER_KEY` | minimal | pushover | Secret | - |
| `PUSHOVER_API_TOKEN` | minimal | pushover | Secret | - |
| `NTFY_URL` | minimal | ntfy | Secret | - |
| `NTFY_TOKEN` | advanced | ntfy | Secret | - |
| `GOTIFY_URL` | minimal | gotify | Secret | - |
| `GOTIFY_TOKEN` | minimal | gotify | Secret | - |
| `PUSHPLUS_TOKEN` | minimal | pushplus | Secret | - |
| `PUSHPLUS_TOPIC` | advanced | pushplus | Variable or Secret | - |
| `CUSTOM_WEBHOOK_URLS` | minimal | custom | Secret | - |
| `CUSTOM_WEBHOOK_BEARER_TOKEN` | advanced | custom | Secret | - |
| `CUSTOM_WEBHOOK_BODY_TEMPLATE` | advanced | custom | Variable or Secret | - |
| `WEBHOOK_VERIFY_SSL` | advanced | ntfy, gotify, custom, astrbot | Variable or Secret | `true` |
| `DISCORD_WEBHOOK_URL` | minimal | discord | Secret | - |
| `DISCORD_BOT_TOKEN` | minimal | discord | Secret | - |
| `DISCORD_MAIN_CHANNEL_ID` | minimal | discord | Secret | - |
| `ASTRBOT_URL` | minimal | astrbot | Secret | - |
| `ASTRBOT_TOKEN` | advanced | astrbot | Secret | - |
| `SERVERCHAN3_SENDKEY` | minimal | serverchan3 | Secret | - |
| `SLACK_WEBHOOK_URL` | minimal | slack | Secret | - |
| `SLACK_BOT_TOKEN` | minimal | slack | Secret | - |
| `SLACK_CHANNEL_ID` | minimal | slack | Secret | - |
| `NOTIFICATION_REPORT_CHANNELS` | advanced | routing | Variable or Secret | - |
| `NOTIFICATION_ALERT_CHANNELS` | advanced | routing | Variable or Secret | - |
| `NOTIFICATION_SYSTEM_ERROR_CHANNELS` | advanced | routing | Variable or Secret | - |
| `NOTIFICATION_DEDUP_TTL_SECONDS` | advanced | noise | Variable or Secret | `0` |
| `NOTIFICATION_COOLDOWN_SECONDS` | advanced | noise | Variable or Secret | `0` |
| `NOTIFICATION_QUIET_HOURS` | advanced | noise | Variable or Secret | - |
| `NOTIFICATION_TIMEZONE` | advanced | noise | Variable or Secret | - |
| `NOTIFICATION_MIN_SEVERITY` | advanced | noise | Variable or Secret | - |
| `NOTIFICATION_DAILY_DIGEST_ENABLED` | advanced | noise | Variable or Secret | `false` |

<!-- notification-actions-env-table:end -->

## Historical proposals

WebPush and Apprise were evaluated. The original evaluation remains in Git history. Neither is an implemented channel.
