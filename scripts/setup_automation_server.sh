#!/bin/bash
set -e

echo "[+] 1. Configuring persistent Netplan on ens2 & ens3..."
sudo bash -c 'cat << "NETPLAN" > /etc/netplan/01-netcfg.yaml
network:
  version: 2
  ethernets:
    ens2:
      dhcp4: false
      addresses:
        - 10.10.30.10/24
      routes:
        - to: 10.255.0.1/32
          via: 10.10.30.1
          metric: 100
        - to: 10.0.0.0/16
          via: 10.10.30.1
          metric: 100
        - to: 10.10.31.0/24
          via: 10.10.30.1
          metric: 100
    ens3:
      dhcp4: true
NETPLAN'

sudo chmod 600 /etc/netplan/01-netcfg.yaml
sudo netplan apply

echo "[+] 2. Clearing old SSH host keys..."
mkdir -p "$HOME/.ssh"
for host in 10.10.30.1 10.10.30.11 10.10.31.1 10.10.31.12 10.0.0.1 10.0.0.2 10.0.0.9 10.0.0.10; do
  ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$host" 2>/dev/null || true
done

echo "[+] 3. Verifying connectivity..."
echo "--- Interfaces ---"
ip -br addr show ens2 ens3
echo "--- Routes ---"
ip route show | grep -E "10.10.30|10.10.31|10.0.0.0"

echo "[✓] Automation server network initialized successfully."
