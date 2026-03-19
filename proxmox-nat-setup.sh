#!/usr/bin/env bash
# Run ONCE as root on the Proxmox HOST.
# NAT rules are static — they always point to Nginx on this host.
# Nginx upstream is what gets updated on each deploy, not these rules.
set -euo pipefail

PUB_IFACE="eth0"    # Proxmox public network interface

# Enable IP forwarding (needed for LXC outbound traffic)
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Allow LXC containers to reach the internet (outbound NAT)
iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o "$PUB_IFACE" -j MASQUERADE
iptables -A FORWARD -i vmbr0 -o "$PUB_IFACE" -j ACCEPT
iptables -A FORWARD -i "$PUB_IFACE" -o vmbr0 -m state --state RELATED,ESTABLISHED -j ACCEPT

# Persist rules across reboots
apt-get install -y iptables-persistent
netfilter-persistent save

echo "✅ NAT rules set. Nginx on this host will route traffic to the current LXC."