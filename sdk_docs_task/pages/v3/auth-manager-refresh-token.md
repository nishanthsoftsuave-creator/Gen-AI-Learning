# AuthManager.refresh_token()

`AuthManager.refresh_token()` exchanges a previously-issued refresh token
for a new session token without requiring the caller to re-supply the
original API key. This is the mechanism long-running processes should use to
stay authenticated across session-token expiry instead of holding the raw
API key in memory for the life of the process.

The returned session token is valid for `ttl_seconds` from the moment the
call succeeds, not from when the original refresh token was issued. Callers
are expected to request a new token proactively, well before `ttl_seconds`
elapses, rather than waiting for a request to fail with an expiry error.

## Parameters

| Name | Type | Default | Required |
|---|---|---|---|
| refresh_token | str | n/a | Yes |
| scope | str | "default" | No |
| ttl_seconds | int | 3600 | No |

`scope` narrows the permissions attached to the returned session token; it
can only narrow, never widen, the scope already granted to the original
refresh token. Requesting a scope wider than the refresh token allows does
not raise an error — it silently returns a token limited to the original,
narrower scope.

## Example

```python
auth = client.auth_manager

session = auth.refresh_token(
    refresh_token=stored_refresh_token,
    scope="send:messages",
    ttl_seconds=3600,
)
```

## Errors

If `refresh_token` has expired or been revoked, `refresh_token()` raises
`TokenExpiredError` rather than returning a token — callers must fall back
to a full re-authentication flow in that case, since an expired refresh
token cannot be renewed.
