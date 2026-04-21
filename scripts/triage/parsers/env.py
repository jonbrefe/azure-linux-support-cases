"""Environment parser — OS, kernel, IMDS, fstab, failed services."""

import json
import os
import re

from triage.common import read_file, make_warning


def parse(path, report_type, config=None):
    """Extract environment data from a sosreport or supportconfig directory.

    Returns:
        dict with environment fields, _sources dict, and _warnings list.
    """
    if report_type == "sosreport":
        return _parse_sosreport(path)
    return _parse_supportconfig(path)


def _parse_sosreport(path):
    info = {"_sources": {}, "_warnings": []}

    # OS release
    os_release = read_file(os.path.join(path, "etc", "os-release"))
    info["_sources"]["os"] = "etc/os-release"
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME="):
            info["os"] = line.split("=", 1)[1].strip('"')
        if line.startswith("VERSION_ID="):
            info["os_version"] = line.split("=", 1)[1].strip('"')

    # Kernel
    uname = read_file(os.path.join(path, "uname")).strip()
    info["_sources"]["kernel"] = "uname"
    if uname:
        parts = uname.split()
        info["kernel"] = parts[2] if len(parts) > 2 else uname
        info["architecture"] = parts[-2] if len(parts) > 2 else ""

    # Hostname
    info["hostname"] = read_file(os.path.join(path, "hostname")).strip()
    info["_sources"]["hostname"] = "hostname"

    # Uptime
    info["uptime"] = read_file(os.path.join(path, "uptime")).strip()
    info["_sources"]["uptime"] = "uptime"

    # Collection date
    info["date"] = read_file(os.path.join(path, "date")).strip()
    info["_sources"]["date"] = "date"

    # CPU count
    cpuinfo = read_file(os.path.join(path, "proc", "cpuinfo"))
    info["cpus"] = str(cpuinfo.count("processor\t:"))
    info["_sources"]["cpus"] = "proc/cpuinfo"

    # Memory
    free_output = read_file(os.path.join(path, "free")).strip()
    info["_sources"]["memory_gb"] = "free"
    for line in free_output.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            if len(parts) >= 2:
                total_kb = int(parts[1])
                info["memory_gb"] = f"{total_kb / 1024 / 1024:.0f}"

    # Hardware (dmidecode)
    dmidecode = read_file(os.path.join(path, "dmidecode"))
    info["_sources"]["manufacturer"] = "dmidecode"
    in_system = False
    for line in dmidecode.splitlines():
        if "System Information" in line:
            in_system = True
        elif in_system:
            if "Manufacturer:" in line:
                info["manufacturer"] = line.split(":", 1)[1].strip()
            elif "Product Name:" in line:
                info["product"] = line.split(":", 1)[1].strip()
                break

    # Azure IMDS
    imds_path = os.path.join(path, "sos_commands", "azure", "instance_metadata.json")
    imds_raw = read_file(imds_path)
    info["_sources"]["imds"] = "sos_commands/azure/instance_metadata.json"
    if imds_raw:
        try:
            imds = json.loads(imds_raw)
            info["imds"] = {
                "vm_name": imds.get("name", ""),
                "resource_group": imds.get("resourceGroupName", ""),
                "subscription_id": imds.get("subscriptionId", ""),
                "location": imds.get("location", ""),
                "vm_size": imds.get("vmSize", ""),
                "offer": imds.get("offer", ""),
                "publisher": imds.get("publisher", ""),
                "sku": imds.get("sku", ""),
                "license_type": imds.get("licenseType", ""),
                "os_type": imds.get("osType", ""),
                "vm_id": imds.get("vmId", ""),
            }
            # Image reference
            storage = imds.get("storageProfile", {})
            img_ref = storage.get("imageReference", {})
            if img_ref:
                info["imds"]["image_offer"] = img_ref.get("offer", "")
                info["imds"]["image_publisher"] = img_ref.get("publisher", "")
                info["imds"]["image_sku"] = img_ref.get("sku", "")
                info["imds"]["image_version"] = img_ref.get("version", "")
                info["imds"]["image_id"] = img_ref.get("id", "")
            # Tags
            tags = imds.get("tags", "")
            if tags:
                info["imds"]["tags"] = tags
        except (json.JSONDecodeError, TypeError):
            info["imds"] = {"error": "Failed to parse IMDS JSON"}

    # Failed services
    failed_path = os.path.join(
        path, "sos_commands", "systemd", "systemctl_list-units_--failed"
    )
    failed_output = read_file(failed_path)
    info["_sources"]["failed_services"] = (
        "sos_commands/systemd/systemctl_list-units_--failed"
    )
    failed_services = []
    for line in failed_output.splitlines():
        line = line.strip()
        if line.startswith("●"):
            parts = line.split()
            if len(parts) >= 2:
                failed_services.append(parts[1])
    info["failed_services"] = failed_services

    if failed_services:
        info["_warnings"].append(make_warning(
            "ENV",
            f"{len(failed_services)} failed systemd service(s)",
            evidence=", ".join(failed_services),
            impact="Failed services may indicate incomplete boot or misconfiguration",
            next_step="Review each failed service with systemctl status <service>",
        ))

    # Subscription manager
    rhsm_path = os.path.join(path, "sos_commands", "subscription_manager")
    if os.path.isdir(rhsm_path):
        identity = read_file(
            os.path.join(rhsm_path, "subscription-manager_identity")
        )
        if identity:
            info["subscription_manager"] = identity.strip()
            info["_sources"]["subscription_manager"] = (
                "sos_commands/subscription_manager/subscription-manager_identity"
            )

    # fstab
    fstab = read_file(os.path.join(path, "etc", "fstab")).strip()
    info["_sources"]["fstab"] = "etc/fstab"
    if fstab:
        info["fstab"] = fstab

    return info


def _parse_supportconfig(path):
    info = {"_sources": {}, "_warnings": []}

    basic = read_file(os.path.join(path, "basic-environment.txt"))
    info["_sources"]["os"] = "basic-environment.txt"

    # OS release
    in_os_release = False
    for line in basic.splitlines():
        if "# /etc/os-release" in line:
            in_os_release = True
            continue
        if in_os_release:
            if line.startswith("#"):
                in_os_release = False
                continue
            if line.startswith("PRETTY_NAME="):
                info["os"] = line.split("=", 1)[1].strip('"')
            if line.startswith("VERSION_ID="):
                info["os_version"] = line.split("=", 1)[1].strip('"')
            if line.startswith("VARIANT_ID="):
                info["variant"] = line.split("=", 1)[1].strip('"')

    # Kernel and arch from uname
    info["_sources"]["kernel"] = "basic-environment.txt (uname)"
    for line in basic.splitlines():
        if line.startswith("Linux ") and "x86_64" in line:
            parts = line.split()
            info["hostname"] = parts[1] if len(parts) > 1 else ""
            info["kernel"] = parts[2] if len(parts) > 2 else ""
            info["architecture"] = "x86_64"
            break

    # Hardware
    info["_sources"]["manufacturer"] = "basic-environment.txt"
    for line in basic.splitlines():
        if "Manufacturer:" in line and "manufacturer" not in info:
            info["manufacturer"] = line.split(":", 1)[1].strip()
        if "Hardware:" in line:
            info["product"] = line.split(":", 1)[1].strip()

    # Collection date
    for line in basic.splitlines():
        if line.startswith("# /bin/date"):
            continue
        m = re.match(r"^[A-Z][a-z]{2} [A-Z]", line)
        if m:
            info["date"] = line.strip()
            break

    # Azure IMDS
    metadata_path = os.path.join(path, "public_cloud", "metadata.txt")
    metadata = read_file(metadata_path)
    info["_sources"]["imds"] = "public_cloud/metadata.txt"
    if metadata:
        imds = {}
        key_map = {
            "name": "vm_name",
            "resourceGroupName": "resource_group",
            "subscriptionId": "subscription_id",
            "location": "location",
            "vmSize": "vm_size",
            "offer": "offer",
            "publisher": "publisher",
            "sku": "sku",
            "licenseType": "license_type",
            "osType": "os_type",
            "vmId": "vm_id",
        }
        for line in metadata.splitlines():
            stripped = line.strip()
            if ":" in stripped and not stripped.startswith("#"):
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                indent = len(line) - len(line.lstrip())
                if key in key_map and value and indent == 4:
                    imds[key_map[key]] = value
        if imds:
            info["imds"] = imds

    # Billing flavor
    billing = read_file(
        os.path.join(path, "public_cloud", "billingflavor.txt")
    ).strip()
    if billing:
        info["billing"] = billing.splitlines()[0]

    # Framework (cloud type)
    framework = read_file(os.path.join(path, "public_cloud", "framework.txt"))
    for line in framework.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            info["cloud"] = line
            break

    # fstab from fs-diskio.txt
    diskio = read_file(os.path.join(path, "fs-diskio.txt"))
    info["_sources"]["fstab"] = "fs-diskio.txt"
    fstab_lines = []
    capturing = False
    for line in diskio.splitlines():
        if "# /etc/fstab" in line:
            capturing = True
            continue
        if capturing:
            if line.startswith("#=="):
                break
            fstab_lines.append(line)
    fstab = "\n".join(fstab_lines).strip()
    if fstab:
        info["fstab"] = fstab

    # Failed services from systemd.txt
    systemd = read_file(os.path.join(path, "systemd.txt"))
    info["_sources"]["failed_services"] = "systemd.txt"
    failed_services = []
    in_failed = False
    for line in systemd.splitlines():
        if "systemctl --failed" in line:
            in_failed = True
            continue
        if in_failed:
            if line.startswith("#") or line.startswith("LOAD"):
                in_failed = False
                continue
            if line.strip().startswith("●"):
                parts = line.split()
                if len(parts) >= 2:
                    failed_services.append(parts[1])
    info["failed_services"] = failed_services

    if failed_services:
        info["_warnings"].append(make_warning(
            "ENV",
            f"{len(failed_services)} failed systemd service(s)",
            evidence=", ".join(failed_services),
            impact="Failed services may indicate incomplete boot or misconfiguration",
            next_step="Review each failed service with systemctl status <service>",
        ))

    # CPU count
    proc = read_file(os.path.join(path, "proc.txt"))
    info["_sources"]["cpus"] = "proc.txt"
    cpu_count = proc.count("processor\t:")
    if cpu_count:
        info["cpus"] = str(cpu_count)

    # Memory
    info["_sources"]["memory_gb"] = "basic-environment.txt"
    for line in basic.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    total_kb = int(parts[1])
                    info["memory_gb"] = f"{total_kb / 1024 / 1024:.0f}"
                except ValueError:
                    pass

    return info
