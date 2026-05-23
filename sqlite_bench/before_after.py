"""Before/After benchmark — SQLAlchemy ORM vs raw sqlite3.executemany.

Runs two paths back-to-back against fresh databases:
    BEFORE (ORM):  bulk_save_objects + on_conflict_do_update
    AFTER (Raw):   sqlite3.executemany INSERT / UPSERT

Captures checkpoint metrics at the specified scales. Results saved as JSON.

Usage:
    python -m sqlite_bench.before_after \\
        --scales 10M,50M \\
        --mode both \\
        --output-dir results/before_after
"""

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from .data_generator import streaming_chunks
from .engine import create_engine_static, create_engine_for_config
from .configs import BenchmarkConfig
from .monitor import collect_system_info
from .paths import orm_insert, orm_upsert, raw_insert, raw_upsert
from .results import percentile
from .schema import create_schema


ORM_CHUNK_SIZE = 5_000
RAW_CHUNK_SIZE = 50_000

# Production-optimal "after" config (matches our paper's recommendation)
AFTER_CONFIG = BenchmarkConfig(
    name="after",
    chunk_size=RAW_CHUNK_SIZE,
    synchronous="NORMAL",
    cache_size=-4096,
    pool_size=5,
    mmap_size=0,
    busy_timeout=30000,
)


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


def _capture(
    mode: str,
    sorted_cps: list[int],
    cp_idx: int,
    overall_start: float,
    segment_start: float,
    seg_lat: list[float],
    all_lat: list[float],
    db_path: str,
) -> dict:
    now = time.perf_counter()
    cp_rows = sorted_cps[cp_idx]
    ct = now - overall_start
    st = now - segment_start
    seg = [l for l in seg_lat if l > 0]
    full = [l for l in all_lat if l > 0]
    prev = sorted_cps[cp_idx - 1] if cp_idx > 0 else 0

    return {
        "mode": mode,
        "checkpoint_rows": cp_rows,
        "cumulative_time_sec": round(ct, 2),
        "cumulative_rows_per_sec": round(cp_rows / ct, 1) if ct > 0 else 0,
        "segment_rows": cp_rows - prev,
        "segment_time_sec": round(st, 2),
        "segment_rows_per_sec": round((cp_rows - prev) / st, 1) if st > 0 else 0,
        "batch_count": len(seg),
        "batch_p50_ms": round(percentile(seg, 50), 1) if seg else 0,
        "batch_p95_ms": round(percentile(seg, 95), 1) if seg else 0,
        "batch_p99_ms": round(percentile(seg, 99), 1) if seg else 0,
        "batch_avg_ms": round(sum(seg) / len(seg), 1) if seg else 0,
        "cumulative_p50_ms": round(percentile(full, 50), 1) if full else 0,
        "cumulative_p99_ms": round(percentile(full, 99), 1) if full else 0,
        "peak_rss_mb": _rss_mb(),
        "db_size_mb": _db_size_mb(db_path),
    }


def _print(tag: str, r: dict) -> None:
    print(
        f"  >>> [{tag}] CHECKPOINT {_fmt(r['checkpoint_rows'])}: "
        f"{r['cumulative_rows_per_sec']:,.0f} r/s "
        f"(seg: {r['segment_rows_per_sec']:,.0f}) | "
        f"p99={r['batch_p99_ms']:.0f}ms | "
        f"db={r['db_size_mb']:.0f}MB | "
        f"rss={r['peak_rss_mb']:.0f}MB"
    )


def _ensure_dedup_index(session) -> None:
    """Create the upsert conflict index after the first insert."""
    session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_bench_natural_key "
            "ON bench_rows "
            "(tenant_id, entity_id, sub_entity_id, bucket_index)"
        )
    )
    session.commit()


def run_orm(db_path: str, total_rows: int, checkpoints: list[int]) -> list[dict]:
    """ORM path: bulk_save_objects first, then on_conflict_do_update."""
    eng, SessionFactory = create_engine_static(db_path, busy_timeout=5000)
    create_schema(eng)
    print(f"  [ORM] target: {_fmt(total_rows)} rows, "
          f"checkpoints: {[_fmt(c) for c in checkpoints]}")

    session = SessionFactory()
    results: list[dict] = []
    inserted = 0
    overall_start = time.perf_counter()
    segment_start = overall_start
    seg_lat: list[float] = []
    all_lat: list[float] = []
    cp_idx = 0
    sorted_cps = sorted(checkpoints)
    is_first = True

    try:
        for chunk in streaming_chunks(total_rows, ORM_CHUNK_SIZE):
            start = time.perf_counter()
            try:
                if is_first:
                    orm_insert(session, chunk)
                    _ensure_dedup_index(session)
                    is_first = False
                else:
                    orm_upsert(session, chunk)
                elapsed_ms = (time.perf_counter() - start) * 1000
                inserted += len(chunk)
                seg_lat.append(elapsed_ms)
                all_lat.append(elapsed_ms)
            except Exception as e:
                session.rollback()
                print(f"  [ORM] error: {e}")
                is_first = False

            while cp_idx < len(sorted_cps) and inserted >= sorted_cps[cp_idx]:
                cp = _capture("orm", sorted_cps, cp_idx, overall_start,
                              segment_start, seg_lat, all_lat, db_path)
                results.append(cp)
                _print("ORM", cp)
                segment_start = time.perf_counter()
                seg_lat = []
                cp_idx += 1
    finally:
        session.close()
        eng.dispose()
    return results


def run_raw(db_path: str, total_rows: int, checkpoints: list[int]) -> list[dict]:
    """Raw path: sqlite3.executemany via dbapi connection."""
    eng, SessionFactory = create_engine_for_config(AFTER_CONFIG, db_path)
    create_schema(eng)
    print(f"  [RAW] target: {_fmt(total_rows)} rows, "
          f"checkpoints: {[_fmt(c) for c in checkpoints]}")

    session = SessionFactory()
    results: list[dict] = []
    inserted = 0
    overall_start = time.perf_counter()
    segment_start = overall_start
    seg_lat: list[float] = []
    all_lat: list[float] = []
    cp_idx = 0
    sorted_cps = sorted(checkpoints)
    is_first = True

    try:
        for chunk in streaming_chunks(total_rows, RAW_CHUNK_SIZE):
            start = time.perf_counter()
            if is_first:
                raw_insert(session, chunk)
                _ensure_dedup_index(session)
                is_first = False
            else:
                raw_upsert(session, chunk)
            elapsed_ms = (time.perf_counter() - start) * 1000
            inserted += len(chunk)
            seg_lat.append(elapsed_ms)
            all_lat.append(elapsed_ms)

            while cp_idx < len(sorted_cps) and inserted >= sorted_cps[cp_idx]:
                cp = _capture("raw", sorted_cps, cp_idx, overall_start,
                              segment_start, seg_lat, all_lat, db_path)
                results.append(cp)
                _print("RAW", cp)
                segment_start = time.perf_counter()
                seg_lat = []
                cp_idx += 1
    finally:
        session.close()
        eng.dispose()
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="ORM vs Raw SQL SQLite benchmark")
    ap.add_argument("--scales", default="10M,50M",
                    help="Comma-separated row counts (e.g. 10M,50M,100M)")
    ap.add_argument("--mode", choices=["orm", "raw", "both"], default="both",
                    help="Which path(s) to run")
    ap.add_argument("--output-dir", default="results/before_after",
                    help="Output directory for results.json")
    ap.add_argument("--resume", default=None,
                    help="Path to results.json — modes with full checkpoint data are skipped")
    args = ap.parse_args()

    checkpoints = parse_scales(args.scales)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    completed_modes: set[str] = set()
    existing_results: list[dict] = []
    if args.resume and Path(args.resume).exists():
        with open(args.resume) as f:
            data = json.load(f)
        existing_results = data.get("results", [])
        per_mode: dict[str, set[int]] = {}
        for r in existing_results:
            per_mode.setdefault(r["mode"], set()).add(r["checkpoint_rows"])
        for mode, cps in per_mode.items():
            if cps >= set(checkpoints):
                completed_modes.add(mode)
        if completed_modes:
            print(f"Resuming. Skipping: {sorted(completed_modes)}")

    sys_info = collect_system_info()
    all_results: list[dict] = list(existing_results)

    modes_to_run: list[str] = []
    if args.mode in ("raw", "both") and "raw" not in completed_modes:
        modes_to_run.append("raw")
    if args.mode in ("orm", "both") and "orm" not in completed_modes:
        modes_to_run.append("orm")

    total_start = time.perf_counter()
    for mode in modes_to_run:
        max_target = max(checkpoints)
        with tempfile.TemporaryDirectory(dir=str(output_dir), prefix=f"db_{mode}_") as tmp:
            db_path = os.path.join(tmp, f"{mode}.db")
            print(f"\n{'=' * 70}\n{mode.upper()} run | {_fmt(max_target)} rows\n{'=' * 70}")
            if mode == "orm":
                cp_results = run_orm(db_path, max_target, checkpoints)
            else:
                cp_results = run_raw(db_path, max_target, checkpoints)
            all_results.extend(cp_results)

        out = {
            "system_info": sys_info,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_runtime_sec": round(time.perf_counter() - total_start, 1),
            "checkpoints": checkpoints,
            "results": all_results,
        }
        with open(output_dir / "results.json", "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nSaved {output_dir / 'results.json'}")

    runtime_min = (time.perf_counter() - total_start) / 60
    print(f"\n{'=' * 70}\nCOMPLETE — runtime {runtime_min:.1f} min\n{'=' * 70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
