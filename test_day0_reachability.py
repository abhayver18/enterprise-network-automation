import socket
import yaml
from concurrent.futures import ThreadPoolExecutor
from netmiko import ConnectHandler

USERNAME = "automation"
PASSWORD = "cisco123"

def check_tcp_port(ip, port=22, timeout=2):
    """Fast pre-check to confirm SSH socket is open."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def test_device(device):
    name = device["name"]
    ip = device["ip"]

    # Phase 1: Port 22 check
    if not check_tcp_port(ip):
        return (False, f"[-] {name:<10} ({ip:<15}) -> UNREACHABLE (Port 22 closed/unreachable)")

    # Phase 2: Netmiko login
    conn_params = {
        "device_type": "cisco_ios",
        "host": ip,
        "username": USERNAME,
        "password": PASSWORD,
        "fast_cli": True,
        "timeout": 5,
        "conn_timeout": 5,
    }

    try:
        with ConnectHandler(**conn_params) as net_connect:
            prompt = net_connect.find_prompt()
            return (True, f"[+] {name:<10} ({ip:<15}) -> SUCCESS (Prompt: {prompt})")
    except Exception as exc:
        return (False, f"[-] {name:<10} ({ip:<15}) -> AUTH/CLI FAILED ({exc})")

def main():
    inventory_path = "inventory_day0.yaml"
    with open(inventory_path, "r") as f:
        config = yaml.safe_load(f)
    devices = config.get("devices", [])

    print(f"\n=======================================================")
    print(f" Checking Day-0 SSH Reachability across {len(devices)} Devices")
    print(f"=======================================================\n")

    success_count = 0
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(test_device, devices))

    # Print sorted output
    for success, log in sorted(results, key=lambda x: x[0], reverse=True):
        print(log)
        if success:
            success_count += 1

    print(f"\n-------------------------------------------------------")
    print(f"Summary: {success_count}/{len(devices)} devices operational via SSH.")
    print(f"-------------------------------------------------------\n")

if __name__ == "__main__":
    main()
