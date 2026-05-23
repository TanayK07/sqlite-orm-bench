"""Result aggregation, percentile math, CSV/summary writers."""

import csv
import os
from dataclasses import dataclass


@dataclass
class RunResult:
    config_name: str
    total_rows: int
    total_time_sec: float
    avg_rows_per_sec: float
    batch_latencies_ms: list[float]
    batch_p50_ms: float
    batch_p95_ms: float
    batch_p99_ms: float
    read_p50_ms: float
    read_p95_ms: float
    read_p99_ms: float
    max_wal_mb: float
    peak_rss_mb: float
    total_errors: int
    interface_errors: int
    lock_errors: int


def percentile(data: list[float], p: float) -> float:
    """Linear-interpolated percentile (matches numpy default)."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def write_metrics_csv(samples: list[dict], output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "metrics.csv")
    if not samples:
        return path

    all_keys: list[str] = []
    seen: set[str] = set()
    max_core_count = 0
    for sample in samples:
        for k in sample.keys():
            if k == "cpu_per_core":
                max_core_count = max(max_core_count, len(sample.get(k, [])))
                continue
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    flat_keys = list(all_keys)
    if max_core_count:
        flat_keys.extend([f"cpu_core_{i}" for i in range(max_core_count)])

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=flat_keys, extrasaction="ignore")
        writer.writeheader()
        for sample in samples:
            flat = {}
            for k, v in sample.items():
                if k == "cpu_per_core":
                    for i, cv in enumerate(v):
                        flat[f"cpu_core_{i}"] = cv
                else:
                    flat[k] = v
            writer.writerow(flat)
    return path


def write_latencies_csv(
    latencies_ms: list[float], output_dir: str, filename: str
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["batch_index", "latency_ms"])
        for i, lat in enumerate(latencies_ms):
            writer.writerow([i, round(lat, 2)])
    return path


def build_run_result(
    config_name: str,
    total_rows: int,
    total_time_sec: float,
    batch_latencies_ms: list[float],
    read_latencies_ms: list[float],
    monitor_samples: list[dict],
    interface_errors: int,
    lock_errors: int,
    total_errors: int,
) -> RunResult:
    return RunResult(
        config_name=config_name,
        total_rows=total_rows,
        total_time_sec=round(total_time_sec, 2),
        avg_rows_per_sec=(
            round(total_rows / total_time_sec, 1) if total_time_sec > 0 else 0
        ),
        batch_latencies_ms=batch_latencies_ms,
        batch_p50_ms=round(percentile(batch_latencies_ms, 50), 1),
        batch_p95_ms=round(percentile(batch_latencies_ms, 95), 1),
        batch_p99_ms=round(percentile(batch_latencies_ms, 99), 1),
        read_p50_ms=round(percentile(read_latencies_ms, 50), 1),
        read_p95_ms=round(percentile(read_latencies_ms, 95), 1),
        read_p99_ms=round(percentile(read_latencies_ms, 99), 1),
        max_wal_mb=max((s.get("wal_size_mb", 0) for s in monitor_samples), default=0),
        peak_rss_mb=max((s.get("rss_mb", 0) for s in monitor_samples), default=0),
        total_errors=total_errors,
        interface_errors=interface_errors,
        lock_errors=lock_errors,
    )


def write_summary(results: list[RunResult], output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "summary.csv")
    fields = [
        "config",
        "rows",
        "time_sec",
        "rows_per_sec",
        "batch_p50",
        "batch_p95",
        "batch_p99",
        "read_p50",
        "read_p95",
        "read_p99",
        "max_wal_mb",
        "peak_rss_mb",
        "errors",
        "interface_err",
        "lock_err",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "config": r.config_name,
                    "rows": r.total_rows,
                    "time_sec": r.total_time_sec,
                    "rows_per_sec": r.avg_rows_per_sec,
                    "batch_p50": r.batch_p50_ms,
                    "batch_p95": r.batch_p95_ms,
                    "batch_p99": r.batch_p99_ms,
                    "read_p50": r.read_p50_ms,
                    "read_p95": r.read_p95_ms,
                    "read_p99": r.read_p99_ms,
                    "max_wal_mb": r.max_wal_mb,
                    "peak_rss_mb": r.peak_rss_mb,
                    "errors": r.total_errors,
                    "interface_err": r.interface_errors,
                    "lock_err": r.lock_errors,
                }
            )

    txt_path = os.path.join(output_dir, "summary.txt")
    header = (
        f"{'Config':<20} {'rows/s':>10} {'batch_p50':>10} {'batch_p99':>10} "
        f"{'read_p99':>10} {'WAL_MB':>8} {'RSS_MB':>8} {'Errors':>7}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for r in results:
        lines.append(
            f"{r.config_name:<20} {r.avg_rows_per_sec:>10.0f} "
            f"{r.batch_p50_ms:>10.1f} {r.batch_p99_ms:>10.1f} "
            f"{r.read_p99_ms:>10.1f} {r.max_wal_mb:>8.1f} "
            f"{r.peak_rss_mb:>8.1f} {r.total_errors:>7d}"
        )
    lines.append(sep)

    summary_text = "\n".join(lines)
    with open(txt_path, "w") as f:
        f.write(summary_text + "\n")

    print("\n" + summary_text)
    return csv_path
