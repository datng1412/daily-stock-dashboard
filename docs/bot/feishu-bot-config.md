# Feishu notification setup

For group reports, add a custom bot in Feishu group settings and set `FEISHU_WEBHOOK_URL` in your local secret configuration. Match the bot's optional keyword with `FEISHU_WEBHOOK_KEYWORD` and signing secret with `FEISHU_WEBHOOK_SECRET`. The sender prefixes the configured keyword and adds the required timestamp and signature when configured. Check group membership, posting permissions, and IP allowlists if delivery fails.

App and Stream bot features use `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, and, for Stream mode, `FEISHU_STREAM_ENABLED=true`. App credentials alone do not enable group webhook delivery. See the [bot integration guide](../bot-command_EN.md) for interactive commands and [notification checks](../notifications.md#check-configuration-and-delivery) to diagnose delivery.

## Feishu automation webhook

When a Feishu automation consumes a report card, define the trigger shape and map the action's message to `card.elements[0].text.content`.

```json
{
  "msg_type": "interactive",
  "card": {
    "config": { "wide_screen_mode": true },
    "elements": [
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "..."
        }
      }
    ],
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "A股智能分析报告"
      }
    }
  }
}
```

The [automation screenshot](img_11.png) shows the field mapping.
