# Customer Email Draft

Generate a customer-facing email draft for the specified case number. Follow `.github/copilot-instructions.md` for data handling, redaction, and support boundary rules.

**All sensitive data MUST be redacted in customer emails.** See Redaction Rules in the base instructions.

---

## FORMAT

- Use markdown formatting
- Full sentences
- Clean paragraphs
- Saved as `email-draft_YYYY-MM-DD_HHMM.md` inside the case directory

## STRUCTURE

Every email draft MUST contain these sections in this exact order:

```
# Customer Email Draft — <case number>

**Subject:** <descriptive summary> TrackingID#<case number>

---

(Opening paragraph: greeting, thank the customer, state what was analyzed)

## Summary of Findings

(Plain-language summary of the environment and current state — OS, VM size,
key infrastructure facts. No raw script output. Summarize for the customer.)

## Key Observations

(Numbered list of significant findings — explain each clearly.
Include root cause analysis or relevant context.
Reference public documentation URLs where available.)

## Support Scope (Azure vs Vendor)

(State what Azure Support validated.
List what falls under vendor or customer responsibility.
Include the Microsoft support scope reference URL when flagging out-of-scope items.)

## Recommended Next Steps

### Required Actions

(Numbered list of actions the customer must take to resolve the issue.
Include vendor contact guidance where appropriate.)

### Optional Recommendations

(Numbered list of non-blocking improvements or best practices —
e.g. masking a harmless failed service, enabling accelerated networking.
Omit this subsection if there are no optional items.)

(Closing: offer continued assistance, sign off)
```

## NOTES

- Section names may vary slightly to match the case context (e.g. "Environment Overview" instead of "Summary of Findings") but all four content areas must be present
- Never include raw script output or internal case notes in the email
- All sensitive data must be redacted or generalized

## SUBJECT LINE FORMAT

All email subjects MUST follow this pattern:

```
<descriptive summary> TrackingID#<case number>
```

Example:
```
OpenJDK 11 CVE Remediation on RHEL 9 — Red Hat ELS Subscription Required TrackingID#2501010010001234
```

## CONTENT REQUIREMENTS

- Explain:
  - Package + version
  - Lifecycle status (include relevant dates when possible)
  - Repository source
- If non-standard repo:
  - Clearly state it (e.g. OpenJDK 11 ELS repo)
- Explain subscription dependency:
  - Not included in Azure PAYG
  - Requires vendor add-on

## PUBLIC DOCUMENTATION URLS

- When public URLs are available in the case notes (e.g. Red Hat KB articles, CVE links, vendor lifecycle pages), include them in the customer email
- Only include URLs that point to public vendor documentation accessible to the customer
- Format as direct links the customer can follow

## CVE EXPLANATION

- Explain vendor model:
  - CVEs validated via vendor advisories
  - Not based on upstream versions

## NEXT STEPS

- Contact vendor:
  - Red Hat / SUSE / Canonical
- Validate:
  - Subscription entitlement
  - CVE remediation status

## SCOPE CLARITY

- Azure:
  - Platform + OS-level validation
- Vendor:
  - Lifecycle, repos, CVEs, subscriptions
- When flagging out-of-scope items in customer emails, always include:
  - A clear explanation of what falls outside Microsoft Azure support
  - The reference: [Linux and open-source technology support in Azure](https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/support-linux-open-source-technology)
  - Guidance on the appropriate contact (vendor support, community forums)

## TONE

Professional, supportive, firm on boundaries
