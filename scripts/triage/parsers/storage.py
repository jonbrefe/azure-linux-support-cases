"""Storage parser — SCSI, NVMe, LVM, df, mounts, btrfs, Azure disk tiers."""

import json
import os
import re

from triage.common import (
    read_file,
    extract_scc_command,
    find_file_glob,
    make_warning,
)

# ---------------------------------------------------------------------------
# Azure managed disk tier limits: (max_size_gib, tier_name, iops, throughput_mbps)
# ---------------------------------------------------------------------------

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


def _load_custom_tiers(config):
    """Load custom disk tiers from config-specified JSON if provided."""
    if not config:
        return TIER_MAP
    path = config.get("disk_tiers_db_path")
    if not path or not os.path.isfile(path):
        return TIER_MAP
    with open(path, "r") as f:
        return json.load(f)


def _load_custom_vm_limits(config):
    """Load custom VM limits from config-specified JSON if provided."""
    if not config:
        return VM_DISK_LIMITS
    path = config.get("vm_size_limits_db_path")
    if not path or not os.path.isfile(path):
        return VM_DISK_LIMITS
    with open(path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tier resolution
# ---------------------------------------------------------------------------

def get_disk_tier(storage_type, size_gb, tier_map=None):
    """Return (tier_name, max_iops, max_throughput_mbps) for a disk."""
    if tier_map is None:
        tier_map = TIER_MAP
    tiers = tier_map.get(storage_type)
    if tiers:
        for max_size, name, iops, tput in tiers:
            if size_gb <= max_size:
                return name, iops, tput
        _, name, iops, tput = tiers[-1]
        return name, iops, tput
    return None, None, None


# ---------------------------------------------------------------------------
# IMDS disk profile parsing
# ---------------------------------------------------------------------------

def _parse_imds_sosreport(path):
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


def _parse_imds_supportconfig(path):
    """Parse Azure disk profile from supportconfig IMDS metadata."""
    metadata = read_file(os.path.join(path, "public_cloud", "metadata.txt"))
    if not metadata:
        return None

    lines = metadata.splitlines()
    result = {"vm_size": "", "disks": []}

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent == 4 and stripped.startswith("vmSize:"):
            result["vm_size"] = stripped.split(":", 1)[1].strip()
            break

    in_storage = False
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

        if indent <= 4 and stripped and not stripped.startswith("storageProfile"):
            if current_disk:
                result["disks"].append(current_disk)
                current_disk = None
            in_storage = False
            continue

        if stripped == "osDisk:":
            if current_disk:
                result["disks"].append(current_disk)
            current_disk = {
                "role": "OS", "lun": "-", "name": "", "size_gb": 0,
                "type": "", "caching": "", "write_accel": "false",
                "iops_throttle": "", "bps_throttle": "",
            }
            in_managed = False
            continue

        if re.match(r"dataDisks\[\d+\]:", stripped):
            if current_disk:
                result["disks"].append(current_disk)
            current_disk = {
                "role": "Data", "lun": "", "name": "", "size_gb": 0,
                "type": "", "caching": "", "write_accel": "false",
                "iops_throttle": "", "bps_throttle": "",
            }
            in_managed = False
            continue

        if not current_disk:
            continue

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


# ---------------------------------------------------------------------------
# Disk profile analysis
# ---------------------------------------------------------------------------

def _analyze_disk_profile(disk_profile, config=None):
    """Analyze disk profile and compute tier + overcommit data.

    Returns dict with enriched disk list and overcommit results.
    """
    if not disk_profile:
        return None

    tier_map = _load_custom_tiers(config)
    vm_limits = _load_custom_vm_limits(config)

    vm_size = disk_profile["vm_size"]
    disks = disk_profile["disks"]

    enriched_disks = []
    total_iops = 0
    total_tput = 0
    has_provisioned = False

    for d in disks:
        size = d["size_gb"]
        dtype = d["type"]
        tier_name, tier_iops, tier_tput = get_disk_tier(dtype, size, tier_map)

        if tier_name is None:
            has_provisioned = True
            try:
                d_iops = int(d.get("iops_throttle", 0) or 0)
                d_tput = int(d.get("bps_throttle", 0) or 0) // (1024 * 1024)
            except ValueError:
                d_iops = 0
                d_tput = 0
            total_iops += d_iops
            total_tput += d_tput
            tier_display = dtype.replace("_LRS", "")
            iops_str = d.get("iops_throttle", "") or "prov."
            tput_str = d.get("bps_throttle", "") or "prov."
        else:
            total_iops += tier_iops
            total_tput += tier_tput
            tier_display = tier_name
            iops_str = f"{tier_iops:,}"
            tput_str = f"{tier_tput:,}"

        enriched_disks.append({
            **d,
            "tier": tier_display,
            "tier_iops": iops_str,
            "tier_tput": tput_str,
        })

    vm_limit = vm_limits.get(vm_size)
    overcommit = None
    if vm_limit:
        vm_iops, vm_tput = vm_limit
        iops_pct = (total_iops / vm_iops * 100) if vm_iops else 0
        tput_pct = (total_tput / vm_tput * 100) if vm_tput else 0
        overcommit = {
            "vm_iops": vm_iops,
            "vm_tput": vm_tput,
            "total_iops": total_iops,
            "total_tput": total_tput,
            "iops_pct": iops_pct,
            "tput_pct": tput_pct,
            "iops_overcommitted": total_iops > vm_iops,
            "tput_overcommitted": total_tput > vm_tput,
        }

    return {
        "vm_size": vm_size,
        "disks": enriched_disks,
        "total_iops": total_iops,
        "total_tput": total_tput,
        "has_provisioned": has_provisioned,
        "vm_limit": vm_limit,
        "overcommit": overcommit,
    }


# ---------------------------------------------------------------------------
# Filesystem filters
# ---------------------------------------------------------------------------

_PSEUDO_FS = [
    "tmpfs", "devtmpfs", "sysfs", "proc", "cgroup", "pstore",
    "efivarfs", "bpf", "tracefs", "configfs", "selinuxfs", "mqueue",
    "hugetlbfs", "debugfs", "securityfs", "devpts", "autofs",
    "binfmt_misc", "sunrpc", "none ", "overlay", "nsfs", "fusectl",
]

_PSEUDO_MOUNT_TYPES = [
    "type sysfs", "type proc", "type devtmpfs", "type securityfs",
    "type tmpfs", "type devpts", "type cgroup", "type pstore",
    "type efivarfs", "type bpf", "type tracefs", "type configfs",
    "type selinuxfs", "type autofs", "type mqueue", "type hugetlbfs",
    "type debugfs", "type binfmt_misc", "type sunrpc", "type fusectl",
    "type nsfs", "type overlay",
]


def filter_df(df_text):
    """Filter df output to show only real filesystems."""
    lines = df_text.splitlines()
    filtered = []
    for line in lines:
        if line.startswith("Filesystem") or line.startswith("Mounted"):
            filtered.append(line)
            continue
        if any(skip in line for skip in _PSEUDO_FS):
            continue
        if line.strip():
            filtered.append(line)
    return "\n".join(filtered)


def filter_mounts(mount_text):
    """Filter mount output to show only real filesystems."""
    lines = mount_text.splitlines()
    filtered = []
    for line in lines:
        if any(skip in line for skip in _PSEUDO_MOUNT_TYPES):
            continue
        if line.strip():
            filtered.append(line)
    return "\n".join(filtered)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse(path, report_type, config=None):
    """Extract storage data from a sosreport or supportconfig directory.

    Returns:
        dict with storage data, disk profile analysis, _sources, _warnings.
    """
    if report_type == "sosreport":
        data = _extract_sosreport(path)
    else:
        data = _extract_supportconfig(path)

    # Enrich disk profile
    data["disk_analysis"] = _analyze_disk_profile(
        data.get("disk_profile"), config
    )

    # Filter df and mounts for clean output
    if data.get("df"):
        data["df_filtered"] = filter_df(data["df"])
    if data.get("mount"):
        data["mount_filtered"] = filter_mounts(data["mount"])

    # Warnings
    data["_warnings"] = []
    analysis = data.get("disk_analysis")
    if analysis and analysis.get("overcommit"):
        oc = analysis["overcommit"]
        if oc["iops_overcommitted"] or oc["tput_overcommitted"]:
            data["_warnings"].append(make_warning(
                "STORAGE",
                "Disk IOPS/throughput overcommitted at VM level",
                evidence=(
                    f"Total disk: {oc['total_iops']:,} IOPS / {oc['total_tput']:,} MB/s; "
                    f"VM cap: {oc['vm_iops']:,} IOPS / {oc['vm_tput']:,} MB/s"
                ),
                impact="Workloads may experience throttling at the VM level",
                next_step="Consider upsizing the VM or reducing disk count/tiers",
            ))

    # Check for SCSI device name instability
    lsscsi = data.get("lsscsi", "").strip()
    nvme = data.get("nvme", "").strip()
    if lsscsi and not nvme:
        data["_warnings"].append(make_warning(
            "STORAGE",
            "SCSI-based disk layout — device names not guaranteed across reboots",
            evidence="lsscsi shows SCSI devices with /dev/sd* names",
            impact="Device names (e.g. sdg) may change after reboot or disk hotplug",
            next_step="Use persistent identifiers (UUID, LVM, /dev/disk/by-*) in fstab",
        ))

    return data


def _extract_sosreport(path):
    """Extract storage data from sosreport."""
    scsi_dir = os.path.join(path, "sos_commands", "scsi")
    block_dir = os.path.join(path, "sos_commands", "block")
    lvm_dir = os.path.join(path, "sos_commands", "lvm2")
    filesys_dir = os.path.join(path, "sos_commands", "filesys")

    data = {
        "_sources": {
            "lsscsi": "sos_commands/scsi/lsscsi",
            "lsblk": "sos_commands/block/lsblk",
            "lvm": "sos_commands/lvm2/",
            "df": "df",
            "mount": "mount",
            "disk_profile": "sos_commands/azure/instance_metadata.json",
        },
    }

    # SCSI devices
    data["lsscsi"] = read_file(os.path.join(scsi_dir, "lsscsi_-s"))
    if not data["lsscsi"].strip():
        data["lsscsi"] = read_file(os.path.join(scsi_dir, "lsscsi"))

    # NVMe devices
    nvme_output = find_file_glob(block_dir, "nvme_list")
    if not nvme_output:
        lsblk = read_file(os.path.join(block_dir, "lsblk"))
        nvme_lines = [l for l in lsblk.splitlines() if "nvme" in l.lower()]
        nvme_output = "\n".join(nvme_lines) if nvme_lines else ""
    data["nvme"] = nvme_output

    # Block devices
    data["lsblk"] = read_file(os.path.join(block_dir, "lsblk"))

    # Filesystem types
    data["lsblk_fs"] = read_file(os.path.join(block_dir, "lsblk_-f_-a_-l"))

    # LVM
    data["pvs"] = find_file_glob(lvm_dir, "pvs_")
    data["vgs"] = find_file_glob(lvm_dir, "vgs_")
    data["lvs"] = find_file_glob(lvm_dir, "lvs_")

    # Filesystem usage
    data["df"] = read_file(os.path.join(path, "df"))

    # Mounts
    data["mount"] = read_file(os.path.join(path, "mount"))

    # Findmnt
    data["findmnt"] = read_file(os.path.join(filesys_dir, "findmnt"))

    # Btrfs
    btrfs_show = ""
    btrfs_dir = os.path.join(path, "sos_commands")
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

    # Azure disk profile
    data["disk_profile"] = _parse_imds_sosreport(path)

    return data


def _extract_supportconfig(path):
    """Extract storage data from supportconfig."""
    diskio = read_file(os.path.join(path, "fs-diskio.txt"))
    lvm_txt = read_file(os.path.join(path, "lvm.txt"))
    btrfs_txt = read_file(os.path.join(path, "fs-btrfs.txt"))

    data = {
        "_sources": {
            "lsscsi": "fs-diskio.txt",
            "lsblk": "fs-diskio.txt",
            "lvm": "lvm.txt",
            "df": "fs-diskio.txt",
            "disk_profile": "public_cloud/metadata.txt",
        },
    }

    # SCSI
    data["lsscsi"] = extract_scc_command(diskio, r"# /usr/bin/lsscsi$")

    # NVMe
    lsblk = extract_scc_command(diskio, r"# /bin/lsblk ")
    nvme_lines = [l for l in lsblk.splitlines() if "nvme" in l.lower()]
    nvme_list = extract_scc_command(diskio, r"nvme list")
    data["nvme"] = nvme_list if nvme_list else "\n".join(nvme_lines)

    # Block devices
    data["lsblk"] = lsblk

    # LVM
    data["pvs"] = extract_scc_command(lvm_txt, r"# /sbin/pvs$")
    data["vgs"] = extract_scc_command(lvm_txt, r"# /sbin/vgs$")
    data["lvs"] = extract_scc_command(lvm_txt, r"# /sbin/lvs$")

    # Filesystem usage
    data["df"] = extract_scc_command(diskio, r"# /bin/df -Th")

    # Findmnt
    data["findmnt"] = extract_scc_command(diskio, r"# /bin/findmnt$")

    # Btrfs
    data["btrfs"] = extract_scc_command(btrfs_txt, r"btrfs filesystem show")

    # Azure disk profile
    data["disk_profile"] = _parse_imds_supportconfig(path)

    return data
