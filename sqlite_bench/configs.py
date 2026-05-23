"""PRAGMA configuration presets and parametric sweeps."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkConfig:
    """Single SQLite configuration for benchmarking."""

    name: str
    chunk_size: int = 5000
    synchronous: str = "NORMAL"
    cache_size: int = -4096
    pool_size: int = 5
    max_overflow: int = 5
    mmap_size: int = 0
    busy_timeout: int = 10000
    journal_mode: str = "WAL"
    temp_store: str = "MEMORY"


PRESETS: dict[str, BenchmarkConfig] = {
    "baseline": BenchmarkConfig(
        name="baseline",
        chunk_size=5000,
        synchronous="NORMAL",
        cache_size=-4096,
        pool_size=5,
        mmap_size=0,
    ),
    "optimized": BenchmarkConfig(
        name="optimized",
        chunk_size=10000,
        synchronous="NORMAL",
        cache_size=-64000,
        pool_size=5,
        mmap_size=268435456,
    ),
    "aggressive": BenchmarkConfig(
        name="aggressive",
        chunk_size=25000,
        synchronous="OFF",
        cache_size=-256000,
        pool_size=5,
        mmap_size=268435456,
    ),
}


def build_chunk_sweep() -> list[BenchmarkConfig]:
    """Parametric sweep over chunk_size with all other knobs fixed."""
    return [
        BenchmarkConfig(
            name=f"chunk_{size}",
            chunk_size=size,
            synchronous="NORMAL",
            cache_size=-64000,
            pool_size=5,
            mmap_size=268435456,
        )
        for size in [1000, 5000, 10000, 25000, 50000]
    ]


def build_pool_sweep(best_chunk: int = 10000) -> list[BenchmarkConfig]:
    """Parametric sweep over pool_size."""
    return [
        BenchmarkConfig(
            name=f"pool_{ps}",
            chunk_size=best_chunk,
            synchronous="NORMAL",
            cache_size=-64000,
            pool_size=ps,
            mmap_size=268435456,
        )
        for ps in [3, 5, 8]
    ]


def get_sweep_configs(sweep: str) -> list[BenchmarkConfig]:
    """Return configs for a named sweep.

    sweep:
        "presets" — baseline, optimized, aggressive
        "chunks"  — chunk_size 1K, 5K, 10K, 25K, 50K
        "pools"   — pool_size 3, 5, 8
        "all"     — presets + chunks + pools (11 configs)
    """
    if sweep == "presets":
        return list(PRESETS.values())
    if sweep == "chunks":
        return build_chunk_sweep()
    if sweep == "pools":
        return build_pool_sweep()
    if sweep == "all":
        return list(PRESETS.values()) + build_chunk_sweep() + build_pool_sweep()
    raise ValueError(f"Unknown sweep: {sweep}")
