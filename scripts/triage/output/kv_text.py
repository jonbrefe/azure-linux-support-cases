"""Compact key-value text output — consistent labels with separators."""

from triage.common import format_bytes


def render(data, report_type, source_dir, config=None):
    """Render all parsed data as compact KV text with separators.

    Args:
        data: dict with keys "env", "storage", "repo", "net", "perf"
        report_type: "sosreport" or "supportconfig"
        source_dir: basename of the source directory
        config: optional config dict

    Returns:
        str: compact KV text report
    """
    lines = []
    sep = "=" * 70
    sub = "─" * 50

    env = data.get("env", {})
    storage = data.get("storage", {})
    repo = data.get("repo", {})
    net = data.get("net", {})
    perf = data.get("perf", {})

    # Header
    lines.append(sep)
    lines.append(f"  Triage Summary — {report_type}")
    lines.append(f"  Source: {source_dir}/")
    lines.append(sep)

    # --- Environment ---
    lines.append("")
    lines.append(f"  {sub}")
    lines.append("  ENVIRONMENT")
    lines.append(f"  {sub}")
    lines.append(f"  OS:            {env.get('os', 'N/A')}")
    lines.append(f"  Version:       {env.get('os_version', 'N/A')}")
    if env.get("variant"):
        lines.append(f"  Variant:       {env['variant']}")
    lines.append(f"  Kernel:        {env.get('kernel', 'N/A')}")
    lines.append(f"  Architecture:  {env.get('architecture', 'N/A')}")
    lines.append(f"  Hostname:      {env.get('hostname', 'N/A')}")
    lines.append(f"  CPUs:          {env.get('cpus', 'N/A')}")
    lines.append(f"  Memory:        {env.get('memory_gb', 'N/A')} GB")
    lines.append(f"  Manufacturer:  {env.get('manufacturer', 'N/A')}")
    lines.append(f"  Product:       {env.get('product', 'N/A')}")
    if env.get("date"):
        lines.append(f"  Collected:     {env['date']}")
    if env.get("uptime"):
        lines.append(f"  Uptime:        {env['uptime']}")
    if env.get("billing"):
        lines.append(f"  Billing:       {env['billing']}")
    if env.get("cloud"):
        lines.append(f"  Cloud:         {env['cloud']}")

    # IMDS
    imds = env.get("imds", {})
    if imds and "error" not in imds:
        lines.append("")
        lines.append(f"  {sub}")
        lines.append("  AZURE IMDS")
        lines.append(f"  {sub}")
        lines.append(f"  VM Name:         {imds.get('vm_name', 'N/A')}")
        lines.append(f"  Resource Group:  {imds.get('resource_group', 'N/A')}")
        lines.append(f"  Subscription:    {imds.get('subscription_id', 'N/A')}")
        lines.append(f"  Location:        {imds.get('location', 'N/A')}")
        lines.append(f"  VM Size:         {imds.get('vm_size', 'N/A')}")
        lines.append(f"  VM ID:           {imds.get('vm_id', 'N/A')}")
        lines.append(f"  OS Type:         {imds.get('os_type', 'N/A')}")
        lines.append(f"  License Type:    {imds.get('license_type', 'N/A')}")
        lines.append(f"  Publisher:       {imds.get('publisher', 'N/A')}")
        lines.append(f"  Offer:           {imds.get('offer', 'N/A')}")
        lines.append(f"  SKU:             {imds.get('sku', 'N/A')}")

    # Failed services
    failed = env.get("failed_services", [])
    lines.append("")
    lines.append(f"  {sub}")
    lines.append("  FAILED SERVICES")
    lines.append(f"  {sub}")
    if failed:
        for svc in failed:
            lines.append(f"  ● {svc}")
    else:
        lines.append("  None detected")

    # --- Repository ---
    lines.append("")
    lines.append(f"  {sub}")
    lines.append("  REPOSITORY")
    lines.append(f"  {sub}")
    if repo.get("type") == "RHEL":
        lines.append(f"  Sub Manager:   {repo.get('subscription_manager', 'N/A')}")
        if repo.get("rhui_package"):
            lines.append(f"  RHUI Package:  {repo['rhui_package']}")
    lines.append(f"  Update Channel: {repo.get('update_channel', 'N/A')}")
    enabled_repos = [r for r in repo.get("repos", []) if r.get("enabled")]
    lines.append(f"  Enabled Repos:  {len(enabled_repos)}")
    disabled_repos = [r for r in repo.get("repos", []) if not r.get("enabled")]
    lines.append(f"  Disabled Repos: {len(disabled_repos)}")

    # --- Storage ---
    analysis = storage.get("disk_analysis")
    if analysis:
        lines.append("")
        lines.append(f"  {sub}")
        lines.append("  AZURE DISK PROFILE")
        lines.append(f"  {sub}")
        lines.append(f"  VM Size:       {analysis['vm_size']}")
        vm_limit = analysis.get("vm_limit")
        if vm_limit:
            lines.append(f"  VM IOPS Cap:   {vm_limit[0]:,}")
            lines.append(f"  VM MB/s Cap:   {vm_limit[1]:,}")
        lines.append(f"  Total IOPS:    {analysis['total_iops']:,}")
        lines.append(f"  Total MB/s:    {analysis['total_tput']:,}")

        oc = analysis.get("overcommit")
        if oc:
            iops_status = "OVERCOMMITTED" if oc["iops_overcommitted"] else "OK"
            tput_status = "OVERCOMMITTED" if oc["tput_overcommitted"] else "OK"
            lines.append(f"  IOPS Status:   {iops_status} ({oc['iops_pct']:.1f}%)")
            lines.append(f"  Tput Status:   {tput_status} ({oc['tput_pct']:.1f}%)")

    # LVM summary
    pvs = storage.get("pvs", "").strip()
    vgs = storage.get("vgs", "").strip()
    lvs = storage.get("lvs", "").strip()
    if pvs or vgs or lvs:
        lines.append("")
        lines.append(f"  {sub}")
        lines.append("  LVM")
        lines.append(f"  {sub}")
        lines.append(f"  Has LVM:       Yes")
    else:
        lines.append("")
        lines.append(f"  LVM:           No")

    # --- Network ---
    lines.append("")
    lines.append(f"  {sub}")
    lines.append("  NETWORK")
    lines.append(f"  {sub}")
    interfaces = net.get("interfaces", [])
    real_ifaces = [i for i in interfaces if i["name"] != "lo"]
    lines.append(f"  Interfaces:    {len(real_ifaces)}")
    if net.get("accelerated_networking"):
        lines.append(f"  Accel Net:     Enabled (mlx5_core)")
    elif net.get("hv_netvsc_only"):
        lines.append(f"  Accel Net:     Not detected (hv_netvsc only)")

    driver_map = net.get("driver_map", {})
    for iface in real_ifaces:
        name = iface["name"]
        ipv4_list = [a["addr"] for a in iface.get("ipv4", [])]
        ipv4_str = ", ".join(ipv4_list) if ipv4_list else "—"
        driver = driver_map.get(name, "")
        lines.append(
            f"  {name:16s} {iface.get('state', ''):8s} "
            f"{driver:12s} {ipv4_str}"
        )

    resolv = net.get("resolv_conf", "").strip()
    if "168.63.129.16" in resolv:
        lines.append(f"  Azure DNS:     Yes (168.63.129.16)")

    # --- Performance ---
    if perf and not perf.get("_skipped"):
        lines.append("")
        lines.append(f"  {sub}")
        lines.append("  PERFORMANCE")
        lines.append(f"  {sub}")
        load = perf.get("load_average")
        if load:
            lines.append(
                f"  Load Avg:      {load['avg_1']:.2f}, "
                f"{load['avg_5']:.2f}, {load['avg_15']:.2f}"
            )
        sar_cpu = perf.get("sar_cpu")
        if sar_cpu:
            lines.append(
                f"  CPU (sar avg): user={sar_cpu['user']:.1f}% "
                f"sys={sar_cpu['system']:.1f}% "
                f"iowait={sar_cpu['iowait']:.1f}% "
                f"idle={sar_cpu['idle']:.1f}%"
            )

    lines.append("")
    lines.append(sep)
    lines.append("")

    return "\n".join(lines)
