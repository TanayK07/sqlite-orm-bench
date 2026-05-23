"""Background process and SQLite file-size sampler.

Spawns a thread that captures RSS, CPU, DB/WAL file size, and SQLite
internals (page_count, fragmentation) at a fixed interval.
"""

import os
import sqlite3
import subprocess
import threading
import time

import psutil


class BenchmarkMonitor:
    """Background sampler — start() / stop() returns samples list."""

    def __init__(self, db_path: str, interval: float = 1.0):
        self.db_path = db_path
        self.wal_path = db_path + "-wal"
        self.interval = interval
        self.process = psutil.Process(os.getpid())
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock_errors = 0
        self._interface_errors = 0

    def record_error(self, error_type: str) -> None:
        if "InterfaceError" in error_type:
            self._interface_errors += 1
        elif "OperationalError" in error_type or "locked" in error_type:
            self._lock_errors += 1

    def start(self) -> None:
        self.process.cpu_percent()
        psutil.cpu_percent(percpu=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> list[dict]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        return self.samples

    def _collect_sqlite_metrics(self) -> dict:
        metrics = {}
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=2)
            try:
                metrics["page_count"] = conn.execute("PRAGMA page_count").fetchone()[0]
                metrics["freelist_count"] = conn.execute(
                    "PRAGMA freelist_count"
                ).fetchone()[0]
                metrics["page_size"] = conn.execute("PRAGMA page_size").fetchone()[0]
                if metrics["page_count"] > 0:
                    metrics["fragmentation_pct"] = round(
                        metrics["freelist_count"] / metrics["page_count"] * 100, 2
                    )
                else:
                    metrics["fragmentation_pct"] = 0.0
            finally:
                conn.close()
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            pass
        return metrics

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                sample: dict = {"timestamp": time.time()}
                mem = self.process.memory_info()
                sample["rss_mb"] = round(mem.rss / (1024 * 1024), 1)
                sample["cpu_pct"] = self.process.cpu_percent()
                sample["cpu_per_core"] = psutil.cpu_percent(percpu=True)

                try:
                    pio = self.process.io_counters()
                    sample["proc_read_mb"] = round(pio.read_bytes / (1024 * 1024), 1)
                    sample["proc_write_mb"] = round(pio.write_bytes / (1024 * 1024), 1)
                except (psutil.AccessDenied, AttributeError):
                    sample["proc_read_mb"] = 0
                    sample["proc_write_mb"] = 0

                sample["db_size_mb"] = (
                    round(os.path.getsize(self.db_path) / (1024 * 1024), 2)
                    if os.path.exists(self.db_path)
                    else 0
                )
                sample["wal_size_mb"] = (
                    round(os.path.getsize(self.wal_path) / (1024 * 1024), 2)
                    if os.path.exists(self.wal_path)
                    else 0
                )

                sample.update(self._collect_sqlite_metrics())
                sample["lock_errors"] = self._lock_errors
                sample["interface_errors"] = self._interface_errors

                self.samples.append(sample)
            except Exception:
                pass

            self._stop.wait(self.interval)


def collect_system_info() -> dict:
    """Capture host metadata for inclusion in result JSON."""
    info = {
        "cpu_count": psutil.cpu_count(logical=True),
        "cpu_physical": psutil.cpu_count(logical=False),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "python_pid": os.getpid(),
    }
    try:
        result = subprocess.run(
            ["lsblk", "-d", "-o", "NAME,SIZE,ROTA,MODEL", "--noheadings"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        info["storage_devices"] = result.stdout.strip()
    except Exception:
        info["storage_devices"] = "unknown"
    return info
