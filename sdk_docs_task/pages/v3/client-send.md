# Client.send()

`Client.send()` is the primary method for pushing a single message through an
already-established Nimbus connection. It serializes the payload, attaches
delivery metadata, and hands the request to the active transport. Most
integrations call this method from a background worker rather than the main
request thread, since delivery can take several hundred milliseconds under
load. The method is synchronous and blocks until the broker acknowledges
receipt or the retry budget is exhausted, whichever happens first. If you need
non-blocking behavior, wrap the call in your own thread pool or async
executor — the SDK itself does not ship an async variant of this method in
the v3 line.

Internally, `send()` reuses the connection's existing TLS session, so calling
it repeatedly does not incur additional handshake cost. The retry behavior
described below only applies to transient broker errors (5xx-equivalent
responses); validation errors on the payload itself are raised immediately
and are never retried.

## Parameters

| Name | Type | Default | Required |
|---|---|---|---|
| payload | dict | n/a | Yes |
| retry_backoff_ms | int | 250 | No |
| timeout_ms | int | 5000 | No |
| idempotency_key | str | None | No |
| max_retries | int | 3 | No |

`retry_backoff_ms` controls the base delay between retry attempts. Nimbus
applies exponential backoff starting from this value, so a `retry_backoff_ms`
of 250 means the first retry waits ~250ms, the second ~500ms, and so on up to
`max_retries` attempts. Setting `idempotency_key` lets the broker deduplicate
retried sends so a flaky network doesn't result in the message being
delivered twice.

## Example

```python
client = Client(api_key="sk_live_...", region="us-east-1")

client.send(
    payload={"event": "order.created", "order_id": "ord_123"},
    retry_backoff_ms=250,
    idempotency_key="order.created:ord_123",
)
```

## Errors

`Client.send()` raises `PayloadValidationError` if the payload cannot be
serialized to JSON, and `DeliveryTimeoutError` if the broker does not
acknowledge within `timeout_ms` across all retry attempts.
