# Reproducing These Results

## Prerequisites

- Python 3.11+
- SQLAlchemy 2.0+
- psutil (for monitoring)
- 8+ GB RAM (for 50M scale runs)
- NVMe storage (for like-for-like comparison)

```bash
pip install -e .
# or
pip install -r requirements.txt
```

## Smoke Test

Verify the harness works in seconds:

```bash
python -m sqlite_bench.before_after --scales 10K --mode both
```

Expected output: raw mode ~50K r/s, ORM mode ~9K r/s. (Numbers will be inflated at 10K scale because of warm filesystem cache and no B-tree growth — meaningful comparison starts around 1M rows.)

## Realistic Runs

### ORM vs Raw at 10M (≈ 50 minutes)

```bash
python -m sqlite_bench.before_after \
    --scales 10M \
    --mode both \
    --output-dir results/before_after
```

### ORM vs Raw at 10M + 50M (≈ 4.5 hours)

```bash
python -m sqlite_bench.before_after \
    --scales 10M,50M \
    --mode both \
    --output-dir results/before_after
```

### Full 11-config sweep × 10M (≈ 5.5 hours)

```bash
python -m sqlite_bench.scale_benchmark \
    --scales 3M,5M,10M \
    --configs all \
    --output-dir results/scale
```

### Resume after interruption

```bash
python -m sqlite_bench.scale_benchmark \
    --scales 3M,5M,10M \
    --configs all \
    --resume results/scale/results.json \
    --output-dir results/scale
```

The harness skips configs that already have complete checkpoint data.

## Generating Reports

```bash
python -m sqlite_bench.report results/scale/results.json
# → produces results/scale/report.html
```

## Avoiding the Lid-Close Trap

Long benchmark runs on a laptop will fail if the lid closes and the machine suspends. Disable suspend before kicking off a multi-hour run:

```bash
gsettings set org.gnome.settings-daemon.plugins.power lid-close-ac-action 'nothing'
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
```

Restore afterward:

```bash
gsettings set org.gnome.settings-daemon.plugins.power lid-close-ac-action 'suspend'
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'suspend'
```

## Running in the Background

```bash
nohup python -m sqlite_bench.scale_benchmark \
    --scales 3M,5M,10M --configs all \
    --output-dir results/scale > results/scale/run.log 2>&1 &
```

Avoid piping to `head` or `tee` for monitoring — a closed pipe will kill the benchmark via SIGPIPE. Redirect to a log file and `tail -f` it.

## Hardware Expectations

### x86 NVMe (our reference)

| Path | 10M | 50M |
|------|-----|-----|
| ORM | ~3,700 r/s | ~3,700 r/s |
| Raw | ~88,000 r/s | ~66,000 r/s |

### x86 SATA SSD

Expect raw throughput to drop 30–50%. ORM throughput is largely CPU-bound and should stay close to NVMe numbers.

### EBS gp3 (3,000 IOPS baseline)

Expect raw to be heavily I/O-bound: 20K–30K r/s. The ORM ceiling will be unchanged (still CPU-bound).

### Spinning disk (rare in 2026 but still real)

Expect raw to drop to 5K–10K r/s at 10M, much worse at 50M. The B-tree growth penalty dominates. Don't put production SQLite on spinning disk.

### ARM (M1 Mac, Graviton)

Per [Marending](https://marending.dev/notes/sqlite-benchmarks/), ARM cores deliver 20–40% higher SQLite throughput at similar TDP. Expect raw at ~110K r/s, ORM still ~3,700 r/s (Python overhead doesn't favor ARM).

### eMMC / SD card

Don't.

## Reporting Your Results

If you run this on different hardware, please open an issue with:

- CPU model + core count
- RAM
- Storage type and model
- Filesystem (ext4, xfs, btrfs, apfs)
- Kernel version
- Python version
- SQLAlchemy version
- The `results.json` file
- The HTML report (optional)

I'm interested in building a cross-hardware comparison table.
