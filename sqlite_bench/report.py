"""Generate detailed HTML benchmark report from results JSON."""

import json
import os
from datetime import datetime


def _fmt_num(n: float, decimals: int = 1) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.{decimals}f}M"
    if n >= 1_000:
        return f"{n / 1_000:.{decimals}f}K"
    return f"{n:.{decimals}f}"


def _fmt_rows(n: int) -> str:
    if n >= 1_000_000:
        return f"{n // 1_000_000}M"
    if n >= 1_000:
        return f"{n // 1_000}K"
    return str(n)


def _fmt_time(seconds: float) -> str:
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"
    if seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    return f"{seconds:.1f}s"


COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6",
    "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#6366f1",
    "#84cc16",
]

CSS = """<style>
:root {
    --bg: #f8fafc; --card: #ffffff; --text: #1e293b; --muted: #64748b;
    --border: #e2e8f0; --accent: #3b82f6; --success: #22c55e;
    --warning: #f59e0b; --danger: #ef4444;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: var(--bg); color: var(--text); line-height: 1.6; }
.container { max-width: 1400px; margin: 0 auto; padding: 24px; }
h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
h2 { font-size: 22px; font-weight: 600; margin: 32px 0 16px; padding-bottom: 8px;
     border-bottom: 2px solid var(--accent); }
h3 { font-size: 18px; font-weight: 600; margin: 20px 0 12px; }
.subtitle { color: var(--muted); font-size: 14px; margin-bottom: 24px; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
             gap: 16px; margin-bottom: 24px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px;
        padding: 20px; }
.card .label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;
               color: var(--muted); margin-bottom: 4px; }
.card .value { font-size: 28px; font-weight: 700; }
.card .detail { font-size: 12px; color: var(--muted); margin-top: 4px; }
.chart-container { background: var(--card); border: 1px solid var(--border);
                   border-radius: 12px; padding: 20px; margin-bottom: 24px; }
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
@media (max-width: 900px) { .chart-row { grid-template-columns: 1fr; } }
canvas { max-height: 400px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px 12px; text-align: right; border-bottom: 1px solid var(--border); }
th { background: #f1f5f9; font-weight: 600; text-transform: uppercase; font-size: 11px;
     letter-spacing: 0.05em; color: var(--muted); position: sticky; top: 0; }
td:first-child, th:first-child { text-align: left; }
tr:hover td { background: #f8fafc; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 12px;
              overflow-x: auto; margin-bottom: 24px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px;
         font-weight: 600; }
.badge-success { background: #dcfce7; color: #166534; }
.badge-warning { background: #fef3c7; color: #92400e; }
.badge-danger { background: #fee2e2; color: #991b1b; }
.findings { background: var(--card); border: 1px solid var(--border); border-radius: 12px;
            padding: 20px; margin-bottom: 24px; }
.findings li { margin-bottom: 8px; }
.config-tag { display: inline-block; background: #eff6ff; color: #1d4ed8; padding: 1px 6px;
              border-radius: 4px; font-size: 12px; font-weight: 600; font-family: monospace; }
.header-bar { display: flex; justify-content: space-between; align-items: flex-start;
              flex-wrap: wrap; margin-bottom: 24px; }
.sys-info { font-size: 12px; color: var(--muted); text-align: right; }
.sys-info span { display: block; }
.perf-bar { height: 6px; border-radius: 3px; background: var(--border); margin-top: 6px; }
.perf-fill { height: 100%; border-radius: 3px; }
</style>"""


def generate_html_report(results_data: dict, output_path: str) -> str:
    html = _build_html(results_data)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path


def _build_html(data: dict) -> str:
    sys_info = data.get("system_info", {})
    results = data.get("results", [])
    configs = data.get("configs", {})
    generated_at = data.get("generated_at", datetime.now().isoformat())
    total_runtime = data.get("total_runtime_sec", 0)

    by_config: dict[str, list] = {}
    by_checkpoint: dict[int, list] = {}
    for r in results:
        by_config.setdefault(r["config_name"], []).append(r)
        by_checkpoint.setdefault(r["checkpoint_rows"], []).append(r)

    checkpoints = sorted(by_checkpoint.keys())
    config_names = sorted(by_config.keys())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SQLite Benchmark Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
{CSS}
</head>
<body>
<div class="container">
{_build_header(sys_info, generated_at, total_runtime, results)}
{_build_summary_cards(results, checkpoints, config_names)}
{_build_findings(results, by_config, configs, checkpoints)}
<h2>Throughput Overview</h2>
<div class="chart-row">
<div class="chart-container"><canvas id="throughputChart"></canvas></div>
<div class="chart-container"><canvas id="scalingChart"></canvas></div>
</div>
<h2>Latency Analysis</h2>
<div class="chart-row">
<div class="chart-container"><canvas id="latencyChart"></canvas></div>
<div class="chart-container"><canvas id="latencyScalingChart"></canvas></div>
</div>
<h2>Resource Usage</h2>
<div class="chart-row">
<div class="chart-container"><canvas id="rssChart"></canvas></div>
<div class="chart-container"><canvas id="dbSizeChart"></canvas></div>
</div>
{_build_config_table(configs)}
{_build_results_table(results, checkpoints, config_names)}
{_build_latency_table(results, checkpoints, config_names)}
{_build_resource_table(results, checkpoints, config_names)}
</div>
<script>
const RESULTS = {json.dumps(results)};
const CONFIGS = {json.dumps(config_names)};
const CHECKPOINTS = {json.dumps(checkpoints)};
const COLORS = {json.dumps(COLORS[:len(config_names)])};
{_build_chart_js()}
</script>
</body>
</html>"""


def _build_header(sys_info: dict, generated_at: str, total_runtime: float,
                  results: list) -> str:
    total_rows = sum(r.get("checkpoint_rows", 0) for r in results)
    total_configs = len(set(r["config_name"] for r in results))
    total_checkpoints = len(set(r["checkpoint_rows"] for r in results))
    cpu = sys_info.get("cpu_count", "?")
    ram = sys_info.get("ram_total_gb", "?")
    storage = sys_info.get("storage_devices", "unknown")

    return f"""<div class="header-bar">
<div>
<h1>SQLite Benchmark Report</h1>
<div class="subtitle">Generated {generated_at[:19].replace('T', ' ')} &mdash;
{total_configs} configs &times; {total_checkpoints} scale(s) &mdash;
{_fmt_num(total_rows, 0)} total rows inserted &mdash; runtime {_fmt_time(total_runtime)}</div>
</div>
<div class="sys-info">
<span><strong>CPU:</strong> {cpu} cores</span>
<span><strong>RAM:</strong> {ram} GB</span>
<span><strong>Storage:</strong> {storage[:60]}</span>
</div>
</div>"""


def _build_summary_cards(results: list, checkpoints: list, config_names: list) -> str:
    if not results:
        return ""

    best_throughput = max(results, key=lambda r: r.get("cumulative_rows_per_sec", 0))
    lowest_p99 = min(results, key=lambda r: r.get("batch_p99_ms", float("inf")))
    total_errors = sum(r.get("total_errors", 0) for r in results)
    max_scale = max(r.get("checkpoint_rows", 0) for r in results)
    largest_results = [r for r in results if r["checkpoint_rows"] == max_scale]
    best_at_scale = max(largest_results,
                        key=lambda r: r.get("cumulative_rows_per_sec", 0)) if largest_results else best_throughput

    error_badge = "badge-success" if total_errors == 0 else "badge-danger"
    error_text = "Zero errors" if total_errors == 0 else f"{total_errors} errors"

    return f"""<div class="card-grid">
<div class="card">
<div class="label">Best Throughput</div>
<div class="value">{_fmt_num(best_throughput['cumulative_rows_per_sec'], 0)}/s</div>
<div class="detail"><span class="config-tag">{best_throughput['config_name']}</span>
at {_fmt_rows(best_throughput['checkpoint_rows'])} rows</div>
</div>
<div class="card">
<div class="label">Lowest Batch P99</div>
<div class="value">{lowest_p99.get('batch_p99_ms', 0):.0f}ms</div>
<div class="detail"><span class="config-tag">{lowest_p99['config_name']}</span>
at {_fmt_rows(lowest_p99['checkpoint_rows'])} rows</div>
</div>
<div class="card">
<div class="label">Best at Max Scale ({_fmt_rows(max_scale)})</div>
<div class="value">{_fmt_num(best_at_scale['cumulative_rows_per_sec'], 0)}/s</div>
<div class="detail"><span class="config-tag">{best_at_scale['config_name']}</span></div>
</div>
<div class="card">
<div class="label">Max Scale Tested</div>
<div class="value">{_fmt_rows(max_scale)}</div>
<div class="detail">{len(set(r['config_name'] for r in results))} configs tested</div>
</div>
<div class="card">
<div class="label">Error Status</div>
<div class="value"><span class="badge {error_badge}">{error_text}</span></div>
<div class="detail">Across all runs</div>
</div>
</div>"""


def _build_findings(results: list, by_config: dict, configs: dict,
                    checkpoints: list) -> str:
    if not results or not checkpoints:
        return ""

    findings = []

    max_cp = max(checkpoints)
    at_max = [r for r in results if r["checkpoint_rows"] == max_cp]
    if at_max:
        best = max(at_max, key=lambda r: r.get("cumulative_rows_per_sec", 0))
        worst = min(at_max, key=lambda r: r.get("cumulative_rows_per_sec", 0))
        findings.append(
            f"At <strong>{_fmt_rows(max_cp)}</strong> rows, "
            f"<span class='config-tag'>{best['config_name']}</span> leads at "
            f"<strong>{best['cumulative_rows_per_sec']:.0f} rows/s</strong>, "
            f"while <span class='config-tag'>{worst['config_name']}</span> trails at "
            f"{worst['cumulative_rows_per_sec']:.0f} rows/s "
            f"({(1 - worst['cumulative_rows_per_sec']/best['cumulative_rows_per_sec'])*100:.0f}% slower)."
        )

    if len(checkpoints) >= 2:
        min_cp = min(checkpoints)
        for cfg_name, cfg_results in by_config.items():
            early = [r for r in cfg_results if r["checkpoint_rows"] == min_cp]
            late = [r for r in cfg_results if r["checkpoint_rows"] == max_cp]
            if early and late:
                early_rps = early[0].get("cumulative_rows_per_sec", 0)
                late_rps = late[0].get("cumulative_rows_per_sec", 0)
                if early_rps > 0:
                    degradation = (1 - late_rps / early_rps) * 100
                    if degradation > 15:
                        findings.append(
                            f"<span class='config-tag'>{cfg_name}</span> shows "
                            f"<strong>{degradation:.0f}%</strong> throughput degradation "
                            f"from {_fmt_rows(min_cp)} to {_fmt_rows(max_cp)} rows."
                        )
                    elif degradation < -5:
                        findings.append(
                            f"<span class='config-tag'>{cfg_name}</span> actually "
                            f"<strong>speeds up {-degradation:.0f}%</strong> from "
                            f"{_fmt_rows(min_cp)} to {_fmt_rows(max_cp)} (warm cache effect)."
                        )

    error_configs = [r["config_name"] for r in results if r.get("total_errors", 0) > 0]
    if error_configs:
        findings.append(
            f"<span class='badge badge-danger'>Errors detected</span> in: "
            + ", ".join(f"<span class='config-tag'>{c}</span>" for c in set(error_configs))
        )
    elif results:
        findings.append(
            "<span class='badge badge-success'>Zero errors</span> across all configs "
            "and scales &mdash; QueuePool fix validated."
        )

    if not findings:
        return ""

    items = "\n".join(f"<li>{f}</li>" for f in findings)
    return f"""<h2>Key Findings</h2>
<div class="findings"><ul>{items}</ul></div>"""


def _build_config_table(configs: dict) -> str:
    if not configs:
        return ""

    rows = ""
    for name, c in sorted(configs.items()):
        rows += f"""<tr>
<td><span class="config-tag">{name}</span></td>
<td>{c.get('chunk_size', '-')}</td>
<td>{c.get('synchronous', '-')}</td>
<td>{_fmt_num(abs(c.get('cache_size', 0)), 0)} KB</td>
<td>{c.get('pool_size', '-')}</td>
<td>{_fmt_num(c.get('mmap_size', 0) / (1024*1024), 0)} MB</td>
<td>{c.get('busy_timeout', '-')}ms</td>
</tr>"""

    return f"""<h2>Configuration Details</h2>
<div class="table-wrap"><table>
<thead><tr><th>Config</th><th>Chunk Size</th><th>Synchronous</th>
<th>Cache</th><th>Pool Size</th><th>mmap</th><th>Busy Timeout</th></tr></thead>
<tbody>{rows}</tbody>
</table></div>"""


def _build_results_table(results: list, checkpoints: list, config_names: list) -> str:
    if not results:
        return ""

    rows = ""
    for cp in checkpoints:
        cp_results = sorted(
            [r for r in results if r["checkpoint_rows"] == cp],
            key=lambda r: -r.get("cumulative_rows_per_sec", 0),
        )
        for i, r in enumerate(cp_results):
            highlight = ' style="font-weight:600"' if i == 0 else ""
            errs = r.get("total_errors", 0)
            err_badge = (f'<span class="badge badge-danger">{errs}</span>'
                         if errs > 0 else f'<span class="badge badge-success">0</span>')
            seg_rps = r.get("segment_rows_per_sec", r.get("cumulative_rows_per_sec", 0))
            rows += f"""<tr{highlight}>
<td>{_fmt_rows(cp)}</td>
<td><span class="config-tag">{r['config_name']}</span></td>
<td>{r.get('cumulative_rows_per_sec', 0):,.0f}</td>
<td>{seg_rps:,.0f}</td>
<td>{_fmt_time(r.get('cumulative_time_sec', 0))}</td>
<td>{r.get('batch_count', 0)}</td>
<td>{err_badge}</td>
</tr>"""

    return f"""<h2>Throughput Results</h2>
<div class="table-wrap"><table>
<thead><tr><th>Scale</th><th>Config</th><th>Cumulative rows/s</th>
<th>Segment rows/s</th><th>Time</th><th>Batches</th><th>Errors</th></tr></thead>
<tbody>{rows}</tbody>
</table></div>"""


def _build_latency_table(results: list, checkpoints: list, config_names: list) -> str:
    if not results:
        return ""

    rows = ""
    for cp in checkpoints:
        cp_results = sorted(
            [r for r in results if r["checkpoint_rows"] == cp],
            key=lambda r: r.get("batch_p99_ms", float("inf")),
        )
        for r in cp_results:
            rows += f"""<tr>
<td>{_fmt_rows(cp)}</td>
<td><span class="config-tag">{r['config_name']}</span></td>
<td>{r.get('batch_p50_ms', 0):,.0f}</td>
<td>{r.get('batch_p95_ms', 0):,.0f}</td>
<td>{r.get('batch_p99_ms', 0):,.0f}</td>
<td>{r.get('batch_min_ms', 0):,.0f}</td>
<td>{r.get('batch_max_ms', 0):,.0f}</td>
<td>{r.get('read_p50_ms', 0):,.1f}</td>
<td>{r.get('read_p99_ms', 0):,.1f}</td>
</tr>"""

    return f"""<h2>Latency Details</h2>
<div class="table-wrap"><table>
<thead><tr><th>Scale</th><th>Config</th><th>Batch P50</th><th>Batch P95</th>
<th>Batch P99</th><th>Batch Min</th><th>Batch Max</th>
<th>Read P50</th><th>Read P99</th></tr></thead>
<tbody>{rows}</tbody>
</table></div>"""


def _build_resource_table(results: list, checkpoints: list, config_names: list) -> str:
    if not results:
        return ""

    rows = ""
    for cp in checkpoints:
        cp_results = sorted(
            [r for r in results if r["checkpoint_rows"] == cp],
            key=lambda r: r["config_name"],
        )
        for r in cp_results:
            rows += f"""<tr>
<td>{_fmt_rows(cp)}</td>
<td><span class="config-tag">{r['config_name']}</span></td>
<td>{r.get('peak_rss_mb', 0):,.0f}</td>
<td>{r.get('db_size_mb', 0):,.0f}</td>
<td>{r.get('max_wal_mb', 0):,.1f}</td>
<td>{r.get('total_errors', 0)}</td>
<td>{r.get('interface_errors', 0)}</td>
<td>{r.get('lock_errors', 0)}</td>
</tr>"""

    return f"""<h2>Resource &amp; Error Details</h2>
<div class="table-wrap"><table>
<thead><tr><th>Scale</th><th>Config</th><th>Peak RSS (MB)</th><th>DB Size (MB)</th>
<th>Max WAL (MB)</th><th>Total Errors</th><th>Interface Errs</th>
<th>Lock Errs</th></tr></thead>
<tbody>{rows}</tbody>
</table></div>"""


def _build_chart_js() -> str:
    return """
function groupBy(arr, key) {
    return arr.reduce((acc, item) => {
        (acc[item[key]] = acc[item[key]] || []).push(item);
        return acc;
    }, {});
}

function fmtRows(n) {
    if (n >= 1e6) return (n/1e6).toFixed(0) + 'M';
    if (n >= 1e3) return (n/1e3).toFixed(0) + 'K';
    return n.toString();
}

const byCheckpoint = groupBy(RESULTS, 'checkpoint_rows');
const byConfig = groupBy(RESULTS, 'config_name');

// 1. Throughput bar chart — per checkpoint, grouped by config
(function() {
    const labels = CHECKPOINTS.map(fmtRows);
    const datasets = CONFIGS.map((cfg, i) => ({
        label: cfg,
        backgroundColor: COLORS[i % COLORS.length],
        data: CHECKPOINTS.map(cp => {
            const match = RESULTS.find(r => r.config_name === cfg && r.checkpoint_rows === cp);
            return match ? Math.round(match.cumulative_rows_per_sec) : 0;
        })
    }));
    new Chart(document.getElementById('throughputChart'), {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: 'Throughput by Scale (rows/s)' },
                       legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'rows/s' } } }
        }
    });
})();

// 2. Scaling line chart — rows/s vs scale for each config
(function() {
    const datasets = CONFIGS.map((cfg, i) => {
        const cfgResults = (byConfig[cfg] || []).sort((a,b) => a.checkpoint_rows - b.checkpoint_rows);
        return {
            label: cfg,
            borderColor: COLORS[i % COLORS.length],
            backgroundColor: COLORS[i % COLORS.length] + '20',
            fill: false,
            tension: 0.3,
            data: cfgResults.map(r => ({ x: r.checkpoint_rows, y: Math.round(r.cumulative_rows_per_sec) }))
        };
    });
    new Chart(document.getElementById('scalingChart'), {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: 'Scaling Behavior (Throughput vs DB Size)' },
                       legend: { position: 'bottom' } },
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Rows in DB' },
                     ticks: { callback: fmtRows } },
                y: { beginAtZero: true, title: { display: true, text: 'rows/s' } }
            }
        }
    });
})();

// 3. Latency bar chart — p50/p95/p99 at max checkpoint
(function() {
    const maxCp = Math.max(...CHECKPOINTS);
    const atMax = RESULTS.filter(r => r.checkpoint_rows === maxCp)
                         .sort((a,b) => a.batch_p99_ms - b.batch_p99_ms);
    const labels = atMax.map(r => r.config_name);

    new Chart(document.getElementById('latencyChart'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'P50 (ms)', backgroundColor: '#3b82f6', data: atMax.map(r => r.batch_p50_ms || 0) },
                { label: 'P95 (ms)', backgroundColor: '#f59e0b', data: atMax.map(r => r.batch_p95_ms || 0) },
                { label: 'P99 (ms)', backgroundColor: '#ef4444', data: atMax.map(r => r.batch_p99_ms || 0) },
            ]
        },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: 'Batch Latency at ' + fmtRows(maxCp) + ' rows (ms)' },
                       legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'ms' } } }
        }
    });
})();

// 4. Latency scaling chart — p99 vs scale
(function() {
    const datasets = CONFIGS.map((cfg, i) => {
        const cfgResults = (byConfig[cfg] || []).sort((a,b) => a.checkpoint_rows - b.checkpoint_rows);
        return {
            label: cfg,
            borderColor: COLORS[i % COLORS.length],
            fill: false,
            tension: 0.3,
            data: cfgResults.map(r => ({ x: r.checkpoint_rows, y: r.batch_p99_ms || 0 }))
        };
    });
    new Chart(document.getElementById('latencyScalingChart'), {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: 'Batch P99 Latency vs DB Size' },
                       legend: { position: 'bottom' } },
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Rows in DB' },
                     ticks: { callback: fmtRows } },
                y: { beginAtZero: true, title: { display: true, text: 'P99 (ms)' } }
            }
        }
    });
})();

// 5. RSS chart — peak RSS vs scale
(function() {
    const datasets = CONFIGS.map((cfg, i) => {
        const cfgResults = (byConfig[cfg] || []).sort((a,b) => a.checkpoint_rows - b.checkpoint_rows);
        return {
            label: cfg,
            borderColor: COLORS[i % COLORS.length],
            fill: false,
            tension: 0.3,
            data: cfgResults.map(r => ({ x: r.checkpoint_rows, y: r.peak_rss_mb || 0 }))
        };
    });
    new Chart(document.getElementById('rssChart'), {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: 'Peak RSS Memory vs DB Size' },
                       legend: { position: 'bottom' } },
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Rows in DB' },
                     ticks: { callback: fmtRows } },
                y: { beginAtZero: true, title: { display: true, text: 'MB' } }
            }
        }
    });
})();

// 6. DB size chart
(function() {
    const datasets = CONFIGS.map((cfg, i) => {
        const cfgResults = (byConfig[cfg] || []).sort((a,b) => a.checkpoint_rows - b.checkpoint_rows);
        return {
            label: cfg,
            borderColor: COLORS[i % COLORS.length],
            fill: false,
            tension: 0.3,
            data: cfgResults.map(r => ({ x: r.checkpoint_rows, y: r.db_size_mb || 0 }))
        };
    });
    new Chart(document.getElementById('dbSizeChart'), {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: 'Database Size vs Rows Inserted' },
                       legend: { position: 'bottom' } },
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Rows in DB' },
                     ticks: { callback: fmtRows } },
                y: { beginAtZero: true, title: { display: true, text: 'MB' } }
            }
        }
    });
})();
"""


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m benchmarks.report <results.json> [output.html]")
        sys.exit(1)
    json_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else json_path.replace(".json", ".html")
    with open(json_path) as f:
        data = json.load(f)
    path = generate_html_report(data, output)
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
