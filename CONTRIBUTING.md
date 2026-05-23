# Contributing

Issues and PRs welcome.

## Particularly interested in

- **Results on other hardware tiers** — cloud VMs, ARM (M1, Graviton), spinning disk, eMMC. Open an issue with your `results.json` + system info per [docs/reproducing.md](docs/reproducing.md).
- **Other ORMs** — Peewee, Tortoise, SQLModel. Same benchmark harness, different `paths.py` implementation. PR welcome.
- **Other databases** — DuckDB, Postgres (libpq vs psycopg vs SQLAlchemy). Natural extension.
- **Bug fixes** — particularly around result aggregation, percentile math, and the edge case where checkpoints fall inside a single chunk.

## Setup

```bash
git clone https://github.com/TanayK07/sqlite-orm-bench.git
cd sqlite-orm-bench
pip install -e ".[dev]"
```

## Code style

- Black with line-length 100
- Ruff for linting
- Python 3.11+ syntax (`str | None`, not `Optional[str]`)
- PEP 604 unions everywhere

```bash
black sqlite_bench/
ruff check sqlite_bench/
```

## Running tests

```bash
# Fast smoke test
python -m sqlite_bench.before_after --scales 10K --mode both

# Full validation (≈ 5 hours, don't do this on CI)
python -m sqlite_bench.scale_benchmark --scales 3M,5M,10M --configs all
```

## PR checklist

- [ ] Smoke test passes locally
- [ ] No new wall-finishing or project-specific references
- [ ] Type hints use PEP 604 syntax
- [ ] No `print()` outside of CLI entry points (use the existing checkpoint printing helpers)
- [ ] If adding a new config: include rationale in PR description
