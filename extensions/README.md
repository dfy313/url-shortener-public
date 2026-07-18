# 📺 Url Shortener – Extensions

This section explores several potential enhancements that could be made to the URL Shortener architecture. While the current implementation is fully functional, real-world systems often evolve over time to address additional scalability, reliability, and operational concerns.

Each extension below highlights a limitation of the current design, discusses possible implementation approaches, and explains the benefits that the enhancement would provide.

## Extension #1 — Key Expiration Service

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current system allows clients to specify an optional `expirationTime` when creating a short URL, but expiration is not actively enforced. As a result, links may continue working after their intended expiration date has passed.

### Proposed Enhancement

Introduce a dedicated **Key Expiration Service** responsible for:

- Scanning for expired URLs.
- Marking expired URLs as inactive (or permanently deleting them).
- Removing expired entries from Redis.
- Publishing expiration events into the CDC pipeline so downstream systems can react accordingly.

The **Read Service** should also validate expiration when loading URLs from Aurora, providing a second layer of protection if the expiration service is delayed or temporarily unavailable.

Expiration enforcement should occur at multiple layers of the system, including the background expiration workers, the CDC pipeline, and the read/write path. This defensive approach ensures that expired URLs cannot continue serving traffic indefinitely, even if a cleanup job is delayed or temporarily unavailable.

### Expired Key Lifecycle

Another design consideration is determining what should happen to the auto generated `shortKey` or the user supplied `custom_alias` after a URL expires. The appropriate approach depends on the platform's requirements for security, consistency, and efficient use of the available key space. Common approaches include:

- **Permanently reserve the key**, preventing it from ever being reused.
- **Recycle automatically generated keys** while keeping custom aliases permanently reserved.
- **Delay reuse** by placing expired keys into a temporary retention period before returning them to the available key pool.
- **Soft delete** the URL, allowing the original owner to renew or restore the expired link.

### Benefits

- Supports temporary and time-limited links
- Prevents expired URLs from serving traffic

<br>

</details>

## Extension #2 — More Secure Key Generation (Auto Generation Flow)

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current system generates short URLs using a globally incrementing **Redis counter** combined with **Sqids Base62 encoding**.

For example:

```text
Counter = 0 → SqidsEncode(0) = bMZn4Y
Counter = 1 → SqidsEncode(1) = UkLWZg
Counter = 2 → SqidsEncode(2) = gbHJdm
Counter = 3 → ...
```

While Sqids produces compact, human-friendly identifiers, the resulting sequence remains deterministic. As a result, anyone familiar with the key generation algorithm can predict which short keys correspond to neighboring counter values.

This creates an **enumeration vulnerability**, where attackers can systematically generate candidate short URLs and probe the redirect endpoint in an attempt to discover valid links. It also leaks information about system activity, as external observers may be able to estimate URL creation volume by analyzing generated identifiers.

### Proposed Enhancement

Introduce a **secret-keyed transformation** step before encoding identifiers with Sqids. Rather than encoding the Redis counter directly, first transform the counter using an HMAC-based hashing function:

```text
Counter = 0 → HMAC(secret, 0) = Digest → SqidsEncode(TruncatedDigest) = QMQKZLK3Hy4C
Counter = 1 → HMAC(secret, 1) = Digest → SqidsEncode(TruncatedDigest) = CcuHkyGK5Bc8
Counter = 2 → HMAC(secret, 2) = Digest → SqidsEncode(TruncatedDigest) = se6KB1juIPmd
Counter = 3 → ...
```

Example implementation:

```python
def generate_short_key_with_redis(r):
    SQIDS_SECRET = "SECRET".encode("utf-8")
    sqids_instance = Sqids(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_length=6)
    while True:
        counter = r.incr("url_shortener:counter")
        counter_bytes = counter.to_bytes(8, byteorder="big", signed=False)
        digest = hmac.new(SQIDS_SECRET, counter_bytes, hashlib.sha256).digest()
        truncated_digest = int.from_bytes(digest[:8], byteorder="big") & ((1 << 63) - 1)
        short_key = sqids_instance.encode([truncated_digest])
        if not r.sismember("url_shortener:custom_aliases", short_key):
            return short_key
```

The Redis counter continues to provide a unique input source, while the HMAC transformation makes generated identifiers significantly more difficult to predict. Unlike the current implementation, observing one short URL no longer provides useful information about neighboring URLs, future URLs, or overall system activity.

### Collision Considerations

The current auto-generated key implementation derives identifiers directly from a monotonically increasing counter and therefore cannot produce collisions for automatically generated URLs. However, the HMAC-based approach introduces a finite output space by truncating the digest before encoding. As a result, collisions become theoretically possible.

To mitigate this risk:

- Continue enforcing a unique constraint on `shortKey` within Aurora.
- Retry key generation when a conflict occurs.
- Incorporate an attempt counter into the HMAC input when generating retry candidates.

Although collisions become theoretically possible, they remain extremely unlikely in practice. Because the generated identifiers occupy a 63-bit space, the probability that a newly generated key collides with one of the existing keys is approximately:

```text
Existing Keys / 2^63
```

### Benefits

- Makes large-scale URL enumeration significantly more difficult.
- Improves privacy for shortened links.
- Prevents attackers from predicting neighboring identifiers.
- Reduces information leakage about system activity and traffic volume.

<br>

</details>

## Extension #3 — Better Handling of Duplicates (Custom Alias Flow)

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current system tracks custom aliases separately from autogenerated short keys. Custom aliases are stored in the `url_shortener:custom_aliases` Redis set, whereas autogenerated short keys are derived from the Redis counter and are not tracked in this set.

When a client creates a new short URL and provides a custom alias, the Write Service performs a quick Redis lookup to verify that the alias does not already exist within `url_shortener:custom_aliases`. However, this validation does not account for existing autogenerated short keys.

As a result, there is a rare edge case where a user may request a custom alias that matches a previously generated short key. Because autogenerated keys are not included in the Redis validation, the conflict is not detected until the database insert is attempted and rejected by the MySQL unique constraint. Assuming a user selects a uniformly random six-character alias from the same 62-character alphabet, the probability that it matches an existing autogenerated six-character key is approximately:

```text
Existing Autogenerated Keys / 62^6
```

### Proposed Enhancement

Introduce a centralized Redis set that tracks **all reserved short keys**, regardless of whether they were generated automatically or provided as custom aliases:

```text
url_shortener:reserved_short_keys
```

Whenever a new short URL is created, the proposed key would first be validated against this shared set. By maintaining a single namespace for all short keys, the system can detect conflicts before attempting a database write.

The database should continue enforcing a unique constraint on `shortKey`, providing a final correctness guarantee in the event of race conditions or concurrent requests that attempt to reserve the same key simultaneously.

### Benefits

- Prevents collisions between autogenerated keys and custom aliases.
- Establishes a single namespace for all short keys.
- Detects conflicts before attempting a database write.
- Provides faster feedback to clients when a key is already in use.

<br>

</details>

## Extension #4 — Cache Eviction

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current system caches short URL mappings in Redis to improve read performance. However, cached entries are never removed unless the Redis instance is restarted or manually cleared. As traffic grows, Redis may accumulate a large number of infrequently accessed URLs, causing memory consumption to steadily increase over time.

### Proposed Enhancement

The current implementation stores all cached URLs within a single Redis hash:

```text
url_shortener:shortKey_cache
    ├── abc123 → https://wikipedia.com
    ├── xyz321 → https://facebook.com
    └── ...
```

We should restructure the cache so that each short URL is stored as its own Redis key:

```text
url_shortener:shortKey_cache:abc123 → https://wikipedia.com
url_shortener:shortKey_cache:xyz321 → https://facebook.com
...
```

This allows a TTL (Time-To-Live) to be assigned to each cached URL independently. When a cache entry expires, Redis automatically removes it from memory. If the same short URL is requested again, the Read Service can reload the mapping from the Database and repopulate the cache. The database remains the source of truth, while Redis continues to function as a temporary performance layer.

### Cache Eviction Policy

In addition to assigning TTLs, Redis can also be configured with a maximum memory limit and a cache eviction policy. For example, an **allkeys-lru** policy preferentially evicts the least recently used entries when memory becomes constrained, helping keep frequently accessed URLs in the cache while removing less active ones. Choosing an appropriate eviction policy allows the cache to adapt automatically as traffic patterns evolve.

### Benefits

- Prevents Redis memory usage from growing indefinitely
- Enables per-entry TTLs and automatic cache eviction.
- Prioritizes frequently accessed URLs in the cache
- Automatically removes stale cache entries

<br>

</details>

## Extension #5 — Redis Reliability

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current system relies on Redis for several important operations:

- Caching short URL mappings for fast reads
- Generating unique short keys via the global counter
- Tracking reserved custom aliases

While Redis significantly improves performance, the current implementation assumes it is always available. If Redis becomes unavailable, the **Read Service** can continue serving requests by falling back to MySQL, albeit with increased latency and database load.

The **Write Service**, however, depends on Redis for key generation and duplicate detection. Without Redis, it may be unable to safely create new short URLs. As a result, Redis represents a potential single point of failure for write operations within the system.

### Proposed Enhancement

Introduce explicit failure handling for Redis outages within the **Write Service**. If Redis becomes unavailable, the application should detect the failure and respond in a predictable manner. Possible approaches include:

- Temporarily rejecting write requests with a `503 Service Unavailable` response until Redis is restored.
- Falling back to an alternative key-generation mechanism.
- Maintaining a secondary key-generation service for disaster recovery scenarios.

The Redis infrastructure itself can also be made more resilient through:

- Redis replication
- Automatic failover
- Multi-AZ deployments
- Managed Redis offerings such as Amazon ElastiCache

These improvements reduce the likelihood of Redis outages and help minimize recovery time when failures do occur.

### Benefits

- Prevents Redis from becoming a single point of failure
- Allows operations to continue during Redis outages
- Improves overall system availability and resilience
- Provides predictable behavior during infrastructure failures

<br>

</details>

<br>
