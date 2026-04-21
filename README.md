# Azure Linux Support Cases

An AI-assisted case processing toolkit for Azure Linux support engineers. Uses GitHub Copilot with structured prompts to analyze sosreport/supportconfig data and generate standardized case documentation.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Overview

This toolkit helps Linux Support Escalation Engineers (SEEs) working Azure cases to:

- **Extract** structured data from sosreport and supportconfig archives (environment, storage, networking, repositories)
- **Analyze** Azure VM configurations, disk tiers, accelerated networking, RHUI/subscription status, and billing model
- **Generate** standardized DFM case notes and customer-facing email drafts
- **Enforce** consistent support boundary documentation (Azure vs vendor responsibility)

The triage extraction tool (`scripts/triage_extract.py`) is a standalone Python CLI that works independently. The Copilot instructions (`.github/copilot-instructions.md`) provide an AI-assisted workflow that integrates the tool into a complete case processing pipeline.

## Quick Start

### Prerequisites

- Python 3.8+
- No external dependencies — uses only the Python standard library

### Extract triage data from a sosreport

```bash
cd scripts/
python3 triage_extract.py --input /path/to/sosreport-directory --format all --out /tmp/output
```

This produces three files:

| File | Description |
|------|-------------|
| `dfm_sections.md` | Structured markdown sections for DFM case notes |
| `kv_summary.txt` | Key-value summary for quick reference |
| `warnings.txt` | Anomalies, misconfigurations, and action items |

### Extract from a supportconfig

```bash
python3 triage_extract.py --input /path/to/scc_hostname_date --format all --out /tmp/output
```

### Extract from a compressed archive

```bash
python3 triage_extract.py --input /path/to/sosreport-server.tar.xz --format all --out /tmp/output
```

Archives are automatically extracted to `<filename>.d/` next to the original file.

### Run specific parsers only

```bash
# Environment + storage only
python3 triage_extract.py --input /path/to/sosreport --parsers env,storage --format dfm

# Network analysis only
python3 triage_extract.py --input /path/to/sosreport --parsers net --format kv
```

## Repository Structure

```
.github/
  copilot-instructions.md          # Copilot AI agent instructions
scripts/
  triage_extract.py                # CLI entry point
  triage/                          # Triage package
    __init__.py
    common.py                      # Shared utilities
    config.py                      # Configuration handling
    detectors.py                   # Format detection + archive extraction
    parsers/                       # Data extraction parsers
      env.py                       # OS, kernel, IMDS, fstab, failed services
      storage.py                   # SCSI, NVMe, LVM, df, Azure disk tiers
      repo.py                      # Repos, RHUI, subscription manager, zypper
      net.py                       # Interfaces, AN, link stats, routes, DNS
      perf.py                      # Performance metrics (opt-in)
    output/                        # Output formatters
      dfm_md.py                    # DFM markdown sections
      kv_text.py                   # Key-value text summary
      warnings_report.py           # Warnings and anomalies report
  extract-env.py                   # Legacy script (superseded)
  extract-storage.py               # Legacy script (superseded)
  extract-repos.py                 # Legacy script (superseded)
  extract-network.py               # Legacy script (superseded)
templates/
  case-input.md                    # Template for case data input
cases/
  <case-number>/                   # Per-case output directory
    dfm-notes_YYYY-MM-DD_HHMM.md  # DFM case notes (timestamped)
    email-draft_YYYY-MM-DD_HHMM.md # Customer email draft (timestamped)
```

## Triage Extraction Tool

The core of this toolkit is `scripts/triage_extract.py` — a modular CLI that parses sosreport and supportconfig data into structured analysis.

### Supported Input Formats

| Format | Detection |
|--------|-----------|
| sosreport | Presence of `uname` file + `sos_commands/` directory |
| supportconfig | Presence of `basic-environment.txt` file |
| Archives | `.tar.xz`, `.tar.gz`, `.tar.bz2`, `.tgz` (auto-extracted) |

### Parsers

| Parser | Flag | What It Extracts |
|--------|------|------------------|
| `env` | `--parsers env` | OS, kernel, architecture, hostname, CPU/memory, Azure IMDS, failed services, fstab |
| `storage` | `--parsers storage` | SCSI/NVMe devices, LVM, filesystems, Azure disk tier analysis, IOPS/throughput limits, overcommit check |
| `repo` | `--parsers repo` | Subscription manager, RHUI, update channel, enabled/disabled repos, zypper repos (SLES), warnings |
| `net` | `--parsers net` | Interfaces, accelerated networking detection, link statistics, routes, DNS, firewall, bonding, IMDS network |
| `perf` | `--parsers perf` | CPU, memory, I/O statistics (opt-in, not included in default set) |

Default: `env,storage,repo,net`

### Output Formats

| Format | Flag | File | Description |
|--------|------|------|-------------|
| DFM Markdown | `--format dfm` | `dfm_sections.md` | Structured sections ready for DFM case notes |
| Key-Value | `--format kv` | `kv_summary.txt` | Flat key-value pairs for quick reference |
| Warnings | `--format warnings` | `warnings.txt` | Anomalies, misconfigurations, billing issues |
| All | `--format all` | All three | Default — generates all formats |

### Configuration

Optional JSON config file (`--config path/to/config.json`):

```json
{
  "scrub_mode": "none",
  "include_all_logs": false,
  "enable_perf_parsing": false,
  "vm_size_limits_db_path": null,
  "disk_tiers_db_path": null
}
```

| Key | Values | Description |
|-----|--------|-------------|
| `scrub_mode` | `none`, `light`, `strict` | Data scrubbing level |
| `include_all_logs` | `true`/`false` | Include all log entries vs summary only |
| `enable_perf_parsing` | `true`/`false` | Enable performance parser |
| `vm_size_limits_db_path` | path or `null` | Custom VM size limits database |
| `disk_tiers_db_path` | path or `null` | Custom disk tier database |

### Key Detections

The tool automatically detects and flags:

- **Azure VM context** — VM size, region, resource group, subscription (from IMDS)
- **Disk tier analysis** — Maps attached disks to Azure Premium SSD tiers with IOPS/throughput limits
- **Storage overcommit** — Compares aggregate disk IOPS to VM-level caps
- **Accelerated networking** — Detects mlx5_core VF driver alongside hv_netvsc
- **RHUI configuration** — Identifies RHUI package, update channel, and registration status
- **BYOS/PAYG billing mismatch** — Flags RHUI on BYOS VMs as a billing anomaly
- **Repository warnings** — EPEL, third-party repos, duplicate repo definitions
- **Failed services** — Identifies systemd units in failed state
- **SCSI device name instability** — Warns that `/dev/sd*` names may change across reboots

## Copilot Integration

The `.github/copilot-instructions.md` file configures GitHub Copilot to act as a Senior Linux Support Escalation Engineer. When loaded in VS Code, Copilot follows a structured workflow:

1. **Data Extraction** — Run `triage_extract.py`, parse logs and case data
2. **Technical Analysis** — Identify lifecycle status, subscription gaps, CVE relevance
3. **Distribution Model** — Apply RHEL/SLES/Ubuntu patching and lifecycle rules
4. **Support Boundaries** — Separate Azure support scope from vendor responsibility

### Copilot-Generated Outputs

| Output | Location | Purpose |
|--------|----------|---------|
| DFM Case Notes | `cases/<id>/dfm-notes_YYYY-MM-DD_HHMM.md` | Internal engineering documentation |
| Email Draft | `cases/<id>/email-draft_YYYY-MM-DD_HHMM.md` | Customer-facing communication |

### Using with Copilot

1. Open the workspace in VS Code with Copilot enabled
2. Provide a case number and point to the sosreport/supportconfig location
3. Copilot runs the extraction tool, analyzes results, and generates both outputs
4. Review, edit, and send

## Supported Distributions

| Distribution | Log Format | Update Channels |
|-------------|------------|-----------------|
| RHEL | sosreport | RHUI, Red Hat CDN, EUS, E4S |
| SLES | supportconfig | SUSE Cloud (PAYG), SCC, SMT/RMT |
| Ubuntu | sosreport | APT, ESM |

## Support Scope Reference

This toolkit enforces clear documentation of support boundaries per [Microsoft's Linux support policy](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/support-linux-open-source-technology):

| Scope | Responsibility |
|-------|---------------|
| **Azure Support** | Platform infrastructure, OS-level validation, package/repo identification, PAYG first-level Linux support |
| **Vendor** (Red Hat / SUSE / Canonical) | Lifecycle, subscription entitlement, repository access, CVE remediation, custom kernels |
| **Customer** | Application code, custom configurations, third-party agents |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting changes.

## Security

See [SECURITY.md](SECURITY.md) for reporting security vulnerabilities.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
