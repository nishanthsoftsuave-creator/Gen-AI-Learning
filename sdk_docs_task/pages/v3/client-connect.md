# Client.connect()

`Client.connect()` establishes the underlying transport session that every
other `Client` method depends on. It is typically called once at process
startup and the resulting client instance is reused for the lifetime of the
process. Calling `connect()` again on an already-connected client is a no-op
that returns the existing session rather than opening a second one, so it is
safe to call defensively in code paths that may run more than once.

The method resolves the correct regional endpoint from the `region`
parameter, performs the TLS handshake, and exchanges the `api_key` for a
short-lived session token. That session token — not the raw API key — is
what gets attached to every subsequent request, so the API key itself never
travels with individual `send()` calls.

## Parameters

| Name | Type | Default | Required |
|---|---|---|---|
| api_key | str | n/a | Yes |
| region | str | n/a | Yes |
| timeout_ms | int | 10000 | No |
| keep_alive | bool | True | No |

`region` must be one of the supported Nimbus regions (`us-east-1`,
`eu-west-1`, `ap-south-1`). Passing an unsupported region raises
`UnsupportedRegionError` before any network call is made. `keep_alive`
determines whether the client sends periodic pings to keep the session token
from expiring during idle periods; disabling it is only recommended for
short-lived scripts.

## Example

```python
client = Client()
client.connect(
    api_key="sk_live_...",
    region="eu-west-1",
    keep_alive=True,
)
```

## Errors

`Client.connect()` raises `AuthenticationError` if the API key is invalid or
revoked, and `UnsupportedRegionError` if `region` does not match a known
Nimbus region.
