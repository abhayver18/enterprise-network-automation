#!/usr/bin/env python3
import sys
import re
import yaml
from netmiko import ConnectHandler

INVENTORY_FILE = "inventory/devices.yaml"

def load_inventory():
    try:
        with open(INVENTORY_FILE, "r") as f:
            data = yaml.safe_load(f)
        defaults = data.get("defaults", {})
        ces = {d["hostname"]: d for d in data.get("devices", []) if d.get("hostname") in ["HYD-R1", "PUNE-R1"]}
        return defaults, ces
    except Exception as e:
        print(f"[!] Error reading inventory: {e}")
        sys.exit(1)

def run_cmd(conn, cmd):
    try:
        return conn.send_command(cmd)
    except Exception as e:
        return f"ERROR: {e}"

def check_ce(device_info, defaults, test_target_ip, source_ip):
    hostname = device_info["hostname"]
    host_ip = device_info.get("ip") or device_info.get("host")
    
    dev_params = {
        "device_type": defaults.get("device_type", "cisco_ios"),
        "host": host_ip,
        "username": defaults.get("username", "automation"),
        "password": defaults.get("password", "cisco123"),
        "secret": defaults.get("secret", "cisco123"),
        "global_delay_factor": 1,
        "fast_cli": False,
    }

    print(f"\n[*] Testing from {hostname} ({host_ip})...")
    try:
        with ConnectHandler(**dev_params) as conn:
            conn.enable()

            # 1. PE-CE Route Check
            route_out = run_cmd(conn, f"show ip route {test_target_ip}")
            has_route = "Known via" in route_out or "Routing entry for" in route_out
            print(f"    - Route to remote site ({test_target_ip}): {'FOUND' if has_route else 'MISSING'}")

            # 2. End-to-End Ping Test
            ping_cmd = f"ping {test_target_ip} source {source_ip} repeat 5"
            ping_out = run_cmd(conn, ping_cmd)
            match = re.search(r'Success rate is (\d+) percent \((\d+)/(\d+)\)', ping_out)
            
            if match:
                rate = match.group(1)
                count = f"{match.group(2)}/{match.group(3)}"
                status = "PASS" if rate == "100" else ("DEGRADED" if int(rate) > 0 else "FAIL")
                print(f"    - End-to-End Ping ({source_ip} -> {test_target_ip}): {status} ({rate}%, {count})")
            else:
                print(f"    - End-to-End Ping: FAILED (No response)")

            # 3. Path Traceroute Check
            tr_cmd = f"traceroute {test_target_ip} source {source_ip} numeric probe 1"
            tr_out = run_cmd(conn, tr_cmd)
            mpls_hops = len(re.findall(r'MPLS: label \d+', tr_out))
            print(f"    - Core MPLS Encapsulation: {'CONFIRMED (' + str(mpls_hops) + ' labeled hops)' if mpls_hops > 0 else 'UNLABELED / DIRECT'}")

    except Exception as e:
        print(f"[!] SSH Connection failure on {hostname}: {e}")

def main():
    defaults, ces = load_inventory()
    if "HYD-R1" not in ces or "PUNE-R1" not in ces:
        print("[!] HYD-R1 or PUNE-R1 missing from inventory.")
        sys.exit(1)

    print("=" * 70)
    print(" CUSTOMER BRANCH-TO-BRANCH END-TO-END VALIDATION")
    print("=" * 70)

    # Hyderabad (LAN: 10.20.10.1) -> Pune (LAN: 10.30.10.1)
    check_ce(ces["HYD-R1"], defaults, test_target_ip="10.30.10.1", source_ip="10.20.10.1")

    # Pune (LAN: 10.30.10.1) -> Hyderabad (LAN: 10.20.10.1)
    check_ce(ces["PUNE-R1"], defaults, test_target_ip="10.20.10.1", source_ip="10.30.10.1")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
