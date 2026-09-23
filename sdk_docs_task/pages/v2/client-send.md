# Client.send()

`Client.send()` sends a single message over the connection opened by
`Client.connect()`. It is a blocking call: it returns only once the broker
has acknowledged the message or the configured retries have been exhausted.
Validation failures on the payload are raised immediately and are never
retried.

## Parameters

| Name | Type | Default | Required |
|---|---|---|---|
| payload | dict | n/a | Yes |
| retry_backoff_ms | int | 100 | No |
| timeout_ms | int | 5000 | No |
| max_retries | int | 3 | No |

`retry_backoff_ms` is the base delay, in milliseconds, between retry
attempts when the broker returns a transient error. Nimbus doubles the delay
on each subsequent attempt up to `max_retries` tries.

## Example

```python
client = Client(api_key="sk_live_...")
client.connect(region="us-east-1")

client.send(
    payload={"event": "order.created", "order_id": "ord_123"},
    retry_backoff_ms=100,
)
```

## Errors

`Client.send()` raises `PayloadValidationError` if the payload cannot be
serialized to JSON, and `DeliveryTimeoutError` if the broker does not
acknowledge within `timeout_ms` across all retry attempts.
