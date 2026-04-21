"""DFM markdown output — renders extracted data as DFM-ready markdown sections."""

import os

from triage.common import format_bytes


def render(data, report_type, source_dir, config=None):
    """Render all parsed data as DFM-ready markdown sections.

    Args:
        data: dict with keys "env", "storage", "repo", "net", "perf"
        report_type: "sosreport" or "supportconfig"
        source_dir: basename of the source directory
        config: optional config dict

    Returns:
        str: complete markdown text
    """
    sections = []

    env = data.get("env", {})
    storage = data.get("storage", {})
    repo = data.get("repo", {})
    net = data.get("net", {})
    perf = data.get("perf", {})

    sections.append(_render_env(env, report_type, source_dir))
    sections.append(_render_storage(storage, report_type, source_dir))
    sections.append(_render_repo(repo, report_type, source_dir))
    sections.append(_render_net(net, report_type, source_dir))

    if perf and not perf.get("_skipped"):
        sections.append(_render_perf(perf, report_type, source_dir))

    return "\n".join(s for s in sections if s)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def _render_env(info, report_type, source_dir):
    lines = []
    lines.append(f"### Environment Summary")
    lines.append("")
    lines.append(f"Source: `{source_dir}/` ({report_type})")
    lines.append("")

    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| OS | {info.get('os', 'N/A')} |")
    lines.append(f"| Version | {info.get('os_version', 'N/A')} |")
    if info.get("variant"):
        lines.append(f"| Variant | {info['variant']} |")
    lines.append(f"| Kernel | {info.get('kernel', 'N/A')} |")
    lines.append(f"| Architecture | {info.get('architecture', 'N/A')} |")
    lines.append(f"| Hostname | {info.get('hostname', 'N/A')} |")
    lines.append(f"| CPUs | {info.get('cpus', 'N/A')} |")
    lines.append(f"| Memory | {info.get('memory_gb', 'N/A')} GB |")
    lines.append(f"| Manufacturer | {info.get('manufacturer', 'N/A')} |")
    lines.append(f"| Product | {info.get('product', 'N/A')} |")
    if info.get("boot_mode"):
        lines.append(f"| Boot Mode | {info['boot_mode']} |")
    if info.get("vm_generation"):
        lines.append(f"| VM Generation | {info['vm_generation']} |")
    if info.get("date"):
        lines.append(f"| Collected | {info['date']} |")
    if info.get("uptime"):
        lines.append(f"| Uptime | {info['uptime']} |")
    if info.get("billing"):
        lines.append(f"| Billing | {info['billing']} |")
    if info.get("cloud"):
        lines.append(f"| Cloud | {info['cloud']} |")
    lines.append("")

    # IMDS
    imds = info.get("imds", {})
    if imds and "error" not in imds:
        lines.append("**Azure IMDS**")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| VM Name | {imds.get('vm_name', 'N/A')} |")
        lines.append(f"| Resource Group | {imds.get('resource_group', 'N/A')} |")
        lines.append(f"| Subscription | {imds.get('subscription_id', 'N/A')} |")
        lines.append(f"| Location | {imds.get('location', 'N/A')} |")
        lines.append(f"| VM Size | {imds.get('vm_size', 'N/A')} |")
        lines.append(f"| VM ID | {imds.get('vm_id', 'N/A')} |")
        lines.append(f"| OS Type | {imds.get('os_type', 'N/A')} |")
        lines.append(f"| License Type | {imds.get('license_type', 'N/A')} |")
        lines.append(f"| Publisher | {imds.get('publisher', 'N/A')} |")
        lines.append(f"| Offer | {imds.get('offer', 'N/A')} |")
        lines.append(f"| SKU | {imds.get('sku', 'N/A')} |")
        if imds.get("security_type"):
            lines.append(f"| Security Type | {imds['security_type']} |")
        if imds.get("secure_boot"):
            lines.append(f"| Secure Boot | {imds['secure_boot']} |")
        if imds.get("vtpm"):
            lines.append(f"| vTPM | {imds['vtpm']} |")

        if imds.get("image_id") or imds.get("image_offer"):
            lines.append("")
            lines.append("**Image Reference**")
            lines.append("")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            if imds.get("image_id"):
                lines.append(f"| ID | {imds['image_id']} |")
            if imds.get("image_publisher"):
                lines.append(f"| Publisher | {imds['image_publisher']} |")
            if imds.get("image_offer"):
                lines.append(f"| Offer | {imds['image_offer']} |")
            if imds.get("image_sku"):
                lines.append(f"| SKU | {imds['image_sku']} |")
            if imds.get("image_version"):
                lines.append(f"| Version | {imds['image_version']} |")
        lines.append("")

    # Failed services
    failed = info.get("failed_services", [])
    lines.append("**Failed Services**")
    lines.append("")
    if failed:
        for svc in failed:
            lines.append(f"- `{svc}`")
    else:
        lines.append("None detected")
    lines.append("")

    # Subscription manager
    if info.get("subscription_manager"):
        lines.append("**Subscription Manager**")
        lines.append("")
        lines.append(f"```")
        lines.append(info["subscription_manager"])
        lines.append(f"```")
        lines.append("")

    # fstab
    if info.get("fstab"):
        lines.append("**`/etc/fstab`**")
        lines.append("")
        lines.append("```")
        for line in info["fstab"].splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(stripped)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _render_storage(data, report_type, source_dir):
    lines = []
    lines.append(f"### Storage Summary")
    lines.append("")
    lines.append(f"Source: `{source_dir}/` ({report_type})")
    lines.append("")

    # SCSI
    lsscsi = data.get("lsscsi", "").strip()
    if lsscsi:
        lines.append("**SCSI Devices**")
        lines.append("")
        lines.append("```")
        lines.append(lsscsi)
        lines.append("```")
        lines.append("")

    # NVMe
    nvme = data.get("nvme", "").strip()
    if nvme:
        lines.append("**NVMe Devices**")
        lines.append("")
        lines.append("```")
        lines.append(nvme)
        lines.append("```")
        lines.append("")
    else:
        lines.append("**NVMe Devices:** None detected")
        lines.append("")

    # Block devices
    lsblk = data.get("lsblk", "").strip()
    if lsblk:
        lines.append("**Block Devices (lsblk)**")
        lines.append("")
        lines.append("```")
        lines.append(lsblk)
        lines.append("```")
        lines.append("")

    # LVM
    pvs = data.get("pvs", "").strip()
    vgs = data.get("vgs", "").strip()
    lvs = data.get("lvs", "").strip()
    if pvs or vgs or lvs:
        lines.append("**LVM — Physical Volumes**")
        lines.append("")
        lines.append("```")
        lines.append(pvs if pvs else "(none)")
        lines.append("```")
        lines.append("")
        lines.append("**LVM — Volume Groups**")
        lines.append("")
        lines.append("```")
        lines.append(vgs if vgs else "(none)")
        lines.append("```")
        lines.append("")
        lines.append("**LVM — Logical Volumes**")
        lines.append("")
        lines.append("```")
        lines.append(lvs if lvs else "(none)")
        lines.append("```")
        lines.append("")
    else:
        lines.append("**LVM:** No LVM configuration detected")
        lines.append("")

    # Filesystem usage
    df_text = data.get("df_filtered", data.get("df", "")).strip()
    if df_text:
        lines.append("**Filesystem Usage (df)**")
        lines.append("")
        lines.append("```")
        lines.append(df_text)
        lines.append("```")
        lines.append("")

    # Mounts
    mount_text = data.get("mount_filtered", "").strip()
    findmnt = data.get("findmnt", "").strip()
    if mount_text:
        lines.append("**Mount Points (real filesystems)**")
        lines.append("")
        lines.append("```")
        lines.append(mount_text)
        lines.append("```")
        lines.append("")
    elif findmnt:
        lines.append("**Mount Points (findmnt)**")
        lines.append("")
        lines.append("```")
        lines.append(findmnt)
        lines.append("```")
        lines.append("")

    # Btrfs
    btrfs = data.get("btrfs", "").strip()
    if btrfs:
        lines.append("**Btrfs Status**")
        lines.append("")
        lines.append("```")
        lines.append(btrfs)
        lines.append("```")
        lines.append("")

    # Azure disk profile
    analysis = data.get("disk_analysis")
    if analysis:
        lines.append("**Azure Disk Profile**")
        lines.append("")
        lines.append(f"VM Size: `{analysis['vm_size']}`")
        vm_limit = analysis.get("vm_limit")
        if vm_limit:
            lines.append(
                f"VM Uncached Disk Cap: {vm_limit[0]:,} IOPS / {vm_limit[1]:,} MB/s"
            )
        else:
            lines.append(
                "VM Uncached Disk Cap: (not in lookup — verify manually)"
            )
        lines.append("")

        # Disk table
        disks = analysis.get("disks", [])
        if disks:
            lines.append(
                "| Role | LUN | Size | Tier | Type | IOPS | MB/s | Cache | WA |"
            )
            lines.append(
                "|------|-----|------|------|------|------|------|-------|-----|"
            )
            for d in disks:
                wa = "Yes" if d.get("write_accel") == "true" else "No"
                dtype_short = d.get("type", "").replace("_LRS", "")
                lines.append(
                    f"| {d['role']} | {d['lun']} | {d['size_gb']}G "
                    f"| {d.get('tier', '')} | {dtype_short} "
                    f"| {d.get('tier_iops', '')} | {d.get('tier_tput', '')} "
                    f"| {d.get('caching', '')} | {wa} |"
                )
            lines.append(
                f"| **TOTAL** | | | | "
                f"| **{analysis['total_iops']:,}** "
                f"| **{analysis['total_tput']:,}** | | |"
            )
            lines.append("")

        # Overcommit
        oc = analysis.get("overcommit")
        if oc:
            lines.append("**Overcommit Analysis**")
            lines.append("")
            iops_status = (
                "OVERCOMMITTED" if oc["iops_overcommitted"] else "OK"
            )
            tput_status = (
                "OVERCOMMITTED" if oc["tput_overcommitted"] else "OK"
            )
            lines.append(
                f"- IOPS: {oc['total_iops']:,} / {oc['vm_iops']:,} "
                f"({oc['iops_pct']:.1f}%) [{iops_status}]"
            )
            lines.append(
                f"- Throughput: {oc['total_tput']:,} / {oc['vm_tput']:,} "
                f"({oc['tput_pct']:.1f}%) [{tput_status}]"
            )
            if oc["iops_overcommitted"] or oc["tput_overcommitted"]:
                lines.append("")
                lines.append(
                    "⚠ Storage is OVERCOMMITTED — disks can deliver more "
                    "than the VM allows. Workloads may experience throttling "
                    "at the VM level."
                )
            else:
                headroom_iops = oc["vm_iops"] - oc["total_iops"]
                headroom_tput = oc["vm_tput"] - oc["total_tput"]
                lines.append(
                    f"- Headroom: {headroom_iops:,} IOPS / {headroom_tput:,} MB/s"
                )
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

def _render_repo(info, report_type, source_dir):
    lines = []
    lines.append(f"### Repository Summary")
    lines.append("")
    lines.append(f"Source: `{source_dir}/` ({report_type})")
    lines.append("")

    repo_type = info.get("type", "")

    if repo_type == "RHEL":
        return _render_rhel_repo(info, lines)
    return _render_sles_repo(info, lines)


def _render_rhel_repo(info, lines):
    lines.append(f"- **Subscription Manager:** {info.get('subscription_manager', 'N/A')}")
    if info.get("rhui_package"):
        lines.append(f"- **RHUI Package:** `{info['rhui_package']}`")
    lines.append(f"- **Update Channel:** {info.get('update_channel', 'N/A')}")
    lines.append("")

    # Enabled repos by source
    lines.append("**Enabled Repositories**")
    lines.append("")
    enabled = [r for r in info.get("repos", []) if r.get("enabled")]
    if not enabled:
        lines.append("None")
    else:
        sources = {}
        for r in enabled:
            sources.setdefault(r["source"], []).append(r)
        for source in [
            "RHUI", "Red Hat CDN", "Microsoft", "EPEL",
            "Third-party", "Unknown",
        ]:
            repos = sources.get(source, [])
            if not repos:
                continue
            lines.append(f"**[{source}]** ({len(repos)} repos)")
            lines.append("")
            for r in repos:
                lines.append(f"- `{r['id']}`")
                if r.get("baseurl"):
                    lines.append(f"  - {r['baseurl']}")
            lines.append("")

    # Disabled count
    disabled = [r for r in info.get("repos", []) if not r.get("enabled")]
    if disabled:
        lines.append(f"Disabled: {len(disabled)} repos (debug, source, etc.)")
        lines.append("")

    # Repo files
    repo_files = info.get("repo_files", [])
    if repo_files:
        lines.append("**Repo Files**")
        lines.append("")
        lines.append("| File | Status |")
        lines.append("|------|--------|")
        for rf in repo_files:
            fname = rf["file"]
            if rf.get("empty"):
                lines.append(f"| `{fname}` | (empty) |")
            elif rf.get("parse_error"):
                lines.append(f"| `{fname}` | (parse error) |")
            else:
                en = sum(1 for r in rf.get("repos", []) if r.get("enabled"))
                total = len(rf.get("repos", []))
                lines.append(f"| `{fname}` | {en}/{total} enabled |")
        lines.append("")

    # Warnings
    _render_inline_warnings(info, lines)

    return "\n".join(lines)


def _render_sles_repo(info, lines):
    lines.append(f"- **Update Channel:** {info.get('update_channel', 'N/A')}")
    lines.append("")

    # Modules/extensions
    modules = info.get("modules", {})
    if modules:
        lines.append("**Modules / Extensions**")
        lines.append("")
        lines.append("| Module | Enabled | Disabled |")
        lines.append("|--------|---------|----------|")
        for module, counts in sorted(modules.items()):
            lines.append(
                f"| {module} | {counts['enabled']} | {counts['disabled']} |"
            )
        lines.append("")

    # Enabled repos by source
    lines.append("**Enabled Repositories**")
    lines.append("")
    enabled = [r for r in info.get("repos", []) if r.get("enabled")]
    if not enabled:
        lines.append("None")
    else:
        sources = {}
        for r in enabled:
            sources.setdefault(r["source"], []).append(r)
        for source in [
            "SUSE Cloud (PAYG)", "SUSE SCC", "SUSE SMT/RMT",
            "Microsoft", "Third-party", "Unknown",
        ]:
            repos = sources.get(source, [])
            if not repos:
                continue
            lines.append(f"**[{source}]** ({len(repos)} repos)")
            lines.append("")
            for r in repos:
                lines.append(f"- {r.get('name', r.get('alias', ''))}")
            lines.append("")

    # Disabled count
    disabled = [r for r in info.get("repos", []) if not r.get("enabled")]
    if disabled:
        lines.append(f"Disabled: {len(disabled)} repos (debug, source, etc.)")
        lines.append("")

    # Warnings
    _render_inline_warnings(info, lines)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def _render_net(data, report_type, source_dir):
    lines = []
    lines.append(f"### Network Summary")
    lines.append("")
    lines.append(f"Source: `{source_dir}/` ({report_type})")
    lines.append("")

    # Interfaces table
    interfaces = data.get("interfaces", [])
    driver_map = data.get("driver_map", {})
    if interfaces:
        lines.append("**Interfaces**")
        lines.append("")
        lines.append("| Name | State | MAC | MTU | Driver | IPv4 Address |")
        lines.append("|------|-------|-----|-----|--------|-------------|")
        for iface in interfaces:
            name = iface["name"]
            if name == "lo":
                continue
            state = iface.get("state", "")
            mac = iface.get("mac", "") or "—"
            mtu = iface.get("mtu", "")
            driver = driver_map.get(name, "")
            ipv4_list = [a["addr"] for a in iface.get("ipv4", [])]
            ipv4_str = ", ".join(ipv4_list) if ipv4_list else "—"
            lines.append(
                f"| {name} | {state} | {mac} | {mtu} | {driver} | {ipv4_str} |"
            )
        lines.append("")

        # Accelerated networking
        if data.get("accelerated_networking"):
            lines.append(
                "**Accelerated Networking:** Enabled (mlx5_core VF detected)"
            )
        elif data.get("hv_netvsc_only"):
            lines.append(
                "**Accelerated Networking:** Not detected (hv_netvsc only)"
            )
        lines.append("")

    # Link statistics
    link_stats = data.get("link_stats", {})
    non_lo = {k: v for k, v in link_stats.items() if k != "lo"}
    has_traffic = any(
        v["rx_bytes"] > 0 or v["tx_bytes"] > 0 for v in non_lo.values()
    )
    if non_lo and has_traffic:
        lines.append("**Link Statistics**")
        lines.append("")
        lines.append(
            "| Interface | RX Bytes | RX Pkts | RX Err | RX Drop "
            "| TX Bytes | TX Pkts | TX Err | TX Drop |"
        )
        lines.append(
            "|-----------|----------|---------|--------|-------- "
            "|----------|---------|--------|---------|"
        )
        for iface, st in sorted(non_lo.items()):
            rx_b = format_bytes(st["rx_bytes"])
            tx_b = format_bytes(st["tx_bytes"])
            err = " ⚠" if st["rx_errors"] > 0 or st["tx_errors"] > 0 else ""
            drop = " ⚠" if st["rx_dropped"] > 0 or st["tx_dropped"] > 0 else ""
            lines.append(
                f"| {iface} | {rx_b} | {st['rx_packets']:,} "
                f"| {st['rx_errors']:,}{err} | {st['rx_dropped']:,}{drop} "
                f"| {tx_b} | {st['tx_packets']:,} "
                f"| {st['tx_errors']:,}{err} | {st['tx_dropped']:,}{drop} |"
            )
        lines.append("")

    # Routes
    routes = data.get("routes", [])
    if routes:
        lines.append("**Routes**")
        lines.append("")
        lines.append("| Destination | Via | Dev | Proto |")
        lines.append("|-------------|-----|-----|-------|")
        for r in routes:
            lines.append(
                f"| {r['dest']} | {r['via'] or '—'} "
                f"| {r['dev']} | {r['proto']} |"
            )
        lines.append("")

    # DNS
    resolv = data.get("resolv_conf", "").strip()
    if resolv:
        lines.append("**DNS Configuration**")
        lines.append("")
        lines.append("```")
        for line in resolv.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        lines.append("```")
        if "168.63.129.16" in resolv:
            lines.append("")
            lines.append("Note: Using Azure DNS (168.63.129.16)")
        lines.append("")

    # Firewall
    lines.append("**Firewall**")
    lines.append("")
    fw_zones = data.get("firewall_zones", "").strip()
    fw_service = data.get("firewall_service", "").strip()
    if fw_zones:
        if "FirewallD is not running" in fw_zones:
            lines.append("firewalld: not running")
        else:
            active_found = False
            for line in fw_zones.splitlines():
                if "(active)" in line:
                    active_found = True
                    lines.append(f"Active zone: {line.strip()}")
            if not active_found:
                lines.append("firewalld: running (no active zones)")
    elif fw_service:
        if "inactive" in fw_service or "dead" in fw_service:
            lines.append("firewalld: inactive/disabled")
        elif "active" in fw_service:
            lines.append("firewalld: active")
        else:
            lines.append("firewalld: status unknown")
    else:
        iptables = data.get("iptables", "").strip()
        nftables = data.get("nftables", "").strip()
        if iptables:
            rule_count = sum(
                1 for line in iptables.splitlines()
                if line.strip() and not line.startswith("Chain")
                and not line.startswith("target") and not line.startswith("num")
            )
            lines.append(
                f"firewalld: not available; iptables rules: {rule_count}"
            )
        elif nftables:
            lines.append("firewalld: not available; nftables in use")
        else:
            lines.append("Firewall status: not available")
    lines.append("")

    # Bonding
    bonding = data.get("bonding", {})
    if bonding:
        import re as _re
        lines.append("**Bonding**")
        lines.append("")
        for bond_name, bond_text in sorted(bonding.items()):
            mode_m = _re.search(r"Bonding Mode:\s*(.*)", bond_text)
            mode = mode_m.group(1) if mode_m else "unknown"
            slaves = _re.findall(r"Slave Interface:\s*(\S+)", bond_text)
            lines.append(
                f"- `{bond_name}`: mode={mode}, slaves={', '.join(slaves)}"
            )
        lines.append("")

    # Socket summary
    ss_s = data.get("ss_s", "").strip()
    if ss_s:
        lines.append("**Socket Summary**")
        lines.append("")
        lines.append("```")
        lines.append(ss_s)
        lines.append("```")
        lines.append("")

    # IMDS network
    imds_net = data.get("imds_network", {})
    if imds_net and imds_net.get("interface"):
        lines.append("**IMDS Network Metadata**")
        lines.append("")
        for idx, iface in enumerate(imds_net["interface"]):
            ipv4 = iface.get("ipv4", {})
            addrs = ipv4.get("ipAddress", [])
            subnets = ipv4.get("subnet", [])
            mac = iface.get("macAddress", "")
            mac_fmt = (
                ":".join(mac[i:i+2] for i in range(0, len(mac), 2)).lower()
                if mac and ":" not in mac else mac
            )
            subnet_str = ""
            if subnets:
                s = subnets[0]
                subnet_str = f"{s.get('address', '')}/{s.get('prefix', '')}"
            ip_strs = [a.get("privateIpAddress", "") for a in addrs]
            lines.append(f"- Interface {idx}: MAC `{mac_fmt}`")
            lines.append(f"  - Subnet: {subnet_str}")
            for ip in ip_strs:
                pub = ""
                for a in addrs:
                    if (a.get("privateIpAddress") == ip
                            and a.get("publicIpAddress")):
                        pub = f" (public: {a['publicIpAddress']})"
                lines.append(f"  - IP: {ip}{pub}")
        lines.append("")

    # Wicked (SLES)
    wicked = data.get("wicked_status", "").strip()
    if wicked:
        lines.append("**Wicked Interface Status**")
        lines.append("")
        lines.append("```")
        lines.append(wicked)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

def _render_perf(data, report_type, source_dir):
    lines = []
    lines.append(f"### Performance Summary")
    lines.append("")

    load = data.get("load_average")
    if load:
        lines.append(
            f"- **Load Average:** {load['avg_1']:.2f}, "
            f"{load['avg_5']:.2f}, {load['avg_15']:.2f}"
        )
        lines.append("")

    sar_cpu = data.get("sar_cpu")
    if sar_cpu:
        lines.append("**SAR CPU Average**")
        lines.append("")
        lines.append(
            f"- User: {sar_cpu['user']:.1f}%, System: {sar_cpu['system']:.1f}%, "
            f"IOWait: {sar_cpu['iowait']:.1f}%, Idle: {sar_cpu['idle']:.1f}%"
        )
        lines.append("")

    vmstat = data.get("vmstat_s", "").strip()
    if vmstat:
        lines.append("**vmstat -s**")
        lines.append("")
        lines.append("```")
        lines.append(vmstat)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_inline_warnings(info, lines):
    """Render warnings inline within a section."""
    warnings = info.get("_warnings", [])
    if warnings:
        lines.append("**Warnings**")
        lines.append("")
        for w in warnings:
            lines.append(f"- ⚠ {w['message']}")
        lines.append("")
