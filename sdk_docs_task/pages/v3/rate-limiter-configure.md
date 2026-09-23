# RateLimiter.configure()

`RateLimiter.configure()` sets the client-side throttle that Nimbus applies
before a request ever leaves the process, which is separate from — and
tighter than — the rate limit enforced on the broker itself. The purpose of
the client-side limiter is to fail fast and predictably instead of letting
the broker's own limiter return 429s that then have to be handled as retry
logic in application code.

Configuring the limiter does not affect requests already in flight; it only
applies to requests queued after `configure()` returns. Calling `configure()`
a second time replaces the previous configuration entirely rather than
merging with it.

## Parameters

| Name | Type | Default | Required |
|---|---|---|---|
| max_requests | int | 100 | No |
| window_ms | int | 60000 | No |
| burst | int | 20 | No |

`max_requests` and `window_ms` together define the sustained rate — 100
requests per 60000ms by default, i.e. 100 requests per minute. `burst` allows
short spikes above the sustained rate: up to `burst` additional requests may
be sent immediately even if the sustained budget for the current window is
already exhausted, as long as the previous window left burst capacity
unused.

## Example

```python
limiter = client.rate_limiter

limiter.configure(
    max_requests=100,
    window_ms=60000,
    burst=20,
)
```

## Errors

`RateLimiter.configure()` raises `ValueError` if `burst` is greater than
`max_requests`, since a burst allowance larger than the sustained budget
would make the sustained limit meaningless.
