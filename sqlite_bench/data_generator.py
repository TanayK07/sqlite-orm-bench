"""Streaming row generator.

Produces unique benchmark rows on demand with constant memory.
Each chunk yielded contains `chunk_size` rows with deterministic-but-unique
natural keys, so upsert benchmarks can re-insert the same keys.
"""

import random
from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4


def _generate_row(
    tenant_id: str, entity_id: int, sub_entity_id: int, bucket_index: int
) -> dict:
    """Build one row with a unique natural key tuple."""
    return {
        "row_id": str(uuid4()),
        "tenant_id": tenant_id,
        "entity_id": entity_id,
        "sub_entity_id": sub_entity_id,
        "bucket_index": bucket_index,
        "measurement_x": round(random.uniform(-1000, 1000), 6),
        "measurement_y": round(random.uniform(-1000, 1000), 6),
        "measurement_z": round(random.uniform(0, 100), 6),
        "category_id": random.randint(0, 4),
        "weight": round(random.betavariate(5.0, 2.0), 4),
        "status": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }


def streaming_chunks(
    total_rows: int,
    chunk_size: int,
    tenant_id: str | None = None,
    deterministic: bool = True,
) -> Generator[list[dict], None, None]:
    """Yield chunks of unique rows. Constant memory regardless of total_rows.

    Natural-key layout (tenant, entity, sub_entity, bucket) is deterministic so
    re-running the same generator with the same tenant_id produces conflicting
    rows for upsert benchmarks.

    Args:
        total_rows: Total rows to generate across all chunks.
        chunk_size: Rows per yielded chunk.
        tenant_id: Override tenant_id; auto-generated if None.
        deterministic: If True, walk natural keys in a fixed pattern.
                       If False, use random keys (rarely useful — disables upsert collisions).
    """
    if tenant_id is None:
        tenant_id = str(uuid4())

    generated = 0
    counter = 0

    # Walk natural keys: 1000 entities × 1000 sub-entities × N buckets
    while generated < total_rows:
        remaining = min(chunk_size, total_rows - generated)
        rows: list[dict] = []

        for _ in range(remaining):
            if deterministic:
                entity_id = counter % 1000
                sub_entity_id = (counter // 1000) % 1000
                bucket_index = counter // 1_000_000
            else:
                entity_id = random.randint(0, 999)
                sub_entity_id = random.randint(0, 999)
                bucket_index = random.randint(0, 1_000_000)

            rows.append(
                _generate_row(tenant_id, entity_id, sub_entity_id, bucket_index)
            )
            counter += 1

        generated += len(rows)
        yield rows


def get_tenant_id() -> str:
    """Helper for callers that want a stable tenant ID across runs."""
    return str(uuid4())
