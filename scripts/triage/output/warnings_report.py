"""Warnings-only report — structured warnings from all parsers."""


def render(data, report_type, source_dir, config=None):
    """Render a warnings-only report from all parser outputs.

    Collects _warnings from each parser and formats them as a structured
    report with Category, Message, Evidence, Impact, and Next Step.

    Args:
        data: dict with keys "env", "storage", "repo", "net", "perf"
        report_type: "sosreport" or "supportconfig"
        source_dir: basename of the source directory
        config: optional config dict

    Returns:
        str: warnings report text
    """
    # Collect all warnings
    all_warnings = []
    for section in ["env", "storage", "repo", "net", "perf"]:
        section_data = data.get(section, {})
        warnings = section_data.get("_warnings", [])
        all_warnings.extend(warnings)

    lines = []
    sep = "=" * 70

    lines.append(sep)
    lines.append(f"  Warnings Report — {report_type}")
    lines.append(f"  Source: {source_dir}/")
    lines.append(f"  Total Warnings: {len(all_warnings)}")
    lines.append(sep)

    if not all_warnings:
        lines.append("")
        lines.append("  No warnings detected.")
        lines.append("")
        lines.append(sep)
        return "\n".join(lines)

    # Group by category
    categories = {}
    for w in all_warnings:
        cat = w.get("category", "UNKNOWN")
        categories.setdefault(cat, []).append(w)

    category_order = [
        "SECURITY", "ENV", "STORAGE", "REPO", "NET",
        "PERF", "SCOPE", "MISSING", "UNKNOWN",
    ]

    for cat in category_order:
        warnings = categories.get(cat, [])
        if not warnings:
            continue

        lines.append("")
        lines.append(f"  [{cat}] — {len(warnings)} warning(s)")
        lines.append(f"  {'─' * 50}")

        for i, w in enumerate(warnings, 1):
            lines.append(f"  {i}. {w.get('message', '')}")
            if w.get("evidence"):
                lines.append(f"     Evidence:  {w['evidence']}")
            if w.get("impact"):
                lines.append(f"     Impact:    {w['impact']}")
            if w.get("next_step"):
                lines.append(f"     Next Step: {w['next_step']}")
            lines.append("")

    lines.append(sep)
    lines.append("")

    return "\n".join(lines)
