# Ninjas Swarming Post + DFM Entry

Generate a Ninjas swarming post and DFM case notes entry for cases we are swarming (not owning). Follow `.github/copilot-instructions.md` for data handling, redaction, and case processing rules.

---

## WHEN TO USE

- The engineer is swarming (not the case owner)
- A quick consult or validation is needed from the Ninjas channel
- The case owner stays engaged; we do not assign or transfer the case
- The triage extraction tool may be used to collect environment data before posting

## STRICT RULES

1. **No ownership transfer.** Do NOT assign the case, do NOT ask anyone to "take" the case, and do NOT imply ownership transfer. If deeper engagement is needed, propose "collab" as the engagement method and state the case owner stays engaged.
2. **No PII in the Teams post.** No Subscription IDs, credentials, full raw log files, customer names, or anything restricted. The DFM case notes entry MAY include hostnames, IPs, subscription IDs, and resource groups — these are internal documents and follow the standard DFM redaction rules (see Redaction Rules section).
3. **Engineer-to-engineer voice.** Guidance in Ninjas is NOT to be copy/pasted to the customer. Do not write in a customer-ready voice.
4. **Command output excerpts** must use prompt-to-prompt style (include command prompt, full output, and next prompt). If too large, summarize and say "available on request".
5. **Availability line required.** Do not post in a way that requires follow-up if going offline. Add an availability line and any timing constraints.
6. **Swarming first, collab if needed.** Share what was tried, what is needed, and the explicit ask. Prefer swarming first; propose collab only if no response for high-sev or the issue is too complex.

## INPUTS

The engineer provides case context through any combination of:

- Case intake data (problem description, severity, environment, troubleshooting done)
- Sosreport or supportconfig archive (analyze with the triage extraction tool)
- Log snippets, package lists, or CVE identifiers
- Explicit swarming variables (SR number, availability, specific ask)

Extract the following fields from the provided data — do NOT ask the engineer to fill in a template. If a field cannot be determined from context, ask only for the missing critical fields (SR number, severity, explicit ask, availability):

| Field | Description |
|-------|-------------|
| SR number | Case number (from intake data or ask if not provided) |
| Severity | Severity and customer tier (from intake data) |
| Short title | Synthesize a one-line problem title from the issue description |
| Customer environment | VM size, distro, version, workload type — extract from sosreport/IMDS/intake (no PII) |
| Issue summary | What is broken, exact symptom, impact — from problem description |
| When (UTC) | Approximate issue time window — from intake data |
| Troubleshooting done | What was tried — from intake data and sosreport analysis |
| Artifacts available | What diagnostics exist (sosreport, supportconfig, etc.) — state "available" without attaching |
| Key findings | Facts observed from analysis — from triage output and manual log review |
| Ask for Ninjas | What input is needed — use the engineer's explicit ask from the case notes or intake data. Do NOT synthesize from analysis |
| Availability | Engineer's availability — ask if not provided |

## OUTPUT FORMAT

Generate TWO sections in a single file:

### (A) NINJAS SWARMING POST

```
## Ninjas Swarming Response


**Key findings:**
- <finding 1>
- <finding 2>

### Next Actions (Swarming Response)

- <action 1>
- <action 2>
- Case owner remains engaged
```

- Use **bold labels** (`**Sev:**`, `**Env:**`, etc.) — required for Teams readability
- **Blank line between every field** — Teams collapses adjacent lines into one paragraph without blank-line separation
- Env uses pipe-separated values for quick scanning
- Break multi-item symptoms into bullet lists, not run-on sentences
- 8–15 lines max, concise, scannable
- No PII, no subscription IDs, no raw logs
- Public URLs (vendor errata, CVE pages, KB articles) are allowed and encouraged
- No emojis or icons
- Engineer tone throughout
- When responding to an existing swarming thread (not asking a question), omit SR#, Sev, Ask, and Availability from the Teams post — the thread already contains this context. These fields may still appear in the DFM case notes entry
- When new evidence is provided, focus only on the new findings — do not repeat information from the previous interaction

### (B) DFM CASE NOTES ENTRY

```
## DFM Case Notes Entry

### Swarming Request

- Posted swarming response to Azure Linux Ninjas Teams channel
- Teams post URL: <url_if_provided>
- Date/time: <timestamp>

### Issue Summary

<Expanded version of the symptom and environment — full sentences>

### Technical Findings

(Include triage-extracted data relevant to the reported problem.
Use the same structured subsections as DFM notes:
Environment Summary, Storage Summary, Repository Summary, Network Summary.
Only include subsections that are relevant to the issue — do not include
all triage output by default. Include additional subsections if specifically
requested or if they contain anomalies related to the problem.
Environment Summary should always be included for baseline context.)

### Troubleshooting Performed

- <bullet 1>
- <bullet 2>
- ...

### Key Findings

- <finding 1>
- <finding 2>

### Next Actions (Swarming Response)

- <action 1>
- <action 2>
- Case owner remains engaged
```

- Same content as the post but expanded with full context
- Must be copy/paste ready into DFM notes
- Include the Teams post URL if provided
- When sosreport or supportconfig was analyzed, include triage-extracted Technical Findings relevant to the reported problem — Environment Summary should always be included for baseline context; other subsections (Storage, Repository, Network) only when relevant to the issue or containing anomalies
- When new evidence is provided, focus only on the new findings — do not repeat information from the previous interaction
- **No PII in the Teams post section** — no subscription IDs, customer names, credentials, or raw logs
- **DFM entry may include internal identifiers** (hostnames, IPs, subscription IDs, resource groups) per standard DFM redaction rules — these are internal documents

## FILE NAMING

Swarming files are saved as:

```
cases/<case-number>/ninjas-swarm_YYYY-MM-DD_HHMM.md
```

- Each swarming interaction gets its own file with a unique timestamp
- Do NOT update a previous swarming file with new findings — create a new file instead
- The new file should reference the previous interaction when relevant (e.g. "Previous post: ninjas-swarm_2026-04-21_1100.md")
- Multiple swarming files per case represent the chronological progression of the investigation

## TEAMS POST URL

- If the engineer provides the Teams post URL after posting, add it to the DFM entry under "Swarming Request"
- If not yet available, use placeholder: `<pending — update after posting>`

## TRIAGE TOOL INTEGRATION

- The triage extraction tool may be run before generating the swarming post to collect environment, storage, network, and repository data
- Include relevant extracted findings in key findings and customer environment sections
- Do NOT mention the tool name in the Ninjas post or DFM entry — use generic references only

## TONE

Direct, technical, peer-to-peer. No customer-facing language.
