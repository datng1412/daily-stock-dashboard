# Security and Secrets

## Never commit

- .env
- SSI credentials
- access tokens
- auth headers
- raw auth responses
- account IDs
- private keys

## Diagnostics

Allowed:
- provider name
- endpoint label
- HTTP status
- sanitized error summary

Forbidden:
- token
- consumer secret
- authorization header
- raw response containing credentials