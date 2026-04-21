# Scripts

Extraction and analysis tools for Azure Linux support case data.

## Triage Extraction Tool

`triage_extract.py` is the primary CLI tool. It parses sosreport and supportconfig data into structured analysis outputs.

### Usage

```bash
python3 triage_extract.py --input <path> [--out <dir>] [--parsers env,storage,repo,net] [--format all]
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input`, `-i` | Yes | — | Path to sosreport/supportconfig directory or archive |
| `--out`, `-o` | No | stdout | Output directory for report files |
| `--config`, `-c` | No | defaults | Path to JSON configuration file |
| `--parsers`, `-p` | No | `env,storage,repo,net` | Comma-separated list of parsers to run |
| `--format`, `-f` | No | `all` | Output format: `dfm`, `kv`, `warnings`, or `all` |

### Examples

```bash
# Full analysis with all outputs
python3 triage_extract.py -i /path/to/sosreport -f all -o /tmp/output

# Quick environment check
python3 triage_extract.py -i /path/to/sosreport -p env -f kv

# Storage analysis only, DFM format
python3 triage_extract.py -i /path/to/sosreport -p storage -f dfm

# Supportconfig input
python3 triage_extract.py -i /path/to/scc_hostname_date -f all -o /tmp/output

# Compressed archive (auto-extracted)
python3 triage_extract.py -i /path/to/sosreport.tar.xz -f all -o /tmp/output
```

## Package Structure

```
triage/
  __init__.py              # Package init, version
  common.py                # Shared file I/O, formatting, warning helpers
  config.py                # Configuration loading and defaults
  detectors.py             # sosreport/supportconfig detection, archive extraction
  parsers/
    __init__.py
    env.py                 # OS, kernel, IMDS, fstab, failed services
    storage.py             # Disks, LVM, filesystems, Azure disk tiers, overcommit
    repo.py                # Repos, RHUI, sub-manager, zypper, update channels
    net.py                 # Interfaces, AN, ethtool, link stats, routes, DNS
    perf.py                # CPU, memory, I/O (opt-in via --parsers perf)
  output/
    __init__.py
    dfm_md.py              # DFM markdown sections renderer
    kv_text.py             # Key-value text summary renderer
    warnings_report.py     # Warnings and anomalies renderer
```

## Legacy Scripts

The individual extraction scripts are superseded by `triage_extract.py`:

| Legacy Script | Replaced By |
|--------------|-------------|
| `extract-env.py` | `--parsers env` |
| `extract-storage.py` | `--parsers storage` |
| `extract-repos.py` | `--parsers repo` |
| `extract-network.py` | `--parsers net` |

These remain in the repository for reference but are no longer maintained.
