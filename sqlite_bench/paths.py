"""ORM and raw write paths used by the benchmarks.

orm_insert / orm_upsert  → SQLAlchemy bulk_save_objects + on_conflict_do_update
raw_insert / raw_upsert  → sqlite3.executemany via the dbapi connection
"""

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .schema import INSERT_SQL, UPSERT_SQL, BenchRow, row_to_tuple


def orm_insert(session: Session, rows: list[dict]) -> None:
    """ORM bulk insert via bulk_save_objects + commit."""
    session.bulk_save_objects([BenchRow(**row) for row in rows])
    session.commit()


def orm_upsert(session: Session, rows: list[dict]) -> None:
    """ORM upsert using sqlite_insert().on_conflict_do_update()."""
    stmt = sqlite_insert(BenchRow).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["tenant_id", "entity_id", "sub_entity_id", "bucket_index"],
        set_={
            "measurement_x": stmt.excluded.measurement_x,
            "measurement_y": stmt.excluded.measurement_y,
            "measurement_z": stmt.excluded.measurement_z,
            "category_id": stmt.excluded.category_id,
            "weight": stmt.excluded.weight,
            "status": stmt.excluded.status,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    session.execute(stmt)
    session.commit()


def raw_insert(session: Session, rows: list[dict]) -> None:
    """Raw executemany — bypasses SQLAlchemy ORM entirely."""
    raw_conn = session.connection().connection.dbapi_connection
    tuples = [row_to_tuple(r) for r in rows]
    raw_conn.executemany(INSERT_SQL, tuples)
    session.commit()


def raw_upsert(session: Session, rows: list[dict]) -> None:
    """Raw executemany upsert with ON CONFLICT DO UPDATE."""
    raw_conn = session.connection().connection.dbapi_connection
    tuples = [row_to_tuple(r) for r in rows]
    raw_conn.executemany(UPSERT_SQL, tuples)
    session.commit()
