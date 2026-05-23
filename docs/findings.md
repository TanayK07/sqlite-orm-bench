# Detailed Findings

See [ARTICLE.md](../ARTICLE.md) for the full long-form writeup with industry comparison.

## Quick Reference

### Five Key Conclusions

1. **The ORM Is the Bottleneck, Not SQLite** — 11 configs × 10M rows, never exceeded 3,821 r/s. Raw `executemany` hits 87,893 r/s.
2. **PRAGMA Tuning Is Irrelevant for ORM Workloads** — `sync=OFF`, 64MB cache, 256MB mmap, 8-conn pool: all within 26%.
3. **Chunk Size Controls Latency, Not Throughput** — p99 scales 66× (313ms → 20,508ms). Throughput drops only 20%.
4. **Baseline Config Wins** — `sync=NORMAL`, default cache, `pool=5`, `chunk=5000`. No exotic PRAGMAs needed.
5. **Raw SQL Degrades Gracefully at Scale** — 87,893 r/s @ 10M → 65,742 r/s @ 50M (25% drop). I/O scaling curve.
6. **QueuePool Eliminates Concurrency Errors** — Zero errors across 110M rows.

### When to Bypass Your ORM

| Scenario | ORM | Raw SQL |
|----------|-----|---------|
| < 1K rows | Good enough | Premature optimization |
| 10K–1M rows | 2–5 min/M | 7 sec/M |
| 1M–100M rows | 45 min/10M | 1.9 min/10M |
| Sustained > 1K r/s | Ceiling at 3.8K | Headroom to 88K |
| Upsert-heavy | Slow | 18× faster |

### Surprising Findings From the Literature

- **`temp_store=MEMORY` can be slower than disk** (Forward Email)
- **SQLite's default exponential backoff is bad** — uniform 1ms is better (Margheim)
- **WAL is slower than DELETE at low concurrency** — 43% slower at 1 worker (Khurana)
- **50-connection pool is 23× slower than single writer** (Schwartz)
- **Node.js version matters more than SQLite config** — v24 57% slower than v20 (Forward Email)

See [ARTICLE.md](../ARTICLE.md) sections "Surprising Findings From the Literature" and "How Our Numbers Compare to the Industry".
