"""Detect sosreport/supportconfig format and handle archive extraction."""

import os
import shutil
import subprocess
import tarfile
import tempfile


def detect_type(path):
    """Detect whether the path is a sosreport or supportconfig directory.

    Returns:
        "sosreport", "supportconfig", or None
    """
    if os.path.isfile(os.path.join(path, "uname")) and os.path.isdir(
        os.path.join(path, "sos_commands")
    ):
        return "sosreport"
    if os.path.isfile(os.path.join(path, "basic-environment.txt")):
        return "supportconfig"
    return None


def is_archive(path):
    """Check if path is a supported archive file."""
    name = os.path.basename(path).lower()
    return name.endswith((".tar.xz", ".tar.gz", ".tar.bz2", ".tgz"))


def extract_archive(archive_path):
    """Extract a tar archive to <archive_path>.d/ alongside the original.

    Returns:
        Path to the directory containing the extracted report root.
    """
    dest_dir = archive_path + ".d"
    if os.path.isdir(dest_dir):
        return _find_report_in_dir(dest_dir)

    os.makedirs(dest_dir, exist_ok=True)
    try:
        with tarfile.open(archive_path, "r:*") as tf:
            # Security: check for path traversal
            for member in tf.getmembers():
                member_path = os.path.join(dest_dir, member.name)
                if not os.path.realpath(member_path).startswith(
                    os.path.realpath(dest_dir)
                ):
                    raise ValueError(
                        f"Archive contains path traversal: {member.name}"
                    )
            tf.extractall(dest_dir)
    except (tarfile.TarError, ValueError) as e:
        raise RuntimeError(f"Failed to extract {archive_path}: {e}") from e

    return _find_report_in_dir(dest_dir)


def _find_report_in_dir(base_dir):
    """Find the sosreport/supportconfig root inside an extracted directory.

    Archives often contain a single top-level directory. This function
    descends one level if needed to find the actual report root.
    """
    # Check if base_dir itself is a report
    report_type = detect_type(base_dir)
    if report_type:
        return base_dir

    # Check immediate subdirectories
    entries = [
        e for e in os.listdir(base_dir)
        if os.path.isdir(os.path.join(base_dir, e))
    ]
    for entry in entries:
        candidate = os.path.join(base_dir, entry)
        if detect_type(candidate):
            return candidate

    # If nothing found, return base_dir and let caller handle detection failure
    return base_dir


def resolve_input(input_path):
    """Resolve an input path to a report directory.

    Handles both directories and archives transparently.

    Returns:
        (report_path, report_type) tuple.
        report_type is "sosreport", "supportconfig", or None.
    """
    path = os.path.abspath(input_path)

    if os.path.isfile(path) and is_archive(path):
        report_path = extract_archive(path)
    elif os.path.isdir(path):
        report_path = path
    else:
        raise FileNotFoundError(f"Input not found: {path}")

    report_type = detect_type(report_path)
    return report_path, report_type
