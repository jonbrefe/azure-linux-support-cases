"""Network parser — interfaces, routes, DNS, firewall, bonding, IMDS network."""

import json
import os
import re

from triage.common import (
    read_file,
    extract_scc_command,
    extract_scc_config,
    format_bytes,
    make_warning,
)


# ---------------------------------------------------------------------------
# Interface / stats / route parsing
# ---------------------------------------------------------------------------

def parse_interfaces(ip_addr_text):
    """Parse ip addr output into structured interface list."""
    interfaces = []
    current = None
    for line in ip_addr_text.splitlines():
        m = re.match(r"^\d+:\s+(\S+?):\s+<([^>]*)>\s*(.*)", line)
        if m:
            if current:
                interfaces.append(current)
            name = m.group(1).rstrip(":")
            rest = m.group(3)
            mtu_m = re.search(r"mtu\s+(\d+)", rest)
            state_m = re.search(r"state\s+(\S+)", rest)
            current = {
                "name": name,
                "mtu": mtu_m.group(1) if mtu_m else "",
                "state": state_m.group(1) if state_m else "",
                "mac": "",
                "ipv4": [],
                "ipv6": [],
                "driver": "",
            }
        elif current:
            stripped = line.strip()
            mac_m = re.match(r"link/ether\s+([0-9a-f:]+)", stripped)
            if mac_m:
                current["mac"] = mac_m.group(1)
            ip4_m = re.match(r"inet\s+(\S+)\s+.*scope\s+(\S+)", stripped)
            if ip4_m:
                current["ipv4"].append(
                    {"addr": ip4_m.group(1), "scope": ip4_m.group(2)}
                )
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
    section = None
    for line in ip_link_text.splitlines():
        m = re.match(r"^\d+:\s+(\S+?):", line)
        if m:
            current_iface = m.group(1).rstrip(":")
            stats[current_iface] = {
                "rx_bytes": 0, "tx_bytes": 0,
                "rx_packets": 0, "tx_packets": 0,
                "rx_errors": 0, "tx_errors": 0,
                "rx_dropped": 0, "tx_dropped": 0,
            }
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


def _parse_ethtool_driver(text):
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
        routes.append({"dest": dest, "via": via, "dev": dev, "proto": proto})
    return routes


def _parse_hwinfo_drivers(hwinfo_text):
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


def _parse_imds_network_supportconfig(metadata_path):
    """Parse network info from supportconfig IMDS metadata."""
    text = read_file(metadata_path)
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
# Main parser
# ---------------------------------------------------------------------------

def parse(path, report_type, config=None):
    """Extract network data from a sosreport or supportconfig directory.

    Returns:
        dict with network data, parsed interfaces/routes, _sources, _warnings.
    """
    if report_type == "sosreport":
        data = _extract_sosreport(path)
    else:
        data = _extract_supportconfig(path)

    # Parse structured data
    data["interfaces"] = parse_interfaces(data.get("ip_addr", ""))
    data["link_stats"] = parse_link_stats(data.get("ip_link", ""))
    data["routes"] = parse_routes(data.get("ip_route", ""))

    # Build driver map
    ethtool_drivers = data.get("ethtool_drivers", {})
    driver_map = {}
    for iface, text in ethtool_drivers.items():
        info = _parse_ethtool_driver(text)
        driver_map[iface] = info.get("driver", "")

    hwinfo = data.get("hwinfo_netcard", "")
    if hwinfo and not driver_map:
        driver_map = _parse_hwinfo_drivers(hwinfo)

    data["driver_map"] = driver_map

    # Accelerated networking detection
    has_an = any(d == "mlx5_core" for d in driver_map.values())
    all_hv = (
        set(driver_map.values()) - {""} == {"hv_netvsc"}
        if driver_map else False
    )
    data["accelerated_networking"] = has_an
    data["hv_netvsc_only"] = all_hv

    # Warnings
    data["_warnings"] = []

    # Check for errors/drops
    for iface, st in data["link_stats"].items():
        if iface == "lo":
            continue
        if st["rx_errors"] > 0 or st["tx_errors"] > 0:
            data["_warnings"].append(make_warning(
                "NET",
                f"Interface {iface} has RX/TX errors",
                evidence=(
                    f"RX errors: {st['rx_errors']:,}, "
                    f"TX errors: {st['tx_errors']:,}"
                ),
                impact="Network errors may indicate driver, cable, or congestion issues",
                next_step=f"Check ethtool -S {iface} for detailed error counters",
            ))
        if st["rx_dropped"] > 0 or st["tx_dropped"] > 0:
            data["_warnings"].append(make_warning(
                "NET",
                f"Interface {iface} has RX/TX drops",
                evidence=(
                    f"RX dropped: {st['rx_dropped']:,}, "
                    f"TX dropped: {st['tx_dropped']:,}"
                ),
                impact="Dropped packets may cause retransmissions or connection issues",
                next_step=(
                    f"Check ring buffer sizes (ethtool -g {iface}) "
                    f"and kernel drop counters"
                ),
            ))

    return data


# ---------------------------------------------------------------------------
# Sosreport extraction
# ---------------------------------------------------------------------------

def _extract_sosreport(path):
    """Extract network data from a sosreport directory."""
    net_dir = os.path.join(path, "sos_commands", "networking")
    nm_dir = os.path.join(path, "sos_commands", "networkmanager")
    fw_dir = os.path.join(path, "sos_commands", "firewalld")

    data = {
        "_sources": {
            "ip_addr": "sos_commands/networking/ip_-d_address",
            "ip_link": "sos_commands/networking/ip_-s_-d_link",
            "ip_route": "sos_commands/networking/ip_route_show_table_all",
            "resolv_conf": "etc/resolv.conf",
            "ethtool": "sos_commands/networking/ethtool_-i_*",
            "imds_network": "sos_commands/azure/instance_metadata.json",
        },
    }

    # Interfaces
    data["ip_addr"] = read_file(os.path.join(net_dir, "ip_-d_address"))
    if not data["ip_addr"].strip():
        data["ip_addr"] = read_file(os.path.join(net_dir, "ip_-o_addr"))
    data["ip_link"] = read_file(os.path.join(net_dir, "ip_-s_-d_link"))

    # Routes
    data["ip_route"] = read_file(
        os.path.join(net_dir, "ip_route_show_table_all")
    )

    # DNS
    data["resolv_conf"] = read_file(os.path.join(path, "etc", "resolv.conf"))

    # Hostname
    data["hostname"] = read_file(os.path.join(path, "hostname")).strip()
    if not data["hostname"]:
        data["hostname"] = read_file(
            os.path.join(path, "etc", "hostname")
        ).strip()

    # Ethtool driver info
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
        data["iptables"] = read_file(
            os.path.join(net_dir, "iptables_-t_filter_-nvL")
        )
        if not data.get("iptables", "").strip():
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

def _extract_supportconfig(path):
    """Extract network data from a supportconfig directory."""
    network_txt = read_file(os.path.join(path, "network.txt"))

    data = {
        "_sources": {
            "ip_addr": "network.txt",
            "ip_route": "network.txt",
            "resolv_conf": "network.txt",
            "imds_network": "public_cloud/metadata.txt",
        },
    }

    # Interfaces
    data["ip_addr"] = extract_scc_command(network_txt, r"# /sbin/ip addr$")
    data["ip_link"] = extract_scc_command(
        network_txt, r"# /sbin/ip -stats link$"
    )

    # Routes
    data["ip_route"] = extract_scc_command(
        network_txt, r"# /sbin/ip route show table main$"
    )
    if not data["ip_route"].strip():
        data["ip_route"] = extract_scc_command(
            network_txt, r"# /sbin/ip route$"
        )

    # DNS
    data["resolv_conf"] = extract_scc_config(
        network_txt, r"# /etc/resolv.conf$"
    )

    # Hostname
    data["hostname"] = extract_scc_command(
        network_txt, r"# /bin/hostname$"
    ).strip()
    if not data["hostname"]:
        data["hostname"] = extract_scc_command(
            network_txt, r"# /etc/HOSTNAME$"
        ).strip()

    # Wicked / NetworkManager / firewall status
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

    # Ethtool — supportconfig may not have per-interface ethtool
    data["ethtool_drivers"] = {}
    data["hwinfo_netcard"] = extract_scc_command(
        network_txt, r"# /usr/sbin/hwinfo --netcard$"
    )

    # IMDS network
    data["imds_network"] = {}
    metadata_path = os.path.join(path, "public_cloud", "metadata.txt")
    if os.path.isfile(metadata_path):
        data["imds_network"] = _parse_imds_network_supportconfig(metadata_path)

    return data
