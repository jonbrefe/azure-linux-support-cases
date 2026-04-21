#!/usr/bin/env python3
"""Extract repository configuration from sosreport or supportconfig."""

import configparser
import os
import re
import sys


def detect_type(path):
    """Detect whether the path is a sosreport or supportconfig directory."""
    if os.path.isfile(os.path.join(path, "uname")) and os.path.isdir(
        os.path.join(path, "sos_commands")
    ):
        return "sosreport"
    if os.path.isfile(os.path.join(path, "basic-environment.txt")):
        return "supportconfig"
    return None


def read_file(path):
    """Read file contents, return empty string if missing."""
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except (FileNotFoundError, IsADirectoryError):
        return ""


def classify_rhel_repo(repo_id, baseurl, name):
    """Classify a RHEL repo by source type."""
    if "rhui" in repo_id or "rhui" in baseurl or "from RHUI" in name:
        return "RHUI"
    if "rhui" in baseurl or "microsoft.com/pulp" in baseurl:
        return "RHUI"
    if "microsoft.com" in baseurl or "packages.microsoft.com" in baseurl:
        return "Microsoft"
    if "epel" in repo_id:
        return "EPEL"
    if "redhat.com" in baseurl:
        return "Red Hat CDN"
    if baseurl:
        return "Third-party"
    return "Unknown"


def classify_sles_repo(alias, uri, service):
    """Classify a SLES repo by source type."""
    if "susecloud" in uri or "susecloud" in alias:
        return "SUSE Cloud (PAYG)"
    if "smt" in uri or "rmt" in uri:
        return "SUSE SMT/RMT"
    if "scc.suse.com" in uri:
        return "SUSE SCC"
    if "microsoft.com" in uri or "packages-microsoft" in alias:
        return "Microsoft"
    if uri:
        return "Third-party"
    return "Unknown"


def extract_sles_module(alias):
    """Extract SLES module/extension name from repo alias."""
    # Format: Module_Name_x86_64:SLE-Module-Name15-SP6-Updates
    if ":" in alias:
        service_part = alias.split(":")[0]
        return service_part.replace("_x86_64", "").replace("_", " ")
    return alias


def extract_sosreport(path):
    """Extract repo data from a sosreport directory."""
    info = {
        "type": "RHEL",
        "subscription_manager": None,
        "rhui_package": None,
        "repos": [],
        "repo_files": [],
        "warnings": [],
    }

    # Subscription manager identity
    sub_mgr_path = os.path.join(
        path, "sos_commands", "subscription_manager", "subscription-manager_identity"
    )
    sub_mgr = read_file(sub_mgr_path).strip()
    if "not yet registered" in sub_mgr.lower() or not sub_mgr:
        info["subscription_manager"] = "Not registered"
    else:
        info["subscription_manager"] = sub_mgr

    # Check for RHUI package
    installed_rpms = read_file(os.path.join(path, "installed-rpms"))
    for line in installed_rpms.splitlines():
        if "rhui-" in line.lower():
            pkg = line.split()[0] if line.split() else line.strip()
            info["rhui_package"] = pkg
            break

    # Parse yum.repos.d
    repos_dir = os.path.join(path, "etc", "yum.repos.d")
    if os.path.isdir(repos_dir):
        for fname in sorted(os.listdir(repos_dir)):
            if not fname.endswith(".repo"):
                continue
            fpath = os.path.join(repos_dir, fname)
            content = read_file(fpath)
            if not content.strip():
                info["repo_files"].append({"file": fname, "repos": [], "empty": True})
                continue

            # Parse INI-style repo file
            parser = configparser.ConfigParser(interpolation=None)
            try:
                parser.read_string(content)
            except configparser.Error:
                # Fallback: manual parse for malformed files
                info["repo_files"].append(
                    {"file": fname, "repos": [], "parse_error": True}
                )
                continue

            file_repos = []
            for section in parser.sections():
                name = parser.get(section, "name", fallback=section)
                baseurl = parser.get(section, "baseurl", fallback="")
                enabled = parser.get(section, "enabled", fallback="0").strip()
                gpgcheck = parser.get(section, "gpgcheck", fallback="0").strip()
                sslclientcert = parser.get(section, "sslclientcert", fallback="")

                source = classify_rhel_repo(section, baseurl, name)

                repo = {
                    "id": section,
                    "name": name.strip(),
                    "baseurl": baseurl.strip(),
                    "enabled": enabled == "1",
                    "gpgcheck": gpgcheck == "1",
                    "source": source,
                }
                if sslclientcert:
                    repo["ssl_cert"] = sslclientcert.strip()

                file_repos.append(repo)
                info["repos"].append(repo)

            info["repo_files"].append({"file": fname, "repos": file_repos})

    # Detect update channel status
    has_rhui = any(r["source"] == "RHUI" and r["enabled"] for r in info["repos"])
    has_cdn = any(r["source"] == "Red Hat CDN" and r["enabled"] for r in info["repos"])
    has_epel = any(r["source"] == "EPEL" and r["enabled"] for r in info["repos"])
    has_third_party = any(
        r["source"] == "Third-party" and r["enabled"] for r in info["repos"]
    )

    if has_rhui:
        info["update_channel"] = "Azure RHUI"
    elif has_cdn:
        info["update_channel"] = "Red Hat CDN (subscription-manager)"
    else:
        info["update_channel"] = "None"

    # Warnings
    if info["subscription_manager"] == "Not registered" and not has_rhui:
        info["warnings"].append(
            "No update channel: subscription-manager not registered and no RHUI repos"
        )
    if info["subscription_manager"] == "Not registered" and has_rhui:
        info["warnings"].append(
            "subscription-manager shows 'Not registered' but RHUI is configured — "
            "this is normal for Azure PAYG/RHUI systems"
        )
    if has_epel:
        info["warnings"].append(
            "EPEL repository enabled — packages from EPEL are not supported by Red Hat"
        )
    if has_third_party:
        third = [r["name"] for r in info["repos"] if r["source"] == "Third-party" and r["enabled"]]
        info["warnings"].append(
            f"Third-party repositories enabled: {', '.join(third)}"
        )

    return info


def extract_supportconfig(path):
    """Extract repo data from a supportconfig directory."""
    info = {
        "type": "SLES",
        "subscription_manager": None,
        "repos": [],
        "modules": {},
        "warnings": [],
    }

    # Parse zypper repos from updates.txt
    updates = read_file(os.path.join(path, "updates.txt"))
    in_repos = False
    header_seen = False
    for line in updates.splitlines():
        # Only match the "zypper ... repos -d" command, not "zypper ... services"
        if "zypper" in line and "repos -d" in line and not line.strip().startswith("#--"):
            in_repos = True
            header_seen = False
            continue
        if in_repos:
            if line.startswith("#==") or (line.startswith("#") and "Command" in line):
                in_repos = False
                continue
            # Skip header lines
            if line.strip().startswith("#") or line.strip().startswith("---"):
                header_seen = True
                continue
            if not header_seen and line.strip().startswith("#"):
                continue
            if not line.strip() or line.strip().startswith("---"):
                continue

            # Parse pipe-delimited row
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 8:
                continue

            # Skip the # column (first element is usually the number)
            try:
                num = int(parts[0])
            except (ValueError, IndexError):
                continue

            alias = parts[1] if len(parts) > 1 else ""
            name = parts[2] if len(parts) > 2 else ""
            enabled = parts[3] if len(parts) > 3 else ""
            repo_type = parts[8] if len(parts) > 8 else ""
            uri = parts[9] if len(parts) > 9 else ""
            service = parts[10] if len(parts) > 10 else ""

            source = classify_sles_repo(alias, uri, service)
            module = extract_sles_module(alias)
            is_enabled = enabled.strip().lower() == "yes"

            repo = {
                "num": num,
                "alias": alias,
                "name": name,
                "enabled": is_enabled,
                "type": repo_type,
                "uri": uri,
                "source": source,
                "module": module,
            }
            info["repos"].append(repo)

            # Track modules
            if module not in info["modules"]:
                info["modules"][module] = {"enabled": 0, "disabled": 0}
            if is_enabled:
                info["modules"][module]["enabled"] += 1
            else:
                info["modules"][module]["disabled"] += 1

    # SUSEConnect status from basic-environment.txt
    basic = read_file(os.path.join(path, "basic-environment.txt"))
    in_suseconnect = False
    for line in basic.splitlines():
        if "SUSEConnect" in line and "--status" in line:
            in_suseconnect = True
            continue
        if in_suseconnect:
            if line.startswith("#"):
                in_suseconnect = False
            # Just capture it exists

    # Detect update channel
    has_cloud = any(r["source"] == "SUSE Cloud (PAYG)" and r["enabled"] for r in info["repos"])
    has_scc = any(r["source"] == "SUSE SCC" and r["enabled"] for r in info["repos"])
    has_smt = any(r["source"] == "SUSE SMT/RMT" and r["enabled"] for r in info["repos"])

    if has_cloud:
        info["update_channel"] = "SUSE Cloud (Azure PAYG)"
    elif has_scc:
        info["update_channel"] = "SUSE Customer Center"
    elif has_smt:
        info["update_channel"] = "SUSE SMT/RMT"
    else:
        info["update_channel"] = "None"

    has_third_party = any(
        r["source"] == "Third-party" and r["enabled"] for r in info["repos"]
    )
    if has_third_party:
        third = [r["name"] for r in info["repos"] if r["source"] == "Third-party" and r["enabled"]]
        info["warnings"].append(
            f"Third-party repositories enabled: {', '.join(third)}"
        )

    return info


def print_rhel_report(info, path):
    """Print RHEL repository summary."""
    dirname = os.path.basename(path.rstrip("/"))
    print(f"{'=' * 70}")
    print(f"  Repository Summary — RHEL")
    print(f"  Source: {dirname}/")
    print(f"{'=' * 70}")
    print()

    # Subscription manager
    print(f"  Subscription Manager: {info['subscription_manager']}")
    if info.get("rhui_package"):
        print(f"  RHUI Package:         {info['rhui_package']}")
    print(f"  Update Channel:       {info['update_channel']}")
    print()

    # Enabled repos by source
    print(f"  {'─' * 50}")
    print("  Enabled Repositories")
    print(f"  {'─' * 50}")

    enabled = [r for r in info["repos"] if r["enabled"]]
    if not enabled:
        print("  None")
    else:
        # Group by source
        sources = {}
        for r in enabled:
            sources.setdefault(r["source"], []).append(r)

        for source in ["RHUI", "Red Hat CDN", "Microsoft", "EPEL", "Third-party", "Unknown"]:
            repos = sources.get(source, [])
            if not repos:
                continue
            print(f"\n  [{source}] ({len(repos)} repos)")
            for r in repos:
                print(f"    {r['id']}")
                if r["baseurl"]:
                    # Show domain only for cleaner output
                    url = r["baseurl"]
                    print(f"      → {url}")

    # Disabled repos (count only)
    disabled = [r for r in info["repos"] if not r["enabled"]]
    if disabled:
        print(f"\n  Disabled: {len(disabled)} repos (debug, source, etc.)")

    # Repo files
    print()
    print(f"  {'─' * 50}")
    print("  Repo Files")
    print(f"  {'─' * 50}")
    for rf in info["repo_files"]:
        enabled_count = sum(1 for r in rf.get("repos", []) if r.get("enabled"))
        total = len(rf.get("repos", []))
        if rf.get("empty"):
            print(f"  {rf['file']:40s} (empty)")
        elif rf.get("parse_error"):
            print(f"  {rf['file']:40s} (parse error)")
        else:
            print(f"  {rf['file']:40s} {enabled_count}/{total} enabled")

    # Warnings
    if info["warnings"]:
        print()
        print(f"  {'─' * 50}")
        print("  ⚠ Warnings")
        print(f"  {'─' * 50}")
        for w in info["warnings"]:
            print(f"  • {w}")

    print()
    print(f"{'=' * 70}")


def print_sles_report(info, path):
    """Print SLES repository summary."""
    dirname = os.path.basename(path.rstrip("/"))
    print(f"{'=' * 70}")
    print(f"  Repository Summary — SLES")
    print(f"  Source: {dirname}/")
    print(f"{'=' * 70}")
    print()

    print(f"  Update Channel: {info['update_channel']}")
    print()

    # Modules/extensions
    print(f"  {'─' * 50}")
    print("  Modules / Extensions")
    print(f"  {'─' * 50}")
    for module, counts in sorted(info["modules"].items()):
        en = counts["enabled"]
        dis = counts["disabled"]
        print(f"  {module:50s} {en} enabled, {dis} disabled")

    # Enabled repos
    print()
    print(f"  {'─' * 50}")
    print("  Enabled Repositories")
    print(f"  {'─' * 50}")

    enabled = [r for r in info["repos"] if r["enabled"]]
    if not enabled:
        print("  None")
    else:
        sources = {}
        for r in enabled:
            sources.setdefault(r["source"], []).append(r)

        for source in ["SUSE Cloud (PAYG)", "SUSE SCC", "SUSE SMT/RMT", "Microsoft", "Third-party", "Unknown"]:
            repos = sources.get(source, [])
            if not repos:
                continue
            print(f"\n  [{source}] ({len(repos)} repos)")
            for r in repos:
                print(f"    {r['name']}")

    # Disabled count
    disabled = [r for r in info["repos"] if not r["enabled"]]
    if disabled:
        print(f"\n  Disabled: {len(disabled)} repos (debug, source, etc.)")

    # Warnings
    if info["warnings"]:
        print()
        print(f"  {'─' * 50}")
        print("  ⚠ Warnings")
        print(f"  {'─' * 50}")
        for w in info["warnings"]:
            print(f"  • {w}")

    print()
    print(f"{'=' * 70}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <sosreport-or-supportconfig-directory>")
        sys.exit(1)

    path = os.path.abspath(sys.argv[1])
    if not os.path.isdir(path):
        print(f"Error: {path} is not a directory")
        sys.exit(1)

    report_type = detect_type(path)
    if report_type is None:
        print(f"Error: Cannot detect sosreport or supportconfig in {path}")
        sys.exit(1)

    if report_type == "sosreport":
        info = extract_sosreport(path)
        print_rhel_report(info, path)
    else:
        info = extract_supportconfig(path)
        print_sles_report(info, path)


if __name__ == "__main__":
    main()
