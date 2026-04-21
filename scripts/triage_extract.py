#!/usr/bin/env python3
"""Unified triage extraction tool for Azure Linux support cases.

Usage:
    python triage_extract.py --input <path> [--out <dir>] [--config <cfg.json>]
        [--parsers env,storage,repo,net,perf]
        [--format dfm|kv|warnings|all]

Supports sosreport directories, supportconfig directories, and tar archives
(.tar.xz, .tar.gz, .tar.bz2). Archives are extracted to <archive>.d/ in place.
"""

import argparse
import os
import sys

# Allow running from the scripts/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from triage.config import load_config
from triage.detectors import resolve_input
from triage.parsers import env as env_parser
from triage.parsers import storage as storage_parser
from triage.parsers import repo as repo_parser
from triage.parsers import net as net_parser
from triage.parsers import perf as perf_parser
from triage.output import dfm_md
from triage.output import kv_text
from triage.output import warnings_report


PARSER_MAP = {
    "env": env_parser,
    "storage": storage_parser,
    "repo": repo_parser,
    "net": net_parser,
    "perf": perf_parser,
}

ALL_PARSERS = ["env", "storage", "repo", "net", "perf"]

OUTPUT_MAP = {
    "dfm": ("dfm_sections.md", dfm_md),
    "kv": ("kv_summary.txt", kv_text),
    "warnings": ("warnings.txt", warnings_report),
}


def main():
    parser = argparse.ArgumentParser(
        description="Extract and analyze sosreport/supportconfig data.",
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to sosreport/supportconfig directory or tar archive.",
    )
    parser.add_argument(
        "--out", "-o", default=None,
        help="Output directory for reports. Defaults to stdout.",
    )
    parser.add_argument(
        "--config", "-c", default=None,
        help="Path to JSON config file.",
    )
    parser.add_argument(
        "--parsers", "-p", default="env,storage,repo,net",
        help=(
            "Comma-separated list of parsers to run. "
            "Options: env,storage,repo,net,perf. Default: env,storage,repo,net"
        ),
    )
    parser.add_argument(
        "--format", "-f", default="all",
        help=(
            "Output format(s). Options: dfm,kv,warnings,all. "
            "Default: all. Comma-separated for multiple."
        ),
    )

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Resolve input (handles archives and directories)
    try:
        report_path, report_type = resolve_input(args.input)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if report_type is None:
        print(
            f"Error: Cannot detect sosreport or supportconfig in {report_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    source_dir = os.path.basename(report_path.rstrip("/"))

    # Determine which parsers to run
    requested_parsers = [
        p.strip() for p in args.parsers.split(",") if p.strip()
    ]
    # Enable perf parser if requested
    if "perf" in requested_parsers:
        config["enable_perf_parsing"] = True

    # Run parsers
    results = {}
    for name in requested_parsers:
        mod = PARSER_MAP.get(name)
        if mod is None:
            print(f"Warning: Unknown parser '{name}', skipping.", file=sys.stderr)
            continue
        results[name] = mod.parse(report_path, report_type, config)

    # Determine output formats
    fmt_str = args.format.strip().lower()
    if fmt_str == "all":
        formats = ["dfm", "kv", "warnings"]
    else:
        formats = [f.strip() for f in fmt_str.split(",") if f.strip()]

    # Generate outputs
    for fmt in formats:
        if fmt not in OUTPUT_MAP:
            print(f"Warning: Unknown format '{fmt}', skipping.", file=sys.stderr)
            continue

        filename, renderer = OUTPUT_MAP[fmt]
        output = renderer.render(results, report_type, source_dir, config)

        if args.out:
            os.makedirs(args.out, exist_ok=True)
            out_path = os.path.join(args.out, filename)
            with open(out_path, "w") as f:
                f.write(output)
            print(f"  Written: {out_path}", file=sys.stderr)
        else:
            print(output)


if __name__ == "__main__":
    main()
