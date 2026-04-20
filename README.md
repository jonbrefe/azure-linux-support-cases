# Azure Linux Support Cases

Repository for managing Azure Linux support escalation cases using GitHub Copilot as an AI-assisted case processing engine.

## Purpose

This repo provides a structured workflow for Senior Linux Support Escalation Engineers (SEE) to:

- Process support case data (sosreport, supportconfig, logs, case notes)
- Generate DfM Case Notes (rich text ready)
- Generate Customer-Facing Email Drafts
- Track cases with consistent formatting and support boundary clarity

## Repository Structure

```
.github/
  copilot-instructions.md   # Copilot instructions (SEE prompt)
templates/
  case-input.md             # Template for pasting case data
cases/
  (case files organized by case ID)
scripts/
  (utility scripts for log parsing, data extraction)
```

## Usage

1. Copy `templates/case-input.md` into `cases/` and rename it with the case ID
2. Paste case data (sosreport excerpts, logs, CVEs, notes) into the template
3. Open the file and ask GitHub Copilot to process the case
4. Copilot will follow the instructions in `.github/copilot-instructions.md` to generate:
   - DfM Case Notes
   - Customer Email Draft

## Copilot Instructions

The `.github/copilot-instructions.md` file configures Copilot to act as a Senior Linux Support Escalation Engineer. It enforces:

- Mandatory 4-step processing workflow (Data Extraction, Technical Analysis, Distribution Model, Support Boundaries)
- Strict output formatting (no markdown in outputs, rich text safe)
- Clear separation of Azure Support vs Vendor Responsibility
- Support for RHEL, SLES, and Ubuntu distribution models

## Support Boundaries

| Scope | Responsibility |
|-------|---------------|
| Azure Support | OS-level validation, package presence, repository identification |
| Vendor (Red Hat / SUSE / Canonical) | Lifecycle, subscription entitlement, repository access, CVE remediation |
