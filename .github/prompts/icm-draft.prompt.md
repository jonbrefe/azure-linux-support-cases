# IcM Incident Draft

Generate an IcM (Incident Management) incident draft for filing against a platform team. Follow `.github/copilot-instructions.md` for data handling rules.

**Do NOT include customer PII in the IcM description** — use VM size, OS, region, but not hostname, subscription ID, or resource group.

---

## WHEN TO USE

- A platform-side issue has been confirmed through investigation (e.g. RHUI sync gap, infrastructure failure)
- The issue requires action from a platform engineering team
- Sufficient evidence has been gathered (reproduction, multi-region verification, timeline, etc.)

## INPUTS

Extract IcM fields from the existing case data — DFM notes, swarming posts, sync reports, and sosreport analysis. Do NOT ask the engineer to fill in a template. If a critical field cannot be determined from context (e.g. severity, impacted regions), ask only for those missing fields.

## IcM FORM FIELDS

All fields marked with `*` are required by the IcM portal.

| Field | Required | Description |
|-------|----------|-------------|
| Owning Team | * | The team responsible for the incident (e.g. `AzTux/RHUI`) |
| Tags | | Optional tags for categorization |
| Title | * | Short, descriptive incident title — include the specific issue and scope |
| Description | * | Detailed incident description (see Description Format below) |
| Attachments | | Supporting files — sync reports, sosreport excerpts, verification output |
| Environment | * | Deployment environment — must be one of: `UNKNOWN`, `DOGFOOD`, `INT`, `PPE`, `PROD`, `STAGING`, `TEST` |
| Severity | * | Incident severity: `1` (critical), `2` (high), `25` (medium-high), `3` (medium), `4` (low) |
| Cloud Instance | * | Azure cloud instance (e.g. `Public`, `USGov`, `China`) |
| Impacted Services | * | Services affected (e.g. `AzTux`) |
| Customer/SLA Impact | * | `Yes` or `No` — whether customers or SLAs are directly affected |
| Impacted Regions | * | Azure regions affected (comma-separated list or `All`) |

## DESCRIPTION FORMAT

The Description field must be structured for quick triage by the platform team:

```
## Issue Summary

<1-2 sentence description of the confirmed issue>

## Impact

- Affected systems: <what is affected — e.g. RHEL 8 PAYG VMs served by stale RHUI endpoints>
- Customer impact: <compliance gaps, missing security patches, blocked updates>
- Scope: <number of regions affected, estimated blast radius>
- Duration: <how long the issue has persisted>

## Evidence

### Timeline

| Date/Time (UTC) | Event |
|------------------|-------|
| <date> | <event> |

### Verification Results

<Summary of testing methodology and results — e.g. multi-region endpoint checks,
package version comparisons, reproduction on fresh VMs>

<Include a table or bullet list of per-region/per-endpoint results>

### Expected vs Actual

- Expected: <what should happen — e.g. errata available within 24h of CDN publication>
- Actual: <what is happening — e.g. 3/5 tested endpoints still serving stale packages after 5+ days>

## Affected Packages / Advisories

<List of specific packages, versions, and advisory IDs involved>

## Support Case Reference

- Case: <case number>
- Severity: <case severity>
- Customer environment: <brief — OS, region, VM size>

## Recommended Action

<What the platform team should investigate or fix>
```

## SEVERITY GUIDANCE

| IcM Severity | Use When |
|-------------|----------|
| 1 | Widespread outage affecting many customers, SLA breach imminent |
| 2 | Significant impact, multiple customers/regions affected, security exposure |
| 25 | Moderate impact, limited regions, workaround available |
| 3 | Low impact, single region, non-critical functionality |
| 4 | Informational, minor issue, no direct customer impact |

## OUTPUT FORMAT

Generate a single markdown file with all IcM fields clearly labeled:

```
# IcM Incident Draft — <case number>

## IcM Fields

| Field | Value |
|-------|-------|
| Owning Team | <team> |
| Tags | <tags or "None"> |
| Title | <title> |
| Environment | <environment> |
| Severity | <severity> |
| Cloud Instance | <cloud instance> |
| Impacted Services | <services> |
| Customer/SLA Impact | <Yes/No> |
| Impacted Regions | <regions> |

## Description

<Full structured description per the Description Format above>

## Attachments

<List of files to attach, with brief description of each>
```

## FILE NAMING

IcM files are saved as:

```
cases/<case-number>/icm-draft_YYYY-MM-DD_HHMM.md
```

## CONTENT RULES

- Title should be specific and actionable — not generic (e.g. "RHEL 8 BaseOS RHUI mirror sync delay — 3/5 endpoints stale for 5+ days" not "RHUI issue")
- Description must include concrete evidence — package versions, region-level results, timeline
- Include case number as reference but do NOT include customer PII in the IcM description — use VM size, OS, region, but not hostname, subscription ID, or resource group
- Attachments section should reference files by name only (the engineer will attach them manually in the portal)
- When DFM notes and sync reports exist for the case, extract all evidence from those files — do not re-analyze from scratch
- The Description field content should be copy/paste ready for the IcM portal

## TONE

Technical, factual, platform-engineering audience. Focus on evidence and action needed.
