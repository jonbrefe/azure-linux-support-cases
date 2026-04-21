"""Repository parser — subscription, RHUI, repos, update channel, warnings."""

import configparser
import os
import re

from triage.common import read_file, make_warning


def _classify_rhel_repo(repo_id, baseurl, name):
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


def _classify_sles_repo(alias, uri, service):
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


def _extract_sles_module(alias):
    """Extract SLES module/extension name from repo alias."""
    if ":" in alias:
        service_part = alias.split(":")[0]
        return service_part.replace("_x86_64", "").replace("_", " ")
    return alias


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse(path, report_type, config=None):
    """Extract repository data from a sosreport or supportconfig directory.

    Returns:
        dict with repo data, update channel, _sources, _warnings.
    """
    if report_type == "sosreport":
        return _parse_sosreport(path)
    return _parse_supportconfig(path)


# ---------------------------------------------------------------------------
# Sosreport (RHEL)
# ---------------------------------------------------------------------------

def _parse_sosreport(path):
    info = {
        "type": "RHEL",
        "subscription_manager": None,
        "rhui_package": None,
        "repos": [],
        "repo_files": [],
        "_warnings": [],
        "_sources": {
            "subscription_manager": (
                "sos_commands/subscription_manager/subscription-manager_identity"
            ),
            "repos": "etc/yum.repos.d/",
            "rhui_package": "installed-rpms",
        },
    }

    # Subscription manager identity
    sub_mgr_path = os.path.join(
        path, "sos_commands", "subscription_manager",
        "subscription-manager_identity",
    )
    sub_mgr = read_file(sub_mgr_path).strip()
    if "not yet registered" in sub_mgr.lower() or not sub_mgr:
        info["subscription_manager"] = "Not registered"
    else:
        info["subscription_manager"] = sub_mgr

    # RHUI package
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
                info["repo_files"].append(
                    {"file": fname, "repos": [], "empty": True}
                )
                continue

            parser = configparser.ConfigParser(interpolation=None)
            try:
                parser.read_string(content)
            except configparser.Error:
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
                sslclientcert = parser.get(
                    section, "sslclientcert", fallback=""
                )

                source = _classify_rhel_repo(section, baseurl, name)

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

    # Detect update channel
    has_rhui = any(
        r["source"] == "RHUI" and r["enabled"] for r in info["repos"]
    )
    has_cdn = any(
        r["source"] == "Red Hat CDN" and r["enabled"] for r in info["repos"]
    )
    has_epel = any(
        r["source"] == "EPEL" and r["enabled"] for r in info["repos"]
    )
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
        info["_warnings"].append(make_warning(
            "REPO",
            "No update channel: subscription-manager not registered and no RHUI repos",
            evidence="subscription-manager identity: Not registered; no RHUI repos found",
            impact="System cannot receive security updates",
            next_step="Register with subscription-manager or configure RHUI",
        ))
    if info["subscription_manager"] == "Not registered" and has_rhui:
        info["_warnings"].append(make_warning(
            "REPO",
            "subscription-manager 'Not registered' with RHUI configured — normal for Azure PAYG",
            evidence="subscription-manager identity: Not registered; RHUI repos present",
            impact="None — expected on PAYG/RHUI systems",
            next_step="No action required",
        ))
    if has_epel:
        info["_warnings"].append(make_warning(
            "REPO",
            "EPEL repository enabled",
            evidence="EPEL repo(s) enabled in yum.repos.d",
            impact="Packages from EPEL are not supported by Red Hat",
            next_step="Verify if EPEL packages are in use; consider disabling if not needed",
        ))
    if has_third_party:
        third = [
            r["name"] for r in info["repos"]
            if r["source"] == "Third-party" and r["enabled"]
        ]
        info["_warnings"].append(make_warning(
            "REPO",
            f"Third-party repositories enabled: {', '.join(third)}",
            evidence="Non-standard repo(s) in yum.repos.d",
            impact="Third-party packages may conflict with vendor-supported packages",
            next_step="Review third-party repos and validate compatibility",
        ))

    return info


# ---------------------------------------------------------------------------
# Supportconfig (SLES)
# ---------------------------------------------------------------------------

def _parse_supportconfig(path):
    info = {
        "type": "SLES",
        "subscription_manager": None,
        "repos": [],
        "modules": {},
        "_warnings": [],
        "_sources": {
            "repos": "updates.txt",
            "modules": "updates.txt",
        },
    }

    updates = read_file(os.path.join(path, "updates.txt"))
    in_repos = False
    header_seen = False
    for line in updates.splitlines():
        if ("zypper" in line and "repos -d" in line
                and not line.strip().startswith("#--")):
            in_repos = True
            header_seen = False
            continue
        if in_repos:
            if line.startswith("#==") or (
                line.startswith("#") and "Command" in line
            ):
                in_repos = False
                continue
            if line.strip().startswith("#") or line.strip().startswith("---"):
                header_seen = True
                continue
            if not header_seen and line.strip().startswith("#"):
                continue
            if not line.strip() or line.strip().startswith("---"):
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 8:
                continue

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

            source = _classify_sles_repo(alias, uri, service)
            module = _extract_sles_module(alias)
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

            if module not in info["modules"]:
                info["modules"][module] = {"enabled": 0, "disabled": 0}
            if is_enabled:
                info["modules"][module]["enabled"] += 1
            else:
                info["modules"][module]["disabled"] += 1

    # Detect update channel
    has_cloud = any(
        r["source"] == "SUSE Cloud (PAYG)" and r["enabled"]
        for r in info["repos"]
    )
    has_scc = any(
        r["source"] == "SUSE SCC" and r["enabled"] for r in info["repos"]
    )
    has_smt = any(
        r["source"] == "SUSE SMT/RMT" and r["enabled"] for r in info["repos"]
    )

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
        third = [
            r["name"] for r in info["repos"]
            if r["source"] == "Third-party" and r["enabled"]
        ]
        info["_warnings"].append(make_warning(
            "REPO",
            f"Third-party repositories enabled: {', '.join(third)}",
            evidence="Non-standard repo(s) in zypper repos",
            impact="Third-party packages may conflict with vendor-supported packages",
            next_step="Review third-party repos and validate compatibility",
        ))

    return info
