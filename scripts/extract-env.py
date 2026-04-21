#!/usr/bin/env python3
"""Extract basic environment information from sosreport or supportconfig."""

import json
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


def extract_sosreport(path):
    """Extract environment data from a sosreport directory."""
    info = {}

    # OS release
    os_release = read_file(os.path.join(path, "etc", "os-release"))
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME="):
            info["os"] = line.split("=", 1)[1].strip('"')
        if line.startswith("VERSION_ID="):
            info["os_version"] = line.split("=", 1)[1].strip('"')

    # Kernel
    uname = read_file(os.path.join(path, "uname")).strip()
    if uname:
        parts = uname.split()
        info["kernel"] = parts[2] if len(parts) > 2 else uname
        info["architecture"] = parts[-2] if len(parts) > 2 else ""

    # Hostname
    info["hostname"] = read_file(os.path.join(path, "hostname")).strip()

    # Uptime
    info["uptime"] = read_file(os.path.join(path, "uptime")).strip()

    # Collection date
    info["date"] = read_file(os.path.join(path, "date")).strip()

    # CPU count
    cpuinfo = read_file(os.path.join(path, "proc", "cpuinfo"))
    info["cpus"] = str(cpuinfo.count("processor\t:"))

    # Memory
    free_output = read_file(os.path.join(path, "free")).strip()
    for line in free_output.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            if len(parts) >= 2:
                total_kb = int(parts[1])
                info["memory_gb"] = f"{total_kb / 1024 / 1024:.0f}"

    # Hardware
    dmidecode = read_file(os.path.join(path, "dmidecode"))
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
            # Tags (redacted for display)
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
    failed_services = []
    for line in failed_output.splitlines():
        line = line.strip()
        if line.startswith("●"):
            parts = line.split()
            if len(parts) >= 2:
                failed_services.append(parts[1])
    info["failed_services"] = failed_services

    # Subscription manager
    rhsm_path = os.path.join(
        path, "sos_commands", "subscription_manager"
    )
    if os.path.isdir(rhsm_path):
        identity = read_file(
            os.path.join(rhsm_path, "subscription-manager_identity")
        )
        if identity:
            info["subscription_manager"] = identity.strip()

    # fstab
    fstab = read_file(os.path.join(path, "etc", "fstab")).strip()
    if fstab:
        info["fstab"] = fstab

    return info


def extract_supportconfig(path):
    """Extract environment data from a supportconfig directory."""
    info = {}

    basic = read_file(os.path.join(path, "basic-environment.txt"))

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
    for line in basic.splitlines():
        if line.startswith("Linux ") and "x86_64" in line:
            parts = line.split()
            info["hostname"] = parts[1] if len(parts) > 1 else ""
            info["kernel"] = parts[2] if len(parts) > 2 else ""
            info["architecture"] = "x86_64"
            break

    # Hardware
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
    if metadata:
        imds = {}
        # Supportconfig IMDS is YAML-like with indentation
        # Parse flat key-value pairs from indented lines
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
                # Only map keys at the right indentation depth
                # (4 spaces = compute-level attributes)
                indent = len(line) - len(line.lstrip())
                if key in key_map and value and indent == 4:
                    imds[key_map[key]] = value
        if imds:
            info["imds"] = imds

    # Billing flavor
    billing = read_file(os.path.join(path, "public_cloud", "billingflavor.txt")).strip()
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

    # CPU count
    proc = read_file(os.path.join(path, "proc.txt"))
    cpu_count = proc.count("processor\t:")
    if cpu_count:
        info["cpus"] = str(cpu_count)

    # Memory
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


def print_report(info, report_type, path):
    """Print formatted environment summary."""
    dirname = os.path.basename(path.rstrip("/"))
    print(f"{'=' * 70}")
    print(f"  Environment Summary — {report_type}")
    print(f"  Source: {dirname}/")
    print(f"{'=' * 70}")
    print()

    print(f"  OS:            {info.get('os', 'N/A')}")
    print(f"  Version:       {info.get('os_version', 'N/A')}")
    if info.get("variant"):
        print(f"  Variant:       {info['variant']}")
    print(f"  Kernel:        {info.get('kernel', 'N/A')}")
    print(f"  Architecture:  {info.get('architecture', 'N/A')}")
    print(f"  Hostname:      {info.get('hostname', 'N/A')}")
    print(f"  CPUs:          {info.get('cpus', 'N/A')}")
    print(f"  Memory:        {info.get('memory_gb', 'N/A')} GB")
    print(f"  Manufacturer:  {info.get('manufacturer', 'N/A')}")
    print(f"  Product:       {info.get('product', 'N/A')}")
    if info.get("date"):
        print(f"  Collected:     {info['date']}")
    if info.get("uptime"):
        print(f"  Uptime:        {info['uptime']}")
    if info.get("billing"):
        print(f"  Billing:       {info['billing']}")
    if info.get("cloud"):
        print(f"  Cloud:         {info['cloud']}")

    # IMDS
    imds = info.get("imds", {})
    if imds:
        print()
        print(f"  {'─' * 50}")
        print("  Azure IMDS")
        print(f"  {'─' * 50}")
        print(f"  VM Name:         {imds.get('vm_name', 'N/A')}")
        print(f"  Resource Group:  {imds.get('resource_group', 'N/A')}")
        print(f"  Subscription:    {imds.get('subscription_id', 'N/A')}")
        print(f"  Location:        {imds.get('location', 'N/A')}")
        print(f"  VM Size:         {imds.get('vm_size', 'N/A')}")
        print(f"  VM ID:           {imds.get('vm_id', 'N/A')}")
        print(f"  OS Type:         {imds.get('os_type', 'N/A')}")
        print(f"  License Type:    {imds.get('license_type', 'N/A')}")
        print(f"  Publisher:       {imds.get('publisher', 'N/A')}")
        print(f"  Offer:           {imds.get('offer', 'N/A')}")
        print(f"  SKU:             {imds.get('sku', 'N/A')}")
        # Image reference (sosreport)
        if imds.get("image_id") or imds.get("image_offer"):
            print()
            print("  Image Reference:")
            if imds.get("image_id"):
                print(f"    ID:          {imds['image_id']}")
            if imds.get("image_publisher"):
                print(f"    Publisher:   {imds['image_publisher']}")
            if imds.get("image_offer"):
                print(f"    Offer:       {imds['image_offer']}")
            if imds.get("image_sku"):
                print(f"    SKU:         {imds['image_sku']}")
            if imds.get("image_version"):
                print(f"    Version:     {imds['image_version']}")

    # Failed services
    failed = info.get("failed_services", [])
    print()
    print(f"  {'─' * 50}")
    print("  Failed Services")
    print(f"  {'─' * 50}")
    if failed:
        for svc in failed:
            print(f"  ● {svc}")
    else:
        print("  None detected")

    # Subscription manager
    if info.get("subscription_manager"):
        print()
        print(f"  {'─' * 50}")
        print("  Subscription Manager")
        print(f"  {'─' * 50}")
        for line in info["subscription_manager"].splitlines():
            if line.strip():
                print(f"  {line.strip()}")

    # fstab
    if info.get("fstab"):
        print()
        print(f"  {'─' * 50}")
        print("  /etc/fstab")
        print(f"  {'─' * 50}")
        for line in info["fstab"].splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                print(f"    {stripped}")

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
    else:
        info = extract_supportconfig(path)

    print_report(info, report_type, path)


if __name__ == "__main__":
    main()
