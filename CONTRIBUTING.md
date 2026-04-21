# Contributing

Contributions are welcome. This guide covers the process for submitting changes.

## Getting Started

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Test against real sosreport/supportconfig data (see [Testing](#testing))
5. Submit a pull request

## Development Setup

```bash
git clone https://github.com/jbrenes_microsoft/azure-linux-support-cases.git
cd azure-linux-support-cases
```

No dependencies to install — the triage tool uses only the Python standard library (Python 3.8+).

## Project Structure

- `scripts/triage_extract.py` — CLI entry point
- `scripts/triage/parsers/` — Data extraction parsers (one per subsystem)
- `scripts/triage/output/` — Output formatters (DFM markdown, key-value, warnings)
- `scripts/triage/common.py` — Shared utilities
- `scripts/triage/config.py` — Configuration handling
- `scripts/triage/detectors.py` — Format detection and archive extraction
- `.github/copilot-instructions.md` — Copilot agent instructions

## Adding a New Parser

1. Create `scripts/triage/parsers/<name>.py`
2. Implement a `parse(report_path, report_type, config)` function that returns a dict
3. Handle both `"sosreport"` and `"supportconfig"` report types
4. Register the parser in `PARSER_MAP` in `triage_extract.py`
5. Add rendering logic in `scripts/triage/output/dfm_md.py` and `kv_text.py`

### Parser Contract

```python
def parse(report_path: str, report_type: str, config: dict) -> dict:
    """Extract data from a report directory.

    Args:
        report_path: Absolute path to the sosreport/supportconfig directory.
        report_type: "sosreport" or "supportconfig".
        config: Configuration dict from config.py.

    Returns:
        Dict with extracted data. Structure is parser-specific.
        Include a "warnings" key (list of dicts) for anomalies.
    """
```

### Warning Format

Use `common.make_warning()` for structured warnings:

```python
from triage.common import make_warning

warnings.append(make_warning(
    category="STORAGE",
    message="Filesystem /data at 95% capacity",
    evidence="/dev/sda1 950G/1000G",
    impact="Risk of write failures",
    next_step="Expand filesystem or clean up data",
))
```

Categories: `ENV`, `STORAGE`, `REPO`, `NET`, `PERF`, `SECURITY`, `SCOPE`, `MISSING`

## Adding a New Output Format

1. Create `scripts/triage/output/<name>.py`
2. Implement a `render(results, report_type, source_dir, config)` function that returns a string
3. Register it in `OUTPUT_MAP` in `triage_extract.py`

## Testing

Test against real (anonymized) sosreport or supportconfig data:

```bash
# Full extraction
python3 scripts/triage_extract.py --input /path/to/sosreport --format all --out /tmp/test-output

# Single parser
python3 scripts/triage_extract.py --input /path/to/sosreport --parsers env --format kv

# Supportconfig
python3 scripts/triage_extract.py --input /path/to/scc_hostname_date --format all --out /tmp/test-output
```

Verify:
- No Python errors or tracebacks
- Output files are generated with expected sections
- Warnings are emitted for known anomalies in the test data
- Both sosreport and supportconfig formats produce consistent output

## Copilot Instructions Changes

When modifying `.github/copilot-instructions.md`:

- Maintain the existing section order and heading hierarchy
- Test with Copilot Chat to verify the instructions produce correct outputs
- Never reference internal tool names in DFM notes or email output templates
- Keep the DFM and email template structures in sync with actual generated outputs

## Code Style

- Python 3.8+ compatible (no walrus operator, no `match` statements)
- Standard library only — no external dependencies
- Use docstrings for modules and public functions
- Follow existing patterns in the codebase

## Commit Messages

- Short subject line (50 chars or less)
- Blank line before body (if needed)
- Bullet points for multiple changes

## Pull Request Guidelines

- One logical change per PR
- Include a description of what changed and why
- Reference any related issues
- Ensure no customer data, credentials, or internal hostnames are included

## Data Safety

**Never commit real customer data.** All sosreport/supportconfig data must remain outside the repository. The `cases/` directory in the repo is for generated outputs only — actual log files are analyzed in their original location and never copied in.
