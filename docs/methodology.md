# Methodology

This document describes the test design and the reasoning behind each decision.

## Two Complementary Benchmarks

### 1. Config Sweep (`scale_benchmark`)

**Question**: Does PRAGMA tuning affect ORM write throughput?

**Design**: One harness, 11 SQLite configurations, same row count (10M). Each config gets a freshly-created database, runs streaming inserts through SQLAlchemy's bulk path, captures checkpoint metrics at 3M / 5M / 10M.

**Why ORM-only here**: The point of this benchmark is to test whether config tuning *can* improve a typical Python-backed SQLite workload. If raw `executemany` is the answer, that's a different question (covered by Benchmark 2).

### 2. Before/After (`before_after`)

**Question**: How much throughput does the ORM leave on the table?

**Design**: Two paths run against fresh databases:
- **Before (ORM)**: SQLAlchemy `bulk_save_objects` + `on_conflict_do_update` via `sqlite_insert`. Uses the typical legacy production setup (`StaticPool`, `busy_timeout=5000`, default PRAGMAs).
- **After (Raw)**: `sqlite3.executemany` via the DBAPI connection. Uses our production-optimal config (`QueuePool`, `busy_timeout=30000`).

Both paths run insert-then-upsert at multiple checkpoint scales (default 10M, 50M).

**Why these two paths**: We wanted to bracket the realistic range. The ORM path represents what most Python services do. The raw path is the floor — anything slower is your code, not SQLite.

## What We Measure

| Metric | How |
|--------|-----|
| Throughput | `rows / elapsed_seconds`, both cumulative and per-segment |
| Latency p50/p95/p99 | Per-chunk wall time, linear-interpolated percentile |
| Peak RSS | `psutil.Process.memory_info().rss`, sampled every 1s |
| DB size | Sum of `.db`, `.db-wal`, `.db-shm` file sizes |
| Error count | Per-class: `OperationalError` (locks), `InterfaceError`, total |

## Data Generation

A streaming generator yields chunks of unique rows with deterministic natural keys (`tenant_id`, `entity_id`, `sub_entity_id`, `bucket_index`). Constant memory regardless of total scale.

Determinism is intentional: re-running with the same `tenant_id` produces *identical* natural keys, which lets the upsert path exercise actual ON CONFLICT behavior instead of always inserting fresh.

## What's NOT Measured

- **Read throughput**: Different benchmark, different conclusions. See Marending or Khurana (referenced in ARTICLE.md).
- **Mixed read/write workloads**: Workload-dependent; would require a synthetic OLTP harness.
- **Replication / streaming backup**: Out of scope. See Litestream / LiteFS.
- **Cross-database comparison**: Out of scope. We're measuring the ORM tax, not SQLite vs Postgres.

## Crash Recovery

Both benchmarks save results to JSON after each config (scale) or mode (before/after). The `--resume` flag skips configs/modes that already have complete checkpoint data.

This matters: a 50M ORM run takes ~3.8 hours. Laptop suspends, kernel reboots, and accidental SIGPIPE from piping output to `head` have all killed our runs at least once.

## Threading Model

Each benchmark runs in a **single process, single thread** for inserts. A background daemon thread samples `psutil` metrics every 1s. SQLite is fundamentally single-writer; multi-writer SQLite is a separate study.

## Hardware Sensitivity

All measurements were taken on:

- CPU: 8 physical cores / 16 logical
- RAM: 23.2 GB
- Storage: Samsung 990 EVO Plus 1TB NVMe (PCIe 4.0)
- OS: Linux 6.8.0

**Relative findings should hold across hardware**:
- ORM-to-raw ratio (~20×) is CPU-bound, not I/O-bound
- p99-vs-chunk-size relationship is transaction-time bound, not hardware-bound
- Config irrelevance for ORM holds because the ORM saturates Python before SQLite

**Absolute throughput will vary**:
- EBS gp3: expect 40–60% of NVMe
- Spinning disk: expect 5–10× lower writes
- ARM (M1, Graviton): expect 20–40% improvement (per Marending)
- eMMC / SD card: expect 20–50× lower writes

See [reproducing.md](reproducing.md) for hardware-specific notes.
