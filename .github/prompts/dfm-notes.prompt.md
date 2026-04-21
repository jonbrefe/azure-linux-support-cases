# DFM Case Notes

Generate DFM case notes for the specified case number. Follow `.github/copilot-instructions.md` for data handling, redaction, case continuity, and case processing workflow rules.

---

## FORMAT RULES

- Use markdown formatting
- Professional engineer tone
- Saved as `dfm-notes_YYYY-MM-DD_HHMM.md` inside the case directory

## STRUCTURE

Every DFM notes file MUST contain these sections in this exact order:

```
# DFM Case Notes — <case number>

## Case Metadata

(Table: case number, date, current status, engineer)

## Problem Statement

(Clear, concise description of the customer's reported problem)

## Business Impact

(Severity, affected systems, customer urgency — if known)

## Timeline

(Chronological list of key events: case opened, data received, analysis milestones,
communications sent)

## Customer Environment

(Table or bullet list: OS, VM size, region, hostname, subscription type)

## Technical Findings

### Environment Summary

(Extracted environment data, formatted as tables)
- OS / version / kernel / architecture
- Azure IMDS (VM name, resource group, subscription, location, VM size, image)
- Failed services
- Subscription manager status
- /etc/fstab

### Observations

(Key facts observed during analysis — symptoms, error patterns, anomalies)

### Analysis

(Technical reasoning connecting observations to the problem —
correlation of errors, timeline analysis, comparison with expected behavior)

### Storage Summary

(Extracted storage data, formatted as tables)
- SCSI / NVMe device listing
- SCSI device name persistence note (if SCSI-based)
- Block device layout table
- LVM summary (VGs, LVs, sizes, free space)
- Filesystem usage table
- Azure disk profile table (tier, IOPS, throughput, caching)
- Overcommit analysis (if VM caps available)

### Repository Summary

(Extracted repository data, formatted as tables)
- Update channel (RHUI / Red Hat CDN / SUSE Cloud / SCC / None)
- RHUI package and status (if applicable)
- Enabled / disabled repos by source
- Repo files and counts
- Warnings (EPEL, third-party, duplicate repos)
- Subscription manager clarification (if RHUI)

### Network Summary

(Extracted network data, formatted as tables)
- Interfaces (name, state, MAC, MTU, driver, IPv4)
- Accelerated networking status
- Link statistics (RX/TX bytes, packets, errors, drops)
- Routes table
- DNS configuration
- Firewall status
- Socket summary
- IMDS network metadata (if available)

## Root Cause / Working Hypothesis

(Confirmed root cause if determined, or current working hypothesis with
confidence level and remaining unknowns)

## Linux Distribution Support Model

(Explanation of the distro's patching/lifecycle model relevant to the case)

## Support Scope Clarification

(What is in-scope for Azure vs vendor vs customer responsibility)

## Actions Taken

(Bullet list of what was done during analysis)

## Validation / Current Status

(Current state after actions taken — what was confirmed, what changed,
what remains unresolved)

## Next Steps

(Bullet list of recommended actions with owners: Microsoft, customer, vendor)

## Reusability Notes

(Patterns, solutions, or lessons learned that may apply to future cases —
omit if nothing notable)
```

## NOTES

- Subsections under Technical Findings are only included when the data exists (e.g. no Repository Summary if repo data was not extracted)
- For cases without sosreport/supportconfig (e.g. CVE-only cases), Technical Findings may contain prose instead of the structured subsections
- LVM data belongs in Storage Summary, not Environment Summary

## CONTENT REQUIREMENTS

- Include OS, packages, repo source, CVEs
- Clearly identify:
  - Non-standard repositories (e.g. OpenJDK 11 ELS)
  - PAYG vs non-PAYG
  - Lifecycle status
- Include internal references (allowed):
  - KBs (e.g. 7095973)
  - Advisory checks
  - IcM/case validation methods

**IF SOSREPORT/SUPPORTCONFIG EXISTS:**
- Include:
  - OS release
  - Kernel version
  - Architecture
  - Azure context (IMDS if present)
  - Update channel (RHUI / Red Hat CDN / SUSE Cloud / SCC / None)
  - Repository warnings (EPEL, third-party, duplicate repos)
- DO NOT invent missing info

## TONE

Direct, technical, escalation-level
