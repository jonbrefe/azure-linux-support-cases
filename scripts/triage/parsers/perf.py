"""Performance parser — sar, iostat, mpstat, vmstat (optional, behind flag)."""

import os
import re

from triage.common import read_file, extract_scc_command, make_warning


def parse(path, report_type, config=None):
    """Extract performance data from a sosreport or supportconfig directory.

    This parser is only active when config["enable_perf_parsing"] is True.

    Returns:
        dict with performance data, _sources, _warnings.
        Returns minimal dict if perf parsing is disabled.
    """
    if not config or not config.get("enable_perf_parsing"):
        return {"_sources": {}, "_warnings": [], "_skipped": True}

    if report_type == "sosreport":
        return _parse_sosreport(path)
    return _parse_supportconfig(path)


def _parse_sosreport(path):
    data = {
        "_sources": {},
        "_warnings": [],
    }

    # sar data — typically in sos_commands/sar/
    sar_dir = os.path.join(path, "sos_commands", "sar")
    if os.path.isdir(sar_dir):
        data["_sources"]["sar"] = "sos_commands/sar/"
        # Look for sar text output files
        for fname in sorted(os.listdir(sar_dir)):
            fpath = os.path.join(sar_dir, fname)
            if not os.path.isfile(fpath):
                continue
            content = read_file(fpath)
            if not content.strip():
                continue

            # CPU utilization summary from sar
            if "cpu" in fname.lower() or "sar" in fname.lower():
                cpu_summary = _extract_sar_cpu_summary(content)
                if cpu_summary:
                    data["sar_cpu"] = cpu_summary

            # IO stats from sar
            if "io" in fname.lower() or "disk" in fname.lower():
                io_summary = _extract_sar_io_summary(content)
                if io_summary:
                    data["sar_io"] = io_summary

    # vmstat from proc or sos_commands
    vmstat_path = os.path.join(path, "sos_commands", "process", "vmstat_-s")
    vmstat = read_file(vmstat_path)
    if vmstat.strip():
        data["vmstat_s"] = vmstat.strip()
        data["_sources"]["vmstat"] = "sos_commands/process/vmstat_-s"

    # uptime / load average (already in env, but check for historical)
    uptime = read_file(os.path.join(path, "uptime")).strip()
    if uptime:
        load_avg = _extract_load_average(uptime)
        if load_avg:
            data["load_average"] = load_avg

    # Warnings for high load
    if data.get("load_average"):
        avg_15 = data["load_average"].get("avg_15", 0)
        if avg_15 > 0:
            data["_warnings"].append(make_warning(
                "PERF",
                f"15-minute load average: {avg_15:.2f}",
                evidence=f"uptime shows load average {avg_15:.2f}",
                impact="High load may indicate CPU contention or I/O wait",
                next_step="Correlate with CPU count and check for I/O wait in sar/vmstat",
            ))

    return data


def _parse_supportconfig(path):
    data = {
        "_sources": {},
        "_warnings": [],
    }

    # basic-environment.txt may have vmstat, uptime
    basic = read_file(os.path.join(path, "basic-environment.txt"))

    # vmstat
    vmstat = extract_scc_command(basic, r"# /usr/bin/vmstat -s$")
    if not vmstat:
        vmstat = extract_scc_command(basic, r"# /bin/vmstat -s$")
    if vmstat.strip():
        data["vmstat_s"] = vmstat.strip()
        data["_sources"]["vmstat"] = "basic-environment.txt"

    # uptime / load
    uptime_text = extract_scc_command(basic, r"# /usr/bin/uptime$")
    if not uptime_text:
        uptime_text = extract_scc_command(basic, r"# /bin/uptime$")
    if uptime_text.strip():
        load_avg = _extract_load_average(uptime_text.strip())
        if load_avg:
            data["load_average"] = load_avg

    return data


def _extract_sar_cpu_summary(text):
    """Extract average CPU line from sar output."""
    for line in text.splitlines():
        if "Average" in line and "all" in line:
            parts = line.split()
            try:
                return {
                    "user": float(parts[2]),
                    "system": float(parts[4]),
                    "iowait": float(parts[5]),
                    "idle": float(parts[-1]),
                }
            except (IndexError, ValueError):
                pass
    return None


def _extract_sar_io_summary(text):
    """Extract average I/O line from sar -d output."""
    for line in text.splitlines():
        if "Average" in line and "DEV" not in line:
            parts = line.split()
            if len(parts) >= 5:
                return {"raw": line.strip()}
    return None


def _extract_load_average(uptime_text):
    """Extract load average from uptime output."""
    m = re.search(
        r"load average:\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+)",
        uptime_text,
    )
    if m:
        return {
            "avg_1": float(m.group(1)),
            "avg_5": float(m.group(2)),
            "avg_15": float(m.group(3)),
        }
    return None
