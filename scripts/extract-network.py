#!/usr/bin/env python3
"""Extract network information from sosreport or supportconfig.

Covers: interfaces (IP addresses, MACs, MTU, state), routes, DNS configuration,
ethtool driver info (hv_netvsc / mlx5_core for accelerated networking detection),
firewall status, bonding/teaming, socket summary, and IMDS network metadata.
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


def extract_scc_command(text, command_pattern):
    """Extract output of a command from supportconfig section files."""
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


# ---------------------------------------------------------------------------
# Sosreport extraction
# ---------------------------------------------------------------------------

def extract_sosreport(path):
    """Extract network data from a sosreport directory."""
    net_dir = os.path.join(path, "sos_commands", "networking")
    nm_dir = os.path.join(path, "sos_commands", "networkmanager")
    fw_dir = os.path.join(path, "sos_commands", "firewalld")

    data = {}

    # Interfaces
    data["ip_addr"] = read_file(os.path.join(net_dir, "ip_-d_address"))
    if not data["ip_addr"].strip():
        data["ip_addr"] = read_file(os.path.join(net_dir, "ip_-o_addr"))
    data["ip_link"] = read_file(os.path.join(net_dir, "ip_-s_-d_link"))

    # Routes
    data["ip_route"] = read_file(os.path.join(net_dir, "ip_route_show_table_all"))

    # DNS
    data["resolv_conf"] = read_file(os.path.join(path, "etc", "resolv.conf"))

    # Hostname
    data["hostname"] = read_file(os.path.join(path, "hostname")).strip()
    if not data["hostname"]:
        data["hostname"] = read_file(os.path.join(path, "etc", "hostname")).strip()

    # Ethtool driver info — discover interfaces
    data["ethtool_drivers"] = {}
    if os.path.isdir(net_dir):
        for fname in sorted(os.listdir(net_dir)):
            if fname.startswith("ethtool_-i_") and not fname.endswith("_lo"):
                iface = fname[len("ethtool_-i_"):]
                data["ethtool_drivers"][iface] = read_file(
                    os.path.join(net_dir, fname)
                )

    # Socket summary
    data["ss_s"] = read_file(os.path.join(net_dir, "ss_-s"))

    # Firewall
    data["firewall_zones"] = read_file(
        os.path.join(fw_dir, "firewall-cmd_--list-all-zones")
    )
    if not data["firewall_zones"].strip():
        # Check iptables
        data["iptables"] = read_file(
            os.path.join(net_dir, "iptables_-t_filter_-nvL")
        )
        if not data["iptables"].strip():
            # Try nftables
            data["nftables"] = read_file(
                os.path.join(net_dir, "nft_list_ruleset")
            )

    # NetworkManager
    data["nmcli_dev"] = read_file(os.path.join(nm_dir, "nmcli_dev"))
    data["nmcli_general"] = read_file(
        os.path.join(nm_dir, "nmcli_general_status")
    )

    # Bonding
    bond_dir = os.path.join(path, "proc", "net", "bonding")
    data["bonding"] = {}
    if os.path.isdir(bond_dir):
        for fname in sorted(os.listdir(bond_dir)):
            data["bonding"][fname] = read_file(os.path.join(bond_dir, fname))

    # IMDS network
    imds_path = os.path.join(
        path, "sos_commands", "azure", "instance_metadata.json"
    )
    data["imds_network"] = {}
    try:
        with open(imds_path, "r") as f:
            imds = json.load(f)
        data["imds_network"] = imds.get("network", {})
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    return data


# ---------------------------------------------------------------------------
# Supportconfig extraction
# ---------------------------------------------------------------------------

def extract_supportconfig(path):
    """Extract network data from a supportconfig directory."""
    network_txt = read_file(os.path.join(path, "network.txt"))

    data = {}

    # Interfaces
    data["ip_addr"] = extract_scc_command(network_txt, r"# /sbin/ip addr$")
    data["ip_link"] = extract_scc_command(network_txt, r"# /sbin/ip -stats link$")

    # Routes
    data["ip_route"] = extract_scc_command(
        network_txt, r"# /sbin/ip route show table main$"
    )
    if not data["ip_route"].strip():
        data["ip_route"] = extract_scc_command(network_txt, r"# /sbin/ip route$")

    # DNS
    data["resolv_conf"] = extract_scc_config(network_txt, r"# /etc/resolv.conf$")

    # Hostname
    data["hostname"] = extract_scc_command(network_txt, r"# /bin/hostname$").strip()
    if not data["hostname"]:
        data["hostname"] = extract_scc_command(
            network_txt, r"# /etc/HOSTNAME$"
        ).strip()

    # Wicked or NetworkManager status
    data["network_service"] = extract_scc_command(
        network_txt, r"# /bin/systemctl status network.service$"
    )
    data["firewall_service"] = extract_scc_command(
        network_txt, r"# /bin/systemctl status firewalld.service$"
    )
    data["wicked_status"] = extract_scc_command(
        network_txt, r"# /usr/sbin/wicked ifstatus --verbose all$"
    )

    # Socket summary
    data["ss_s"] = extract_scc_command(network_txt, r"# /usr/sbin/ss -s$")
    if not data["ss_s"].strip():
        data["ss_s"] = extract_scc_command(network_txt, r"# /usr/bin/ss -s$")

    # Ethtool — supportconfig doesn't always have per-interface ethtool
    data["ethtool_drivers"] = {}
    # Try hwinfo for NIC driver info
    data["hwinfo_netcard"] = extract_scc_command(
        network_txt, r"# /usr/sbin/hwinfo --netcard$"
    )

    # IMDS network
    data["imds_network"] = {}
    metadata_path = os.path.join(path, "public_cloud", "metadata.txt")
    if os.path.isfile(metadata_path):
        data["imds_network"] = parse_imds_network_supportconfig(metadata_path)

    return data


def parse_imds_network_supportconfig(metadata_path):
    """Parse network info from supportconfig IMDS metadata."""
    text = read_file(metadata_path)
    # Try to find JSON block
    lines = text.splitlines()
    in_json = False
    json_lines = []
    brace_depth = 0
    for line in lines:
        stripped = line.strip()
        if not in_json and stripped.startswith("{"):
            in_json = True
        if in_json:
            json_lines.append(line)
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth <= 0:
                break
    if json_lines:
        try:
            d = json.loads("\n".join(json_lines))
            return d.get("network", {})
        except json.JSONDecodeError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Interface parsing
# ---------------------------------------------------------------------------

def parse_interfaces(ip_addr_text):
    """Parse ip addr output into structured interface list."""
    interfaces = []
    current = None
    for line in ip_addr_text.splitlines():
        # Interface line: "2: eth0: <flags> mtu 1500 ..."
        m = re.match(r"^\d+:\s+(\S+?):\s+<([^>]*)>\s*(.*)", line)
        if m:
            if current:
                interfaces.append(current)
            name = m.group(1).rstrip(":")
            flags = m.group(2)
            rest = m.group(3)
            mtu_m = re.search(r"mtu\s+(\d+)", rest)
            state_m = re.search(r"state\s+(\S+)", rest)
            current = {
                "name": name,
                "flags": flags,
                "mtu": mtu_m.group(1) if mtu_m else "",
                "state": state_m.group(1) if state_m else "",
                "mac": "",
                "ipv4": [],
                "ipv6": [],
                "driver": "",
            }
        elif current:
            stripped = line.strip()
            # MAC address
            mac_m = re.match(r"link/ether\s+([0-9a-f:]+)", stripped)
            if mac_m:
                current["mac"] = mac_m.group(1)
            # IPv4
            ip4_m = re.match(r"inet\s+(\S+)\s+.*scope\s+(\S+)", stripped)
            if ip4_m:
                current["ipv4"].append(
                    {"addr": ip4_m.group(1), "scope": ip4_m.group(2)}
                )
            # IPv6
            ip6_m = re.match(r"inet6\s+(\S+)\s+.*scope\s+(\S+)", stripped)
            if ip6_m:
                current["ipv6"].append(
                    {"addr": ip6_m.group(1), "scope": ip6_m.group(2)}
                )
    if current:
        interfaces.append(current)
    return interfaces


def parse_link_stats(ip_link_text):
    """Parse ip -s -d link output for RX/TX stats per interface."""
    stats = {}
    current_iface = None
    section = None  # "RX" or "TX"
    for line in ip_link_text.splitlines():
        m = re.match(r"^\d+:\s+(\S+?):", line)
        if m:
            current_iface = m.group(1).rstrip(":")
            stats[current_iface] = {"rx_bytes": 0, "tx_bytes": 0,
                                     "rx_packets": 0, "tx_packets": 0,
                                     "rx_errors": 0, "tx_errors": 0,
                                     "rx_dropped": 0, "tx_dropped": 0}
            section = None
            continue
        if current_iface:
            stripped = line.strip()
            if stripped.startswith("RX:"):
                section = "RX"
                continue
            elif stripped.startswith("TX:"):
                section = "TX"
                continue
            if section and stripped and not stripped.startswith("link/"):
                parts = stripped.split()
                if len(parts) >= 4 and parts[0].isdigit():
                    if section == "RX":
                        stats[current_iface]["rx_bytes"] = int(parts[0])
                        stats[current_iface]["rx_packets"] = int(parts[1])
                        stats[current_iface]["rx_errors"] = int(parts[2])
                        stats[current_iface]["rx_dropped"] = int(parts[3])
                    elif section == "TX":
                        stats[current_iface]["tx_bytes"] = int(parts[0])
                        stats[current_iface]["tx_packets"] = int(parts[1])
                        stats[current_iface]["tx_errors"] = int(parts[2])
                        stats[current_iface]["tx_dropped"] = int(parts[3])
                    section = None
    return stats


def parse_ethtool_driver(text):
    """Parse ethtool -i output, return dict with driver, version, etc."""
    info = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            info[key.strip()] = val.strip()
    return info


def parse_routes(route_text):
    """Parse ip route output into a list of route dicts."""
    routes = []
    for line in route_text.splitlines():
        line = line.strip()
        if not line or line.startswith("broadcast") or line.startswith("local"):
            continue
        parts = line.split()
        if len(parts) < 1:
            continue
        dest = parts[0]
        via = ""
        dev = ""
        proto = ""
        for i, p in enumerate(parts):
            if p == "via" and i + 1 < len(parts):
                via = parts[i + 1]
            elif p == "dev" and i + 1 < len(parts):
                dev = parts[i + 1]
            elif p == "proto" and i + 1 < len(parts):
                proto = parts[i + 1]
        routes.append({
            "dest": dest, "via": via, "dev": dev, "proto": proto
        })
    return routes


def format_bytes(n):
    """Format byte count to human-readable."""
    if n >= 1_000_000_000_000:
        return f"{n / 1_000_000_000_000:.1f} TB"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_section(title):
    """Print a section header."""
    print()
    print(f"  {'─' * 60}")
    print(f"  {title}")
    print(f"  {'─' * 60}")


def print_report(data, report_type, path):
    """Print formatted network summary."""
    dirname = os.path.basename(path.rstrip("/"))
    print(f"{'=' * 70}")
    print(f"  Network Summary — {report_type}")
    print(f"  Source: {dirname}/")
    print(f"{'=' * 70}")

    # --- Interfaces ---
    print_section("Interfaces")
    interfaces = parse_interfaces(data.get("ip_addr", ""))
    link_stats = parse_link_stats(data.get("ip_link", ""))
    ethtool_drivers = data.get("ethtool_drivers", {})

    if not interfaces:
        print("    (no interface data available)")
    else:
        # Build driver map
        driver_map = {}
        for iface, text in ethtool_drivers.items():
            info = parse_ethtool_driver(text)
            driver_map[iface] = info.get("driver", "")

        # Also check hwinfo for supportconfig
        hwinfo = data.get("hwinfo_netcard", "")
        if hwinfo and not driver_map:
            driver_map = parse_hwinfo_drivers(hwinfo)

        # Detect accelerated networking
        has_an = any(d == "mlx5_core" for d in driver_map.values())

        # Print table
        print(f"    {'Name':<16} {'State':<8} {'MAC':<19} {'MTU':<6} {'Driver':<12} {'IPv4 Address'}")
        print(f"    {'─' * 16} {'─' * 8} {'─' * 19} {'─' * 6} {'─' * 12} {'─' * 20}")
        for iface in interfaces:
            name = iface["name"]
            if name == "lo":
                continue
            state = iface["state"]
            mac = iface["mac"] or "—"
            mtu = iface["mtu"]
            driver = driver_map.get(name, "")
            ipv4_list = [a["addr"] for a in iface["ipv4"]]
            ipv4_str = ", ".join(ipv4_list) if ipv4_list else "—"
            print(f"    {name:<16} {state:<8} {mac:<19} {mtu:<6} {driver:<12} {ipv4_str}")

        if has_an:
            print()
            print("    **Accelerated Networking:** Enabled (mlx5_core VF detected)")
        else:
            # Check if only hv_netvsc
            drivers = set(driver_map.values()) - {""}
            if drivers and drivers <= {"hv_netvsc"}:
                print()
                print("    **Accelerated Networking:** Not detected (hv_netvsc only)")

    # --- Link Statistics ---
    if link_stats:
        non_lo = {k: v for k, v in link_stats.items() if k != "lo"}
        has_errors = any(
            v["rx_errors"] > 0 or v["tx_errors"] > 0 or
            v["rx_dropped"] > 0 or v["tx_dropped"] > 0
            for v in non_lo.values()
        )
        if has_errors or any(
            v["rx_bytes"] > 0 or v["tx_bytes"] > 0 for v in non_lo.values()
        ):
            print_section("Link Statistics")
            print(f"    {'Interface':<16} {'RX Bytes':>12} {'RX Pkts':>12} {'RX Err':>8} {'RX Drop':>8} {'TX Bytes':>12} {'TX Pkts':>12} {'TX Err':>8} {'TX Drop':>8}")
            print(f"    {'─' * 16} {'─' * 12} {'─' * 12} {'─' * 8} {'─' * 8} {'─' * 12} {'─' * 12} {'─' * 8} {'─' * 8}")
            for iface, st in sorted(non_lo.items()):
                rx_b = format_bytes(st["rx_bytes"])
                tx_b = format_bytes(st["tx_bytes"])
                err_flag = ""
                if st["rx_errors"] > 0 or st["tx_errors"] > 0:
                    err_flag = " ⚠"
                drop_flag = ""
                if st["rx_dropped"] > 0 or st["tx_dropped"] > 0:
                    drop_flag = " ⚠"
                print(f"    {iface:<16} {rx_b:>12} {st['rx_packets']:>12,} {st['rx_errors']:>8,}{err_flag} {st['rx_dropped']:>8,}{drop_flag} {tx_b:>12} {st['tx_packets']:>12,} {st['tx_errors']:>8,}{err_flag} {st['tx_dropped']:>8,}{drop_flag}")

    # --- Routes ---
    print_section("Routes")
    routes = parse_routes(data.get("ip_route", ""))
    if not routes:
        print("    (no routing data available)")
    else:
        print(f"    {'Destination':<22} {'Via':<18} {'Dev':<12} {'Proto'}")
        print(f"    {'─' * 22} {'─' * 18} {'─' * 12} {'─' * 10}")
        for r in routes:
            print(f"    {r['dest']:<22} {r['via'] or '—':<18} {r['dev']:<12} {r['proto']}")

    # --- DNS ---
    print_section("DNS Configuration")
    resolv = data.get("resolv_conf", "").strip()
    if resolv:
        for line in resolv.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                print(f"    {line}")
        # Check for Azure DNS
        if "168.63.129.16" in resolv:
            print()
            print("    Note: Using Azure DNS (168.63.129.16)")
    else:
        print("    (resolv.conf not available)")

    # --- Firewall ---
    print_section("Firewall")
    fw_zones = data.get("firewall_zones", "").strip()
    fw_service = data.get("firewall_service", "").strip()
    if fw_zones:
        if "FirewallD is not running" in fw_zones:
            print("    firewalld: not running")
        else:
            # Show active zones only
            active_found = False
            for line in fw_zones.splitlines():
                if "(active)" in line:
                    active_found = True
                    print(f"    Active zone: {line.strip()}")
            if not active_found:
                print("    firewalld: running (no active zones)")
    elif fw_service:
        if "inactive" in fw_service or "dead" in fw_service:
            print("    firewalld: inactive/disabled")
        elif "active" in fw_service:
            print("    firewalld: active")
        else:
            print("    firewalld: status unknown")
    else:
        iptables = data.get("iptables", "").strip()
        nftables = data.get("nftables", "").strip()
        if iptables:
            # Count non-default rules
            rule_count = sum(
                1 for line in iptables.splitlines()
                if line.strip() and not line.startswith("Chain") and
                not line.startswith("target") and
                not line.startswith("num")
            )
            print(f"    firewalld: not available; iptables rules: {rule_count}")
        elif nftables:
            print("    firewalld: not available; nftables in use")
        else:
            print("    Firewall status: not available")

    # --- Bonding ---
    bonding = data.get("bonding", {})
    if bonding:
        print_section("Bonding")
        for bond_name, bond_text in sorted(bonding.items()):
            mode_m = re.search(r"Bonding Mode:\s*(.*)", bond_text)
            mode = mode_m.group(1) if mode_m else "unknown"
            slaves = re.findall(r"Slave Interface:\s*(\S+)", bond_text)
            print(f"    {bond_name}: mode={mode}, slaves={', '.join(slaves)}")

    # --- Socket Summary ---
    ss_s = data.get("ss_s", "").strip()
    if ss_s:
        print_section("Socket Summary")
        for line in ss_s.splitlines():
            print(f"    {line}")

    # --- IMDS Network ---
    imds_net = data.get("imds_network", {})
    if imds_net and imds_net.get("interface"):
        print_section("IMDS Network Metadata")
        for idx, iface in enumerate(imds_net["interface"]):
            ipv4 = iface.get("ipv4", {})
            addrs = ipv4.get("ipAddress", [])
            subnets = ipv4.get("subnet", [])
            mac = iface.get("macAddress", "")
            mac_fmt = ":".join(
                mac[i:i+2] for i in range(0, len(mac), 2)
            ).lower() if mac and ":" not in mac else mac
            subnet_str = ""
            if subnets:
                s = subnets[0]
                subnet_str = f"{s.get('address', '')}/{s.get('prefix', '')}"
            ip_strs = [a.get("privateIpAddress", "") for a in addrs]
            print(f"    Interface {idx}: MAC {mac_fmt}")
            print(f"      Subnet: {subnet_str}")
            for ip in ip_strs:
                pub = ""
                for a in addrs:
                    if a.get("privateIpAddress") == ip and a.get("publicIpAddress"):
                        pub = f" (public: {a['publicIpAddress']})"
                print(f"      IP: {ip}{pub}")

    # --- Wicked (SLES) ---
    wicked = data.get("wicked_status", "").strip()
    if wicked:
        print_section("Wicked Interface Status")
        for line in wicked.splitlines():
            print(f"    {line}")

    print()


def parse_hwinfo_drivers(hwinfo_text):
    """Parse hwinfo --netcard output to extract driver names per interface."""
    drivers = {}
    current_driver = ""
    current_device = ""
    for line in hwinfo_text.splitlines():
        stripped = line.strip()
        m = re.match(r"Driver:\s+\"(\S+)\"", stripped)
        if m:
            current_driver = m.group(1)
        m2 = re.match(r"Device File:\s+(\S+)", stripped)
        if m2:
            current_device = m2.group(1)
        if stripped == "" and current_driver and current_device:
            drivers[current_device] = current_driver
            current_driver = ""
            current_device = ""
    if current_driver and current_device:
        drivers[current_device] = current_driver
    return drivers


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
