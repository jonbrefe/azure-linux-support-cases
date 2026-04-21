"""Shared utilities for triage parsers and output modules."""

import os
import re


def read_file(path):
    """Read file contents, return empty string if missing."""
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return ""


def extract_scc_command(text, command_pattern):
    """Extract output of a command from supportconfig section files.

    Finds the block after a line matching the command_pattern regex and
    returns all lines until the next section marker (#==).
    """
    lines = text.splitlines()
    output = []
    capturing = False
    for line in lines:
        if capturing:
            if line.startswith("#=="):
                break
            output.append(line)
        elif re.search(command_pattern, line):
            capturing = True
    return "\n".join(output).strip()


def extract_scc_config(text, config_pattern):
    """Extract a configuration file block from supportconfig section files.

    Similar to extract_scc_command but matches '# <path>' lines under
    Configuration File headers.
    """
    lines = text.splitlines()
    output = []
    capturing = False
    for line in lines:
        if capturing:
            if line.startswith("#=="):
                break
            output.append(line)
        elif re.search(config_pattern, line):
            capturing = True
    return "\n".join(output).strip()


def find_file_glob(directory, prefix):
    """Find first file in directory starting with prefix, return its contents."""
    if not os.path.isdir(directory):
        return ""
    for f in sorted(os.listdir(directory)):
        if f.startswith(prefix):
            return read_file(os.path.join(directory, f))
    return ""


def format_bytes(n):
    """Format byte count to human-readable string."""
    if n >= 1_000_000_000_000:
        return f"{n / 1_000_000_000_000:.1f} TB"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


def make_warning(category, message, evidence="", impact="", next_step=""):
    """Create a structured warning dict.

    Categories: ENV, STORAGE, REPO, NET, PERF, SECURITY, SCOPE, MISSING
    """
    return {
        "category": category,
        "message": message,
        "evidence": evidence,
        "impact": impact,
        "next_step": next_step,
    }
