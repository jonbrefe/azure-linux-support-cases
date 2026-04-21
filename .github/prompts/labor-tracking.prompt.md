# DFM Labor Tracking

Generate a DFM labor entry for pasting into the DFM time tracking system. Follow `.github/copilot-instructions.md` for data handling rules.

---

## INPUTS

Extract from the engineer's message or existing DFM case notes. If a field is not provided, handle as noted:

| Field | Required | If Missing |
|-------|----------|------------|
| Case/SR number | Yes | Ask |
| Date worked (local) | Yes | Ask |
| Start time / End time or Duration | Yes | Ask |
| Is late entry? | Yes | Assume No |
| Work performed (bullets) | Yes | Derive from DFM notes if available; otherwise ask |
| Key artifacts (e.g. sosreport, supportconfig) | No | Omit |
| Outcome/progress | No | Use "No resolution yet; progressed investigation." |
| Next step | No | Omit |

## HARD RULES

- Labor must be recorded daily by 11:59 PM local time. If the engineer says the entry is late, include a late reason justification. If not late, do NOT mention late reason.
- A note must be added whenever labor is added — always produce a note.
- Classification must be selected — always propose the best match.
- Use the duration exactly as provided. Do NOT change it, estimate new time, or round it.
- Do NOT include any customer PII (hostnames, subscription IDs, IPs, credentials, secrets, raw logs).
- Do NOT invent work that was not performed. If info is missing, write neutrally and state "Details not provided".
- Do NOT mention internal tool or script names in the output. Use generic descriptions (e.g. "Analyzed sosreport data", "Performed multi-region verification").
- When DFM case notes exist for the case, derive the labor note from those notes — do not re-analyze logs.

## CLASSIFICATION BUCKETS

Always propose ONE classification from this list:

- **Troubleshooting / Investigation** — analyzing logs, reproducing issues, root cause analysis
- **Data Collection / Analysis** — gathering sosreport, supportconfig, requesting customer data
- **Internal Collaboration** — swarming, Ninjas posts, IcM filing, collab sessions
- **Customer Communication** — email drafts, calls, follow-ups
- **Documentation / Case Notes** — writing DFM notes, updating case status
- **Escalation Management** — vendor escalation, IcM triage, cross-team handoff

## OUTPUT FORMAT

Return ONLY these sections in this exact order, plain text, no markdown formatting:

```
DFM Labor Note (paste into Note field):
<3-6 lines: factual actions performed + purpose + outcome/progress.
Mention artifacts at high level only (e.g. "reviewed sosreport").
Use advisory IDs and IcM numbers where applicable.>

Suggested Classification: <ONE label from the list above>

Duration: <exactly as provided by engineer>

Late Reason (only if late): <1-2 sentence justification>
```

## EXAMPLE

```
DFM Labor Note (paste into Note field):
Analyzed sosreport from RHEL 8.10 PAYG VM. Confirmed RHUI sync gap — RHSA-2026:8534 (libarchive) and RHSA-2026:8352 (bind-export-libs) not available on customer's RHUI endpoint despite CDN publication 5+ days ago. Reproduced independently on fresh marketplace VM. Performed multi-region RHUI endpoint verification (5 regions, 3/5 stale). Filed IcM 783813265 (Sev 2) against AzTux/RHUI. Provided workarounds to customer.

Suggested Classification: Troubleshooting / Investigation

Duration: 4h 30m
```
