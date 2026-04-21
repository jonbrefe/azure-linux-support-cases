# Cases

Generated case documentation files, organized by case number.

## Structure

```
cases/
  <case-number>/
    dfm-notes_YYYY-MM-DD_HHMM.md     # Internal DFM case notes
    email-draft_YYYY-MM-DD_HHMM.md    # Customer-facing email draft
```

- Each case gets its own directory named by the case number
- Files are timestamped to allow multiple revisions per case
- DFM notes contain full technical findings (internal use)
- Email drafts contain redacted, customer-appropriate summaries

## Important

- **Never commit real customer data** (sosreport, supportconfig, raw logs) to this directory
- Log files are analyzed in their original location — not copied here
- Only generated markdown outputs belong in case directories
- The `.gitignore` excludes common data patterns, but always verify before committing
