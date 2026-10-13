#!/usr/bin/env python3
import sys
import re
import yaml
from netmiko import ConnectHandler

INVENTORY_FILE = "inventory/devices.yaml"
TARGET_HOSTNAMES = ["SP-P1", "SP-PE1", "SP-PE2", "SP-PE3"]

def load_inventory():
    try:
        with open(INVENTORY_FILE, "r") as f:
            data = yaml.safe_load(f)
        defaults = data.get("defaults", {})
        devices = [d for d in data.get("devices", []) if d.get("hostname") in TARGET_HOSTNAMES]
        return defaults, devices
    except Exception as e:
        print(f"[!] Error loading inventory file: {e}")
        sys.exit(1)

def run_command(net_connect, cmd):
    try:
        return net_connect.send_command(cmd)
    except Exception as e:
        return f"ERROR: {e}"

def parse_ospf(output):
    """Checks if OSPF neighbors exist and are in FULL state."""
    full_count = len(re.findall(r'\bFULL/', output))
    init_or_down = len(re.findall(r'\b(2WAY|INIT|EXSTART|EXCHANGE|LOADING|DOWN)/', output))
    if full_count > 0 and init_or_down == 0:
        return f"PASS ({full_count} FULL)"
    elif full_count > 0 and init_or_down > 0:
        return f"WARN ({full_count} FULL, {init_or_down} NOT FULL)"
    elif "OSPF not enabled" in output or not output.strip():
        return "N/A or NONE"
    return "FAIL (No FULL)"

def parse_ldp(output):
    """Checks if LDP neighbors are in Oper state."""
    oper_count = len(re.findall(r'State:\s*Oper', output, re.IGNORECASE))
    non_oper = len(re.findall(r'State:\s*(?!Oper\b)\w+', output, re.IGNORECASE))
    if oper_count > 0 and non_oper == 0:
        return f"PASS ({oper_count} Oper)"
    elif oper_count > 0 and non_oper > 0:
        return f"WARN ({oper_count} Oper, {non_oper} DOWN)"
    elif not output.strip():
        return "FAIL (0 peers)"
    return "FAIL"

def parse_bgp_vpnv4(output, is_p_router=False):
    """Strictly matches valid IPv4 neighbor rows in the summary table."""
    if is_p_router:
        return "N/A (P Core)"
    
    peers = 0
    established = 0
    for line in output.strip().splitlines():
        # Match only lines starting with an IPv4 address
        if re.match(r'^\d{1,3}(?:\.\d{1,3}){3}\s+', line.strip()):
            parts = line.strip().split()
            if len(parts) >= 10:
                peers += 1
                last_col = parts[-1]
                # Established peers display integer received prefixes
                if last_col.isdigit():
                    established += 1

    if peers > 0 and established == peers:
        return f"PASS ({established}/{peers} Up)"
    elif peers > 0:
        return f"FAIL ({established}/{peers} Up)"
    return "N/A / No Peers"

def parse_vrf(output, is_p_router=False):
    """Checks if VRF routes exist on PE routers."""
    if is_p_router:
        return "N/A (P Core)"
    if "Routing Table: ENTERPRISE" in output or "ENTERPRISE" in output:
        route_lines = [l for l in output.splitlines() if re.match(r'^[BCOSD]\b', l.strip())]
        if route_lines:
            return f"PASS ({len(route_lines)} routes)"
        return "WARN (VRF up, 0 routes)"
    return "FAIL (VRF missing)"

def verify_device(device_info, defaults):
    hostname = device_info.get("hostname")
    host_ip = device_info.get("ip") or device_info.get("host")
    is_p_router = (hostname == "SP-P1")

    dev_params = {
        "device_type": defaults.get("device_type", "cisco_ios"),
        "host": host_ip,
        "username": defaults.get("username", "automation"),
        "password": defaults.get("password", "cisco123"),
        "secret": defaults.get("secret", "cisco123"),
        "global_delay_factor": defaults.get("global_delay_factor", 1),
        "fast_cli": False,
    }

    results = {
        "hostname": hostname,
        "ip": host_ip,
        "ssh": "FAIL",
        "ospf": "N/A",
        "ldp": "N/A",
        "vpnv4": "N/A",
        "vrf": "N/A"
    }

    print(f"[*] Connecting to {hostname} ({host_ip})...")
    try:
        with ConnectHandler(**dev_params) as net_connect:
            net_connect.enable()
            results["ssh"] = "OK"

            # 1. OSPF
            out_ospf = run_command(net_connect, "show ip ospf neighbor")
            results["ospf"] = parse_ospf(out_ospf)

            # 2. LDP
            out_ldp = run_command(net_connect, "show mpls ldp neighbor")
            results["ldp"] = parse_ldp(out_ldp)

            # 3. MP-BGP VPNv4
            out_bgp = run_command(net_connect, "show ip bgp vpnv4 all summary")
            results["vpnv4"] = parse_bgp_vpnv4(out_bgp, is_p_router)

            # 4. VRF Routing
            out_vrf = run_command(net_connect, "show ip route vrf ENTERPRISE")
            results["vrf"] = parse_vrf(out_vrf, is_p_router)

    except Exception as e:
        results["ssh"] = f"FAIL ({e.__class__.__name__})"

    return results

def main():
    defaults, devices = load_inventory()
    if not devices:
        print("[!] No matching SP devices found in inventory.")
        sys.exit(1)

    print("=" * 82)
    print(" SERVICE PROVIDER CORE COMPLIANCE & STATE VERIFICATION")
    print("=" * 82)

    summary_list = []
    for dev in sorted(devices, key=lambda x: x["hostname"]):
        summary_list.append(verify_device(dev, defaults))

    print("\n" + "=" * 82)
    print(f"{'HOSTNAME':<10} {'IP':<16} {'SSH':<8} {'OSPF':<15} {'MPLS LDP':<15} {'MP-BGP':<14} {'VRF'}")
    print("-" * 82)
    for r in summary_list:
        print(f"{r['hostname']:<10} {r['ip']:<16} {r['ssh']:<8} {r['ospf']:<15} {r['ldp']:<15} {r['vpnv4']:<14} {r['vrf']}")
    print("=" * 82)

if __name__ == "__main__":
    main()
