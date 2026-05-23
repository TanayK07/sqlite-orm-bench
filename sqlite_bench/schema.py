"""Generic benchmark schema.

Designed to mimic a realistic production table:
  - UUID primary key
  - Multi-column unique index for upsert testing
  - Mix of integers, floats, strings, timestamps
  - ~500 bytes per row
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase

metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


class BenchRow(Base):
    """Benchmark row — represents a single record in the test table.

    Schema chosen to be representative of production workloads:
      - Composite uniqueness (tenant + entity + sub-entity + index)
      - Numeric measurements
      - Categorical fields
      - Tracking timestamps
    """

    __tablename__ = "bench_rows"

    row_id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False)
    sub_entity_id = Column(Integer, nullable=False)
    bucket_index = Column(Integer, nullable=False)

    measurement_x = Column(Float, nullable=False)
    measurement_y = Column(Float, nullable=False)
    measurement_z = Column(Float, nullable=False)

    category_id = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    status = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "entity_id",
            "sub_entity_id",
            "bucket_index",
            name="uq_bench_row_natural_key",
        ),
        Index("ix_bench_tenant_entity", "tenant_id", "entity_id"),
    )


INSERT_SQL = (
    "INSERT INTO bench_rows "
    "(row_id, tenant_id, entity_id, sub_entity_id, bucket_index, "
    "measurement_x, measurement_y, measurement_z, "
    "category_id, weight, status, created_at, updated_at) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


UPSERT_SQL = (
    "INSERT INTO bench_rows "
    "(row_id, tenant_id, entity_id, sub_entity_id, bucket_index, "
    "measurement_x, measurement_y, measurement_z, "
    "category_id, weight, status, created_at, updated_at) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
    "ON CONFLICT(tenant_id, entity_id, sub_entity_id, bucket_index) "
    "DO UPDATE SET "
    "measurement_x=excluded.measurement_x, "
    "measurement_y=excluded.measurement_y, "
    "measurement_z=excluded.measurement_z, "
    "category_id=excluded.category_id, "
    "weight=excluded.weight, "
    "status=excluded.status, "
    "updated_at=excluded.updated_at"
)


INSERT_COLUMNS: tuple[str, ...] = (
    "row_id",
    "tenant_id",
    "entity_id",
    "sub_entity_id",
    "bucket_index",
    "measurement_x",
    "measurement_y",
    "measurement_z",
    "category_id",
    "weight",
    "status",
    "created_at",
    "updated_at",
)


def row_to_tuple(row: dict) -> tuple:
    """Convert dict row → ordered tuple for executemany."""
    return tuple(row.get(col) for col in INSERT_COLUMNS)


def create_schema(engine) -> None:
    """Create tables on the given engine."""
    metadata.create_all(engine)
