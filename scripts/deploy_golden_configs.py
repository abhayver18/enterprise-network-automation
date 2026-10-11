import os
import sys
import yaml
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

def load_inventory(filepath):
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def deploy_config(device_info, defaults):
    hostname = device_info['hostname']
    ip = device_info['ip']
    cfg_path = device_info['config_file']

    if not os.path.exists(cfg_path):
        print(f"[-] Config file missing for {hostname}: {cfg_path}")
        return False

    device_params = {
        'device_type': defaults.get('device_type', 'cisco_ios'),
        'host': ip,
        'username': defaults['username'],
        'password': defaults['password'],
        'secret': defaults.get('secret', defaults['password']),
        'fast_cli': False
    }

    print(f"[*] Connecting to {hostname} ({ip})...")
    try:
        with ConnectHandler(**device_params) as net_connect:
            net_connect.enable()
            print(f"[+] Connected to {hostname}. Pushing {cfg_path}...")
            
            output = net_connect.send_config_from_file(cfg_path)
            net_connect.save_config()
            
            print(f"[✓] Successfully deployed and saved configuration on {hostname}!\n")
            return True

    except (NetmikoTimeoutException, NetmikoAuthenticationException) as err:
        print(f"[!] Authentication/Timeout failure on {hostname}: {err}\n")
        return False
    except Exception as e:
        print(f"[!] Unexpected error on {hostname}: {e}\n")
        return False

def select_devices(devices):
    print("\n" + "=" * 45)
    print("        TARGET DEVICE SELECTION")
    print("=" * 45)
    for idx, dev in enumerate(devices, start=1):
        print(f"  [{idx}] {dev['hostname']} ({dev['ip']})")
    print(f"  [A] All devices")
    print(f"  [Q] Quit")
    print("=" * 45)

    choice = input("Enter selection (e.g. 1, '1,2', or 'A'): ").strip()

    if choice.upper() == 'Q':
        print("[*] Aborted by user.")
        sys.exit(0)
    elif choice.upper() == 'A':
        return devices

    selected = []
    indices = [c.strip() for c in choice.split(',')]
    for item in indices:
        if item.isdigit():
            val = int(item)
            if 1 <= val <= len(devices):
                selected.append(devices[val - 1])
            else:
                print(f"[!] Skipping invalid selection index: {val}")
        else:
            # Also allow typing the hostname directly
            match = [d for d in devices if d['hostname'].lower() == item.lower()]
            if match:
                selected.extend(match)
            else:
                print(f"[!] Unknown device name or index: {item}")

    if not selected:
        print("[!] No valid devices selected. Exiting.")
        sys.exit(1)

    return selected

def main():
    inventory_path = "inventory/devices.yaml"
    if not os.path.exists(inventory_path):
        print(f"Error: Inventory file '{inventory_path}' not found.")
        sys.exit(1)

    inv = load_inventory(inventory_path)
    defaults = inv.get('defaults', {})
    all_devices = inv.get('devices', [])

    if not all_devices:
        print(f"Error: No devices found in '{inventory_path}'.")
        sys.exit(1)

    target_devices = select_devices(all_devices)

    print("\n" + "=" * 45)
    print(f"Deploying to: {', '.join(d['hostname'] for d in target_devices)}")
    print("=" * 45 + "\n")

    results = {}
    for dev in target_devices:
        status = deploy_config(dev, defaults)
        results[dev['hostname']] = "PASS" if status else "FAIL"

    print("=" * 45)
    print("           DEPLOYMENT SUMMARY")
    print("=" * 45)
    for host, res in results.items():
        print(f"{host:<20}: {res}")
    print("=" * 45)

if __name__ == "__main__":
    main()
