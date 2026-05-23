"""Production pattern: ORM for correctness, raw SQL for throughput.

The recommendation from our benchmarks isn't "drop your ORM" — it's
"add a raw fast-path for the hot bulk routes." This example shows how.

Single-row creates still flow through SQLAlchemy (gets you validation,
relationships, change tracking, the works). Bulk inserts/upserts bypass
the ORM and hit sqlite3.executemany directly.

Our measurements:
    session.add() loop:        ~250 r/s     (1×)
    bulk_save_objects:       ~3,700 r/s     (15×)
    raw executemany:        ~88,000 r/s     (350×)
"""

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from sqlite_bench.paths import raw_insert, raw_upsert
from sqlite_bench.schema import BenchRow


class BenchRepository:
    """Hybrid repository: ORM where it makes sense, raw SQL where it matters."""

    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────────────────────────────────────────────────
    # ORM path — use for: single CRUD, validation, relationship traversal
    # ────────────────────────────────────────────────────────────────────────

    def create(self, data: dict[str, Any]) -> BenchRow:
        """Single-row insert via the ORM. Use for normal CRUD."""
        obj = BenchRow(**data)
        self.db.add(obj)
        self.db.flush()
        return obj

    def get(self, row_id: str) -> BenchRow | None:
        """Single-row read."""
        return self.db.query(BenchRow).filter_by(row_id=row_id).first()

    def update(self, row_id: str, changes: dict[str, Any]) -> BenchRow | None:
        """Partial update. ORM gives you change tracking + validation."""
        obj = self.get(row_id)
        if obj is None:
            return None
        for k, v in changes.items():
            setattr(obj, k, v)
        self.db.flush()
        return obj

    def delete(self, row_id: str) -> bool:
        obj = self.get(row_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.flush()
        return True

    # ────────────────────────────────────────────────────────────────────────
    # Raw fast-path — use for: bulk inserts, ingestion jobs, ETL
    # ────────────────────────────────────────────────────────────────────────

    def bulk_insert_turbo(self, rows: Iterable[dict[str, Any]]) -> int:
        """Raw executemany — 18–24× faster than the ORM path.

        Bypasses object instantiation, attribute instrumentation, identity-map
        lookup, and unit-of-work bookkeeping. Use when you have thousands+
        rows to insert and don't need any of those features.

        Caller is responsible for chunking. Recommended: 5K rows per call
        for predictable p99 latency.
        """
        rows_list = list(rows)
        raw_insert(self.db, rows_list)
        return len(rows_list)

    def bulk_upsert_turbo(self, rows: Iterable[dict[str, Any]]) -> int:
        """Raw executemany upsert. Same speedup as bulk_insert_turbo."""
        rows_list = list(rows)
        raw_upsert(self.db, rows_list)
        return len(rows_list)


# Usage:
#
#     repo = BenchRepository(session)
#
#     # Normal CRUD — fine through ORM
#     row = repo.create({"row_id": "...", "tenant_id": "...", ...})
#
#     # Bulk ingest — use the fast path
#     for chunk in chunks_of_5000(incoming_data):
#         repo.bulk_insert_turbo(chunk)
