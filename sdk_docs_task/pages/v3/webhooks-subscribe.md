# Webhooks.subscribe()

`Webhooks.subscribe()` registers a URL that Nimbus will call whenever an
event matching your subscription occurs. Subscriptions are account-scoped,
not connection-scoped, so a subscription created from one process is visible
to every other process using the same account. This is the recommended way
to receive delivery receipts and inbound events without polling.

Nimbus retries failed callback deliveries (any response that is not a 2xx)
using the same exponential-backoff scheme described for `Client.send()`, up
to `max_attempts` times, after which the event is written to the dead-letter
log for that subscription instead of being dropped silently.

## Parameters

| Name | Type | Default | Required |
|---|---|---|---|
| url | str | n/a | Yes |
| events | list[str] | ["message.received"] | No |
| secret | str | None | No |
| max_attempts | int | 5 | No |

When `secret` is set, every callback request Nimbus makes to `url` includes
an `X-Nimbus-Signature` header containing an HMAC-SHA256 signature of the
raw request body, computed with `secret` as the key. Verifying this header
on your endpoint is the recommended way to confirm a callback actually came
from Nimbus rather than a spoofed request.

## Example

```python
webhooks = client.webhooks

webhooks.subscribe(
    url="https://api.example.com/hooks/nimbus",
    events=["message.received", "message.failed"],
    secret="whsec_abc123",
)
```

On the receiving end, verify the signature before processing:

```python
import hmac, hashlib

expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, request.headers["X-Nimbus-Signature"]):
    raise ValueError("signature mismatch")
```

## Errors

`Webhooks.subscribe()` raises `InvalidUrlError` if `url` is not HTTPS, since
Nimbus refuses to deliver callbacks over plain HTTP.
