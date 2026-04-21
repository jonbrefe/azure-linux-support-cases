#!/usr/bin/env python3
"""Extract storage information from sosreport or supportconfig.

Covers: SCSI devices, NVMe devices, block devices (lsblk), LVM (PVs/VGs/LVs),
filesystem usage (df), mount points, and btrfs status.
"""

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


def find_file_glob(directory, prefix):
    """Find first file in directory starting with prefix."""
    if not os.path.isdir(directory):
        return ""
    for f in sorted(os.listdir(directory)):
        if f.startswith(prefix):
            return read_file(os.path.join(directory, f))
    return ""


def extract_scc_command(text, command_pattern):
    """Extract output of a command from supportconfig section files.

    Finds the block after a line matching '# <command_pattern>' and returns
    all lines until the next section marker (#==).
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


# Azure managed disk tier limits: (max_size_gib, tier_name, iops, throughput_mbps)
PREMIUM_SSD_TIERS = [
    (4, "P1", 120, 25),
    (8, "P2", 120, 25),
    (16, "P3", 120, 25),
    (32, "P4", 120, 25),
    (64, "P6", 240, 50),
    (128, "P10", 500, 100),
    (256, "P15", 1100, 125),
    (512, "P20", 2300, 150),
    (1024, "P30", 5000, 200),
    (2048, "P40", 7500, 250),
    (4096, "P50", 7500, 250),
    (8192, "P60", 16000, 500),
    (16384, "P70", 18000, 750),
    (32767, "P80", 20000, 900),
]

STANDARD_SSD_TIERS = [
    (4, "E1", 500, 60),
    (8, "E2", 500, 60),
    (16, "E3", 500, 60),
    (32, "E4", 500, 60),
    (64, "E6", 500, 60),
    (128, "E10", 500, 60),
    (256, "E15", 500, 60),
    (512, "E20", 500, 60),
    (1024, "E30", 500, 60),
    (2048, "E40", 500, 60),
    (4096, "E50", 500, 60),
    (8192, "E60", 2000, 400),
    (16384, "E70", 4000, 600),
    (32767, "E80", 6000, 750),
]

STANDARD_HDD_TIERS = [
    (32, "S4", 500, 60),
    (64, "S6", 500, 60),
    (128, "S10", 500, 60),
    (256, "S15", 500, 60),
    (512, "S20", 500, 60),
    (1024, "S30", 500, 60),
    (2048, "S40", 500, 60),
    (4096, "S50", 500, 60),
    (8192, "S60", 1300, 300),
    (16384, "S70", 2000, 500),
    (32767, "S80", 2000, 500),
]

TIER_MAP = {
    "Premium_LRS": PREMIUM_SSD_TIERS,
    "StandardSSD_LRS": STANDARD_SSD_TIERS,
    "Standard_LRS": STANDARD_HDD_TIERS,
}

# VM-level uncached disk limits: vm_size -> (max_iops, max_throughput_mbps)
# Common Azure VM families. Add more as needed.
VM_DISK_LIMITS = {
    # Dv5 / Dasv5 / Dadsv5
    "Standard_D2as_v5": (3750, 82),
    "Standard_D4as_v5": (6400, 144),
    "Standard_D8as_v5": (12800, 200),
    "Standard_D16as_v5": (25600, 384),
    "Standard_D32as_v5": (51200, 768),
    "Standard_D48as_v5": (76800, 1148),
    "Standard_D64as_v5": (80000, 1200),
    "Standard_D96as_v5": (80000, 1315),
    "Standard_D2s_v5": (3750, 85),
    "Standard_D4s_v5": (6400, 170),
    "Standard_D8s_v5": (12800, 255),
    "Standard_D16s_v5": (25600, 500),
    "Standard_D32s_v5": (51200, 865),
    "Standard_D48s_v5": (76800, 1315),
    "Standard_D64s_v5": (80000, 1735),
    "Standard_D96s_v5": (80000, 2600),
    # Ev5 / Easv5 / Eadsv5
    "Standard_E2as_v5": (3750, 82),
    "Standard_E4as_v5": (6400, 144),
    "Standard_E8as_v5": (12800, 200),
    "Standard_E16as_v5": (25600, 384),
    "Standard_E20as_v5": (32000, 480),
    "Standard_E32as_v5": (51200, 768),
    "Standard_E48as_v5": (76800, 1148),
    "Standard_E64as_v5": (80000, 1200),
    "Standard_E96as_v5": (80000, 1315),
    "Standard_E2s_v5": (3750, 85),
    "Standard_E4s_v5": (6400, 170),
    "Standard_E8s_v5": (12800, 255),
    "Standard_E16s_v5": (25600, 500),
    "Standard_E20s_v5": (32000, 625),
    "Standard_E32s_v5": (51200, 865),
    "Standard_E48s_v5": (76800, 1315),
    "Standard_E64s_v5": (80000, 1735),
    "Standard_E96s_v5": (80000, 2600),
    # Mv2
    "Standard_M208s_v2": (80000, 3750),
    "Standard_M208ms_v2": (80000, 3750),
    "Standard_M416s_v2": (80000, 7500),
    "Standard_M416ms_v2": (80000, 7500),
    # Msv2 / Mdsv2
    "Standard_M32ms_v2": (20000, 500),
    "Standard_M64s_v2": (40000, 1000),
    "Standard_M64ms_v2": (40000, 1000),
    "Standard_M128s_v2": (80000, 2000),
    "Standard_M128ms_v2": (80000, 2000),
    "Standard_M192is_v2": (80000, 2000),
    "Standard_M192ims_v2": (80000, 2000),
    # Lsv3
    "Standard_L8s_v3": (12800, 400),
    "Standard_L16s_v3": (25600, 800),
    "Standard_L32s_v3": (51200, 1600),
    "Standard_L48s_v3": (76800, 2400),
    "Standard_L64s_v3": (80000, 3200),
    "Standard_L80s_v3": (80000, 4000),
    # Dv4 / Dsv4
    "Standard_D2s_v4": (3200, 48),
    "Standard_D4s_v4": (6400, 96),
    "Standard_D8s_v4": (12800, 192),
    "Standard_D16s_v4": (25600, 384),
    "Standard_D32s_v4": (51200, 768),
    "Standard_D48s_v4": (76800, 1152),
    "Standard_D64s_v4": (80000, 1200),
    # Ev4 / Esv4
    "Standard_E2s_v4": (3200, 48),
    "Standard_E4s_v4": (6400, 96),
    "Standard_E8s_v4": (12800, 192),
    "Standard_E16s_v4": (25600, 384),
    "Standard_E20s_v4": (32000, 480),
    "Standard_E32s_v4": (51200, 768),
    "Standard_E48s_v4": (76800, 1152),
    "Standard_E64s_v4": (80000, 1200),
    # Dasv4
    "Standard_D2as_v4": (3200, 48),
    "Standard_D4as_v4": (6400, 96),
    "Standard_D8as_v4": (12800, 192),
    "Standard_D16as_v4": (25600, 384),
    "Standard_D32as_v4": (51200, 768),
    "Standard_D48as_v4": (76800, 1152),
    "Standard_D64as_v4": (80000, 1200),
    "Standard_D96as_v4": (80000, 1200),
    # Easv4
    "Standard_E2as_v4": (3200, 48),
    "Standard_E4as_v4": (6400, 96),
    "Standard_E8as_v4": (12800, 192),
    "Standard_E16as_v4": (25600, 384),
    "Standard_E20as_v4": (32000, 480),
    "Standard_E32as_v4": (51200, 768),
    "Standard_E48as_v4": (76800, 1152),
    "Standard_E64as_v4": (80000, 1200),
    "Standard_E96as_v4": (80000, 1200),
}


def get_disk_tier(storage_type, size_gb):
    """Return (tier_name, max_iops, max_throughput_mbps) for a disk."""
    tiers = TIER_MAP.get(storage_type)
    if tiers:
        for max_size, name, iops, tput in tiers:
            if size_gb <= max_size:
                return name, iops, tput
        # Larger than any tier — use the largest
        _, name, iops, tput = tiers[-1]
        return name, iops, tput
    # PremiumV2 / Ultra — limits are provisioned, not size-based
    return None, None, None


def parse_imds_sosreport(path):
    """Parse Azure disk profile from sosreport IMDS JSON."""
    imds_path = os.path.join(path, "sos_commands", "azure", "instance_metadata.json")
    raw = read_file(imds_path)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None

    result = {"vm_size": data.get("vmSize", ""), "disks": []}
    sp = data.get("storageProfile", {})

    # OS disk
    od = sp.get("osDisk", {})
    if od:
        result["disks"].append({
            "role": "OS",
            "lun": "-",
            "name": od.get("name", ""),
            "size_gb": int(od.get("diskSizeGB", 0) or 0),
            "type": od.get("managedDisk", {}).get("storageAccountType", ""),
            "caching": od.get("caching", ""),
            "write_accel": od.get("writeAcceleratorEnabled", "false"),
            "iops_throttle": od.get("opsPerSecondThrottle", ""),
            "bps_throttle": od.get("bytesPerSecondThrottle", ""),
        })

    # Data disks
    for dd in sp.get("dataDisks", []):
        result["disks"].append({
            "role": "Data",
            "lun": str(dd.get("lun", "")),
            "name": dd.get("name", ""),
            "size_gb": int(dd.get("diskSizeGB", 0) or 0),
            "type": dd.get("managedDisk", {}).get("storageAccountType", ""),
            "caching": dd.get("caching", ""),
            "write_accel": dd.get("writeAcceleratorEnabled", "false"),
            "iops_throttle": dd.get("opsPerSecondThrottle", ""),
            "bps_throttle": dd.get("bytesPerSecondThrottle", ""),
        })

    return result


def parse_imds_supportconfig(path):
    """Parse Azure disk profile from supportconfig IMDS metadata."""
    metadata = read_file(os.path.join(path, "public_cloud", "metadata.txt"))
    if not metadata:
        return None

    lines = metadata.splitlines()
    result = {"vm_size": "", "disks": []}

    # Get vmSize
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent == 4 and stripped.startswith("vmSize:"):
            result["vm_size"] = stripped.split(":", 1)[1].strip()
            break

    # Parse storageProfile section
    in_storage = False
    in_os_disk = False
    in_data_disk = False
    current_disk = None
    in_managed = False

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if stripped == "storageProfile:":
            in_storage = True
            continue

        if not in_storage:
            continue

        # Exit storageProfile on same-level or lower indent
        if indent <= 4 and stripped and not stripped.startswith("storageProfile"):
            # Save last disk
            if current_disk:
                result["disks"].append(current_disk)
                current_disk = None
            in_storage = False
            continue

        # osDisk section
        if stripped == "osDisk:":
            if current_disk:
                result["disks"].append(current_disk)
            current_disk = {"role": "OS", "lun": "-", "name": "", "size_gb": 0,
                           "type": "", "caching": "", "write_accel": "false",
                           "iops_throttle": "", "bps_throttle": ""}
            in_os_disk = True
            in_data_disk = False
            in_managed = False
            continue

        # dataDisks[N] section
        if re.match(r"dataDisks\[\d+\]:", stripped):
            if current_disk:
                result["disks"].append(current_disk)
            current_disk = {"role": "Data", "lun": "", "name": "", "size_gb": 0,
                           "type": "", "caching": "", "write_accel": "false",
                           "iops_throttle": "", "bps_throttle": ""}
            in_data_disk = True
            in_os_disk = False
            in_managed = False
            continue

        if not current_disk:
            continue

        # managedDisk sub-section
        if stripped == "managedDisk:":
            in_managed = True
            continue

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if in_managed and key == "storageAccountType":
                current_disk["type"] = value
                in_managed = False
            elif key == "diskSizeGB" and value:
                current_disk["size_gb"] = int(value)
            elif key == "caching":
                current_disk["caching"] = value
            elif key == "lun" and value:
                current_disk["lun"] = value
            elif key == "name" and value and not current_disk["name"]:
                current_disk["name"] = value
            elif key == "writeAcceleratorEnabled":
                current_disk["write_accel"] = value
            elif key == "opsPerSecondThrottle":
                current_disk["iops_throttle"] = value
            elif key == "bytesPerSecondThrottle":
                current_disk["bps_throttle"] = value

    if current_disk:
        result["disks"].append(current_disk)

    return result if result["disks"] else None


def print_disk_profile(disk_profile):
    """Print Azure disk tier analysis with overcommit check."""
    if not disk_profile:
        return

    vm_size = disk_profile["vm_size"]
    disks = disk_profile["disks"]

    print_section("Azure Disk Profile")
    print(f"    VM Size: {vm_size}")

    vm_limits = VM_DISK_LIMITS.get(vm_size)
    if vm_limits:
        print(f"    VM Uncached Disk Cap: {vm_limits[0]:,} IOPS / {vm_limits[1]:,} MB/s")
    else:
        print(f"    VM Uncached Disk Cap: (not in lookup — verify manually)")

    print()

    # Table header
    hdr = f"    {'Role':<5} {'LUN':<4} {'Size':>6} {'Tier':<14} {'Type':<18} {'IOPS':>8} {'MB/s':>7} {'Cache':<10} {'WA':<5}"
    print(hdr)
    print(f"    {'─'*5} {'─'*4} {'─'*6} {'─'*14} {'─'*18} {'─'*8} {'─'*7} {'─'*10} {'─'*5}")

    total_iops = 0
    total_tput = 0
    has_provisioned = False

    for d in disks:
        size = d["size_gb"]
        dtype = d["type"]
        tier_name, tier_iops, tier_tput = get_disk_tier(dtype, size)

        # For PremiumV2/Ultra, use provisioned values if available
        if tier_name is None:
            iops_str = d.get("iops_throttle", "") or "prov."
            tput_str = d.get("bps_throttle", "") or "prov."
            has_provisioned = True
            try:
                total_iops += int(d.get("iops_throttle", 0) or 0)
                total_tput += int(d.get("bps_throttle", 0) or 0) // (1024 * 1024)
            except ValueError:
                pass
            tier_display = dtype.replace("_LRS", "")
        else:
            iops_str = f"{tier_iops:,}"
            tput_str = f"{tier_tput:,}"
            total_iops += tier_iops
            total_tput += tier_tput
            tier_display = tier_name

        wa = "Yes" if d.get("write_accel") == "true" else "No"
        dtype_short = dtype.replace("_LRS", "")

        print(f"    {d['role']:<5} {d['lun']:<4} {size:>5}G {tier_display:<14} {dtype_short:<18} {iops_str:>8} {tput_str:>7} {d['caching']:<10} {wa:<5}")

    # Totals
    print(f"    {'─'*5} {'─'*4} {'─'*6} {'─'*14} {'─'*18} {'─'*8} {'─'*7} {'─'*10} {'─'*5}")
    provnote = " *" if has_provisioned else ""
    print(f"    {'TOTAL':<5} {'':<4} {'':<6} {'':<14} {'':<18} {total_iops:>8,} {total_tput:>7,}")
    if has_provisioned:
        print(f"    * PremiumV2/Ultra IOPS shown only if provisioned values are in IMDS")

    # Overcommit check
    if vm_limits:
        vm_iops, vm_tput = vm_limits
        print()
        print(f"    Overcommit Analysis:")
        iops_pct = (total_iops / vm_iops * 100) if vm_iops else 0
        tput_pct = (total_tput / vm_tput * 100) if vm_tput else 0

        iops_status = "OVERCOMMITTED" if total_iops > vm_iops else "OK"
        tput_status = "OVERCOMMITTED" if total_tput > vm_tput else "OK"

        print(f"      IOPS:       {total_iops:>8,} / {vm_iops:>8,}  ({iops_pct:5.1f}%)  [{iops_status}]")
        print(f"      Throughput: {total_tput:>8,} / {vm_tput:>8,}  ({tput_pct:5.1f}%)  [{tput_status}]")

        if total_iops > vm_iops or total_tput > vm_tput:
            print()
            print(f"    ⚠  Storage is OVERCOMMITTED — disks can deliver more than the VM allows.")
            print(f"       Workloads may experience throttling at the VM level.")
        else:
            headroom_iops = vm_iops - total_iops
            headroom_tput = vm_tput - total_tput
            print(f"      Headroom:   {headroom_iops:>8,} IOPS / {headroom_tput:>5,} MB/s")


def print_section(title):
    """Print a section header."""
    print()
    print(f"  {'─' * 60}")
    print(f"  {title}")
    print(f"  {'─' * 60}")


def print_raw(text, indent=4):
    """Print text with indentation, skip empty."""
    if not text.strip():
        print(f"{' ' * indent}(not available)")
        return
    for line in text.splitlines():
        print(f"{' ' * indent}{line}")


def extract_sosreport(path):
    """Extract storage data from sosreport."""
    scsi_dir = os.path.join(path, "sos_commands", "scsi")
    block_dir = os.path.join(path, "sos_commands", "block")
    lvm_dir = os.path.join(path, "sos_commands", "lvm2")
    filesys_dir = os.path.join(path, "sos_commands", "filesys")

    data = {}

    # SCSI devices
    data["lsscsi"] = read_file(os.path.join(scsi_dir, "lsscsi_-s"))
    if not data["lsscsi"].strip():
        data["lsscsi"] = read_file(os.path.join(scsi_dir, "lsscsi"))

    # NVMe devices
    nvme_output = find_file_glob(block_dir, "nvme_list")
    if not nvme_output:
        # Check if any nvme devices appear in lsblk
        lsblk = read_file(os.path.join(block_dir, "lsblk"))
        nvme_lines = [l for l in lsblk.splitlines() if "nvme" in l.lower()]
        nvme_output = "\n".join(nvme_lines) if nvme_lines else ""
    data["nvme"] = nvme_output

    # Block devices (lsblk)
    data["lsblk"] = read_file(os.path.join(block_dir, "lsblk"))

    # Filesystem types
    data["lsblk_fs"] = read_file(os.path.join(block_dir, "lsblk_-f_-a_-l"))

    # LVM - PVs
    data["pvs"] = find_file_glob(lvm_dir, "pvs_")

    # LVM - VGs
    data["vgs"] = find_file_glob(lvm_dir, "vgs_")

    # LVM - LVs
    data["lvs"] = find_file_glob(lvm_dir, "lvs_")

    # Filesystem usage (df)
    data["df"] = read_file(os.path.join(path, "df"))

    # Mounts
    data["mount"] = read_file(os.path.join(path, "mount"))

    # Findmnt
    data["findmnt"] = read_file(os.path.join(filesys_dir, "findmnt"))

    # Btrfs
    btrfs_dir = os.path.join(path, "sos_commands")
    btrfs_show = ""
    for root_dir, dirs, files in os.walk(btrfs_dir):
        for f in files:
            if "btrfs" in f.lower() and "filesystem" in f.lower():
                btrfs_show = read_file(os.path.join(root_dir, f))
                break
    data["btrfs"] = btrfs_show

    # Device mapper
    data["dmsetup"] = read_file(
        os.path.join(path, "sos_commands", "devicemapper", "dmsetup_info_-c")
    )

    # Azure disk profile from IMDS
    data["disk_profile"] = parse_imds_sosreport(path)

    return data


def extract_supportconfig(path):
    """Extract storage data from supportconfig."""
    diskio = read_file(os.path.join(path, "fs-diskio.txt"))
    lvm_txt = read_file(os.path.join(path, "lvm.txt"))
    btrfs_txt = read_file(os.path.join(path, "fs-btrfs.txt"))

    data = {}

    # SCSI devices
    data["lsscsi"] = extract_scc_command(diskio, r"# /usr/bin/lsscsi$")

    # NVMe devices — check lsblk for nvme entries
    lsblk = extract_scc_command(diskio, r"# /bin/lsblk ")
    nvme_lines = [l for l in lsblk.splitlines() if "nvme" in l.lower()]
    # Also check for nvme list command
    nvme_list = extract_scc_command(diskio, r"nvme list")
    data["nvme"] = nvme_list if nvme_list else "\n".join(nvme_lines)

    # Block devices
    data["lsblk"] = lsblk

    # LVM - PVs
    data["pvs"] = extract_scc_command(lvm_txt, r"# /sbin/pvs$")

    # LVM - VGs
    data["vgs"] = extract_scc_command(lvm_txt, r"# /sbin/vgs$")

    # LVM - LVs
    data["lvs"] = extract_scc_command(lvm_txt, r"# /sbin/lvs$")

    # Filesystem usage
    data["df"] = extract_scc_command(diskio, r"# /bin/df -Th")

    # Findmnt
    data["findmnt"] = extract_scc_command(diskio, r"# /bin/findmnt$")

    # Btrfs
    data["btrfs"] = extract_scc_command(btrfs_txt, r"btrfs filesystem show")

    # Azure disk profile from IMDS
    data["disk_profile"] = parse_imds_supportconfig(path)

    return data


def filter_df(df_text):
    """Filter df output to show only real filesystems."""
    lines = df_text.splitlines()
    filtered = []
    for line in lines:
        # Keep header line
        if line.startswith("Filesystem") or line.startswith("Mounted"):
            filtered.append(line)
            continue
        # Skip pseudo/virtual filesystems
        if any(
            skip in line
            for skip in [
                "tmpfs",
                "devtmpfs",
                "sysfs",
                "proc",
                "cgroup",
                "pstore",
                "efivarfs",
                "bpf",
                "tracefs",
                "configfs",
                "selinuxfs",
                "mqueue",
                "hugetlbfs",
                "debugfs",
                "securityfs",
                "devpts",
                "autofs",
                "binfmt_misc",
                "sunrpc",
                "none ",
                "overlay",
                "nsfs",
                "fusectl",
            ]
        ):
            continue
        if line.strip():
            filtered.append(line)
    return "\n".join(filtered)


def filter_mounts(mount_text):
    """Filter mount output to show only real filesystems."""
    lines = mount_text.splitlines()
    filtered = []
    for line in lines:
        if any(
            skip in line
            for skip in [
                "type sysfs",
                "type proc",
                "type devtmpfs",
                "type securityfs",
                "type tmpfs",
                "type devpts",
                "type cgroup",
                "type pstore",
                "type efivarfs",
                "type bpf",
                "type tracefs",
                "type configfs",
                "type selinuxfs",
                "type autofs",
                "type mqueue",
                "type hugetlbfs",
                "type debugfs",
                "type binfmt_misc",
                "type sunrpc",
                "type fusectl",
                "type nsfs",
                "type overlay",
            ]
        ):
            continue
        if line.strip():
            filtered.append(line)
    return "\n".join(filtered)


def print_report(data, report_type, path):
    """Print formatted storage summary."""
    dirname = os.path.basename(path.rstrip("/"))
    print(f"{'=' * 70}")
    print(f"  Storage Summary — {report_type}")
    print(f"  Source: {dirname}/")
    print(f"{'=' * 70}")

    # SCSI
    print_section("SCSI Devices")
    print_raw(data.get("lsscsi", ""))

    # NVMe
    nvme = data.get("nvme", "").strip()
    if nvme:
        print_section("NVMe Devices")
        print_raw(nvme)
    else:
        print_section("NVMe Devices")
        print("    No NVMe devices detected")

    # Block devices
    print_section("Block Devices (lsblk)")
    print_raw(data.get("lsblk", ""))

    # Filesystem types
    if data.get("lsblk_fs", "").strip():
        print_section("Filesystem Types (lsblk -f)")
        print_raw(data["lsblk_fs"])

    # LVM
    pvs = data.get("pvs", "").strip()
    vgs = data.get("vgs", "").strip()
    lvs = data.get("lvs", "").strip()
    if pvs or vgs or lvs:
        print_section("LVM — Physical Volumes")
        print_raw(pvs if pvs else "(none)")

        print_section("LVM — Volume Groups")
        print_raw(vgs if vgs else "(none)")

        print_section("LVM — Logical Volumes")
        print_raw(lvs if lvs else "(none)")
    else:
        print_section("LVM")
        print("    No LVM configuration detected")

    # Device mapper
    if data.get("dmsetup", "").strip():
        print_section("Device Mapper")
        print_raw(data["dmsetup"])

    # Filesystem usage
    print_section("Filesystem Usage (df)")
    df_text = data.get("df", "")
    print_raw(filter_df(df_text) if df_text else "")

    # Mounts
    if data.get("mount", "").strip():
        print_section("Mount Points (real filesystems)")
        print_raw(filter_mounts(data["mount"]))
    elif data.get("findmnt", "").strip():
        print_section("Mount Points (findmnt)")
        print_raw(data["findmnt"])

    # Btrfs
    btrfs = data.get("btrfs", "").strip()
    if btrfs:
        print_section("Btrfs Status")
        print_raw(btrfs)

    # Azure disk profile
    print_disk_profile(data.get("disk_profile"))

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
        data = extract_sosreport(path)
    else:
        data = extract_supportconfig(path)

    print_report(data, report_type, path)


if __name__ == "__main__":
    main()
