#!/usr/bin/env bash
# Run ONCE as root on the Proxmox HOST.
# NAT rules cover the entire LXC subnet — no per-container rules needed.
set -euo pipefail

PUB_IFACE="eth0"
LXC_SUBNET="10.10.10.0/24"

echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Allow LXC containers to reach the internet
iptables -t nat -A POSTROUTING -s "$LXC_SUBNET" -o "$PUB_IFACE" -j MASQUERADE
iptables -A FORWARD -i vmbr0 -o "$PUB_IFACE" -j ACCEPT
iptables -A FORWARD -i "$PUB_IFACE" -o vmbr0 -m state \
  --state RELATED,ESTABLISHED -j ACCEPT

apt-get install -y iptables-persistent
netfilter-persistent save

echo "✅ NAT rules set for subnet $LXC_SUBNET"