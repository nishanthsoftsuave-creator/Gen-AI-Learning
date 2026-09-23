# RateLimiter.configure()

`RateLimiter.configure()` sets the client-side throttle Nimbus applies
before a request leaves the process. This is separate from the rate limit
enforced on the broker itself, and exists so applications can fail fast
instead of handling 429 responses from the broker as part of normal control
flow.

## Parameters

| Name | Type | Default | Required |
|---|---|---|---|
| max_requests | int | 50 | No |
| window_ms | int | 60000 | No |

`max_requests` and `window_ms` together define the sustained rate — 50
requests per 60000ms by default, i.e. 50 requests per minute. There is no
burst allowance in this version; every request counts against the sustained
budget for its window with no exceptions.

## Example

```python
limiter = client.rate_limiter

limiter.configure(
    max_requests=50,
    window_ms=60000,
)
```

## Errors

`RateLimiter.configure()` raises `ValueError` if `max_requests` is less than
or equal to zero.
