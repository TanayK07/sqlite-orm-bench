# sqlite-orm-bench

> **SQLite handles 88K writes/sec. Your ORM caps at 3,800. PRAGMA tuning won't save you.**

A benchmark harness that quantifies the **ORM tax** on SQLite write performance at 10M–50M row scale. Run an 11-configuration sweep, or compare SQLAlchemy ORM vs raw `executemany` head-to-head. Reproduce our results on your hardware.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Read the article](https://img.shields.io/badge/article-ARTICLE.md-green.svg)](ARTICLE.md)

---

## Headline Results

| Path | 10M rows | 50M rows | p99 |
|------|----------|----------|-----|
| SQLAlchemy ORM | **3,696 r/s** (45 min) | **3,682 r/s** (3.8 hrs) | 1,492 ms |
| Raw `executemany` | **87,893 r/s** (1.9 min) | **65,742 r/s** (12.7 min) | 478 ms |
| **Speedup** | **23.8×** | **17.9×** | **3.1×** |

Across **11 PRAGMA configurations** (sync modes, cache sizes, pool sizes, mmap, chunk sizes), ORM throughput varied only **26%** (3,045–3,821 r/s). The database isn't your bottleneck — your ORM is.

Zero errors across 110 million rows. Every config. Every scale.

→ Full writeup: [**ARTICLE.md**](ARTICLE.md)

---

## What This Benchmarks

Two complementary harnesses:

1. **`scale_benchmark`** — Sweeps 11 SQLite configurations against a fixed scale (default 10M rows). Tests whether PRAGMA tuning matters.
2. **`before_after`** — Compares SQLAlchemy ORM vs raw `sqlite3.executemany` at multiple scales (default 10M and 50M). Measures the ORM overhead directly.

Both:
- Stream rows via a generator (constant memory regardless of scale)
- Capture checkpoint metrics (throughput, p50/p95/p99, RSS, DB size, errors)
- Save results as JSON with `--resume` support (50M ORM runs take 3+ hours; crashes happen)
- Generate HTML reports with Chart.js

---

## Quickstart

```bash
# Clone + install
git clone https://github.com/TanayK07/sqlite-orm-bench.git
cd sqlite-orm-bench
pip install -e .

# Smoke test (≈ 5 seconds)
python -m sqlite_bench.before_after --scales 10K --mode both

# ORM vs Raw at 10M (≈ 50 minutes)
python -m sqlite_bench.before_after --scales 10M --mode both

# Full 11-config sweep × 10M (≈ 5.5 hours)
python -m sqlite_bench.scale_benchmark --scales 3M,5M,10M --configs all

# Generate HTML report
python -m sqlite_bench.report results/scale/results.json
```

---

## Repo Layout

```
sqlite-orm-bench/
├── README.md                        # This file (hook + quickstart)
├── ARTICLE.md                       # Long-form writeup with industry comparison
├── LICENSE                          # MIT
├── pyproject.toml                   # Package metadata
├── sqlite_bench/                    # Python package
│   ├── schema.py                    # Generic benchmark table
│   ├── configs.py                   # PRAGMA presets + parametric sweeps
│   ├── engine.py                    # SQLAlchemy engine factories
│   ├── data_generator.py            # Streaming row generator
│   ├── paths.py                     # ORM + raw write paths
│   ├── monitor.py                   # RSS / CPU / DB-size sampler
│   ├── results.py                   # Percentiles + CSV/summary writers
│   ├── scale_benchmark.py           # CLI: config sweep
│   ├── before_after.py              # CLI: ORM vs raw comparison
│   └── report.py                    # HTML report generator
├── docs/
│   ├── methodology.md               # Test design + decisions
│   ├── findings.md                  # Detailed analysis
│   └── reproducing.md               # Hardware-by-hardware notes
├── examples/
│   └── hybrid_repository.py         # Production pattern: ORM for CRUD, raw for bulk
└── results/sample/                  # Our actual run data (10M + 50M)
    ├── scale_results.json
    ├── scale_report.html
    ├── before_after_results.json
    └── before_after_report.html
```

---

## Configurations Tested

11 configs cover the obvious axes any production engineer might tune:

| Group | Configs | What changes |
|-------|---------|--------------|
| **Presets** | `baseline`, `optimized`, `aggressive` | Realistic deployment profiles |
| **Chunk size sweep** | `chunk_1000` → `chunk_50000` | Transaction batching impact |
| **Pool size sweep** | `pool_3`, `pool_5`, `pool_8` | Connection-pool contention |

Each config defines: `chunk_size`, `synchronous`, `cache_size`, `pool_size`, `max_overflow`, `mmap_size`, `busy_timeout`, `journal_mode`, `temp_store`.

See [`sqlite_bench/configs.py`](sqlite_bench/configs.py) for defaults and how to add your own.

---

## Five Findings

1. **The ORM is the bottleneck, not SQLite.** 11 configs × 10M rows. Throughput varies only 26%. Raw `executemany` on the same hardware hits 87K r/s — 23× faster.
2. **PRAGMA tuning is irrelevant for ORM workloads.** `sync=OFF` doesn't help. 256MB mmap doesn't help. 8-connection pool doesn't help. The ORM consumes the CPU budget before I/O matters.
3. **Chunk size controls latency, not throughput.** p99 scales **66×** across chunk sizes (313 ms → 20,508 ms). Throughput drops only 20%. Use 1K–5K chunks for predictable latency.
4. **Baseline config wins.** `sync=NORMAL`, default cache, `pool=5`, `chunk=5000`. No exotic PRAGMAs needed. Matches production consensus across 7 referenced sources.
5. **QueuePool eliminates concurrency errors.** Zero `database is locked` errors across 110M rows. QueuePool serializes writes at the application level, matching the single-writer architecture every production SQLite deployment converges on.

→ Detailed analysis with industry comparison: [**ARTICLE.md**](ARTICLE.md)

---

## When to Bypass Your ORM

| Scenario | Recommendation |
|----------|---------------|
| Single-row CRUD | Use the ORM |
| < 1K rows per transaction | Use the ORM |
| 10K–1M bulk load | Consider raw SQL (5–10× faster) |
| > 1M bulk load | Use raw SQL (18–24× faster) |
| Sustained > 1K writes/sec | Use raw SQL (ORM caps at 3.8K) |

The hybrid pattern (ORM for normal CRUD, raw `executemany` for bulk paths) is in [`examples/hybrid_repository.py`](examples/hybrid_repository.py).

---

## Reproducing Our Numbers

Hardware we measured on:

| Component | Spec |
|-----------|------|
| CPU | 8-core / 16-thread |
| RAM | 23.2 GB DDR |
| Storage | Samsung 990 EVO Plus 1TB NVMe |
| OS | Linux 6.8.0 |
| Python | 3.11 |
| SQLAlchemy | 2.0 |

Your absolute numbers will differ on EBS, spinning disk, or eMMC — but the **relative findings** (ORM-to-raw ratio, config irrelevance, chunk-size effect on latency) should hold.

See [`docs/reproducing.md`](docs/reproducing.md) for storage-specific guidance.

---

## Acknowledgements

This benchmark draws on prior work from:

- [Expensify](https://use.expensify.com/blog/scaling-sqlite-to-4m-qps-on-a-single-server) — SQLite at 4M QPS
- [Ben Johnson / Litestream](https://fly.io/blog/all-in-on-sqlite-litestream/) — WAL semantics in production
- [Stephen Margheim / Fractaled Mind](https://fractaledmind.com/2024/04/15/sqlite-on-rails-the-how-and-why-of-optimal-performance/) — Rails 8 IMMEDIATE transactions
- [Evan Schwartz](https://emschwartz.me/psa-your-sqlite-connection-pool-might-be-ruining-your-write-performance/) — Connection-pool write contention
- [Shivek Khurana](https://shivekkhurana.com/blog/sqlite-in-production/) — WAL vs DELETE benchmarks
- [Forward Email](https://forwardemail.net/en/blog/docs/sqlite-performance-optimization-pragma-chacha20-production-guide) — PRAGMA deep dive

Full references in [ARTICLE.md](ARTICLE.md).

---

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome. Particularly interested in:
- Results on other hardware tiers (cloud, ARM, spinning disk)
- Other ORMs (Peewee, Tortoise, SQLModel) — same benchmark harness, different paths
- Other databases (DuckDB, Postgres) — would be a natural extension
