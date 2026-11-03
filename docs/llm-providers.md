# LLM provider configuration

The [English LLM guide](LLM_CONFIG_GUIDE_EN.md) owns configuration priority, channel setup, YAML, compatibility, and rollback. Use the Web channel editor and [the channel preset definitions](../apps/dsa-web/src/components/settings/llmProviderTemplates.ts) for the built-in protocol and endpoint suggestions.

## Channel examples

Set real credentials in the secret environment. These examples illustrate a native DeepSeek channel and an OpenAI-compatible endpoint.

```env
LLM_CHANNELS=deepseek
LLM_DEEPSEEK_PROTOCOL=deepseek
LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK_API_KEY=YOUR_PROVIDER_KEY
LLM_DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro
LITELLM_MODEL=deepseek/deepseek-v4-flash
```

```env
LLM_CHANNELS=my_proxy
LLM_MY_PROXY_PROTOCOL=openai
LLM_MY_PROXY_BASE_URL=https://your-proxy.example.com/v1
LLM_MY_PROXY_API_KEY=YOUR_PROVIDER_KEY
LLM_MY_PROXY_MODELS=gpt-5.5,claude-sonnet-4-6
```

Use the model ID enabled for your account. An OpenAI-compatible gateway generally expects an `openai/`-prefixed LiteLLM route. Preserve explicit provider-prefixed routes where the adapter requires them. A successful connection test verifies only the tested endpoint, model, and credential combination at that time. See the [channel diagnostics](LLM_CONFIG_GUIDE_EN.md#web-channel-editor-compatibility-migration-and-rollback-rules) for discovery, optional capability checks, and saved configuration behavior.
