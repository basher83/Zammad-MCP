# Configuration reference

This page lists every environment variable that the Zammad MCP server reads.
The [README](../../README.md#configuration) shows the minimal configuration.
The [HTTP transport guide](../deployment/http-transport.md) shows how to deploy the HTTP transport.

The server loads a `.env` file from the current working directory at startup.
Variables already set in the process environment take precedence over the file.
Boolean variables accept only `1`, `true`, `yes`, or `on` as true values, unless a section says otherwise.
Keep your `.env` file out of version control. The repository `.gitignore` already excludes it.

## Zammad connection and authentication

The server needs `ZAMMAD_URL` and one authentication method.

| Variable | Default | Description |
|----------|---------|-------------|
| `ZAMMAD_URL` | - | Required. Zammad API base URL, including the `/api/v1` path. Only `http` and `https` URLs are accepted |
| `ZAMMAD_HTTP_TOKEN` | - | API token. Recommended |
| `ZAMMAD_OAUTH2_TOKEN` | - | OAuth2 token |
| `ZAMMAD_USERNAME` | - | Username. Use together with `ZAMMAD_PASSWORD` |
| `ZAMMAD_PASSWORD` | - | Password. Use together with `ZAMMAD_USERNAME` |
| `ZAMMAD_HTTP_TOKEN_FILE` | - | Path to a file that contains the API token |
| `ZAMMAD_OAUTH2_TOKEN_FILE` | - | Path to a file that contains the OAuth2 token |
| `ZAMMAD_PASSWORD_FILE` | - | Path to a file that contains the password |
| `ZAMMAD_INSECURE` | unset | Disable TLS certificate verification. Set it only for self-signed or internal certificate chains on a trusted network path. Any other value keeps verification enabled |

Secret-file variables follow the Docker secrets pattern.
A non-empty file takes precedence over the plain variable.
If the file cannot be read, the server logs a warning and uses the plain variable.
If the file is empty or contains only whitespace, the server uses the plain variable.

The server fails at startup with a message that names the problem when:

- `ZAMMAD_URL` is unset or malformed
- no authentication method is set
- `ZAMMAD_TOKEN` is set instead of `ZAMMAD_HTTP_TOKEN`

`ZAMMAD_*` credentials authenticate the server to Zammad.
They do not authenticate MCP clients that connect to the server.

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. An unknown value logs a warning and uses `INFO` |

## Transport

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http`. The value is case-insensitive. Any other value fails at startup |
| `MCP_HOST` | `127.0.0.1` | Host address for the HTTP transport. Ignored for stdio |
| `MCP_PORT` | - | Port for the HTTP transport. Required when `MCP_TRANSPORT=http`. Must be an integer from 1 to 65535 |

The server does not implement inbound MCP client authentication.
Bind to `0.0.0.0` only behind an authenticated TLS proxy or inside a network restricted to trusted clients.
See the [HTTP transport guide](../deployment/http-transport.md) for deployment steps.

## Webhook events (HTTP transport only)

| Variable | Default | Description |
|----------|---------|-------------|
| `ZAMMAD_WEBHOOK_SECRET` | unset | HMAC SHA1 Signature Token shared with the Zammad webhook. `POST /webhooks/zammad` returns `503` until it is set |

See [Webhook events](../deployment/http-transport.md#webhook-events) for the Zammad setup and the event format.

## Audit logging

Audit logging is disabled by default. When enabled, the server writes one JSON object per line
(JSON Lines) for every MCP tool call, each Zammad connection attempt at startup, and each URL
security check that flags a local or private-network Zammad host.

| Variable | Default | Description |
|----------|---------|-------------|
| `ZAMMAD_AUDIT_LOG_ENABLED` | unset | Enable with `1`, `true`, `yes`, or `on` |
| `ZAMMAD_AUDIT_LOG_DESTINATION` | `stderr` | `stderr`, `file`, or `syslog` |
| `ZAMMAD_AUDIT_LOG_FILE` | - | Append target, required if destination is `file` |

Example record:

```json
{"timestamp": "2026-09-08T12:00:00+00:00", "event_type": "tool_call", "action": "zammad_get_ticket", "success": true, "duration_ms": 12.5, "details": {}}
```

Event types are `tool_call`, `authentication`, and `security_validation`.
Records never contain tool arguments, Zammad responses, credentials, or full URLs.
Failures are recorded by exception type only.
Any `details` key that contains `password`, `passwd`, `token`, `secret`, `authorization`,
`credential`, `data`, `api_key`, `api-key`, or `apikey` is redacted.
Audit output never uses stdout, so the default `stderr` destination is safe for the stdio transport.
Invalid enabled configuration (unknown destination or missing file path) fails at startup.

## Ticket export

`zammad_export_tickets` is read-only against Zammad but writes a JSON Lines file on the host that runs
the MCP server. Each line is one JSON object per ticket, with its title, group, state, priority, timestamps,
optional tags, and conversation articles converted to plain text. The tool is intended for bulk exports
that would exceed MCP response-size limits.

Without filters, the tool pages through the list endpoint with no result cap.
With `query`, `group`, `state`, `created_after`, or `created_before`, it uses the search
endpoint, which Zammad caps at 10,000 results.
Internal articles are excluded unless `include_internal_articles` is set.
Tags cost one extra request per ticket when `include_tags` is set.

| Variable | Default | Description |
|----------|---------|-------------|
| `ZAMMAD_EXPORT_DIR` | unset | Directory that exports are confined to. Export is disabled until it is set to an existing directory |

Filesystem confinement: `output_path` must end in `.jsonl`. Relative paths are resolved inside
`ZAMMAD_EXPORT_DIR`. Absolute paths are accepted only if they resolve inside it. Symlinks are
resolved before the containment check, so `..` traversal or a symlink that points outside the directory
is rejected. The file is opened in append mode and flushed per ticket, so an interrupted export can
be continued with `resume_from_page`. Per-ticket failures are counted and reported in the summary
without stopping the export.

## Rate limiting, retries, and circuit breaker

The client wraps every Zammad request with retries, an optional client-side throttle, and a circuit breaker.
A variable that is set to an invalid value fails at startup.

| Variable | Default | Meaning |
|----------|---------|---------|
| `ZAMMAD_RATE_LIMIT_ENABLED` | `false` | Opt in to client-side throttling. Accepts `1`/`true`/`yes`/`on` or `0`/`false`/`no`/`off` |
| `ZAMMAD_RATE_LIMIT_REQUESTS` | `60` | Max requests per window (>= 1) |
| `ZAMMAD_RATE_LIMIT_WINDOW` | `60` | Window length in seconds (> 0) |
| `ZAMMAD_MAX_RETRIES` | `3` | Retries for safe reads. `0` disables |
| `ZAMMAD_RETRY_BACKOFF_BASE` | `1.0` | Backoff seconds: `base * 2^attempt` (> 0) |
| `ZAMMAD_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before failing fast (>= 1) |
| `ZAMMAD_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `30` | Seconds before requests are allowed again (> 0). One more failure re-opens the circuit |

Behavior to be aware of:

- Only `GET`/`HEAD`/`OPTIONS` are retried, on HTTP 429/500/502/503/504, connection errors, and timeouts.
  Writes (`POST`/`PUT`/`PATCH`/`DELETE`) are sent exactly once, so a slow Zammad never duplicates a ticket or article.
- A `Retry-After` header expressed in seconds overrides the backoff (capped at 60s). Other formats fall back to backoff.
- Throttling and circuit state are per process. Multiple server instances do not share a budget.
- When retries are exhausted or the circuit is open, tools return an `Error:` message that names the cause. A 429
  outcome (or a throttled write) points at rate limiting and `ZAMMAD_RATE_LIMIT_ENABLED`. A 5xx outcome reports a
  server error. Reduce request frequency, paginate, or enable throttling if you keep hitting Zammad's limits.
