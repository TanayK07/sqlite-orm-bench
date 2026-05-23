"""Multi-config scale benchmark — single process, streaming generation.

Runs each configuration in `--configs` against the same row count, capturing
checkpoint metrics at 3M / 5M / 10M (configurable). Each config gets its own
fresh database file. Results saved as JSON for crash-recovery (`--resume`).

Usage:
    python -m sqlite_bench.scale_benchmark \\
        --scales 3M,5M,10M \\
        --configs all \\
        --output-dir results/scale
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .configs import BenchmarkConfig, get_sweep_configs
from .data_generator import streaming_chunks
from .engine import create_engine_for_config
from .monitor import collect_system_info
from .paths import orm_upsert
from .results import percentile
from .schema import create_schema


def parse_scales(s: str) -> list[int]:
    out = []
    for part in s.split(","):
        p = part.strip().upper()
        if p.endswith("M"):
            out.append(int(float(p[:-1]) * 1_000_000))
        elif p.endswith("K"):
            out.append(int(float(p[:-1]) * 1_000))
        else:
            out.append(int(p))
    return sorted(out)


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _db_size_mb(db_path: str) -> float:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        p = db_path + suffix
        if os.path.exists(p):
            total += os.path.getsize(p)
    return round(total / (1024 * 1024), 2)


def _rss_mb() -> float:
    try:
        import psutil
        return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return 0.0


def _capture_checkpoint(
    config_name: str,
    sorted_cps: list[int],
    cp_idx: int,
    overall_start: float,
    segment_start: float,
    segment_latencies: list[float],
    all_latencies: list[float],
    db_path: str,
    errors: int,
) -> dict:
    now = time.perf_counter()
    cp_rows = sorted_cps[cp_idx]
    cumulative_time = now - overall_start
    segment_time = now - segment_start
    seg = [l for l in segment_latencies if l > 0]
    full = [l for l in all_latencies if l > 0]
    prev = sorted_cps[cp_idx - 1] if cp_idx > 0 else 0

    return {
        "config_name": config_name,
        "checkpoint_rows": cp_rows,
        "cumulative_time_sec": round(cumulative_time, 2),
        "cumulative_rows_per_sec": round(cp_rows / cumulative_time, 1)
        if cumulative_time > 0
        else 0,
        "segment_rows": cp_rows - prev,
        "segment_time_sec": round(segment_time, 2),
        "segment_rows_per_sec": round((cp_rows - prev) / segment_time, 1)
        if segment_time > 0
        else 0,
        "batch_count": len(seg),
        "batch_p50_ms": round(percentile(seg, 50), 1) if seg else 0,
        "batch_p95_ms": round(percentile(seg, 95), 1) if seg else 0,
        "batch_p99_ms": round(percentile(seg, 99), 1) if seg else 0,
        "batch_avg_ms": round(sum(seg) / len(seg), 1) if seg else 0,
        "cumulative_batch_p50_ms": round(percentile(full, 50), 1) if full else 0,
        "cumulative_batch_p99_ms": round(percentile(full, 99), 1) if full else 0,
        "peak_rss_mb": _rss_mb(),
        "db_size_mb": _db_size_mb(db_path),
        "total_errors": errors,
    }


def _print_checkpoint(r: dict) -> None:
    print(
        f"  >>> CHECKPOINT {_fmt(r['checkpoint_rows'])}: "
        f"{r['cumulative_rows_per_sec']:,.0f} rows/s "
        f"(seg: {r['segment_rows_per_sec']:,.0f}) | "
        f"p99={r['batch_p99_ms']:.0f}ms | "
        f"db={r['db_size_mb']:.0f}MB | "
        f"rss={r['peak_rss_mb']:.0f}MB | "
        f"errors={r['total_errors']}"
    )


def run_config(
    config: BenchmarkConfig,
    db_path: str,
    target_rows: int,
    checkpoints: list[int],
) -> list[dict]:
    """Run one config to target_rows, capturing checkpoint metrics."""
    eng, SessionFactory = create_engine_for_config(config, db_path)
    create_schema(eng)

    print(f"\n{'=' * 70}")
    print(
        f"Config: {config.name} | target: {_fmt(target_rows)} rows | "
        f"checkpoints: {[_fmt(c) for c in checkpoints]}"
    )
    print(
        f"  chunk={config.chunk_size} sync={config.synchronous} "
        f"cache={config.cache_size} pool={config.pool_size} mmap={config.mmap_size}"
    )
    print("=" * 70)
    print("DB ready. Starting insertion...")

    session = SessionFactory()
    results: list[dict] = []
    inserted = 0
    overall_start = time.perf_counter()
    segment_start = overall_start
    segment_latencies: list[float] = []
    all_latencies: list[float] = []
    cp_idx = 0
    sorted_cps = sorted(checkpoints)
    errors = 0

    try:
        for chunk in streaming_chunks(target_rows, config.chunk_size):
            start = time.perf_counter()
            try:
                orm_upsert(session, chunk)
                elapsed_ms = (time.perf_counter() - start) * 1000
                inserted += len(chunk)
                segment_latencies.append(elapsed_ms)
                all_latencies.append(elapsed_ms)
            except Exception as e:
                session.rollback()
                errors += 1
                print(f"  Error: {e}")

            while cp_idx < len(sorted_cps) and inserted >= sorted_cps[cp_idx]:
                elapsed = time.perf_counter() - overall_start
                rate = inserted / elapsed if elapsed > 0 else 0
                print(
                    f"  {_fmt(inserted)} rows | {rate:,.0f} rows/s | "
                    f"{elapsed:.0f}s elapsed"
                )
                cp = _capture_checkpoint(
                    config.name,
                    sorted_cps,
                    cp_idx,
                    overall_start,
                    segment_start,
                    segment_latencies,
                    all_latencies,
                    db_path,
                    errors,
                )
                results.append(cp)
                _print_checkpoint(cp)
                segment_start = time.perf_counter()
                segment_latencies = []
                cp_idx += 1
    finally:
        session.close()
        eng.dispose()

    return results


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Multi-config SQLite scale benchmark"
    )
    ap.add_argument(
        "--scales",
        default="3M,5M,10M",
        help="Comma-separated checkpoint sizes (e.g. 3M,5M,10M)",
    )
    ap.add_argument(
        "--configs",
        default="all",
        choices=["presets", "chunks", "pools", "all"],
        help="Which sweep to run",
    )
    ap.add_argument(
        "--output-dir",
        default="results/scale",
        help="Directory for JSON results and DB files",
    )
    ap.add_argument(
        "--resume",
        default=None,
        help="Path to results.json from a prior run; configs with full checkpoint "
        "data are skipped",
    )
    args = ap.parse_args()

    checkpoints = parse_scales(args.scales)
    target = max(checkpoints)
    configs = get_sweep_configs(args.configs)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load resume state
    completed: set[str] = set()
    existing_results: list[dict] = []
    if args.resume and Path(args.resume).exists():
        with open(args.resume) as f:
            data = json.load(f)
        existing_results = data.get("results", [])
        per_cfg: dict[str, set[int]] = {}
        for r in existing_results:
            per_cfg.setdefault(r["config_name"], set()).add(r["checkpoint_rows"])
        for name, cps in per_cfg.items():
            if cps >= set(checkpoints):
                completed.add(name)
        if completed:
            print(f"Resuming. Skipping: {sorted(completed)}")

    sys_info = collect_system_info()
    all_results: list[dict] = list(existing_results)
    config_defs: dict[str, dict] = {}

    total_start = time.perf_counter()
    todo = [c for c in configs if c.name not in completed]
    for i, cfg in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] Starting {cfg.name}...")
        config_defs[cfg.name] = {
            "chunk_size": cfg.chunk_size,
            "synchronous": cfg.synchronous,
            "cache_size": cfg.cache_size,
            "pool_size": cfg.pool_size,
            "mmap_size": cfg.mmap_size,
            "busy_timeout": cfg.busy_timeout,
        }

        with tempfile.TemporaryDirectory(dir=str(output_dir), prefix=f"db_{cfg.name}_") as tmp:
            db_path = os.path.join(tmp, f"{cfg.name}.db")
            cfg_results = run_config(cfg, db_path, target, checkpoints)
            all_results.extend(cfg_results)

        # Save after each config — crash recovery
        out = {
            "system_info": sys_info,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_runtime_sec": round(time.perf_counter() - total_start, 1),
            "configs": config_defs,
            "checkpoints": checkpoints,
            "results": all_results,
        }
        with open(output_dir / "results.json", "w") as f:
            json.dump(out, f, indent=2)
        print(f"  Saved intermediate results to {output_dir / 'results.json'}")

    runtime_hours = (time.perf_counter() - total_start) / 3600
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {len(all_results)} results across {len(configs)} configs")
    print(f"Runtime: {runtime_hours:.1f} hours")
    print(f"JSON:   {output_dir / 'results.json'}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
