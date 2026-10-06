# OAuth for remote harnesses

Per-user OAuth is optional. Leave it off and the server keeps using one static
Zammad credential (`ZAMMAD_HTTP_TOKEN`, `ZAMMAD_OAUTH2_TOKEN`, or
`ZAMMAD_USERNAME` and `ZAMMAD_PASSWORD`) for every caller. That is the path
for stdio and for a shared API token.

Turn it on when a remote MCP harness should sign each person in, and Zammad
should see that person. The reference harness for this profile is
[Claude.ai](https://claude.ai). The same sign-in also covers the other Claude
apps that share Claude.ai's connector authentication: Claude Desktop, Claude
mobile, Cowork, and Claude Code. Any other MCP client that follows the same
OAuth rules can use this server the same way.

Set `ZAMMAD_MCP_OAUTH` to `1`, `true`, `yes`, or `on` to enable it. Any other
value, or leaving it unset, keeps the static credential path.

## What the signed-in user inherits

The harness never receives the person's Zammad password. It completes OAuth
against this MCP server. This server sends the browser to Zammad's own
authorization page. Zammad issues an access token for the account that signed
in. Later tool calls send that token to the Zammad API as
`Authorization: Bearer …`.

Zammad then applies that account's roles, groups, and permissions. A second
person who connects gets a different Zammad token. While this mode is on, the
server does not fall back to `ZAMMAD_HTTP_TOKEN` or the other static
credentials.

## What you register where

Two different redirect URLs are involved. They are not interchangeable.

| Party | URL | Where it is registered |
| --- | --- | --- |
| Zammad | `{MCP_PUBLIC_URL}/auth/callback` | Zammad → Admin → System → API → Applications |
| Claude.ai (hosted apps) | `https://claude.ai/api/mcp/auth_callback` | Not in Zammad. Claude presents it to this server through client registration |
| Claude Code | `http://localhost/callback` and `http://127.0.0.1/callback`, any port | Same. This server accepts the loopback redirect on any port |

`MCP_PUBLIC_URL` is the origin only, for example `https://mcp.example.com`.
The connector URL a harness saves is `{MCP_PUBLIC_URL}/mcp`, for example
`https://mcp.example.com/mcp`. That full URL is the OAuth resource identifier
and must match what the person enters, including the `/mcp` path.

Zammad in production mode accepts only an `https://` callback. Use an `https`
origin for `MCP_PUBLIC_URL` when the Zammad instance is in production.

## Zammad application

In Zammad, open **Admin → System → API → Applications** and create an
application:

| Field | Value |
| --- | --- |
| Name | A label such as `Zammad MCP` |
| Callback URL | `{MCP_PUBLIC_URL}/auth/callback` |

Copy the client id and client secret into `ZAMMAD_OAUTH_CLIENT_ID` and
`ZAMMAD_OAUTH_CLIENT_SECRET`. Zammad grants the scope `full` only. This server
requests that scope and does not forward harness scopes such as
`offline_access` to Zammad.

## Server environment

`ZAMMAD_MCP_OAUTH` requires HTTP transport. Example:

```bash
ZAMMAD_MCP_OAUTH=true
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_PUBLIC_URL=https://mcp.example.com
ZAMMAD_URL=https://help.example/api/v1
ZAMMAD_OAUTH_CLIENT_ID=the-zammad-application-id
ZAMMAD_OAUTH_CLIENT_SECRET=the-zammad-application-secret
```

`ZAMMAD_URL` still includes `/api/v1`. The server derives Zammad's
`/oauth/authorize` and `/oauth/token` endpoints from that host.

Put TLS in front of the process. Claude.ai calls the server from the public
internet (`160.79.104.0/21`). The connector URL has to be the HTTPS URL
Claude.ai can reach, and `MCP_PUBLIC_URL` has to be that same origin.

`ZAMMAD_INSECURE` still disables TLS verification for the connection to
Zammad. Leave it unset on a public certificate.

## Add the connector in Claude.ai

1. In Claude.ai, open **Customize → Connectors → Add custom connector**.
   Organization owners use **Organization settings → Connectors → Add → Custom**.
2. Enter the connector URL `{MCP_PUBLIC_URL}/mcp`.
3. Choose **Sign in now** (or **Sign in when needed**). Do not choose **No sign in**.
4. For the OAuth client, **Use Claude's published identity** is the match for
   this server. **Register automatically** also works. Leave the client secret
   empty. This server treats the harness as a public client.

Claude.ai discovers the authorization server from a `401` response. The
`WWW-Authenticate` header points at the protected-resource metadata. That
document's `resource` value is the connector URL, and its first
`authorization_servers` entry is `MCP_PUBLIC_URL`. The authorization server
metadata then advertises:

- S256 PKCE (`code_challenge_methods_supported`)
- Dynamic client registration (`registration_endpoint`)
- Client ID Metadata Documents (`client_id_metadata_document_supported: true`)
- Public clients (`none` in `token_endpoint_auth_methods_supported`)

Claude.ai uses a Client ID Metadata Document only when both of those last two
values are present. This server sends both, and it also accepts dynamic
registration for harnesses that do not publish a metadata document. The token
endpoint accepts `application/x-www-form-urlencoded`. A refresh token that is
no longer valid returns `invalid_grant`.

On the sign-in page the person sees Zammad, not a password form on this
server. After Zammad redirects back to `{MCP_PUBLIC_URL}/auth/callback`, this
server redirects the browser to the harness callback
(`https://claude.ai/api/mcp/auth_callback` for the hosted Claude apps).

## Other harnesses

A harness other than Claude.ai can connect when it implements the same
remote-MCP OAuth profile:

- It starts from a `401` and reads protected-resource metadata.
- It uses the authorization-code grant with S256 PKCE.
- It identifies itself with a Client ID Metadata Document or dynamic client
  registration, as a public client (`token_endpoint_auth_method=none`).
- Its redirect URI is `https`, or a loopback `http://localhost` or
  `http://127.0.0.1` URL. Loopback redirects match with the port ignored, which
  is what Claude Code needs.

The Zammad user is still whoever completes Zammad's authorization page.

## What stays on the static path

Do not set `ZAMMAD_MCP_OAUTH` when:

- the client is a local stdio process
- every caller should share one Zammad API token

Those deployments are unchanged. HTTP without this flag still has no inbound
MCP authentication. Keep that listener on loopback or a private network, as
the [HTTP transport guide](http-transport.md) describes.
